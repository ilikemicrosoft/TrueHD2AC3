from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dts2ac3.models import AppSettings, AudioTrack, WorkflowResult
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
        converted_audio_resolver: Callable[[Path, AudioTrack, Path], Path] | None = None,
    ) -> None:
        self._runner = runner
        self._converted_audio_resolver = (
            converted_audio_resolver or self._default_converted_audio_path
        )
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        if hasattr(self._runner, "cancel"):
            self._runner.cancel()

    def scan_truehd_tracks(
        self,
        source_file: Path,
        settings: AppSettings,
        on_log=lambda line: None,
    ) -> list[AudioTrack]:
        probe_result = self._runner.run(
            build_probe_command(settings.mkvtoolnix_dir, source_file),
            on_log,
        )
        if probe_result.cancelled:
            raise RuntimeError("Job canceled.")
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
        self._cancel_requested = False
        validation = validate_tools(settings.mkvtoolnix_dir, settings.eac3to_dir)
        if not validation.is_valid:
            return WorkflowResult(False, error_message=", ".join(validation.errors))

        if not settings.output_dir or not settings.working_dir:
            return WorkflowResult(False, error_message="Output and working directories are required.")

        settings.output_dir.mkdir(parents=True, exist_ok=True)
        settings.working_dir.mkdir(parents=True, exist_ok=True)

        try:
            truehd_tracks = self.scan_truehd_tracks(source_file, settings, on_log)
        except RuntimeError as exc:
            return WorkflowResult(False, error_message=str(exc))

        if selected_track_id is None:
            return WorkflowResult(
                False,
                error_message="Select exactly one TrueHD track before running.",
            )

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
    def _default_converted_audio_path(
        source_file: Path,
        selected_track: AudioTrack,
        working_dir: Path,
    ) -> Path:
        return working_dir / f"{source_file.stem}.track{selected_track.track_id}.ac3"
