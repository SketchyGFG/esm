# TODOS

## WIP

## later
- [ ] find out how to trigger the *regeneration* of whole systems? maybe even as a tool
- [ ] new tool that sets a players position on the database directly, to fix broken players when they get yeeted to 0,0,0
- [ ] config.backup.additional should support globbing
- [ ] wipe-tool: find a way to also remove wiped playfields from the player registries to avoid teleportation bugs (since the bug is still not fixed)
- [ ] fix purge-tools: these need to also delete related data in the database and cache! Probably not difficult to finish implementing, but a PITA to test.
- [ ] allow admins to whisper to haimster for instructions
- [ ] integrate haimster as tool, maybe aswell run integrated? => for the rewrite
- [ ] needs a big rewrite:
      - haimster
      - an event system that propagates game events (not only chat messages)
      - a separate server with a GUI to manage stuff (incl. chatlog)
      - discord integration - with the ability to control esm+haimster from discord, post the chatlog there, etc.
- [ ] extend documentation, add readme_tools or something to explain the new ones

## optional
- [ ] SDS: a configurable treshold for change size in MB at what point it makes sense to enable the shareddataurl or keep the old method?
- [+] how can the haimster chat messages be made visible in discord, EWA, EAH? -> Changed to use sendertype Player, see if that helps => nope. sounds like its not possible.
- [ ] implement allowMultpleServerInstances switch? Once enabled, do not check for instances of the game before starting, do not start if startmode is set to direct, etc.
- [+] fix all FS-modifying tests to use the test fixture of the usually existing ramdisk (R:) - or use mocks!
- [ ] offer some kind of better interactive mode for different stuff
  - [ ] add fzf-like selection, also replace user prompts with that.
  - [ ] interactive mode for wipe galaxy tool?
  - [ ] add a -batchmode when there are interactive prompts, in doubt, defaulting to the most defensive option
- [ ] GUI!?
- [ ] create separate windows-gui thingy that resides in the taskbar or similar and provides a shortcut to the cli tool?
- [ ] ask notoats to create a downloadable release of his contained exe, so i can add it as 3rd party requirement
- [ ] provide full installation package with install bat, that installs esm, the tools (osfmount, peazip, emprc, etc.)?
- [ ] implement warning/talkback via tickets for when an admin is required (e.g. low disk space, etc.), e.g. as an extra tool, so it can just be planned in EAH, or as delayed task after a startup (e.g. 5 minutes after the server started) - alternatively just a discord bot.
- [ ] add switch to backup-tool to make backups EWA-compatible
- [ ] provide tool to fix item icons as good as possible in EWA, current process:
   1. open item list in eah, CTRL+A, CTRL+C and copy into text file? Or find out how the item list file in epf got created
      - info from notoats: should be trivial to convert to python
      blocksmap.dat: https://gist.github.com/NotOats/36b6192b4703d55aa5ce334388ff1990
      my old ECF file reader: https://gist.github.com/NotOats/a585298736c70930c89545c4c56aeae9
      just load the item list from ECF files ("BlocksConfig.ecf", "ItemsConfig.ecf") and overwrite with blocksmap.dat entries
   1. read itemid, itemname, devicename from that eah list
   1. find block by matching devicename with blocktype
   1. find customicon name
   1. save customicon as itemid for EWA.
- [ ] add cb:shield:$id function to be able to get a ships shield values?
- [ ] proper python-native connector to the EGS server to not have to use the emprc

## done
- [x] tool to delete the cache, so we can use the esm-taskprocessor to do it for us
- [x] esm: use the "Import Commands"-Feature of EAH to restart it every now and then?
  TOOL_RESTART.txt https://forum.empyrion-homeworld.net/t/restart-master-please-help-me-gtx-doesn-t-care/29105
  TOOL_STOP.txt https://empyriononline.com/threads/tool-empyrion-server-auto-update-tools-v2-0-1-0.26031/
- [x] new bash script: that executes the esm commands in a list and deletes them (or renames as "done") afterwards. Great for automating one-shot stuff, like wipes, player fixes, exports, etc.
  - bash script would be more versatile
  - for regular tasks, we already have everything in place (and EAH or EWA for scheduling)
