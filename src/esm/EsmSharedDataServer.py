import glob
import json
import logging
import os
import re
import shutil
import signal
import socket
import threading
import dirhash
import humanize
import socketserver
import time
from typing import List
from functools import cached_property
from pathlib import Path
from limits import parse
from esm import Tools
from esm.ConfigModels import MainConfig
from esm.DataTypes import ZipFile
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmHttpThrottledHandler import EsmHttpThrottledHandler
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.exceptions import RequirementsNotFulfilledError, SafetyException

log = logging.getLogger(__name__)

@Service
class EsmSharedDataServer:
    """
    ESM shared data server.
    This will automatically create the shared data zips and provide a dedicated webserver to serve them.
    This supports files for manual download as well as the new SharedDataURL-Feature since v1.11.7
    """
    _httpServerWorker: threading.Thread = None
    _httpServer: socketserver.BaseServer = None
    _activeConnections: set[socket.socket] = set()

    @cached_property
    def config(self) -> MainConfig:
        return self.configService.config
    
    @cached_property
    def configService(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    def dedicatedServer(self) -> EsmDedicatedServer:
        return ServiceRegistry.get(EsmDedicatedServer)

    def start(self, wait: bool = False, forceRecreate: bool=False):
        """
            prepare the files and start the shared data server
            if wait = false, you will have to call stop() to stop the server
        """
        zipFiles = self.ensureZipFilesAreUpToDate(forceRecreate)
        self.prepareIndexHtml(zipFiles)
        self.startServer(zipFiles, wait=wait)

    def resume(self, wait: bool = False):
        """
            just resume the shared data server, do not recreate the files nor change configuration
            if wait = false, you will have to call stop() to stop the server
        """
        zipFiles = self.findZipFiles()
        if len(zipFiles) < 1 or len(zipFiles) > 2:
            raise RequirementsNotFulfilledError(f"Expected 2 zip files in the wwwroot folder, found {len(zipFiles)}. Aborting resume since files might be missing, start the server without the resume option to regenerate the data.")
        self.startServer(zipFiles, wait=wait)

    def stop(self):
        if len(self._activeConnections) > 0:
            self.closeActiveConnections()
        if self._httpServer:
            self._httpServer.shutdown()
        if self._httpServerWorker:
            self._httpServerWorker.join()
        self.stopServing()

    def closeActiveConnections(self):
        log.warning(f"Closing {len(self._activeConnections)} active connections")
        for sock in list(self._activeConnections):  # Iterate over a copy to avoid modification issues
            try:
                log.debug(f"Closing connection: {sock.getpeername()}")
                sock.settimeout(1)
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except OSError as e:
                log.warning(f"Error closing socket {sock.getpeername()}: {e}")

    def startServer(self, zipFiles: List[ZipFile], wait: bool = False):
        """
            prepare the files and start the download server
        """
        self.checkSharedDataURLConfiguration()

        log.info(f"Server configured to allow max {humanize.naturalsize(self.config.downloadtool.maxGlobalBandwith, gnu=False)}/s in total network bandwidth.")
        log.info(f"Server configured to allow max {humanize.naturalsize(self.config.downloadtool.maxClientBandwith, gnu=False)}/s network bandwith per connection.")

        servingUrlRoot = self.getServingUrlRoot()
        log.debug(f"Server root url is set to: '{servingUrlRoot}'")
        
        manualZipFile = Tools.findZipFileByName(zipFiles, startsWith=self.config.downloadtool.manualZipName)
        if manualZipFile:
            servingUrlManualZip = f"{servingUrlRoot}/{manualZipFile.name}"
            log.info(f"Shared data zip file for manual download is at: '{servingUrlManualZip}' (instructions: '{servingUrlRoot}')")

        if self.config.downloadtool.useSharedDataURLFeature:
            autoZipFile = Tools.findZipFileByName(zipFiles, startsWith=self.config.downloadtool.autoZipName.split(".")[0])
            if not autoZipFile:
                raise SafetyException(f"Could not find auto zip file with name '{self.config.downloadtool.autoZipName}' in the wwwroot folder. You probably need to recreate the zip files.")
            
            sharedDataUrl = self.getSharedDataURL(servingUrlRoot, autoZipFile)

            log.info(f"Shared data zip file for server is at: '{sharedDataUrl}'")
            log.warning(f"Using this SharedDataURL feature is dangerous! Make sure the URL above will be reachable for all your players, or it might break some clients! Read the data/readme_shareddata.md for more information.")

            if self.config.downloadtool.autoEditDedicatedYaml:
                self.configService.backupDedicatedYaml()
                # actually alter the dedicated.yaml, changing or adding the shareddataurl to what we just created
                sharedDataUrl = f"_{sharedDataUrl}"
                self.configService.changeSharedDataUrl(sharedDataUrl)

                # check if the configuration of the dedicated yaml (we will not make any changes to it) has the auto zip url configured properly
                self.checkDedicatedYamlHasAutoZipUrl(sharedDataUrl)
                if not self.config.downloadtool.startWithMainServer:
                    log.warning(f"The dedicated yaml has been updated to point to the shared data tool, make sure to restart the server for it to take effect!")
            else:
                log.warning(f"You turned off the autoEditDedicatedYaml feature. The dedicated yaml will NOT be updated automatically, make sure it the correct url! Otherwise it might break the game!")
        if wait:
            self.startServingAndWait(zipFiles)
        else:
            self.startServing(zipFiles)

    def startServingAndWait(self, zipFiles: List[ZipFile]):
        log.info(f"Starting download server for {len(zipFiles)} zip files (excluding default assets).")
        def NoOp(*args):
            raise KeyboardInterrupt()
        try:
            signal.signal(signal.SIGINT, NoOp)
            log.info(f"Press CTRL+C to stop the server.")
            self.serve(zipFiles)
        except KeyboardInterrupt:
            log.info(f"SharedData server shutting down.")
        finally:
            log.info(f"SharedData server stopped serving. Total downloads: {EsmHttpThrottledHandler.globalZipDownloads}")
            
            if self.config.downloadtool.useSharedDataURLFeature and self.config.downloadtool.autoEditDedicatedYaml:
                self.configService.removeSharedDataUrl()
                if not self.config.downloadtool.startWithMainServer:
                    log.warning(f"The dedicated yaml has been rolled back to its original state, make sure to restart the server for it to take effect!")

    def startServing(self, zipFiles: List[ZipFile]):
        log.info(f"Starting download server for {len(zipFiles)} zip files (excluding default assets).")
        def doServe():
            self.serve(zipFiles)
        self._httpServerWorker = threading.Thread(target=doServe, daemon=True)
        self._httpServerWorker.start()

    def stopServing(self):
        log.info(f"SharedData server stopped serving. Total downloads: {EsmHttpThrottledHandler.globalZipDownloads}")
        if self.config.downloadtool.useSharedDataURLFeature and self.config.downloadtool.autoEditDedicatedYaml:
            self.configService.removeSharedDataUrl()
            if not self.config.downloadtool.startWithMainServer:
                log.warning(f"The dedicated yaml has been rolled back to its original state, make sure to restart the server for it to take effect!")

    def getSharedDataURL(self, servingUrlRoot, autoZipFile: ZipFile):
        if len(self.config.downloadtool.customSharedDataURL) > 1:
            log.warning(f"Server configured to use a custom shared data url: '{self.config.downloadtool.customSharedDataURL}', make sure it is reachable for all your players, or it might break the game!")
            return self.config.downloadtool.customSharedDataURL
        else:
            return f"{servingUrlRoot}/{autoZipFile.name}"

    def getServingUrlRoot(self):
        if len(self.config.downloadtool.customExternalHostNameAndPort) > 1:
            log.debug(f"Server configured to use a custom external host name and port: '{self.config.downloadtool.customExternalHostNameAndPort}'")
            return self.config.downloadtool.customExternalHostNameAndPort
        else:
            myHostIp = Tools.getOwnIp(self.config)
            return f"http://{myHostIp}:{self.config.downloadtool.serverPort}"

    def ensureZipFilesAreUpToDate(self, forceRecreate=False) -> List[ZipFile]:
        """
            ensure that the zip files for download are up to date, comparing the hashdb with the scenario
        """
        scenarioName = self.config.dedicatedConfig.GameConfig.CustomScenario
        pathToScenarioFolder = Path(f"{self.config.paths.install}/Content/Scenarios/{scenarioName}").resolve()
        pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData")

        if forceRecreate:
            return self.prepareZipFiles(pathToSharedDataFolder)

        log.info(f"Checking if shared data folder '{pathToSharedDataFolder}' has been updated...")
        oldHash = self.readHashfile()
        newHash = self.calculateHashForDir(pathToSharedDataFolder)
        
        if oldHash == newHash:
            log.info(f"Shared data folder '{pathToSharedDataFolder}' has not been modified, no need to update the shared data zip files.")
            return self.findZipFiles()
        else:
            log.info(f"Shared data folder '{pathToSharedDataFolder}' has been modified.")
            return self.prepareZipFiles(pathToSharedDataFolder)

    def writeHashfile(self, pathToSharedDataFolder: Path):
        """
            write the hash to file
        """
        newHash = self.calculateHashForDir(pathToSharedDataFolder)
        pathToHashfile = Path(self.config.downloadtool.wwwroot).joinpath("shareddata.md5").resolve()
        with open(pathToHashfile, "w") as f:
            json.dump(newHash, f, indent=4)

    def calculateHashForDir(self, pathToFolder: Path) -> str:
        """
            calculates the md5 hash of the given folder including all its content
        """
        with Tools.Timer() as timer:
            log.debug(f"Checking if the folder '{pathToFolder}' has been updated...")
            # create a hash from the whole shared data folder using dirhash
            # do not use jobs > 1, since multiprocessing doesn't work with the distributed executable :/
            newHash = dirhash.dirhash(pathToFolder, match="**", algorithm="md5", jobs=1)
        log.debug(f"Checked folder '{pathToFolder}' in {timer.elapsedTime} seconds.")
        return newHash

    def readHashfile(self) -> dict:
        """
            read and return the hash from file
        """
        pathToHashDb = Path(self.config.downloadtool.wwwroot).joinpath("shareddata.md5").resolve()
        hashDb = {}
        if pathToHashDb.is_file():
            with open(pathToHashDb, "r") as f:
                hashDb = json.load(f)
        return hashDb

    def prepareZipFiles(self, pathToSharedDataFolder: Path) -> List[ZipFile]:
        """
            prepare the zip files for download by creating them and moving them to the wwwroot folder
        """
        log.info(f"Creating new shared data zip files from '{pathToSharedDataFolder}' for download.")
        zipFiles = self.createSharedDataZipFiles(pathToSharedDataFolder)
        zipFiles = self.moveSharedDataZipFilesToWwwroot(zipFiles)
        self.writeHashfile(pathToSharedDataFolder)

        for zipFile in zipFiles:
            log.info(f"Created SharedData zip file as '{zipFile.wwwrootPath}' with a size of '{humanize.naturalsize(zipFile.size, gnu=False)}'.")
        return zipFiles
    
    def findZipFiles(self) -> List[ZipFile]:
        """
        find the zip files that we need to serve
        """
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        zipFiles = []

        # check if there is a manual zip file
        manualZipFilePath = wwwroot.joinpath(self.config.downloadtool.manualZipName)
        if manualZipFilePath.exists():
            log.info(f"Found manual shared data zip file '{manualZipFilePath.name}'")
            zipFiles.append(ZipFile(name=self.config.downloadtool.manualZipName, path=manualZipFilePath, size=manualZipFilePath.stat().st_size))

        if self.config.downloadtool.useSharedDataURLFeature:
            # check if there are auto zip files, if so, add the latest
            filePattern = f"{wwwroot.resolve()}/{self.config.downloadtool.autoZipName.split(".")[0]}*.zip"
            files = glob.glob(pathname=filePattern)
            if len(files) > 0:
                path = Path(max(files, key=os.path.getmtime))
                if path.exists():
                    log.info(f"Found auto shared data zip file '{path.name}'")
                    zipFiles.append(ZipFile(name=path.name, path=path, size=path.stat().st_size))

        return zipFiles

    def checkSharedDataURLConfiguration(self):
        """
        check that the dedicated yaml has the auto zip url configured properly, and warn about it if not
        """
        if not self.config.downloadtool.useSharedDataURLFeature and self.config.dedicatedConfig.GameConfig.SharedDataURL is not None:
            if self.config.dedicatedConfig.GameConfig.SharedDataURL.startswith(f"_http://{Tools.getOwnIp(self.config)}:"):
                log.warning(f"The SharedDataURL seems to point to the shared data tool, but the useSharedDataURLFeature toggle is set to false. Please check the configuration of the downloadtool.")

    def checkDedicatedYamlHasAutoZipUrl(self, expectedConfiguration):
        """
        check that the dedicated yaml has the configuration we expect, and warn if not.
        """
        if self.config.dedicatedConfig.GameConfig.SharedDataURL == expectedConfiguration:
            log.debug(f"The dedicated yaml has the correct SharedDataURL configuration: '{self.config.dedicatedConfig.GameConfig.SharedDataURL}'.")
        else:
            dedicatedYamlPath = Path(self.config.paths.install).joinpath(self.config.server.dedicatedYaml).resolve()
            log.warning(f"The dedicated yaml '{dedicatedYamlPath}' has an incorrect SharedDataURL configuration: '{self.config.dedicatedConfig.GameConfig.SharedDataURL}'. Expected: '{expectedConfiguration}'")
    
    def replaceInTemplate(self, content: str, placeholder, value):
        if value:
            return content.replace(placeholder, str(value))
        else:
            return content.replace(placeholder, "")
    
    def prepareIndexHtml(self, zipFiles: List[ZipFile]):
        """
         copy the index.template.html into the wwwroot folder and replace placeholders
        """
        indexTemplateFilePath = Path("data/index.template.html").resolve()

        autoZipFileName = ""
        if self.config.downloadtool.useSharedDataURLFeature:
            indexTemplateFilePath = Path("data/index.shared.template.html").resolve()
            autoZipFile = Tools.findZipFileByName(zipFiles, startsWith=self.config.downloadtool.autoZipName.split(".")[0])
            if autoZipFile is not None:
                autoZipFileName = autoZipFile.name

        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        content = indexTemplateFilePath.read_text()
        content = self.replaceInTemplate(content, "$SHAREDDATAZIPFILENAME", self.config.downloadtool.manualZipName)
        content = self.replaceInTemplate(content, "$SHAREDDATAAUTOZIPFILE", autoZipFileName)
        content = self.replaceInTemplate(content, "$CACHEFOLDERNAME", self.getCacheFolderName())
        content = self.replaceInTemplate(content, "$SRV_NAME", self.config.dedicatedConfig.ServerConfig.Srv_Name)
        content = self.replaceInTemplate(content, "$SRV_DESCRIPTION", self.config.dedicatedConfig.ServerConfig.Srv_Description)
        content = self.replaceInTemplate(content, "$SRV_PASSWORD", self.config.dedicatedConfig.ServerConfig.Srv_Password)
        content = self.replaceInTemplate(content, "$SRV_MAXPLAYERS", self.config.dedicatedConfig.ServerConfig.Srv_MaxPlayers)
        content = self.replaceInTemplate(content, "$SRV_PORT", self.config.dedicatedConfig.ServerConfig.Srv_Port)
        content = self.replaceInTemplate(content, "$SRV_IP", Tools.getOwnIp(self.config))
        content = self.replaceInTemplate(content, "$MAXALLOWEDSIZECLASS", self.config.dedicatedConfig.ServerConfig.MaxAllowedSizeClass)
        content = self.replaceInTemplate(content, "$PLAYERLOGINPARALLELCOUNT", self.config.dedicatedConfig.ServerConfig.PlayerLoginParallelCount)
        content = self.replaceInTemplate(content, "$PLAYERLOGINFULLSERVERQUEUECOUNT", self.config.dedicatedConfig.ServerConfig.PlayerLoginFullServerQueueCount)
        
        indexFilePath = wwwroot.joinpath("index.html").resolve()
        if indexFilePath.exists():
            FsTools.deleteFile(indexFilePath)
        indexFilePath.write_text(content)
        log.debug(f"Created index.html at '{indexFilePath}'")

    def moveSharedDataZipFilesToWwwroot(self, zipFiles: List[ZipFile]) -> List[ZipFile]:
        """
        move the zip files to the wwwroot folder
        """
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()

        if not wwwroot.exists():
            FsTools.createDir(wwwroot)

        # clean up directory first by deleting all zip files
        filePattern = f"{wwwroot.resolve()}/*.zip"
        files = glob.glob(pathname=filePattern)
        for file in files:
            filePath = Path(file)
            if filePath.exists():
                log.debug(f"Deleting old zip file at '{file}'")
                FsTools.deleteFile(filePath)

        for zipFile in zipFiles:
            wwwrootZipFilePath = wwwroot.joinpath(zipFile.name).resolve()
            if wwwrootZipFilePath.exists():
                log.debug(f"Deleting old zip file at '{wwwrootZipFilePath}'")
                FsTools.deleteFile(wwwrootZipFilePath)
            log.debug(f"Moving zip file '{zipFile.path}' to '{wwwroot}'")
            shutil.move(zipFile.path, wwwroot)
            log.debug(f"result of zip creation: '{wwwrootZipFilePath}'")
            zipFile.wwwrootPath = wwwrootZipFilePath
        return zipFiles
    
    def findUniqueGameId(self):
        """
        return the unique game id from the first found log file that contains that string.

        This is the line in Logs/4243/Dedicated_*.log
        16-19:45:13.388 21_45 -LOG- Mode=currentId, GameSeed=42069420, UniqueId=1519611569, EntityId=5001
        """
        # find gameserver logfile and extract unique game id
        buildNumber = self.dedicatedServer().getBuildNumber()
        logFilePattern = "Dedicated_*.log"
        logFileDirectoryPath = self.config.paths.install.joinpath(f"Logs")
        logFileDirectoryForCurrentBuildPath = logFileDirectoryPath.joinpath(buildNumber).resolve()
        log.debug(f"Trying to extract unique game id from logfiles in '{logFileDirectoryForCurrentBuildPath}' with pattern '{logFilePattern}'")

        for possiblePath in glob.glob(root_dir=logFileDirectoryForCurrentBuildPath, pathname=logFilePattern, recursive=True):
            logFilePath = Path(logFileDirectoryForCurrentBuildPath).joinpath(possiblePath).resolve()
            uniqueGameId = self.readUniqueGameId(logFilePath)
            if uniqueGameId is not None:
                return uniqueGameId
        log.debug(f"Did not find unique game id in any of the {logFilePattern} files in '{logFileDirectoryForCurrentBuildPath}', will try the whole log folder again")

        # try the whole log folder again
        for possiblePath in glob.glob(root_dir=logFileDirectoryPath, pathname=f"**/{logFilePattern}", recursive=True):
            logFilePath = Path(logFileDirectoryPath).joinpath(possiblePath).resolve()
            uniqueGameId = self.readUniqueGameId(logFilePath)
            if uniqueGameId is not None:
                return uniqueGameId

        log.warning(f"Did not find unique game id in any of the {logFilePattern} files in '{logFileDirectoryPath}'. You may need to start the server at least once so esm can find out the id.")
        return None

    def readUniqueGameId(self, logFilePath: Path):
        if logFilePath.exists():
            log.debug(f"Trying to extract unique game id from logfile '{logFilePath}'")
            with open(logFilePath, 'r') as f:
                for line in f:
                    if "UniqueId" in line:
                        # extract unique game id from logline, which is the number after the 'UniqueId=' string
                        uniqueGameId = re.search(r"UniqueId=(\d+)", line).group(1)
                        return uniqueGameId
    
    def getUniqueGameId(self):
        """
        return the unique game id from context, or find it via #findUniqueGameId()
        """
        if not self.config.context.get("uniqueGameId"):
            self.config.context["uniqueGameId"] = self.findUniqueGameId()
        return self.config.context.get("uniqueGameId")
    
    def getCacheFolderName(self):
        """
        constructs the cache folder name with following pattern {gamename}_{serverip}_{unique game id}
        Unless the cache folder name override is active, then just return what has been configured
        """
        if self.config.downloadtool.useCustomCacheFolderName:
            return self.config.downloadtool.customCacheFolderName

        gameName = self.config.dedicatedConfig.GameConfig.GameName
        serverIp = Tools.getOwnIp(self.config)
        uniqueGameId = self.getUniqueGameId()
        if uniqueGameId:
            cacheFolderName = f"{gameName}_{serverIp}_{uniqueGameId}"
            log.debug(f"Generated cache folder name '{cacheFolderName}'")
            return cacheFolderName
        else:
            log.debug(f"Could not determine unique game id. Using default cache folder name '{self.config.downloadtool.customCacheFolderName}'")
            return self.config.downloadtool.customCacheFolderName

    def createSharedDataZipFiles(self, pathToSharedDataFolder: Path) -> List[ZipFile]:
        """
            actually creates the zip files for the shared data download, if shared data url feature is enabled, it will create both, the manual and the auto zip
        """
        if not pathToSharedDataFolder.exists():
            log.warning(f"Path to the shared data in the games scenario folder '{pathToSharedDataFolder}' does not exist. Please check the configuration.")
            return
        
        tempFolder = Path(self.config.downloadtool.tempFolder).resolve()
        if tempFolder.exists():
            log.debug(f"deleting old temporary folder '{tempFolder}'")
            FsTools.deleteDir(tempFolder, True)
        FsTools.createDir(tempFolder)

        cacheFolderName = self.getCacheFolderName()
        cacheFolder = tempFolder.joinpath(cacheFolderName)

        FsTools.createDir(cacheFolder)
        log.debug(f"Copying files from '{pathToSharedDataFolder}' to cacheFolder '{cacheFolder}'")
        FsTools.copyDir(source=pathToSharedDataFolder, destination=cacheFolder)
        log.debug(f"Created cachefolder '{cacheFolder}'")

        # increase the modification timestamps of all files by 12 hours
        self.increaseModificationTimestamps(cacheFolder)
        
        # create manual zip from the cacheFolder
        log.debug(f"Creating manual zip from tempFolder '{tempFolder}' with name '{self.config.downloadtool.manualZipName}'")
        manualZipFile = self.createZipFile(tempFolder, self.config.downloadtool.manualZipName)
        zipFiles = [manualZipFile]

        if self.config.downloadtool.useSharedDataURLFeature:
            # create auto zip from the folder
            subFolder = tempFolder.joinpath(cacheFolderName)
            generatedAutoZipName = f"{self.config.downloadtool.autoZipName.split(".")[0]}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
            log.debug(f"Creating auto zip from folder '{subFolder}' with name '{generatedAutoZipName}'")
            autoZipFile = self.createZipFile(subFolder, generatedAutoZipName)
            zipFiles = [manualZipFile, autoZipFile]
        return zipFiles

    def createZipFile(self, folder: Path, zipFileName):
        # remove the extension from the filename to get the name of the zip file
        zipNameNoExtension = zipFileName.split(".")[0]
        zipResult = shutil.make_archive(zipNameNoExtension, 'zip', folder)
        zipPath = Path(zipResult).resolve()
        zipfileSize = zipPath.stat().st_size
        return ZipFile(zipFileName, zipPath, zipfileSize, 0, None)

    def increaseModificationTimestamps(self, folder):
        """
        increase the modification timestamps of all files in given folder by whatever value was set in the config
        """
        timeDifference = self.config.downloadtool.timeToAddToModificationTimestamps
        for root, dirs, files in os.walk(folder):
            for file in files:
                path = os.path.join(root, file)
                currentMTime = os.path.getmtime(path)
                newMTime = currentMTime + timeDifference
                os.utime(path, (newMTime, newMTime))
        timeDiffHuman = humanize.naturaldelta(timeDifference)
        log.debug(f"Altered all files in folder '{folder}', added {timeDiffHuman} to their last modified timestamps.")
    
    def serve(self, zipFiles: List[ZipFile]):
        """
        starts the httpd server using the different configurations for the given zipFiles
        """
        serverPort = self.config.downloadtool.serverPort
        handler = self._setUpSharedDataHandler(zipFiles)

        if self.config.communication.chatlogViewerEnabled:
            servingUrlRoot = self.getServingUrlRoot()
            pSgmt = self.config.communication.chatlogViewerPathSegment
            log.info(f"Enabling chat log viewer on path '{servingUrlRoot}{pSgmt}'")

            chatLogViewerFiles = [f"{pSgmt}", f"{pSgmt}/index.html", f"{pSgmt}/script.js", f"{pSgmt}/styles.css"]
            handler.whitelist = chatLogViewerFiles
            handler.rateLimitExceptions = chatLogViewerFiles
            handler.redirects = [
                {"source": f"{pSgmt}", "destination": f"{pSgmt}/index.html", "code": 301},
                {"source": f"{pSgmt}/", "destination": f"{pSgmt}/index.html", "code": 301},
            ]
            haimsterChatLog = f"{self.config.communication.haimsterHost}{self.config.communication.chatlogPath}"
            log.info(f"Will proxy chatlog url at: '{haimsterChatLog}'")
            handler.proxiedPaths = [
                {"path": f"{pSgmt}/chatlog.json", "target": haimsterChatLog},
            ]

        try:
            with socketserver.ThreadingTCPServer(("", serverPort), handler) as httpd:
                self._httpServer = httpd
                httpd.serve_forever()
        except Exception as e:
            log.debug(e)

    def _setUpSharedDataHandler(self, zipFiles) -> EsmHttpThrottledHandler:
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        sharedDataHandler = EsmHttpThrottledHandler
        EsmHttpThrottledHandler.rootDirectory = wwwroot.resolve() # this is the root of the webserver
        EsmHttpThrottledHandler.globalBandwidthLimit = self.config.downloadtool.maxGlobalBandwith
        EsmHttpThrottledHandler.clientBandwidthLimit = self.config.downloadtool.maxClientBandwith
        EsmHttpThrottledHandler.rateLimit = parse(self.config.downloadtool.rateLimit)
        EsmHttpThrottledHandler.zipFiles = zipFiles
        EsmHttpThrottledHandler.activeConnections = self._activeConnections
        return sharedDataHandler
