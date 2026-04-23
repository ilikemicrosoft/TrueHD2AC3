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
