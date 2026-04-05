from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


_app = QApplication.instance() or QApplication([])


def test_live_status_widget_shows_recording_and_processing_text():
    from talky.ui import LiveStatusWidget

    LiveStatusWidget._MIN_VISIBLE_SECONDS = 0.0
    LiveStatusWidget._STATE_DEBOUNCE_SECONDS = 0.0
    widget = LiveStatusWidget()
    widget.show_recording("en")
    assert widget.isVisible()
    assert widget.title.text() == "Recording"

    widget.show_processing("mixed")
    assert widget.isVisible()
    assert widget.title.text() == "正在识别"

    widget.show_post_processing("mixed")
    assert widget.isVisible()
    assert widget.title.text() == "后处理中"

    widget.hide_status()
    assert not widget.isVisible()

    widget.show_post_processing("en")
    assert widget.isVisible()
    assert widget.title.text() == "Post Processing"

    widget.hide_status()
    assert not widget.isVisible()


def test_live_status_widget_subtitle_animation_ticks():
    from talky.ui import LiveStatusWidget

    LiveStatusWidget._MIN_VISIBLE_SECONDS = 0.0
    LiveStatusWidget._STATE_DEBOUNCE_SECONDS = 0.0
    widget = LiveStatusWidget()
    widget.show_recording("en")
    first = widget.subtitle.text()
    widget._on_animation_tick()
    second = widget.subtitle.text()
    assert first.startswith("Listening")
    assert second.startswith("Listening")
    assert first != second

    widget.show_processing("zh")
    p1 = widget.subtitle.text()
    widget._on_animation_tick()
    p2 = widget.subtitle.text()
    assert p1.startswith("转译中")
    assert p2.startswith("转译中")
    assert p1 != p2


def test_live_status_widget_has_logo_and_no_focus_flags():
    from talky.ui import LiveStatusWidget

    widget = LiveStatusWidget()
    assert widget.logo.pixmap() is not None
    assert widget.logo.width() == 48
    assert widget.logo.height() == 48
    flags = widget.windowFlags()
    assert bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus)
    assert bool(flags & Qt.WindowType.ToolTip)
