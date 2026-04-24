import os
from pathlib import Path

from truehd2ac3.main import resolve_settings_path


def test_resolve_settings_path_prefers_new_app_name(tmp_path: Path) -> None:
    os.environ["APPDATA"] = str(tmp_path)

    settings_path = resolve_settings_path()

    assert settings_path == tmp_path / "TrueHD2AC3" / "settings.json"


def test_resolve_settings_path_migrates_old_app_name_when_present(tmp_path: Path) -> None:
    os.environ["APPDATA"] = str(tmp_path)
    old_dir = tmp_path / "DTS2AC3"
    old_dir.mkdir()
    (old_dir / "settings.json").write_text("{}", encoding="utf-8")

    settings_path = resolve_settings_path()

    assert settings_path == tmp_path / "TrueHD2AC3" / "settings.json"
    assert settings_path.exists()
