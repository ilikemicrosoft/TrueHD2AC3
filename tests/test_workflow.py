from pathlib import Path

from dts2ac3.models import AppSettings, CommandResult, ToolValidationResult
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


class CancelAwareRunner:
    def __init__(self):
        self.cancel_requested = False

    def run(self, command, on_output):
        on_output("line 1")
        if self.cancel_requested:
            return CommandResult(
                return_code=130,
                stdout_lines=["line 1"],
                stderr_lines=["cancelled"],
                cancelled=True,
            )
        on_output("line 2")
        return CommandResult(return_code=0, stdout_lines=["line 1", "line 2"], stderr_lines=[])

    def cancel(self):
        self.cancel_requested = True


def test_workflow_runs_probe_convert_merge_and_cleanup(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            CommandResult(
                return_code=0,
                stdout_lines=[
                    '{"tracks":[{"id":1,"type":"audio","codec":"TrueHD","properties":{"language":"eng","audio_channels":8}}]}'
                ],
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


def test_workflow_requires_explicit_truehd_selection_when_multiple_candidates_exist(
    tmp_path: Path,
) -> None:
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


def test_cancel_marks_result_as_cancelled(tmp_path: Path):
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


def test_scan_truehd_tracks_returns_truehd_candidates_only(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            CommandResult(
                return_code=0,
                stdout_lines=[
                    '{"tracks":['
                    '{"id":1,"type":"audio","codec":"TrueHD","properties":{"language":"jpn","audio_channels":8,"track_name":"Japanese"}},'
                    '{"id":2,"type":"audio","codec":"AC-3","properties":{"language":"eng","audio_channels":6,"track_name":"English AC3"}}'
                    ']}'
                ],
                stderr_lines=[],
            )
        ]
    )
    coordinator = WorkflowCoordinator(runner=runner)
    settings = AppSettings(
        mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
        eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
        output_dir=tmp_path,
        working_dir=tmp_path,
    )

    tracks = coordinator.scan_truehd_tracks(tmp_path / "movie.mkv", settings)

    assert [track.track_id for track in tracks] == [1]


def test_cleanup_failure_is_logged_but_not_fatal(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            CommandResult(
                return_code=0,
                stdout_lines=[
                    '{"tracks":[{"id":1,"type":"audio","codec":"TrueHD","properties":{"language":"eng","audio_channels":8}}]}'
                ],
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
