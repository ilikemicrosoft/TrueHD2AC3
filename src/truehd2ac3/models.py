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
