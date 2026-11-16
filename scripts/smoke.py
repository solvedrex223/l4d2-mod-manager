import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from mod_manager.game import AddonList, write_addonlist
from mod_manager.store import Store
from mod_manager.ui.conflicts_tab import ConflictsTab
from mod_manager.ui.main_window import MainWindow
from mod_manager.ui.mods_model import ActiveConflictsRole
from mod_manager.workshop_meta import WorkshopDetails, merge_details
from mod_manager.vpk_meta import scan_addons
import vpk

app = QApplication([])


def row_for_tag(list_widget, value):
    role = 0x0100 + 1
    for r in range(list_widget.count()):
        if list_widget.item(r).data(role) == value:
            return r
    return -1


# ---------- Part 1: fake game tree ----------
root = Path("/tmp/opencode/m1")
if root.exists():
    shutil.rmtree(root)
game = root / "Left 4 Dead 2"
addons = game / "left4dead2" / "addons"
ws = addons / "workshop"
ws.mkdir(parents=True)


def make_vpk(out: Path, files: dict[str, bytes]):
    src = out.with_suffix(".src")
    for rel, data in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    vpk.new(str(src)).save(str(out))
    return out


make_vpk(addons / "a.vpk", {"scripts/a.txt": b"x", "addoninfo.txt": b'"AddonInfo"\n{\n\taddontitle "Mod A"\n}\n'})
make_vpk(ws / "w1.vpk", {"materials/x.vmt": b"1", "addoninfo.txt": b'"AddonInfo"\n{\n\taddontitle "Mod W1"\n\taddonContent_Skin 1\n}\n'})
make_vpk(ws / "999.vpk", {"materials/x.vmt": b"2", "materials/y.vmt": b"2"})

(game / "left4dead2" / "addonlist.txt").write_text(
    write_addonlist({"workshop/w1.vpk": True, "a.vpk": True, "workshop/999.vpk": True}),
    encoding="utf-8",
)
store_path = root / "store.json"
store = Store(path=store_path)
metas = scan_addons(addons)
addonlist = AddonList.load(game)
store.sync_with_scan(metas, addonlist.entries)
store.save()

fake_cache = {"999": WorkshopDetails("999", title="Steam 999 Title", tags=("Sounds",))}
merged = merge_details(metas, fake_cache, fetcher=None)
by_rel = {m.rel_path: m for m in merged.metas}
assert by_rel["workshop/999.vpk"].title == "Steam 999 Title"
assert by_rel["workshop/999.vpk"].title_source == "workshop"
assert by_rel["workshop/w1.vpk"].title_source == "addoninfo"
print("workshop merge OK")

win = MainWindow(merged.metas, store, game, addonlist)
tab = win._mods_tab
model = tab.model
conflicts_idx = win._tabs.indexOf(win._conflicts_tab)
assert win._tabs.isTabEnabled(conflicts_idx)
rows = {
    model.data(model.index(r), Qt.ItemDataRole.DisplayRole): r
    for r in range(model.rowCount())
}
assert model.data(model.index(rows["Steam 999 Title"]), ActiveConflictsRole) == 1
assert model.data(model.index(rows["Mod W1"]), ActiveConflictsRole) == 1

view = tab.view
assert not tab.details.isVisibleTo(tab)
view.setCurrentIndex(tab.proxy.mapFromSource(model.index(rows["Mod W1"])))
assert tab.details.isVisibleTo(tab)
assert tab.delegate._highlight == {"workshop/999.vpk"}
assert model.setData(
    model.index(rows["Steam 999 Title"]), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
)
assert json.loads(store_path.read_text())["mods"]["workshop/999.vpk"]["enabled"] is False
assert list(AddonList.load(game).entries) == ["workshop/w1.vpk", "a.vpk", "workshop/999.vpk"]
assert not win._tabs.isTabEnabled(conflicts_idx)
tab.details.close_requested.emit()
assert not tab.details.isVisibleTo(tab) and not view.currentIndex().isValid()

canvas_option = QStyleOptionViewItem()
canvas_option.rect = QRect(0, 0, 200, 152)
canvas = QPixmap(200, 152)
canvas.fill()
painter = QPainter(canvas)
tab.delegate.paint(painter, canvas_option, model.index(rows["Mod W1"]))
painter.end()
print("mods tab OK: grid select/highlight/toggle/paint")

