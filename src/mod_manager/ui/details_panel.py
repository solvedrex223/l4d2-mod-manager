from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..categories import categories_for
from ..conflicts import Conflict
from ..vpk_meta import ModMeta
from .flow_layout import FlowLayout
from .mods_model import human_size

_CHIP_STYLE = (
    "background: #3d6a8f; color: white; border-radius: 5px;"
    "padding: 1px 7px; font-size: 11px;"
)
_CUSTOM_CHIP_STYLE = (
    "background: #7a5c9e; color: white; border-radius: 5px;"
    "padding: 1px 7px; font-size: 11px;"
)
_GROUP_CHIP_STYLE = (
    "background: #3d8f5f; color: white; border-radius: 5px;"
    "padding: 1px 7px; font-size: 11px;"
)

_ZWSP = "\u200b"
_SOFT_BREAK_AFTER = 24


def soften_text(text: str | None) -> str | None:
    if not text:
        return text
    out = []
    for token in text.split(" "):
        while len(token) > _SOFT_BREAK_AFTER:
            out.append(token[:_SOFT_BREAK_AFTER] + _ZWSP)
            token = token[_SOFT_BREAK_AFTER:]
        out.append(token)
    return " ".join(out)
_HEADER_STYLE = "color: #9aa0aa; font-size: 11px; font-weight: bold;"
_LINK_STYLE = "color: #6fb3e0;"


class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(_HEADER_STYLE)


