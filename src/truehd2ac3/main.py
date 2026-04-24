from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from truehd2ac3.process_runner import ProcessRunner
from truehd2ac3.settings import AppSettingsStore
from truehd2ac3.ui.main_window import MainWindow
from truehd2ac3.workflow import WorkflowCoordinator


def resolve_settings_path() -> Path:
    appdata_root = Path(os.environ.get("APPDATA", "."))
    new_settings_path = appdata_root / "TrueHD2AC3" / "settings.json"
    old_settings_path = appdata_root / "DTS2AC3" / "settings.json"

    if not new_settings_path.exists() and old_settings_path.exists():
        new_settings_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_settings_path, new_settings_path)

    return new_settings_path


def main() -> int:
    app = QApplication(sys.argv)
    settings_path = resolve_settings_path()
    store = AppSettingsStore(settings_path)
    settings = store.load()
    workflow = WorkflowCoordinator(ProcessRunner())

    window = MainWindow(
        settings=settings,
        scan_tracks=workflow.scan_audio_tracks,
        run_job=workflow.run_job,
        cancel_job=workflow.cancel,
        save_settings=store.save,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
