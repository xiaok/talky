from __future__ import annotations

import importlib
import signal
import sys
from types import SimpleNamespace


def test_install_signal_handlers_calls_tray_quit(monkeypatch) -> None:
    fake_qtwidgets = SimpleNamespace(QApplication=object)
    fake_pyqt6 = SimpleNamespace(QtWidgets=fake_qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6", fake_pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", fake_qtwidgets)

    main_module = importlib.import_module("main")

    registered: dict[int, object] = {}

    def fake_signal(sig, handler):
        registered[sig] = handler
        return handler

    monkeypatch.setattr(signal, "signal", fake_signal)

    calls: list[str] = []
    tray_app = SimpleNamespace(quit_app=lambda: calls.append("quit"))
    controller = SimpleNamespace(stop=lambda: calls.append("stop"))

    main_module.install_signal_handlers(tray_app=tray_app, controller=controller)

    assert signal.SIGINT in registered
    assert signal.SIGTERM in registered

    registered[signal.SIGINT](signal.SIGINT, None)

    assert calls == ["quit"]