class DetailsPanel(QWidget):
    toggled = Signal(str, bool)
    conflict_selected = Signal(str)
    details_requested = Signal()
    close_requested = Signal()
    tags_changed = Signal(str, list)
    new_category_requested = Signal()
    groups_changed = Signal(str, list)
    new_group_requested = Signal()
    random_groups_changed = Signal(str, list)
    new_random_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        self._meta: ModMeta | None = None
        self._lookup: dict[str, ModMeta] = {}
        self._conflicts: list[Conflict] = []
        self._custom_tags: list[str] = []
        self._custom_categories: list[str] = []
        self._group_ids: list[str] = []
        self._groups: dict[str, str] = {}
        self._random_ids: list[str] = []
        self._random_registry: dict[str, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header_label = QLabel("Mod details")
        header_label.setStyleSheet("font-weight: bold; padding: 2px;")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setFlat(True)
        close_btn.setToolTip("Close details")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(header_label)
        header.addStretch(1)
        header.addWidget(close_btn)
        header_container = QWidget()
        header_container.setLayout(header)
        header_container.setStyleSheet("background: #2c3038;")
        outer.addWidget(header_container)

        self._empty = QLabel("Select a mod to see its details.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet("color: #9aa0aa;")
        outer.addWidget(self._empty)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._thumb_pixmap: QPixmap | None = None
        layout.addWidget(self.thumb)

        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.title)

        self.title_note = QLabel("Title from Steam Workshop")
        self.title_note.setStyleSheet("color: #7f96a8; font-size: 10px;")
        self.title_note.setVisible(False)
        layout.addWidget(self.title_note)

        self.author = QLabel()
        self.author.setWordWrap(True)
        self.author.setStyleSheet("color: #9aa0aa;")
        layout.addWidget(self.author)

        self.chips_container = QWidget()
        self.chips = FlowLayout(self.chips_container, spacing=4)
        self.chips.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chips_container)

        self.add_category_btn = QPushButton("Add Category")
        self.add_category_btn.setToolTip("Assign custom categories to this mod")
        self.add_category_btn.setVisible(False)
        self.add_group_btn = QPushButton("Add to Group")
        self.add_group_btn.setToolTip("Add this mod to a group")
        self.add_group_btn.setVisible(False)
        self.add_random_btn = QPushButton("Add to Random")
        self.add_random_btn.setToolTip("Add this mod to a random group")
        self.add_random_btn.setVisible(False)
        buttons_row = QWidget()
        buttons_layout = FlowLayout(buttons_row, spacing=4)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        for btn in (self.add_category_btn, self.add_group_btn, self.add_random_btn):
            buttons_layout.addWidget(btn)
        layout.addWidget(buttons_row)

        self.tagline = QLabel()
        self.tagline.setWordWrap(True)
        self.tagline.setStyleSheet("color: #b8bec8; font-style: italic;")
        layout.addWidget(self.tagline)

        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.description)

        facts = QFormLayout()
        facts.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.f_filename = QLabel()
        self.f_filename.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.f_filename.setWordWrap(True)
        self.f_source = QLabel()
        self.f_source.setWordWrap(True)
        self.f_size = QLabel()
        self.f_files = QLabel()
        facts.addRow("File", self.f_filename)
        facts.addRow("Source", self.f_source)
        facts.addRow("Size", self.f_size)
        facts.addRow("Contains", self.f_files)
        layout.addLayout(facts)

        self.workshop_btn = QPushButton("Open Workshop page")
        self.workshop_btn.setStyleSheet("color: #6fb3e0;")
        self.workshop_btn.setVisible(False)
        layout.addWidget(self.workshop_btn)

        self.enabled_cb = QCheckBox("Enabled")
        layout.addWidget(self.enabled_cb)

        layout.addWidget(SectionHeader("ACTIVE CONFLICTS"))
        self.active_list = QLabel()
        self.active_list.setWordWrap(True)
        self.active_list.setTextFormat(Qt.TextFormat.RichText)
        self.active_list.linkActivated.connect(self.conflict_selected.emit)
        layout.addWidget(self.active_list)

        self.potential_header = SectionHeader("POTENTIAL CONFLICTS")
        self.potential_header.setVisible(False)
        layout.addWidget(self.potential_header)
        self.potential_list = QLabel()
        self.potential_list.setWordWrap(True)
        self.potential_list.setTextFormat(Qt.TextFormat.RichText)
        self.potential_list.linkActivated.connect(self.conflict_selected.emit)
        self.potential_list.setVisible(False)
        layout.addWidget(self.potential_list)

        self.conflicts_btn = QPushButton("View conflict details…")
        self.conflicts_btn.setVisible(False)
        layout.addWidget(self.conflicts_btn)

        self.files_header = SectionHeader("FILES")
        self.files_header.setVisible(False)
        layout.addWidget(self.files_header)
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderHidden(True)
        self.files_tree.setMaximumHeight(280)
        self.files_tree.setVisible(False)
        layout.addWidget(self.files_tree)

        layout.addStretch(1)
        self._scroll.setWidget(content)
        self._scroll.setVisible(False)
        outer.addWidget(self._scroll)

        self.enabled_cb.toggled.connect(self._on_enabled_toggled)
        self.workshop_btn.clicked.connect(self._open_workshop)
        self.conflicts_btn.clicked.connect(self.details_requested.emit)
        close_btn.clicked.connect(self.close_requested.emit)
        self.add_category_btn.clicked.connect(self._open_category_picker)
        self.add_group_btn.clicked.connect(self._open_group_picker)
        self.add_random_btn.clicked.connect(self._open_random_picker)

    def set_custom_categories(self, names: list[str]) -> None:
        self._custom_categories = list(names)

    def set_groups(self, registry: list[tuple[str, str]]) -> None:
        self._groups = dict(registry)

    def set_random_groups(self, registry: list[tuple[str, str]]) -> None:
        self._random_registry = dict(registry)

    def _open_random_picker(self) -> None:
        if self._meta is None:
            return
        menu = QMenu(self)
        for rg_id, name in self._random_registry.items():
            action = menu.addAction(name)
            action.setData(rg_id)
            action.setCheckable(True)
            action.setChecked(rg_id in self._random_ids)
        menu.addSeparator()
        new_action = menu.addAction("New random group…")
        chosen = menu.exec(
            self.add_random_btn.mapToGlobal(self.add_random_btn.rect().bottomLeft())
        )
        if chosen is None:
            return
        if chosen is new_action:
            self.new_random_requested.emit()
            return
        rg_id = chosen.data()
        ids = list(self._random_ids)
        if chosen.isChecked():
            if rg_id not in ids:
                ids.append(rg_id)
        elif rg_id in ids:
            ids.remove(rg_id)
        self.random_groups_changed.emit(self._meta.rel_path, ids)

    def _open_group_picker(self) -> None:
        if self._meta is None:
            return
        menu = QMenu(self)
        for group_id, name in self._groups.items():
            action = menu.addAction(name)
            action.setData(group_id)
            action.setCheckable(True)
            action.setChecked(group_id in self._group_ids)
        menu.addSeparator()
        new_action = menu.addAction("New group…")
        chosen = menu.exec(
            self.add_group_btn.mapToGlobal(self.add_group_btn.rect().bottomLeft())
        )
        if chosen is None:
            return
        if chosen is new_action:
            self.new_group_requested.emit()
            return
        group_id = chosen.data()
        ids = list(self._group_ids)
        if chosen.isChecked():
            if group_id not in ids:
                ids.append(group_id)
        elif group_id in ids:
            ids.remove(group_id)
        self.groups_changed.emit(self._meta.rel_path, ids)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_thumb_scale()

    def _set_thumb(self, pix: QPixmap | None) -> None:
        self._thumb_pixmap = pix
        if pix is None:
            self.thumb.setPixmap(QPixmap())
            self.thumb.setText("(no image)")
            self.thumb.setFixedHeight(120)
            return
        self.thumb.clear()
        self._update_thumb_scale()

    def _update_thumb_scale(self) -> None:
        pix = self._thumb_pixmap
        if pix is None:
            return
        available = max(80, self._scroll.viewport().width() - 4)
        capped = min(340, available)
        scaled = pix.scaled(
            capped,
            capped * 9 // 16,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumb.setPixmap(scaled)
        self.thumb.setFixedHeight(scaled.height())

    def _open_category_picker(self) -> None:
        if self._meta is None:
            return
        menu = QMenu(self)
        for name in self._custom_categories:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name in self._custom_tags)
        menu.addSeparator()
        new_action = menu.addAction("New category…")
        chosen = menu.exec(self.add_category_btn.mapToGlobal(self.add_category_btn.rect().bottomLeft()))
        if chosen is None:
            return
        if chosen is new_action:
            self.new_category_requested.emit()
            return
        name = chosen.text()
        tags = list(self._custom_tags)
        if chosen.isChecked():
            if name not in tags:
                tags.append(name)
        elif name in tags:
            tags.remove(name)
        self.tags_changed.emit(self._meta.rel_path, tags)

    def clear(self) -> None:
        self._meta = None
        self._empty.setVisible(True)
        self._scroll.setVisible(False)

    def current_rel(self) -> str | None:
        return self._meta.rel_path if self._meta else None

    def _on_enabled_toggled(self, checked: bool) -> None:
        if self._meta is not None:
            self.toggled.emit(self._meta.rel_path, checked)

    def _open_workshop(self) -> None:
        if self._meta is None or self._meta.source != "workshop":
            return
        stem = self._meta.filename.rsplit(".", 1)[0]
        if stem.isdigit():
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(
                QUrl(
                    f"https://steamcommunity.com/sharedfiles/filedetails/?id={stem}"
                )
            )

    def set_enabled(self, enabled: bool) -> None:
        self.enabled_cb.blockSignals(True)
        self.enabled_cb.setChecked(enabled)
        self.enabled_cb.blockSignals(False)

    def set_context(
        self,
        meta: ModMeta,
        enabled: bool,
        conflicts: list[Conflict],
        lookup: dict[str, ModMeta],
        custom_tags: list[str] | None = None,
        group_ids: list[str] | None = None,
        random_ids: list[str] | None = None,
    ) -> None:
        self._meta = meta
        self._lookup = lookup
        self._conflicts = conflicts
        self._custom_tags = list(custom_tags or [])
        self._group_ids = list(group_ids or [])
        self._random_ids = list(random_ids or [])
        self._empty.setVisible(False)
        self._scroll.setVisible(True)
        self.set_enabled(enabled)

        if meta.thumbnail is not None:
            pix = QPixmap(str(meta.thumbnail))
            self._set_thumb(pix if not pix.isNull() else None)
        else:
            self._set_thumb(None)

        self.title.setText(soften_text(meta.title))
        self.title_note.setVisible(meta.title_source == "workshop")
        author_bits = []
        if meta.author:
            author_bits.append(f"by {meta.author}")
        if meta.version:
            author_bits.append(f"v{meta.version}")
        self.author.setText(soften_text("  ·  ".join(author_bits)))
        if meta.parse_error:
            self.author.setText(self.author.text() + f"  ⚠ {meta.parse_error}")

        while self.chips.count():
            item = self.chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        workshop_chips = list(
            dict.fromkeys(
                categories_for(meta.content_flags) + list(meta.workshop_tags)
            )
        )
        for label in workshop_chips:
            chip = QLabel(label)
            chip.setStyleSheet(_CHIP_STYLE)
            self.chips.addWidget(chip)
        for label in self._custom_tags:
            chip = QLabel(label)
            chip.setStyleSheet(_CUSTOM_CHIP_STYLE)
            self.chips.addWidget(chip)
        for group_id in self._group_ids:
            group_name = self._groups.get(group_id)
            if group_name is None:
                continue
            chip = QLabel(group_name)
            chip.setStyleSheet(_GROUP_CHIP_STYLE)
            self.chips.addWidget(chip)
        self.chips_container.setVisible(
            bool(workshop_chips or self._custom_tags or self._group_ids)
        )
        self.add_category_btn.setVisible(True)
        self.add_group_btn.setVisible(True)
        self.add_random_btn.setVisible(True)

        self.tagline.setText(soften_text(meta.tagline))
        self.tagline.setVisible(bool(meta.tagline))
        self.description.setText(soften_text(meta.description))
        self.description.setVisible(bool(meta.description))

        stem = meta.filename.rsplit(".", 1)[0]
        self.f_filename.setText(meta.filename)
        source_label = "Workshop" if meta.source == "workshop" else "Loose VPK"
        if meta.source == "workshop" and stem.isdigit():
            source_label += f" (ID {stem})"
        self.f_source.setText(source_label)
        self.f_size.setText(human_size(meta.size))
        self.f_files.setText(f"{len(meta.file_paths)} files")
        self.workshop_btn.setVisible(meta.source == "workshop" and stem.isdigit())

        active = [c for c in conflicts if c.active]
        potential = [c for c in conflicts if not c.active]
        if active:
            rows = []
            for c in active:
                title = self._lookup[c.other].title if c.other in self._lookup else c.other
                verdict = "wins" if c.winner == meta.rel_path else "loses"
                color = "#4caf50" if verdict == "wins" else "#e05555"
                rows.append(
                    f'<a href="{c.other}" style="color:#6fb3e0;">{title}</a> '
                    f'— {len(c.shared)} files — <span style="color:{color};">{verdict}</span>'
                )
            self.active_list.setText("<br>".join(rows))
        else:
            self.active_list.setText('<span style="color:#4caf50;">None</span>')

        self.potential_header.setVisible(bool(potential))
        self.potential_list.setVisible(bool(potential))
        if potential:
            rows = []
            for c in potential:
                title = self._lookup[c.other].title if c.other in self._lookup else c.other
                verdict = "would win" if c.winner == meta.rel_path else "would lose"
                rows.append(
                    f'<a href="{c.other}" style="color:#8a9aa8;">{title}</a> '
                    f'— {len(c.shared)} files — <span style="color:#8a9aa8;">{verdict} if both enabled</span>'
                )
            self.potential_list.setText("<br>".join(rows))

        self.conflicts_btn.setVisible(bool(active or potential))

        self._fill_files(meta)

    def _fill_files(self, meta: ModMeta) -> None:
        tree = self.files_tree
        tree.clear()
        if not meta.file_paths:
            self.files_header.setVisible(False)
            tree.setVisible(False)
            return
        groups: dict[str, list[str]] = {}
        for path in sorted(meta.file_paths):
            parts = path.split("/", 1)
            key = parts[0] if len(parts) > 1 else "(root)"
            groups.setdefault(key, []).append(
                parts[1] if len(parts) > 1 else parts[0]
            )
        for group, files in sorted(groups.items()):
            top = QTreeWidgetItem([f"{group}  ({len(files)})"])
            for name in files:
                QTreeWidgetItem(top, [name])
            tree.addTopLevelItem(top)
        self.files_header.setVisible(True)
        tree.setVisible(True)
