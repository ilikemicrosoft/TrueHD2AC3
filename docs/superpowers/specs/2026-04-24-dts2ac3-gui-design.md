# DTS2AC3 GUI Design

## Overview

This project will be a Windows desktop utility built with Python and PySide6 to automate a common local media workflow:

1. Load a user-selected source media file.
2. Inspect the file's tracks using MKVToolNix tools.
3. Detect one or more TrueHD audio tracks.
4. Let the user choose which detected TrueHD track to convert.
5. Convert the chosen track to AC3 5.1 with eac3to using user-configurable arguments.
6. Merge the converted AC3 track into a newly generated output file with MKVToolNix.
7. Optionally preserve or replace the original TrueHD track in the final file.

The application is intentionally a workflow orchestrator rather than a media-processing engine. All extraction, probing, conversion, and muxing should rely on existing MKVToolNix and eac3to commands wherever practical.

## Goals

- Provide a local GUI for users who want to convert TrueHD tracks to AC3 5.1 without manually running several tools.
- Remember the install directories for MKVToolNix and eac3to.
- Support importing broadly compatible media files and let the underlying tools determine support.
- Surface original tool output and errors directly in the interface.
- Allow the user to pick among multiple detected TrueHD tracks.
- Allow the user to choose whether the original TrueHD track is preserved or replaced in the final file.
- Allow the user to choose output directory, working directory, and final output file name.
- Automatically clean temporary files from the working directory after successful completion when enabled.

## Non-Goals For First Version

- Batch queue processing for multiple files.
- Editing video, subtitle, chapter, attachment, or metadata content beyond what is required for the merge operation.
- Advanced preset management beyond saving the latest used values.
- Deep media parsing implemented by custom decoders or third-party Python media libraries.

## User Experience

The first version uses a single-window interface with five logical areas:

### 1. Tool Paths

- MKVToolNix installation directory picker.
- eac3to installation directory picker.
- Validation action that checks required executables and reports missing tools before processing starts.

Expected required executables:

- `mkvmerge.exe`
- `mkvextract.exe`
- `mkvinfo.exe` if needed for fallback inspection
- `eac3to.exe`

### 2. Source And Output

- Source file picker.
- Output directory picker.
- Working directory picker.
- Output file name input prefilled from the source file's base name.

The application should remember the latest directories and repopulate them when reopened.

### 3. Track Scan And Selection

- Scan button to inspect the source media file.
- Track list showing at minimum:
  - Track ID
  - Codec
  - Language if available
  - Channel or audio description if available
  - Default track flag if available
- Only detected TrueHD audio tracks are selectable for conversion.
- When multiple TrueHD tracks exist, the user must explicitly choose one. No automatic guesswork.
- If no TrueHD track is found, the UI should say so clearly and keep the process blocked.

### 4. Conversion Options

- Editable eac3to argument field with default value `%_.ac3 -640`.
- Choice to preserve or replace the selected original TrueHD track.
- Toggle for automatic cleanup of temporary files.

### 5. Execution And Logs

- Start button.
- Stop or cancel button.
- Scrollable real-time log view.
- The log view must show:
  - The command being executed
  - Standard output
  - Standard error
  - Process exit code
- Tool-provided error text should be displayed directly without summarizing away the original details.

## Technical Architecture

The application should be organized into lightweight layers.

### GUI Layer

Responsible for:

- Rendering widgets
- Collecting user input
- Showing track results
- Showing real-time logs
- Enabling and disabling actions based on state

The GUI must not embed media-command knowledge directly.

### Workflow Layer

Responsible for orchestrating the end-to-end job:

1. Validate tool paths and user selections.
2. Probe the source file.
3. Confirm a selectable TrueHD track exists.
4. Convert the selected track with eac3to.
5. Merge the new AC3 track into a new output file with MKVToolNix.
6. Clean temporary files if requested.

This layer also owns job state and stage transitions so the UI can show meaningful progress.

### Tool Adapter Layer

Responsible for wrapping external executables in focused helpers such as:

- `probe_tracks(...)`
- `convert_truehd_to_ac3(...)`
- `merge_output(...)`
- `validate_tool_installations(...)`

These helpers should return structured results plus raw command output. They should not contain UI code.

### Configuration Layer

Responsible for reading and writing persisted application settings to a local JSON file under `%APPDATA%\\DTS2AC3\\settings.json`.

Stored values:

- MKVToolNix directory
- eac3to directory
- Last output directory
- Last working directory
- Last used eac3to argument string
- Last cleanup preference
- Last preserve-or-replace preference

## Media Command Strategy

The application should prefer these external commands:

### Track Inspection

Primary approach:

- Use `mkvmerge -J <source>` to obtain machine-readable track metadata.

Reason:

- JSON output is easier and safer to parse than free-form console output.

Fallback:

- Use `mkvinfo` only if additional details are required or if JSON inspection is insufficient for a particular edge case.

### Conversion

Primary approach:

- Call `eac3to` directly against the source file and selected track when possible, using the configured arguments ending in AC3 output.

Default argument behavior:

- The GUI pre-fills `%_.ac3 -640`.
- At execution time, `%_` is resolved to a generated temporary output base path in the working directory.

