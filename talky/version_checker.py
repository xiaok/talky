from __future__ import annotations

import json
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

CURRENT_VERSION = "Talky-2026.03.27-d833b66-unsigned"
CURRENT_BUILD_ID = "duqREy"


class VersionChecker(QObject):
    """Check for app updates via local file or remote URL."""

    update_available = pyqtSignal(str, str)  # (latest_version, download_url)

    def check_async(self) -> None:
        thread = threading.Thread(target=self._check, daemon=True)
        thread.start()

    def _check(self) -> None:
        info_path = Path.home() / ".talky" / "update_info.json"
        if not info_path.exists():
            return
        try:
            data = json.loads(info_path.read_text(encoding="utf-8"))
            latest = str(data.get("latest_version", ""))
            url = str(data.get("download_url", ""))
            if latest and self._is_newer(latest, CURRENT_VERSION):
                self.update_available.emit(latest, url)
        except Exception:
            pass

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        try:
            def _parse(v: str) -> tuple[int, ...]:
                return tuple(int(x) for x in v.split("-")[0].split("."))

            return _parse(latest) > _parse(current)
        except Exception:
            return False
