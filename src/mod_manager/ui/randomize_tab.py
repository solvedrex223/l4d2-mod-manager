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

from ..randomizer import RollPick
from ..vpk_meta import ModMeta

_CARD_STYLE = (
    "QFrame#RGroupCard { background: #33373d; border-radius: 8px;"
    "border: 1px solid #4a4f57; }"
)
_GRAY = "#9aa0aa"
_GREEN = "#4caf50"


class RandomMemberRow(QWidget):
    def __init__(
        self,
        kind: str,
        ref: str,
        label: str,
        tooltip: str,
        thumb: QPixmap | None,
        picked: bool,
        rg_id: str,
        on_remove: Callable[[str, str, str], None],
        on_select: Callable[[str, str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        if thumb is not None:
            thumb_label = QLabel()
            thumb_label.setPixmap(thumb)
            thumb_label.setFixedSize(52, 30)
            row.addWidget(thumb_label)

        name_btn = QPushButton(label)
        name_btn.setToolTip(tooltip)
        name_btn.setFlat(True)
        name_btn.setStyleSheet("text-align: left;")
        name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if picked:
            name_btn.setStyleSheet("text-align: left; color: #4caf50; font-weight: bold;")
        name_btn.clicked.connect(lambda: on_select(kind, ref))
        row.addWidget(name_btn, 1)

        if picked:
            tag = QLabel("picked")
            tag.setStyleSheet(f"color: {_GREEN}; font-size: 10px;")
            row.addWidget(tag)

        remove_btn = QToolButton()
        remove_btn.setText("×")
        remove_btn.setToolTip("Remove from random group")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: on_remove(rg_id, kind, ref))
        row.addWidget(remove_btn)


class RGroupCard(QFrame):
    def __init__(
        self,
        rg_id: str,
        name: str,
        member_rows: list[tuple],
        pick: RollPick | None,
        pick_label: str | None,
        on_add_member: Callable[[str], None],
        on_rename: Callable[[str], None],
        on_delete: Callable[[str], None],
        on_remove_member: Callable[[str, str, str], None],
        on_select: Callable[[str, str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.rg_id = rg_id
        self.setObjectName("RGroupCard")
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

        self.name_label = QLabel(f"{name}  ({len(member_rows)})")
        self.name_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.name_label)

        if pick is not None and pick_label:
            badge = QLabel(f"→ {pick_label}")
            badge.setStyleSheet(f"color: {_GREEN}; font-size: 11px;")
            header.addWidget(badge)
        header.addStretch(1)

        add_btn = QPushButton("Add member…")
        add_btn.clicked.connect(lambda: on_add_member(rg_id))
        header.addWidget(add_btn)
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(lambda: on_rename(rg_id))
        header.addWidget(rename_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: on_delete(rg_id))
        header.addWidget(delete_btn)
        layout.addLayout(header)

        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 0, 0, 0)
        body_layout.setSpacing(4)
        for row_args in member_rows:
            body_layout.addWidget(RandomMemberRow(*row_args))
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


class RandomizeTab(QWidget):
    new_random_group_requested = Signal()
    random_rename_requested = Signal(str)
    random_delete_requested = Signal(str)
    add_member_requested = Signal(str)
    member_remove_requested = Signal(str, str, str)
    member_selected = Signal(str, str)
    randomize_requested = Signal(bool)

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
        self._random_groups: dict[str, dict] = {}
        self._group_names: dict[str, str] = {}
        self._group_membership: dict[str, list[str]] = {}
        self._enabled_map: dict[str, bool] = {}
        self._picks: dict[str, RollPick] = {}
        self._collapsed: set[str] = set()
        self._cards: dict[str, RGroupCard] = {}

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search random groups or mods…")
        new_btn = QPushButton("New random group")
        new_btn.clicked.connect(self.new_random_group_requested.emit)
        self.expand_btn = QPushButton("Collapse all")
        self.expand_btn.clicked.connect(self._toggle_expand_all)
        self.dry_btn = QPushButton("Randomize")
        self.dry_btn.setToolTip("Roll all random groups now (without starting the game)")
        self.dry_btn.clicked.connect(lambda: self.randomize_requested.emit(False))
        self.start_btn = QPushButton("▶ Start L4D2")
        self.start_btn.setToolTip("Roll all random groups and launch the game")
        self.start_btn.setStyleSheet(
            "QPushButton { background: #3d8f5f; color: white; font-weight: bold;"
            "border-radius: 4px; padding: 5px 14px; }"
        )
        self.start_btn.clicked.connect(lambda: self.randomize_requested.emit(True))
        top.addWidget(self.search, 1)
        top.addWidget(new_btn)
        top.addWidget(self.expand_btn)
        top.addWidget(self.dry_btn)
        top.addWidget(self.start_btn)
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

        self._empty = QLabel(
            "No random groups yet — each one rolls exactly one of its members on Start."
        )
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color: {_GRAY};")
        layout.addWidget(self._empty)

        self._no_match = QLabel("No random groups match the search.")
        self._no_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_match.setStyleSheet(f"color: {_GRAY};")
        self._no_match.setVisible(False)
        layout.addWidget(self._no_match)

        self.search.textChanged.connect(lambda _: self.refresh())

    def _toggle_expand_all(self) -> None:
        if self._collapsed:
            self._collapsed.clear()
        else:
            self._collapsed = set(self._random_groups)
        for rg_id, card in self._cards.items():
            card.set_expanded(rg_id not in self._collapsed)
        self.expand_btn.setText(
            "Expand all" if self._collapsed else "Collapse all"
        )

    def set_picks(self, picks: dict[str, RollPick]) -> None:
        self._picks = dict(picks or {})

    def refresh(
        self,
        random_groups: dict[str, dict] | None = None,
        group_names: dict[str, str] | None = None,
        group_membership: dict[str, list[str]] | None = None,
        enabled_map: dict[str, bool] | None = None,
    ) -> None:
        if random_groups is not None:
            self._random_groups = dict(random_groups)
        if group_names is not None:
            self._group_names = dict(group_names)
        if group_membership is not None:
            self._group_membership = dict(group_membership)
        if enabled_map is not None:
            self._enabled_map = dict(enabled_map)

        self._collapsed = {rid for rid in self._collapsed if rid in self._random_groups}
        self.expand_btn.setText(
            "Expand all" if self._collapsed else "Collapse all"
        )

        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards = {}

        if not self._random_groups:
            self._empty.setVisible(True)
            self._no_match.setVisible(False)
            self._scroll.setVisible(False)
            return
        self._empty.setVisible(False)
        self._scroll.setVisible(True)

        needle = self.search.text().strip().lower()
        matched = 0
        for rg_id in sorted(
            self._random_groups,
            key=lambda rid: self._random_groups[rid].get("name", ""),
        ):
            rg = self._random_groups[rg_id]
            name = rg.get("name", "")
            member_rows, labels = self._build_member_rows(rg_id, rg)
            if needle:
                name_hit = needle in name.lower()
                member_hit = any(
                    needle in label.lower() for label in labels
                )
                if not name_hit and not member_hit:
                    continue
            matched += 1
            pick = self._picks.get(rg_id)
            pick_label = None
            if pick is not None:
                pick_label = self._member_label(pick.kind, pick.ref)
            card = RGroupCard(
                rg_id,
                name,
                member_rows,
                pick,
                pick_label,
                self.add_member_requested.emit,
                self.random_rename_requested.emit,
                self.random_delete_requested.emit,
                self.member_remove_requested.emit,
                self.member_selected.emit,
            )
            if rg_id in self._collapsed:
                card.set_expanded(False)
            self._cards[rg_id] = card
            self._content_layout.insertWidget(
                self._content_layout.count() - 1, card
            )

        self._no_match.setVisible(matched == 0)

    def _member_label(self, kind: str, ref: str) -> str:
        if kind == "group":
            name = self._group_names.get(ref)
            if name is None:
                return f"missing group {ref}"
            return f"Group: {name} ({len(self._group_membership.get(ref, []))} mods)"
        meta = self._lookup.get(ref)
        if meta is None:
            return f"missing mod {ref}"
        return meta.title

    def _build_member_rows(self, rg_id: str, rg: dict) -> tuple[list[tuple], list[str]]:
        pick = self._picks.get(rg_id)
        rows: list[tuple] = []
        labels: list[str] = []
        for member in rg.get("members", []):
            kind = member.get("kind", "mod")
            ref = member.get("ref", "")
            label = self._member_label(kind, ref)
            labels.append(label)
            picked = (
                pick is not None and pick.kind == kind and pick.ref == ref
            )
            if kind == "group":
                thumb = None
                tooltip = ref
            else:
                meta = self._lookup.get(ref)
                thumb = self._thumbs.get(ref) if meta else None
                tooltip = ref
            rows.append(
                (
                    kind,
                    ref,
                    label,
                    tooltip,
                    thumb,
                    picked,
                    rg_id,
                    self.member_remove_requested.emit,
                    self.member_selected.emit,
                )
            )
        return rows, labels
