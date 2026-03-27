from __future__ import annotations

import os
import shlex
import subprocess
import sys
import pyperclip
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTextEdit,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from talky.controller import AppController
from talky.startup_gate import alert_if_local_ollama_unready
from talky.hotkey import GlobalShortcutListener, label_for_hotkey_tokens
from talky.models import AppSettings
from talky.recommended_ollama import recommended_model_name
from talky.permissions import (
    check_microphone_granted,
    is_accessibility_trusted,
    request_microphone_permission,
)
from talky.runtime_setup import ensure_local_whisper_runtime
from talky.debug_log import append_debug_log
from talky.error_report import append_error_report

_ZH = {
    "settings": "\u8bbe\u7f6e",
    "save": "\u4fdd\u5b58",
    "check_accessibility": "\u65e0\u969c\u788d",
    "shared_dictionary": "\u5171\u4eab\u8bcd\u5178",
    "base_params": "\u57fa\u7840\u53c2\u6570",
    "hotkey": "\u70ed\u952e",
    "whisper_model": "Whisper \u6a21\u578b",
    "ollama_model": "Ollama \u6a21\u578b",
    "ollama_host": "Ollama \u5730\u5740",
    "asr_language": "ASR \u8bed\u8a00",
    "ui_language": "UI \u8bed\u8a00",
    "paste_delay": "\u7c98\u8d34\u5ef6\u8fdf",
    "llm_debug_stream": "LLM \u8c03\u8bd5\u6d41\u8f93\u51fa",
    "saved": "\u5df2\u4fdd\u5b58",
    "open_dashboard": "\u6253\u5f00\u9762\u677f",
    "show_last_error": "\u9519\u8bef\u4fe1\u606f",
    "no_error_yet": "\u6682\u65e0\u9519\u8bef\u8bb0\u5f55",
    "last_error_title": "\u6700\u8fd1\u9519\u8bef",
    "copy": "\u590d\u5236",
    "close": "\u5173\u95ed",
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
    "permission_status": "\u6743\u9650\u72b6\u6001",
    "mic_permission": "\u9ea6\u514b\u98ce\u6743\u9650",
    "accessibility_permission": "\u8f85\u52a9\u529f\u80fd\u6743\u9650",
    "granted": "\u5df2\u6388\u6743",
    "not_granted": "\u672a\u6388\u6743",
    "request_mic_permission": "\u8bf7\u6c42\u9ea6\u514b\u98ce\u6743\u9650",
    "ui_option_english": "\u82f1\u6587",
    "ui_option_chinese": "\u4e2d\u6587",
    "hotkey_record_button": "\u5f55\u5236\u81ea\u5b9a\u4e49\u70ed\u952e",
    "hotkey_reset_default": "\u6062\u590d\u9ed8\u8ba4\uff08Fn\uff09",
    "hotkey_recommended_fallback": "\u4f7f\u7528\u63a8\u8350\u5907\u7528\uff08Right Option\uff09",
    "hotkey_custom_hint": "\u5f53\u524d\u81ea\u5b9a\u4e49\uff1a",
    "hotkey_custom_empty": "\u5c1a\u672a\u5f55\u5236\u81ea\u5b9a\u4e49\u70ed\u952e",
    "model_setup_title": "需要 Whisper 模型",
    "model_setup_desc": "Talky 需要 Whisper 模型来进行语音识别。\n选择下载或提供自己的模型路径。",
    "download_model": "下载模型（约 3 GB）",
    "i_have_model": "我已有模型",
    "model_path_placeholder": "路径或 HuggingFace 仓库 ID",
    "confirm_model": "确认",
    "downloading_model": "正在下载模型… 首次下载约需 3–5 分钟。",
    "preparing_runtime": "正在准备运行环境…",
    "download_done": "下载完成！现在可以使用语音输入了。",
    "download_done_restarting": "下载完成，正在重启 Talky…",
    "download_failed": "下载失败",
    "reset": "重置",
    "reset_confirm": "确定要重置所有设置并重启 Talky 吗？\n这将删除 ~/.talky/settings.json",
}


def _tr(locale: str, en: str, key: str | None = None) -> str:
    if locale == "mixed" and key:
        return _ZH.get(key, en)
    return en


def _asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name


def _restart_command() -> list[str]:
    """Build a safe argv for relaunch on macOS app and source runs."""
    args = [arg for arg in sys.argv[1:] if not str(arg).startswith("-psn_")]
    return [sys.executable, *args]


