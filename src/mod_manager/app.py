from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from .config import Settings, cache_dir, load_settings, save_settings, validate_game_dir
from .game import AddonList, addons_dir
from .store import Store
from .ui.main_window import MainWindow
from .ui.scan import ScanWorker
from .ui.setup_dialog import SetupDialog
from .workshop_meta import details_to_dict


class Controller:
    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._settings: Settings = load_settings()
        self._window: MainWindow | None = None
        self._progress: QProgressDialog | None = None
        self._worker: ScanWorker | None = None

    def run(self) -> int:
        game_dir = self._resolve_game_dir()
        if game_dir is None:
            return 0
        self.start_scan(game_dir)
        return self._app.exec()

    def _resolve_game_dir(self, force_prompt: bool = False) -> Path | None:
        if not force_prompt:
            current = self._settings.game_dir
            if current and validate_game_dir(current):
                return Path(current)
        dialog = SetupDialog(initial=self._settings.game_dir)
        if dialog.exec() != SetupDialog.DialogCode.Accepted:
            return None
        game_dir = dialog.game_dir()
        if game_dir is None:
            return None
        self._settings.game_dir = str(game_dir)
        save_settings(self._settings)
        return game_dir

    def start_scan(self, game_dir: Path) -> None:
        if self._window is not None:
            self._window.close()
            self._window = None
        progress = QProgressDialog("Scanning mods…", None, 0, 0)
        progress.setWindowTitle("Scanning mods")
        progress.show()
        store = Store.load()
        worker = ScanWorker(
            addons_dir(game_dir),
            cache_dir() / "thumbs",
            workshop_cache=store.workshop_meta,
        )
        worker.progress.connect(self._on_progress)
        worker.scan_done.connect(lambda result: self._on_scan_done(game_dir, result))
        worker.failed.connect(self._on_failed)
        self._progress = progress
        self._worker = worker
        worker.start()

    def _on_progress(self, done: int, total: int, rel: str) -> None:
        if self._progress is None:
            return
        self._progress.setMaximum(total)
        self._progress.setValue(done)
        self._progress.setLabelText(f"{rel}\n({done}/{total})" if total else rel)

    def _on_scan_done(self, game_dir: Path, result) -> None:
        metas = result.metas
        addonlist = AddonList.load(game_dir)
        original = dict(addonlist.entries)
        rels = [m.rel_path for m in metas]
        addonlist.reconcile(rels)

        store = Store.load()
        for rel, entry in store.mods.items():
            if rel in addonlist.entries:
                addonlist.entries[rel] = entry["enabled"]
        report = store.sync_with_scan(metas, addonlist.entries)
        for file_id, details in result.new_cache.items():
            store.workshop_meta[file_id] = details_to_dict(details)
        store.save()

        if addonlist.entries != original:
            addonlist.save(game_dir)

        self._close_progress()
        self._window = MainWindow(
            metas,
            store,
            game_dir,
            addonlist,
            report,
            on_change_game_dir=self._change_game_dir,
            on_rescan=lambda: self.start_scan(game_dir),
        )
        self._window.show()
        if result.fetch_failed:
            self._window.statusBar().showMessage(
                "Workshop data unavailable — some titles will update on next scan",
                8000,
            )
        elif result.fetched:
            self._window.statusBar().showMessage(
                f"Fetched Workshop data for {result.fetched} mods", 8000
            )

    def _on_failed(self, message: str) -> None:
        self._close_progress()
        QMessageBox.critical(None, "Scan failed", message)
        self._app.quit()

    def _change_game_dir(self) -> None:
        game_dir = self._resolve_game_dir(force_prompt=True)
        if game_dir is None:
            return
        self.start_scan(game_dir)

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None
        self._worker = None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("L4D2 Mod Manager")
    app.setDesktopFileName("l4d2-mod-manager")
    controller = Controller(app)
    return controller.run()


if __name__ == "__main__":
    sys.exit(main())
