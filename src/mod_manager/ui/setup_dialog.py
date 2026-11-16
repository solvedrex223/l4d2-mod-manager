from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..config import autodetect_game_dir, normalize_game_dir, validate_game_dir


class SetupDialog(QDialog):
    def __init__(self, parent=None, initial: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("L4D2 Mod Manager — Setup")
        self.setMinimumWidth(520)
        self._game_dir: Path | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select your Left 4 Dead 2 installation:"))

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        browse_btn = QPushButton("Browse…")
        row.addWidget(self.path_edit)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.ok_btn = QPushButton("Continue")
        self.ok_btn.setDefault(True)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        browse_btn.clicked.connect(self._browse)
        self.path_edit.textChanged.connect(self._validate)
        self.ok_btn.clicked.connect(self.accept)

        if initial and validate_game_dir(initial):
            self.path_edit.setText(str(normalize_game_dir(Path(initial))))
        else:
            detected = autodetect_game_dir()
            if detected is not None:
                self.path_edit.setText(str(detected))
        self._validate()

    def _browse(self) -> None:
        start = self.path_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Left 4 Dead 2 folder", start)
        if chosen:
            self.path_edit.setText(chosen)

    def _validate(self) -> None:
        text = self.path_edit.text().strip()
        if not text:
            self._game_dir = None
            self.status_label.setText("")
            self.ok_btn.setEnabled(False)
            return
        path = Path(text)
        if validate_game_dir(path):
            self._game_dir = normalize_game_dir(path)
            self.status_label.setText(f"Valid directory")
            self.ok_btn.setEnabled(True)
        else:
            self._game_dir = None
            self.status_label.setText("Not a valid game folder — it must contain left4dead2/addons/.")
            self.ok_btn.setEnabled(False)

    def game_dir(self) -> Path | None:
        return self._game_dir
