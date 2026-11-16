from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RollPick:
    kind: str
    ref: str
    mods: tuple[str, ...]


@dataclass(frozen=True)
class RollResult:
    enable_map: dict[str, bool]
    picks: dict[str, RollPick]


def member_mods(
    member: dict,
    group_membership: Mapping[str, list[str]],
    known_mods: set[str] | None = None,
) -> list[str]:
    if member.get("kind") == "group":
        return list(group_membership.get(member.get("ref"), []))
    ref = member.get("ref")
    if not ref:
        return []
    if known_mods is not None and ref not in known_mods:
        return []
    return [ref]


def roll(
    random_groups: dict,
    group_membership: Mapping[str, list[str]],
    rng: random.Random,
    known_mods: set[str] | None = None,
) -> RollResult:
    picks: dict[str, RollPick] = {}
    chosen: set[str] = set()
    all_member_mods: set[str] = set()

    for rg_id in sorted(random_groups):
        resolved = []
        for member in random_groups[rg_id].get("members", []):
            mods = member_mods(member, group_membership, known_mods)
            if mods:
                resolved.append((member, mods))
        if not resolved:
            continue
        member, mods = resolved[rng.randrange(len(resolved))]
        picks[rg_id] = RollPick(
            kind=member.get("kind", "mod"),
            ref=member.get("ref", ""),
            mods=tuple(mods),
        )
        for _member, member_mod_list in resolved:
            all_member_mods.update(member_mod_list)
        chosen.update(mods)

    enable_map = {rel: rel in chosen for rel in all_member_mods}
    return RollResult(enable_map=enable_map, picks=picks)
