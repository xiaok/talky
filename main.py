from __future__ import annotations

import signal
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from talky.permissions import is_accessibility_trusted


def default_config_path() -> Path:
    return Path.home() / ".talky" / "settings.json"


def install_signal_handlers(*, tray_app, controller) -> None:
    def _handle_signal(signum, _frame) -> None:  # noqa: ANN001
        del signum
        try:
            tray_app.quit_app()
        except Exception:
            try:
                controller.stop()
            except Exception:
                pass
            app = QApplication.instance()
            if app is not None:
                app.quit()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def main() -> int:
    from talky.config_store import AppConfigStore
    from talky.controller import AppController
    from talky.ui import SettingsWindow, TrayApp

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config_store = AppConfigStore(default_config_path())
    controller = AppController(config_store=config_store)
    settings_window = SettingsWindow(controller=controller)
    tray_app = TrayApp(controller=controller, settings_window=settings_window)
    install_signal_handlers(tray_app=tray_app, controller=controller)

    if not is_accessibility_trusted(prompt=True):
        tray_app._show_error(  # noqa: SLF001 - startup prompt convenience
            "Accessibility permission missing. Auto-paste may fail. "
            "Grant permission in System Settings."
        )

    controller.start()
    tray_app.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
