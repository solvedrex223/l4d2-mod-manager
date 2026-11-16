from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..vpk_meta import ModMeta

_CARD_STYLE = (
    "QFrame#GroupCard { background: #33373d; border-radius: 8px;"
    "border: 1px solid #4a4f57; }"
)
_GRAY = "#9aa0aa"


class MemberRow(QWidget):
    def __init__(
        self,
        meta: ModMeta,
        group_id: str,
        thumb: QPixmap | None,
        on_remove: Callable[[str, str], None],
        on_select: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        thumb_label = QLabel()
        if thumb is not None:
            thumb_label.setPixmap(thumb)
        thumb_label.setFixedSize(52, 30)
        row.addWidget(thumb_label)

        name_btn = QPushButton(meta.title)
        name_btn.setToolTip(meta.rel_path)
        name_btn.setFlat(True)
        name_btn.setStyleSheet("text-align: left;")
        name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        name_btn.clicked.connect(lambda: on_select(meta.rel_path))
        row.addWidget(name_btn, 1)

        remove_btn = QToolButton()
        remove_btn.setText("×")
        remove_btn.setToolTip("Remove from group")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: on_remove(group_id, meta.rel_path))
        row.addWidget(remove_btn)


class GroupCard(QFrame):
    def __init__(
        self,
        group_id: str,
        name: str,
        members: list[ModMeta],
        all_enabled: bool,
        thumbs: dict[str, QPixmap],
        on_toggle_all: Callable[[str, bool], None],
        on_rename: Callable[[str], None],
        on_delete: Callable[[str], None],
        on_remove_member: Callable[[str, str], None],
        on_select_mod: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.group_id = group_id
        self.setObjectName("GroupCard")
        self.setStyleSheet(_CARD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.arrow = QToolButton()
        self.arrow.setCheckable(True)
        self.arrow.setChecked(True)
        self.arrow.setArrowType(Qt.ArrowType.DownArrow)
        header.addWidget(self.arrow)

        self.name_label = QLabel(f"{name}  ({len(members)})")
        self.name_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.name_label)
        header.addStretch(1)

        self.toggle_btn = QPushButton(
            "Disable all" if all_enabled else "Enable all"
        )
        self.toggle_btn.clicked.connect(
            lambda: on_toggle_all(group_id, not all_enabled)
        )
        header.addWidget(self.toggle_btn)

        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(lambda: on_rename(group_id))
        header.addWidget(rename_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: on_delete(group_id))
        header.addWidget(delete_btn)
        layout.addLayout(header)

        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 0, 0, 0)
        body_layout.setSpacing(4)
        for meta in members:
            body_layout.addWidget(
                MemberRow(
                    meta, group_id, thumbs.get(meta.rel_path),
                    on_remove_member, on_select_mod,
                )
            )
        layout.addWidget(self.body)

        self.arrow.toggled.connect(self._arrow_toggled)

    def _arrow_toggled(self, checked: bool) -> None:
        self.body.setVisible(checked)
        self.arrow.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def set_expanded(self, expanded: bool) -> None:
        if self.arrow.isChecked() != expanded:
            self.arrow.setChecked(expanded)

    def is_expanded(self) -> bool:
        return self.arrow.isChecked()


class GroupsTab(QWidget):
    new_group_requested = Signal()
    group_rename_requested = Signal(str)
    group_delete_requested = Signal(str)
    group_toggle_requested = Signal(str, bool)
    member_remove_requested = Signal(str, str)
    mod_selected = Signal(str)

    def __init__(self, metas: list[ModMeta], parent=None) -> None:
        super().__init__(parent)
        self._lookup = {m.rel_path: m for m in metas}
        self._thumbs: dict[str, QPixmap] = {}
        for meta in metas:
            if meta.thumbnail is None:
                continue
            pix = QPixmap(str(meta.thumbnail))
            if not pix.isNull():
                self._thumbs[meta.rel_path] = pix.scaled(
                    52, 30,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        self._assignments: dict[str, list[str]] = {}
        self._groups: dict[str, dict] = {}
        self._enabled_map: dict[str, bool] = {}
        self._collapsed: set[str] = set()
        self._cards: dict[str, GroupCard] = {}

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search groups or mods…")
        new_btn = QPushButton("New group")
        new_btn.clicked.connect(self.new_group_requested.emit)
        self.expand_btn = QPushButton("Collapse all")
        self.expand_btn.clicked.connect(self._toggle_expand_all)
        top.addWidget(self.search, 1)
        top.addWidget(new_btn)
        top.addWidget(self.expand_btn)
        layout.addLayout(top)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 4, 0, 0)
        self._content_layout.setSpacing(10)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        self._empty = QLabel("No groups yet — create one here or from a mod's details panel.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color: {_GRAY};")
        layout.addWidget(self._empty)

        self._no_match = QLabel("No groups match the search.")
        self._no_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_match.setStyleSheet(f"color: {_GRAY};")
        self._no_match.setVisible(False)
        layout.addWidget(self._no_match)

        self.search.textChanged.connect(lambda _: self.refresh())

    def _toggle_expand_all(self) -> None:
        if self._collapsed:
            self._collapsed.clear()
        else:
            self._collapsed = set(self._groups)
        for group_id, card in self._cards.items():
            card.set_expanded(group_id not in self._collapsed)
        self.expand_btn.setText(
            "Expand all" if self._collapsed else "Collapse all"
        )

    def refresh(
        self,
        assignments: dict[str, list[str]] | None = None,
        groups: dict[str, dict] | None = None,
        enabled_map: dict[str, bool] | None = None,
    ) -> None:
        if assignments is not None:
            self._assignments = {rel: list(ids) for rel, ids in assignments.items() if ids}
        if groups is not None:
            self._groups = dict(groups)
        if enabled_map is not None:
            self._enabled_map = dict(enabled_map)

        self._collapsed = {gid for gid in self._collapsed if gid in self._groups}
        self.expand_btn.setText(
            "Expand all" if self._collapsed else "Collapse all"
        )

        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards = {}

        if not self._groups:
            self._empty.setVisible(True)
            self._no_match.setVisible(False)
            self._scroll.setVisible(False)
            return
        self._empty.setVisible(False)
        self._scroll.setVisible(True)

        needle = self.search.text().strip().lower()
        matched = 0
        for group_id in sorted(self._groups, key=lambda gid: self._groups[gid].get("name", "")):
            name = self._groups[group_id].get("name", "")
            members = self._members_of(group_id)
            if needle:
                name_hit = needle in name.lower()
                member_hit = any(
                    needle in m.title.lower() or needle in m.filename.lower()
                    for m in members
                )
                if not name_hit and not member_hit:
                    continue
            matched += 1
            all_enabled = bool(members) and all(
                self._enabled_map.get(m.rel_path) for m in members
            )
            card = GroupCard(
                group_id,
                name,
                members,
                all_enabled,
                self._thumbs,
                self.group_toggle_requested.emit,
                self.group_rename_requested.emit,
                self.group_delete_requested.emit,
                self.member_remove_requested.emit,
                self.mod_selected.emit,
            )
            if group_id in self._collapsed:
                card.set_expanded(False)
            self._cards[group_id] = card
            self._content_layout.insertWidget(
                self._content_layout.count() - 1, card
            )

        self._no_match.setVisible(matched == 0)

    def _members_of(self, group_id: str) -> list[ModMeta]:
        metas = [
            self._lookup[rel]
            for rel, ids in self._assignments.items()
            if group_id in ids and rel in self._lookup
        ]
        return sorted(metas, key=lambda m: m.title.lower())
