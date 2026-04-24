from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from truehd2ac3.models import AppSettings


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
