from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListView,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..categories import CUSTOM_TAG, UNCATEGORIZED_TAG
from ..conflicts import ConflictIndex
from ..vpk_meta import ModMeta
from .card_delegate import CardDelegate
from .categories_panel import CategoriesPanel
from .conflict_dialog import ConflictDialog
from .details_panel import DetailsPanel
from .mods_model import (
    AuthorSortRole,
    CategorySortRole,
    ConflictsSortRole,
    EnabledSortRole,
    ModsModel,
    NameSortRole,
    SizeSortRole,
)

_SORTS: list[tuple[str, int]] = [
    ("Name", NameSortRole),
    ("Author", AuthorSortRole),
    ("Category", CategorySortRole),
    ("Size", SizeSortRole),
    ("Conflicts", ConflictsSortRole),
    ("Enabled", EnabledSortRole),
]


class ModsProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._filter_text = ""
        self._filter_tag: str | None = None
        self._filter_subtag: str | None = None

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.strip().lower()
        self.invalidateFilter()

    def set_category_filter(self, tag: str | None, subtag: str | None = None) -> None:
        self._filter_tag = tag
        self._filter_subtag = subtag
        self.invalidateFilter()

    def _tag_match(self, meta) -> bool:
        if self._filter_tag is None:
            return True
        if self._filter_tag == CUSTOM_TAG:
            custom = self.sourceModel().custom_tags_for(meta.rel_path)
            if self._filter_subtag is None:
                return bool(custom)
            return self._filter_subtag in custom
        tags = meta.workshop_tags
        if self._filter_tag == UNCATEGORIZED_TAG:
            return not tags and self._filter_subtag is None
        if self._filter_tag not in tags:
            return False
        if self._filter_subtag is not None and self._filter_subtag not in tags:
            return False
        return True

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()
        meta = model.meta_at(source_row)
        if self._filter_text:
            haystack = " ".join(
                [meta.title, meta.author or "", meta.filename, meta.rel_path]
            ).lower()
            if self._filter_text not in haystack:
                return False
        return self._tag_match(meta)

    def lessThan(self, left, right) -> bool:
        lv = left.data(self.sortRole())
        rv = right.data(self.sortRole())
        if lv is None:
            return True
        if rv is None:
            return False
        try:
            return lv < rv
        except TypeError:
            return str(lv) < str(rv)


