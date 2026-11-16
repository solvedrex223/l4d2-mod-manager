from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..vpk_meta import scan_addons
from ..workshop_meta import WorkshopDetails, dict_to_details, merge_details


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    scan_done = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        addons_dir: Path,
        thumb_cache: Path,
        workshop_cache: dict[str, WorkshopDetails] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._addons_dir = addons_dir
        self._thumb_cache = thumb_cache
        self._workshop_cache = workshop_cache or {}

    def run(self) -> None:
        try:
            metas = scan_addons(
                self._addons_dir,
                self._thumb_cache,
                lambda i, n, rel: self.progress.emit(i, n, rel),
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return

        cache = {
            fid: dict_to_details(fid, data) for fid, data in self._workshop_cache.items()
        }
        self.progress.emit(0, 0, "Fetching Workshop data…")
        result = merge_details(metas, cache)
        self.scan_done.emit(result)