ctab = win._conflicts_tab
assert ctab._empty.isVisibleTo(ctab)
ctab.toggle_requested.emit("workshop/999.vpk", True)
assert win._tabs.isTabEnabled(conflicts_idx)
assert ctab._summary.text() == "1 active conflict group"
ctab.make_winner_requested.emit("workshop/999.vpk", ["workshop/w1.vpk", "workshop/999.vpk"])
assert list(AddonList.load(game).entries) == ["workshop/999.vpk", "workshop/w1.vpk", "a.vpk"]
assert win._conflicts.for_mod("workshop/999.vpk")[0].winner == "workshop/999.vpk"
print("conflicts tab OK: toggle + make-winner")

cat_tab = tab.categories
names = [win._tabs.tabText(i) for i in range(win._tabs.count())]
assert names == ["Mods", "Groups", "Randomize", "Conflicts"], names
assert cat_tab.isVisibleTo(tab)
cat_tab.filter_selected.emit("Sounds", None)
assert tab.proxy.rowCount() == 1
assert tab._chip_label.text() == "Category: Sounds" and tab._chip_widget.isVisibleTo(tab)
cat_tab.filter_selected.emit(None, None)
assert tab.proxy.rowCount() == 3 and not tab._chip_widget.isVisibleTo(tab)
cat_tab.filter_selected.emit("Uncategorized", None)
assert tab.proxy.rowCount() == 2
cat_tab.filter_selected.emit(None, None)
tab.cat_toggle.setChecked(False)
assert not cat_tab.isVisibleTo(tab)
tab.cat_toggle.setChecked(True)
assert cat_tab.isVisibleTo(tab)
print("categories sidebar OK: filter, chip, toggle")

# custom categories (M3)
assert cat_tab.tag_list.count() == 3  # All + Sounds + Uncategorized, no Custom yet
assert row_for_tag(cat_tab.tag_list, "Custom") == -1
assert win._create_custom_category("Kits")
assert not win._create_custom_category("Kits")
assert cat_tab.tag_list.count() == 4
assert cat_tab.tag_list.item(1).text() == "Custom (0)"

win._set_mod_tags("workshop/w1.vpk", ["Kits"])
saved = json.loads(store_path.read_text())
assert saved["custom_categories"] == ["Kits"]
assert saved["mods"]["workshop/w1.vpk"]["tags"] == ["Kits"]
assert cat_tab.tag_list.item(1).text() == "Custom (1)"
assert model.custom_tags_for("workshop/w1.vpk") == ["Kits"]

view.setCurrentIndex(tab.proxy.mapFromSource(model.index(rows["Mod W1"])))
assert tab.details.add_category_btn.isVisibleTo(tab.details)
assert tab.details._custom_tags == ["Kits"]

custom_row = row_for_tag(cat_tab.tag_list, "Custom")
cat_tab.tag_list.setCurrentRow(custom_row)
assert cat_tab.sub_header.text() == "Custom"
assert row_for_tag(cat_tab.sub_list, "Kits") == 1
cat_tab.sub_list.setCurrentRow(1)
assert tab.proxy.rowCount() == 1
assert tab._chip_label.text() == "Category: Custom › Kits"

tab.details.tags_changed.emit("workshop/999.vpk", ["Kits"])
saved = json.loads(store_path.read_text())
assert saved["mods"]["workshop/999.vpk"]["tags"] == ["Kits"]
assert cat_tab.tag_list.item(1).text() == "Custom (2)"

tab.set_category_filter(None, None)
affected = win._delete_custom_category("Kits")
assert affected == 2
saved = json.loads(store_path.read_text())
assert saved["custom_categories"] == []
assert saved["mods"]["workshop/w1.vpk"]["tags"] == []
assert row_for_tag(cat_tab.tag_list, "Custom") == -1
print("custom categories OK: create, assign, filter, cascade delete")

# groups (M4)
gtab = win._groups_tab
assert gtab._empty.isVisibleTo(gtab) and not gtab._scroll.isVisibleTo(gtab)
gid = win._create_group("Tank stuff")
assert gid is not None and win._create_group("Tank stuff") is None
assert gtab._cards[gid].name_label.text().startswith("Tank stuff")