- [x] BUG: when shareddata is being downloaded, the tool will NOT shutdown automatically (!) - can lead to issues when EGS shuts down in the meantime.
- [x] haimster-connector, if an answer is longer than x, send two messages! => no more obvious bot messages
- [x] a scenario update should validate all yamls for galaxy generation, since errors here lead to broken savegames! especially the playfield yamls
- [x] BUG: shared-data tool should not roll back to backup, but just remove the line instead since changes while the tool was running may get lost. ruamel yaml_rt should work well with this
- [x] new zip, provide the server zip as manual download aswell, along with the instructions for people to "install" manually
  - need to find out how eleon calculates the zip name in _shareddatazips, alternatively, make it configurable.
- [x] add support for the tool to run along with the shared-data-server, without having to start it separatedly
- [x] shared data tool should recognize when it is needed to update the shared data zip, by creating and keeping a hashdb of it, ideally only of the shared data folder
  - save the hashdb along with the zip, so we know its state/version.
- [x] BUG: wipe-tool territories causes NPE when custom territories are not configured
- [x] read the territory config from the galaxyconfig.ecf ourselves. Search for "Child Territory" - Blocks.
- [x] wipe-tool --show* options should work without instance-check, also in dryrun it should work with --dblocation (to get some stats from backups)
- [x] tool to generate the effective config
- [x] new server endpoint (or reuse shared-data-tool?) where someone can see/read the current chatlog, ideally with a search functionality, initially scrolled to the bottom.
      - actually, haimster should provide the download, esm has to proxy it.
- [x] shared-data-tool server needs a spinner
- [x] BUG: shared-data-tool shows stacktrace on connection errors of clients -> just log.warn and thats it.
- [x] BUG: when shutting down, we have to kill the emprc listener!
- [x] BUG: connector should not forward chat messages from the server tab!
- [x] BUG started connector server doesn't log into our esm logger properly
- [x] updating list of playernames should depend on player events => even less calls to DB
- [x] BUG: remove bogus duplicates from the chatlog in the export tool
- [x] tool to export chatlogs from the DB
- [x] integrate haimster-connector as new tool, optionally running along with the server?
- [x] add an AI-powered chatbot, chatgpt-like that roleplays as a spacefaring hamster that reacts to player chat?
- [x] add option to disable auto-editing of dedicated yaml in shared data tool
- [x] add option to override the host and port when aut-editing the dedicated yaml in the shared data tool
- [x] resume mode / create mode for the shared data server to be able to control if we actually want to recreate the zip.
- [-] find out if there is *any* information the client requests on the shared data server to see how we can implement it => nothing. its useless.
- [x] maybe the shared data tool could remove the shareddataurl property when it is shut down to make sure the server doesn't use it when its off.
- [-] use http redirects to work around the issue of having to edit the dedicated yaml? It follows, but doesn't care.
- [x] add support for the new shareddata-url feature once it is released and we know how it works
- [x] read the id of the savegame data folder name for the savegame tool from the main dedicated log, once the game has started once.
  - see logfile and search for the "UniqueId" when the game logs something like: 23-01:04:31.793 18_04 -LOG- Mode=currentQuery, GameSeed=8979695, UniqueId=931593376, EntityId=1001
  - it may be necessary to find the proper logfile first though, since the logs are not related to the savegame
- [x] add some more placeholders for the html-template, e.g. one for the password from the dedicated.yaml
- [x] bug: delete-all does not back up the esm logs properly
- [x] fix shared data download: files in the zip have to have their modification timestamp increased by at least 12 hours, since the game assumes anything else to be outdated for some reason.
- [x] fix logging of dirsync on scenario update
- [x] automatically create esm-default-config.example.yaml when building release
- [x] add separate tool that allows to download the shared data folder of the currently configured game
- [x] implement bandwidth-limits to shared-data-download tool
- [x] refactor tools, make them wipe instead, or make all tools have the option to additionally purge too? Make it more conscise.
  - [x] tool-wipe (--territory|--file) --wipetype --nocleardiscovered --minimumage
  - [x] tool-clear-discoveredby (--territory|--file) 
  - [-] tool-cleanup-purge-wiped
  - [x] tool-cleanup-shared
  - [x] tool-cleanup-removed-entities
