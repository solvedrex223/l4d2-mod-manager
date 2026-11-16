import json
from types import SimpleNamespace

from mod_manager.store import Store


def _meta(rel):
    return SimpleNamespace(rel_path=rel)


def test_sync_adds_new_mods_with_enabled_from_map(tmp_path):
    store = Store(path=tmp_path / "store.json")
    report = store.sync_with_scan([_meta("a.vpk"), _meta("workshop/b.vpk")], {"a.vpk": False})
    assert report.added == ["a.vpk", "workshop/b.vpk"]
    assert store.mods["a.vpk"]["enabled"] is False
    assert store.mods["workshop/b.vpk"]["enabled"] is True


def test_sync_removes_stale_and_keeps_user_data(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("keep.vpk", True, tags=["Skins"])
    store.upsert_mod("gone.vpk", False)

    report = store.sync_with_scan([_meta("keep.vpk")], {})

    assert report.removed == ["gone.vpk"]
    assert "gone.vpk" not in store.mods
    assert store.mods["keep.vpk"]["tags"] == ["Skins"]


def test_round_trip(tmp_path):
    path = tmp_path / "store.json"
    store = Store(path=path)
    store.upsert_mod("a.vpk", True, tags=["Skins", "Music"])
    store.groups["g1"] = {"name": "Tank skins", "randomizable": True, "probability": 0.5}
    store.save()

    loaded = Store.load(path)
    assert loaded.mods == {"a.vpk": {"enabled": True, "tags": ["Skins", "Music"], "groups": []}}
    assert loaded.groups["g1"]["name"] == "Tank skins"
    assert loaded.enabled_map() == {"a.vpk": True}


def test_load_missing_or_corrupt(tmp_path):
    assert Store.load(tmp_path / "missing.json").mods == {}
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{oops", encoding="utf-8")
    assert Store.load(corrupt).mods == {}


def test_set_enabled(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    store.set_enabled("a.vpk", False)
    store.set_enabled("unknown.vpk", False)
    assert store.enabled_map() == {"a.vpk": False}


def test_workshop_meta_round_trip(tmp_path):
    path = tmp_path / "store.json"
    store = Store(path=path)
    store.workshop_meta["100"] = {"title": "T", "description": None, "tags": ["Sounds"]}
    store.save()
    loaded = Store.load(path)
    assert loaded.workshop_meta == {
        "100": {"title": "T", "description": None, "tags": ["Sounds"]}
    }


def test_custom_categories_round_trip(tmp_path):
    path = tmp_path / "store.json"
    store = Store(path=path)
    store.upsert_mod("a.vpk", True)
    store.add_custom_category("Kits")
    store.add_custom_category("Silenced")
    store.set_mod_tags("a.vpk", ["Kits", "Silenced"])
    store.save()

    loaded = Store.load(path)
    assert loaded.custom_categories == ["Kits", "Silenced"]
    assert loaded.mod_tags("a.vpk") == ["Kits", "Silenced"]


def test_add_custom_category_validation(tmp_path):
    store = Store(path=tmp_path / "store.json")
    assert store.add_custom_category("  Kits  ")
    assert store.custom_categories == ["Kits"]
    assert not store.add_custom_category("Kits")
    assert not store.add_custom_category("   ")
    assert not store.add_custom_category("")


def test_delete_custom_category_cascades(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    store.upsert_mod("b.vpk", True)
    store.add_custom_category("Kits")
    store.add_custom_category("Other")
    store.set_mod_tags("a.vpk", ["Kits", "Other"])
    store.set_mod_tags("b.vpk", ["Kits"])

    affected = store.delete_custom_category("Kits")

    assert affected == 2
    assert store.custom_categories == ["Other"]
    assert store.mod_tags("a.vpk") == ["Other"]
    assert store.mod_tags("b.vpk") == []


def test_set_mod_tags_drops_unknown_categories(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    store.add_custom_category("Kits")
    store.set_mod_tags("a.vpk", ["Kits", "NotRegistered"])
    assert store.mod_tags("a.vpk") == ["Kits"]
    store.set_mod_tags("missing.vpk", ["Kits"])
    assert store.mod_tags("missing.vpk") == []


def test_custom_assignments_skips_empty(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    store.upsert_mod("b.vpk", True)
    store.add_custom_category("Kits")
    store.set_mod_tags("a.vpk", ["Kits"])
    assert store.custom_assignments() == {"a.vpk": ["Kits"]}


def test_groups_round_trip(tmp_path):
    path = tmp_path / "store.json"
    store = Store(path=path)
    store.upsert_mod("a.vpk", True)
    gid = store.add_group("Tank skins")
    assert gid is not None
    store.set_mod_groups("a.vpk", [gid])
    store.save()

    loaded = Store.load(path)
    assert loaded.groups[gid] == {"name": "Tank skins"}
    assert loaded.mod_groups("a.vpk") == [gid]


def test_obsolete_group_fields_stripped_on_load(tmp_path):
    path = tmp_path / "store.json"
    payload = {
        "version": 1,
        "mods": {},
        "groups": {"g1": {"name": "Old", "randomizable": True, "probability": 0.3}},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = Store.load(path)
    assert loaded.groups["g1"] == {"name": "Old"}


def test_add_group_validation(tmp_path):
    store = Store(path=tmp_path / "store.json")
    assert store.add_group("  Kits  ") == "g1"
    assert store.add_group("Kits") is None
    assert store.add_group("   ") is None
    assert store.add_group("") is None


def test_rename_group_preserves_membership(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    gid = store.add_group("Tank skins")
    other = store.add_group("Music")
    store.set_mod_groups("a.vpk", [gid, other])

    assert store.rename_group(gid, "Tank picks")
    assert store.group_name(gid) == "Tank picks"
    assert store.mod_groups("a.vpk") == [gid, other]
    assert not store.rename_group(gid, "Music")
    assert not store.rename_group(gid, "  ")


def test_delete_group_cascades(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    store.upsert_mod("b.vpk", True)
    gid = store.add_group("Tank skins")
    other = store.add_group("Music")
    store.set_mod_groups("a.vpk", [gid, other])
    store.set_mod_groups("b.vpk", [gid])

    affected = store.delete_group(gid)

    assert affected == 2
    assert set(store.groups) == {other}
    assert store.mod_groups("a.vpk") == [other]
    assert store.mod_groups("b.vpk") == []


def test_set_mod_groups_strips_unknown(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    gid = store.add_group("Kits")
    store.set_mod_groups("a.vpk", [gid, "ghost"])
    assert store.mod_groups("a.vpk") == [gid]
    store.set_mod_groups("missing.vpk", [gid])
    assert store.mod_groups("missing.vpk") == []


def test_group_members_and_assignments(tmp_path):
    store = Store(path=tmp_path / "store.json")
    store.upsert_mod("a.vpk", True)
    store.upsert_mod("b.vpk", True)
    store.upsert_mod("c.vpk", True)
    gid = store.add_group("Kits")
    store.set_mod_groups("a.vpk", [gid])
    store.set_mod_groups("b.vpk", [gid])
    assert store.group_members(gid) == ["a.vpk", "b.vpk"]
    assert store.group_assignments() == {"a.vpk": [gid], "b.vpk": [gid]}


def test_random_groups_round_trip(tmp_path):
    path = tmp_path / "store.json"
    store = Store(path=path)
    store.upsert_mod("a.vpk", True)
    gid = store.add_group("Skins")
    rid = store.add_random_group("Tank music")
    assert rid is not None
    assert store.add_random_member(rid, "mod", "a.vpk")
    assert store.add_random_member(rid, "group", gid)
    store.save()

    loaded = Store.load(path)
    rg = loaded.random_groups[rid]
    assert rg["name"] == "Tank music"
    assert rg["members"] == [
        {"kind": "mod", "ref": "a.vpk"},
        {"kind": "group", "ref": gid},
    ]


def test_add_random_group_validation(tmp_path):
    store = Store(path=tmp_path / "store.json")
    assert store.add_random_group(" Tank music ") == "r1"
    assert store.add_random_group("Tank music") is None
    assert store.add_random_group("  ") is None


def test_random_member_add_remove(tmp_path):
    store = Store(path=tmp_path / "store.json")
    rid = store.add_random_group("Roll")
    assert store.add_random_member(rid, "mod", "a.vpk")
    assert not store.add_random_member(rid, "mod", "a.vpk")  # duplicate
    assert not store.add_random_member(rid, "weapon", "a.vpk")  # bad kind
    assert not store.add_random_member("ghost", "mod", "a.vpk")
    assert store.remove_random_member(rid, "mod", "a.vpk")
    assert not store.remove_random_member(rid, "mod", "a.vpk")
    assert store.random_groups[rid]["members"] == []


def test_rename_and_delete_random_group(tmp_path):
    store = Store(path=tmp_path / "store.json")
    rid = store.add_random_group("Roll")
    other = store.add_random_group("Other")
    assert store.rename_random_group(rid, "Dice")
    assert store.random_group_name(rid) == "Dice"
    assert not store.rename_random_group(rid, "Other")
    assert not store.rename_random_group("ghost", "X")
    store.delete_random_group(other)
    assert set(store.random_groups) == {rid}
    store.delete_random_group(rid)
    assert store.random_groups == {}


def test_mod_random_groups(tmp_path):
    store = Store(path=tmp_path / "store.json")
    r1 = store.add_random_group("A")
    r2 = store.add_random_group("B")
    store.add_random_member(r1, "mod", "a.vpk")
    store.add_random_member(r2, "mod", "b.vpk")
    assert store.mod_random_groups("a.vpk") == [r1]
    assert store.mod_random_groups("b.vpk") == [r2]
    assert store.mod_random_groups("c.vpk") == []
