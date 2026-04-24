from pathlib import Path

from truehd2ac3.models import AudioTrack
from truehd2ac3.tooling import (
    build_eac3to_convert_command,
    build_mkvextract_command,
    build_mkvmerge_command,
    build_probe_command,
    find_truehd_tracks,
    parse_mkvmerge_tracks,
    validate_tool_directories,
)


def test_validate_tool_directories_reports_missing_binaries(tmp_path: Path) -> None:
    result = validate_tool_directories(tmp_path, tmp_path)

    assert result.is_valid is False
    assert "mkvmerge.exe" in result.errors
    assert "eac3to.exe" in result.errors


def test_parse_mkvmerge_tracks_extracts_audio_track_fields() -> None:
    payload = {
        "tracks": [
            {
                "id": 0,
                "type": "video",
                "codec": "AVC/H.264/MPEG-4p10",
                "properties": {},
            },
            {
                "id": 1,
                "type": "audio",
                "codec": "TrueHD Atmos",
                "properties": {
                    "language": "jpn",
                    "audio_channels": 8,
                    "default_track": True,
                    "track_name": "Japanese Atmos",
                },
            },
            {
                "id": 2,
                "type": "audio",
                "codec": "DTS-HD Master Audio",
                "properties": {
                    "language": "eng",
                    "audio_channels": 6,
                    "default_track": False,
                },
            },
        ]
    }

    tracks = parse_mkvmerge_tracks(payload)

    assert [track.track_id for track in tracks] == [1, 2]
    assert tracks[0].codec == "TrueHD Atmos"
    assert tracks[0].language == "jpn"
    assert tracks[0].channels == 8
    assert tracks[0].is_default is True
    assert tracks[0].display_name == "Japanese Atmos"


def test_find_truehd_tracks_returns_all_truehd_candidates() -> None:
    payload = {
        "tracks": [
            {
                "id": 1,
                "type": "audio",
                "codec": "TrueHD Atmos",
                "properties": {"language": "jpn", "audio_channels": 8},
            },
            {
                "id": 2,
                "type": "audio",
                "codec": "TrueHD",
                "properties": {"language": "eng", "audio_channels": 8},
            },
            {
                "id": 3,
                "type": "audio",
                "codec": "AC-3",
                "properties": {"language": "eng", "audio_channels": 6},
            },
        ]
    }

    truehd_tracks = find_truehd_tracks(parse_mkvmerge_tracks(payload))

    assert [track.track_id for track in truehd_tracks] == [1, 2]


def test_build_probe_command_uses_mkvmerge_json_output() -> None:
    command = build_probe_command(
        Path(r"C:\Program Files\MKVToolNix"),
        Path(r"D:\media\movie.mkv"),
    )

    assert command == [
        str(Path(r"C:\Program Files\MKVToolNix") / "mkvmerge.exe"),
        "-J",
        str(Path(r"D:\media\movie.mkv")),
    ]


def test_build_mkvextract_command_extracts_selected_track() -> None:
    command = build_mkvextract_command(
        mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
        source_file=Path(r"D:\media\movie.mkv"),
        selected_track=AudioTrack(
            track_id=3,
            codec="TrueHD Atmos",
            language="jpn",
            channels=8,
            is_default=True,
            display_name="Japanese Atmos",
        ),
        working_dir=Path(r"D:\temp"),
    )

    assert command == [
        str(Path(r"C:\Program Files\MKVToolNix") / "mkvextract.exe"),
        str(Path(r"D:\media\movie.mkv")),
        "tracks",
        "3:" + str(Path(r"D:\temp") / "movie.track3.thd"),
    ]


def test_build_eac3to_convert_command_expands_percent_placeholder() -> None:
    command = build_eac3to_convert_command(
        eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
        source_file=Path(r"D:\temp\movie.track3.thd"),
        selected_track=AudioTrack(
            track_id=3,
            codec="TrueHD Atmos",
            language="jpn",
            channels=8,
            is_default=True,
            display_name="Japanese Atmos",
        ),
        working_dir=Path(r"D:\temp"),
        argument_template="%_.ac3 -640",
    )

    assert command == [
        str(Path(r"C:\Program Files (x86)\eac3to_3.52") / "eac3to.exe"),
        str(Path(r"D:\temp\movie.track3.thd")),
        str(Path(r"D:\temp") / "movie.track3.ac3"),
        "-640",
    ]


def test_build_eac3to_convert_command_preserves_spaces_in_output_path() -> None:
    command = build_eac3to_convert_command(
        eac3to_dir=Path(r"C:\Program Files (x86)\eac3to_3.52"),
        source_file=Path(r"D:\temp files\ac3 output\movie.track3.thd"),
        selected_track=AudioTrack(
            track_id=3,
            codec="TrueHD Atmos",
            language="jpn",
            channels=8,
            is_default=True,
            display_name="Japanese Atmos",
        ),
        working_dir=Path(r"D:\temp files\ac3 output"),
        argument_template="%_.ac3 -640",
    )

    assert command == [
        str(Path(r"C:\Program Files (x86)\eac3to_3.52") / "eac3to.exe"),
        str(Path(r"D:\temp files\ac3 output\movie.track3.thd")),
        str(Path(r"D:\temp files\ac3 output") / "movie.track3.ac3"),
        "-640",
    ]


def test_build_mkvmerge_replace_command_excludes_selected_track() -> None:
    track = AudioTrack(
        track_id=3,
        codec="TrueHD Atmos",
        language="jpn",
        channels=8,
        is_default=True,
        display_name="Japanese Atmos",
    )

    command = build_mkvmerge_command(
        mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
        source_file=Path(r"D:\media\movie.mkv"),
        output_file=Path(r"D:\exports\movie.ac3.mkv"),
        converted_audio_file=Path(r"D:\temp\movie.track3.ac3"),
        selected_track=track,
        replace_selected_truehd=True,
    )

    assert command == [
        str(Path(r"C:\Program Files\MKVToolNix") / "mkvmerge.exe"),
        "-o",
        str(Path(r"D:\exports\movie.ac3.mkv")),
        "--audio-tracks",
        "!3",
        str(Path(r"D:\media\movie.mkv")),
        "--language",
        "0:jpn",
        "--track-name",
        "0:Japanese Atmos (AC3 5.1)",
        str(Path(r"D:\temp\movie.track3.ac3")),
    ]


def test_build_mkvmerge_preserve_command_keeps_original_audio_tracks() -> None:
    track = AudioTrack(
        track_id=1,
        codec="TrueHD",
        language="eng",
        channels=8,
        is_default=True,
        display_name="English TrueHD",
    )

    command = build_mkvmerge_command(
        mkvtoolnix_dir=Path(r"C:\Program Files\MKVToolNix"),
        source_file=Path(r"D:\media\movie.mkv"),
        output_file=Path(r"D:\exports\movie.ac3.mkv"),
        converted_audio_file=Path(r"D:\temp\movie.track1.ac3"),
        selected_track=track,
        replace_selected_truehd=False,
    )

    assert "--audio-tracks" not in command
