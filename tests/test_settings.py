from pathlib import Path

from truehd2ac3.settings import AppSettingsStore


def test_load_returns_defaults_when_settings_file_is_missing(tmp_path: Path) -> None:
    store = AppSettingsStore(tmp_path / "settings.json")

    settings = store.load()

    assert settings.mkvtoolnix_dir is None
    assert settings.eac3to_dir is None
    assert settings.output_dir is None
    assert settings.working_dir is None
    assert settings.eac3to_args == "%_.ac3 -640"
    assert settings.replace_selected_truehd is False
    assert settings.cleanup_temp_files is True


def test_save_round_trips_settings_values(tmp_path: Path) -> None:
    store = AppSettingsStore(tmp_path / "settings.json")
    settings = store.load()
    settings.mkvtoolnix_dir = Path(r"C:\Program Files\MKVToolNix")
    settings.eac3to_dir = Path(r"C:\Program Files (x86)\eac3to_3.52")
    settings.output_dir = Path(r"D:\exports")
    settings.working_dir = Path(r"D:\temp\truehd2ac3")
    settings.eac3to_args = "%_.ac3 -640"
    settings.replace_selected_truehd = True
    settings.cleanup_temp_files = False

    store.save(settings)

    loaded = store.load()
    assert loaded.mkvtoolnix_dir == Path(r"C:\Program Files\MKVToolNix")
    assert loaded.eac3to_dir == Path(r"C:\Program Files (x86)\eac3to_3.52")
    assert loaded.output_dir == Path(r"D:\exports")
    assert loaded.working_dir == Path(r"D:\temp\truehd2ac3")
    assert loaded.eac3to_args == "%_.ac3 -640"
    assert loaded.replace_selected_truehd is True
    assert loaded.cleanup_temp_files is False
