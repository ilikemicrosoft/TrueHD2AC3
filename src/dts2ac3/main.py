from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from dts2ac3.process_runner import ProcessRunner
from dts2ac3.settings import AppSettingsStore
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
        cancel_job=workflow.cancel,
        save_settings=store.save,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
