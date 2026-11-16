from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..conflicts import Conflict
from ..vpk_meta import ModMeta

_RED = QColor(220, 60, 60)
_GRAY = QColor(150, 150, 150)


class ConflictDialog(QDialog):
    def __init__(
        self,
        meta: ModMeta,
        conflicts: list[Conflict],
        lookup: dict[str, ModMeta],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Conflicts — {meta.title}")
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        intro = QLabel(
            f"<b>{len(conflicts)}</b> mods replace files also replaced by "
            f"<b>{meta.title}</b> (<i>{meta.rel_path}</i>)"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        tree = QTreeWidget()
        tree.setColumnCount(1)
        tree.setHeaderLabel("Conflicting mods and shared files")
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)

        for conflict in conflicts:
            other = lookup.get(conflict.other)
            other_title = other.title if other else conflict.other
            count = len(conflict.shared)
            if conflict.active:
                verdict = "wins" if conflict.winner == meta.rel_path else "loses"
                label = f"{other_title}  —  {count} shared files  [ACTIVE, this mod {verdict}]"
            else:
                verdict = "would win" if conflict.winner == meta.rel_path else "would lose"
                label = f"{other_title}  —  {count} shared files  [inactive, this mod {verdict} if both enabled]"
            item = QTreeWidgetItem([label])
            item.setForeground(0, _RED if conflict.active else _GRAY)
            tree.addTopLevelItem(item)
            for path in conflict.shared:
                child = QTreeWidgetItem([path])
                child.setFont(0, mono)
                child.setForeground(0, _GRAY)
                item.addChild(child)

        layout.addWidget(tree)

        note = QLabel(
            "Winner = the mod listed higher in the load order (addonlist.txt). "
            "Toggling a mod off resolves its active conflicts."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)
