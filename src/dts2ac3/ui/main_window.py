from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from dts2ac3.models import AppSettings, AudioTrack, WorkflowResult
from dts2ac3.tooling import is_truehd_track

DEFAULT_MKVTOOLNIX_DIR = Path(r"C:\Program Files\MKVToolNix")
DEFAULT_EAC3TO_DIR = Path(r"C:\Program Files (x86)\eac3to_3.52")


class JobThread(QThread):
    log_line = Signal(str)
    job_finished = Signal(object)

    def __init__(self, run_job, job_kwargs: dict) -> None:
        super().__init__()
        self._run_job = run_job
        self._job_kwargs = job_kwargs

    def run(self) -> None:
        result = self._run_job(**self._job_kwargs, on_log=self._emit_log)
        self.job_finished.emit(result)

    def _emit_log(self, line: str) -> None:
        self.log_line.emit(line)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        scan_tracks,
        run_job,
        cancel_job,
        save_settings,
        detect_tool_dir=None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._scan_tracks = scan_tracks
        self._run_job = run_job
        self._cancel_job = cancel_job
        self._save_settings = save_settings
        self._detect_tool_dir = detect_tool_dir or self._default_detect_tool_dir
        self._tracks: list[AudioTrack] = []
        self._job_thread: JobThread | None = None
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
        self.audio_track_list = QListWidget()
        self.audio_track_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self.keep_radio = QRadioButton("保留原 TrueHD")
        self.replace_radio = QRadioButton("替换选中的 TrueHD")
        self.cleanup_checkbox = QCheckBox("完成后删除临时文件")
        self.scan_button = QPushButton("扫描音轨")
        self.start_button = QPushButton("开始处理")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)

        form.addRow("MKVToolNix 目录", self._line_with_browse(self.mkvtoolnix_edit, self.pick_directory))
        form.addRow("eac3to 目录", self._line_with_browse(self.eac3to_edit, self.pick_directory))
        form.addRow("源文件", self._line_with_browse(self.source_file_edit, self.pick_file))
        form.addRow("导出目录", self._line_with_browse(self.output_dir_edit, self.pick_directory))
        form.addRow("工作目录", self._line_with_browse(self.working_dir_edit, self.pick_directory))
        form.addRow("输出文件名", self.output_name_edit)
        form.addRow("TrueHD 音轨", self.track_combo)
        form.addRow("eac3to 参数", self.eac3to_args_edit)

        radio_row = QHBoxLayout()
        radio_row.addWidget(self.keep_radio)
        radio_row.addWidget(self.replace_radio)

        button_row = QHBoxLayout()
        button_row.addWidget(self.scan_button)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        layout.addLayout(form)
        layout.addLayout(radio_row)
        layout.addWidget(self.cleanup_checkbox)
        layout.addLayout(button_row)
        layout.addWidget(QLabel("扫描到的全部音轨"))
        layout.addWidget(self.audio_track_list)
        layout.addWidget(QLabel("命令输出"))
        layout.addWidget(self.log_output)
        self.setCentralWidget(central)

        self.scan_button.clicked.connect(self.handle_scan_tracks)
        self.start_button.clicked.connect(self.handle_run_job)
        self.stop_button.clicked.connect(self.handle_cancel_job)
        self.source_file_edit.textChanged.connect(self.handle_source_file_changed)

    def _line_with_browse(self, line_edit: QLineEdit, picker) -> QWidget:
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(lambda: picker(line_edit))
        row.addWidget(line_edit)
        row.addWidget(browse_button)
        return container

    def _load_settings(self) -> None:
        autodetected = False
        mkvtoolnix_dir = self._settings.mkvtoolnix_dir
        eac3to_dir = self._settings.eac3to_dir

        if mkvtoolnix_dir is None:
            mkvtoolnix_dir = self._detect_tool_dir("mkvtoolnix")
            if mkvtoolnix_dir is not None:
                self._settings.mkvtoolnix_dir = mkvtoolnix_dir
                autodetected = True

        if eac3to_dir is None:
            eac3to_dir = self._detect_tool_dir("eac3to")
            if eac3to_dir is not None:
                self._settings.eac3to_dir = eac3to_dir
                autodetected = True

        if mkvtoolnix_dir:
            self.mkvtoolnix_edit.setText(str(mkvtoolnix_dir))
        else:
            self.mkvtoolnix_edit.setPlaceholderText("未侦测到，请手动填入路径")

        if eac3to_dir:
            self.eac3to_edit.setText(str(eac3to_dir))
        else:
            self.eac3to_edit.setPlaceholderText("未侦测到，请手动填入路径")

        if self._settings.output_dir:
            self.output_dir_edit.setText(str(self._settings.output_dir))
        if self._settings.working_dir:
            self.working_dir_edit.setText(str(self._settings.working_dir))
        self.eac3to_args_edit.setText(self._settings.eac3to_args)
        self.replace_radio.setChecked(self._settings.replace_selected_truehd)
        self.keep_radio.setChecked(not self._settings.replace_selected_truehd)
        self.cleanup_checkbox.setChecked(self._settings.cleanup_temp_files)

        if autodetected:
            self._save_settings(self._settings)

    def pick_directory(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择目录", target.text().strip())
        if selected:
            target.setText(selected)

    def pick_file(self, target: QLineEdit) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "选择片源文件", target.text().strip())
        if selected:
            target.setText(selected)

    def handle_source_file_changed(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        source_path = Path(cleaned)
        if not self.output_name_edit.text().strip():
            self.output_name_edit.setText(source_path.stem)

    def handle_scan_tracks(self) -> None:
        source_text = self.source_file_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "缺少源文件", "请先选择要扫描的片源文件。")
            return

        source_path = Path(source_text)
        self._sync_settings_from_form()
        self.track_combo.clear()
        self.audio_track_list.clear()
        self.append_log(f"Scanning: {source_path}")
        try:
            self._tracks = self._scan_tracks(source_path, self._settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "扫描失败", str(exc))
            return

        truehd_tracks: list[AudioTrack] = []
        for track in self._tracks:
            item = QListWidgetItem(self._format_track_label(track))
            if is_truehd_track(track):
                truehd_tracks.append(track)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.audio_track_list.addItem(item)

        if not truehd_tracks:
            self.append_log("No TrueHD tracks detected.")
            QMessageBox.information(self, "未找到 TrueHD", "没有检测到可转换的 TrueHD 音轨。")
            return

        for track in truehd_tracks:
            label = self._format_track_label(track)
            self.track_combo.addItem(label, track.track_id)

    def handle_run_job(self) -> None:
        source_text = self.source_file_edit.text().strip()
        output_name = self.output_name_edit.text().strip()
        if not source_text or not output_name:
            QMessageBox.warning(self, "缺少参数", "请先填写源文件和输出文件名。")
            return

        selected_track_id = self.track_combo.currentData()
        self._sync_settings_from_form()
        self._save_settings(self._settings)

        self._set_running_state(True)
        self.append_log("Starting job...")
        self._job_thread = JobThread(
            run_job=self._run_job,
            job_kwargs={
                "settings": self._settings,
                "source_file": Path(source_text),
                "output_file_name": output_name,
                "selected_track_id": selected_track_id,
            },
        )
        self._job_thread.log_line.connect(self.append_log)
        self._job_thread.job_finished.connect(self._handle_job_finished)
        self._job_thread.start()

    def handle_cancel_job(self) -> None:
        self.append_log("Cancellation requested.")
        self._cancel_job()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._sync_settings_from_form()
        self._save_settings(self._settings)
        super().closeEvent(event)

    def _handle_job_finished(self, result: WorkflowResult) -> None:
        self._set_running_state(False)
        self._job_thread = None
        if result.success:
            self.append_log(f"Done: {result.output_file}")
            QMessageBox.information(self, "处理完成", f"输出文件已生成：\n{result.output_file}")
        else:
            QMessageBox.critical(self, "处理失败", result.error_message or "Unknown error")

    def _set_running_state(self, running: bool) -> None:
        self.scan_button.setEnabled(not running)
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    @staticmethod
    def _as_path(widget: QLineEdit) -> Path | None:
        text = widget.text().strip()
        return Path(text) if text else None

    def _sync_settings_from_form(self) -> None:
        self._settings.mkvtoolnix_dir = self._as_path(self.mkvtoolnix_edit)
        self._settings.eac3to_dir = self._as_path(self.eac3to_edit)
        self._settings.output_dir = self._as_path(self.output_dir_edit)
        self._settings.working_dir = self._as_path(self.working_dir_edit)
        self._settings.eac3to_args = self.eac3to_args_edit.text().strip()
        self._settings.replace_selected_truehd = self.replace_radio.isChecked()
        self._settings.cleanup_temp_files = self.cleanup_checkbox.isChecked()

    @staticmethod
    def _default_existing_dir(candidate: Path) -> Path | None:
        return candidate if candidate.exists() else None

    @staticmethod
    def _default_detect_tool_dir(tool_name: str) -> Path | None:
        defaults = {
            "mkvtoolnix": DEFAULT_MKVTOOLNIX_DIR,
            "eac3to": DEFAULT_EAC3TO_DIR,
        }
        candidate = defaults.get(tool_name)
        if candidate is None:
            return None
        return candidate if candidate.exists() else None

    @staticmethod
    def _format_track_label(track: AudioTrack) -> str:
        channel_text = f"{track.channels}ch" if track.channels is not None else "unknown"
        return f"#{track.track_id} | {track.language} | {channel_text} | {track.codec} | {track.display_name}"

    def append_log(self, line: str) -> None:
        self.log_output.appendPlainText(line)
