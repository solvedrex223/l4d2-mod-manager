from pathlib import Path

from mod_manager.vpk_meta import ModMeta
from mod_manager.workshop_meta import (
    WorkshopDetails,
    _parse_response,
    details_to_dict,
    dict_to_details,
    merge_details,
)


def _meta(
    rel="workshop/100.vpk",
    title="100",
    title_source="filename",
    description=None,
    source="workshop",
):
    return ModMeta(
        rel_path=rel,
        abs_path=Path("/tmp") / rel,
        source=source,
        size=10,
        title=title,
        title_source=title_source,
        description=description,
    )


def test_parse_response_extracts_fields_and_skips_errors():
    payload = {
        "response": {
            "publishedfiledetails": [
                {
                    "publishedfileid": "100",
                    "result": 1,
                    "title": "  John Cena  ",
                    "description": "desc",
                    "tags": [{"tag": "Charger"}, {"tag": "Sounds"}, {"tag": ""}],
                },
                {"publishedfileid": "101", "result": 9, "title": "error item"},
                {"publishedfileid": "102", "result": 1, "title": ""},
            ]
        }
    }
    details = _parse_response(payload)
    assert set(details) == {"100", "102"}
    assert details["100"].title == "John Cena"
    assert details["100"].description == "desc"
    assert details["100"].tags == ("Charger", "Sounds")
    assert details["102"].title is None


def test_details_dict_round_trip():
    original = WorkshopDetails("100", title="T", description="D", tags=("A", "B"))
    assert dict_to_details("100", details_to_dict(original)) == original


def test_merge_cache_hit_skips_fetch():
    meta = _meta()
    cache = {"100": WorkshopDetails("100", title="Cached Title", description="cdesc")}
    calls = []
    result = merge_details([meta], cache, fetcher=lambda ids: calls.append(ids) or {})
    assert calls == []
    m = result.metas[0]
    assert m.title == "Cached Title"
    assert m.title_source == "workshop"
    assert m.description == "cdesc"
    assert result.fetched == 0
    assert not result.fetch_failed


def test_merge_fetches_only_uncached_ids():
    meta_new = _meta(rel="workshop/200.vpk", title="200")
    meta_cached = _meta(rel="workshop/100.vpk", title="100")
    cache = {"100": WorkshopDetails("100", title="Cached")}
    fetched = {"200": WorkshopDetails("200", title="Fetched Title", tags=("Sounds",))}
    calls = []

    def fetcher(ids):
        calls.append(ids)
        return fetched

    result = merge_details([meta_new, meta_cached], cache, fetcher=fetcher)
    assert calls == [["200"]]
    assert result.fetched == 1
    by_rel = {m.rel_path: m for m in result.metas}
    assert by_rel["workshop/200.vpk"].title == "Fetched Title"
    assert by_rel["workshop/200.vpk"].title_source == "workshop"
    assert by_rel["workshop/100.vpk"].title == "Cached"
    assert "200" in result.new_cache


def test_merge_local_addoninfo_title_wins():
    meta = _meta(title="Local Title", title_source="addoninfo", description=None)
    cache = {
        "100": WorkshopDetails(
            "100", title="Steam Title", description="Steam desc", tags=("Sounds",)
        )
    }
    result = merge_details([meta], cache, fetcher=None)
    m = result.metas[0]
    assert m.title == "Local Title"
    assert m.title_source == "addoninfo"
    assert m.description == "Steam desc"
    assert m.workshop_tags == ("Sounds",)


def test_merge_fetch_failure_keeps_filename_title():
    meta = _meta()
    result = merge_details([meta], {}, fetcher=lambda ids: {})
    m = result.metas[0]
    assert m.title == "100"
    assert m.title_source == "filename"
    assert result.fetch_failed
    assert result.new_cache == {}


def test_merge_fetcher_exception_is_contained():
    def boom(ids):
        raise RuntimeError("network down")

    meta = _meta()
    result = merge_details([meta], {}, fetcher=boom)
    assert result.metas[0].title == "100"
    assert result.fetch_failed


def test_merge_ignores_loose_mods():
    meta = _meta(rel="skin.vpk", title="skin", source="loose")
    calls = []
    result = merge_details([meta], {}, fetcher=lambda ids: calls.append(ids) or {})
    assert calls == []
    assert result.metas[0].title == "skin"
    assert not result.fetch_failed


def test_merge_preserves_order_and_multiple_mods():
    metas = [
        _meta(rel="workshop/300.vpk", title="300"),
        _meta(rel="a.vpk", title="A Mod", title_source="addoninfo", source="loose"),
        _meta(rel="workshop/100.vpk", title="100"),
    ]
    cache = {"100": WorkshopDetails("100", title="One Hundred")}
    fetched = {"300": WorkshopDetails("300", title="Three Hundred")}
    result = merge_details(metas, cache, fetcher=lambda ids: fetched)
    assert [m.rel_path for m in result.metas] == [
        "workshop/300.vpk",
        "a.vpk",
        "workshop/100.vpk",
    ]
    assert result.metas[0].title == "Three Hundred"
    assert result.metas[1].title == "A Mod"
    assert result.metas[2].title == "One Hundred"
