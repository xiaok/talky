from __future__ import annotations

import importlib
import signal
import sys
from types import SimpleNamespace


class FakeSignal:
    def __init__(self) -> None:
        self.connected: list[object] = []

    def connect(self, callback) -> None:
        self.connected.append(callback)


class FakeQTimer:
    def __init__(self) -> None:
        self.interval: int | None = None
        self.timeout = FakeSignal()
        self.started = False
        self.stopped = False

    def setInterval(self, interval: int) -> None:
        self.interval = interval

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeApp:
    def __init__(self) -> None:
        self.aboutToQuit = FakeSignal()
        self.props: dict[str, object] = {}
        self.quit_called = False

    def setProperty(self, key: str, value: object) -> None:
        self.props[key] = value

    def quit(self) -> None:
        self.quit_called = True


def test_install_signal_handlers_defers_quit_until_qt_tick(monkeypatch) -> None:
    app = FakeApp()
    created_timers: list[FakeQTimer] = []

    class FakeQApplication:
        @staticmethod
        def instance() -> FakeApp:
            return app

    def fake_qtimer_factory() -> FakeQTimer:
        timer = FakeQTimer()
        created_timers.append(timer)
        return timer

    fake_qtwidgets = SimpleNamespace(QApplication=FakeQApplication)
    fake_qtcore = SimpleNamespace(QTimer=fake_qtimer_factory)
    fake_pyqt6 = SimpleNamespace(QtWidgets=fake_qtwidgets, QtCore=fake_qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6", fake_pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", fake_qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", fake_qtcore)
    sys.modules.pop("main", None)

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
    assert calls == []

    assert len(created_timers) == 1
    tick = created_timers[0].timeout.connected[0]
    tick()

    assert calls == ["quit"]


def test_install_signal_handlers_starts_qt_signal_pump_timer(monkeypatch) -> None:
    app = FakeApp()
    created_timers: list[FakeQTimer] = []

    class FakeQApplication:
        @staticmethod
        def instance() -> FakeApp:
            return app

    def fake_qtimer_factory() -> FakeQTimer:
        timer = FakeQTimer()
        created_timers.append(timer)
        return timer

    fake_qtwidgets = SimpleNamespace(QApplication=FakeQApplication)
    fake_qtcore = SimpleNamespace(QTimer=fake_qtimer_factory)
    fake_pyqt6 = SimpleNamespace(QtWidgets=fake_qtwidgets, QtCore=fake_qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6", fake_pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", fake_qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", fake_qtcore)
    sys.modules.pop("main", None)

    main_module = importlib.import_module("main")

    monkeypatch.setattr(signal, "signal", lambda sig, handler: handler)

    tray_app = SimpleNamespace(quit_app=lambda: None)
    controller = SimpleNamespace(stop=lambda: None)

    main_module.install_signal_handlers(tray_app=tray_app, controller=controller)

    assert len(created_timers) == 1
    timer = created_timers[0]
    assert timer.interval == 200
    assert timer.started is True
    assert len(timer.timeout.connected) == 1
    assert main_module._SIGNAL_PUMP_TIMER is timer
    assert app.props["talky_signal_pump_timer"] is timer
    assert len(app.aboutToQuit.connected) == 1
