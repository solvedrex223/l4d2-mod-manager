from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QPixmap

from ..categories import categories_for
from ..conflicts import ConflictIndex
from ..vpk_meta import ModMeta

ThumbnailRole = int(Qt.ItemDataRole.UserRole) + 1
MetaRole = ThumbnailRole + 1
NameSortRole = ThumbnailRole + 2
AuthorSortRole = ThumbnailRole + 3
CategorySortRole = ThumbnailRole + 4
SizeSortRole = ThumbnailRole + 5
ConflictsSortRole = ThumbnailRole + 6
EnabledSortRole = ThumbnailRole + 7
ActiveConflictsRole = ThumbnailRole + 8
PotentialConflictsRole = ThumbnailRole + 9
CustomTagsRole = ThumbnailRole + 10


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


class ModsModel(QAbstractListModel):
    toggled = Signal(str, bool)

    def __init__(
        self,
        metas: list[ModMeta],
        enabled_map: dict[str, bool],
        order: list[str],
        conflicts: ConflictIndex,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._metas = list(metas)
        self._enabled = dict(enabled_map)
        self._order = list(order)
        self._conflicts = conflicts
        self._conflicts.set_state(self._enabled, self._order)
        self._rows = {meta.rel_path: row for row, meta in enumerate(self._metas)}
        self._pixmaps: dict[str, QPixmap] = {}
        self._broken_thumbs: set[str] = set()
        self._custom_tags: dict[str, list[str]] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._metas)

    def meta_at(self, row: int) -> ModMeta:
        return self._metas[row]

    def row_for(self, rel_path: str) -> int:
        return self._rows.get(rel_path, -1)

    def enabled_map(self) -> dict[str, bool]:
        return dict(self._enabled)

    def custom_tags_for(self, rel_path: str) -> list[str]:
        return list(self._custom_tags.get(rel_path, ()))

    def set_custom_tags(self, assignments: dict[str, list[str]]) -> None:
        self._custom_tags = {rel: list(tags) for rel, tags in assignments.items() if tags}
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._metas) - 1, 0))

    def set_order(self, order: list[str]) -> None:
        self._order = list(order)
        self._conflicts.set_state(self._enabled, self._order)
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._metas) - 1, 0))

    def _thumb(self, meta: ModMeta) -> QPixmap | None:
        if meta.rel_path in self._broken_thumbs or meta.thumbnail is None:
            return None
        cached = self._pixmaps.get(meta.rel_path)
        if cached is not None:
            return cached
        pix = QPixmap(str(meta.thumbnail))
        if pix.isNull():
            self._broken_thumbs.add(meta.rel_path)
            return None
        pix = pix.scaled(
            192,
            108,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmaps[meta.rel_path] = pix
        return pix

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        meta = self._metas[index.row()]

        if role in (MetaRole,):
            return meta
        if role == Qt.ItemDataRole.DisplayRole:
            return meta.title
        if role in (ThumbnailRole, Qt.ItemDataRole.DecorationRole):
            return self._thumb(meta)
        if role == Qt.ItemDataRole.CheckStateRole:
            return (
                Qt.CheckState.Checked
                if self._enabled.get(meta.rel_path)
                else Qt.CheckState.Unchecked
            )
        if role == Qt.ItemDataRole.ToolTipRole:
            parts = [meta.title, meta.rel_path]
            if meta.parse_error:
                parts.append(f"Parse error: {meta.parse_error}")
            return "\n".join(parts)
        if role == NameSortRole:
            return meta.title.lower()
        if role == AuthorSortRole:
            return (meta.author or "").lower()
        if role == CategorySortRole:
            return ", ".join(categories_for(meta.content_flags))
        if role == SizeSortRole:
            return meta.size
        if role == ConflictsSortRole:
            active = self._conflicts.active_count(meta.rel_path)
            potential = self._conflicts.potential_count(meta.rel_path)
            return active * 1000 + potential
        if role == EnabledSortRole:
            return 1 if self._enabled.get(meta.rel_path) else 0
        if role == ActiveConflictsRole:
            return self._conflicts.active_count(meta.rel_path)
        if role == PotentialConflictsRole:
            return self._conflicts.potential_count(meta.rel_path)
        if role == CustomTagsRole:
            return self.custom_tags_for(meta.rel_path)
        return None

    def flags(self, index):
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.CheckStateRole or not index.isValid():
            return False
        state = Qt.CheckState(value) if isinstance(value, int) else value
        meta = self._metas[index.row()]
        enabled = state == Qt.CheckState.Checked
        if enabled == self._enabled.get(meta.rel_path):
            return False
        self._enabled[meta.rel_path] = enabled
        self._conflicts.set_state(self._enabled, self._order)
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._metas) - 1, 0))
        self.toggled.emit(meta.rel_path, enabled)
        return True
