from __future__ import annotations

import pyperclip
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTextEdit,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from talky.controller import AppController
from talky.hotkey import GlobalShortcutListener
from talky.models import AppSettings
from talky.permissions import is_accessibility_trusted

_ZH = {
    "settings": "\u8bbe\u7f6e",
    "save": "\u4fdd\u5b58",
    "check_accessibility": "\u65e0\u969c\u788d",
    "shared_dictionary": "\u5171\u4eab\u8bcd\u5178",
    "base_params": "\u57fa\u7840\u53c2\u6570",
    "hotkey": "\u70ed\u952e",
    "whisper_model": "Whisper \u6a21\u578b",
    "ollama_model": "Ollama \u6a21\u578b",
    "asr_language": "ASR \u8bed\u8a00",
    "ui_language": "UI \u8bed\u8a00",
    "paste_delay": "\u7c98\u8d34\u5ef6\u8fdf",
    "llm_debug_stream": "LLM \u8c03\u8bd5\u6d41\u8f93\u51fa",
    "saved": "\u5df2\u4fdd\u5b58",
    "access_granted": "\u65e0\u969c\u788d\u6743\u9650\u5df2\u5f00\u542f",
    "access_missing": "\u9700\u8981\u65e0\u969c\u788d\u6743\u9650",
    "open_settings": "\u6253\u5f00\u8bbe\u7f6e",
    "quit": "\u9000\u51fa",
    "started": "\u5df2\u542f\u52a8",
    "error": "\u9519\u8bef",
    "popup_title": "\u65e0\u53ef\u7528\u7126\u70b9",
    "popup_subtitle": "\u53ef\u590d\u5236\u540e\u624b\u52a8\u7c98\u8d34",
    "copy_close": "\u590d\u5236\u5e76\u5173\u95ed",
    "settings_subtitle": "\u73bb\u7483\u98ce\u683c\u8bbe\u7f6e\u9762\u677f\uff1a\u8bcd\u5178\uff0c\u6a21\u578b\uff0c\u5f55\u97f3\u53c2\u6570",
}


def _tr(locale: str, en: str, key: str | None = None) -> str:
    if locale == "mixed" and key:
        return f"{en} ({_ZH[key]})"
    return en


IOS26_STYLESHEET = """
QWidget {
    font-family: "PingFang SC", "Helvetica Neue", "Arial";
    color: #000000;
}

QWidget#RootView {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #EDEDED,
        stop: 1 #D9D9D9
    );
    border: 1px solid rgba(255, 255, 255, 120);
    border-radius: 24px;
}

QFrame#GlowLayer {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(237, 74, 32, 65),
        stop: 1 rgba(237, 74, 32, 18)
    );
    border-radius: 20px;
}

QFrame#GlassCard, QFrame#PopupCard {
    background: rgba(255, 255, 255, 235);
    border: 1px solid rgba(0, 0, 0, 26);
    border-radius: 22px;
}

QLabel#WindowTitle {
    font-size: 22px;
    font-weight: 700;
    color: #000000;
}

QLabel#WindowSubtitle {
    font-size: 13px;
    color: #272727;
}

QLabel#CardTitle {
    font-size: 15px;
    font-weight: 600;
    color: #000000;
}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {
    border: 1px solid rgba(0, 0, 0, 45);
    border-radius: 16px;
    background: rgba(255, 255, 255, 250);
    padding: 8px 10px;
    selection-background-color: rgba(237, 74, 32, 145);
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid rgba(237, 74, 32, 225);
}

QTextEdit#ResultPanel {
    background: #FFFFFF;
    color: #000000;
    border: 1px solid rgba(0, 0, 0, 55);
}

QPushButton {
    border: none;
    border-radius: 16px;
    padding: 9px 15px;
    font-weight: 600;
}

QPushButton#PrimaryButton {
    background: #ED4A20;
    color: #000000;
}

QPushButton#PrimaryButton:hover {
    background: #F45B2F;
}

QPushButton#SecondaryButton {
    background: rgba(255, 255, 255, 230);
    color: #000000;
    border: 1px solid rgba(0, 0, 0, 26);
}

QPushButton#SecondaryButton:hover {
    background: rgba(255, 255, 255, 255);
}

QMessageBox {
    background: #FFFFFF;
}

QMessageBox QLabel {
    color: #000000;
}

QMessageBox QPushButton {
    background: #FFFFFF;
    color: #000000;
    border: 1px solid rgba(0, 0, 0, 45);
    border-radius: 10px;
    padding: 6px 12px;
}
"""