The workflow must ensure the selected track mapping is correct for eac3to's track addressing scheme.

### Merge

Primary approach:

- Use `mkvmerge` to create the new output file.

Preserve mode:

- Keep all original tracks.
- Add the converted AC3 track as a new audio track.

Replace mode:

- Keep the original file's non-selected tracks.
- Exclude the selected original TrueHD track from the remux.
- Add the converted AC3 track.

The merge helper must build the correct command line for both modes and preserve unrelated streams whenever possible.

## Track Identification Rules

TrueHD detection should rely on structured metadata from MKVToolNix, not filename guessing or language guessing.

A candidate track must:

- Be an audio track.
- Identify as Dolby TrueHD or equivalent TrueHD codec naming from tool output.

The interface should support multiple candidates and list all of them.

Track list display should be descriptive enough that the user can tell tracks apart when there are several TrueHD entries, for example by language or channel layout where available.

## Working Directory Behavior

The working directory holds temporary conversion artifacts such as the generated AC3 file and any helper outputs required by the workflow.

Rules:

- The user can choose the working directory.
- Temporary file names should include the source base name and selected track ID where useful.
- Automatic cleanup runs only after successful completion by default.
- If the job fails, temporary files should be preserved unless the user manually clears them later. This helps debugging.

## Output Naming Behavior

- The output file name input should auto-fill from the source file's base name on source selection.
- The user can edit that value before running the job.
- The output extension should be derived from the muxing target, which for the first version is expected to be `.mkv`.

Even when the source format is more broadly accepted, first-version output should target MKV because the muxing flow is built on MKVToolNix behavior.

## Error Handling

Errors should be handled in four categories:

### Configuration Errors

- Missing executable paths
- Invalid directories
- Unwritable output directory
- Missing source file

These should block execution before the job starts.

### Probe Errors

- Track scan command fails
- Source file unsupported by the underlying tools
- No TrueHD tracks detected

These should stop the workflow and display both a short human-readable status and raw tool output.

### Conversion Errors

- eac3to returns a non-zero exit code
- Expected AC3 output file is not created

These should stop the workflow, keep temporary files, and show raw output.

### Merge Or Cleanup Errors

- muxing command fails
- cleanup cannot delete temporary files

Muxing failure is fatal. Cleanup failure should be reported as a warning if the final output file is already valid.

## Cancellation

The first version should support canceling the currently running external process.

Behavior:

- If the current child process is still active, terminate it.
- Mark the job as canceled.
- Preserve generated temporary files for inspection.
- Record cancellation in the log.

Full process-tree termination can be implemented if needed on Windows, but the design only requires safe cancellation of the active external command in version one.

## Testing Strategy

The project should emphasize test coverage around the non-UI logic.

### Unit Tests

Target areas:

- Settings load and save behavior
- MKVToolNix JSON parsing into track models
- TrueHD track filtering
- eac3to command building
- mkvmerge command building for preserve and replace modes
- Output path and temporary path generation

### Process Simulation Tests

Use mocked subprocess execution to verify:

- Success path sequencing
- Probe failure handling
- Conversion failure handling
- Merge failure handling
- Cleanup decisions
- Log forwarding behavior

### GUI Tests

Keep these limited in the first version:

- Basic state enablement
- Correct population of scanned TrueHD tracks
- Log text append behavior

The goal is to keep most logic testable without requiring a real desktop interaction harness.

## Delivery Plan

The first deliverable should be a runnable Python project with:

- dependency manifest
- source tree
- tests
- README with setup instructions

Packaging into a standalone Windows executable can be added later, likely with PyInstaller, once the workflow is stable.

## Risks And Decisions

### eac3to Track Addressing

The exact mapping between MKVToolNix track IDs and eac3to's expected track selectors may differ. The implementation should isolate this in the adapter layer and validate it with representative test cases and sample command behavior.

### Source Format Compatibility

The user wants broader adaptability for input formats. The design therefore allows broad import attempts, but does not promise every format will work. The underlying command output should be shown directly whenever the source cannot be handled.

### Multiple TrueHD Tracks

This is an explicit supported scenario. The UI and workflow must require manual track selection when more than one TrueHD track exists. The tool should never auto-pick a track in that case.

## Open Design Decision Resolved

For version one:

- UI technology: Python + PySide6
- Processing scope: single file
- Input compatibility: broad attempt, tool-driven validation
- Output target: MKV
- Command visibility: embedded real-time GUI log panel
- Selected TrueHD handling: user chooses preserve or replace
- Multiple TrueHD tracks: user must explicitly choose the target track

## Success Criteria

The first version is successful when a user can:

1. Open the application.
2. Save valid MKVToolNix and eac3to directories.
3. Choose a source media file.
4. Scan tracks and see all detected TrueHD candidates.
5. Select one TrueHD track for conversion.
6. Keep or replace the original TrueHD track.
7. Run conversion and remux.
8. See raw command output live in the GUI.
9. Receive a newly generated MKV in the chosen output directory.
10. Have temporary files cleaned automatically after a successful run when cleanup is enabled.