view.setCurrentIndex(tab.proxy.mapFromSource(model.index(rows["Mod W1"])))
tab.details.groups_changed.emit("workshop/w1.vpk", [gid])
saved = json.loads(store_path.read_text())
assert saved["mods"]["workshop/w1.vpk"]["groups"] == [gid]
assert gtab._cards[gid].name_label.text() == "Tank stuff  (1)"
assert tab.details.add_group_btn.isVisibleTo(tab.details)
assert tab.details._group_ids == [gid]
chips = [
    gtab_chips.text()
    for i in range(tab.details.chips.count())
    if (w := tab.details.chips.itemAt(i).widget()) is not None
    for gtab_chips in [w]
]
assert "Tank stuff" in chips

# bulk disable through the group card signal
gtab.group_toggle_requested.emit(gid, False)
saved = json.loads(store_path.read_text())
assert saved["mods"]["workshop/w1.vpk"]["enabled"] is False
assert '"workshop\\w1.vpk"\t\t"0"' in (game / "left4dead2" / "addonlist.txt").read_text()
assert gtab._cards[gid].toggle_btn.text() == "Enable all", "label must flip after bulk disable"
gtab.group_toggle_requested.emit(gid, True)
saved = json.loads(store_path.read_text())
assert saved["mods"]["workshop/w1.vpk"]["enabled"] is True
assert gtab._cards[gid].toggle_btn.text() == "Disable all"

# second member, then remove one via the member row signal
tab.details.groups_changed.emit("workshop/999.vpk", [gid])
assert gtab._cards[gid].name_label.text() == "Tank stuff  (2)"
gtab.member_remove_requested.emit(gid, "workshop/w1.vpk")
saved = json.loads(store_path.read_text())
assert saved["mods"]["workshop/w1.vpk"]["groups"] == []

# rename updates card + chips
assert win._rename_group(gid, "Tank picks")
assert gtab._cards[gid].name_label.text().startswith("Tank picks")
view.setCurrentIndex(tab.proxy.mapFromSource(model.index(rows["Steam 999 Title"])))
chips = [
    w.text()
    for i in range(tab.details.chips.count())
    if (w := tab.details.chips.itemAt(i).widget()) is not None
]
assert "Tank picks" in chips

# collapse/expand all
gtab._toggle_expand_all()
assert not gtab._cards[gid].is_expanded()
gtab._toggle_expand_all()
assert gtab._cards[gid].is_expanded()

# delete cascades
affected = win._delete_group(gid)
assert affected == 1
saved = json.loads(store_path.read_text())
assert saved["groups"] == {}
assert saved["mods"]["workshop/999.vpk"]["groups"] == []
assert gtab._empty.isVisibleTo(gtab)
print("groups OK: create, assign, chips, bulk toggle, remove, rename, cascade delete")

# randomize (M5)
import mod_manager.ui.main_window as mw_mod

rtab5 = win._randomize_tab
assert rtab5._empty.isVisibleTo(rtab5) and not rtab5._scroll.isVisibleTo(rtab5)
corner = win.menuBar().cornerWidget()
assert corner is not None and "Start L4D2" in corner.text()
assert tab.details.add_random_btn is not None

rid = win._create_random_group("Tank music")
assert rid is not None and win._create_random_group("Tank music") is None
assert rtab5._cards[rid].name_label.text().startswith("Tank music")

view.setCurrentIndex(tab.proxy.mapFromSource(model.index(rows["Mod W1"])))
tab.details.random_groups_changed.emit("workshop/w1.vpk", [rid])
saved = json.loads(store_path.read_text())
assert {"kind": "mod", "ref": "workshop/w1.vpk"} in saved["random_groups"][rid]["members"]
tab.details.random_groups_changed.emit("workshop/999.vpk", [rid])
assert tab.details._random_ids == [rid]


class _FakeDesktop:
    urls = []

    @staticmethod
    def openUrl(url):
        _FakeDesktop.urls.append(url.toString())