def _restart_current_process(reason: str) -> bool:
    """Restart process robustly across source run and bundled app run.

    In a bundled macOS .app, os.execv replaces the process in-place (same PID),
    which prevents macOS WindowServer from re-registering the NSStatusItem
    (tray icon).  Instead we exit cleanly and use `open` via LaunchServices
    to start a brand-new process with a fresh PID after a short delay.
    """
    cmd = _restart_command()
    append_debug_log(
        f"Restart requested ({reason}); executable={sys.executable}; argv={cmd!r}"
    )
    # --- Bundled .app: use `open` so macOS properly re-registers the app ---
    if getattr(sys, "frozen", False):
        try:
            app_bundle = _find_app_bundle_path()
            if app_bundle:
                launch_cmd = f"sleep 0.5; open {shlex.quote(str(app_bundle))}"
            else:
                launch_cmd = f"sleep 0.5; {shlex.join(cmd)}"
            subprocess.Popen(  # noqa: S603
                ["/bin/sh", "-c", launch_cmd],
                close_fds=True,
                start_new_session=True,
            )
            append_debug_log(f"Bundled restart launcher spawned: {launch_cmd}")
            return True
        except Exception as exc:
            append_debug_log("Bundled restart launcher failed", exc=exc)
            return False
    # --- Source run: in-place exec (same PID is fine) ---
    try:
        os.execv(sys.executable, cmd)
    except Exception as exc:
        append_debug_log("os.execv restart failed; trying subprocess fallback", exc=exc)
    try:
        subprocess.Popen(cmd, close_fds=True)  # noqa: S603
        append_debug_log("Restart fallback subprocess launched successfully")
        return True
    except Exception as exc:
        append_debug_log("Restart fallback subprocess launch failed", exc=exc)
        return False


def _find_app_bundle_path() -> Path | None:
    """Walk up from sys.executable to find the enclosing .app bundle."""
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


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

QComboBox#InsetIconField {
    padding-right: 34px;
}

QComboBox#InsetIconField::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 18px;
    right: 8px;
    border: none;
}

QSpinBox#InsetStepperField {
    padding-right: 34px;
}

QSpinBox#InsetStepperField::up-button,
QSpinBox#InsetStepperField::down-button {
    subcontrol-origin: padding;
    width: 16px;
    right: 8px;
    border: none;
}

QSpinBox#InsetStepperField::up-button {
    subcontrol-position: top right;
}

QSpinBox#InsetStepperField::down-button {
    subcontrol-position: bottom right;
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


class CustomHotkeyCaptureDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Record custom hotkey")
        self.setModal(True)
        self.resize(420, 140)
        self.captured_tokens: list[str] = []

        self.info = QLabel("Press and hold your desired hotkey now...")
        self.info.setObjectName("WindowSubtitle")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(self.info)
        self.setLayout(layout)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        tokens = self._tokens_from_event(event)
        if tokens:
            self.captured_tokens = tokens
            self.info.setText(f"Captured: {label_for_hotkey_tokens(tokens)}")
            QTimer.singleShot(120, self.accept)
            return
        super().keyPressEvent(event)

    def _tokens_from_event(self, event) -> list[str]:
        tokens: set[str] = set()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.AltModifier:
            tokens.add("alt")
        if mods & Qt.KeyboardModifier.ControlModifier:
            tokens.add("ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            tokens.add("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            tokens.add("cmd")
        return sorted(tokens)


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
        self.hotkey_combo.setObjectName("InsetIconField")
        self.hotkey_combo.addItem("Fn / Globe (Default)", userData="fn")
        self.hotkey_combo.addItem("Right Option", userData="right_option")
        self.hotkey_combo.addItem("Right Command", userData="right_command")
        self.hotkey_combo.addItem("Command + Option", userData="command_option")
        self.hotkey_combo.addItem("Custom (record below)", userData="custom")
        self.hotkey_combo.currentIndexChanged.connect(self._on_hotkey_mode_changed)

        self.hotkey_record_button = QPushButton(
            _tr(self._locale, "Record custom hotkey", "hotkey_record_button")
        )
        self.hotkey_record_button.setObjectName("SecondaryButton")
        self.hotkey_record_button.clicked.connect(self._begin_custom_hotkey_record)

        self.hotkey_reset_default_button = QPushButton(
            _tr(self._locale, "Reset to default (Fn)", "hotkey_reset_default")
        )
        self.hotkey_reset_default_button.setObjectName("SecondaryButton")
        self.hotkey_reset_default_button.clicked.connect(self._reset_default_hotkey)

        self.hotkey_recommended_button = QPushButton(
            _tr(
                self._locale,
                "Use recommended fallback (Right Option)",
                "hotkey_recommended_fallback",
            )
        )
        self.hotkey_recommended_button.setObjectName("SecondaryButton")
        self.hotkey_recommended_button.clicked.connect(self._use_recommended_fallback_hotkey)

        self.hotkey_custom_preview = QLabel("")
        self.hotkey_custom_preview.setObjectName("WindowSubtitle")

        self._custom_hotkey_tokens: list[str] = []

        hotkey_controls = QVBoxLayout()
        hotkey_controls.setContentsMargins(0, 0, 0, 0)
        hotkey_controls.setSpacing(8)
        hotkey_controls.addWidget(self.hotkey_combo)
        hotkey_controls.addWidget(self.hotkey_record_button)
        hotkey_controls.addWidget(self.hotkey_custom_preview)
        hotkey_controls.addWidget(self.hotkey_recommended_button)
        hotkey_controls.addWidget(self.hotkey_reset_default_button)
        self.hotkey_widget = QWidget()
        self.hotkey_widget.setLayout(hotkey_controls)

        self._mode_combo = QComboBox()
        self._mode_combo.setObjectName("InsetIconField")
        self._mode_combo.addItem("Local (Free)", userData="local")
        self._mode_combo.addItem("Remote Ollama (LAN)", userData="remote")
        self._mode_combo.addItem("Cloud (Subscription)", userData="cloud")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._cloud_url_input = QLineEdit()
        self._cloud_url_input.setPlaceholderText("http://192.168.x.x:8000")
        self._cloud_key_input = QLineEdit()
        self._cloud_key_input.setPlaceholderText("sk-talky-...")
        self._cloud_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.whisper_model_input = QLineEdit()
        self.ollama_model_input = QLineEdit()
        self.ollama_host_input = QLineEdit()
        self.ollama_host_input.setPlaceholderText("http://127.0.0.1:11434")
        self.language_input = QLineEdit()
        self.ui_locale_combo = QComboBox()
        self.ui_locale_combo.setObjectName("InsetIconField")
        self.ui_locale_combo.addItem(
            _tr(self._locale, "English", "ui_option_english"), userData="en"
        )
        self.ui_locale_combo.addItem(
            _tr(self._locale, "Chinese", "ui_option_chinese"), userData="mixed"
        )
        self.paste_delay_input = QSpinBox()
        self.paste_delay_input.setObjectName("InsetStepperField")
        self.paste_delay_input.setRange(50, 2000)
        self.paste_delay_input.setSuffix(" ms")
        self.llm_debug_stream_checkbox = QCheckBox()

        self.save_button = QPushButton(_tr(self._locale, "Save", "save"))
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save_settings)

        self.reset_button = QPushButton(_tr(self._locale, "Reset", "reset"))
        self.reset_button.setObjectName("SecondaryButton")
        self.reset_button.clicked.connect(self._reset_settings)

        self.permission_button = QPushButton(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        self.permission_button.setObjectName("SecondaryButton")
        self.permission_button.clicked.connect(self._check_accessibility)

        self.request_mic_button = QPushButton(
            _tr(self._locale, "Request Microphone Permission", "request_mic_permission")
        )
        self.request_mic_button.setObjectName("SecondaryButton")
        self.request_mic_button.clicked.connect(self._request_microphone_permission)

        self.permission_status_title = self._card_title(
            _tr(self._locale, "Permission Status", "permission_status")
        )
        self.mic_permission_label = QLabel(
            _tr(self._locale, "Microphone Permission", "mic_permission")
        )
        self.mic_permission_label.setObjectName("WindowSubtitle")
        self.mic_status_value_label = QLabel("")
        self.mic_status_value_label.setObjectName("WindowSubtitle")

        self.ax_permission_label = QLabel(
            _tr(self._locale, "Accessibility Permission", "accessibility_permission")
        )
        self.ax_permission_label.setObjectName("WindowSubtitle")
        self.ax_status_value_label = QLabel("")
        self.ax_status_value_label.setObjectName("WindowSubtitle")

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        fields = [
            ("Processing Mode", "processing_mode", self._mode_combo),
            ("Cloud API URL", "cloud_api_url", self._cloud_url_input),
            ("Cloud API Key", "cloud_api_key", self._cloud_key_input),
            ("Record Hotkey", "hotkey", self.hotkey_widget),
            ("Whisper Model", "whisper_model", self.whisper_model_input),
            ("ASR Language", "asr_language", self.language_input),
            ("Ollama Host", "ollama_host", self.ollama_host_input),
            ("Ollama Model", "ollama_model", self.ollama_model_input),
            ("UI Language", "ui_language", self.ui_locale_combo),
            ("Auto Paste Delay", "paste_delay", self.paste_delay_input),
            ("LLM Debug Stream", "llm_debug_stream", self.llm_debug_stream_checkbox),
        ]

        for row, (en_text, key, widget) in enumerate(fields):
            label = QLabel(_tr(self._locale, en_text, key))
            label.setObjectName("WindowSubtitle")
            form.addWidget(label, row, 0)
            form.addWidget(widget, row, 1)
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
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 14)
        self._params_card_title = self._card_title(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        settings_layout.addWidget(self._params_card_title)
        settings_layout.addLayout(form)
        settings_layout.addWidget(self.permission_status_title)
        permission_grid = QGridLayout()
        permission_grid.setHorizontalSpacing(12)
        permission_grid.setVerticalSpacing(8)
        permission_grid.addWidget(self.mic_permission_label, 0, 0)
        permission_grid.addWidget(self.mic_status_value_label, 0, 1)
        permission_grid.addWidget(self.request_mic_button, 0, 2)
        permission_grid.addWidget(self.ax_permission_label, 1, 0)
        permission_grid.addWidget(self.ax_status_value_label, 1, 1)
        permission_grid.addWidget(self.permission_button, 1, 2)
        settings_layout.addLayout(permission_grid)

        container_layout.addWidget(dictionary_card, 1)
        container_layout.addWidget(settings_card, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(container)

        button_row = QHBoxLayout()
        button_row.addWidget(self.reset_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)

        root.addWidget(scroll_area, 1)
        root.addLayout(button_row, 0)
        self.setLayout(root)
        self.setStyleSheet(IOS26_STYLESHEET)
        self.controller.settings_updated.connect(self.load_from_settings)
        self.load_from_settings(self.controller.settings)

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        self._apply_locale_texts()
        self.dictionary_edit.setPlainText("\n".join(settings.custom_dictionary))
        self._custom_hotkey_tokens = [t.strip().lower() for t in settings.custom_hotkey if t.strip()]
        idx = self.hotkey_combo.findData(settings.hotkey)
        self.hotkey_combo.setCurrentIndex(0 if idx < 0 else idx)
        self._apply_hotkey_control_state()
        mode_idx = self._mode_combo.findData(settings.mode)
        self._mode_combo.setCurrentIndex(0 if mode_idx < 0 else mode_idx)
        self._cloud_url_input.setText(settings.cloud_api_url)
        self._cloud_key_input.setText(settings.cloud_api_key)
        self._update_cloud_field_visibility()
        self.whisper_model_input.setText(settings.whisper_model)
        self.ollama_host_input.setText(settings.ollama_host)
        self.ollama_model_input.setText(settings.ollama_model)
        self.language_input.setText(settings.language)
        locale_idx = self.ui_locale_combo.findData(settings.ui_locale)
        self.ui_locale_combo.setCurrentIndex(0 if locale_idx < 0 else locale_idx)
        self.paste_delay_input.setValue(settings.auto_paste_delay_ms)
        self.llm_debug_stream_checkbox.setChecked(settings.llm_debug_stream)
        self._refresh_permission_status()

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
        self.permission_status_title.setText(
            _tr(self._locale, "Permission Status", "permission_status")
        )
        self.mic_permission_label.setText(
            _tr(self._locale, "Microphone Permission", "mic_permission")
        )
        self.ax_permission_label.setText(
            _tr(self._locale, "Accessibility Permission", "accessibility_permission")
        )
        self.save_button.setText(_tr(self._locale, "Save", "save"))
        self.reset_button.setText(_tr(self._locale, "Reset", "reset"))
        self.permission_button.setText(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        self.request_mic_button.setText(
            _tr(self._locale, "Request Microphone Permission", "request_mic_permission")
        )
        self.hotkey_record_button.setText(
            _tr(self._locale, "Record custom hotkey", "hotkey_record_button")
        )
        self.hotkey_reset_default_button.setText(
            _tr(self._locale, "Reset to default (Fn)", "hotkey_reset_default")
        )
        self.hotkey_recommended_button.setText(
            _tr(
                self._locale,
                "Use recommended fallback (Right Option)",
                "hotkey_recommended_fallback",
            )
        )
        self.ui_locale_combo.setItemText(
            0, _tr(self._locale, "English", "ui_option_english")
        )
        self.ui_locale_combo.setItemText(
            1, _tr(self._locale, "Chinese", "ui_option_chinese")
        )
        for label, en_text, key in self._form_labels:
            label.setText(_tr(self._locale, en_text, key))
        self._refresh_custom_hotkey_preview()

    def _on_mode_changed(self, _index: int) -> None:
        self._update_cloud_field_visibility()

    def _update_cloud_field_visibility(self) -> None:
        is_cloud = str(self._mode_combo.currentData()) == "cloud"
        self._cloud_url_input.setVisible(is_cloud)
        self._cloud_key_input.setVisible(is_cloud)
        self.whisper_model_input.setVisible(not is_cloud)
        self.ollama_host_input.setVisible(not is_cloud)
        self.ollama_model_input.setVisible(not is_cloud)
        for label, _en, key in self._form_labels:
            if key in ("cloud_api_url", "cloud_api_key"):
                label.setVisible(is_cloud)
            elif key in ("whisper_model", "ollama_host", "ollama_model"):
                label.setVisible(not is_cloud)

    def _on_hotkey_mode_changed(self) -> None:
        self._apply_hotkey_control_state()

    def _apply_hotkey_control_state(self) -> None:
        current_mode = str(self.hotkey_combo.currentData())
        is_custom = current_mode == "custom"
        self.hotkey_record_button.setEnabled(is_custom)
        self.hotkey_custom_preview.setVisible(is_custom)
        self._refresh_custom_hotkey_preview()

    def _refresh_custom_hotkey_preview(self) -> None:
        if not self._custom_hotkey_tokens:
            text = _tr(
                self._locale,
                "No custom hotkey recorded yet.",
                "hotkey_custom_empty",
            )
            self.hotkey_custom_preview.setText(text)
            return
        value = label_for_hotkey_tokens(self._custom_hotkey_tokens)
        prefix = _tr(self._locale, "Custom:", "hotkey_custom_hint")
        self.hotkey_custom_preview.setText(f"{prefix} {value}")

    def _begin_custom_hotkey_record(self) -> None:
        dialog = CustomHotkeyCaptureDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        valid, reason, tokens = self._validate_custom_hotkey(set(dialog.captured_tokens))
        if not valid:
            QMessageBox.warning(self, "Talky", reason)
            self._refresh_custom_hotkey_preview()
            return

        self._custom_hotkey_tokens = tokens
        self._refresh_custom_hotkey_preview()
        QMessageBox.information(
            self,
            "Talky",
            f"Custom hotkey recorded: {label_for_hotkey_tokens(tokens)}",
        )

    def _validate_custom_hotkey(self, tokens: set[str]) -> tuple[bool, str, list[str]]:
        filtered = sorted(t for t in tokens if t)
        if not filtered:
            return False, "No valid key detected. Hold modifiers or function keys.", []

        if len(filtered) == 1 and filtered[0] in {"space", "enter"}:
            return False, "Single typing key is not allowed for hold-to-talk.", []

        token_set = set(filtered)
        if "cmd" in token_set and "space" in token_set:
            return False, "Cmd+Space conflicts with system shortcuts. Choose another hotkey.", []

        stable_tokens = {
            "alt",
            "cmd",
            "ctrl",
            "shift",
            "fn",
        }
        normalized = [t for t in filtered if t in stable_tokens]
        if not normalized:
            return False, "Only modifier keys are supported for custom hotkey.", []
        return True, "", normalized

    def _reset_default_hotkey(self) -> None:
        self.hotkey_combo.setCurrentIndex(self.hotkey_combo.findData("fn"))

    def _use_recommended_fallback_hotkey(self) -> None:
        self.hotkey_combo.setCurrentIndex(self.hotkey_combo.findData("right_option"))

    def _refresh_permission_status(self) -> None:
        mic_ok, _ = check_microphone_granted()
        ax_ok = is_accessibility_trusted(prompt=False)
        self.mic_status_value_label.setText(
            _tr(self._locale, "granted", "granted")
            if mic_ok
            else _tr(self._locale, "not granted", "not_granted")
        )
        self.ax_status_value_label.setText(
            _tr(self._locale, "granted", "granted")
            if ax_ok
            else _tr(self._locale, "not granted", "not_granted")
        )
        self.request_mic_button.setVisible(not mic_ok)
        self.permission_button.setVisible(not ax_ok)

    def _save_settings(self) -> None:
        terms = [
            line.strip()
            for line in self.dictionary_edit.toPlainText().splitlines()
            if line.strip()
        ]
        hotkey_mode = str(self.hotkey_combo.currentData())
        custom_hotkey = list(self._custom_hotkey_tokens)
        if hotkey_mode == "custom":
            valid, reason, normalized = self._validate_custom_hotkey(set(custom_hotkey))
            if not valid:
                QMessageBox.warning(self, "Talky", reason)
                return
            custom_hotkey = normalized

        selected_mode = str(self._mode_combo.currentData())
        selected_host = (
            self.ollama_host_input.text().strip().rstrip("/")
            or "http://127.0.0.1:11434"
        )
        selected_model = self.ollama_model_input.text().strip() or recommended_model_name()
        ok, reason = self._validate_mode_ready(
            mode=selected_mode,
            ollama_host=selected_host,
            ollama_model=selected_model,
        )
        if not ok:
            QMessageBox.warning(self, "Talky", reason)
            current_idx = self._mode_combo.findData(self.controller.settings.mode)
            if current_idx >= 0:
                self._mode_combo.setCurrentIndex(current_idx)
            return

        settings = AppSettings(
            custom_dictionary=terms,
            hotkey=hotkey_mode,
            custom_hotkey=custom_hotkey,
            whisper_model=self.whisper_model_input.text().strip() or "./local_whisper_model",
            ollama_model=selected_model,
            ollama_host=selected_host,
            ui_locale=str(self.ui_locale_combo.currentData()),
            language=self.language_input.text().strip() or "zh",
            auto_paste_delay_ms=self.paste_delay_input.value(),
            llm_debug_stream=self.llm_debug_stream_checkbox.isChecked(),
            sample_rate=self.controller.settings.sample_rate,
            channels=self.controller.settings.channels,
            mode=selected_mode,
            cloud_api_url=self._cloud_url_input.text().strip(),
            cloud_api_key=self._cloud_key_input.text().strip(),
        )
        # Delay hotkey listener rebuild until after the click event loop settles.
        # This avoids macOS input-source assertion crashes on some machines.
        QTimer.singleShot(0, lambda s=settings: self._apply_settings_deferred(s))

    def _validate_mode_ready(
        self,
        *,
        mode: str,
        ollama_host: str,
        ollama_model: str,
    ) -> tuple[bool, str]:
        """Require local/remote mode to be actually reachable before applying."""
        if mode == "cloud":
            return True, ""
        if mode not in {"local", "remote"}:
            return False, f"Unsupported mode: {mode}"

        from talky.models import list_ollama_models

        models = list_ollama_models(ollama_host)
        if not models:
            return (
                False,
                "Cannot reach Ollama or no models found on host: "
                f"{ollama_host}\n\n"
                "Please verify host/port and ensure at least one model is installed.",
            )
        if ollama_model not in models:
            preview = ", ".join(models[:6])
            return (
                False,
                f"Model '{ollama_model}' is not available on {ollama_host}.\n\n"
                f"Available models: {preview}",
            )
        return True, ""

    def _apply_settings_deferred(self, settings: AppSettings) -> None:
        self.controller.update_settings(settings)
        self._refresh_permission_status()
        QMessageBox.information(self, "Talky", _tr(settings.ui_locale, "Settings saved.", "saved"))

    def _reset_settings(self) -> None:
        confirm_msg = _tr(
            self._locale,
            "Reset all settings and restart Talky?\n"
            "This will delete ~/.talky/settings.json",
            "reset_confirm",
        )
        reply = QMessageBox.question(
            self,
            "Talky",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        config_path = Path.home() / ".talky" / "settings.json"
        try:
            config_path.unlink(missing_ok=True)
        except Exception:
            pass
        if _restart_current_process("settings_reset"):
            QApplication.quit()
            return
        QMessageBox.warning(
            self,
            "Talky",
            "Automatic restart failed. Please relaunch Talky manually.",
        )

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
        self._refresh_permission_status()

    def _request_microphone_permission(self) -> None:
        locale = str(self.ui_locale_combo.currentData())
        granted, detail = request_microphone_permission()
        self._refresh_permission_status()
        if granted:
            QMessageBox.information(
                self,
                "Talky",
                "Microphone permission granted.",
            )
            return
        QMessageBox.warning(
            self,
            "Talky",
            "Microphone permission missing."
            + "\nSystem Settings > Privacy & Security > Microphone."
            + (f"\nDetails: {detail}" if detail else ""),
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
        self._refresh_permission_status()
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
        self._last_error_message = ""
        self.dictionary_shortcut_listener = GlobalShortcutListener(
            on_trigger=self.controller.request_show_settings
        )
        self._ready_for_tray_click = False

        icon = self._load_tray_icon()
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("Talky - Local Voice Input Assistant")

        menu = QMenu()
        locale = self.controller.settings.ui_locale
        self.open_action = QAction(_tr(locale, "Dashboard", "open_dashboard"), menu)
        self.show_last_error_action = QAction(
            _tr(locale, "Error Message", "show_last_error"), menu
        )
        self.quit_action = QAction(_tr(locale, "Quit", "quit"), menu)
        menu.addAction(self.open_action)
        menu.addAction(self.show_last_error_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)

        self.open_action.triggered.connect(self.show_settings)
        self.show_last_error_action.triggered.connect(self._show_last_error_dialog)
        self.quit_action.triggered.connect(self.quit_app)
        self.show_last_error_action.setEnabled(False)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

        self.controller.status_signal.connect(self._show_status)
        self.controller.error_signal.connect(
            self._show_error, Qt.ConnectionType.QueuedConnection
        )
        self.controller.show_result_popup_signal.connect(self._show_result_popup)
        self.controller.show_settings_window_signal.connect(self.show_settings)
        self.controller.settings_updated.connect(self._on_settings_updated)

    def _load_tray_icon(self) -> QIcon:
        icon_2x_path = _asset_path("tray_icon@2x.png")
        icon_path = _asset_path("tray_icon.png")
        if icon_2x_path.exists():
            pixmap = QPixmap(str(icon_2x_path))
            pixmap.setDevicePixelRatio(2.0)
            icon = QIcon(pixmap)
        elif icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QIcon()
        if icon.isNull():
            icon = self.settings_window.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolume
            )
        icon.setIsMask(True)
        return icon

    def show(self) -> None:
        if self.tray.icon().isNull():
            self.tray.setIcon(self._load_tray_icon())
        icon = self.tray.icon()
        append_debug_log(
            f"TrayApp.show(): icon.isNull={icon.isNull()}, "
            f"availableSizes={icon.availableSizes()}, "
            f"isSystemTrayAvailable={QSystemTrayIcon.isSystemTrayAvailable()}"
        )
        self.tray.show()
        self.tray.setVisible(True)
        QTimer.singleShot(200, self._verify_tray_visible)
        self.dictionary_shortcut_listener.start()
        QTimer.singleShot(1500, self._enable_tray_click)
        locale = self.controller.settings.ui_locale
        self._show_status(_tr(locale, "Talky started. Hold hotkey to record.", "started"))

    def _verify_tray_visible(self) -> None:
        visible = self.tray.isVisible()
        append_debug_log(f"TrayApp._verify_tray_visible(): isVisible={visible}")
        if not visible:
            append_debug_log("Tray not visible after show(); retrying with fresh icon")
            self.tray.setIcon(self._load_tray_icon())
            self.tray.show()
            self.tray.setVisible(True)

    def _enable_tray_click(self) -> None:
        self._ready_for_tray_click = True

    def show_settings(self) -> None:
        if alert_if_local_ollama_unready(self.controller.config_store):
            self.controller.update_settings(self.controller.config_store.load())
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def quit_app(self) -> None:
        self.dictionary_shortcut_listener.stop()
        self.controller.stop()
        self.tray.hide()
        QApplication.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if not self._ready_for_tray_click:
            return
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_settings()

    def _show_status(self, message: str) -> None:
        self.tray.showMessage("Talky", message, QSystemTrayIcon.MessageIcon.Information, 1200)

    def _show_error(self, message: str) -> None:
        append_error_report(
            message,
            source="tray_error_signal",
            settings=self.controller.settings,
        )
        if message == "__MODEL_NOT_FOUND__":
            self._show_model_setup()
            return
        locale = self.controller.settings.ui_locale
        self._last_error_message = message
        self.show_last_error_action.setEnabled(True)
        self.tray.showMessage(
            f"Talky {_tr(locale, 'Error', 'error')}",
            message,
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )

    def _show_last_error_dialog(self) -> None:
        locale = self.controller.settings.ui_locale
        if not self._last_error_message:
            QMessageBox.information(
                self.settings_window,
                "Talky",
                _tr(locale, "No error yet.", "no_error_yet"),
            )
            return

        dialog = QDialog(self.settings_window)
        dialog.setWindowTitle(_tr(locale, "Last Error", "last_error_title"))
        dialog.resize(760, 360)

        layout = QVBoxLayout(dialog)
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(self._last_error_message)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        copy_button = QPushButton(_tr(locale, "Copy", "copy"))
        close_button = QPushButton(_tr(locale, "Close", "close"))
        copy_button.clicked.connect(lambda: pyperclip.copy(self._last_error_message))
        close_button.clicked.connect(dialog.accept)
        button_row.addWidget(copy_button)
        button_row.addWidget(close_button)

        layout.addWidget(details)
        layout.addLayout(button_row)
        dialog.exec()

    def _show_result_popup(self, text: str) -> None:
        self.result_popup.show_text(text, self.controller.settings.ui_locale)

    def _show_model_setup(self) -> None:
        if hasattr(self, "_model_dialog") and self._model_dialog.isVisible():
            return
        self._model_dialog = ModelSetupDialog(
            locale=self.controller.settings.ui_locale
        )
        self._model_dialog.model_configured.connect(self._on_model_configured)
        self._model_dialog.show()
        self._model_dialog.raise_()
        self._model_dialog.activateWindow()

    def _on_model_configured(self, model_value: str) -> None:
        settings = self.controller.settings
        settings.whisper_model = model_value
        self.controller.config_store.save(settings)
        self.tray.showMessage(
            "Talky",
            _tr(
                settings.ui_locale,
                "Download complete, restarting Talky…",
                "download_done_restarting",
            ),
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )
        QTimer.singleShot(400, self._restart_app)

    def _restart_app(self) -> None:
        self.dictionary_shortcut_listener.stop()
        self.controller.stop()
        self.tray.hide()
        if _restart_current_process("model_configured"):
            QApplication.quit()
            return
        # Restart failed: restore tray visibility so app doesn't look "dead".
        self.tray.show()
        QMessageBox.warning(
            self.settings_window,
            "Talky",
            "Automatic restart failed. Please relaunch Talky manually.",
        )

    def _on_settings_updated(self, settings: AppSettings) -> None:
        locale = settings.ui_locale
        self.open_action.setText(_tr(locale, "Dashboard", "open_dashboard"))
        self.show_last_error_action.setText(
            _tr(locale, "Error Message", "show_last_error")
        )
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


class _ModelDownloadThread(QThread):
    """Background thread for downloading whisper model from HuggingFace."""

    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, repo_id: str, parent=None) -> None:
        super().__init__(parent)
        self.repo_id = repo_id
        self.dl_bytes: int = 0
        self.dl_total: int = 0
        self.preparing_runtime = False

    def run(self) -> None:
        try:
            from huggingface_hub import snapshot_download
            from tqdm import tqdm as _tqdm_base

            thread_ref = self

            class _PollingTqdm(_tqdm_base):
                """Writes progress to shared ints instead of emitting Qt signals."""

                def __init__(self, *args, **kwargs):
                    kwargs.pop("name", None)
                    kwargs["disable"] = False
                    super().__init__(*args, **kwargs)

                def update(self, n=1):
                    super().update(n)
                    thread_ref.dl_bytes = int(self.n)
                    thread_ref.dl_total = int(self.total or 0)

                def display(self, *args, **kwargs):
                    pass

            path = snapshot_download(
                self.repo_id, tqdm_class=_PollingTqdm
            )
            self.preparing_runtime = True
            ok, detail = ensure_local_whisper_runtime()
            if not ok:
                self.failed.emit(f"Runtime setup failed: {detail}")
                return
            self.finished.emit(path)
        except Exception as exc:
            self.failed.emit(str(exc))


class ModelSetupDialog(QDialog):
    """Shown when whisper model is missing on first recording."""

    HF_REPO = "mlx-community/whisper-large-v3-mlx"
    model_configured = pyqtSignal(str)

    def __init__(self, locale: str = "en", parent=None) -> None:
        super().__init__(parent)
        self._locale = locale
        self._download_thread: _ModelDownloadThread | None = None
        self._in_runtime_prep = False
        self.setWindowTitle(
            _tr(locale, "Whisper Model Required", "model_setup_title")
        )
        self.setFixedSize(460, 310)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(0)

        title = QLabel(
            _tr(locale, "Whisper Model Required", "model_setup_title")
        )
        title.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #1D1D1F;"
        )
        layout.addWidget(title)
        layout.addSpacing(6)

        desc = QLabel(
            _tr(
                locale,
                "Talky needs a Whisper model for speech recognition.\n"
                "Choose to download or provide your own model path.",
                "model_setup_desc",
            )
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #6E6E73;")
        layout.addWidget(desc)
        layout.addSpacing(18)

        self._download_btn = QPushButton(
            _tr(locale, "Download Model (~3 GB)", "download_model")
        )
        self._download_btn.setStyleSheet(
            "QPushButton { background: qlineargradient("
            "x1:0,y1:0,x2:0,y2:1,stop:0 #F05A30,stop:1 #E04420);"
            "color: #FFF; font-size: 13px; font-weight: 500;"
            "border: 1px solid rgba(0,0,0,0.12); border-radius: 5px;"
            "padding: 7px 0; }"
            "QPushButton:hover { background: qlineargradient("
            "x1:0,y1:0,x2:0,y2:1,stop:0 #F86840,stop:1 #EE5030); }"
        )
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.clicked.connect(self._start_download)
        layout.addWidget(self._download_btn)
        layout.addSpacing(10)

        have_row = QHBoxLayout()
        self._have_btn = QPushButton(
            _tr(locale, "I have a model", "i_have_model")
        )
        self._have_btn.setStyleSheet(
            "QPushButton { background: #F2F2F7; color: #1D1D1F;"
            "font-size: 13px; border: 1px solid #D1D1D6;"
            "border-radius: 5px; padding: 7px 16px; }"
            "QPushButton:hover { background: #E8E8ED; }"
        )
        self._have_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._have_btn.clicked.connect(self._toggle_custom_input)
        have_row.addWidget(self._have_btn)
        have_row.addStretch()
        layout.addLayout(have_row)
        layout.addSpacing(8)

        self._custom_row = QHBoxLayout()
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText(
            _tr(
                locale,
                "Path or HuggingFace repo ID",
                "model_path_placeholder",
            )
        )
        self._custom_input.setStyleSheet(
            "QLineEdit { font-size: 13px; padding: 5px 8px;"
            "border: 1px solid #D1D1D6; border-radius: 5px; }"
        )
        self._custom_confirm = QPushButton(
            _tr(locale, "Confirm", "confirm_model")
        )
        self._custom_confirm.setStyleSheet(
            "QPushButton { background: #F2F2F7; color: #1D1D1F;"
            "font-size: 13px; border: 1px solid #D1D1D6;"
            "border-radius: 5px; padding: 5px 14px; }"
            "QPushButton:hover { background: #E8E8ED; }"
        )
        self._custom_confirm.clicked.connect(self._confirm_custom)
        self._custom_row.addWidget(self._custom_input, 1)
        self._custom_row.addWidget(self._custom_confirm)
        custom_widget = QWidget()
        custom_widget.setLayout(self._custom_row)
        custom_widget.setVisible(False)
        self._custom_widget = custom_widget
        layout.addWidget(custom_widget)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background: #E5E5EA; border: none; border-radius: 3px; }"
            "QProgressBar::chunk { background: #ED4A20; border-radius: 3px; }"
        )
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        layout.addSpacing(6)

        self._progress = QLabel("")
        self._progress.setStyleSheet("font-size: 12px; color: #86868B;")
        self._progress.setWordWrap(True)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        layout.addStretch()

    def _toggle_custom_input(self) -> None:
        visible = not self._custom_widget.isVisible()
        self._custom_widget.setVisible(visible)
        if visible:
            self._custom_input.setFocus()

    def _confirm_custom(self) -> None:
        value = self._custom_input.text().strip()
        if not value:
            return
        self.model_configured.emit(value)
        self.accept()

    def _start_download(self) -> None:
        self._download_btn.setEnabled(False)
        self._have_btn.setEnabled(False)
        self._custom_widget.setVisible(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._in_runtime_prep = False
        self._progress.setVisible(True)
        self._progress.setText(
            _tr(
                self._locale,
                "Downloading model… First download takes about 3–5 minutes.",
                "downloading_model",
            )
        )

        self._download_thread = _ModelDownloadThread(self.HF_REPO, self)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.failed.connect(self._on_download_failed)
        self._download_thread.start()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_progress)
        self._poll_timer.start(500)

    def _poll_progress(self) -> None:
        t = self._download_thread
        if t is None:
            return
        total = t.dl_total
        downloaded = t.dl_bytes
        if t.preparing_runtime:
            if not self._in_runtime_prep:
                self._progress_bar.setRange(0, 0)
                self._in_runtime_prep = True
            self._progress.setText(
                _tr(
                    self._locale,
                    "Preparing runtime environment…",
                    "preparing_runtime",
                )
            )
            return
        if total <= 0:
            return
        pct = min(int(downloaded * 100 / total), 100)
        self._progress_bar.setValue(pct)
        dl_gb = downloaded / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        self._progress.setText(
            f"Downloading… {dl_gb:.1f} GB / {total_gb:.1f} GB ({pct}%)"
        )

    def _on_download_finished(self, _path: str) -> None:
        if hasattr(self, "_poll_timer"):
            self._poll_timer.stop()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._progress.setText(
            _tr(
                self._locale,
                "Download complete! You can use voice input now.",
                "download_done",
            )
        )
        self._progress.setStyleSheet("font-size: 12px; color: #34C759;")
        self.model_configured.emit(self.HF_REPO)
        QTimer.singleShot(1200, self.accept)

    def _on_download_failed(self, error: str) -> None:
        if hasattr(self, "_poll_timer"):
            self._poll_timer.stop()
        self._progress_bar.setRange(0, 100)
        self._progress.setText(
            _tr(self._locale, "Download failed", "download_failed")
            + f": {error}"
        )
        self._progress.setStyleSheet("font-size: 12px; color: #FF3B30;")
        self._download_btn.setEnabled(True)
        self._have_btn.setEnabled(True)
