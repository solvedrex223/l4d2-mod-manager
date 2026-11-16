from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace

import requests

from .vpk_meta import ModMeta

API_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
CHUNK_SIZE = 100
TIMEOUT = 10


@dataclass(frozen=True)
class WorkshopDetails:
    file_id: str
    title: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()


def details_to_dict(details: WorkshopDetails) -> dict:
    return {
        "title": details.title,
        "description": details.description,
        "tags": list(details.tags),
    }


def dict_to_details(file_id: str, data: dict) -> WorkshopDetails:
    return WorkshopDetails(
        file_id=file_id,
        title=data.get("title"),
        description=data.get("description"),
        tags=tuple(data.get("tags", ())),
    )


def _parse_response(payload: dict) -> dict[str, WorkshopDetails]:
    details: dict[str, WorkshopDetails] = {}
    for item in payload.get("response", {}).get("publishedfiledetails", []):
        file_id = str(item.get("publishedfileid", ""))
        if not file_id or item.get("result") != 1:
            continue
        title = (item.get("title") or "").strip() or None
        description = (item.get("description") or "").strip() or None
        tags = tuple(
            tag.get("tag", "")
            for tag in item.get("tags", [])
            if tag.get("tag")
        )
        details[file_id] = WorkshopDetails(
            file_id=file_id, title=title, description=description, tags=tags
        )
    return details


def fetch_details(file_ids: list[str], timeout: int = TIMEOUT) -> dict[str, WorkshopDetails]:
    details: dict[str, WorkshopDetails] = {}
    for start in range(0, len(file_ids), CHUNK_SIZE):
        chunk = file_ids[start : start + CHUNK_SIZE]
        data = {"itemcount": len(chunk)}
        for i, file_id in enumerate(chunk):
            data[f"publishedfileids[{i}]"] = file_id
        try:
            response = requests.post(API_URL, data=data, timeout=timeout)
            response.raise_for_status()
            details.update(_parse_response(response.json()))
        except Exception:
            continue
    return details


Fetcher = Callable[[list[str]], dict[str, WorkshopDetails]]


@dataclass(frozen=True)
class MergeResult:
    metas: list = field(default_factory=list)
    new_cache: dict[str, WorkshopDetails] = field(default_factory=dict)
    fetched: int = 0
    fetch_failed: bool = False


def _workshop_id(meta: ModMeta) -> str | None:
    if meta.source != "workshop":
        return None
    stem = meta.filename.rsplit(".", 1)[0]
    return stem if stem.isdigit() else None


def merge_details(
    metas: Iterable,
    cache: dict[str, WorkshopDetails],
    fetcher: Fetcher | None = fetch_details,
) -> MergeResult:
    metas = list(metas)
    cached = dict(cache)

    missing = []
    for meta in metas:
        file_id = _workshop_id(meta)
        if file_id and file_id not in cached and file_id not in missing:
            missing.append(file_id)

    new_cache: dict[str, WorkshopDetails] = {}
    if missing and fetcher is not None:
        try:
            new_cache = fetcher(missing)
        except Exception:
            new_cache = {}
        if not isinstance(new_cache, dict):
            new_cache = {}
        cached.update(new_cache)

    fetch_failed = bool(missing) and not new_cache

    merged: list[ModMeta] = []
    for meta in metas:
        file_id = _workshop_id(meta)
        info = cached.get(file_id) if file_id else None
        if info is None:
            merged.append(meta)
            continue
        if meta.title_source == "filename" and info.title:
            merged.append(
                replace(
                    meta,
                    title=info.title,
                    title_source="workshop",
                    description=meta.description or info.description,
                    workshop_tags=info.tags,
                )
            )
        else:
            merged.append(
                replace(
                    meta,
                    description=meta.description or info.description,
                    workshop_tags=info.tags,
                )
            )
    return MergeResult(
        metas=merged, new_cache=new_cache, fetched=len(new_cache), fetch_failed=fetch_failed
    )
