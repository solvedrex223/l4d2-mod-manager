from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QListView, QStyledItemDelegate, QStyle

from .mods_model import (
    ActiveConflictsRole,
    MetaRole,
    PotentialConflictsRole,
    ThumbnailRole,
)

CARD_W, CARD_H = 200, 152
THUMB_H = 108
PAD = 4
BADGE_D = 22
CHECK_SIZE = 18

_RED = QColor(214, 57, 57)
_RED_TINT = QColor(214, 57, 57, 30)
_GRAY = QColor(140, 140, 140)
_TEXT = QColor(230, 230, 230)
_DIM = QColor(0, 0, 0, 120)


class CardDelegate(QStyledItemDelegate):
    def __init__(self, view: QListView, parent=None) -> None:
        super().__init__(parent)
        self._view = view
        self._highlight: set[str] = set()

    def set_highlight(self, rel_paths: set[str]) -> None:
        self._highlight = rel_paths

    def sizeHint(self, option, index) -> QSize:
        return QSize(CARD_W, CARD_H)

    def _checkbox_rect(self, card: QRect) -> QRect:
        return QRect(card.left() + 6, card.top() + 6, CHECK_SIZE, CHECK_SIZE)

    def _badge_rect(self, thumb: QRect) -> QRect:
        return QRect(thumb.right() - BADGE_D - 6, thumb.top() + 6, BADGE_D, BADGE_D)

    def paint(self, painter: QPainter, option, index) -> None:
        meta = index.data(MetaRole)
        if meta is None:
            return
        pix = index.data(ThumbnailRole)
        enabled = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        active = index.data(ActiveConflictsRole) or 0
        potential = index.data(PotentialConflictsRole) or 0
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        highlighted = meta.rel_path in self._highlight

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        card = option.rect.adjusted(PAD, PAD, -PAD, -PAD)

        bg = QColor(58, 62, 70) if not selected else QColor(48, 86, 128)
        painter.setPen(QPen(QColor(90, 96, 106), 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(card, 8, 8)

        if highlighted:
            painter.setPen(QPen(_RED, 3))
            painter.setBrush(_RED_TINT)
            painter.drawRoundedRect(card, 8, 8)

        inner = card.adjusted(4, 4, -4, -4)
        thumb = QRect(
            inner.x() + (inner.width() - 192) // 2,
            inner.y(),
            192,
            THUMB_H,
        )
        if pix is not None:
            painter.drawPixmap(
                thumb.x() + (thumb.width() - pix.width()) // 2,
                thumb.y() + (thumb.height() - pix.height()) // 2,
                pix,
            )
            if not enabled:
                painter.fillRect(thumb, _DIM)
        else:
            painter.fillRect(thumb, QColor(45, 48, 54))
            painter.setPen(QColor(120, 124, 132))
            font = QFont(option.font)
            font.setPointSize(28)
            font.setBold(True)
            painter.setFont(font)
            initial = meta.title[:1].upper() if meta.title else "?"
            painter.drawText(thumb, Qt.AlignmentFlag.AlignCenter, initial)

        if not enabled:
            painter.setPen(_GRAY)
        else:
            painter.setPen(_TEXT)

        name_rect = QRect(
            inner.x(),
            thumb.bottom() + 6,
            inner.width(),
            option.fontMetrics.height() + 4,
        )
        painter.setFont(option.font)
        name = option.fontMetrics.elidedText(
            meta.title, Qt.TextElideMode.ElideRight, name_rect.width()
        )
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, name)

        check = self._checkbox_rect(card)
        painter.setBrush(QColor(250, 250, 250, 230))
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        painter.drawRoundedRect(check, 3, 3)
        if enabled:
            painter.setPen(QPen(QColor(40, 150, 70), 2))
            c = check.adjusted(4, 4, -4, -4)
            painter.drawLine(c.left(), c.top() + c.height() // 2, c.left() + c.width() // 2 - 1, c.bottom())
            painter.drawLine(c.left() + c.width() // 2 - 1, c.bottom(), c.right(), c.top())

        if active or potential:
            badge = self._badge_rect(thumb)
            painter.setBrush(_RED if active else QColor(110, 110, 110, 220))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(badge)
            painter.setPen(QColor(255, 255, 255))
            font = QFont(option.font)
            font.setPointSizeF(8.5)
            font.setBold(True)
            painter.setFont(font)
            text = str(active) if active else f"{potential}?"
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.position().toPoint()
            if self._checkbox_rect(option.rect).contains(pos):
                checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
                new_state = (
                    Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked
                )
                return model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
        return False
