from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import random

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from ..conflicts import ConflictIndex
from ..game import AddonList, game_process_running
from ..randomizer import roll
from ..store import Store, SyncReport
from ..vpk_meta import ModMeta
from .conflicts_tab import ConflictsTab
from .groups_tab import GroupsTab
from .launch_dialog import LaunchDialog
from .mods_tab import ModsTab
from .randomize_tab import RandomizeTab


class MainWindow(QMainWindow):
    def __init__(
        self,
        metas: list[ModMeta],
        store: Store,
        game_dir: Path,
        addonlist: AddonList,
        sync_report: SyncReport | None = None,
        on_change_game_dir: Callable[[], None] | None = None,
        on_rescan: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("L4D2 Mod Manager")
        self.resize(1100, 650)

        self._store = store
        self._game_dir = game_dir
        self._addonlist = addonlist
        self._conflicts = ConflictIndex(metas)
        self._on_change_game_dir = on_change_game_dir
        self._launch_dialog: LaunchDialog | None = None
        self._launch_timer: QTimer | None = None
        self._launch_ticks = 0
        self._launch_poll_ms = 1000
        self._launch_timeout_ticks = 90
        self._launch_detected_ms = 800
        self._launch_note_ms = 6000

        self._tabs = QTabWidget()
        enabled_map = dict(store.enabled_map())
        order = list(addonlist.entries)
        self._mods_tab = ModsTab(
            metas, enabled_map, order, self._conflicts, on_toggle=self._toggle_mod
        )
        self._tabs.addTab(self._mods_tab, "Mods")

        self._groups_tab = GroupsTab(metas)
        self._groups_tab.new_group_requested.connect(self._new_group_dialog)
        self._groups_tab.group_rename_requested.connect(self._rename_group_dialog)
        self._groups_tab.group_delete_requested.connect(self._delete_group_dialog)
        self._groups_tab.group_toggle_requested.connect(self._toggle_group)
        self._groups_tab.member_remove_requested.connect(self._remove_from_group)
        self._groups_tab.mod_selected.connect(self._jump_to_mod)
        self._tabs.addTab(self._groups_tab, "Groups")

        self._mods_tab.model.toggled.connect(
            lambda *_: self._groups_tab.refresh(enabled_map=self._store.enabled_map())
        )

        self._randomize_tab = RandomizeTab(metas)
        self._randomize_tab.new_random_group_requested.connect(self._new_random_group_dialog)
        self._randomize_tab.random_rename_requested.connect(self._rename_random_group_dialog)
        self._randomize_tab.random_delete_requested.connect(self._delete_random_group_dialog)
        self._randomize_tab.add_member_requested.connect(self._add_random_member_dialog)
        self._randomize_tab.member_remove_requested.connect(self._remove_random_member)
        self._randomize_tab.member_selected.connect(self._random_member_selected)
        self._randomize_tab.randomize_requested.connect(self._randomize_and_launch)
        self._tabs.addTab(self._randomize_tab, "Randomize")

        self._conflicts_tab = ConflictsTab(metas, self._conflicts)
        conflicts_index = self._tabs.addTab(self._conflicts_tab, "Conflicts")
        self._conflicts_tab.toggle_requested.connect(self._toggle_via_model)
        self._conflicts_tab.make_winner_requested.connect(self._make_winner)
        self._conflicts_tab.has_conflicts_changed.connect(
            lambda has: self._tabs.setTabEnabled(conflicts_index, has)
        )
        self._tabs.setTabEnabled(conflicts_index, self._conflicts_tab.has_conflicts)
        self._mods_tab.model.toggled.connect(lambda *_: self._conflicts_tab.refresh())
        self.setCentralWidget(self._tabs)

        self._mods_tab.details.tags_changed.connect(self._set_mod_tags)
        self._mods_tab.details.new_category_requested.connect(self._new_category_for_current)
        self._mods_tab.details.groups_changed.connect(self._set_mod_groups)
        self._mods_tab.details.new_group_requested.connect(self._new_group_for_current)
        self._mods_tab.details.random_groups_changed.connect(self._set_mod_random_groups)
        self._mods_tab.details.new_random_requested.connect(self._new_random_for_current)
        self._push_custom_tags()
        self._push_groups()
        self._push_random_groups()

        self._start_btn = QPushButton("▶ Start L4D2")
        self._start_btn.setToolTip("Roll all random groups and launch the game")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #3d8f5f; color: white; font-weight: bold;"
            "border-radius: 4px; padding: 4px 12px; }"
        )
        self._start_btn.clicked.connect(lambda: self._randomize_and_launch(True))
        self.menuBar().setCornerWidget(self._start_btn)

        self._refresh_status()
        if sync_report is not None and (sync_report.added or sync_report.removed):
            self.statusBar().showMessage(
                f"Library sync: {len(sync_report.added)} added, "
                f"{len(sync_report.removed)} removed",
                8000,
            )

        menu = self.menuBar().addMenu("&File")
        rescan_action = menu.addAction("Rescan")
        rescan_action.triggered.connect(lambda: on_rescan() if on_rescan else None)
        change_action = menu.addAction("Change Game Directory…")
        change_action.triggered.connect(self._change_dir)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        categories_menu = self.menuBar().addMenu("&Categories")
        add_cat_action = categories_menu.addAction("Add custom category…")
        add_cat_action.triggered.connect(self._add_custom_category_dialog)
        del_cat_action = categories_menu.addAction("Delete custom category…")
        del_cat_action.triggered.connect(self._delete_custom_category_dialog)

    def _toggle_mod(self, rel_path: str, enabled: bool) -> None:
        self._store.set_enabled(rel_path, enabled)
        self._store.save()
        self._addonlist.set(rel_path, enabled)
        self._addonlist.save(self._game_dir)
        self._refresh_status()

    def _toggle_via_model(self, rel_path: str, enabled: bool) -> None:
        self._mods_tab.toggle(rel_path, enabled)

    def _push_custom_tags(self) -> None:
        assignments = self._store.custom_assignments()
        registry = list(self._store.custom_categories)
        self._mods_tab.set_custom_tags(assignments)
        self._mods_tab.categories.set_custom_tags(assignments, registry)
        self._mods_tab.details.set_custom_categories(registry)

    def _create_custom_category(self, name: str) -> bool:
        if not self._store.add_custom_category(name):
            return False
        self._store.save()
        self._push_custom_tags()
        return True

    def _add_custom_category_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "Add custom category", "Category name:")
        if not ok:
            return
        if not self._create_custom_category(name):
            QMessageBox.warning(
                self, "Add custom category", "Invalid or duplicate category name."
            )

    def _delete_custom_category(self, name: str) -> int:
        affected = self._store.delete_custom_category(name)
        self._store.save()
        self._push_custom_tags()
        return affected

    def _delete_custom_category_dialog(self) -> None:
        if not self._store.custom_categories:
            QMessageBox.information(
                self, "Delete custom category", "There are no custom categories yet."
            )
            return
        assignments = self._store.custom_assignments()
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete custom category")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select a category to delete:"))
        list_widget = QListWidget()
        for name in self._store.custom_categories:
            count = sum(1 for tags in assignments.values() if name in tags)
            QListWidgetItem(f"{name} ({count} mods)", list_widget)
        list_widget.setCurrentRow(0)
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Delete | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted or list_widget.currentRow() < 0:
            return
        chosen = self._store.custom_categories[list_widget.currentRow()]
        answer = QMessageBox.question(
            self,
            "Delete custom category",
            f"Delete '{chosen}' and unassign it from all mods?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._delete_custom_category(chosen)

    def _set_mod_tags(self, rel_path: str, tags: list[str]) -> None:
        self._store.set_mod_tags(rel_path, tags)
        self._store.save()
        self._push_custom_tags()

    def _new_category_for_current(self) -> None:
        rel = self._mods_tab.details.current_rel()
        if rel is None:
            return
        name, ok = QInputDialog.getText(
            self, "New category", f"Category name (also assigned to this mod):"
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "New category", "Category name cannot be empty.")
            return
        if name not in self._store.custom_categories:
            if not self._create_custom_category(name):
                QMessageBox.warning(
                    self, "New category", "Invalid or duplicate category name."
                )
                return
        tags = self._store.mod_tags(rel)
        if name not in tags:
            tags.append(name)
        self._set_mod_tags(rel, tags)

    def _push_groups(self) -> None:
        assignments = self._store.group_assignments()
        registry = [
            (gid, g.get("name", "")) for gid, g in self._store.groups.items()
        ]
        self._mods_tab.set_groups(assignments, registry)
        self._groups_tab.refresh(
            assignments, dict(self._store.groups), self._store.enabled_map()
        )

    def _create_group(self, name: str) -> str | None:
        group_id = self._store.add_group(name)
        if group_id is None:
            return None
        self._store.save()
        self._push_groups()
        return group_id

    def _new_group_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "New group", "Group name:")
        if not ok:
            return
        if self._create_group(name) is None:
            QMessageBox.warning(self, "New group", "Invalid or duplicate group name.")

    def _rename_group(self, group_id: str, name: str) -> bool:
        if not self._store.rename_group(group_id, name):
            return False
        self._store.save()
        self._push_groups()
        return True

    def _rename_group_dialog(self, group_id: str) -> None:
        current = self._store.group_name(group_id) or ""
        name, ok = QInputDialog.getText(
            self, "Rename group", "Group name:", text=current
        )
        if not ok:
            return
        if not self._rename_group(group_id, name):
            QMessageBox.warning(self, "Rename group", "Invalid or duplicate group name.")

    def _delete_group(self, group_id: str) -> int:
        affected = self._store.delete_group(group_id)
        self._store.save()
        self._push_groups()
        return affected

    def _delete_group_dialog(self, group_id: str) -> None:
        name = self._store.group_name(group_id) or ""
        members = len(self._store.group_members(group_id))
        answer = QMessageBox.question(
            self,
            "Delete group",
            f"Delete '{name}' ({members} mod(s))? Mods are not deleted, only unassigned.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._delete_group(group_id)

    def _set_mod_groups(self, rel_path: str, group_ids: list[str]) -> None:
        self._store.set_mod_groups(rel_path, group_ids)
        self._store.save()
        self._push_groups()

    def _remove_from_group(self, group_id: str, rel_path: str) -> None:
        ids = self._store.mod_groups(rel_path)
        if group_id in ids:
            ids.remove(group_id)
        self._set_mod_groups(rel_path, ids)

    def _new_group_for_current(self) -> None:
        rel = self._mods_tab.details.current_rel()
        if rel is None:
            return
        name, ok = QInputDialog.getText(
            self, "New group", "Group name (current mod will be added):"
        )
        if not ok:
            return
        group_id = self._create_group(name)
        if group_id is None:
            QMessageBox.warning(self, "New group", "Invalid or duplicate group name.")
            return
        ids = self._store.mod_groups(rel)
        if group_id not in ids:
            ids.append(group_id)
        self._set_mod_groups(rel, ids)

    def _toggle_group(self, group_id: str, enabled: bool) -> None:
        for rel in self._store.group_members(group_id):
            self._mods_tab.toggle(rel, enabled)

    def _jump_to_mod(self, rel_path: str) -> None:
        self._tabs.setCurrentWidget(self._mods_tab)
        self._mods_tab.jump_to(rel_path)

    def _push_random_groups(self) -> None:
        assignments = {
            rel: self._store.mod_random_groups(rel) for rel in self._store.mods
        }
        assignments = {rel: ids for rel, ids in assignments.items() if ids}
        registry = [
            (rid, rg.get("name", ""))
            for rid, rg in self._store.random_groups.items()
        ]
        self._mods_tab.set_random_groups(assignments, registry)
        self._randomize_tab.refresh(
            {rid: dict(rg) for rid, rg in self._store.random_groups.items()},
            {gid: g.get("name", "") for gid, g in self._store.groups.items()},
            {gid: self._store.group_members(gid) for gid in self._store.groups},
            self._store.enabled_map(),
        )

    def _create_random_group(self, name: str) -> str | None:
        rg_id = self._store.add_random_group(name)
        if rg_id is None:
            return None
        self._store.save()
        self._push_random_groups()
        return rg_id

    def _new_random_group_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "New random group", "Random group name:")
        if not ok:
            return
        if self._create_random_group(name) is None:
            QMessageBox.warning(
                self, "New random group", "Invalid or duplicate random group name."
            )

    def _rename_random_group(self, rg_id: str, name: str) -> bool:
        if not self._store.rename_random_group(rg_id, name):
            return False
        self._store.save()
        self._push_random_groups()
        return True

    def _rename_random_group_dialog(self, rg_id: str) -> None:
        current = self._store.random_group_name(rg_id) or ""
        name, ok = QInputDialog.getText(
            self, "Rename random group", "Random group name:", text=current
        )
        if not ok:
            return
        if not self._rename_random_group(rg_id, name):
            QMessageBox.warning(
                self, "Rename random group", "Invalid or duplicate name."
            )

    def _delete_random_group(self, rg_id: str) -> None:
        self._store.delete_random_group(rg_id)
        self._store.save()
        self._randomize_tab.set_picks({})
        self._push_random_groups()

    def _delete_random_group_dialog(self, rg_id: str) -> None:
        name = self._store.random_group_name(rg_id) or ""
        answer = QMessageBox.question(
            self, "Delete random group", f"Delete '{name}'?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._delete_random_group(rg_id)

    def _random_member_rows(self) -> list[tuple[str, str | None, str]]:
        rows: list[tuple[str, str | None, str]] = [("header", None, "GROUPS")]
        for gid in sorted(
            self._store.groups, key=lambda g: self._store.group_name(g) or ""
        ):
            gname = self._store.group_name(gid) or ""
            count = len(self._store.group_members(gid))
            rows.append(("group", gid, f"Group: {gname} ({count} mods)"))
        rows.append(("header", None, "MODS"))
        metas = self._mods_tab.model
        mod_rows = sorted(
            (
                ("mod", metas.meta_at(row).rel_path, metas.meta_at(row).title)
                for row in range(metas.rowCount())
            ),
            key=lambda r: r[2].lower(),
        )
        rows.extend(mod_rows)
        return rows

    def _add_random_member_dialog(self, rg_id: str) -> None:
        rg = self._store.random_groups.get(rg_id)
        if rg is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Add members")
        dialog.resize(420, 480)
        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText("Filter mods and groups…")
        layout.addWidget(search)
        list_widget = QListWidget()
        current = {
            (m.get("kind"), m.get("ref")) for m in rg.get("members", [])
        }
        rows = self._random_member_rows()
        items = []
        gray = QColor(150, 154, 162)
        for kind, ref, label in rows:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (kind, ref))
            if kind == "header":
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setForeground(gray)
            else:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if (kind, ref) in current
                    else Qt.CheckState.Unchecked
                )
            list_widget.addItem(item)
            items.append(item)

        def apply_filter(text: str) -> None:
            needle = text.strip().lower()
            for i, (kind, _ref, label) in enumerate(rows):
                if kind == "header":
                    list_widget.setRowHidden(i, bool(needle))
                else:
                    list_widget.setRowHidden(
                        i, bool(needle) and needle not in label.lower()
                    )

        search.textChanged.connect(apply_filter)
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = {
            items[i].data(Qt.ItemDataRole.UserRole)
            for i in range(len(items))
            if items[i].checkState() == Qt.CheckState.Checked
        }
        for kind, ref in current - target:
            self._store.remove_random_member(rg_id, kind, ref)
        for kind, ref in target - current:
            self._store.add_random_member(rg_id, kind, ref)
        self._store.save()
        self._push_random_groups()

    def _remove_random_member(self, rg_id: str, kind: str, ref: str) -> None:
        self._store.remove_random_member(rg_id, kind, ref)
        self._store.save()
        self._push_random_groups()

    def _random_member_selected(self, kind: str, ref: str) -> None:
        if kind == "group":
            self._tabs.setCurrentWidget(self._groups_tab)
        else:
            self._jump_to_mod(ref)

    def _set_mod_random_groups(self, rel_path: str, rg_ids: list[str]) -> None:
        current = set(self._store.mod_random_groups(rel_path))
        target = {rg_id for rg_id in rg_ids if rg_id in self._store.random_groups}
        for rg_id in current - target:
            self._store.remove_random_member(rg_id, "mod", rel_path)
        for rg_id in target - current:
            self._store.add_random_member(rg_id, "mod", rel_path)
        self._store.save()
        self._push_random_groups()

    def _new_random_for_current(self) -> None:
        rel = self._mods_tab.details.current_rel()
        if rel is None:
            return
        name, ok = QInputDialog.getText(
            self, "New random group", "Name (current mod will be added):"
        )
        if not ok:
            return
        rg_id = self._create_random_group(name)
        if rg_id is None:
            QMessageBox.warning(
                self, "New random group", "Invalid or duplicate random group name."
            )
            return
        self._store.add_random_member(rg_id, "mod", rel)
        self._store.save()
        self._push_random_groups()

    def _apply_roll(self) -> tuple:
        rng = random.Random()
        group_membership = {
            gid: self._store.group_members(gid) for gid in self._store.groups
        }
        result = roll(
            self._store.random_groups,
            group_membership,
            rng,
            known_mods=set(self._store.mods),
        )
        for rel, enabled in result.enable_map.items():
            self._mods_tab.toggle(rel, enabled)
        self._randomize_tab.set_picks(result.picks)
        self._push_random_groups()
        enabled_count = sum(1 for value in result.enable_map.values() if value)
        return result, enabled_count

    def _randomize_and_launch(self, launch: bool) -> None:
        if launch and self._launch_dialog is not None and self._launch_dialog.isVisible():
            return
        if not self._store.random_groups:
            self.statusBar().showMessage("No random groups defined", 5000)
            if launch:
                answer = QMessageBox.question(
                    self,
                    "Start L4D2",
                    "No random groups defined. Start the game anyway?",
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self._start_game_with_feedback(rolled=False)
            return
        if not launch:
            _result, enabled_count = self._apply_roll()
            self.statusBar().showMessage(
                f"Rolled — {enabled_count} mod(s) enabled", 8000
            )
            return
        self._start_game_with_feedback(rolled=True)

    def _start_game_with_feedback(self, rolled: bool) -> None:
        dialog = LaunchDialog(self)
        self._launch_dialog = dialog
        dialog.show()
        QApplication.processEvents()

        enabled_count = 0
        if rolled:
            _result, enabled_count = self._apply_roll()
            self.statusBar().showMessage(
                f"Rolled — {enabled_count} mod(s) enabled", 8000
            )

        dialog.set_stage("Starting Left 4 Dead 2…")
        QDesktopServices.openUrl(QUrl("steam://run/550"))
        QApplication.processEvents()

        timer = QTimer(self)
        self._launch_timer = timer
        self._launch_ticks = 0
        timer.timeout.connect(lambda: self._poll_game(dialog, timer))
        dialog.finished.connect(self._clear_launch_refs)
        timer.start(self._launch_poll_ms)
        if game_process_running(self._game_dir):
            self._game_detected(dialog, timer)

    def _poll_game(self, dialog: LaunchDialog, timer: QTimer) -> None:
        self._launch_ticks += 1
        if game_process_running(self._game_dir):
            self._game_detected(dialog, timer)
        elif self._launch_ticks >= self._launch_timeout_ticks:
            timer.stop()
            dialog.timeout_note()
            QTimer.singleShot(self._launch_note_ms, dialog.close)

    def _game_detected(self, dialog: LaunchDialog, timer: QTimer) -> None:
        timer.stop()
        dialog.game_detected()
        QTimer.singleShot(self._launch_detected_ms, dialog.close)

    def _clear_launch_refs(self) -> None:
        if self._launch_timer is not None:
            self._launch_timer.stop()
            self._launch_timer = None
        self._launch_dialog = None

    def _make_winner(self, rel_path: str, group_rels: list[str]) -> None:
        order = list(self._addonlist.entries)
        others = [rel for rel in group_rels if rel != rel_path and rel in order]
        if rel_path not in order or not others:
            return
        top = min(others, key=order.index)
        if order.index(rel_path) < order.index(top):
            return
        order.remove(rel_path)
        order.insert(order.index(top), rel_path)
        self._addonlist.reorder(order)
        self._addonlist.save(self._game_dir)
        self._mods_tab.apply_new_order(order)
        self._conflicts_tab.refresh()
        self._refresh_status()

    def _refresh_status(self) -> None:
        enabled_map = self._store.enabled_map()
        enabled = sum(1 for value in enabled_map.values() if value)
        self.statusBar().showMessage(
            f"{len(enabled_map)} mods · {enabled} enabled · "
            f"{self._conflicts.total_active_pairs()} active conflicts"
        )

    def _change_dir(self) -> None:
        if self._on_change_game_dir is not None:
            self._on_change_game_dir()

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Scan failed", message)
