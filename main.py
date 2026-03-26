from __future__ import annotations

import os
import signal
import sys
import threading
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from talky.permissions import is_accessibility_trusted

_SIGNAL_PUMP_TIMER = None
_PENDING_EXIT_SIGNAL: int | None = None
_EXIT_REQUESTED = False


def default_config_path() -> Path:
    return Path.home() / ".talky" / "settings.json"


def _force_exit_after_timeout(signum: int) -> None:
    app = QApplication.instance()
    if app is not None:
        os._exit(128 + signum)


def _request_graceful_exit(*, tray_app, controller, signum: int) -> None:
    global _EXIT_REQUESTED
    if _EXIT_REQUESTED:
        return
    _EXIT_REQUESTED = True

    fallback = threading.Timer(2.0, _force_exit_after_timeout, args=(signum,))
    fallback.daemon = True
    fallback.start()

    app = QApplication.instance()
    if app is not None:
        try:
            app.aboutToQuit.connect(fallback.cancel)
        except Exception:
            pass

    try:
        tray_app.quit_app()
    except Exception:
        try:
            controller.stop()
        except Exception:
            pass
        if app is not None:
            app.quit()


def _install_qt_signal_pump(*, tray_app, controller) -> None:
    qapp_instance = getattr(QApplication, "instance", None)
    if qapp_instance is None:
        return
    try:
        app = qapp_instance()
    except Exception:
        return
    if app is None:
        return

    try:
        from PyQt6.QtCore import QTimer
    except Exception:
        return

    timer = QTimer()
    timer.setInterval(200)
    def _poll_pending_exit() -> None:
        global _PENDING_EXIT_SIGNAL
        if _PENDING_EXIT_SIGNAL is None:
            return
        signum = _PENDING_EXIT_SIGNAL
        _PENDING_EXIT_SIGNAL = None
        _request_graceful_exit(
            tray_app=tray_app,
            controller=controller,
            signum=signum,
        )

    timer.timeout.connect(_poll_pending_exit)
    timer.start()

    try:
        app.aboutToQuit.connect(timer.stop)
    except Exception:
        pass

    global _SIGNAL_PUMP_TIMER
    _SIGNAL_PUMP_TIMER = timer

    try:
        app.setProperty("talky_signal_pump_timer", timer)
    except Exception:
        pass


def install_signal_handlers(*, tray_app, controller) -> None:
    def _handle_signal(signum, _frame) -> None:  # noqa: ANN001
        global _PENDING_EXIT_SIGNAL
        _PENDING_EXIT_SIGNAL = int(signum)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    _install_qt_signal_pump(tray_app=tray_app, controller=controller)


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

    # --- Onboarding / preflight check ---
    from talky.onboarding import (
        OllamaStatus,
        OnboardingWizard,
        detect_system_locale,
        run_preflight_check,
        show_returning_user_prompt,
    )

    settings = config_store.load()
    if settings.mode != "cloud":
        status = run_preflight_check()
        if status != OllamaStatus.READY:
            locale = detect_system_locale()
            is_first_run = not config_store.config_path.exists()
            if is_first_run:
                wizard = OnboardingWizard(
                    config_store=config_store,
                    ollama_status=status,
                    locale=locale,
                )
                wizard.exec()
            else:
                show_returning_user_prompt(status, locale=locale)

    controller.start()
    tray_app.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
