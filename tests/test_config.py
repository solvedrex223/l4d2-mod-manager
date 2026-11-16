from pathlib import Path

from mod_manager.config import (
    Settings,
    autodetect_game_dir,
    load_settings,
    normalize_game_dir,
    save_settings,
    validate_game_dir,
)


def test_validate_and_normalize(game_dir, tmp_path):
    assert validate_game_dir(game_dir)
    assert validate_game_dir(game_dir / "left4dead2")
    assert normalize_game_dir(game_dir / "left4dead2") == game_dir
    assert not validate_game_dir(tmp_path)
    assert not validate_game_dir(None)
    assert not validate_game_dir("/nonexistent/path")


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(game_dir="/some/dir"), path)
    loaded = load_settings(path)
    assert loaded.game_dir == "/some/dir"
    assert load_settings(tmp_path / "missing.json").game_dir is None


def test_corrupt_settings_falls_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_settings(path).game_dir is None


def test_autodetect_via_libraryfolders(tmp_path, game_dir, monkeypatch):
    steam_root = tmp_path / "steam"
    library = tmp_path / "other_library"
    common = library / "steamapps" / "common" / "Left 4 Dead 2" / "left4dead2" / "addons"
    common.mkdir(parents=True)
    (steam_root / "steamapps").mkdir(parents=True)
    (steam_root / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' % library,
        encoding="utf-8",
    )
    monkeypatch.setattr("mod_manager.config.default_steam_roots", lambda: [steam_root])
    assert autodetect_game_dir() == library / "steamapps" / "common" / "Left 4 Dead 2"


def test_autodetect_finds_game_in_root_library(tmp_path, monkeypatch):
    steam_root = tmp_path / "steam"
    addons = steam_root / "steamapps" / "common" / "Left 4 Dead 2" / "left4dead2" / "addons"
    addons.mkdir(parents=True)
    monkeypatch.setattr("mod_manager.config.default_steam_roots", lambda: [steam_root])
    assert autodetect_game_dir() == steam_root / "steamapps" / "common" / "Left 4 Dead 2"


def test_autodetect_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("mod_manager.config.default_steam_roots", lambda: [])
    assert autodetect_game_dir() is None
