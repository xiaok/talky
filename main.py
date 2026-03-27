from __future__ import annotations

import fcntl
import os
import signal
import sys
import threading
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from talky.macos_ui import activate_foreground_app
from talky.permissions import (
    check_microphone_granted,
    is_accessibility_trusted,
    request_microphone_permission,
)

_SIGNAL_PUMP_TIMER = None
_PENDING_EXIT_SIGNAL: int | None = None
_EXIT_REQUESTED = False
_SINGLE_INSTANCE_LOCK_FD: int | None = None


def _run_packaged_import_self_check() -> int | None:
    """Optional build-time self-check for packaged runtime imports.

    Enabled by TALKY_SELF_CHECK_IMPORTS=1.
    Returns:
      - None when self-check mode is not enabled
      - 0 when all required imports are available
      - 1 when any required import fails
    """
    if os.environ.get("TALKY_SELF_CHECK_IMPORTS") != "1":
        return None

    import importlib.util

    hard_fail_modules = ("numpy",)
    optional_runtime_modules = ("mlx", "mlx_whisper")
    failures: list[tuple[str, str]] = []
    warnings: list[str] = []

    for name in hard_fail_modules:
        try:
            __import__(name)
        except Exception as exc:
            failures.append((name, str(exc)))

    for name in optional_runtime_modules:
        try:
            __import__(name)
            continue
        except Exception as exc:
            detail = str(exc)
            spec = importlib.util.find_spec(name)
            # mxl/mlx_whisper are optional in bundle: runtime installer can provide them.
            # Only warn here; do not block DMG generation.
            if spec is None:
                warnings.append(
                    f"{name}: not bundled (expected; runtime installer will provide it)."
                )
                continue
            # Compiled extension init can fail on some build hosts even when present.
            if "initializing the extension" in detail.lower():
                warnings.append(
                    f"{name}: import failed during extension init, "
                    "but module is bundled (continuing)."
                )
                continue
            warnings.append(f"{name}: import warning ({detail})")

    if failures:
        print("Talky packaged import self-check failed:", file=sys.stderr)
        for name, detail in failures:
            print(f"  - {name}: {detail}", file=sys.stderr)
        return 1

    for item in warnings:
        print(f"Talky packaged import self-check warning: {item}", file=sys.stderr)
    print("Talky packaged import self-check passed: numpy")
    return 0


def default_config_path() -> Path:
    return Path.home() / ".talky" / "settings.json"


def single_instance_lock_path() -> Path:
    return Path.home() / ".talky" / "talky.lock"


def show_settings_signal_path() -> Path:
    return Path.home() / ".talky" / "show_settings.signal"


def notify_running_instance_show_settings() -> None:
    signal_path = show_settings_signal_path()
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    signal_path.write_text(str(os.getpid()), encoding="utf-8")


def try_acquire_single_instance_lock() -> bool:
    lock_path = single_instance_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    except Exception:
        os.close(fd)
        return True

    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("utf-8"))
    except Exception:
        pass

    global _SINGLE_INSTANCE_LOCK_FD
    _SINGLE_INSTANCE_LOCK_FD = fd
    return True


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


def _request_microphone_permission_after_start() -> None:
    mic_ok, _ = check_microphone_granted()
    if mic_ok:
        return
    request_microphone_permission()


def main() -> int:
    check_result = _run_packaged_import_self_check()
    if check_result is not None:
        return check_result

    if not try_acquire_single_instance_lock():
        notify_running_instance_show_settings()
        print("Talky is already running. Skip duplicate launch.", file=sys.stderr)
        return 0

    from PyQt6.QtWidgets import QMessageBox

    from talky.config_store import AppConfigStore
    from talky.controller import AppController
    from talky.debug_log import append_debug_log
    from talky.error_report import install_exception_report_hooks
    from talky.startup_gate import ensure_cloud_ready, ensure_local_ollama_ready, ensure_whisper_ready
    from talky.ui import SettingsWindow, TrayApp

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    append_debug_log("Talky startup")
    activate_foreground_app()

    try:
        from Foundation import (  # type: ignore[import-not-found]
            NSApplication,
            NSProcessInfo,
            NSUserDefaults,
        )

        NSApplication.sharedApplication().disableRelaunchOnLogin()
        NSProcessInfo.processInfo().disableAutomaticTermination_("Talky")
        NSUserDefaults.standardUserDefaults().setBool_forKey_(
            False, "NSQuitAlwaysKeepsWindows"
        )
    except Exception:
        pass

    try:
        from AppKit import NSApp, NSAppearance  # type: ignore[import-not-found]

        NSApp.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))
    except Exception:
        pass

    config_store = AppConfigStore(default_config_path())
    install_exception_report_hooks(settings_supplier=config_store.load)
    settings = config_store.load()

    if settings.mode == "cloud":
        if not ensure_cloud_ready(config_store):
            return 1
    else:
        if not ensure_local_ollama_ready(config_store):
            return 1

    if not ensure_whisper_ready(config_store):
        return 1

    if not is_accessibility_trusted(prompt=True):
        QMessageBox.warning(
            None,
            "Talky",
            "Accessibility permission missing. Auto-paste may fail. "
            "Grant permission in System Settings.",
        )

    controller = AppController(config_store=config_store)
    settings_window = SettingsWindow(controller=controller)
    tray_app = TrayApp(controller=controller, settings_window=settings_window)
    install_signal_handlers(tray_app=tray_app, controller=controller)

    def _cleanup_on_quit() -> None:
        """Kill child processes so macOS doesn't think the app is still alive."""
        import multiprocessing
        import multiprocessing.resource_tracker
        import signal as _signal

        for child in multiprocessing.active_children():
            try:
                child.terminate()
                child.join(timeout=1)
                if child.is_alive():
                    child.kill()
            except Exception:
                pass
        try:
            tracker_pid = getattr(
                multiprocessing.resource_tracker._resource_tracker, "_pid", None
            )
            if tracker_pid:
                os.kill(tracker_pid, _signal.SIGTERM)
        except Exception:
            pass
        os._exit(0)

    app.aboutToQuit.connect(_cleanup_on_quit)

    controller.start()
    activate_foreground_app()
    tray_app.show()

    def _deferred_local_ollama_recheck() -> None:
        """Re-verify Ollama after UI is up; if unreachable, notify and open Settings."""
        from PyQt6.QtWidgets import QSystemTrayIcon

        from talky.onboarding import OllamaStatus, detect_system_locale, run_preflight_check
        from talky.startup_gate import apply_ollama_host_from_settings

        s = config_store.load()
        if s.mode == "cloud":
            return
        apply_ollama_host_from_settings(s)
        if run_preflight_check() == OllamaStatus.READY:
            return
        activate_foreground_app()
        loc = detect_system_locale()
        msg = (
            "本地模式未连接 Ollama，正在打开设置…"
            if loc == "zh"
            else "Local mode: Ollama not reachable. Opening Settings…"
        )
        try:
            tray_app.tray.showMessage(
                "Talky",
                msg,
                QSystemTrayIcon.MessageIcon.Warning,
                10000,
            )
        except Exception:
            pass
        tray_app.show_settings()

    from PyQt6.QtCore import QTimer

    QTimer.singleShot(250, _request_microphone_permission_after_start)
    QTimer.singleShot(450, _deferred_local_ollama_recheck)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
