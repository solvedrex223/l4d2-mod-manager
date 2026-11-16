from mod_manager.vpk_meta import parse_addoninfo, read_mod, scan_addons

from conftest import REAL_ADDONINFO


def _install(game_dir, vpk_file, workshop=False):
    addons = game_dir / "left4dead2" / "addons"
    target_dir = addons / "workshop" if workshop else addons
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / vpk_file.name
    target.write_bytes(vpk_file.read_bytes())
    return target


def test_parse_addoninfo_extracts_fields_and_flags():
    info = parse_addoninfo(REAL_ADDONINFO)
    assert info.title == "Team Health Counter"
    assert info.author == "Rayman1103"
    assert info.version == "4"
    assert info.tagline == "Adds a health counter for Survivor teammates."
    assert info.content_flags == {"script"}


def test_parse_addoninfo_without_root_block():
    info = parse_addoninfo('addontitle "Bare"\naddonContent_Skin 1\n')
    assert info.title == "Bare"
    assert info.content_flags == {"skin"}


def test_parse_addoninfo_addontittle_typo():
    info = parse_addoninfo(
        '"AddonInfo"\n{\n\taddontittle "U Got That"\n\taddonauthor "Shira"\n}\n'
    )
    assert info.title == "U Got That"
    assert info.author == "Shira"


def test_read_mod_full_metadata(game_dir, vpk_factory):
    vpk_file = vpk_factory(
        {"materials/models/w_eagle.vmt": b"x", "scripts/foo.txt": b"y"},
        addoninfo=REAL_ADDONINFO,
        name="121088866",
    )
    _install(game_dir, vpk_file, workshop=True)
    addons = game_dir / "left4dead2" / "addons"

    meta = read_mod("workshop/121088866.vpk", addons)

    assert meta.title == "Team Health Counter"
    assert meta.author == "Rayman1103"
    assert meta.source == "workshop"
    assert meta.content_flags == {"script"}
    assert set(meta.file_paths) == {
        "addoninfo.txt",
        "materials/models/w_eagle.vmt",
        "scripts/foo.txt",
    }
    assert meta.parse_error is None
    assert meta.thumbnail is None


def test_read_mod_uses_jpg_beside_workshop_vpk(game_dir, vpk_factory):
    vpk_file = vpk_factory({}, name="999")
    target = _install(game_dir, vpk_file, workshop=True)
    (target.with_suffix(".jpg")).write_bytes(b"\xff\xd8fakejpg")
    meta = read_mod("workshop/999.vpk", game_dir / "left4dead2" / "addons")
    assert meta.thumbnail == target.with_suffix(".jpg")


def test_read_mod_extracts_loose_thumbnail_to_cache(game_dir, vpk_factory, tmp_path):
    vpk_file = vpk_factory(
        {"addonimage.jpg": b"\xff\xd8fakejpg"}, addoninfo=REAL_ADDONINFO, name="cool"
    )
    _install(game_dir, vpk_file)
    cache = tmp_path / "thumbs"

    meta = read_mod("cool.vpk", game_dir / "left4dead2" / "addons", cache)

    assert meta.thumbnail is not None
    assert meta.thumbnail.read_bytes() == b"\xff\xd8fakejpg"
    assert meta.thumbnail.parent == cache


def test_read_mod_without_addoninfo_falls_back_to_stem(game_dir, vpk_factory):
    vpk_file = vpk_factory({"materials/a.vmt": b"x"}, name="12345")
    _install(game_dir, vpk_file, workshop=True)
    meta = read_mod("workshop/12345.vpk", game_dir / "left4dead2" / "addons")
    assert meta.title == "12345"
    assert meta.author is None
    assert meta.parse_error is None


def test_read_mod_double_extension_addoninfo(game_dir, vpk_factory):
    vpk_file = vpk_factory(
        {"materials/a.vmt": b"x", "addoninfo.txt.txt": REAL_ADDONINFO.encode()},
        name="dd",
    )
    _install(game_dir, vpk_file, workshop=True)
    meta = read_mod("workshop/dd.vpk", game_dir / "left4dead2" / "addons")
    assert meta.title == "Team Health Counter"
    assert meta.author == "Rayman1103"
    assert meta.content_flags == {"script"}
    assert meta.parse_error is None


def test_read_mod_addoninfo_case_insensitive(game_dir, vpk_factory):
    vpk_file = vpk_factory(
        {"materials/a.vmt": b"x", "AddonInfo.TXT": REAL_ADDONINFO.encode()},
        name="ci",
    )
    _install(game_dir, vpk_file, workshop=True)
    meta = read_mod("workshop/ci.vpk", game_dir / "left4dead2" / "addons")
    assert meta.title == "Team Health Counter"
    assert meta.author == "Rayman1103"


def test_read_mod_cp1252_addoninfo(game_dir, vpk_factory):
    vpk_file = vpk_factory(
        {}, addoninfo=b'"AddonInfo"\n{\n\taddontitle "caf\xe9"\n}\n', name="cp"
    )
    _install(game_dir, vpk_file, workshop=True)
    meta = read_mod("workshop/cp.vpk", game_dir / "left4dead2" / "addons")
    assert meta.title == "café"
    assert meta.parse_error is None


def test_read_mod_corrupt_vpk(game_dir):
    addons = game_dir / "left4dead2" / "addons" / "workshop"
    (addons / "broken.vpk").write_bytes(b"this is not a vpk at all")
    meta = read_mod("workshop/broken.vpk", game_dir / "left4dead2" / "addons")
    assert meta.title == "broken"
    assert meta.parse_error is not None
    assert meta.file_paths == ()


def test_read_mod_recovers_cp1252_file_paths(game_dir, tmp_path):
    import vpk

    src = tmp_path / "cp_src"
    (src / "materials").mkdir(parents=True)
    (src / "materials" / "caf\u00e9.vmt").write_bytes(b"x")
    out = tmp_path / "cp.vpk"
    vpk.new(str(src), path_enc="cp1252").save(str(out))
    target = _install(game_dir, out, workshop=True)

    meta = read_mod("workshop/cp.vpk", game_dir / "left4dead2" / "addons")

    assert meta.parse_error is None
    assert any("caf" in p for p in meta.file_paths)


def test_scan_addons_reports_progress_and_metas(game_dir, vpk_factory):
    addons = game_dir / "left4dead2" / "addons"
    for name in ("a", "b"):
        vpk_file = vpk_factory({}, addoninfo=REAL_ADDONINFO, name=name)
        (addons / vpk_file.name).write_bytes(vpk_file.read_bytes())

    calls = []
    metas = scan_addons(addons, progress=lambda i, n, rel: calls.append((i, n, rel)))

    assert [m.rel_path for m in metas] == ["a.vpk", "b.vpk"]
    assert calls == [(1, 2, "a.vpk"), (2, 2, "b.vpk")]