class SettingsWindow(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._locale = self.controller.settings.ui_locale
        self.setWindowTitle("Talky - Settings")
        self.resize(600, 520)
        self._fade_in_animation: QPropertyAnimation | None = None
        self._form_labels: list[tuple[QLabel, str, str]] = []

        self.dictionary_edit = QPlainTextEdit()
        self.dictionary_edit.setPlaceholderText(
            "One term per line. Plain: TensorRT. Person: person:Tom"
        )

        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItem("Fn / Globe (Primary)", userData="fn")
        self.hotkey_combo.addItem("Right Option (Fallback)", userData="right_option")

        self.whisper_model_input = QLineEdit()
        self.ollama_model_input = QLineEdit()
        self.language_input = QLineEdit()
        self.ui_locale_combo = QComboBox()
        self.ui_locale_combo.addItem("English", userData="en")
        self.ui_locale_combo.addItem("Chinese", userData="mixed")
        self.paste_delay_input = QSpinBox()
        self.paste_delay_input.setRange(50, 2000)
        self.paste_delay_input.setSuffix(" ms")
        self.llm_debug_stream_checkbox = QCheckBox()

        self.save_button = QPushButton(_tr(self._locale, "Save", "save"))
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save_settings)

        self.permission_button = QPushButton(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        self.permission_button.setObjectName("SecondaryButton")
        self.permission_button.clicked.connect(self._check_accessibility)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        left_col = [
            ("Record Hotkey", "hotkey", self.hotkey_combo),
            ("Whisper Model", "whisper_model", self.whisper_model_input),
            ("ASR Language", "asr_language", self.language_input),
        ]
        right_col = [
            ("Ollama Model", "ollama_model", self.ollama_model_input),
            ("UI Language", "ui_language", self.ui_locale_combo),
            ("Auto Paste Delay", "paste_delay", self.paste_delay_input),
            (
                "LLM Debug Stream",
                "llm_debug_stream",
                self.llm_debug_stream_checkbox,
            ),
        ]

        for row, (en_text, key, widget) in enumerate(left_col):
            label = QLabel(_tr(self._locale, en_text, key))
            label.setObjectName("WindowSubtitle")
            form.addWidget(label, row, 0)
            form.addWidget(widget, row, 1)
            self._form_labels.append((label, en_text, key))
        for row, (en_text, key, widget) in enumerate(right_col):
            label = QLabel(_tr(self._locale, en_text, key))
            label.setObjectName("WindowSubtitle")
            form.addWidget(label, row, 2)
            form.addWidget(widget, row, 3)
            self._form_labels.append((label, en_text, key))

        root = QVBoxLayout()
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        container = QWidget()
        container.setObjectName("RootView")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(22, 22, 22, 22)
        container_layout.setSpacing(14)

        self._title_label = QLabel(_tr(self._locale, "Settings", "settings"))
        self._title_label.setObjectName("WindowTitle")
        self._subtitle_label = QLabel(
            _tr(
                self._locale,
                "Glassmorphism panel for dictionary, models, and recording.",
                "settings_subtitle",
            )
        )
        self._subtitle_label.setObjectName("WindowSubtitle")
        container_layout.addWidget(self._title_label)
        container_layout.addWidget(self._subtitle_label)

        dictionary_card = self._build_glass_card()
        dictionary_layout = QVBoxLayout(dictionary_card)
        dictionary_layout.setContentsMargins(16, 14, 16, 16)
        self._dictionary_card_title = self._card_title(
            _tr(self._locale, "Shared Dictionary (ASR + LLM)", "shared_dictionary")
        )
        dictionary_layout.addWidget(self._dictionary_card_title)
        self.dictionary_edit.setMinimumHeight(230)
        dictionary_layout.addWidget(self.dictionary_edit)

        settings_card = self._build_glass_card()
        settings_card.setMaximumHeight(210)
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 14)
        self._params_card_title = self._card_title(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        settings_layout.addWidget(self._params_card_title)
        settings_layout.addLayout(form)

        container_layout.addWidget(dictionary_card, 1)
        container_layout.addWidget(settings_card, 0)

        button_row = QHBoxLayout()
        button_row.addWidget(self.permission_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        container_layout.addLayout(button_row)

        root.addWidget(container)
        self.setLayout(root)
        self.setStyleSheet(IOS26_STYLESHEET)
        self.controller.settings_updated.connect(self.load_from_settings)
        self.load_from_settings(self.controller.settings)

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        self._apply_locale_texts()
        self.dictionary_edit.setPlainText("\n".join(settings.custom_dictionary))
        idx = self.hotkey_combo.findData(settings.hotkey)
        self.hotkey_combo.setCurrentIndex(0 if idx < 0 else idx)
        self.whisper_model_input.setText(settings.whisper_model)
        self.ollama_model_input.setText(settings.ollama_model)
        self.language_input.setText(settings.language)
        locale_idx = self.ui_locale_combo.findData(settings.ui_locale)
        self.ui_locale_combo.setCurrentIndex(0 if locale_idx < 0 else locale_idx)
        self.paste_delay_input.setValue(settings.auto_paste_delay_ms)
        self.llm_debug_stream_checkbox.setChecked(settings.llm_debug_stream)

    def _apply_locale_texts(self) -> None:
        self.setWindowTitle(f"Talky - {_tr(self._locale, 'Settings', 'settings')}")
        self._title_label.setText(_tr(self._locale, "Settings", "settings"))
        self._subtitle_label.setText(
            _tr(
                self._locale,
                "Glassmorphism panel for dictionary, models, and recording.",
                "settings_subtitle",
            )
        )
        self._dictionary_card_title.setText(
            _tr(self._locale, "Shared Dictionary (ASR + LLM)", "shared_dictionary")
        )
        self._params_card_title.setText(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        self.save_button.setText(_tr(self._locale, "Save", "save"))
        self.permission_button.setText(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        for label, en_text, key in self._form_labels:
            label.setText(_tr(self._locale, en_text, key))

    def _save_settings(self) -> None:
        terms = [
            line.strip()
            for line in self.dictionary_edit.toPlainText().splitlines()
            if line.strip()
        ]
        settings = AppSettings(
            custom_dictionary=terms,
            hotkey=str(self.hotkey_combo.currentData()),
            whisper_model=self.whisper_model_input.text().strip() or "./local_whisper_model",
            ollama_model=self.ollama_model_input.text().strip() or "qwen3.5:9b",
            ui_locale=str(self.ui_locale_combo.currentData()),
            language=self.language_input.text().strip() or "zh",
            auto_paste_delay_ms=self.paste_delay_input.value(),
            llm_debug_stream=self.llm_debug_stream_checkbox.isChecked(),
            sample_rate=self.controller.settings.sample_rate,
            channels=self.controller.settings.channels,
        )
        self.controller.update_settings(settings)
        QMessageBox.information(self, "Talky", _tr(settings.ui_locale, "Settings saved.", "saved"))

    def _check_accessibility(self) -> None:
        locale = str(self.ui_locale_combo.currentData())
        trusted = is_accessibility_trusted(prompt=True)
        if trusted:
            QMessageBox.information(
                self,
                "Talky",
                _tr(locale, "Accessibility permission granted.", "access_granted"),
            )
            return
        QMessageBox.warning(
            self,
            "Talky",
            _tr(locale, "Accessibility permission missing.", "access_missing")
            + "\nSystem Settings > Privacy & Security > Accessibility.",
        )

    def _build_glass_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GlassCard")
        return card

    def _card_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_in_animation = anim


class TrayApp:
    def __init__(self, controller: AppController, settings_window: SettingsWindow) -> None:
        self.controller = controller
        self.settings_window = settings_window
        self.result_popup = ResultPopupWindow()
        self.dictionary_shortcut_listener = GlobalShortcutListener(
            on_trigger=self.controller.request_show_settings
        )

        icon = QIcon()
        if icon.isNull():
            icon = settings_window.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolume
            )
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("Talky - Local Voice Input Assistant")

        menu = QMenu()
        locale = self.controller.settings.ui_locale
        self.open_action = QAction(_tr(locale, "Open Settings", "open_settings"), menu)
        self.quit_action = QAction(_tr(locale, "Quit", "quit"), menu)
        menu.addAction(self.open_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)

        self.open_action.triggered.connect(self.show_settings)
        self.quit_action.triggered.connect(self.quit_app)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

        self.controller.status_signal.connect(self._show_status)
        self.controller.error_signal.connect(self._show_error)
        self.controller.show_result_popup_signal.connect(self._show_result_popup)
        self.controller.show_settings_window_signal.connect(self.show_settings)
        self.controller.settings_updated.connect(self._on_settings_updated)

    def show(self) -> None:
        self.tray.show()
        self.dictionary_shortcut_listener.start()
        locale = self.controller.settings.ui_locale
        self._show_status(_tr(locale, "Talky started. Hold hotkey to record.", "started"))

    def show_settings(self) -> None:
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def quit_app(self) -> None:
        self.dictionary_shortcut_listener.stop()
        self.controller.stop()
        self.tray.hide()
        QApplication.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_settings()

    def _show_status(self, message: str) -> None:
        self.tray.showMessage("Talky", message, QSystemTrayIcon.MessageIcon.Information, 1200)

    def _show_error(self, message: str) -> None:
        locale = self.controller.settings.ui_locale
        self.tray.showMessage(
            f"Talky {_tr(locale, 'Error', 'error')}",
            message,
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )

    def _show_result_popup(self, text: str) -> None:
        self.result_popup.show_text(text, self.controller.settings.ui_locale)

    def _on_settings_updated(self, settings: AppSettings) -> None:
        locale = settings.ui_locale
        self.open_action.setText(_tr(locale, "Open Settings", "open_settings"))
        self.quit_action.setText(_tr(locale, "Quit", "quit"))


class ResultPopupWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(560, 360)
        self._fade_animation: QPropertyAnimation | None = None
        self._slide_animation: QPropertyAnimation | None = None

        self.text_view = QTextEdit()
        self.text_view.setObjectName("ResultPanel")
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText("Generated content will appear here.")

        self.title = QLabel("No Focus Target Detected")
        self.title.setObjectName("CardTitle")
        self.subtitle = QLabel("Result is ready. Copy and paste manually.")
        self.subtitle.setObjectName("WindowSubtitle")

        self.copy_close_button = QPushButton("Copy and Close")
        self.copy_close_button.setObjectName("PrimaryButton")
        self.copy_close_button.clicked.connect(self._copy_and_close)

        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("PopupCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 12)
        shadow.setColor(Qt.GlobalColor.gray)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.addWidget(self.title)
        card_layout.addWidget(self.subtitle)
        card_layout.addWidget(self.text_view)
        card_layout.addWidget(self.copy_close_button)
        root.addWidget(card)
        self.setLayout(root)
        self.setStyleSheet(IOS26_STYLESHEET)

    def show_text(self, text: str, locale: str) -> None:
        self.title.setText(_tr(locale, "No Focus Target Detected", "popup_title"))
        self.subtitle.setText(_tr(locale, "Result is ready. Copy and paste manually.", "popup_subtitle"))
        self.copy_close_button.setText(_tr(locale, "Copy and Close", "copy_close"))
        self.text_view.setPlainText(text)
        self._move_to_bottom_right()
        end_rect = self.geometry()
        start_rect = QRect(end_rect.x(), end_rect.y() + 18, end_rect.width(), end_rect.height())
        self.setGeometry(start_rect)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._animate_popup(start_rect, end_rect)

    def _copy_and_close(self) -> None:
        pyperclip.copy(self.text_view.toPlainText())
        self.close()

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        x = rect.x() + rect.width() - self.width() - 24
        y = rect.y() + rect.height() - self.height() - 24
        self.move(x, y)

    def _animate_popup(self, start_rect: QRect, end_rect: QRect) -> None:
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(190)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()
        self._fade_animation = fade

        slide = QPropertyAnimation(self, b"geometry")
        slide.setDuration(190)
        slide.setStartValue(start_rect)
        slide.setEndValue(end_rect)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start()
        self._slide_animation = slide