- [-] tool to wipe/purge a list of playfields passed in the command line and/or file?
- [x] refactor configuration once again: put base-config as default-config into the module, and provide an example custom config. The game has to do some sanity checks on startup to make sure the required configurations are in place (like installdir, dedicated yaml, etc.) - Or use something more sophisticated, e.g. a proper getter for config properties that retrieve it from custom -> base -> fallback to a default. => use pydantic!
- [x] check requirements should do a test copy with robocopy
- [x] when useRamdisk is enabled, enable checks for its file structure, when its not, do not start use the synchronizer (of course)
- [-] game-install should have the option to install the scenario? or...
- [x] use pyinstaller to create a distributable program without any installation overhead: <https://pyinstaller.org/>
- [x] update scenario should provide a sync function so that only the real changes are copied, to avoid data-redownloads.
- [x] add more empclient functions, especially the sync event announcements.
- [x] implement warning/talkback to server chat for syncs, backups probably even random stuff with funny hamster sentences.
- [x] make emprc client log the return codes properly
- [x] make sure the async-able commands do not check the binding port.
- [x] integrity check: checks if things fit together (e.g. dedicated.yaml config), our own config when running multiple instances, etc.
  - or adapt config to dedicated.yaml, especially when paths change. probably as a sanity check implementation
  - may also just check the config, e.g. if all paths exist
- [x] remove redundant configuration that can be read from the dedicated yaml instead, and do that?
- [x] check for 8dot3name
- [x] update should have the option to disable the steam check?
- [-] usecase: create configuration? => probably not needed. the custom config covers our needs.
- [-] wipes from the wipetool should propagate to EAH? do i need to alter EAHs database too? => no access to eah's dat files.
- [x] make sure the script only runs once? probably by opening up a port, that way there's no need for cleanups.
- [x] create batch file to integrate with EAH
- [x] add versioning and --version option to show it
- [x] make script open up a port to avoid having multiple instances running
- [x] tool to find and delete obsolete folders in Shared
- [x] purge the wiped: check for wipeinfos containing "all", and purge those (fs operations only)
- [x] usecase: purge galaxy
- [x] tool: clean structures that have been removed in the DB, but still exist on the FS (optional also give a min age)
- [x] catch ctrl+c or sigints properly
- [x] server-resume - usecase, for when you have to kill the script and start it again without having to kill the server.
- [x] feature: add the ability to delete the discovered by flag to the wipe tool
- [x] tool: deletes the "discovered by" flags for given systems/playfields (potentially also for wipes/purges)
- [x] add some for spinner or similar when server is running, to see if the console-suspend-bug has hit again
- [x] implement server-callback with empremoteclient
- [x] re-mount option for when ramdisk size has to be updated or ramdisk is down for some reason.
- [x] print out wipetype descriptions on help too.
- [x] custom dblocation may not be given in conjunction with nodryrun.
- [x] usecase: wipe galaxy - integrate other script
- [x] split the config in a "basic" config, an custom config that overwrites the basic config.
- [x] debugmode
- [x] add proper cli - use the click library to extend the scripts with command line tools
- [x] usecase: deinstall ramdisk
- [x] change delete functions so that it maintains a list and the user is asked at the end.
- [x] change delete functions so that the path has to be at least 3 levels deep before deleting anything?
- [x] usecase: delete savegame, including tool data, potential mod data too, add extensions like for the backup
- [x] usecase: install game
- [x] usecase: update game
- [x] tool should check free disk space before starting server (especially in ramdisk mode)
- [x] tool should check free disk space before doing a new static backup
- [x] usecase: create manual static backup
- [x] usecase: create incremental backup
- [x] add ram2mirror synchronizer
- [x] implement DI
- [x] usecase: stop gameserver properly
- [x] implement regular ram2mirror sync
- [x] use pathlib instead of os.path wherever possible
- [x] usecase: server reboot
- [x] usecase: install ramdisk
- [x] usecase: kill gameserver (via sigterm)
- [x] usecase: start up gameserver

#### copyright by Vollinger 2023-2025
