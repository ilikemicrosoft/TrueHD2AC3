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
    tokens = [
        token.replace("%_.ac3", str(output_file)).replace("%_", str(output_file.with_suffix("")))
        for token in argument_template.split()
    ]

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
