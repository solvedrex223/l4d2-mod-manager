from types import SimpleNamespace

from mod_manager.conflicts import ConflictIndex, ModStats


def _meta(rel, *paths):
    return SimpleNamespace(rel_path=rel, file_paths=list(paths))


def _index(*metas, enabled=None, order=None):
    idx = ConflictIndex(metas)
    idx.set_state(enabled or {}, order or [m.rel_path for m in metas])
    return idx


def test_detects_shared_paths_between_mods():
    idx = _index(
        _meta("a.vpk", "materials/skin.vmt", "models/mdl.mdl"),
        _meta("b.vpk", "materials/skin.vmt", "sound/x.wav"),
    )
    conflicts = idx.for_mod("a.vpk")
    assert len(conflicts) == 1
    assert conflicts[0].other == "b.vpk"
    assert conflicts[0].shared == ("materials/skin.vmt",)


def test_metadata_files_are_excluded():
    idx = _index(
        _meta("a.vpk", "addoninfo.txt", "addonimage.jpg"),
        _meta("b.vpk", "addoninfo.txt", "AddonImage.JPG"),
    )
    assert idx.total_pairs() == 0


def test_path_matching_is_case_insensitive():
    idx = _index(
        _meta("a.vpk", "Materials/Skin.VMT"),
        _meta("b.vpk", "materials/skin.vmt"),
    )
    assert idx.total_pairs() == 1


