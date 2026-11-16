import random

from mod_manager.randomizer import member_mods, roll


def _rg(rg_id, name, members):
    return {rg_id: {"name": name, "members": members}}


def _mod(ref):
    return {"kind": "mod", "ref": ref}


def _grp(ref):
    return {"kind": "group", "ref": ref}


def test_member_mods_expands_groups():
    assert member_mods(_mod("a.vpk"), {}) == ["a.vpk"]
    assert member_mods(_grp("g1"), {"g1": ["a.vpk", "b.vpk"]}) == ["a.vpk", "b.vpk"]
    assert member_mods(_grp("missing"), {}) == []


def test_roll_picks_exactly_one_and_disables_rest():
    groups = _rg("r1", "Roll", [_mod("a.vpk"), _mod("b.vpk"), _mod("c.vpk")])
    result = roll(groups, {}, random.Random(42))
    enabled = [rel for rel, on in result.enable_map.items() if on]
    assert len(enabled) == 1
    assert result.enable_map == {rel: rel in enabled for rel in ("a.vpk", "b.vpk", "c.vpk")}
    pick = result.picks["r1"]
    assert pick.kind == "mod"
    assert pick.mods == (enabled[0],)


def test_roll_group_member_expansion():
    groups = _rg(
        "r1", "Roll", [_grp("g1"), _mod("x.vpk")]
    )
    membership = {"g1": ["a.vpk", "b.vpk"]}
    result = roll(groups, membership, random.Random(3))
    pick = result.picks["r1"]
    assert pick.kind == "group" and pick.ref == "g1"
    assert pick.mods == ("a.vpk", "b.vpk")
    assert result.enable_map == {
        "a.vpk": True,
        "b.vpk": True,
        "x.vpk": False,
    }


def test_roll_group_member_not_picked_disables_group_mods():
    groups = _rg(
        "r1", "Roll", [_grp("g1"), _mod("x.vpk")]
    )
    membership = {"g1": ["a.vpk", "b.vpk"]}
    result = roll(groups, membership, random.Random(0))
    pick = result.picks["r1"]
    assert pick.kind == "mod" and pick.ref == "x.vpk"
    assert result.enable_map == {
        "a.vpk": False,
        "b.vpk": False,
        "x.vpk": True,
    }


def test_roll_union_rule_for_mods_in_multiple_groups():
    groups = {
        "r1": {"name": "A", "members": [_mod("shared.vpk"), _mod("one.vpk")]},
        "r2": {"name": "B", "members": [_mod("shared.vpk"), _mod("two.vpk")]},
    }
    saw_enabled = False
    for seed in range(30):
        result = roll(groups, {}, random.Random(seed))
        one_picked = result.picks["r1"].ref == "one.vpk"
        two_picked = result.picks["r2"].ref == "two.vpk"
        shared_picked = not one_picked or not two_picked
        if shared_picked:
            assert result.enable_map["shared.vpk"] is True
            saw_enabled = True
        else:
            assert result.enable_map["shared.vpk"] is False
        assert result.enable_map["one.vpk"] == one_picked
        assert result.enable_map["two.vpk"] == two_picked
    assert saw_enabled


def test_roll_skips_empty_and_unresolvable_groups():
    groups = {
        "r1": {"name": "Empty", "members": []},
        "r2": {"name": "Gone", "members": [_mod("missing.vpk")]},
        "r3": {"name": "Real", "members": [_mod("a.vpk")]},
    }
    result = roll(groups, {}, random.Random(1), known_mods={"a.vpk"})
    assert set(result.picks) == {"r3"}
    assert result.enable_map == {"a.vpk": True}
    assert "missing.vpk" not in result.enable_map


def test_roll_deterministic_with_same_seed():
    groups = _rg(
        "r1", "Roll", [_mod(f"m{i}.vpk") for i in range(10)]
    )
    a = roll(groups, {}, random.Random(7))
    b = roll(groups, {}, random.Random(7))
    assert a == b
    c = roll(groups, {}, random.Random(8))
    assert c.picks["r1"].mods != a.picks["r1"].mods


def test_roll_untouched_mods_absent_from_map():
    groups = _rg("r1", "Roll", [_mod("a.vpk")])
    result = roll(groups, {}, random.Random(0))
    assert "outside.vpk" not in result.enable_map