orig_desktop = mw_mod.QDesktopServices
mw_mod.QDesktopServices = _FakeDesktop
try:
    win._randomize_and_launch(False)
    assert _FakeDesktop.urls == []
    saved = json.loads(store_path.read_text())
    enabled = {rel for rel, e in saved["mods"].items() if e["enabled"]}
    assert ("workshop/w1.vpk" in enabled) != ("workshop/999.vpk" in enabled)
    assert "a.vpk" in enabled  # untouched by the roll
    assert rid in rtab5._picks
    written = (game / "left4dead2" / "addonlist.txt").read_text()
    assert '"AddonList"' in written

    # launch popup: detection path
    from PySide6.QtTest import QTest

    win._launch_poll_ms = 10
    win._launch_detected_ms = 30
    win._launch_note_ms = 30
    detections = iter([False, True])
    orig_gpr = mw_mod.game_process_running
    mw_mod.game_process_running = lambda _gd: next(detections)
    try:
        win._randomize_and_launch(True)
        assert "steam://run/550" in _FakeDesktop.urls
        dlg = win._launch_dialog
        assert dlg is not None and dlg.isVisible()
        QTest.qWait(400)
        assert not dlg.isVisible(), "popup must close after game detection"
        assert win._launch_dialog is None  # refs cleaned up

        # launch popup: timeout path (detector never sees the game)
        mw_mod.game_process_running = lambda _gd: False
        win._launch_timeout_ticks = 3
        win._randomize_and_launch(True)
        dlg2 = win._launch_dialog
        assert dlg2 is not None and dlg2.isVisible()
        assert not dlg2.note.isVisibleTo(dlg2)
        QTest.qWait(150)  # 3 polls x 10ms -> timeout note shows
        assert dlg2.note.isVisibleTo(dlg2)
        QTest.qWait(200)  # note auto-close (30ms)
        assert not dlg2.isVisible(), "popup must auto-close after timeout note"
    finally:
        mw_mod.game_process_running = orig_gpr
finally:
    mw_mod.QDesktopServices = orig_desktop

# mixed membership: group member + mod member, invariant either way
gid2 = win._create_group("Duo")
win._set_mod_groups("workshop/w1.vpk", [gid2])
win._set_mod_groups("a.vpk", [gid2])
rid2 = win._create_random_group("Mixed")
assert win._store.add_random_member(rid2, "group", gid2)
assert win._store.add_random_member(rid2, "mod", "workshop/999.vpk")
win._store.save()
win._push_random_groups()
win._randomize_and_launch(False)
saved = json.loads(store_path.read_text())
enabled = {rel for rel, e in saved["mods"].items() if e["enabled"]}
expected = set()
for _rid, _pick in rtab5._picks.items():
    expected.update(_pick.mods)
assert enabled == expected, (enabled, expected, {k: (v.kind, v.ref) for k, v in rtab5._picks.items()})

win._remove_random_member(rid2, "group", gid2)
assert all(m["kind"] != "group" for m in win._store.random_groups[rid2]["members"])
win._delete_random_group(rid)
win._delete_random_group(rid2)
assert rtab5._empty.isVisibleTo(rtab5)
print("randomize OK: create, assign, dry-run pick-one, start URL, group expansion, cleanup")

# ---------- Part 2: real game dir, read-only ----------
real_game = Path("/mnt/Games/SteamLibrary/steamapps/common/Left 4 Dead 2")
real_metas = scan_addons(real_game / "left4dead2" / "addons", Path("/tmp/opencode/thumbs"))
real_addonlist = AddonList.load(real_game)

from mod_manager.workshop_meta import dict_to_details

cache_raw = json.loads(
    (Path.home() / ".config/l4d2-mod-manager/store.json").read_text()
)["workshop_meta"]
real_cache = {fid: dict_to_details(fid, d) for fid, d in cache_raw.items()}
merged_real = merge_details(real_metas, real_cache, fetcher=None).metas

from mod_manager.conflicts import ConflictIndex
from mod_manager.ui.mods_tab import ModsTab

real_index = ConflictIndex(merged_real)
real_index.set_state(real_addonlist.entries, list(real_addonlist.entries))
real_ctab = ConflictsTab(merged_real, real_index)
groups = real_index.groups()
sizes = [len(g.mods) for g in groups]
assert all(2 <= s < 10 for s in sizes), sizes
assert all(real_addonlist.entries.get(rel) for g in groups for rel in g.mods)

rtab = ModsTab(merged_real, dict(real_addonlist.entries), list(real_addonlist.entries), real_index)
cat = rtab.categories

