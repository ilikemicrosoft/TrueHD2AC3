# DTS2AC3 GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows PySide6 desktop app that detects one or more TrueHD tracks in a source media file, lets the user choose one, converts it to AC3 5.1 with eac3to, and remuxes the result into a new MKV via MKVToolNix while showing raw command output live in the GUI.

**Architecture:** Use a small `src/dts2ac3` package split into focused modules: dataclass models, JSON-backed settings, external tool adapters, a cancellable workflow coordinator, and a PySide6 main window. Keep media work in external commands and test most behavior through pure command builders and mocked subprocess execution rather than deep GUI automation.

**Tech Stack:** Python 3.12, PySide6, pytest, pytest-qt, dataclasses, pathlib, subprocess, JSON config files.

---

## Planned File Structure

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/dts2ac3/__init__.py`
- Create: `src/dts2ac3/main.py`
- Create: `src/dts2ac3/models.py`
- Create: `src/dts2ac3/settings.py`
- Create: `src/dts2ac3/tooling.py`
- Create: `src/dts2ac3/process_runner.py`
- Create: `src/dts2ac3/workflow.py`
- Create: `src/dts2ac3/ui/__init__.py`
- Create: `src/dts2ac3/ui/main_window.py`
- Create: `tests/conftest.py`
- Create: `tests/test_settings.py`
- Create: `tests/test_tooling.py`
- Create: `tests/test_workflow.py`
- Create: `tests/test_main_window.py`

Each module has one clear job:

- `models.py`: track, tool, settings, and workflow result dataclasses.
- `settings.py`: load and save `%APPDATA%\DTS2AC3\settings.json`.
- `tooling.py`: build and parse MKVToolNix/eac3to commands.
- `process_runner.py`: execute commands and stream log lines.
- `workflow.py`: orchestrate validate, probe, convert, merge, and cleanup.
- `ui/main_window.py`: render widgets and bridge GUI actions to the workflow.

### Task 1: Bootstrap The Package And Settings Persistence

**Files:**
- Create: `pyproject.toml`
- Create: `src/dts2ac3/__init__.py`
- Create: `src/dts2ac3/models.py`
- Create: `src/dts2ac3/settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write the failing settings tests**

```python
from pathlib import Path

from dts2ac3.settings import AppSettingsStore


def test_load_returns_defaults_when_settings_file_is_missing(tmp_path: Path) -> None:
    store = AppSettingsStore(tmp_path / "settings.json")

    settings = store.load()

    assert settings.mkvtoolnix_dir is None
    assert settings.eac3to_dir is None
    assert settings.output_dir is None
    assert settings.working_dir is None
    assert settings.eac3to_args == "%_.ac3 -640"
    assert settings.replace_selected_truehd is False
    assert settings.cleanup_temp_files is True


def test_save_round_trips_settings_values(tmp_path: Path) -> None:
    store = AppSettingsStore(tmp_path / "settings.json")
    settings = store.load()
    settings.mkvtoolnix_dir = Path(r"C:\Program Files\MKVToolNix")
    settings.eac3to_dir = Path(r"C:\Program Files (x86)\eac3to_3.52")
    settings.output_dir = Path(r"D:\exports")
    settings.working_dir = Path(r"D:\temp\dts2ac3")
    settings.eac3to_args = "%_.ac3 -640"
    settings.replace_selected_truehd = True
    settings.cleanup_temp_files = False

    store.save(settings)

    loaded = store.load()
    assert loaded.mkvtoolnix_dir == Path(r"C:\Program Files\MKVToolNix")
    assert loaded.eac3to_dir == Path(r"C:\Program Files (x86)\eac3to_3.52")
    assert loaded.output_dir == Path(r"D:\exports")
    assert loaded.working_dir == Path(r"D:\temp\dts2ac3")
    assert loaded.eac3to_args == "%_.ac3 -640"
    assert loaded.replace_selected_truehd is True
    assert loaded.cleanup_temp_files is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dts2ac3'`

- [ ] **Step 3: Write the minimal package and settings implementation**

`pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dts2ac3"
version = "0.1.0"
description = "PySide6 GUI for converting TrueHD tracks to AC3 and remuxing with MKVToolNix"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "PySide6>=6.8,<7",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3,<9",
  "pytest-qt>=4.4,<5",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
qt_api = "pyside6"

[tool.setuptools.package-dir]
"" = "src"

[tool.setuptools.packages.find]
where = ["src"]
```

`src/dts2ac3/__init__.py`

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

`src/dts2ac3/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    mkvtoolnix_dir: Path | None = None
    eac3to_dir: Path | None = None
    output_dir: Path | None = None
    working_dir: Path | None = None
    eac3to_args: str = "%_.ac3 -640"
    replace_selected_truehd: bool = False
    cleanup_temp_files: bool = True
```

`src/dts2ac3/settings.py`

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from dts2ac3.models import AppSettings


