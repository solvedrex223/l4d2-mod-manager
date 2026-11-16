from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout

_GREEN = "color: #4caf50; font-weight: bold;"
_AMBER = "color: #c9a227;"


class LaunchDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Starting L4D2")
        self.setModal(True)
        self.setFixedSize(360, 140)

        layout = QVBoxLayout(self)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)

        self.stage = QLabel("Rolling random groups…")
        self.stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage.setWordWrap(True)
        layout.addWidget(self.stage)

        self.note = QLabel("")
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        layout.addWidget(self.note)

    def set_stage(self, text: str) -> None:
        self.stage.setText(text)

    def game_detected(self) -> None:
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.stage.setText("Game running ✓")
        self.stage.setStyleSheet(_GREEN)

    def timeout_note(self) -> None:
        self.stage.setText("Game not detected yet")
        self.note.setText(
            "Steam may still be starting — the game may launch anyway."
        )
        self.note.setStyleSheet(_AMBER)
        self.note.setVisible(True)
