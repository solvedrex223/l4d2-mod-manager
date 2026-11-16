from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

_GROUPS: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"campaign", "map"}), "Campaigns"),
    (frozenset({"skin"}), "Skins"),
    (frozenset({"weapon", "weaponmodel"}), "Weapons"),
    (frozenset({"bossinfected", "commoninfected"}), "Infected"),
    (frozenset({"survivor"}), "Survivors"),
    (frozenset({"sound", "music"}), "Sounds"),
    (frozenset({"script"}), "Scripts"),
    (frozenset({"prop"}), "Items"),
)

UNCATEGORIZED_TAG = "Uncategorized"
CUSTOM_TAG = "Custom"

TOP_LEVEL_TAGS = (
    "Sounds",
    "Weapons",
    "Models",
    "Textures",
    "Miscellaneous",
    "Survivors",
    "Scripts",
    "UI",
    "Special Infected",
    "Items",
    "Campaigns",
    "Common Infected",
    "Co-op",
    "Survival",
    "Versus",
    "Scavenge",
)

SUBTAG_PARENTS = {
    "Rifle": "Weapons",
    "SMG": "Weapons",
    "Shotgun": "Weapons",
    "Sniper": "Weapons",
    "Pistol": "Weapons",
    "Melee": "Weapons",
    "M60": "Weapons",
    "Grenade Launcher": "Weapons",
    "Throwable": "Weapons",
    "Bill": "Survivors",
    "Coach": "Survivors",
    "Ellis": "Survivors",
    "Francis": "Survivors",
    "Louis": "Survivors",
    "Nick": "Survivors",
    "Rochelle": "Survivors",
    "Zoey": "Survivors",
    "Boomer": "Special Infected",
    "Charger": "Special Infected",
    "Hunter": "Special Infected",
    "Jockey": "Special Infected",
    "Smoker": "Special Infected",
    "Spitter": "Special Infected",
    "Tank": "Special Infected",
    "Witch": "Special Infected",
    "Adrenaline": "Items",
    "Medkit": "Items",
    "Pills": "Items",
    "Realism": "Co-op",
    "Realism Versus": "Co-op",
    "Single Player": "Co-op",
    "Other": "Miscellaneous",
}

_TOP_SET = frozenset(TOP_LEVEL_TAGS)


def categories_for(flags: Iterable[str]) -> list[str]:
    flagset = {flag.lower() for flag in flags}
    return [label for keys, label in _GROUPS if flagset & keys]


def tag_counts(metas: Iterable) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for meta in metas:
        for tag in meta.workshop_tags:
            counts[tag] += 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def top_level_counts(metas: Iterable) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for meta in metas:
        for tag in meta.workshop_tags:
            if tag in _TOP_SET:
                counts[tag] += 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def uncategorized_count(metas: Iterable) -> int:
    return sum(1 for meta in metas if not meta.workshop_tags)


def custom_counts(
    assignments: dict[str, list[str]], registry: list[str]
) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for tags in assignments.values():
        for tag in tags:
            counts[tag] += 1
    return sorted(
        ((name, counts.get(name, 0)) for name in registry),
        key=lambda item: (-item[1], item[0]),
    )


def _resolve_parent(
    tag: str, metas: list, global_counts: Counter
) -> str | None:
    if tag in SUBTAG_PARENTS:
        return SUBTAG_PARENTS[tag]
    co: Counter[str] = Counter()
    for meta in metas:
        tags = meta.workshop_tags
        if tag not in tags:
            continue
        for other in tags:
            if other in _TOP_SET:
                co[other] += 1
    if not co:
        return None
    return sorted(
        co.items(),
        key=lambda kv: (-kv[1], -global_counts.get(kv[0], 0), kv[0]),
    )[0][0]


def subtag_counts(metas: Iterable, parent: str) -> list[tuple[str, int]]:
    metas = list(metas)
    if parent not in _TOP_SET:
        return []
    global_counts: Counter[str] = Counter()
    for meta in metas:
        for tag in meta.workshop_tags:
            global_counts[tag] += 1

    children = {
        tag
        for tag in global_counts
        if tag not in _TOP_SET and _resolve_parent(tag, metas, global_counts) == parent
    }

    co_counts: Counter[str] = Counter()
    for meta in metas:
        tags = meta.workshop_tags
        if parent not in tags:
            continue
        for tag in tags:
            if tag in children:
                co_counts[tag] += 1
    return sorted(co_counts.items(), key=lambda item: (-item[1], item[0]))