class AppSettingsStore:
    def __init__(self, settings_path: Path) -> None:
        self._settings_path = settings_path

    def load(self) -> AppSettings:
        if not self._settings_path.exists():
            return AppSettings()

        payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return AppSettings(
            mkvtoolnix_dir=self._to_path(payload.get("mkvtoolnix_dir")),
            eac3to_dir=self._to_path(payload.get("eac3to_dir")),
            output_dir=self._to_path(payload.get("output_dir")),
            working_dir=self._to_path(payload.get("working_dir")),
            eac3to_args=payload.get("eac3to_args", "%_.ac3 -640"),
            replace_selected_truehd=payload.get("replace_selected_truehd", False),
            cleanup_temp_files=payload.get("cleanup_temp_files", True),
        )

    def save(self, settings: AppSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        payload = {
            key: str(value) if isinstance(value, Path) else value
            for key, value in payload.items()
        }
        self._settings_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _to_path(value: str | None) -> Path | None:
        return Path(value) if value else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/dts2ac3/__init__.py src/dts2ac3/models.py src/dts2ac3/settings.py tests/test_settings.py
git commit -m "feat: add settings persistence"
```

### Task 2: Add Tool Validation And Track Parsing

**Files:**
- Modify: `src/dts2ac3/models.py`
- Create: `src/dts2ac3/tooling.py`
- Create: `tests/test_tooling.py`

- [ ] **Step 1: Write the failing tooling tests**

```python
from pathlib import Path

from dts2ac3.tooling import (
    find_truehd_tracks,
    parse_mkvmerge_tracks,
    validate_tool_directories,
)


def test_validate_tool_directories_reports_missing_binaries(tmp_path: Path) -> None:
    result = validate_tool_directories(tmp_path, tmp_path)

    assert result.is_valid is False
    assert "mkvmerge.exe" in result.errors
    assert "eac3to.exe" in result.errors


def test_parse_mkvmerge_tracks_extracts_audio_track_fields() -> None:
    payload = {
        "tracks": [
            {
                "id": 0,
                "type": "video",
                "codec": "AVC/H.264/MPEG-4p10",
                "properties": {},
            },
            {
                "id": 1,
                "type": "audio",
                "codec": "TrueHD Atmos",
                "properties": {
                    "language": "jpn",
                    "audio_channels": 8,
                    "default_track": True,
                    "track_name": "Japanese Atmos",
                },
            },
            {
                "id": 2,
                "type": "audio",
                "codec": "DTS-HD Master Audio",
                "properties": {
                    "language": "eng",
                    "audio_channels": 6,
                    "default_track": False,
                },
            },
        ]
    }

    tracks = parse_mkvmerge_tracks(payload)

    assert [track.track_id for track in tracks] == [1, 2]
    assert tracks[0].codec == "TrueHD Atmos"
    assert tracks[0].language == "jpn"
    assert tracks[0].channels == 8
    assert tracks[0].is_default is True
    assert tracks[0].display_name == "Japanese Atmos"


def test_find_truehd_tracks_returns_all_truehd_candidates() -> None:
    payload = {
        "tracks": [
            {
                "id": 1,
                "type": "audio",
                "codec": "TrueHD Atmos",
                "properties": {"language": "jpn", "audio_channels": 8},
            },
            {
                "id": 2,
                "type": "audio",
                "codec": "TrueHD",
                "properties": {"language": "eng", "audio_channels": 8},
            },
            {
                "id": 3,
                "type": "audio",
                "codec": "AC-3",
                "properties": {"language": "eng", "audio_channels": 6},
            },
        ]
    }

    truehd_tracks = find_truehd_tracks(parse_mkvmerge_tracks(payload))

    assert [track.track_id for track in truehd_tracks] == [1, 2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tooling.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for `dts2ac3.tooling`

- [ ] **Step 3: Write the minimal tooling implementation**

`src/dts2ac3/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    mkvtoolnix_dir: Path | None = None
    eac3to_dir: Path | None = None
    output_dir: Path | None = None
    working_dir: Path | None = None
    eac3to_args: str = "%_.ac3 -640"
    replace_selected_truehd: bool = False
    cleanup_temp_files: bool = True


@dataclass(slots=True)
class AudioTrack:
    track_id: int
    codec: str
    language: str
    channels: int | None
    is_default: bool
    display_name: str


@dataclass(slots=True)
class ToolValidationResult:
    is_valid: bool
    errors: list[str]
```

`src/dts2ac3/tooling.py`

```python
from __future__ import annotations

from pathlib import Path

from dts2ac3.models import AudioTrack, ToolValidationResult


def validate_tool_directories(
    mkvtoolnix_dir: Path | None,
    eac3to_dir: Path | None,
) -> ToolValidationResult:
    errors: list[str] = []

    for required in ("mkvmerge.exe", "mkvextract.exe"):
        if mkvtoolnix_dir is None or not (mkvtoolnix_dir / required).exists():
            errors.append(required)

    if eac3to_dir is None or not (eac3to_dir / "eac3to.exe").exists():
        errors.append("eac3to.exe")

    return ToolValidationResult(is_valid=not errors, errors=errors)


def parse_mkvmerge_tracks(payload: dict) -> list[AudioTrack]:
    tracks: list[AudioTrack] = []

    for entry in payload.get("tracks", []):
        if entry.get("type") != "audio":
            continue

        properties = entry.get("properties", {})
        tracks.append(
            AudioTrack(
                track_id=entry["id"],
                codec=entry.get("codec", ""),
                language=properties.get("language", "und"),
                channels=properties.get("audio_channels"),
                is_default=bool(properties.get("default_track", False)),
                display_name=properties.get("track_name") or f"Track {entry['id']}",
            )
        )

    return tracks


def find_truehd_tracks(tracks: list[AudioTrack]) -> list[AudioTrack]:
    return [track for track in tracks if "truehd" in track.codec.lower()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tooling.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dts2ac3/models.py src/dts2ac3/tooling.py tests/test_tooling.py
git commit -m "feat: parse tracks and validate tool paths"
```

### Task 3: Add Command Builders For Probe, Convert, And Merge

**Files:**
- Modify: `src/dts2ac3/models.py`
- Modify: `src/dts2ac3/tooling.py`
- Modify: `tests/test_tooling.py`

- [ ] **Step 1: Extend the test file with failing command-builder tests**

```python
from pathlib import Path

from dts2ac3.models import AudioTrack
from dts2ac3.tooling import (
    build_eac3to_convert_command,
    build_mkvmerge_command,
    build_probe_command,
)


def test_build_probe_command_uses_mkvmerge_json_output() -> None:
    command = build_probe_command(
        Path(r"C:\Program Files\MKVToolNix"),
        Path(r"D:\media\movie.mkv"),
    )

    assert command == [
        str(Path(r"C:\Program Files\MKVToolNix") / "mkvmerge.exe"),
        "-J",
        str(Path(r"D:\media\movie.mkv")),
    ]


def test_build_eac3to_convert_command_expands_percent_placeholder() -> None:
    command = build_eac3to_convert_command(
        eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
        source_file=Path(r"D:\media\movie.mkv"),
        selected_track=AudioTrack(
            track_id=3,
            codec="TrueHD Atmos",
            language="jpn",
            channels=8,
            is_default=True,
            display_name="Japanese Atmos",
        ),
        working_dir=Path(r"D:\temp"),
        argument_template="%_.ac3 -640",
    )

    assert command == [
        str(Path(r"C:\Program Files (x86)\eac3to_3.52") / "eac3to.exe"),
        str(Path(r"D:\media\movie.mkv")),
        "4:",
        str(Path(r"D:\temp") / "movie.track3.ac3"),
        "-640",
    ]


def test_build_mkvmerge_replace_command_excludes_selected_track() -> None:
    track = AudioTrack(
        track_id=3,
        codec="TrueHD Atmos",
        language="jpn",
        channels=8,
        is_default=True,
        display_name="Japanese Atmos",
    )

    command = build_mkvmerge_command(
        mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
        source_file=Path(r"D:\media\movie.mkv"),
        output_file=Path(r"D:\exports\movie.ac3.mkv"),
        converted_audio_file=Path(r"D:\temp\movie.track3.ac3"),
        selected_track=track,
        replace_selected_truehd=True,
    )

    assert command == [
        str(Path(r"C:\Program Files\MKVToolNix") / "mkvmerge.exe"),
        "-o",
        str(Path(r"D:\exports\movie.ac3.mkv")),
        "--audio-tracks",
        "!3",
        str(Path(r"D:\media\movie.mkv")),
        "--language",
        "0:jpn",
        "--track-name",
        "0:Japanese Atmos (AC3 5.1)",
        str(Path(r"D:\temp\movie.track3.ac3")),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tooling.py -v`
Expected: FAIL with missing symbol errors for the three command builder helpers

- [ ] **Step 3: Add the command-building implementation**

`src/dts2ac3/tooling.py`

```python
from __future__ import annotations

from pathlib import Path

from dts2ac3.models import AudioTrack, ToolValidationResult


def validate_tool_directories(
    mkvtoolnix_dir: Path | None,
    eac3to_dir: Path | None,
) -> ToolValidationResult:
    errors: list[str] = []

    for required in ("mkvmerge.exe", "mkvextract.exe"):
        if mkvtoolnix_dir is None or not (mkvtoolnix_dir / required).exists():
            errors.append(required)

    if eac3to_dir is None or not (eac3to_dir / "eac3to.exe").exists():
        errors.append("eac3to.exe")

    return ToolValidationResult(is_valid=not errors, errors=errors)


def parse_mkvmerge_tracks(payload: dict) -> list[AudioTrack]:
    tracks: list[AudioTrack] = []

    for entry in payload.get("tracks", []):
        if entry.get("type") != "audio":
            continue

        properties = entry.get("properties", {})
        tracks.append(
            AudioTrack(
                track_id=entry["id"],
                codec=entry.get("codec", ""),
                language=properties.get("language", "und"),
                channels=properties.get("audio_channels"),
                is_default=bool(properties.get("default_track", False)),
                display_name=properties.get("track_name") or f"Track {entry['id']}",
            )
        )

    return tracks


def find_truehd_tracks(tracks: list[AudioTrack]) -> list[AudioTrack]:
    return [track for track in tracks if "truehd" in track.codec.lower()]


def build_probe_command(mkvtoolnix_dir: Path, source_file: Path) -> list[str]:
    return [str(mkvtoolnix_dir / "mkvmerge.exe"), "-J", str(source_file)]


def build_eac3to_convert_command(
    eac3to_dir: Path,
    source_file: Path,
    selected_track: AudioTrack,
    working_dir: Path,
    argument_template: str,
) -> list[str]:
    output_file = working_dir / f"{source_file.stem}.track{selected_track.track_id}.ac3"
    tokens = argument_template.replace("%_.ac3", str(output_file)).split()

    return [
        str(eac3to_dir / "eac3to.exe"),
        str(source_file),
        f"{selected_track.track_id + 1}:",
        *tokens,
    ]


def build_mkvmerge_command(
    mkvtoolnix_dir: Path,
    source_file: Path,
    output_file: Path,
    converted_audio_file: Path,
    selected_track: AudioTrack,
    replace_selected_truehd: bool,
) -> list[str]:
    command = [
        str(mkvtoolnix_dir / "mkvmerge.exe"),
        "-o",
        str(output_file),
    ]

    if replace_selected_truehd:
        command.extend(["--audio-tracks", f"!{selected_track.track_id}"])

    command.extend(
        [
            str(source_file),
            "--language",
            f"0:{selected_track.language}",
            "--track-name",
            f"0:{selected_track.display_name} (AC3 5.1)",
            str(converted_audio_file),
        ]
    )
    return command
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tooling.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dts2ac3/tooling.py tests/test_tooling.py
git commit -m "feat: add conversion and merge command builders"
```

### Task 4: Add Process Runner And Workflow Orchestration

**Files:**
- Modify: `src/dts2ac3/models.py`
- Create: `src/dts2ac3/process_runner.py`
- Create: `src/dts2ac3/workflow.py`
- Create: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing workflow tests**

```python
from pathlib import Path

from dts2ac3.models import AppSettings, AudioTrack, CommandResult, ToolValidationResult
from dts2ac3.workflow import WorkflowCoordinator


class FakeRunner:
    def __init__(self, results):
        self.results = results
        self.commands = []

    def run(self, command, on_output):
        self.commands.append(command)
        result = self.results.pop(0)
        for line in result.stdout_lines + result.stderr_lines:
            on_output(line)
        return result


def test_workflow_runs_probe_convert_merge_and_cleanup(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            CommandResult(
                return_code=0,
                stdout_lines=['{"tracks":[{"id":1,"type":"audio","codec":"TrueHD","properties":{"language":"eng","audio_channels":8}}]}'],
                stderr_lines=[],
            ),
            CommandResult(return_code=0, stdout_lines=["convert ok"], stderr_lines=[]),
            CommandResult(return_code=0, stdout_lines=["merge ok"], stderr_lines=[]),
        ]
    )

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    converted = work_dir / "movie.track1.ac3"
    converted.write_text("ac3", encoding="utf-8")

    logs: list[str] = []
    coordinator = WorkflowCoordinator(
        runner=runner,
        converted_audio_resolver=lambda source, track, directory: converted,
    )

    result = coordinator.run_job(
        settings=AppSettings(
            mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
            eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
            output_dir=tmp_path / "exports",
            working_dir=work_dir,
            eac3to_args="%_.ac3 -640",
            replace_selected_truehd=False,
            cleanup_temp_files=True,
        ),
        source_file=tmp_path / "movie.mkv",
        output_file_name="movie.ac3",
        selected_track_id=1,
        on_log=logs.append,
        validate_tools=lambda mkv_dir, eac_dir: ToolValidationResult(is_valid=True, errors=[]),
    )

    assert result.success is True
    assert result.output_file == tmp_path / "exports" / "movie.ac3.mkv"
    assert converted.exists() is False
    assert len(runner.commands) == 3
    assert any("merge ok" in line for line in logs)


def test_workflow_requires_explicit_truehd_selection_when_multiple_candidates_exist(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            CommandResult(
                return_code=0,
                stdout_lines=[
                    '{"tracks":['
                    '{"id":1,"type":"audio","codec":"TrueHD","properties":{"language":"jpn","audio_channels":8}},'
                    '{"id":2,"type":"audio","codec":"TrueHD Atmos","properties":{"language":"eng","audio_channels":8}}'
                    ']}'
                ],
                stderr_lines=[],
            )
        ]
    )

    coordinator = WorkflowCoordinator(runner=runner)

    result = coordinator.run_job(
        settings=AppSettings(
            mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
            eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
            output_dir=tmp_path,
            working_dir=tmp_path,
            eac3to_args="%_.ac3 -640",
        ),
        source_file=tmp_path / "movie.mkv",
        output_file_name="movie.ac3",
        selected_track_id=None,
        on_log=lambda line: None,
        validate_tools=lambda mkv_dir, eac_dir: ToolValidationResult(is_valid=True, errors=[]),
    )

    assert result.success is False
    assert result.error_message == "Select exactly one TrueHD track before running."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py -v`
Expected: FAIL with missing symbol errors for `WorkflowCoordinator` or `CommandResult`

- [ ] **Step 3: Write the minimal runner and workflow implementation**

`src/dts2ac3/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    mkvtoolnix_dir: Path | None = None
    eac3to_dir: Path | None = None
    output_dir: Path | None = None
    working_dir: Path | None = None
    eac3to_args: str = "%_.ac3 -640"
    replace_selected_truehd: bool = False
    cleanup_temp_files: bool = True


@dataclass(slots=True)
class AudioTrack:
    track_id: int
    codec: str
    language: str
    channels: int | None
    is_default: bool
    display_name: str


@dataclass(slots=True)
class ToolValidationResult:
    is_valid: bool
    errors: list[str]


@dataclass(slots=True)
class CommandResult:
    return_code: int
    stdout_lines: list[str]
    stderr_lines: list[str]


@dataclass(slots=True)
class WorkflowResult:
    success: bool
    output_file: Path | None = None
    error_message: str | None = None
```

`src/dts2ac3/process_runner.py`

```python
from __future__ import annotations

import subprocess

from dts2ac3.models import CommandResult


class ProcessRunner:
    def run(self, command: list[str], on_output) -> CommandResult:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        stdout_lines = completed.stdout.splitlines()
        stderr_lines = completed.stderr.splitlines()
        for line in stdout_lines + stderr_lines:
            on_output(line)
        return CommandResult(
            return_code=completed.returncode,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
        )
```

`src/dts2ac3/workflow.py`

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dts2ac3.models import AppSettings, ToolValidationResult, WorkflowResult
from dts2ac3.process_runner import ProcessRunner
from dts2ac3.tooling import (
    build_eac3to_convert_command,
    build_mkvmerge_command,
    build_probe_command,
    find_truehd_tracks,
    parse_mkvmerge_tracks,
    validate_tool_directories,
)


class WorkflowCoordinator:
    def __init__(
        self,
        runner: ProcessRunner,
        converted_audio_resolver: Callable[[Path, object, Path], Path] | None = None,
    ) -> None:
        self._runner = runner
        self._converted_audio_resolver = converted_audio_resolver or self._default_converted_audio_path

    def run_job(
        self,
        settings: AppSettings,
        source_file: Path,
        output_file_name: str,
        selected_track_id: int | None,
        on_log,
        validate_tools=validate_tool_directories,
    ) -> WorkflowResult:
        validation = validate_tools(settings.mkvtoolnix_dir, settings.eac3to_dir)
        if not validation.is_valid:
            return WorkflowResult(False, error_message=", ".join(validation.errors))

        try:
            truehd_tracks = self.scan_truehd_tracks(source_file, settings, on_log)
        except RuntimeError as exc:
            return WorkflowResult(False, error_message=str(exc))
        if selected_track_id is None:
            return WorkflowResult(False, error_message="Select exactly one TrueHD track before running.")

        selected_track = next(
            (track for track in truehd_tracks if track.track_id == selected_track_id),
            None,
        )
        if selected_track is None:
            return WorkflowResult(False, error_message="Selected TrueHD track was not found.")

        converted_audio = self._converted_audio_resolver(
            source_file,
            selected_track,
            settings.working_dir,
        )
        convert_result = self._runner.run(
            build_eac3to_convert_command(
                settings.eac3to_dir,
                source_file,
                selected_track,
                settings.working_dir,
                settings.eac3to_args,
            ),
            on_log,
        )
        if convert_result.return_code != 0 or not converted_audio.exists():
            return WorkflowResult(False, error_message="Audio conversion failed.")

        output_file = settings.output_dir / f"{output_file_name}.mkv"
        merge_result = self._runner.run(
            build_mkvmerge_command(
                settings.mkvtoolnix_dir,
                source_file,
                output_file,
                converted_audio,
                selected_track,
                settings.replace_selected_truehd,
            ),
            on_log,
        )
        if merge_result.return_code != 0:
            return WorkflowResult(False, error_message="Muxing failed.")

        if settings.cleanup_temp_files and converted_audio.exists():
            converted_audio.unlink()

        return WorkflowResult(True, output_file=output_file)

    def scan_truehd_tracks(self, source_file: Path, settings: AppSettings, on_log=lambda line: None):
        probe_result = self._runner.run(
            build_probe_command(settings.mkvtoolnix_dir, source_file),
            on_log,
        )
        if probe_result.return_code != 0:
            raise RuntimeError("Track scan failed.")

        probe_payload = json.loads("".join(probe_result.stdout_lines))
        return find_truehd_tracks(parse_mkvmerge_tracks(probe_payload))

    @staticmethod
    def _default_converted_audio_path(source_file: Path, selected_track, working_dir: Path) -> Path:
        return working_dir / f"{source_file.stem}.track{selected_track.track_id}.ac3"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dts2ac3/models.py src/dts2ac3/process_runner.py src/dts2ac3/workflow.py tests/test_workflow.py
git commit -m "feat: add workflow orchestration"
```

### Task 5: Improve The Runner For Real-Time Logs And Cancellation

**Files:**
- Modify: `src/dts2ac3/models.py`
- Modify: `src/dts2ac3/process_runner.py`
- Modify: `src/dts2ac3/workflow.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Add failing tests for streamed output and cancellation**

```python
from dts2ac3.models import AppSettings, CommandResult, ToolValidationResult
from dts2ac3.workflow import WorkflowCoordinator


class CancelAwareRunner:
    def __init__(self):
        self.cancel_requested = False

    def run(self, command, on_output):
        on_output("line 1")
        if self.cancel_requested:
            return CommandResult(return_code=130, stdout_lines=["line 1"], stderr_lines=["cancelled"])
        on_output("line 2")
        return CommandResult(return_code=0, stdout_lines=["line 1", "line 2"], stderr_lines=[])

    def cancel(self):
        self.cancel_requested = True


def test_cancel_marks_result_as_cancelled(tmp_path):
    runner = CancelAwareRunner()
    coordinator = WorkflowCoordinator(runner=runner)

    coordinator.cancel()
    result = coordinator.run_job(
        settings=AppSettings(
            mkvtoolnix_dir=tmp_path,
            eac3to_dir=tmp_path,
            output_dir=tmp_path,
            working_dir=tmp_path,
        ),
        source_file=tmp_path / "movie.mkv",
        output_file_name="movie.ac3",
        selected_track_id=1,
        on_log=lambda line: None,
        validate_tools=lambda mkv_dir, eac_dir: ToolValidationResult(is_valid=True, errors=[]),
    )

    assert result.success is False
    assert result.error_message == "Job canceled."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py -k cancel -v`
Expected: FAIL because `WorkflowCoordinator.cancel` does not exist yet

- [ ] **Step 3: Implement cancellation-aware runner behavior**

`src/dts2ac3/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    mkvtoolnix_dir: Path | None = None
    eac3to_dir: Path | None = None
    output_dir: Path | None = None
    working_dir: Path | None = None
    eac3to_args: str = "%_.ac3 -640"
    replace_selected_truehd: bool = False
    cleanup_temp_files: bool = True


@dataclass(slots=True)
class AudioTrack:
    track_id: int
    codec: str
    language: str
    channels: int | None
    is_default: bool
    display_name: str


@dataclass(slots=True)
class ToolValidationResult:
    is_valid: bool
    errors: list[str]


@dataclass(slots=True)
class CommandResult:
    return_code: int
    stdout_lines: list[str]
    stderr_lines: list[str]
    cancelled: bool = False


@dataclass(slots=True)
class WorkflowResult:
    success: bool
    output_file: Path | None = None
    error_message: str | None = None
```

`src/dts2ac3/process_runner.py`

```python
from __future__ import annotations

import subprocess

from dts2ac3.models import CommandResult


class ProcessRunner:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None

    def run(self, command: list[str], on_output) -> CommandResult:
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        assert self._process.stdout is not None
        for line in self._process.stdout:
            clean = line.rstrip("\r\n")
            stdout_lines.append(clean)
            on_output(clean)

        assert self._process.stderr is not None
        for line in self._process.stderr:
            clean = line.rstrip("\r\n")
            stderr_lines.append(clean)
            on_output(clean)

        return_code = self._process.wait()
        cancelled = return_code == 130
        self._process = None
        return CommandResult(
            return_code=return_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            cancelled=cancelled,
        )

    def cancel(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
```

`src/dts2ac3/workflow.py`

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dts2ac3.models import AppSettings, WorkflowResult
from dts2ac3.process_runner import ProcessRunner
from dts2ac3.tooling import (
    build_eac3to_convert_command,
    build_mkvmerge_command,
    build_probe_command,
    find_truehd_tracks,
    parse_mkvmerge_tracks,
    validate_tool_directories,
)


class WorkflowCoordinator:
    def __init__(
        self,
        runner: ProcessRunner,
        converted_audio_resolver: Callable[[Path, object, Path], Path] | None = None,
    ) -> None:
        self._runner = runner
        self._converted_audio_resolver = converted_audio_resolver or self._default_converted_audio_path
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        if hasattr(self._runner, "cancel"):
            self._runner.cancel()

    def run_job(
        self,
        settings: AppSettings,
        source_file: Path,
        output_file_name: str,
        selected_track_id: int | None,
        on_log,
        validate_tools=validate_tool_directories,
    ) -> WorkflowResult:
        if self._cancel_requested:
            return WorkflowResult(False, error_message="Job canceled.")

        validation = validate_tools(settings.mkvtoolnix_dir, settings.eac3to_dir)
        if not validation.is_valid:
            return WorkflowResult(False, error_message=", ".join(validation.errors))

        probe_result = self._runner.run(build_probe_command(settings.mkvtoolnix_dir, source_file), on_log)
        if probe_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if probe_result.return_code != 0:
            return WorkflowResult(False, error_message="Track scan failed.")

        probe_payload = json.loads("".join(probe_result.stdout_lines))
        truehd_tracks = find_truehd_tracks(parse_mkvmerge_tracks(probe_payload))
        if selected_track_id is None:
            return WorkflowResult(False, error_message="Select exactly one TrueHD track before running.")

        selected_track = next((track for track in truehd_tracks if track.track_id == selected_track_id), None)
        if selected_track is None:
            return WorkflowResult(False, error_message="Selected TrueHD track was not found.")

        converted_audio = self._converted_audio_resolver(source_file, selected_track, settings.working_dir)
        convert_result = self._runner.run(
            build_eac3to_convert_command(
                settings.eac3to_dir,
                source_file,
                selected_track,
                settings.working_dir,
                settings.eac3to_args,
            ),
            on_log,
        )
        if convert_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if convert_result.return_code != 0 or not converted_audio.exists():
            return WorkflowResult(False, error_message="Audio conversion failed.")

        output_file = settings.output_dir / f"{output_file_name}.mkv"
        merge_result = self._runner.run(
            build_mkvmerge_command(
                settings.mkvtoolnix_dir,
                source_file,
                output_file,
                converted_audio,
                selected_track,
                settings.replace_selected_truehd,
            ),
            on_log,
        )
        if merge_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if merge_result.return_code != 0:
            return WorkflowResult(False, error_message="Muxing failed.")

        if settings.cleanup_temp_files and converted_audio.exists():
            converted_audio.unlink()

        return WorkflowResult(True, output_file=output_file)

    @staticmethod
    def _default_converted_audio_path(source_file: Path, selected_track, working_dir: Path) -> Path:
        return working_dir / f"{source_file.stem}.track{selected_track.track_id}.ac3"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dts2ac3/models.py src/dts2ac3/process_runner.py src/dts2ac3/workflow.py tests/test_workflow.py
git commit -m "feat: support cancellation and streamed logs"
```

### Task 6: Build The Main Window And Hook It To The Workflow

**Files:**
- Create: `src/dts2ac3/main.py`
- Create: `src/dts2ac3/ui/__init__.py`
- Create: `src/dts2ac3/ui/main_window.py`
- Create: `tests/conftest.py`
- Create: `tests/test_main_window.py`

- [ ] **Step 1: Write the failing GUI tests**

```python
from pathlib import Path

from dts2ac3.models import AppSettings, AudioTrack
from dts2ac3.ui.main_window import MainWindow


def test_scan_results_populate_truehd_track_dropdown(qtbot, tmp_path: Path) -> None:
    settings = AppSettings(
        mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
        eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
        output_dir=tmp_path,
        working_dir=tmp_path,
    )
    window = MainWindow(
        settings=settings,
        scan_tracks=lambda path: [
            AudioTrack(1, "TrueHD Atmos", "jpn", 8, True, "Japanese Atmos"),
            AudioTrack(2, "TrueHD", "eng", 8, False, "English TrueHD"),
        ],
        run_job=lambda **kwargs: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    window.source_file_edit.setText(str(tmp_path / "movie.mkv"))
    window.handle_scan_tracks()

    assert window.track_combo.count() == 2
    assert window.track_combo.itemData(0) == 1
    assert "Japanese Atmos" in window.track_combo.itemText(0)


def test_log_append_writes_lines_to_text_box(qtbot, tmp_path: Path) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path: [],
        run_job=lambda **kwargs: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    window.append_log("mkvmerge started")

    assert "mkvmerge started" in window.log_output.toPlainText()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_window.py -v`
Expected: FAIL with `ModuleNotFoundError` for `dts2ac3.ui.main_window`

- [ ] **Step 3: Implement the GUI skeleton**

`src/dts2ac3/main.py`

```python
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from dts2ac3.models import AppSettings
from dts2ac3.process_runner import ProcessRunner
from dts2ac3.settings import AppSettingsStore
from dts2ac3.tooling import find_truehd_tracks, parse_mkvmerge_tracks
from dts2ac3.ui.main_window import MainWindow
from dts2ac3.workflow import WorkflowCoordinator


def main() -> int:
    app = QApplication(sys.argv)
    settings_path = Path(os.environ.get("APPDATA", ".")) / "DTS2AC3" / "settings.json"
    store = AppSettingsStore(settings_path)
    settings = store.load()
    workflow = WorkflowCoordinator(ProcessRunner())

    window = MainWindow(
        settings=settings,
        scan_tracks=lambda path: workflow.scan_truehd_tracks(path, settings),
        run_job=workflow.run_job,
        save_settings=store.save,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

`src/dts2ac3/ui/__init__.py`

```python
__all__ = ["main_window"]
```

`src/dts2ac3/ui/main_window.py`

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from dts2ac3.models import AppSettings, AudioTrack


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, scan_tracks, run_job, save_settings) -> None:
        super().__init__()
        self._settings = settings
        self._scan_tracks = scan_tracks
        self._run_job = run_job
        self._save_settings = save_settings
        self._tracks: list[AudioTrack] = []
        self.setWindowTitle("DTS2AC3")
        self.resize(980, 720)
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        form = QFormLayout()

        self.mkvtoolnix_edit = QLineEdit()
        self.eac3to_edit = QLineEdit()
        self.source_file_edit = QLineEdit()
        self.output_dir_edit = QLineEdit()
        self.working_dir_edit = QLineEdit()
        self.output_name_edit = QLineEdit()
        self.eac3to_args_edit = QLineEdit()
        self.track_combo = QComboBox()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self.keep_radio = QRadioButton("保留原 TrueHD")
        self.replace_radio = QRadioButton("替换选中的 TrueHD")
        self.cleanup_checkbox = QCheckBox("完成后删除临时文件")
        self.scan_button = QPushButton("扫描音轨")
        self.start_button = QPushButton("开始处理")

        form.addRow("MKVToolNix 目录", self.mkvtoolnix_edit)
        form.addRow("eac3to 目录", self.eac3to_edit)
        form.addRow("源文件", self.source_file_edit)
        form.addRow("导出目录", self.output_dir_edit)
        form.addRow("工作目录", self.working_dir_edit)
        form.addRow("输出文件名", self.output_name_edit)
        form.addRow("TrueHD 音轨", self.track_combo)
        form.addRow("eac3to 参数", self.eac3to_args_edit)

        radio_row = QHBoxLayout()
        radio_row.addWidget(self.keep_radio)
        radio_row.addWidget(self.replace_radio)

        layout.addLayout(form)
        layout.addLayout(radio_row)
        layout.addWidget(self.cleanup_checkbox)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.start_button)
        layout.addWidget(QLabel("命令输出"))
        layout.addWidget(self.log_output)
        self.setCentralWidget(central)

        self.scan_button.clicked.connect(self.handle_scan_tracks)
        self.start_button.clicked.connect(self.handle_run_job)

    def _load_settings(self) -> None:
        if self._settings.mkvtoolnix_dir:
            self.mkvtoolnix_edit.setText(str(self._settings.mkvtoolnix_dir))
        if self._settings.eac3to_dir:
            self.eac3to_edit.setText(str(self._settings.eac3to_dir))
        if self._settings.output_dir:
            self.output_dir_edit.setText(str(self._settings.output_dir))
        if self._settings.working_dir:
            self.working_dir_edit.setText(str(self._settings.working_dir))
        self.eac3to_args_edit.setText(self._settings.eac3to_args)
        self.replace_radio.setChecked(self._settings.replace_selected_truehd)
        self.keep_radio.setChecked(not self._settings.replace_selected_truehd)
        self.cleanup_checkbox.setChecked(self._settings.cleanup_temp_files)

    def handle_scan_tracks(self) -> None:
        source_path = Path(self.source_file_edit.text().strip())
        self.track_combo.clear()
        self._tracks = self._scan_tracks(source_path)
        for track in self._tracks:
            label = f"#{track.track_id} | {track.language} | {track.codec} | {track.display_name}"
            self.track_combo.addItem(label, track.track_id)

    def handle_run_job(self) -> None:
        selected_track_id = self.track_combo.currentData()
        self._settings.mkvtoolnix_dir = Path(self.mkvtoolnix_edit.text().strip()) if self.mkvtoolnix_edit.text().strip() else None
        self._settings.eac3to_dir = Path(self.eac3to_edit.text().strip()) if self.eac3to_edit.text().strip() else None
        self._settings.output_dir = Path(self.output_dir_edit.text().strip()) if self.output_dir_edit.text().strip() else None
        self._settings.working_dir = Path(self.working_dir_edit.text().strip()) if self.working_dir_edit.text().strip() else None
        self._settings.eac3to_args = self.eac3to_args_edit.text().strip()
        self._settings.replace_selected_truehd = self.replace_radio.isChecked()
        self._settings.cleanup_temp_files = self.cleanup_checkbox.isChecked()
        self._save_settings(self._settings)
        result = self._run_job(
            settings=self._settings,
            source_file=Path(self.source_file_edit.text().strip()),
            output_file_name=self.output_name_edit.text().strip(),
            selected_track_id=selected_track_id,
            on_log=self.append_log,
        )
        if result.success:
            self.append_log(f"Done: {result.output_file}")
        else:
            QMessageBox.critical(self, "处理失败", result.error_message or "Unknown error")

    def append_log(self, line: str) -> None:
        self.log_output.appendPlainText(line)
```

`tests/conftest.py`

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dts2ac3/main.py src/dts2ac3/ui/__init__.py src/dts2ac3/ui/main_window.py tests/conftest.py tests/test_main_window.py
git commit -m "feat: add PySide6 main window"
```

### Task 7: Auto-Fill Output Name And Polish Scan-State Messaging

**Files:**
- Modify: `src/dts2ac3/workflow.py`
- Modify: `src/dts2ac3/ui/main_window.py`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_main_window.py`

- [ ] **Step 1: Add failing GUI tests for source-name autofill and empty TrueHD results**

```python
def test_source_file_prefills_output_name(qtbot, tmp_path: Path) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path: [],
        run_job=lambda **kwargs: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    source = tmp_path / "Movie.Name.2026.mkv"
    window.source_file_edit.setText(str(source))
    window.handle_source_file_changed(str(source))

    assert window.output_name_edit.text() == "Movie.Name.2026"


def test_scan_with_no_truehd_tracks_logs_clear_message(qtbot, tmp_path: Path) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path: [],
        run_job=lambda **kwargs: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    window.source_file_edit.setText(str(tmp_path / "movie.mkv"))
    window.handle_scan_tracks()

    assert "No TrueHD tracks detected." in window.log_output.toPlainText()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_window.py -k "prefills_output_name or no_truehd" -v`
Expected: FAIL because `handle_source_file_changed` does not exist yet and the source field does not auto-fill the output name

- [ ] **Step 3: Implement output-name autofill and better main-window scan messaging**

`src/dts2ac3/workflow.py`

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dts2ac3.models import AppSettings, WorkflowResult
from dts2ac3.process_runner import ProcessRunner
from dts2ac3.tooling import (
    build_eac3to_convert_command,
    build_mkvmerge_command,
    build_probe_command,
    find_truehd_tracks,
    parse_mkvmerge_tracks,
    validate_tool_directories,
)


class WorkflowCoordinator:
    def __init__(
        self,
        runner: ProcessRunner,
        converted_audio_resolver: Callable[[Path, object, Path], Path] | None = None,
    ) -> None:
        self._runner = runner
        self._converted_audio_resolver = converted_audio_resolver or self._default_converted_audio_path
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        if hasattr(self._runner, "cancel"):
            self._runner.cancel()

    def scan_truehd_tracks(self, source_file: Path, settings: AppSettings, on_log=lambda line: None):
        probe_result = self._runner.run(build_probe_command(settings.mkvtoolnix_dir, source_file), on_log)
        if probe_result.return_code != 0:
            raise RuntimeError("Track scan failed.")
        probe_payload = json.loads("".join(probe_result.stdout_lines))
        return find_truehd_tracks(parse_mkvmerge_tracks(probe_payload))

    def run_job(
        self,
        settings: AppSettings,
        source_file: Path,
        output_file_name: str,
        selected_track_id: int | None,
        on_log,
        validate_tools=validate_tool_directories,
    ) -> WorkflowResult:
        if self._cancel_requested:
            return WorkflowResult(False, error_message="Job canceled.")

        validation = validate_tools(settings.mkvtoolnix_dir, settings.eac3to_dir)
        if not validation.is_valid:
            return WorkflowResult(False, error_message=", ".join(validation.errors))

        try:
            truehd_tracks = self.scan_truehd_tracks(source_file, settings, on_log)
        except RuntimeError as exc:
            return WorkflowResult(False, error_message=str(exc))

        if selected_track_id is None:
            return WorkflowResult(False, error_message="Select exactly one TrueHD track before running.")

        selected_track = next((track for track in truehd_tracks if track.track_id == selected_track_id), None)
        if selected_track is None:
            return WorkflowResult(False, error_message="Selected TrueHD track was not found.")

        converted_audio = self._converted_audio_resolver(source_file, selected_track, settings.working_dir)
        convert_result = self._runner.run(
            build_eac3to_convert_command(
                settings.eac3to_dir,
                source_file,
                selected_track,
                settings.working_dir,
                settings.eac3to_args,
            ),
            on_log,
        )
        if convert_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if convert_result.return_code != 0 or not converted_audio.exists():
            return WorkflowResult(False, error_message="Audio conversion failed.")

        output_file = settings.output_dir / f"{output_file_name}.mkv"
        merge_result = self._runner.run(
            build_mkvmerge_command(
                settings.mkvtoolnix_dir,
                source_file,
                output_file,
                converted_audio,
                selected_track,
                settings.replace_selected_truehd,
            ),
            on_log,
        )
        if merge_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if merge_result.return_code != 0:
            return WorkflowResult(False, error_message="Muxing failed.")

        if settings.cleanup_temp_files and converted_audio.exists():
            converted_audio.unlink()

        return WorkflowResult(True, output_file=output_file)

    @staticmethod
    def _default_converted_audio_path(source_file: Path, selected_track, working_dir: Path) -> Path:
        return working_dir / f"{source_file.stem}.track{selected_track.track_id}.ac3"
```

`src/dts2ac3/ui/main_window.py`

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from dts2ac3.models import AppSettings, AudioTrack


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, scan_tracks, run_job, save_settings) -> None:
        super().__init__()
        self._settings = settings
        self._scan_tracks = scan_tracks
        self._run_job = run_job
        self._save_settings = save_settings
        self._tracks: list[AudioTrack] = []
        self.setWindowTitle("DTS2AC3")
        self.resize(980, 720)
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        form = QFormLayout()

        self.mkvtoolnix_edit = QLineEdit()
        self.eac3to_edit = QLineEdit()
        self.source_file_edit = QLineEdit()
        self.output_dir_edit = QLineEdit()
        self.working_dir_edit = QLineEdit()
        self.output_name_edit = QLineEdit()
        self.eac3to_args_edit = QLineEdit()
        self.track_combo = QComboBox()
        self.track_combo.setPlaceholderText("先扫描 TrueHD 音轨")
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self.keep_radio = QRadioButton("保留原 TrueHD")
        self.replace_radio = QRadioButton("替换选中的 TrueHD")
        self.cleanup_checkbox = QCheckBox("完成后删除临时文件")
        self.scan_button = QPushButton("扫描音轨")
        self.start_button = QPushButton("开始处理")

        form.addRow("MKVToolNix 目录", self.mkvtoolnix_edit)
        form.addRow("eac3to 目录", self.eac3to_edit)
        form.addRow("源文件", self.source_file_edit)
        form.addRow("导出目录", self.output_dir_edit)
        form.addRow("工作目录", self.working_dir_edit)
        form.addRow("输出文件名", self.output_name_edit)
        form.addRow("TrueHD 音轨", self.track_combo)
        form.addRow("eac3to 参数", self.eac3to_args_edit)

        radio_row = QHBoxLayout()
        radio_row.addWidget(self.keep_radio)
        radio_row.addWidget(self.replace_radio)

        layout.addLayout(form)
        layout.addLayout(radio_row)
        layout.addWidget(self.cleanup_checkbox)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.start_button)
        layout.addWidget(QLabel("命令输出"))
        layout.addWidget(self.log_output)
        self.setCentralWidget(central)

        self.scan_button.clicked.connect(self.handle_scan_tracks)
        self.start_button.clicked.connect(self.handle_run_job)
        self.source_file_edit.textChanged.connect(self.handle_source_file_changed)

    def _load_settings(self) -> None:
        if self._settings.mkvtoolnix_dir:
            self.mkvtoolnix_edit.setText(str(self._settings.mkvtoolnix_dir))
        if self._settings.eac3to_dir:
            self.eac3to_edit.setText(str(self._settings.eac3to_dir))
        if self._settings.output_dir:
            self.output_dir_edit.setText(str(self._settings.output_dir))
        if self._settings.working_dir:
            self.working_dir_edit.setText(str(self._settings.working_dir))
        self.eac3to_args_edit.setText(self._settings.eac3to_args)
        self.replace_radio.setChecked(self._settings.replace_selected_truehd)
        self.keep_radio.setChecked(not self._settings.replace_selected_truehd)
        self.cleanup_checkbox.setChecked(self._settings.cleanup_temp_files)

    def handle_scan_tracks(self) -> None:
        source_text = self.source_file_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "缺少源文件", "请先选择要扫描的片源文件。")
            return

        source_path = Path(source_text)
        self.track_combo.clear()
        self.append_log(f"Scanning: {source_path}")
        try:
            self._tracks = self._scan_tracks(source_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "扫描失败", str(exc))
            return

        if not self._tracks:
            self.append_log("No TrueHD tracks detected.")
            QMessageBox.information(self, "未找到 TrueHD", "没有检测到可转换的 TrueHD 音轨。")
            return

        for track in self._tracks:
            channel_text = f"{track.channels}ch" if track.channels is not None else "unknown"
            label = f"#{track.track_id} | {track.language} | {channel_text} | {track.codec} | {track.display_name}"
            self.track_combo.addItem(label, track.track_id)

    def handle_source_file_changed(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        source_path = Path(cleaned)
        if not self.output_name_edit.text().strip():
            self.output_name_edit.setText(source_path.stem)

    def handle_run_job(self) -> None:
        source_text = self.source_file_edit.text().strip()
        output_name = self.output_name_edit.text().strip()
        if not source_text or not output_name:
            QMessageBox.warning(self, "缺少参数", "请先填写源文件和输出文件名。")
            return

        selected_track_id = self.track_combo.currentData()
        self._settings.mkvtoolnix_dir = Path(self.mkvtoolnix_edit.text().strip()) if self.mkvtoolnix_edit.text().strip() else None
        self._settings.eac3to_dir = Path(self.eac3to_edit.text().strip()) if self.eac3to_edit.text().strip() else None
        self._settings.output_dir = Path(self.output_dir_edit.text().strip()) if self.output_dir_edit.text().strip() else None
        self._settings.working_dir = Path(self.working_dir_edit.text().strip()) if self.working_dir_edit.text().strip() else None
        self._settings.eac3to_args = self.eac3to_args_edit.text().strip()
        self._settings.replace_selected_truehd = self.replace_radio.isChecked()
        self._settings.cleanup_temp_files = self.cleanup_checkbox.isChecked()
        self._save_settings(self._settings)

        result = self._run_job(
            settings=self._settings,
            source_file=Path(source_text),
            output_file_name=output_name,
            selected_track_id=selected_track_id,
            on_log=self.append_log,
        )
        if result.success:
            self.append_log(f"Done: {result.output_file}")
        else:
            QMessageBox.critical(self, "处理失败", result.error_message or "Unknown error")

    def append_log(self, line: str) -> None:
        self.log_output.appendPlainText(line)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dts2ac3/ui/main_window.py tests/test_main_window.py
git commit -m "feat: polish source naming and scan messaging"
```

### Task 8: Write README And Final Smoke Verification

**Files:**
- Create: `README.md`
- Modify: `tests/test_workflow.py`
- Modify: `src/dts2ac3/workflow.py`

- [ ] **Step 1: Add a failing cleanup-warning test**

```python
def test_cleanup_failure_is_logged_but_not_fatal(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            CommandResult(
                return_code=0,
                stdout_lines=['{"tracks":[{"id":1,"type":"audio","codec":"TrueHD","properties":{"language":"eng","audio_channels":8}}]}'],
                stderr_lines=[],
            ),
            CommandResult(return_code=0, stdout_lines=["convert ok"], stderr_lines=[]),
            CommandResult(return_code=0, stdout_lines=["merge ok"], stderr_lines=[]),
        ]
    )

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    converted = work_dir / "movie.track1.ac3"
    converted.write_text("ac3", encoding="utf-8")

    logs: list[str] = []
    coordinator = WorkflowCoordinator(
        runner=runner,
        converted_audio_resolver=lambda source, track, directory: converted,
    )

    original_unlink = Path.unlink

    def broken_unlink(self):
        if self == converted:
            raise OSError("cleanup denied")
        return original_unlink(self)

    Path.unlink = broken_unlink
    try:
        result = coordinator.run_job(
            settings=AppSettings(
                mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
                eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
                output_dir=tmp_path / "exports",
                working_dir=work_dir,
                eac3to_args="%_.ac3 -640",
                replace_selected_truehd=False,
                cleanup_temp_files=True,
            ),
            source_file=tmp_path / "movie.mkv",
            output_file_name="movie.ac3",
            selected_track_id=1,
            on_log=logs.append,
            validate_tools=lambda mkv_dir, eac_dir: ToolValidationResult(is_valid=True, errors=[]),
        )
    finally:
        Path.unlink = original_unlink

    assert result.success is True
    assert any("cleanup denied" in line for line in logs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py -k cleanup_failure -v`
Expected: FAIL because cleanup exceptions are not logged or handled yet

- [ ] **Step 3: Handle cleanup warnings and write the README**

`src/dts2ac3/workflow.py`

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dts2ac3.models import AppSettings, WorkflowResult
from dts2ac3.process_runner import ProcessRunner
from dts2ac3.tooling import (
    build_eac3to_convert_command,
    build_mkvmerge_command,
    build_probe_command,
    find_truehd_tracks,
    parse_mkvmerge_tracks,
    validate_tool_directories,
)


class WorkflowCoordinator:
    def __init__(
        self,
        runner: ProcessRunner,
        converted_audio_resolver: Callable[[Path, object, Path], Path] | None = None,
    ) -> None:
        self._runner = runner
        self._converted_audio_resolver = converted_audio_resolver or self._default_converted_audio_path
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        if hasattr(self._runner, "cancel"):
            self._runner.cancel()

    def scan_truehd_tracks(self, source_file: Path, settings: AppSettings, on_log=lambda line: None):
        probe_result = self._runner.run(build_probe_command(settings.mkvtoolnix_dir, source_file), on_log)
        if probe_result.return_code != 0:
            raise RuntimeError("Track scan failed.")
        probe_payload = json.loads("".join(probe_result.stdout_lines))
        return find_truehd_tracks(parse_mkvmerge_tracks(probe_payload))

    def run_job(
        self,
        settings: AppSettings,
        source_file: Path,
        output_file_name: str,
        selected_track_id: int | None,
        on_log,
        validate_tools=validate_tool_directories,
    ) -> WorkflowResult:
        if self._cancel_requested:
            return WorkflowResult(False, error_message="Job canceled.")

        validation = validate_tools(settings.mkvtoolnix_dir, settings.eac3to_dir)
        if not validation.is_valid:
            return WorkflowResult(False, error_message=", ".join(validation.errors))

        try:
            truehd_tracks = self.scan_truehd_tracks(source_file, settings, on_log)
        except RuntimeError as exc:
            return WorkflowResult(False, error_message=str(exc))

        if selected_track_id is None:
            return WorkflowResult(False, error_message="Select exactly one TrueHD track before running.")

        selected_track = next((track for track in truehd_tracks if track.track_id == selected_track_id), None)
        if selected_track is None:
            return WorkflowResult(False, error_message="Selected TrueHD track was not found.")

        converted_audio = self._converted_audio_resolver(source_file, selected_track, settings.working_dir)
        convert_result = self._runner.run(
            build_eac3to_convert_command(
                settings.eac3to_dir,
                source_file,
                selected_track,
                settings.working_dir,
                settings.eac3to_args,
            ),
            on_log,
        )
        if convert_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if convert_result.return_code != 0 or not converted_audio.exists():
            return WorkflowResult(False, error_message="Audio conversion failed.")

        output_file = settings.output_dir / f"{output_file_name}.mkv"
        merge_result = self._runner.run(
            build_mkvmerge_command(
                settings.mkvtoolnix_dir,
                source_file,
                output_file,
                converted_audio,
                selected_track,
                settings.replace_selected_truehd,
            ),
            on_log,
        )
        if merge_result.cancelled:
            return WorkflowResult(False, error_message="Job canceled.")
        if merge_result.return_code != 0:
            return WorkflowResult(False, error_message="Muxing failed.")

        if settings.cleanup_temp_files and converted_audio.exists():
            try:
                converted_audio.unlink()
            except OSError as exc:
                on_log(f"Warning: failed to remove temporary file: {exc}")

        return WorkflowResult(True, output_file=output_file)

    @staticmethod
    def _default_converted_audio_path(source_file: Path, selected_track, working_dir: Path) -> Path:
        return working_dir / f"{source_file.stem}.track{selected_track.track_id}.ac3"
```

`README.md`

```markdown
# DTS2AC3

PySide6 desktop utility for Windows that automates a TrueHD-to-AC3 workflow with MKVToolNix and eac3to.

## Features

- Remembers MKVToolNix and eac3to installation directories
- Scans source files with MKVToolNix JSON output
- Lists all detected TrueHD tracks and requires the user to choose one
- Converts the selected TrueHD track to AC3 using configurable eac3to arguments
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
python -m dts2ac3.main
```

## Test

```powershell
python -m pytest
```
```

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS

- [ ] **Step 5: Manual smoke test**

Run:

```powershell
python -m dts2ac3.main
```

Expected:

- Window opens without crashing
- Settings fields load
- Track scan button is usable
- Log area accepts appended output

- [ ] **Step 6: Commit**

```bash
git add README.md src/dts2ac3/workflow.py tests/test_workflow.py
git commit -m "docs: add setup guide and final verification"
```

## Self-Review Notes

### Spec Coverage

- Saved tool paths and defaults: Task 1
- TrueHD scan and multiple-track selection: Tasks 2, 6, and 7
- eac3to `%_.ac3 -640` handling: Task 3
- Preserve vs replace selected TrueHD: Tasks 3 and 8
- Real-time embedded logs and raw tool errors: Tasks 4, 5, 6, and 7
- Working directory cleanup: Task 4
- Single-file scope: enforced across Tasks 4 to 7

### Placeholder Scan

- No `TODO`, `TBD`, or deferred “implement later” markers remain.
- Every code-changing step includes concrete code or command content.

### Type Consistency

- `AppSettings`, `AudioTrack`, `CommandResult`, and `WorkflowResult` names stay consistent across tasks.
- `selected_track_id` is the GUI-to-workflow boundary everywhere.
- The same output naming rule `output_file_name + ".mkv"` is used throughout the plan.
