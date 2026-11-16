from pathlib import Path

from mod_manager.categories import (
    categories_for,
    custom_counts,
    subtag_counts,
    tag_counts,
    top_level_counts,
    uncategorized_count,
)
from mod_manager.vpk_meta import ModMeta


def _meta(rel, tags=()):
    return ModMeta(
        rel_path=rel,
        abs_path=Path("/tmp") / rel,
        source="workshop",
        size=1,
        title=rel,
        workshop_tags=tuple(tags),
    )


def test_single_flags_map_to_categories():
    assert categories_for({"skin"}) == ["Skins"]
    assert categories_for({"campaign"}) == ["Campaigns"]
    assert categories_for({"map"}) == ["Campaigns"]
    assert categories_for({"music"}) == ["Sounds"]
    assert categories_for({"sound"}) == ["Sounds"]
    assert categories_for({"prop"}) == ["Items"]
    assert categories_for({"survivor"}) == ["Survivors"]
    assert categories_for({"script"}) == ["Scripts"]


def test_infected_flags_merge():
    assert categories_for({"bossinfected"}) == ["Infected"]
    assert categories_for({"commoninfected"}) == ["Infected"]
    assert categories_for({"bossinfected", "commoninfected"}) == ["Infected"]


def test_weaponmodel_counts_as_weapons():
    assert categories_for({"weaponmodel"}) == ["Weapons"]
    assert categories_for({"weapon"}) == ["Weapons"]


def test_multiple_categories_ordered():
    result = categories_for({"music", "skin", "bossinfected"})
    assert result == ["Skins", "Infected", "Sounds"]


def test_case_insensitive_and_empty():
    assert categories_for({"Skin"}) == ["Skins"]
    assert categories_for(set()) == []
    assert categories_for({"unknownflag"}) == []


def test_tag_counts_sorted_by_count_then_name():
    metas = [
        _meta("a", ("Sounds", "Tank")),
        _meta("b", ("Sounds", "Weapons")),
        _meta("c", ("Weapons",)),
        _meta("d", ()),
    ]
    assert tag_counts(metas) == [("Sounds", 2), ("Weapons", 2), ("Tank", 1)]


def test_uncategorized_count():
    metas = [_meta("a", ("Sounds",)), _meta("b"), _meta("c")]
    assert uncategorized_count(metas) == 2


def test_custom_counts_sorted_and_includes_empty():
    assignments = {"a": ["Kits", "Fun"], "b": ["Kits"], "c": []}
    registry = ["Zeta", "Kits", "Fun"]
    assert custom_counts(assignments, registry) == [
        ("Kits", 2),
        ("Fun", 1),
        ("Zeta", 0),
    ]


def test_top_level_counts_only_curated_tags_sorted():
    metas = [
        _meta("a", ("Sounds", "Tank")),
        _meta("b", ("Sounds", "Weapons")),
        _meta("c", ("Weapons",)),
        _meta("d", ("Rifle",)),
    ]
    assert top_level_counts(metas) == [("Sounds", 2), ("Weapons", 2)]


def test_subtag_counts_curated_parent_beats_co_occurrence():
    metas = [
        _meta("m1", ("Sounds", "Tank")),
        _meta("m2", ("Sounds", "Tank")),
        _meta("m3", ("Special Infected", "Tank")),
    ]
    infected = subtag_counts(metas, "Special Infected")
    assert ("Tank", 1) in infected
    assert ("Tank", 0) not in subtag_counts(metas, "Sounds")


def test_subtag_counts_intersection_counts():
    metas = [
        _meta("w1", ("Weapons", "SMG")),
        _meta("w2", ("Weapons", "SMG")),
        _meta("w3", ("Weapons",)),
        _meta("w4", ("Weapons",)),
        _meta("w5", ("Weapons",)),
        _meta("w6", ("Weapons",)),
        _meta("s1", ("Sounds", "SMG")),
    ]
    assert subtag_counts(metas, "Weapons") == [("SMG", 2)]


def test_subtag_counts_unknown_tag_falls_back_to_dominant_top_level():
    metas = [
        _meta("a", ("Weapons", "Halo")),
        _meta("b", ("Weapons", "Halo")),
        _meta("c", ("Sounds", "Halo")),
    ]
    assert subtag_counts(metas, "Weapons") == [("Halo", 2)]
    assert subtag_counts(metas, "Sounds") == []


def test_subtag_counts_parentless_tag_excluded():
    metas = [
        _meta("a", ("Solo",)),
        _meta("b", ("Sounds",)),
    ]
    assert subtag_counts(metas, "Sounds") == []
    assert subtag_counts(metas, "Weapons") == []


def test_subtag_counts_top_level_never_a_child():
    metas = [
        _meta("a", ("Weapons", "Sounds")),
        _meta("b", ("Weapons", "Models")),
    ]
    assert subtag_counts(metas, "Weapons") == []


def test_subtag_counts_unknown_parent_returns_empty():
    assert subtag_counts([_meta("a", ("Sounds",))], "Weapons") == []
    assert subtag_counts([_meta("a", ("Sounds",))], "NotACategory") == []