class ModsTab(QWidget):
    category_filter_changed = Signal(object, object)

    def __init__(
        self,
        metas: list[ModMeta],
        enabled_map: dict[str, bool],
        order: list[str],
        conflicts: ConflictIndex,
        on_toggle=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._metas = list(metas)
        self._conflicts = conflicts
        self._lookup = {m.rel_path: m for m in self._metas}
        self._custom_tags: dict[str, list[str]] = {}
        self._group_assignments: dict[str, list[str]] = {}
        self._group_registry: dict[str, str] = {}
        self._random_assignments: dict[str, list[str]] = {}

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, author or file…")
        self._chip_label = QLabel()
        self._chip_clear = QToolButton()
        self._chip_clear.setText("×")
        self._chip_clear.setToolTip("Clear category filter")
        self._chip_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chip_widget = QWidget()
        chip_layout = QHBoxLayout(self._chip_widget)
        chip_layout.setContentsMargins(6, 0, 0, 0)
        chip_layout.setSpacing(2)
        chip_layout.addWidget(self._chip_label)
        chip_layout.addWidget(self._chip_clear)
        self._chip_widget.setVisible(False)
        self.sort_combo = QComboBox()
        for label, _role in _SORTS:
            self.sort_combo.addItem(label)
        self.sort_dir = QPushButton("↑")
        self.sort_dir.setFixedWidth(34)
        self.sort_dir.setCheckable(True)
        self.sort_dir.setToolTip("Toggle ascending / descending")
        top.addWidget(self.search, 1)
        top.addWidget(self._chip_widget)
        top.addWidget(self.sort_combo)
        top.addWidget(self.sort_dir)
        self.cat_toggle = QToolButton()
        self.cat_toggle.setText("Categories")
        self.cat_toggle.setCheckable(True)
        self.cat_toggle.setChecked(True)
        self.cat_toggle.setToolTip("Show or hide the categories sidebar")
        top.addWidget(self.cat_toggle)
        layout.addLayout(top)

        self.model = ModsModel(metas, enabled_map, order, conflicts, self)
        self.model.toggled.connect(self._on_toggled)
        if on_toggle is not None:
            self.model.toggled.connect(on_toggle)

        self.proxy = ModsProxy(self)
        self.proxy.setSourceModel(self.model)
        self._apply_sort()

        self.view = QListView()
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setUniformItemSizes(True)
        self.view.setSpacing(8)
        self.view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerItem)
        self.view.setModel(self.proxy)
        self.delegate = CardDelegate(self.view, self.view)
        self.view.setItemDelegate(self.delegate)

        self.details = DetailsPanel()

        self.categories = CategoriesPanel(metas)
        self.categories.filter_selected.connect(self.set_category_filter)
        self.category_filter_changed.connect(self.categories.sync_filter)
        self.cat_toggle.toggled.connect(self.categories.setVisible)

        splitter = QSplitter()
        splitter.addWidget(self.categories)
        splitter.addWidget(self.view)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setCollapsible(2, False)
        splitter.setSizes([190, 900, 340])
        self._splitter = splitter
        layout.addWidget(splitter, 1)

        if not metas:
            empty = QLabel("No VPK mods found in the game's addons folder.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
            self.view.setVisible(False)
            self.details.setVisible(False)
            self.categories.setVisible(False)
            self.cat_toggle.setEnabled(False)

        self.details.setVisible(False)

        self.search.textChanged.connect(self.proxy.set_filter_text)
        self.sort_combo.currentIndexChanged.connect(lambda _: self._apply_sort())
        self.sort_dir.toggled.connect(lambda _: self._apply_sort())
        self._chip_clear.clicked.connect(lambda: self.set_category_filter(None, None))
        self.details.conflict_selected.connect(self.jump_to)
        self.details.details_requested.connect(self._show_conflicts)
        self.details.toggled.connect(self.toggle)
        self.details.close_requested.connect(self._close_details)
        self.view.selectionModel().currentChanged.connect(self._current_changed)

    def set_category_filter(self, tag: str | None, subtag: str | None = None) -> None:
        self.proxy.set_category_filter(tag, subtag)
        if tag is None:
            self._chip_widget.setVisible(False)
        else:
            label = tag if tag != UNCATEGORIZED_TAG else "Uncategorized"
            if subtag is not None:
                label = f"Category: {label} › {subtag}"
            else:
                label = f"Category: {label}"
            self._chip_label.setText(label)
            self._chip_widget.setVisible(True)
        self.category_filter_changed.emit(tag, subtag)

    def category_filter(self) -> tuple[str | None, str | None]:
        return self.proxy._filter_tag, self.proxy._filter_subtag

    def _apply_sort(self) -> None:
        role = _SORTS[self.sort_combo.currentIndex()][1]
        self.proxy.setSortRole(role)
        order = (
            Qt.SortOrder.DescendingOrder
            if self.sort_dir.isChecked()
            else Qt.SortOrder.AscendingOrder
        )
        self.proxy.sort(0, order)
        self.sort_dir.setText("↓" if self.sort_dir.isChecked() else "↑")

    def _current_meta(self) -> ModMeta | None:
        index = self.view.currentIndex()
        if not index.isValid():
            return None
        return self.model.meta_at(self.proxy.mapToSource(index).row())

    def set_custom_tags(self, assignments: dict[str, list[str]]) -> None:
        self._custom_tags = {rel: list(tags) for rel, tags in assignments.items() if tags}
        self.model.set_custom_tags(assignments)
        self._refresh_details()
        self._update_highlight()

    def set_groups(
        self, assignments: dict[str, list[str]], registry: list[tuple[str, str]]
    ) -> None:
        self._group_assignments = {rel: list(ids) for rel, ids in assignments.items() if ids}
        self._group_registry = dict(registry)
        self.details.set_groups(registry)
        self._refresh_details()

    def set_random_groups(
        self, assignments: dict[str, list[str]], registry: list[tuple[str, str]]
    ) -> None:
        self._random_assignments = {
            rel: list(ids) for rel, ids in assignments.items() if ids
        }
        self.details.set_random_groups(registry)
        self._refresh_details()

    def _current_changed(self, current, _previous) -> None:
        if not current.isValid():
            self.details.setVisible(False)
            self._update_highlight()
            return
        meta = self._current_meta()
        if meta is None:
            self.details.setVisible(False)
        else:
            self._refresh_details()
            self.details.setVisible(True)
        self._update_highlight()

    def _refresh_details(self) -> None:
        meta = self._current_meta()
        if meta is None:
            return
        self.details.set_context(
            meta,
            self.model.enabled_map().get(meta.rel_path, False),
            self._conflicts.for_mod(meta.rel_path),
            self._lookup,
            custom_tags=list(self._custom_tags.get(meta.rel_path, [])),
            group_ids=list(self._group_assignments.get(meta.rel_path, [])),
            random_ids=list(self._random_assignments.get(meta.rel_path, [])),
        )

    def toggle(self, rel_path: str, enabled: bool) -> None:
        row = self.model.row_for(rel_path)
        if row < 0:
            return
        state = Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        self.model.setData(self.model.index(row), state, Qt.ItemDataRole.CheckStateRole)

    def _close_details(self) -> None:
        self.details.setVisible(False)
        self.view.selectionModel().clearSelection()
        self.view.selectionModel().clearCurrentIndex()

    def apply_new_order(self, order: list[str]) -> None:
        self.model.set_order(order)
        self._refresh_details()
        self._update_highlight()

    def _on_toggled(self, rel_path: str, enabled: bool) -> None:
        self._refresh_details()
        self._update_highlight()

    def _update_highlight(self) -> None:
        meta = self._current_meta()
        if meta is None:
            self.delegate.set_highlight(set())
        else:
            self.delegate.set_highlight(
                {c.other for c in self._conflicts.for_mod(meta.rel_path) if c.active}
            )
        self.view.viewport().update()

    def jump_to(self, rel_path: str) -> None:
        row = self.model.row_for(rel_path)
        if row < 0:
            return
        index = self.proxy.mapFromSource(self.model.index(row))
        if index.isValid():
            self.view.setCurrentIndex(index)
            self.view.scrollTo(index)

    def _show_conflicts(self) -> None:
        meta = self._current_meta()
        if meta is None:
            return
        if not self._conflicts.partners(meta.rel_path):
            return
        dlg = ConflictDialog(meta, self._conflicts.for_mod(meta.rel_path), self._lookup, self)
        dlg.exec()
