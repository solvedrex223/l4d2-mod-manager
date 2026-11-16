from __future__ import annotations

import re
import shutil
from collections.abc import Iterable
from pathlib import Path

_ENTRY_RE = re.compile(r'"([^"]+)"\s+"([01])"')


def addonlist_path(game_dir: Path | str) -> Path:
    return Path(game_dir) / "left4dead2" / "addonlist.txt"


def addons_dir(game_dir: Path | str) -> Path:
    return Path(game_dir) / "left4dead2" / "addons"


def _game_rel(rel_path: str) -> str:
    return rel_path.replace("/", "\\")


def parse_addonlist(text: str) -> dict[str, bool]:
    entries: dict[str, bool] = {}
    for match in _ENTRY_RE.finditer(text):
        rel = match.group(1).replace("\\", "/")
        entries[rel] = match.group(2) == "1"
    return entries


def write_addonlist(entries: dict[str, bool]) -> str:
    lines = ['"AddonList"', "{"]
    for rel, enabled in entries.items():
        state = "1" if enabled else "0"
        lines.append(f'\t"{_game_rel(rel)}"\t\t"{state}"')
    lines.append("}")
    return "\n".join(lines) + "\n"


class AddonList:
    def __init__(self, entries: dict[str, bool] | None = None) -> None:
        self.entries: dict[str, bool] = dict(entries or {})

    @classmethod
    def load(cls, game_dir: Path | str) -> AddonList:
        p = addonlist_path(game_dir)
        if not p.exists():
            return cls()
        return cls(parse_addonlist(p.read_text(encoding="utf-8", errors="replace")))

    def save(self, game_dir: Path | str) -> None:
        p = addonlist_path(game_dir)
        if p.exists():
            backup = p.with_name(p.name + ".bak")
            shutil.copy2(p, backup)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(write_addonlist(self.entries), encoding="utf-8")

    def set(self, rel_path: str, enabled: bool) -> None:
        self.entries[rel_path] = enabled

    def reorder(self, order: Iterable[str]) -> None:
        known = [rel for rel in order if rel in self.entries]
        promoted = set(known)
        rest = [rel for rel in self.entries if rel not in promoted]
        self.entries = {rel: self.entries[rel] for rel in known + rest}

    def reconcile(self, existing: Iterable[str]) -> tuple[list[str], list[str]]:
        existing = list(existing)
        added = [rel for rel in existing if rel not in self.entries]
        for rel in added:
            self.entries[rel] = True
        removed = [rel for rel in self.entries if rel not in existing]
        for rel in removed:
            del self.entries[rel]
        return added, removed


def discover_mods(addons: Path | str) -> list[str]:
    addons = Path(addons)
    rels: list[str] = []
    if not addons.is_dir():
        return rels
    rels += sorted(p.name for p in addons.glob("*.vpk") if p.is_file())
    workshop = addons / "workshop"
    if workshop.is_dir():
        rels += sorted(f"workshop/{p.name}" for p in workshop.glob("*.vpk") if p.is_file())
    return rels


def game_process_running(game_dir: Path | str) -> bool:
    game_path = str(game_dir).encode()
    if not game_path:
        return False
    proc = Path("/proc")
    if not proc.is_dir():
        return False
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if not cmdline:
            continue
        for arg in cmdline.split(b"\0"):
            if game_path in arg:
                return True
    return False
