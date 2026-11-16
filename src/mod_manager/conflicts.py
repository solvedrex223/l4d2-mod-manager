from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

EXCLUDED_PATHS = frozenset({"addoninfo.txt", "addonimage.jpg", "addoninfo.txt.txt"})


@dataclass(frozen=True)
class Conflict:
    other: str
    shared: tuple[str, ...]
    active: bool
    winner: str | None


@dataclass(frozen=True)
class ModStats:
    contested: int
    lost: int


@dataclass(frozen=True)
class ConflictGroup:
    mods: tuple[str, ...]
    shared: tuple[str, ...]
    active: bool


class ConflictIndex:
    def __init__(self, metas: Iterable) -> None:
        path_owners: dict[str, list[str]] = {}
        for meta in metas:
            for path in meta.file_paths:
                key = path.lower()
                if key in EXCLUDED_PATHS:
                    continue
                owners = path_owners.setdefault(key, [])
                if meta.rel_path not in owners:
                    owners.append(meta.rel_path)

        pairs: dict[tuple[str, str], list[str]] = {}
        for path, owners in path_owners.items():
            if len(owners) < 2:
                continue
            for i in range(len(owners)):
                for j in range(i + 1, len(owners)):
                    a, b = owners[i], owners[j]
                    key = (a, b) if a < b else (b, a)
                    pairs.setdefault(key, []).append(path)

        self._pairs: dict[tuple[str, str], tuple[str, ...]] = {
            pair: tuple(paths) for pair, paths in pairs.items()
        }
        self._shared_owners: dict[str, tuple[str, ...]] = {
            path: tuple(owners) for path, owners in path_owners.items() if len(owners) > 1
        }
        self._adjacency: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
        for (a, b), shared in self._pairs.items():
            self._adjacency.setdefault(a, []).append((b, shared))
            self._adjacency.setdefault(b, []).append((a, shared))

        self._enabled: dict[str, bool] = {}
        self._order: dict[str, int] = {}

    def set_state(self, enabled_map: dict[str, bool], order: Iterable[str]) -> None:
        self._enabled = dict(enabled_map)
        order_list = list(order)
        self._order = {rel: i for i, rel in enumerate(order_list)}
        self._order_size = len(order_list)

    def enabled_map(self) -> dict[str, bool]:
        return dict(self._enabled)

    def order(self) -> list[str]:
        return sorted(self._order, key=self._order.get)

    def _rank(self, rel: str) -> int:
        return self._order.get(rel, self._order_size)

    def for_mod(self, rel: str) -> list[Conflict]:
        result: list[Conflict] = []
        for other, shared in self._adjacency.get(rel, []):
            active = bool(self._enabled.get(rel)) and bool(self._enabled.get(other))
            winner = rel if self._rank(rel) < self._rank(other) else other
            result.append(Conflict(other=other, shared=shared, active=active, winner=winner))
        result.sort(key=lambda c: (not c.active, -len(c.shared), c.other))
        return result

    def partners(self, rel: str) -> set[str]:
        return {other for other, _ in self._adjacency.get(rel, [])}

    def active_count(self, rel: str) -> int:
        return sum(1 for c in self.for_mod(rel) if c.active)

    def potential_count(self, rel: str) -> int:
        return sum(1 for c in self.for_mod(rel) if not c.active)

    def total_active_pairs(self) -> int:
        return sum(
            1
            for a, b in self._pairs
            if bool(self._enabled.get(a)) and bool(self._enabled.get(b))
        )

    def total_pairs(self) -> int:
        return len(self._pairs)

    def mod_stats(self, rel: str) -> ModStats:
        contested = 0
        lost = 0
        my_rank = self._rank(rel)
        my_enabled = bool(self._enabled.get(rel))
        for path, owners in self._shared_owners.items():
            if rel not in owners:
                continue
            contested += 1
            if not my_enabled:
                continue
            for other in owners:
                if other != rel and bool(self._enabled.get(other)) and self._rank(other) < my_rank:
                    lost += 1
                    break
        return ModStats(contested=contested, lost=lost)

    def groups(self, active_only: bool = True) -> list[ConflictGroup]:
        def eligible(rel: str) -> bool:
            return not active_only or bool(self._enabled.get(rel))

        seen: set[str] = set()
        found: list[ConflictGroup] = []
        for start in self._adjacency:
            if start in seen or not eligible(start):
                continue
            component: set[str] = set()
            stack = [start]
            while stack:
                node = stack.pop()
                if node in component:
                    continue
                component.add(node)
                for other, _shared in self._adjacency[node]:
                    if other not in component and eligible(other):
                        stack.append(other)
            seen |= component
            if active_only and len(component) < 2:
                continue
            shared = tuple(
                sorted(
                    path
                    for path, owners in self._shared_owners.items()
                    if next(iter(owners), None) in component
                )
            )
            active = any(
                bool(self._enabled.get(a)) and bool(self._enabled.get(b))
                for a, b in self._pairs
                if a in component and b in component
            )
            found.append(
                ConflictGroup(
                    mods=tuple(sorted(component, key=self._rank)),
                    shared=shared,
                    active=active,
                )
            )
        found.sort(
            key=lambda g: (
                not g.active,
                -len(g.shared),
                g.mods[0] if g.mods else "",
            )
        )
        return found
