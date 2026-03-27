"""macOS-only helpers so Qt dialogs appear above other apps when launched from Finder/Dock."""

from __future__ import annotations

import sys
from typing import Any


def activate_foreground_app() -> None:
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        return


def prepare_qt_modal_for_macos(widget: Any) -> None:
    """Raise app and keep a dialog/message box above other windows (best-effort)."""
    activate_foreground_app()
    try:
        from PyQt6.QtCore import Qt

        widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    except Exception:
        pass
