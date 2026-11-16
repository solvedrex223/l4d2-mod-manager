import subprocess
import sys
import time
from pathlib import Path

import pytest

from mod_manager.game import (
    AddonList,
    addonlist_path,
    discover_mods,
    game_process_running,
    parse_addonlist,
    write_addonlist,
)

from conftest import REAL_ADDONLIST


def test_parse_real_addonlist():
    entries = parse_addonlist(REAL_ADDONLIST)
    assert list(entries) == ["workshop/1124884266.vpk", "workshop/121088866.vpk", "cool_skin.vpk"]
    assert entries["workshop/1124884266.vpk"] is False
    assert entries["workshop/121088866.vpk"] is True
    assert entries["cool_skin.vpk"] is True


def test_write_preserves_game_format():
    text = write_addonlist({"workshop/121088866.vpk": True, "a.vpk": False})
    assert '"AddonList"\n{\n\t"workshop\\121088866.vpk"\t\t"1"\n\t"a.vpk"\t\t"0"\n}\n' == text


def test_parse_write_round_trip():
    entries = parse_addonlist(REAL_ADDONLIST)
    assert parse_addonlist(write_addonlist(entries)) == entries


def test_load_missing_returns_empty(game_dir):
    assert AddonList.load(game_dir).entries == {}


def test_save_creates_backup(game_dir):
    path = addonlist_path(game_dir)
    path.write_text('"AddonList"\n{\n\t"a.vpk"\t\t"1"\n}\n', encoding="utf-8")

    addonlist = AddonList({"b.vpk": False})
    addonlist.save(game_dir)

    assert path.read_text(encoding="utf-8") == '"AddonList"\n{\n\t"b.vpk"\t\t"0"\n}\n'
    backup = path.with_name(path.name + ".bak")
    assert backup.read_text(encoding="utf-8") == '"AddonList"\n{\n\t"a.vpk"\t\t"1"\n}\n'


def test_reconcile_adds_and_removes():
    addonlist = AddonList({"keep.vpk": True, "stale.vpk": True})
    added, removed = addonlist.reconcile(["keep.vpk", "fresh.vpk"])
    assert added == ["fresh.vpk"]
    assert removed == ["stale.vpk"]
    assert addonlist.entries == {"keep.vpk": True, "fresh.vpk": True}


def test_reorder_moves_entries_and_keeps_flags():
    addonlist = AddonList({"a.vpk": True, "b.vpk": False, "c.vpk": True})
    addonlist.reorder(["c.vpk", "a.vpk"])
    assert list(addonlist.entries) == ["c.vpk", "a.vpk", "b.vpk"]
    assert addonlist.entries == {"c.vpk": True, "a.vpk": True, "b.vpk": False}


def test_reorder_ignores_unknown_rels():
    addonlist = AddonList({"a.vpk": True, "b.vpk": True})
    addonlist.reorder(["nope.vpk", "b.vpk"])
    assert list(addonlist.entries) == ["b.vpk", "a.vpk"]


def test_reorder_round_trips_through_file(game_dir):
    AddonList({"a.vpk": True, "b.vpk": False}).save(game_dir)
    addonlist = AddonList.load(game_dir)
    addonlist.reorder(["b.vpk", "a.vpk"])
    addonlist.save(game_dir)
    reloaded = AddonList.load(game_dir)
    assert list(reloaded.entries) == ["b.vpk", "a.vpk"]
    assert reloaded.entries == {"b.vpk": False, "a.vpk": True}


def test_game_process_running_false_for_unknown_dir(tmp_path):
    assert not game_process_running(tmp_path / "nope")
    assert not game_process_running("")


def test_game_process_running_detects_cmdline(tmp_path):
    if not Path("/proc").exists():
        pytest.skip("requires /proc (Linux)")
    game = tmp_path / "Left 4 Dead 2"
    game.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)", str(game)]
    )
    try:
        deadline = time.time() + 5
        while not game_process_running(game) and time.time() < deadline:
            time.sleep(0.05)
        assert game_process_running(game)
    finally:
        proc.terminate()
        proc.wait()
    deadline = time.time() + 2
    while game_process_running(game) and time.time() < deadline:
        time.sleep(0.05)
    assert not game_process_running(game)


def test_discover_mods(game_dir, vpk_factory):
    addons = game_dir / "left4dead2" / "addons"
    workshop = addons / "workshop"
    vpk_factory({}, name="z_skin")
    loose_vpk = vpk_factory({}, name="loose_mod")
    ws_vpk = vpk_factory({}, name="121088866")
    (addons / loose_vpk.name).write_bytes(loose_vpk.read_bytes())
    (workshop / ws_vpk.name).write_bytes(ws_vpk.read_bytes())

    assert discover_mods(addons) == ["loose_mod.vpk", "workshop/121088866.vpk"]
    assert discover_mods(addons / "nonexistent") == []
