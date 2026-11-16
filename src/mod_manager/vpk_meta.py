from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path

import vpk as vpk_lib

from .game import discover_mods
from .keyvalues import parse

CONTENT_PREFIXES = ("addoncontent_", "content_")
_flag_re = re.compile(r"^[a-z]+$")

_ADDONINFO_CANDIDATES = ("addoninfo.txt", "addoninfo.txt.txt")


def find_addoninfo(file_paths: tuple[str, ...]) -> str | None:
    by_lower = {p.lower(): p for p in file_paths}
    for candidate in _ADDONINFO_CANDIDATES:
        actual = by_lower.get(candidate)
        if actual is not None:
            return actual
    return None


@dataclass(frozen=True)
class AddonInfo:
    title: str | None = None
    author: str | None = None
    version: str | None = None
    tagline: str | None = None
    description: str | None = None
    url: str | None = None
    content_flags: frozenset[str] = frozenset()


def _str(node: dict, key: str) -> str | None:
    value = node.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def parse_addoninfo(text: str) -> AddonInfo:
    kv = parse(text)
    node = kv.get("addoninfo")
    if not isinstance(node, dict):
        node = kv
    flags: set[str] = set()
    for key, value in node.items():
        if value != "1" or not isinstance(value, str):
            continue
        for prefix in CONTENT_PREFIXES:
            if key.startswith(prefix) and len(key) > len(prefix):
                flag = key[len(prefix) :]
                if _flag_re.match(flag):
                    flags.add(flag)
                break
    return AddonInfo(
        title=_str(node, "addontitle") or _str(node, "addontittle"),
        author=_str(node, "addonauthor"),
        version=_str(node, "addonversion"),
        tagline=_str(node, "addontagline"),
        description=_str(node, "addondescription"),
        url=_str(node, "addonurl0"),
        content_flags=frozenset(flags),
    )


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class ModMeta:
    rel_path: str
    abs_path: Path
    source: str
    size: int
    title: str
    title_source: str = "filename"
    author: str | None = None
    version: str | None = None
    tagline: str | None = None
    description: str | None = None
    content_flags: frozenset[str] = frozenset()
    workshop_tags: tuple[str, ...] = ()
    file_paths: tuple[str, ...] = ()
    thumbnail: Path | None = None
    parse_error: str | None = None

    @property
    def filename(self) -> str:
        return Path(self.rel_path).name


def _extract_thumbnail(archive: vpk_lib.VPK, rel_path: str, cache: Path) -> Path | None:
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / (sha1(rel_path.encode()).hexdigest()[:16] + ".jpg")
    if not out.exists():
        try:
            data = archive.get_file("addonimage.jpg").read()
        except Exception:
            return None
        out.write_bytes(data)
    return out


def read_mod(
    rel_path: str, addons: Path | str, thumb_cache: Path | str | None = None
) -> ModMeta:
    addons = Path(addons)
    abs_path = addons / rel_path
    source = "workshop" if rel_path.startswith("workshop/") else "loose"
    try:
        size = abs_path.stat().st_size
    except OSError:
        size = 0
    title = Path(rel_path).stem
    thumbnail: Path | None = None
    file_paths: tuple[str, ...] = ()
    info = AddonInfo()
    parse_error: str | None = None

    if source == "workshop":
        jpg = abs_path.with_suffix(".jpg")
        if jpg.is_file():
            thumbnail = jpg

    try:
        try:
            archive = vpk_lib.open(str(abs_path), read_header_only=False)
        except UnicodeDecodeError:
            archive = vpk_lib.open(str(abs_path), read_header_only=False, path_enc="cp1252")
        file_paths = tuple(str(p) for p in archive)
        raw = None
        info_path = find_addoninfo(file_paths)
        if info_path is not None:
            try:
                raw = archive.get_file(info_path).read()
            except KeyError:
                raw = None
        if raw is not None:
            info = parse_addoninfo(_decode(raw))
        if thumbnail is None and thumb_cache is not None and "addonimage.jpg" in file_paths:
            thumbnail = _extract_thumbnail(archive, rel_path, Path(thumb_cache))
    except Exception as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    if info.title:
        title = info.title
        title_source = "addoninfo"
    else:
        title_source = "filename"

    return ModMeta(
        rel_path=rel_path,
        abs_path=abs_path,
        source=source,
        size=size,
        title=title,
        title_source=title_source,
        author=info.author,
        version=info.version,
        tagline=info.tagline,
        description=info.description,
        content_flags=info.content_flags,
        file_paths=file_paths,
        thumbnail=thumbnail,
        parse_error=parse_error,
    )


ProgressCallback = Callable[[int, int, str], None]


def scan_addons(
    addons: Path | str, thumb_cache: Path | str | None = None, progress: ProgressCallback | None = None
) -> list[ModMeta]:
    rels = discover_mods(addons)
    metas: list[ModMeta] = []
    for i, rel in enumerate(rels, 1):
        metas.append(read_mod(rel, addons, thumb_cache))
        if progress is not None:
            progress(i, len(rels), rel)
    return metas
