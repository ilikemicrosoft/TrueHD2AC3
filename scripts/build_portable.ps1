param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist"
$buildRoot = Join-Path $projectRoot "build"
$appName = "DTS2AC3"
$portableRoot = Join-Path $distRoot "$appName-portable"
$portableAppDir = Join-Path $portableRoot $appName
$archivePath = Join-Path $distRoot "$appName-portable.zip"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

Push-Location $projectRoot
try {
    & $PythonExe -m pip install -e .[dev]

    if (Test-Path $portableRoot) {
        Remove-Item -LiteralPath $portableRoot -Recurse -Force
    }
    if (Test-Path $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force
    }
    if (Test-Path $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }

    & $PythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name $appName `
        --distpath $portableRoot `
        --workpath $buildRoot `
        --specpath $buildRoot `
        --paths src `
        src\dts2ac3\main.py

    $readmePath = Join-Path $portableRoot "README-portable.txt"
    @"
DTS2AC3 Portable
================

Run:
  $appName\$appName.exe

Requirements:
  - MKVToolNix installed
  - eac3to installed

Notes:
  - This is a portable build. Extract the whole folder before running.
  - Current settings are still stored under %APPDATA%\DTS2AC3\settings.json.
"@ | Set-Content -LiteralPath $readmePath -Encoding UTF8

    Compress-Archive -Path "$portableRoot\*" -DestinationPath $archivePath -Force

    Write-Host "Portable app directory: $portableRoot"
    Write-Host "Portable archive: $archivePath"
}
finally {
    Pop-Location
}
