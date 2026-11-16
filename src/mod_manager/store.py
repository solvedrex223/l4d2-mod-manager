from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .config import config_dir

STORE_VERSION = 1


def store_path() -> Path:
    return config_dir() / "store.json"


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


class Store:
    def __init__(self, data: dict | None = None, path: Path | None = None) -> None:
        self.path = path if path is not None else store_path()
        data = data if data is not None else {}
        self.version: int = data.get("version", STORE_VERSION)
        self.mods: dict[str, dict] = data.get("mods", {})
        self.groups: dict[str, dict] = data.get("groups", {})
        self.workshop_meta: dict[str, dict] = data.get("workshop_meta", {})
        self.custom_categories: list[str] = data.get("custom_categories", [])
        self.random_groups: dict[str, dict] = data.get("random_groups", {})
        for group in self.groups.values():
            group.pop("randomizable", None)
            group.pop("probability", None)

    @classmethod
    def load(cls, path: Path | None = None) -> Store:
        p = path if path is not None else store_path()
        if not p.exists():
            return cls(path=p)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(path=p)
        if not isinstance(data, dict):
            return cls(path=p)
        return cls(data, path=p)

    def save(self, path: Path | None = None) -> None:
        p = path if path is not None else self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "mods": self.mods,
            "groups": self.groups,
            "workshop_meta": self.workshop_meta,
            "custom_categories": self.custom_categories,
            "random_groups": self.random_groups,
        }
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)

    def upsert_mod(self, rel_path: str, enabled: bool, tags: list[str] | None = None) -> None:
        existing = self.mods.get(rel_path, {})
        self.mods[rel_path] = {
            "enabled": enabled,
            "tags": tags if tags is not None else existing.get("tags", []),
            "groups": existing.get("groups", []),
        }

    def remove_mod(self, rel_path: str) -> None:
        self.mods.pop(rel_path, None)

    def set_enabled(self, rel_path: str, enabled: bool) -> None:
        if rel_path in self.mods:
            self.mods[rel_path]["enabled"] = enabled

    def enabled_map(self) -> dict[str, bool]:
        return {rel: entry["enabled"] for rel, entry in self.mods.items()}

    def add_custom_category(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.custom_categories:
            return False
        self.custom_categories.append(name)
        self.custom_categories.sort()
        return True

    def delete_custom_category(self, name: str) -> int:
        if name not in self.custom_categories:
            return 0
        self.custom_categories.remove(name)
        affected = 0
        for entry in self.mods.values():
            tags = entry.get("tags", [])
            if name in tags:
                tags = [tag for tag in tags if tag != name]
                entry["tags"] = tags
                affected += 1
        return affected

    def set_mod_tags(self, rel_path: str, tags: list[str]) -> None:
        if rel_path in self.mods:
            self.mods[rel_path]["tags"] = [tag for tag in tags if tag in self.custom_categories]

    def mod_tags(self, rel_path: str) -> list[str]:
        return list(self.mods.get(rel_path, {}).get("tags", []))

    def custom_assignments(self) -> dict[str, list[str]]:
        return {
            rel: list(entry.get("tags", []))
            for rel, entry in self.mods.items()
            if entry.get("tags")
        }

    def add_group(self, name: str) -> str | None:
        name = name.strip()
        if not name or any(g.get("name") == name for g in self.groups.values()):
            return None
        group_id = f"g{len(self.groups) + 1}"
        while group_id in self.groups:
            group_id = f"g{int(group_id[1:]) + 1}"
        self.groups[group_id] = {"name": name}
        return group_id

    def rename_group(self, group_id: str, name: str) -> bool:
        if group_id not in self.groups:
            return False
        name = name.strip()
        if not name or any(
            g.get("name") == name
            for gid, g in self.groups.items()
            if gid != group_id
        ):
            return False
        self.groups[group_id]["name"] = name
        return True

    def group_name(self, group_id: str) -> str | None:
        return self.groups.get(group_id, {}).get("name")

    def delete_group(self, group_id: str) -> int:
        if group_id not in self.groups:
            return 0
        del self.groups[group_id]
        affected = 0
        for entry in self.mods.values():
            groups = entry.get("groups", [])
            if group_id in groups:
                entry["groups"] = [g for g in groups if g != group_id]
                affected += 1
        return affected

    def set_mod_groups(self, rel_path: str, group_ids: list[str]) -> None:
        if rel_path in self.mods:
            self.mods[rel_path]["groups"] = [
                g for g in group_ids if g in self.groups
            ]

    def mod_groups(self, rel_path: str) -> list[str]:
        return list(self.mods.get(rel_path, {}).get("groups", []))

    def group_assignments(self) -> dict[str, list[str]]:
        return {
            rel: list(entry.get("groups", []))
            for rel, entry in self.mods.items()
            if entry.get("groups")
        }

    def group_members(self, group_id: str) -> list[str]:
        return [
            rel
            for rel, entry in self.mods.items()
            if group_id in entry.get("groups", [])
        ]

    def add_random_group(self, name: str) -> str | None:
        name = name.strip()
        if not name or any(
            rg.get("name") == name for rg in self.random_groups.values()
        ):
            return None
        rg_id = f"r{len(self.random_groups) + 1}"
        while rg_id in self.random_groups:
            rg_id = f"r{int(rg_id[1:]) + 1}"
        self.random_groups[rg_id] = {"name": name, "members": []}
        return rg_id

    def rename_random_group(self, rg_id: str, name: str) -> bool:
        if rg_id not in self.random_groups:
            return False
        name = name.strip()
        if not name or any(
            rg.get("name") == name
            for rid, rg in self.random_groups.items()
            if rid != rg_id
        ):
            return False
        self.random_groups[rg_id]["name"] = name
        return True

    def random_group_name(self, rg_id: str) -> str | None:
        return self.random_groups.get(rg_id, {}).get("name")

    def delete_random_group(self, rg_id: str) -> None:
        self.random_groups.pop(rg_id, None)

    def add_random_member(self, rg_id: str, kind: str, ref: str) -> bool:
        rg = self.random_groups.get(rg_id)
        if rg is None or kind not in ("mod", "group"):
            return False
        if any(
            m.get("kind") == kind and m.get("ref") == ref
            for m in rg.get("members", [])
        ):
            return False
        rg["members"].append({"kind": kind, "ref": ref})
        return True

    def remove_random_member(self, rg_id: str, kind: str, ref: str) -> bool:
        rg = self.random_groups.get(rg_id)
        if rg is None:
            return False
        before = len(rg.get("members", []))
        rg["members"] = [
            m
            for m in rg.get("members", [])
            if not (m.get("kind") == kind and m.get("ref") == ref)
        ]
        return len(rg["members"]) != before

    def mod_random_groups(self, rel_path: str) -> list[str]:
        return [
            rg_id
            for rg_id, rg in self.random_groups.items()
            if any(
                m.get("kind") == "mod" and m.get("ref") == rel_path
                for m in rg.get("members", [])
            )
        ]

    def sync_with_scan(self, metas: Iterable, enabled_map: dict[str, bool]) -> SyncReport:
        report = SyncReport()
        scanned = {m.rel_path for m in metas}
        known = set(self.mods)
        for rel in sorted(scanned - known):
            report.added.append(rel)
            self.mods[rel] = {
                "enabled": enabled_map.get(rel, True),
                "tags": [],
                "groups": [],
            }
        for rel in sorted(known - scanned):
            report.removed.append(rel)
            del self.mods[rel]
        return report