def test_active_vs_potential_and_winner_by_order():
    idx = _index(
        _meta("a.vpk", "materials/skin.vmt"),
        _meta("b.vpk", "materials/skin.vmt"),
        _meta("c.vpk", "materials/skin.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "c.vpk": False},
        order=["c.vpk", "a.vpk", "b.vpk"],
    )
    for_mod = idx.for_mod("a.vpk")
    by_other = {c.other: c for c in for_mod}
    assert by_other["b.vpk"].active is True
    assert by_other["b.vpk"].winner == "a.vpk"
    assert by_other["c.vpk"].active is False
    assert by_other["c.vpk"].winner == "c.vpk"
    assert idx.active_count("a.vpk") == 1
    assert idx.potential_count("a.vpk") == 1
    assert idx.total_active_pairs() == 1


def test_mod_missing_from_order_ranks_last():
    idx = _index(
        _meta("a.vpk", "materials/x.vmt"),
        _meta("b.vpk", "materials/x.vmt"),
        enabled={"a.vpk": True, "b.vpk": True},
        order=["b.vpk"],
    )
    assert idx.for_mod("a.vpk")[0].winner == "b.vpk"


def test_disabled_mod_has_no_active_conflicts():
    idx = _index(
        _meta("a.vpk", "materials/x.vmt"),
        _meta("b.vpk", "materials/x.vmt"),
        enabled={"a.vpk": False, "b.vpk": True},
    )
    conflicts = idx.for_mod("a.vpk")
    assert conflicts[0].active is False
    assert idx.total_active_pairs() == 0


def test_partners_and_shared_severity():
    idx = _index(
        _meta("a.vpk", "x.vmt", "y.vmt", "z.vmt"),
        _meta("b.vpk", "x.vmt", "y.vmt"),
        _meta("c.vpk", "x.vmt"),
    )
    assert idx.partners("a.vpk") == {"b.vpk", "c.vpk"}
    assert idx.partners("c.vpk") == {"a.vpk", "b.vpk"}
    by_other = {c.other: c for c in idx.for_mod("a.vpk")}
    assert len(by_other["b.vpk"].shared) == 2
    assert len(by_other["c.vpk"].shared) == 1
    assert idx.total_pairs() == 3


def test_state_change_updates_activity():
    idx = _index(
        _meta("a.vpk", "materials/x.vmt"),
        _meta("b.vpk", "materials/x.vmt"),
        enabled={"a.vpk": False, "b.vpk": True},
    )
    assert idx.total_active_pairs() == 0
    idx.set_state({"a.vpk": True, "b.vpk": True}, ["a.vpk", "b.vpk"])
    assert idx.total_active_pairs() == 1


def test_groups_components_ordered_by_priority():
    idx = _index(
        _meta("c.vpk", "x.vmt"),
        _meta("a.vpk", "x.vmt", "y.vmt"),
        _meta("b.vpk", "y.vmt"),
        _meta("d.vpk", "z.vmt"),
        _meta("e.vpk", "z.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "c.vpk": True, "d.vpk": True, "e.vpk": True},
        order=["c.vpk", "a.vpk", "b.vpk", "d.vpk", "e.vpk"],
    )
    groups = idx.groups()
    assert len(groups) == 2
    assert list(groups[0].mods) == ["c.vpk", "a.vpk", "b.vpk"]
    assert sorted(groups[0].shared) == ["x.vmt", "y.vmt"]
    assert groups[0].active is True
    assert set(groups[1].mods) == {"d.vpk", "e.vpk"}
    assert groups[1].shared == ("z.vmt",)
    assert groups[1].active is True


def test_groups_exclude_disabled_mods():
    idx = _index(
        _meta("a.vpk", "x.vmt"),
        _meta("b.vpk", "x.vmt"),
        _meta("off.vpk", "x.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "off.vpk": False},
        order=["off.vpk", "a.vpk", "b.vpk"],
    )
    groups = idx.groups()
    assert len(groups) == 1
    assert set(groups[0].mods) == {"a.vpk", "b.vpk"}


def test_groups_skip_lonely_enabled_mods():
    idx = _index(
        _meta("a.vpk", "x.vmt"),
        _meta("off.vpk", "x.vmt"),
        enabled={"a.vpk": True, "off.vpk": False},
        order=["a.vpk", "off.vpk"],
    )
    assert idx.groups() == []


def test_groups_do_not_merge_through_disabled_mods():
    idx = _index(
        _meta("a.vpk", "x.vmt"),
        _meta("mid.vpk", "x.vmt", "y.vmt"),
        _meta("b.vpk", "y.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "mid.vpk": False},
        order=["a.vpk", "mid.vpk", "b.vpk"],
    )
    assert idx.groups() == []


def test_groups_full_graph_when_not_active_only():
    idx = _index(
        _meta("a.vpk", "x.vmt"),
        _meta("mid.vpk", "x.vmt", "y.vmt"),
        _meta("b.vpk", "y.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "mid.vpk": False},
        order=["a.vpk", "mid.vpk", "b.vpk"],
    )
    groups = idx.groups(active_only=False)
    assert len(groups) == 1
    assert set(groups[0].mods) == {"a.vpk", "mid.vpk", "b.vpk"}
    assert groups[0].active is False


def test_groups_sort_active_first_in_full_graph():
    idx = _index(
        _meta("a.vpk", "x.vmt"),
        _meta("b.vpk", "x.vmt"),
        _meta("c.vpk", "p1.vmt", "p2.vmt", "p3.vmt"),
        _meta("d.vpk", "p1.vmt", "p2.vmt", "p3.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "c.vpk": False, "d.vpk": False},
        order=["a.vpk", "b.vpk", "c.vpk", "d.vpk"],
    )
    groups = idx.groups(active_only=False)
    assert groups[0].active is True
    assert set(groups[0].mods) == {"a.vpk", "b.vpk"}
    assert groups[1].active is False
    assert len(groups[1].shared) == 3


def test_mod_stats_contested_and_lost():
    idx = _index(
        _meta("a.vpk", "x.vmt", "y.vmt", "own.vmt"),
        _meta("b.vpk", "x.vmt", "y.vmt"),
        _meta("c.vpk", "x.vmt"),
        enabled={"a.vpk": True, "b.vpk": True, "c.vpk": True},
        order=["a.vpk", "b.vpk", "c.vpk"],
    )
    assert idx.mod_stats("a.vpk") == ModStats(contested=2, lost=0)
    assert idx.mod_stats("b.vpk") == ModStats(contested=2, lost=2)
    assert idx.mod_stats("c.vpk") == ModStats(contested=1, lost=1)
    idx.set_state({"a.vpk": True, "b.vpk": True, "c.vpk": False}, ["a.vpk", "b.vpk", "c.vpk"])
    assert idx.mod_stats("c.vpk") == ModStats(contested=1, lost=0)


def test_enabled_map_and_order_getters():
    idx = _index(
        _meta("a.vpk", "x.vmt"),
        _meta("b.vpk", "x.vmt"),
        enabled={"a.vpk": True, "b.vpk": False},
        order=["b.vpk", "a.vpk"],
    )
    assert idx.enabled_map() == {"a.vpk": True, "b.vpk": False}
    assert idx.order() == ["b.vpk", "a.vpk"]
