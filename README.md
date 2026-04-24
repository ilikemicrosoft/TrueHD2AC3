# TrueHD2AC3

PySide6 desktop utility for Windows that automates a TrueHD-to-AC3 workflow with MKVToolNix and eac3to.

## Features

- Remembers MKVToolNix and eac3to installation directories
- Prefills the common local install paths when they exist
- Scans source files with `mkvmerge -J`
- Lists all detected TrueHD tracks and requires the user to choose one
- Converts the selected TrueHD track to AC3 using configurable `eac3to` arguments
- Remuxes the converted AC3 track into a new MKV
- Lets the user preserve or replace the selected original TrueHD track
- Shows raw command output and error text live in the GUI
- Cleans temporary files after successful completion when enabled

## Requirements

- Windows
- Python 3.12+
- MKVToolNix installed
- eac3to installed

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## Run

```powershell
python -m truehd2ac3.main
```

## Test

```powershell
python -m pytest
```
