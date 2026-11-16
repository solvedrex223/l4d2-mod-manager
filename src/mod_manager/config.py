from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import platformdirs

from .keyvalues import parse

APP_NAME = "l4d2-mod-manager"
GAME_DIR_NAME = "Left 4 Dead 2"


def config_dir() -> Path:
    return Path(platformdirs.user_config_dir(APP_NAME))


def cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir(APP_NAME))


def settings_path() -> Path:
    return config_dir() / "settings.json"


@dataclass
class Settings:
    game_dir: str | None = None


def load_settings(path: Path | None = None) -> Settings:
    p = path or settings_path()
    if not p.exists():
        return Settings()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Settings()
    game_dir = data.get("game_dir")
    return Settings(game_dir=game_dir if isinstance(game_dir, str) else None)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def normalize_game_dir(path: Path) -> Path:
    if path.name.lower() == "left4dead2":
        return path.parent
    return path


def validate_game_dir(path: Path | str | None) -> bool:
    if not path:
        return False
    p = normalize_game_dir(Path(path))
    return (p / "left4dead2" / "addons").is_dir()


def default_steam_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".steam/steam",
        home / ".steam/root",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    ]
    return [c for c in candidates if (c / "steamapps").is_dir()]


def find_libraries(root: Path) -> list[Path]:
    libraries = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if not vdf.exists():
        return libraries
    try:
        kv = parse(vdf.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return libraries
    folders = kv.get("libraryfolders")
    if not isinstance(folders, dict):
        return libraries
    for entry in folders.values():
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            libraries.append(Path(entry["path"]))
        elif isinstance(entry, str) and entry:
            libraries.append(Path(entry))
    return libraries


def autodetect_game_dir(steam_roots: list[Path] | None = None) -> Path | None:
    for root in steam_roots if steam_roots is not None else default_steam_roots():
        for library in find_libraries(root):
            game = library / "steamapps" / "common" / GAME_DIR_NAME
            if validate_game_dir(game):
                return game
    return None
