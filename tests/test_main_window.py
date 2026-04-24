from pathlib import Path

from PySide6.QtCore import Qt

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
        scan_tracks=lambda path, runtime_settings: [
            AudioTrack(1, "TrueHD Atmos", "jpn", 8, True, "Japanese Atmos"),
            AudioTrack(2, "AC-3", "eng", 6, False, "English AC3"),
            AudioTrack(3, "TrueHD", "eng", 8, False, "English TrueHD"),
        ],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    window.source_file_edit.setText(str(tmp_path / "movie.mkv"))
    window.handle_scan_tracks()

    assert window.track_combo.count() == 2
    assert window.track_combo.itemData(0) == 1
    assert "Japanese Atmos" in window.track_combo.itemText(0)
    assert window.track_combo.itemData(1) == 3
    assert window.audio_track_list.count() == 3
    assert "English AC3" in window.audio_track_list.item(1).text()
    assert not window.audio_track_list.item(1).flags() & Qt.ItemFlag.ItemIsEnabled


def test_log_append_writes_lines_to_text_box(qtbot, tmp_path: Path) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path, runtime_settings: [],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    window.append_log("mkvmerge started")

    assert "mkvmerge started" in window.log_output.toPlainText()


def test_source_file_prefills_output_name(qtbot, tmp_path: Path) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path, runtime_settings: [],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)

    source = tmp_path / "Movie.Name.2026.mkv"
    window.source_file_edit.setText(str(source))
    window.handle_source_file_changed(str(source))

    assert window.output_name_edit.text() == "Movie.Name.2026"


def test_scan_with_no_truehd_tracks_logs_clear_message(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path, runtime_settings: [],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "dts2ac3.ui.main_window.QMessageBox.information",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "dts2ac3.ui.main_window.QMessageBox.critical",
        lambda *args, **kwargs: None,
    )

    window.source_file_edit.setText(str(tmp_path / "movie.mkv"))
    window.handle_scan_tracks()

    assert "No TrueHD tracks detected." in window.log_output.toPlainText()


def test_scan_uses_current_form_settings(qtbot, tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, Path | None] = {}

    def scan_tracks(path: Path, settings: AppSettings):
        captured["source_file"] = path
        captured["mkvtoolnix_dir"] = settings.mkvtoolnix_dir
        captured["eac3to_dir"] = settings.eac3to_dir
        return []

    window = MainWindow(
        settings=AppSettings(),
        scan_tracks=scan_tracks,
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
    )
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "dts2ac3.ui.main_window.QMessageBox.information",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "dts2ac3.ui.main_window.QMessageBox.critical",
        lambda *args, **kwargs: None,
    )

    source_file = tmp_path / "movie.mkv"
    window.mkvtoolnix_edit.setText(r"C:\Program Files\MKVToolNix")
    window.eac3to_edit.setText(r"C:\Program Files (x86)\eac3to_3.52")
    window.source_file_edit.setText(str(source_file))
    window.handle_scan_tracks()

    assert captured["source_file"] == source_file
    assert captured["mkvtoolnix_dir"] == Path(r"C:\Program Files\MKVToolNix")
    assert captured["eac3to_dir"] == Path(r"C:\Program Files (x86)\eac3to_3.52")


def test_autodetects_missing_tool_dirs_once_and_saves(qtbot, tmp_path: Path) -> None:
    saved_settings: list[AppSettings] = []

    def detect_tool_dir(tool_name: str) -> Path | None:
        if tool_name == "mkvtoolnix":
            return Path(r"C:\Program Files\MKVToolNix")
        if tool_name == "eac3to":
            return Path(r"C:\Program Files (x86)\eac3to_3.52")
        return None

    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path, runtime_settings: [],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: saved_settings.append(
            AppSettings(
                mkvtoolnix_dir=settings.mkvtoolnix_dir,
                eac3to_dir=settings.eac3to_dir,
                output_dir=settings.output_dir,
                working_dir=settings.working_dir,
                eac3to_args=settings.eac3to_args,
                replace_selected_truehd=settings.replace_selected_truehd,
                cleanup_temp_files=settings.cleanup_temp_files,
            )
        ),
        detect_tool_dir=detect_tool_dir,
    )
    qtbot.addWidget(window)

    assert window.mkvtoolnix_edit.text() == r"C:\Program Files\MKVToolNix"
    assert window.eac3to_edit.text() == r"C:\Program Files (x86)\eac3to_3.52"
    assert len(saved_settings) == 1
    assert saved_settings[0].mkvtoolnix_dir == Path(r"C:\Program Files\MKVToolNix")
    assert saved_settings[0].eac3to_dir == Path(r"C:\Program Files (x86)\eac3to_3.52")


def test_shows_missing_tool_message_when_autodetect_fails(qtbot, tmp_path: Path) -> None:
    window = MainWindow(
        settings=AppSettings(output_dir=tmp_path, working_dir=tmp_path),
        scan_tracks=lambda path, runtime_settings: [],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
        detect_tool_dir=lambda tool_name: None,
    )
    qtbot.addWidget(window)

    assert window.mkvtoolnix_edit.text() == ""
    assert window.eac3to_edit.text() == ""
    assert window.mkvtoolnix_edit.placeholderText() == "未侦测到，请手动填入路径"
    assert window.eac3to_edit.placeholderText() == "未侦测到，请手动填入路径"


def test_does_not_autodetect_when_saved_tool_dirs_exist(qtbot, tmp_path: Path) -> None:
    detections: list[str] = []

    def detect_tool_dir(tool_name: str) -> Path | None:
        detections.append(tool_name)
        return Path(r"C:\override\should-not-be-used")

    window = MainWindow(
        settings=AppSettings(
            mkvtoolnix_dir=Path(r"D:\saved\MKVToolNix"),
            eac3to_dir=Path(r"D:\saved\eac3to"),
            output_dir=tmp_path,
            working_dir=tmp_path,
        ),
        scan_tracks=lambda path, runtime_settings: [],
        run_job=lambda **kwargs: None,
        cancel_job=lambda: None,
        save_settings=lambda settings: None,
        detect_tool_dir=detect_tool_dir,
    )
    qtbot.addWidget(window)

    assert window.mkvtoolnix_edit.text() == r"D:\saved\MKVToolNix"
    assert window.eac3to_edit.text() == r"D:\saved\eac3to"
    assert detections == []
