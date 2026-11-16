from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..categories import (
    CUSTOM_TAG,
    UNCATEGORIZED_TAG,
    custom_counts,
    subtag_counts,
    top_level_counts,
    uncategorized_count,
)
from ..vpk_meta import ModMeta

_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class CategoriesPanel(QWidget):
    filter_selected = Signal(object, object)

    def __init__(self, metas: list[ModMeta], parent=None) -> None:
        super().__init__(parent)
        self._metas = list(metas)
        self._current_tag: str | None = None
        self._current_subtag: str | None = None
        self._custom_registry: list[str] = []
        self._custom_assignments: dict[str, list[str]] = {}
        self.setMinimumWidth(190)
        self.setMaximumWidth(190)

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter categories…")
        layout.addWidget(self.search)

        self.tag_list = QListWidget()
        layout.addWidget(self.tag_list, 2)

        self.sub_header = QLabel()
        self.sub_header.setStyleSheet("font-weight: bold; border-top: 1px solid #4a4f57; padding-top: 4px;")
        self.sub_header.setVisible(False)
        layout.addWidget(self.sub_header)

        self.sub_list = QListWidget()
        self.sub_list.setVisible(False)
        layout.addWidget(self.sub_list, 1)

        self._rebuild_tags("")

        self.search.textChanged.connect(self._rebuild_tags)
        self.tag_list.currentRowChanged.connect(self._on_tag_row)
        self.sub_list.currentRowChanged.connect(self._on_subtag_row)

    def _rebuild_tags(self, search_text: str) -> None:
        needle = search_text.strip().lower()
        blocked = self.tag_list.blockSignals(True)
        self.tag_list.clear()

        all_item = QListWidgetItem(f"All mods ({len(self._metas)})")
        all_item.setData(_ROLE, None)
        self.tag_list.addItem(all_item)

        if self._custom_registry:
            assigned = sum(1 for tags in self._custom_assignments.values() if tags)
            custom_item = QListWidgetItem(f"Custom ({assigned})")
            custom_item.setData(_ROLE, CUSTOM_TAG)
            self.tag_list.addItem(custom_item)

        for tag, count in top_level_counts(self._metas):
            if needle and needle not in tag.lower():
                continue
            item = QListWidgetItem(f"{tag} ({count})")
            item.setData(_ROLE, tag)
            self.tag_list.addItem(item)

        uncategorized = uncategorized_count(self._metas)
        if not needle or "uncategorized" in needle:
            unc_item = QListWidgetItem(f"Uncategorized ({uncategorized})")
            unc_item.setData(_ROLE, UNCATEGORIZED_TAG)
            self.tag_list.addItem(unc_item)

        self._select_current_tag()
        self.tag_list.blockSignals(blocked)

    def _select_current_tag(self) -> None:
        current = self.tag_list.currentItem()
        if current is not None and current.data(_ROLE) == self._current_tag:
            return
        blocked = self.tag_list.blockSignals(True)
        for row in range(self.tag_list.count()):
            if self.tag_list.item(row).data(_ROLE) == self._current_tag:
                self.tag_list.setCurrentRow(row)
                break
        else:
            self.tag_list.setCurrentRow(0)
        self.tag_list.blockSignals(blocked)

    def _ensure_visible(self, list_widget: QListWidget, row: int) -> None:
        index = list_widget.model().index(row, 0)
        QTimer.singleShot(
            0,
            lambda: list_widget.scrollTo(
                index, QAbstractItemView.ScrollHint.PositionAtCenter
            ),
        )

    def _on_tag_row(self, row: int) -> None:
        if row < 0:
            return
        tag = self.tag_list.item(row).data(_ROLE)
        self._current_tag = tag
        self._current_subtag = None
        if tag is None or tag == UNCATEGORIZED_TAG:
            self.sub_header.setVisible(False)
            self.sub_list.setVisible(False)
        elif tag == CUSTOM_TAG:
            self._rebuild_custom_subtags()
            self.sub_header.setVisible(True)
            self.sub_list.setVisible(True)
        else:
            self._rebuild_subtags(tag)
            self.sub_header.setVisible(True)
            self.sub_list.setVisible(True)
        self.filter_selected.emit(tag, None)
        self._ensure_visible(self.tag_list, row)

    def _rebuild_custom_subtags(self) -> None:
        blocked = self.sub_list.blockSignals(True)
        self.sub_list.clear()
        self.sub_header.setText(CUSTOM_TAG)

        assigned = sum(1 for tags in self._custom_assignments.values() if tags)
        all_item = QListWidgetItem(f"All Custom ({assigned})")
        all_item.setData(_ROLE, None)
        self.sub_list.addItem(all_item)

        for name, count in custom_counts(self._custom_assignments, self._custom_registry):
            item = QListWidgetItem(f"{name} ({count})")
            item.setData(_ROLE, name)
            self.sub_list.addItem(item)

        self.sub_list.setCurrentRow(0)
        self.sub_list.blockSignals(blocked)

    def _rebuild_subtags(self, tag: str) -> None:
        blocked = self.sub_list.blockSignals(True)
        self.sub_list.clear()
        self.sub_header.setText(tag)

        parent_count = sum(1 for m in self._metas if tag in m.workshop_tags)
        all_item = QListWidgetItem(f"All {tag} ({parent_count})")
        all_item.setData(_ROLE, None)
        self.sub_list.addItem(all_item)

        for sub_tag, count in subtag_counts(self._metas, tag):
            item = QListWidgetItem(f"{sub_tag} ({count})")
            item.setData(_ROLE, sub_tag)
            self.sub_list.addItem(item)

        self.sub_list.setCurrentRow(0)
        self.sub_list.blockSignals(blocked)

    def _on_subtag_row(self, row: int) -> None:
        if row < 0 or self._current_tag in (None, UNCATEGORIZED_TAG):
            return
        self._current_subtag = self.sub_list.item(row).data(_ROLE)
        self.filter_selected.emit(self._current_tag, self._current_subtag)
        self._ensure_visible(self.sub_list, row)

    def set_custom_tags(self, assignments: dict[str, list[str]], registry: list[str]) -> None:
        self._custom_assignments = {rel: list(tags) for rel, tags in assignments.items() if tags}
        self._custom_registry = list(registry)
        self._rebuild_tags(self.search.text() or "")
        if self._current_tag == CUSTOM_TAG:
            self._rebuild_custom_subtags()

    def _select_current_subtag(self, subtag) -> None:
        current_sub = self.sub_list.currentItem()
        if current_sub is not None and current_sub.data(_ROLE) == subtag:
            return
        blocked = self.sub_list.blockSignals(True)
        for row in range(self.sub_list.count()):
            if self.sub_list.item(row).data(_ROLE) == subtag:
                self.sub_list.setCurrentRow(row)
                break
        self.sub_list.blockSignals(blocked)

    def sync_filter(self, tag: str | None, subtag: str | None) -> None:
        self._current_tag = tag
        self._current_subtag = subtag
        if tag == CUSTOM_TAG:
            self._rebuild_custom_subtags()
            self.sub_header.setVisible(True)
            self.sub_list.setVisible(True)
            self._select_current_subtag(subtag)
        elif tag is not None and tag != UNCATEGORIZED_TAG:
            self._rebuild_subtags(tag)
            self.sub_header.setVisible(True)
            self.sub_list.setVisible(True)
            self._select_current_subtag(subtag)
        else:
            self.sub_header.setVisible(False)
            self.sub_list.setVisible(False)
        self._select_current_tag()
