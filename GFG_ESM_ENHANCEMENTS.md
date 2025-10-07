# GFG ESM Enhancements

This document describes the enhancements and changes made to the Empyrion Server Manager (ESM) to support enhanced process tracking and multi-instance server management.

## Overview

The enhancements focus on three main areas:
1. **Multi-Instance Support** - Allow ESM to coexist with other Empyrion server management tools
2. **Process Information Command** - Provide visibility into ESM's process management
3. **Performance Optimization** - Skip unnecessary checks during server startup

## Changes Made

### 1. Multi-Instance Support (Milestone 0)

**Files Modified:**
- `src/esm/ConfigModels.py` (added `allowMultipleInstances` configuration)
- `src/esm/EsmDedicatedServer.py` (enhanced process detection logic)
- `src/esm/EsmMain.py` (fixed server startup logic)

**New Configuration Option:**
```yaml
server:
  allowMultipleInstances: true  # Allow multiple Empyrion server instances
```

**What It Does:**
- Bypasses the process count check that normally prevents multiple Empyrion server instances
- Only works when `startMode: 'direct'` is also configured
- Allows ESM to coexist with other server management tools (like EAH) on the same host
- **Fixed**: ESM no longer exits when detecting an EAH-managed server running
- Maintains backward compatibility - existing configs continue to work unchanged

**Usage:**
```yaml
server:
  startMode: 'direct'              # Required for multi-instance support
  allowMultipleInstances: true     # Enable multi-instance mode
```

### 2. Process Information Command

**Files Modified:**
- `src/esm/EsmDedicatedServer.py` (added `getProcessInfo()` method)
- `src/esm/main.py` (added `process-info` CLI command)

**New CLI Command:**
```bash
esm process-info
```

**What It Shows:**
- Current server configuration (start mode, multiple instances setting)
- Process details (PID, name, status, command line)
- Detection method and multiple instance policy

**Example Output:**
```
ESM Process Information
=====================

Configuration:
  Start Mode: direct
  Allow Multiple Instances: true
  Dedicated YAML: MyServer.yaml
  Graphics Mode: false

Current Process:
  PID: 12345
  Name: EmpyrionDedicated.exe
  Status: Running
  Command Line: C:\Empyrion\DedicatedServer\EmpyrionDedicated.exe -batchmode -nographics -dedicated MyServer.yaml -logFile ../Logs/12345/Dedicated_241201-143022.log

Process Detection:
  Method: Direct mode (bypasses launcher)
  Multiple Instances: Allowed
```

### 3. Shared Data URL Check Optimization

**Files Modified:**
- `src/esm/ConfigModels.py`
- `src/esm/EsmDedicatedServer.py`

**New Configuration Option:**
```yaml
downloadtool:
  skipSharedDataURLCheck: true  # Skip slow URL availability check during startup
```

**What It Does:**
- Skips the HTTP request that validates SharedDataURL availability during server startup
- Significantly reduces server startup time when using external shared data management
- Maintains backward compatibility - existing configs continue to work unchanged
- Only affects ESM's startup check, not Empyrion's use of the SharedDataURL

**Usage:**
```yaml
downloadtool:
  useSharedDataURLFeature: false    # ESM doesn't manage shared data
  skipSharedDataURLCheck: true      # Skip startup URL check
```

## Configuration Examples

### Multi-Instance Setup
```yaml
server:
  dedicatedYaml: 'esm-dedicated.yaml'
  startMode: 'direct'
  allowMultipleInstances: true
  gfxMode: false
```

### External Shared Data Management
```yaml
downloadtool:
  customExternalHostNameAndPort: 'http://your-server.com:9000'
  useSharedDataURLFeature: false
  skipSharedDataURLCheck: true
```

## Backward Compatibility

All changes maintain full backward compatibility:
- Existing configuration files continue to work without modification
- Default values preserve original ESM behavior
- New features are opt-in only
- No breaking changes to existing functionality

## Technical Details

### Process Detection Logic
The enhanced process detection in `EsmDedicatedServer.findProcessByName()` now:
1. Checks if `startMode == DIRECT` AND `allowMultipleInstances == true`
2. If both conditions are met, returns the first process instead of throwing an error
3. Otherwise, maintains the original behavior (prevents multiple instances)

### Server Startup Logic Fix
The `EsmMain.startServer()` method now:
1. Checks if a server is already running via `dedicatedServer.isRunning()`
2. If running AND `allowMultipleInstances` is enabled, proceeds with startup instead of exiting
3. Otherwise, maintains the original behavior (exits with error)

**Problem Solved:**
- Previously: ESM would exit with "A server is already running!" when detecting EAH-managed servers
- Now: ESM proceeds with startup when `allowMultipleInstances: true` is configured
- Log message: `"A server is already running, but allowMultipleInstances is enabled for direct mode - proceeding with startup"`

**Working Directory Fix:**
- Previously: Direct mode used install directory as working directory, causing logs to appear in wrong location
- Now: Direct mode uses DedicatedServer directory as working directory to match launcher behavior, ensuring logs go to correct location

### URL Check Optimization
The `assertSharedDataURLIsAvailable()` method now:
1. Checks the `skipSharedDataURLCheck` configuration option
2. If `true`, skips the HTTP request and returns immediately
3. Otherwise, performs the original URL validation

## Benefits

1. **Multi-Tool Coexistence** - ESM can now run alongside EAH and other server management tools
2. **Faster Server Startup** - Eliminates slow URL checks when managing shared data externally
3. **Better Visibility** - Process info command provides clear insight into ESM's process management
4. **Flexible Configuration** - Users can choose which features to enable/disable
5. **Maintained Safety** - All safety checks remain active by default
6. **Backward Compatibility** - Existing configurations continue to work without modification

## Troubleshooting

### Common Scenarios

**Scenario 1: ESM exits when EAH-managed server is running**
- **Problem**: ESM shows "A server is already running!" and exits
- **Solution**: Add `allowMultipleInstances: true` to your ESM config
- **Required**: Must also have `startMode: 'direct'`

**Scenario 2: Slow server startup with external shared data**
- **Problem**: ESM takes a long time to start due to URL checks
- **Solution**: Add `skipSharedDataURLCheck: true` to your ESM config
- **Note**: Only skip if you're managing shared data externally

**Scenario 3: Want to verify ESM configuration**
- **Solution**: Use `esm process-info` command to see current settings
- **Shows**: Start mode, multiple instances setting, process details

**Scenario 4: Logs appearing in wrong directory**
- **Problem**: Logs showing up in `e:\Logs\` instead of `e:\empyrion\Logs\`
- **Solution**: Fixed in latest version - Direct mode now uses DedicatedServer directory as working directory
- **Note**: The launcher changes to DedicatedServer directory before starting the server, which we now replicate in Direct mode

### Configuration Validation

Use the `process-info` command to verify your setup:
```bash
esm process-info
```

Look for:
- `Start Mode: direct` (required for multi-instance)
- `Allow Multiple Instances: true` (enables coexistence)
- `Multiple Instances: Allowed` (confirms policy)

## Future Enhancements

These changes provide the foundation for more advanced process tracking features:
- Multiple process tracking and management
- Process history and monitoring
- Enhanced detection methods
- Process comparison and analysis tools

---

*These enhancements provide a solid foundation for multi-instance server management while maintaining ESM's reliability and safety features. The changes are minimal, backward-compatible, and solve real-world coexistence scenarios with other Empyrion server management tools.*
