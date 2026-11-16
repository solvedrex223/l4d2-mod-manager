from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..conflicts import ConflictGroup, ConflictIndex
from ..vpk_meta import ModMeta

_CARD_STYLE = (
    "QFrame#GroupCard { background: #33373d; border-radius: 8px;"
    "border: 1px solid #4a4f57; }"
)
_GREEN = "#4caf50"
_RED = "#e05555"
_GRAY = "#9aa0aa"


class GroupCard(QFrame):
    def __init__(
        self,
        group: ConflictGroup,
        index: ConflictIndex,
        lookup: dict[str, ModMeta],
        thumbs: dict[str, QPixmap],
        toggle_requested,
        make_winner_requested,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GroupCard")
        self.setStyleSheet(_CARD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(f"{len(group.mods)} mods · {len(group.shared)} shared files")
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)
        disclosure = QToolButton()
        disclosure.setText("Shared files")
        disclosure.setCheckable(True)
        disclosure.setArrowType(Qt.ArrowType.RightArrow)
        header.addWidget(disclosure)
        layout.addLayout(header)

        files_list = QListWidget()
        files_list.setMaximumHeight(160)
        files_list.setVisible(False)
        for path in group.shared:
            QListWidgetItem(path, files_list)
        layout.addWidget(files_list)

        def _toggle_disclosure(checked: bool) -> None:
            files_list.setVisible(checked)
            disclosure.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            )

        disclosure.toggled.connect(_toggle_disclosure)

        for rank, rel in enumerate(group.mods, start=1):
            layout.addWidget(
                self._mod_row(
                    rel, rank, group, index, lookup, thumbs,
                    toggle_requested, make_winner_requested,
                )
            )

    def _mod_row(
        self,
        rel: str,
        rank: int,
        group: ConflictGroup,
        index: ConflictIndex,
        lookup: dict[str, ModMeta],
        thumbs: dict[str, QPixmap],
        toggle_requested,
        make_winner_requested,
    ) -> QWidget:
        meta = lookup.get(rel)
        title = meta.title if meta else rel
        enabled = index.enabled_map().get(rel, False)
        stats = index.mod_stats(rel)

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        rank_label = QLabel(f"#{rank}")
        rank_label.setFixedWidth(26)
        rank_label.setStyleSheet(f"color: {_GRAY};")
        h.addWidget(rank_label)

        thumb_label = QLabel()
        pix = thumbs.get(rel)
        if pix is not None:
            thumb_label.setPixmap(pix)
        thumb_label.setFixedSize(52, 30)
        h.addWidget(thumb_label)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name_label = QLabel(title)
        name_label.setToolTip(rel)
        verdict = QLabel()
        if stats.lost == 0:
            verdict.setText(f"Wins all {stats.contested} contested files")
            verdict.setStyleSheet(f"font-size: 11px; color: {_GREEN};")
        elif stats.lost == stats.contested:
            verdict.setText(f"Loses all {stats.contested} contested files")
            verdict.setStyleSheet(f"font-size: 11px; color: {_RED};")
        else:
            verdict.setText(
                f"Loses {stats.lost}, wins {stats.contested - stats.lost} of {stats.contested}"
            )
            verdict.setStyleSheet(f"font-size: 11px; color: {_RED};")
        name_col.addWidget(name_label)
        name_col.addWidget(verdict)
        h.addLayout(name_col, 1)

        toggle_btn = QPushButton("Disable" if enabled else "Enable")
        toggle_btn.clicked.connect(
            lambda: toggle_requested.emit(rel, not enabled)
        )
        h.addWidget(toggle_btn)

        winner_btn = QPushButton("Make winner")
        if rank == 1:
            winner_btn.setEnabled(False)
            winner_btn.setToolTip("Already the highest-priority mod in this group")
        else:
            winner_btn.setToolTip("Move this mod above the group's top mod in load order")
            winner_btn.clicked.connect(
                lambda: make_winner_requested.emit(rel, list(group.mods))
            )
        h.addWidget(winner_btn)
        return row


class ConflictsTab(QWidget):
    toggle_requested = Signal(str, bool)
    make_winner_requested = Signal(str, list)
    has_conflicts_changed = Signal(bool)

    def __init__(
        self,
        metas: list[ModMeta],
        conflicts: ConflictIndex,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conflicts = conflicts
        self._lookup = {m.rel_path: m for m in metas}
        self._thumbs: dict[str, QPixmap] = {}
        self._has_groups = False
        for meta in metas:
            if meta.thumbnail is None:
                continue
            pix = QPixmap(str(meta.thumbnail))
            if not pix.isNull():
                self._thumbs[meta.rel_path] = pix.scaled(
                    52,
                    30,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        outer = QVBoxLayout(self)
        self._summary = QLabel()
        self._summary.setStyleSheet("font-weight: bold;")
        outer.addWidget(self._summary)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 4, 0, 0)
        self._content_layout.setSpacing(10)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

        self._empty = QLabel("No active conflicts. All clear.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color: {_GREEN}; font-size: 14px;")
        outer.addWidget(self._empty)

        self.refresh()

    @property
    def has_conflicts(self) -> bool:
        return self._has_groups

    def refresh(self) -> None:
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        groups = self._conflicts.groups()
        if not groups:
            self._empty.setVisible(True)
            self._scroll.setVisible(False)
            self._summary.setText("Conflicts")
        else:
            self._empty.setVisible(False)
            self._scroll.setVisible(True)
            self._summary.setText(
                f"{len(groups)} active conflict "
                f"{'group' if len(groups) == 1 else 'groups'}"
            )
            for group in groups:
                card = GroupCard(
                    group,
                    self._conflicts,
                    self._lookup,
                    self._thumbs,
                    self.toggle_requested,
                    self.make_winner_requested,
                )
                self._content_layout.insertWidget(self._content_layout.count() - 1, card)

        if bool(groups) != self._has_groups:
            self._has_groups = bool(groups)
            self.has_conflicts_changed.emit(self._has_groups)