assert cat.tag_list.count() == 18, cat.tag_list.count()  # All + 16 top-level + Uncategorized
assert cat.tag_list.item(1).text().startswith("Sounds (70)")
assert row_for_tag(cat.tag_list, "Custom") == -1  # empty registry -> no Custom entry
cat.set_custom_tags({"workshop/121088866.vpk": ["Kits"]}, ["Kits"])
assert cat.tag_list.count() == 19
assert cat.tag_list.item(1).text() == "Custom (1)"
assert not cat.sub_list.isVisibleTo(cat)  # hidden until tag selected

weapons_row = row_for_tag(cat.tag_list, "Weapons")
cat.tag_list.setCurrentRow(weapons_row)
assert cat.sub_header.text() == "Weapons"
assert rtab.proxy.rowCount() == 56, rtab.proxy.rowCount()
assert rtab._chip_label.text() == "Category: Weapons"
expected_weapons_children = {
    "Rifle", "SMG", "Shotgun", "Sniper", "Pistol", "M60", "Throwable", "Melee", "Grenade Launcher"
}
assert cat.sub_list.count() == 1 + len(expected_weapons_children)
for child in expected_weapons_children:
    assert row_for_tag(cat.sub_list, child) > 0, child

smg_row = row_for_tag(cat.sub_list, "SMG")
cat.sub_list.setCurrentRow(smg_row)
assert rtab.proxy.rowCount() == 9, rtab.proxy.rowCount()
assert rtab._chip_label.text() == "Category: Weapons › SMG"

si_row = row_for_tag(cat.tag_list, "Special Infected")
cat.tag_list.setCurrentRow(si_row)
for infected_child in ("Tank", "Charger", "Hunter", "Boomer", "Witch", "Jockey", "Smoker", "Spitter"):
    assert row_for_tag(cat.sub_list, infected_child) > 0, infected_child

rtab.set_category_filter(None, None)
assert rtab.proxy.rowCount() == 153

cat.tag_list.setCurrentRow(row_for_tag(cat.tag_list, "Uncategorized"))
assert rtab.proxy.rowCount() == 1

cat.sync_filter("Weapons", "SMG")
assert cat.tag_list.currentItem().data(0x0100 + 1) == "Weapons"
assert cat.sub_list.currentItem().data(0x0100 + 1) == "SMG"
rtab.set_category_filter("Weapons", "SMG")
assert rtab._chip_label.text() == "Category: Weapons › SMG"
assert rtab.proxy.rowCount() == 9

# groups tab with real metas
from mod_manager.ui.groups_tab import GroupsTab

rgroups = GroupsTab(merged_real)
rgroups.refresh(
    {merged_real[0].rel_path: ["g1"], merged_real[1].rel_path: ["g1"]},
    {"g1": {"name": "Favorites", "randomizable": False, "probability": 0.5}},
    {merged_real[0].rel_path: True, merged_real[1].rel_path: False},
)
assert "g1" in rgroups._cards
assert rgroups._cards["g1"].toggle_btn.text() == "Enable all"
rgroups.search.setText("nomatchnothing")
assert rgroups._no_match.isVisibleTo(rgroups)
rgroups.search.setText("")

# randomize tab with real metas
from mod_manager.ui.randomize_tab import RandomizeTab

r_rand = RandomizeTab(merged_real)
r_rand.refresh(
    {
        "r1": {
            "name": "Mix",
            "members": [
                {"kind": "mod", "ref": merged_real[0].rel_path},
                {"kind": "group", "ref": "g1"},
            ],
        }
    },
    {"g1": "Favs"},
    {"g1": [merged_real[1].rel_path]},
    {},
)
assert "r1" in r_rand._cards

# scroll-stability regression: clicking bottom tags must keep them visible
from PySide6.QtTest import QTest

cat.show()
cat.resize(240, 420)
QTest.qWait(30)
for bottom_tag in ("UI", "Scripts"):
    cat.tag_list.scrollToBottom()
    QTest.qWait(20)
    row = row_for_tag(cat.tag_list, bottom_tag)
    assert row > 0, bottom_tag
    item = cat.tag_list.item(row)
    before = cat.tag_list.visualItemRect(item)
    assert before.bottom() <= cat.tag_list.viewport().height(), f"{bottom_tag} not visible pre-click"
    cat.tag_list.setCurrentRow(row)
    QTest.qWait(50)
    after = cat.tag_list.visualItemRect(cat.tag_list.item(row))
    assert after.top() >= 0 and after.bottom() <= cat.tag_list.viewport().height(), (
        f"{bottom_tag} scrolled out of view after click: {after}, viewport={cat.tag_list.viewport().height()}"
    )
    assert cat.tag_list.currentRow() == row
print("scroll stability OK: bottom tags stay visible on click")

# details panel flow layout: many chips wrap, no horizontal scroll
from mod_manager.ui.details_panel import DetailsPanel
from mod_manager.vpk_meta import ModMeta

chip_panel = DetailsPanel()
chip_panel.show()
chip_panel.resize(340, 700)
chip_meta = ModMeta(
    rel_path="workshop/chips.vpk",
    abs_path=Path("/tmp/chips.vpk"),
    source="workshop",
    size=10,
    title="Chip Test",
    content_flags=frozenset(
        {"skin", "sound", "music", "campaign", "map", "survivor", "script", "prop",
         "weapon", "bossinfected", "commoninfected"}
    ),
    workshop_tags=("Charger", "Tank", "Rifle", "SMG", "Shotgun", "Sniper", "Pistol", "Melee"),
)
chip_index = ConflictIndex([chip_meta])
chip_panel.set_context(chip_meta, True, chip_index.for_mod(chip_meta.rel_path), {chip_meta.rel_path: chip_meta})
app.processEvents()
QTest.qWait(30)
assert chip_panel._scroll.horizontalScrollBar().maximum() == 0
chips_height = chip_panel.chips_container.height()
assert chips_height > 60, chips_height  # wrapped into multiple rows

# narrow-width regression: content min never exceeds viewport, thumb rescales
from PySide6.QtGui import QPixmap, QColor

tp = QPixmap(640, 360)
tp.fill(QColor("red"))
chip_meta = ModMeta(
    rel_path="workshop/thumb.vpk",
    abs_path=Path("/tmp/t.vpk"),
    source="workshop",
    size=10,
    title="Thumb Test",
    thumbnail=Path("/tmp/opencode/thumb_test.png"),
)
tp.save("/tmp/opencode/thumb_test.png")
chip_index2 = ConflictIndex([chip_meta])
chip_panel.set_context(chip_meta, True, chip_index2.for_mod(chip_meta.rel_path), {chip_meta.rel_path: chip_meta})
for width in (340, 300):
    chip_panel.resize(width, 700)
    app.processEvents()
    QTest.qWait(30)
    viewport = chip_panel._scroll.viewport().width()
    content = chip_panel._scroll.widget().width()
    min_hint = chip_panel._scroll.widget().minimumSizeHint().width()
    assert content <= viewport, f"content overflows at width={width}: {content} > {viewport}"
    assert min_hint <= viewport, f"min hint blocks at width={width}: {min_hint} > {viewport}"
    assert chip_panel.thumb.pixmap().width() <= viewport - 2
    assert chip_panel._scroll.horizontalScrollBar().maximum() == 0

# long unbreakable text regression (real bug: author line lacked wordWrap)
torture = ModMeta(
    rel_path="workshop/torture.vpk",
    abs_path=Path("/tmp/torture.vpk"),
    source="workshop",
    size=10,
    title="T" * 120,
    author="A" * 120,
    tagline="G" * 120,
    description="D" * 300 + " normal words",
)
chip_panel.set_context(torture, True, [], {torture.rel_path: torture})
app.processEvents()
QTest.qWait(30)
for width in (340, 300):
    chip_panel.resize(width, 700)
    app.processEvents()
    QTest.qWait(30)
    viewport = chip_panel._scroll.viewport().width()
    min_hint = chip_panel._scroll.widget().minimumSizeHint().width()
    assert min_hint <= viewport, f"unbreakable text overflows at {width}: {min_hint} > {viewport}"
    assert chip_panel._scroll.widget().width() <= viewport
    assert chip_panel._scroll.horizontalScrollBar().maximum() == 0
print("long-token wrapping OK at 340/300px")
print(f"flow layout OK: chips wrapped in {chips_height}px, no overflow at 340/300px")

print(f"real dir OK: {len(groups)} conflict groups {sizes}, tag drill-down verified")
print("SMOKE PASSED")
