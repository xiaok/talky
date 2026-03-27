from __future__ import annotations

import os
import shlex
import subprocess
import sys
import pyperclip
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from talky.controller import AppController
from talky.dictionary_entries import DictionaryEntry, parse_dictionary_entries
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
from talky.version_checker import CURRENT_VERSION, VersionChecker

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

_ZH = {
    "save": "保存",
    "check_accessibility": "无障碍",
    "base_params": "基础参数",
    "hotkey": "热键",
    "whisper_model": "Whisper 模型",
    "ollama_model": "Ollama 模型",
    "ollama_host": "Ollama 地址",
    "asr_language": "ASR 语言",
    "ui_language": "UI 语言",
    "paste_delay": "粘贴延迟",
    "llm_debug_stream": "LLM 调试流输出",
    "saved": "已保存",
    "open_dashboard": "打开面板",
    "show_last_error": "错误信息",
    "no_error_yet": "暂无错误记录",
    "last_error_title": "最近错误",
    "copy": "复制",
    "close": "关闭",
    "access_granted": "无障碍权限已开启",
    "access_missing": "需要无障碍权限",
    "open_settings": "打开设置",
    "quit": "退出",
    "started": "已启动",
    "error": "错误",
    "popup_title": "无可用焦点",
    "popup_subtitle": "可复制后手动粘贴",
    "copy_close": "复制并关闭",
    "permission_status": "权限状态",
    "mic_permission": "麦克风权限",
    "accessibility_permission": "辅助功能权限",
    "granted": "已授权",
    "not_granted": "未授权",
    "request_mic_permission": "请求麦克风权限",
    "ui_option_english": "英文",
    "ui_option_chinese": "中文",
    "hotkey_record_button": "录制热键…",
    "hotkey_reset_default": "恢复默认",
    "hotkey_custom_hint": "当前自定义：",
    "hotkey_custom_empty": "尚未录制自定义热键",
    # Tabs
    "home": "主页",
    "history": "历史记录",
    "dictionary": "词典",
    "configs": "配置",
    # Home
    "support_us": "支持我们",
    "support_us_body": "Talky 用❤打造，不如去 GitHub 给我们点个 Star？",
    "star_on_github": "在 GitHub 上 Star",
    "update_available_msg": "发现新版本",
    "update_now": "立即更新",
    # Dictionary
    "new_word": "添加新词",
    "edit_word": "修改",
    "delete_word": "删除",
    "delete_confirm": "确认删除",
    "delete_confirm_msg": "确定要删除此词条吗？",
    "word_label": "词条",
    "type_label": "类型",
    "plain_term": "普通词条",
    "person_term": "人名",
    "no_words_yet": "暂无自定义词条",
    # History
    "no_history": "暂无历史记录",
    "select_date_hint": "选择日期查看记录",
    # General
    "cancel": "取消",
    "ok": "确认",
    # Model setup
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
    # Mode
    "processing_mode": "处理模式",
    "cloud_api_url": "Cloud API URL",
    "cloud_api_key": "Cloud API Key",
    # Prompt tab
    "prompt": "Prompt",
    "prompt_section_title": "LLM System Prompt",
    "prompt_hint": "使用 {dictionary} 插入自定义词典内容。留空则使用内置默认 Prompt。",
    "prompt_restore_default": "恢复默认",
}


def _tr(locale: str, en: str, key: str | None = None) -> str:
    if locale == "mixed" and key:
        return _ZH.get(key, en)
    return en


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


def _entry_to_line(entry: DictionaryEntry) -> str:
    if entry.kind == "person":
        return f"person:{entry.term}"
    return entry.term


def _load_pixmap(path: Path, height: int) -> QPixmap | None:
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return None
        ratio = QApplication.primaryScreen().devicePixelRatio() if QApplication.primaryScreen() else 2.0
        scaled = pixmap.scaledToHeight(
            int(height * ratio), Qt.TransformationMode.SmoothTransformation
        )
        scaled.setDevicePixelRatio(ratio)
        return scaled
    except Exception:
        return None


def _make_keycap(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Keycap")
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lbl


def _restart_command() -> list[str]:
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
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


# ---------------------------------------------------------------------------
# StyledComboBox – QComboBox with a visible chevron arrow
# ---------------------------------------------------------------------------

class StyledComboBox(QComboBox):
    """QComboBox subclass that draws a visible chevron arrow on the right."""

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#8E8E93"), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        cx = self.width() - 14
        cy = self.height() // 2
        p.drawLine(cx - 4, cy - 2, cx, cy + 2)
        p.drawLine(cx, cy + 2, cx + 4, cy - 2)
        p.end()


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

NATIVE_STYLESHEET = """
/* ---- Global ---- */
QWidget {
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", "PingFang SC";
    font-size: 13px;
    color: #1D1D1F;
}

/* ---- Segmented tab bar ---- */
QFrame#SegmentedBar {
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

QPushButton#SegmentTab {
    background: transparent;
    color: #86868B;
    font-size: 12px;
    font-weight: 500;
    padding: 5px 18px;
    border-radius: 5px;
    border: none;
    min-width: 56px;
}

QPushButton#SegmentTab:checked {
    background: #FFFFFF;
    color: #ED4A20;
    font-weight: 600;
}

QPushButton#SegmentTab:hover:!checked {
    color: #1D1D1F;
}

/* ---- Form controls ---- */
QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    background: #FFFFFF;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: rgba(237, 74, 32, 0.3);
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid rgba(237, 74, 32, 0.55);
    padding: 3px 7px;
}

QComboBox {
    padding-right: 26px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    right: 2px;
    border: none;
}

QComboBox::down-arrow {
    width: 0; height: 0;
}

QSpinBox::up-button, QSpinBox::down-button {
    border: none;
    width: 16px;
}

QSpinBox::up-button { subcontrol-position: top right; }
QSpinBox::down-button { subcontrol-position: bottom right; }

/* ---- Buttons ---- */
QPushButton {
    border: none;
    border-radius: 5px;
    padding: 5px 12px;
    font-weight: 500;
    font-size: 13px;
}

QPushButton#PrimaryButton {
    background: #ED4A20;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background: #F45B2F;
}

QPushButton#SecondaryButton {
    background: #F2F2F7;
    color: #1D1D1F;
    border: 1px solid #D1D1D6;
}

QPushButton#SecondaryButton:hover {
    background: #E5E5EA;
}

QPushButton#LinkButton {
    background: transparent;
    color: #ED4A20;
    border: none;
    padding: 2px 0px;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#LinkButton:hover {
    color: #F45B2F;
}

/* ---- Typography ---- */
QLabel#WindowTitle {
    font-size: 28px;
    font-weight: 800;
    color: #1D1D1F;
}

QLabel#VersionLabel {
    font-size: 12px;
    font-weight: 300;
    color: #AEAEB2;
}

QLabel#WindowSubtitle {
    font-size: 12px;
    color: #86868B;
}

QLabel#CardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #1D1D1F;
}

QLabel#FormLabel {
    font-size: 13px;
    color: #3A3A3C;
}

/* ---- Keycap badge ---- */
QLabel#Keycap {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FCFCFC, stop:1 #ECECEC);
    border-top: 1px solid #D8D8DC;
    border-left: 1px solid #C7C7CC;
    border-right: 1px solid #C7C7CC;
    border-bottom: 2px solid #AEAEB2;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 12px;
    font-family: "SF Mono", "Menlo", monospace;
    font-weight: 600;
    color: #3A3A3C;
}

/* ---- Section frame ---- */
QFrame#SectionFrame {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 10px;
}

/* ---- History sidebar ---- */
QPushButton#DateItem {
    background: transparent;
    color: #3A3A3C;
    font-size: 12px;
    font-weight: 500;
    padding: 6px 10px;
    border-radius: 5px;
    border: none;
    text-align: left;
}

QPushButton#DateItem:checked {
    background: rgba(237, 74, 32, 0.08);
    color: #ED4A20;
    font-weight: 600;
}

QPushButton#DateItem:hover:!checked {
    background: rgba(0, 0, 0, 0.04);
}

/* ---- Chat bubble ---- */
QFrame#ChatBubble {
    background: #F2F2F7;
    border: none;
    border-radius: 14px;
    border-top-left-radius: 4px;
}

/* ---- Word card ---- */
QFrame#WordCard {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

QPushButton#WordActionButton {
    background: transparent;
    color: #86868B;
    font-size: 11px;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 4px;
    border: none;
}

QPushButton#WordActionButton:hover {
    background: rgba(237, 74, 32, 0.08);
    color: #ED4A20;
}

/* ---- Update banner ---- */
QFrame#UpdateBanner {
    background: rgba(237, 74, 32, 0.06);
    border: 1px solid rgba(237, 74, 32, 0.15);
    border-radius: 8px;
}

/* ---- Instruction / Refer card ---- */
QFrame#InstructionCard, QFrame#ReferCard {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 8px;
}

/* ---- Radio & Checkbox ---- */
QRadioButton {
    spacing: 6px;
    font-size: 13px;
    color: #1D1D1F;
}

QCheckBox {
    spacing: 6px;
    font-size: 13px;
}

/* ---- Scroll bars ---- */
QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    width: 7px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.12);
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}

QScrollBar:horizontal {
    height: 0;
}

/* ---- Text views ---- */
QPlainTextEdit {
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    background: #FFFFFF;
    padding: 6px;
    font-family: "SF Mono", "Menlo", monospace;
    font-size: 12px;
    selection-background-color: rgba(237, 74, 32, 0.3);
}

QTextEdit#ResultPanel {
    background: #FFFFFF;
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    padding: 6px;
}

/* ---- Message boxes ---- */
QMessageBox {
    background: #FFFFFF;
}

QMessageBox QLabel {
    color: #1D1D1F;
}

QMessageBox QPushButton {
    background: #F2F2F7;
    color: #1D1D1F;
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    padding: 4px 14px;
    min-width: 60px;
}

/* ---- Popup card ---- */
QFrame#PopupCard {
    background: rgba(255, 255, 255, 245);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
}

/* ---- Progress bar ---- */
QProgressBar {
    background: #E5E5EA;
    border: none;
    border-radius: 3px;
}

QProgressBar::chunk {
    background: #ED4A20;
    border-radius: 3px;
}
"""

IOS26_STYLESHEET = NATIVE_STYLESHEET


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

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


class WordEditDialog(QDialog):
    def __init__(self, parent=None, term="", kind="term", locale="en"):
        super().__init__(parent)
        self._locale = locale
        is_new = not term
        self.setWindowTitle(
            _tr(locale, "Add Word", "new_word") if is_new
            else _tr(locale, "Edit Word", "edit_word")
        )
        self.setModal(True)
        self.resize(380, 190)
        self.setStyleSheet(NATIVE_STYLESHEET)

        self.term_input = QLineEdit(term)
        self.term_input.setPlaceholderText(_tr(locale, "Enter word or phrase...", None))

        self.kind_combo = StyledComboBox()
        self.kind_combo.addItem(_tr(locale, "Plain term", "plain_term"), userData="term")
        self.kind_combo.addItem(_tr(locale, "Person name", "person_term"), userData="person")
        if kind == "person":
            self.kind_combo.setCurrentIndex(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(_tr(locale, "Cancel", "cancel"))
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton(_tr(locale, "OK", "ok"))
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        word_lbl = QLabel(_tr(locale, "Word", "word_label"))
        word_lbl.setObjectName("FormLabel")
        layout.addWidget(word_lbl)
        layout.addWidget(self.term_input)
        type_lbl = QLabel(_tr(locale, "Type", "type_label"))
        type_lbl.setObjectName("FormLabel")
        layout.addWidget(type_lbl)
        layout.addWidget(self.kind_combo)
        layout.addLayout(btn_row)

    def get_result(self) -> tuple[str, str]:
        return self.term_input.text().strip(), str(self.kind_combo.currentData())


# ---------------------------------------------------------------------------
# Dictionary word card
# ---------------------------------------------------------------------------

class DictionaryWordCard(QFrame):
    def __init__(
        self,
        index: int,
        entry: DictionaryEntry,
        on_edit,
        on_delete,
        locale: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self.entry = entry
        self.setObjectName("WordCard")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(6)

        if entry.kind == "person":
            initial = entry.term[0].upper() if entry.term else "P"
            badge = QLabel(initial)
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "background: rgba(237,74,32,0.08); border-radius: 11px;"
                " font-size: 11px; font-weight: 600; color: #ED4A20;"
            )
            layout.addWidget(badge)

        term_label = QLabel(entry.term)
        term_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(term_label)
        layout.addStretch()

        self._edit_btn = QPushButton(_tr(locale, "Edit", "edit_word"))
        self._edit_btn.setObjectName("WordActionButton")
        self._edit_btn.setFixedHeight(22)
        self._edit_btn.setVisible(False)
        self._edit_btn.clicked.connect(lambda: on_edit(self._index))

        self._del_btn = QPushButton(_tr(locale, "Delete", "delete_word"))
        self._del_btn.setObjectName("WordActionButton")
        self._del_btn.setFixedHeight(22)
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(lambda: on_delete(self._index))

        layout.addWidget(self._edit_btn)
        layout.addWidget(self._del_btn)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._edit_btn.setVisible(True)
        self._del_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._edit_btn.setVisible(False)
        self._del_btn.setVisible(False)
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
# Tab: Home
# ---------------------------------------------------------------------------

class HomeTab(QWidget):
    def __init__(self, controller: AppController, locale: str = "en", parent=None):
        super().__init__(parent)
        self.controller = controller
        self._locale = locale

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _load_pixmap(_asset_path("talky-logo.png"), 96)
        if pixmap is None:
            pixmap = _load_pixmap(_asset_path("talky_installer.png"), 96)
        if pixmap is not None:
            logo_label.setPixmap(pixmap)
        layout.addWidget(logo_label)

        title = QLabel("Talky")
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"v{CURRENT_VERSION}")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(4)

        instruction_card = QFrame()
        instruction_card.setObjectName("InstructionCard")
        ic_layout = QVBoxLayout(instruction_card)
        ic_layout.setContentsMargins(16, 14, 16, 14)
        ic_layout.setSpacing(10)

        _hint_style = "font-size: 13px; color: #3A3A3C;"

        line1 = QHBoxLayout()
        line1.setSpacing(5)
        line1.setContentsMargins(0, 0, 0, 0)
        line1.addStretch()
        _l1a = QLabel("Hold")
        _l1a.setStyleSheet(_hint_style)
        line1.addWidget(_l1a)
        line1.addWidget(_make_keycap("Fn"))
        _l1b = QLabel("to dictate. Release to transcribe.")
        _l1b.setStyleSheet(_hint_style)
        line1.addWidget(_l1b)
        line1.addStretch()
        ic_layout.addLayout(line1)

        line2 = QHBoxLayout()
        line2.setSpacing(5)
        line2.setContentsMargins(0, 0, 0, 0)
        line2.addStretch()
        _l2a = QLabel("Press")
        _l2a.setStyleSheet(_hint_style)
        line2.addWidget(_l2a)
        line2.addWidget(_make_keycap("\u2303"))
        line2.addWidget(_make_keycap("\u2325"))
        line2.addWidget(_make_keycap("\u2318"))
        _l2b = QLabel("to open Dashboard.")
        _l2b.setStyleSheet(_hint_style)
        line2.addWidget(_l2b)
        line2.addStretch()
        ic_layout.addLayout(line2)

        layout.addWidget(instruction_card)

        self._update_banner = QFrame()
        self._update_banner.setObjectName("UpdateBanner")
        self._update_banner.setVisible(False)
        ub_layout = QHBoxLayout(self._update_banner)
        ub_layout.setContentsMargins(12, 10, 12, 10)
        self._update_text = QLabel()
        self._update_text.setObjectName("WindowSubtitle")
        self._update_text.setWordWrap(True)
        self._update_button = QPushButton(
            _tr(self._locale, "Update Now", "update_now")
        )
        self._update_button.setObjectName("PrimaryButton")
        self._update_url = ""
        self._update_button.clicked.connect(self._on_update_clicked)
        ub_layout.addWidget(self._update_text, 1)
        ub_layout.addWidget(self._update_button)
        layout.addWidget(self._update_banner)

        support_card = QFrame()
        support_card.setObjectName("SectionFrame")
        sc_layout = QVBoxLayout(support_card)
        sc_layout.setContentsMargins(14, 12, 14, 14)
        sc_layout.setSpacing(8)

        self._support_title = QLabel(
            _tr(self._locale, "Support Us", "support_us")
        )
        self._support_title.setObjectName("CardTitle")
        sc_layout.addWidget(self._support_title)

        body_row = QHBoxLayout()
        body_row.setSpacing(5)
        body_row.setContentsMargins(0, 0, 0, 0)
        heart = QLabel("\u2764\ufe0f")
        heart.setStyleSheet("font-size: 14px;")
        heart.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        body_row.addWidget(heart)
        self._support_body = QLabel(
            _tr(
                self._locale,
                "Talky is built with love \u2014 why not give us a star on GitHub?",
                "support_us_body",
            )
        )
        self._support_body.setWordWrap(True)
        self._support_body.setStyleSheet("font-size: 13px; color: #3A3A3C;")
        body_row.addWidget(self._support_body, 1)
        sc_layout.addLayout(body_row)

        self._github_button = QPushButton(
            "\u2605  " + _tr(self._locale, "Star on GitHub", "star_on_github")
        )
        self._github_button.setObjectName("SecondaryButton")
        self._github_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._github_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/shintemy/talky")
            )
        )
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addWidget(self._github_button)
        btn_row.addStretch()
        sc_layout.addLayout(btn_row)

        layout.addWidget(support_card)

        layout.addStretch(1)

        self._version_checker = VersionChecker()
        self._version_checker.update_available.connect(self._on_update_available)
        QTimer.singleShot(1500, self._version_checker.check_async)

    def _on_update_available(self, version: str, url: str) -> None:
        self._update_url = url
        msg = _tr(self._locale, "New version available", "update_available_msg")
        self._update_text.setText(f"{msg}: v{version}")
        self._update_button.setText(
            _tr(self._locale, "Update Now", "update_now")
        )
        self._update_banner.setVisible(True)

    def _on_update_clicked(self) -> None:
        if self._update_url:
            QDesktopServices.openUrl(QUrl(self._update_url))

    def update_locale(self, locale: str) -> None:
        self._locale = locale
        self._support_title.setText(_tr(locale, "Support Us", "support_us"))
        self._support_body.setText(
            _tr(
                locale,
                "Talky is built with love \u2014 why not give us a star on GitHub?",
                "support_us_body",
            )
        )
        self._github_button.setText(
            "\u2605  " + _tr(locale, "Star on GitHub", "star_on_github")
        )
        self._update_button.setText(_tr(locale, "Update Now", "update_now"))


# ---------------------------------------------------------------------------
# Tab: History
# ---------------------------------------------------------------------------

class HistoryTab(QWidget):
    def __init__(self, controller: AppController, locale: str = "en", parent=None):
        super().__init__(parent)
        self.controller = controller
        self._locale = locale

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar_widget = QWidget()
        self._sidebar_layout = QVBoxLayout(self._sidebar_widget)
        self._sidebar_layout.setContentsMargins(8, 12, 8, 12)
        self._sidebar_layout.setSpacing(2)

        self._date_group = QButtonGroup(self)
        self._date_group.setExclusive(True)
        self._date_group.buttonClicked.connect(self._on_date_selected)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setWidget(self._sidebar_widget)
        sidebar_scroll.setFixedWidth(150)
        layout.addWidget(sidebar_scroll)

        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.08);")
        layout.addWidget(separator)

        self._content_area = QWidget()
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(10)

        self._hint_label = QLabel(_tr(locale, "Select a date to view history", "select_date_hint"))
        self._hint_label.setObjectName("WindowSubtitle")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(self._hint_label)
        self._content_layout.addStretch()

        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_scroll.setWidget(self._content_area)
        layout.addWidget(content_scroll, 1)

    def refresh(self) -> None:
        for btn in list(self._date_group.buttons()):
            self._date_group.removeButton(btn)
            btn.setParent(None)
            btn.deleteLater()

        _clear_layout(self._sidebar_layout)

        dates = self.controller.history_store.list_dates()
        if not dates:
            empty = QLabel(_tr(self._locale, "No history yet", "no_history"))
            empty.setObjectName("WindowSubtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._sidebar_layout.addWidget(empty)
            self._sidebar_layout.addStretch()
            return

        for date_str in dates:
            btn = QPushButton(date_str)
            btn.setObjectName("DateItem")
            btn.setCheckable(True)
            btn.setProperty("date", date_str)
            self._date_group.addButton(btn)
            self._sidebar_layout.addWidget(btn)
        self._sidebar_layout.addStretch()

        _clear_layout(self._content_layout)
        self._hint_label = QLabel(_tr(self._locale, "Select a date to view history", "select_date_hint"))
        self._hint_label.setObjectName("WindowSubtitle")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(self._hint_label)
        self._content_layout.addStretch()

    def _on_date_selected(self, btn) -> None:
        date_str = btn.property("date")
        self._show_entries(date_str)

    def _show_entries(self, date_str: str) -> None:
        _clear_layout(self._content_layout)
        entries = self.controller.history_store.read_entries(date_str)
        if not entries:
            empty = QLabel(_tr(self._locale, "No history yet", "no_history"))
            empty.setObjectName("WindowSubtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch()
            return

        for time_str, text in entries:
            bubble = QFrame()
            bubble.setObjectName("ChatBubble")
            b_layout = QVBoxLayout(bubble)
            b_layout.setContentsMargins(14, 10, 14, 10)
            b_layout.setSpacing(4)
            time_label = QLabel(time_str)
            time_label.setStyleSheet("font-size: 11px; color: #86868B; font-weight: 500;")
            b_layout.addWidget(time_label)
            text_label = QLabel(text)
            text_label.setWordWrap(True)
            text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text_label.setStyleSheet("font-size: 13px; color: #1D1D1F;")
            b_layout.addWidget(text_label)
            self._content_layout.addWidget(bubble)

        self._content_layout.addStretch()


# ---------------------------------------------------------------------------
# Tab: Dictionary
# ---------------------------------------------------------------------------

class DictionaryTab(QWidget):
    def __init__(self, controller: AppController, locale: str = "en", parent=None):
        super().__init__(parent)
        self.controller = controller
        self._locale = locale
        self._entries: list[DictionaryEntry] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 8, 24, 8)
        outer.setSpacing(12)

        top_row = QHBoxLayout()
        self._new_word_btn = QPushButton(
            "+ " + _tr(self._locale, "New Word", "new_word")
        )
        self._new_word_btn.setObjectName("SecondaryButton")
        self._new_word_btn.clicked.connect(self._on_add_word)
        top_row.addWidget(self._new_word_btn)
        top_row.addStretch()
        outer.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(6)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)
        self._grid_layout.setColumnStretch(2, 1)
        scroll.setWidget(self._grid_container)
        outer.addWidget(scroll, 1)

        self._empty_label = QLabel(
            _tr(self._locale, "No custom words yet", "no_words_yet")
        )
        self._empty_label.setObjectName("WindowSubtitle")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)
        outer.addWidget(self._empty_label)

        self.refresh_from_settings(controller.settings)

    def refresh(self) -> None:
        self.refresh_from_settings(self.controller.settings)

    def refresh_from_settings(self, settings: AppSettings) -> None:
        raw_lines = [ln for ln in settings.custom_dictionary if ln.strip()]
        self._entries = parse_dictionary_entries(raw_lines)
        self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        _clear_layout(self._grid_layout)
        self._empty_label.setVisible(not self._entries)
        for i, entry in enumerate(self._entries):
            card = DictionaryWordCard(
                index=i, entry=entry,
                on_edit=self._on_edit_word,
                on_delete=self._on_delete_word,
                locale=self._locale,
            )
            self._grid_layout.addWidget(card, i // 3, i % 3)

    def _on_add_word(self) -> None:
        dialog = WordEditDialog(parent=self, locale=self._locale)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term, kind = dialog.get_result()
        if not term:
            return
        self._entries.append(DictionaryEntry(term=term, kind=kind))
        self._save_and_rebuild()

    def _on_edit_word(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            return
        entry = self._entries[index]
        dialog = WordEditDialog(
            parent=self, term=entry.term, kind=entry.kind, locale=self._locale
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term, kind = dialog.get_result()
        if not term:
            return
        self._entries[index] = DictionaryEntry(term=term, kind=kind)
        self._save_and_rebuild()

    def _on_delete_word(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            return
        entry = self._entries[index]
        reply = QMessageBox.question(
            self,
            _tr(self._locale, "Confirm Delete", "delete_confirm"),
            _tr(self._locale, "Delete this word?", "delete_confirm_msg")
            + f'\n\n"{entry.term}"',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._entries[index]
        self._save_and_rebuild()

    def _save_and_rebuild(self) -> None:
        lines = [_entry_to_line(e) for e in self._entries]
        self.controller.update_dictionary(lines)
        self._rebuild_grid()

    def update_locale(self, locale: str) -> None:
        self._locale = locale
        self._new_word_btn.setText("+ " + _tr(locale, "New Word", "new_word"))
        self._empty_label.setText(_tr(locale, "No custom words yet", "no_words_yet"))
        self._rebuild_grid()


# ---------------------------------------------------------------------------
# Tab: Prompt
# ---------------------------------------------------------------------------

class PromptTab(QWidget):
    def __init__(self, controller: AppController, locale: str = "en", parent=None):
        super().__init__(parent)
        self.controller = controller
        self._locale = locale

        from talky.prompting import DEFAULT_LLM_PROMPT_TEMPLATE

        self._default_template = DEFAULT_LLM_PROMPT_TEMPLATE

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 8, 0, 0)
        content_layout.setSpacing(12)

        section = QFrame()
        section.setObjectName("SectionFrame")
        sec_layout = QVBoxLayout(section)
        sec_layout.setContentsMargins(16, 14, 16, 14)
        sec_layout.setSpacing(10)

        self._title_label = QLabel(
            _tr(locale, "LLM System Prompt", "prompt_section_title")
        )
        self._title_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #1D1D1F;"
        )
        sec_layout.addWidget(self._title_label)

        self._editor = QPlainTextEdit()
        self._editor.setMinimumHeight(260)
        self._editor.setStyleSheet(
            "QPlainTextEdit { font-size: 12px; font-family: 'Menlo', monospace;"
            " border: 1px solid #D1D1D6; border-radius: 5px; background: #FFFFFF;"
            " padding: 8px; color: #1D1D1F; }"
            "QPlainTextEdit:focus { border: 2px solid rgba(237, 74, 32, 0.55); padding: 7px; }"
        )
        sec_layout.addWidget(self._editor)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(0)
        self._hint_label = QLabel(
            _tr(
                locale,
                "Use {dictionary} to insert custom dictionary terms. "
                "Leave empty to use the built-in default.",
                "prompt_hint",
            )
        )
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet("font-size: 11px; color: #86868B;")
        hint_row.addWidget(self._hint_label, 1)
        hint_row.addSpacing(12)

        self._restore_btn = QPushButton(
            _tr(locale, "Restore Default", "prompt_restore_default")
        )
        self._restore_btn.setObjectName("LinkButton")
        self._restore_btn.setStyleSheet(
            "QPushButton#LinkButton { color: #ED4A20; font-size: 11px; }"
            "QPushButton#LinkButton:hover { color: #C43A18; text-decoration: underline; }"
        )
        self._restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restore_btn.clicked.connect(self._restore_default)
        hint_row.addWidget(self._restore_btn)
        sec_layout.addLayout(hint_row)

        content_layout.addWidget(section)
        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        template = settings.custom_llm_prompt or self._default_template
        if self._editor.toPlainText() != template:
            self._editor.setPlainText(template)
        self._apply_locale_texts()

    def collect_prompt(self) -> str:
        text = self._editor.toPlainText().strip()
        if text == self._default_template.strip():
            return ""
        return text

    def _restore_default(self) -> None:
        self._editor.setPlainText(self._default_template)

    def _apply_locale_texts(self) -> None:
        self._title_label.setText(
            _tr(self._locale, "LLM System Prompt", "prompt_section_title")
        )
        self._hint_label.setText(
            _tr(
                self._locale,
                "Use {dictionary} to insert custom dictionary terms. "
                "Leave empty to use the built-in default.",
                "prompt_hint",
            )
        )
        self._restore_btn.setText(
            _tr(self._locale, "Restore Default", "prompt_restore_default")
        )

    def update_locale(self, locale: str) -> None:
        self._locale = locale
        self._apply_locale_texts()


# ---------------------------------------------------------------------------
# Tab: Configs (merged — old structure + new features)
# ---------------------------------------------------------------------------

class ConfigsTab(QWidget):
    def __init__(self, controller: AppController, locale: str = "en", parent=None):
        super().__init__(parent)
        self.controller = controller
        self._locale = locale
        self._custom_hotkey_tokens: list[str] = []
        self._form_labels: list[tuple[QLabel, str, str]] = []

        # ---- Processing Mode ----
        self._mode_combo = StyledComboBox()
        self._mode_combo.addItem("Local (Free)", userData="local")
        self._mode_combo.addItem("Remote Ollama (LAN)", userData="remote")
        self._mode_combo.addItem("Cloud (Subscription)", userData="cloud")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._cloud_url_input = QLineEdit()
        self._cloud_url_input.setPlaceholderText("http://192.168.x.x:8000")
        self._cloud_key_input = QLineEdit()
        self._cloud_key_input.setPlaceholderText("sk-talky-...")
        self._cloud_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        # ---- Hotkey radio group ----
        self._hotkey_button_group = QButtonGroup(self)
        self._hotkey_mode_map: dict[int, str] = {}
        self._hotkey_id_for_mode: dict[str, int] = {}

        _HOTKEY_OPTIONS = [
            ("fn", "Fn / Globe (Default)", "fn"),
            ("right_option", "Right Option", "\u2325"),
            ("right_command", "Right Command", "\u2318"),
            ("command_option", "Command + Option", "\u2318 \u2325"),
            ("custom", "Custom", None),
        ]

        hotkey_group = QVBoxLayout()
        hotkey_group.setSpacing(4)
        hotkey_group.setContentsMargins(0, 0, 0, 0)

        for i, (mode, label_text, keycap_text) in enumerate(_HOTKEY_OPTIONS):
            self._hotkey_mode_map[i] = mode
            self._hotkey_id_for_mode[mode] = i

            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(0, 0, 0, 0)
            radio = QRadioButton(label_text)
            self._hotkey_button_group.addButton(radio, i)
            row.addWidget(radio)
            if keycap_text:
                row.addWidget(_make_keycap(keycap_text))
            row.addStretch()
            hotkey_group.addLayout(row)

        self._custom_area = QWidget()
        custom_row = QHBoxLayout(self._custom_area)
        custom_row.setContentsMargins(22, 2, 0, 0)
        custom_row.setSpacing(8)
        self.hotkey_record_button = QPushButton(
            _tr(self._locale, "Record Hotkey\u2026", "hotkey_record_button")
        )
        self.hotkey_record_button.setObjectName("SecondaryButton")
        self.hotkey_record_button.clicked.connect(self._begin_custom_hotkey_record)
        self.hotkey_custom_preview = QLabel("")
        self.hotkey_custom_preview.setObjectName("WindowSubtitle")
        custom_row.addWidget(self.hotkey_record_button)
        custom_row.addWidget(self.hotkey_custom_preview)
        custom_row.addStretch()
        hotkey_group.addWidget(self._custom_area)

        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 2, 0, 0)
        self.hotkey_reset_link = QPushButton(
            _tr(self._locale, "Reset to Default", "hotkey_reset_default")
        )
        self.hotkey_reset_link.setObjectName("LinkButton")
        self.hotkey_reset_link.clicked.connect(self._reset_default_hotkey)
        reset_row.addWidget(self.hotkey_reset_link)
        reset_row.addStretch()
        hotkey_group.addLayout(reset_row)

        self.hotkey_widget = QWidget()
        self.hotkey_widget.setLayout(hotkey_group)

        self._hotkey_button_group.idClicked.connect(self._on_hotkey_mode_changed)

        # ---- Other form widgets ----
        self.whisper_model_combo = StyledComboBox()
        self.whisper_model_combo.addItem("mlx-community/whisper-large-v3-mlx")

        self.language_combo = StyledComboBox()
        self.language_combo.addItem("中文", userData="zh")
        self.language_combo.addItem("English", userData="en")
        self.language_combo.addItem("日本語", userData="ja")
        self.language_combo.addItem("한국어", userData="ko")
        self.language_combo.addItem("Deutsch", userData="de")
        self.language_combo.addItem("Français", userData="fr")
        self.language_combo.addItem("Español", userData="es")

        self.ollama_host_input = QLineEdit()
        self.ollama_host_input.setPlaceholderText("http://127.0.0.1:11434")
        self.ollama_host_input.editingFinished.connect(
            lambda: self._populate_ollama_models(self.ollama_host_input.text().strip())
        )

        self.ollama_model_combo = StyledComboBox()

        self.ui_locale_combo = StyledComboBox()
        self.ui_locale_combo.addItem(
            _tr(self._locale, "English", "ui_option_english"), userData="en"
        )
        self.ui_locale_combo.addItem(
            _tr(self._locale, "Chinese", "ui_option_chinese"), userData="mixed"
        )

        # ---- Permission widgets ----
        self.mic_permission_label = QLabel(
            _tr(self._locale, "Microphone", "mic_permission")
        )
        self.mic_permission_label.setObjectName("FormLabel")
        self.mic_permission_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.mic_status_value_label = QLabel("")

        self.ax_permission_label = QLabel(
            _tr(self._locale, "Accessibility", "accessibility_permission")
        )
        self.ax_permission_label.setObjectName("FormLabel")
        self.ax_permission_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.ax_status_value_label = QLabel("")

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

        # ---- Form grid (right-aligned labels) ----
        form = QGridLayout()
        form.setColumnMinimumWidth(0, 120)
        form.setColumnStretch(0, 0)
        form.setColumnStretch(1, 1)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        fields = [
            ("Processing Mode", "processing_mode", self._mode_combo),
            ("Cloud API URL", "cloud_api_url", self._cloud_url_input),
            ("Cloud API Key", "cloud_api_key", self._cloud_key_input),
            ("Record Hotkey", "hotkey", self.hotkey_widget),
            ("Whisper Model", "whisper_model", self.whisper_model_combo),
            ("ASR Language", "asr_language", self.language_combo),
            ("Ollama Host", "ollama_host", self.ollama_host_input),
            ("Ollama Model", "ollama_model", self.ollama_model_combo),
            ("UI Language", "ui_language", self.ui_locale_combo),
        ]
        for row_idx, (en_text, key, widget) in enumerate(fields):
            label = QLabel(_tr(self._locale, en_text, key))
            label.setObjectName("FormLabel")
            v_align = (
                Qt.AlignmentFlag.AlignTop if key in ("hotkey",)
                else Qt.AlignmentFlag.AlignVCenter
            )
            label.setAlignment(Qt.AlignmentFlag.AlignRight | v_align)
            form.addWidget(label, row_idx, 0)
            form.addWidget(widget, row_idx, 1)
            self._form_labels.append((label, en_text, key))

        # ---- Permission grid ----
        perm_grid = QGridLayout()
        perm_grid.setColumnMinimumWidth(0, 120)
        perm_grid.setColumnStretch(0, 0)
        perm_grid.setColumnStretch(1, 0)
        perm_grid.setColumnStretch(2, 1)
        perm_grid.setHorizontalSpacing(12)
        perm_grid.setVerticalSpacing(8)
        perm_grid.addWidget(self.mic_permission_label, 0, 0)
        perm_grid.addWidget(self.mic_status_value_label, 0, 1)
        perm_grid.addWidget(self.request_mic_button, 0, 2)
        perm_grid.addWidget(self.ax_permission_label, 1, 0)
        perm_grid.addWidget(self.ax_status_value_label, 1, 1)
        perm_grid.addWidget(self.permission_button, 1, 2)

        # ---- Assemble layout ----
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 12, 24, 16)
        content_layout.setSpacing(16)

        params_section = QFrame()
        params_section.setObjectName("SectionFrame")
        ps_layout = QVBoxLayout(params_section)
        ps_layout.setContentsMargins(16, 14, 16, 14)
        ps_layout.setSpacing(10)
        self._params_card_title = QLabel(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        self._params_card_title.setObjectName("CardTitle")
        ps_layout.addWidget(self._params_card_title)
        ps_layout.addLayout(form)
        content_layout.addWidget(params_section)

        perm_section = QFrame()
        perm_section.setObjectName("SectionFrame")
        pm_layout = QVBoxLayout(perm_section)
        pm_layout.setContentsMargins(16, 14, 16, 14)
        pm_layout.setSpacing(10)
        self._perm_title = QLabel(
            _tr(self._locale, "Permission Status", "permission_status")
        )
        self._perm_title.setObjectName("CardTitle")
        pm_layout.addWidget(self._perm_title)
        pm_layout.addLayout(perm_grid)
        content_layout.addWidget(perm_section)

        content_layout.addStretch()

        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 8, 0, 0)
        reset_row.addStretch()
        self.reset_button = QPushButton(
            _tr(locale, "Reset All Settings…", "reset")
        )
        self.reset_button.setObjectName("LinkButton")
        self.reset_button.setStyleSheet(
            "QPushButton#LinkButton { color: #AEAEB2; font-size: 11px; }"
            "QPushButton#LinkButton:hover { color: #FF3B30; }"
        )
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self._reset_settings)
        reset_row.addWidget(self.reset_button)
        reset_row.addStretch()
        content_layout.addLayout(reset_row)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._apply_hotkey_control_state()

    # -- Load / Collect --

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        self._apply_locale_texts()

        mode_idx = self._mode_combo.findData(settings.mode)
        self._mode_combo.setCurrentIndex(0 if mode_idx < 0 else mode_idx)
        self._cloud_url_input.setText(settings.cloud_api_url)
        self._cloud_key_input.setText(settings.cloud_api_key)
        self._update_mode_field_visibility()

        self._custom_hotkey_tokens = [
            t.strip().lower() for t in settings.custom_hotkey if t.strip()
        ]
        button_id = self._hotkey_id_for_mode.get(settings.hotkey, 0)
        btn = self._hotkey_button_group.button(button_id)
        if btn:
            btn.setChecked(True)
        self._apply_hotkey_control_state()

        wm_idx = self.whisper_model_combo.findText(settings.whisper_model)
        if wm_idx < 0 and settings.whisper_model:
            self.whisper_model_combo.addItem(settings.whisper_model)
            wm_idx = self.whisper_model_combo.count() - 1
        if wm_idx >= 0:
            self.whisper_model_combo.setCurrentIndex(wm_idx)

        lang_idx = self.language_combo.findData(settings.language)
        self.language_combo.setCurrentIndex(0 if lang_idx < 0 else lang_idx)

        self.ollama_host_input.setText(settings.ollama_host)
        self._populate_ollama_models(settings.ollama_host)
        om_idx = self.ollama_model_combo.findText(settings.ollama_model)
        if om_idx < 0 and settings.ollama_model:
            self.ollama_model_combo.addItem(settings.ollama_model)
            om_idx = self.ollama_model_combo.count() - 1
        if om_idx >= 0:
            self.ollama_model_combo.setCurrentIndex(om_idx)

        locale_idx = self.ui_locale_combo.findData(settings.ui_locale)
        self.ui_locale_combo.setCurrentIndex(0 if locale_idx < 0 else locale_idx)
        self._refresh_permission_status()

    def collect_settings(self) -> dict:
        checked_id = self._hotkey_button_group.checkedId()
        hotkey_mode = self._hotkey_mode_map.get(checked_id, "fn")
        lang_data = self.language_combo.currentData()
        return {
            "mode": str(self._mode_combo.currentData()),
            "cloud_api_url": self._cloud_url_input.text().strip(),
            "cloud_api_key": self._cloud_key_input.text().strip(),
            "hotkey": hotkey_mode,
            "custom_hotkey": list(self._custom_hotkey_tokens),
            "whisper_model": self.whisper_model_combo.currentText().strip() or "./local_whisper_model",
            "language": str(lang_data) if lang_data else "zh",
            "ollama_host": (
                self.ollama_host_input.text().strip().rstrip("/")
                or "http://127.0.0.1:11434"
            ),
            "ollama_model": self.ollama_model_combo.currentText().strip() or recommended_model_name(),
            "ui_locale": str(self.ui_locale_combo.currentData()),
            "auto_paste_delay_ms": 120,
            "llm_debug_stream": False,
        }

    def _apply_locale_texts(self) -> None:
        self._params_card_title.setText(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        self._perm_title.setText(
            _tr(self._locale, "Permission Status", "permission_status")
        )
        self.mic_permission_label.setText(
            _tr(self._locale, "Microphone", "mic_permission")
        )
        self.ax_permission_label.setText(
            _tr(self._locale, "Accessibility", "accessibility_permission")
        )
        self.permission_button.setText(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        self.request_mic_button.setText(
            _tr(self._locale, "Request Microphone Permission", "request_mic_permission")
        )
        self.hotkey_record_button.setText(
            _tr(self._locale, "Record Hotkey\u2026", "hotkey_record_button")
        )
        self.hotkey_reset_link.setText(
            _tr(self._locale, "Reset to Default", "hotkey_reset_default")
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

    def _populate_ollama_models(self, host: str = "") -> None:
        from talky.models import list_ollama_models

        current = self.ollama_model_combo.currentText()
        self.ollama_model_combo.blockSignals(True)
        self.ollama_model_combo.clear()
        models = list_ollama_models(host)
        for m in models:
            self.ollama_model_combo.addItem(m)
        if current and self.ollama_model_combo.findText(current) < 0:
            self.ollama_model_combo.addItem(current)
        if current:
            idx = self.ollama_model_combo.findText(current)
            if idx >= 0:
                self.ollama_model_combo.setCurrentIndex(idx)
        self.ollama_model_combo.blockSignals(False)

    # -- Mode --

    def _on_mode_changed(self, _index: int) -> None:
        self._update_mode_field_visibility()
        mode = str(self._mode_combo.currentData())
        if mode != "cloud":
            host = self.ollama_host_input.text().strip() if mode == "remote" else ""
            self._populate_ollama_models(host)

    def _update_mode_field_visibility(self) -> None:
        mode = str(self._mode_combo.currentData())
        is_cloud = mode == "cloud"
        is_remote = mode == "remote"

        self._cloud_url_input.setVisible(is_cloud)
        self._cloud_key_input.setVisible(is_cloud)
        self.whisper_model_combo.setVisible(not is_cloud)
        self.language_combo.setVisible(not is_cloud)
        self.ollama_host_input.setVisible(is_remote)
        self.ollama_model_combo.setVisible(not is_cloud)

        for label, _en, key in self._form_labels:
            if key in ("cloud_api_url", "cloud_api_key"):
                label.setVisible(is_cloud)
            elif key == "ollama_host":
                label.setVisible(is_remote)
            elif key in ("whisper_model", "asr_language", "ollama_model"):
                label.setVisible(not is_cloud)

    def _validate_mode_ready(
        self,
        *,
        mode: str,
        ollama_host: str,
        ollama_model: str,
    ) -> tuple[bool, str]:
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

    # -- Hotkey --

    def _on_hotkey_mode_changed(self, _button_id: int) -> None:
        self._apply_hotkey_control_state()

    def _apply_hotkey_control_state(self) -> None:
        checked_id = self._hotkey_button_group.checkedId()
        is_custom = self._hotkey_mode_map.get(checked_id) == "custom"
        self._custom_area.setVisible(is_custom)
        self._refresh_custom_hotkey_preview()

    def _refresh_custom_hotkey_preview(self) -> None:
        if not self._custom_hotkey_tokens:
            self.hotkey_custom_preview.setText(
                _tr(self._locale, "No custom hotkey recorded yet.", "hotkey_custom_empty")
            )
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
        stable_tokens = {"alt", "cmd", "ctrl", "shift", "fn"}
        normalized = [t for t in filtered if t in stable_tokens]
        if not normalized:
            return False, "Only modifier keys are supported for custom hotkey.", []
        return True, "", normalized

    def _reset_default_hotkey(self) -> None:
        default_id = self._hotkey_id_for_mode.get("fn", 0)
        btn = self._hotkey_button_group.button(default_id)
        if btn:
            btn.setChecked(True)
        self._apply_hotkey_control_state()

    # -- Permissions --

    def _refresh_permission_status(self) -> None:
        mic_ok, _ = check_microphone_granted()
        ax_ok = is_accessibility_trusted(prompt=False)

        granted_text = _tr(self._locale, "Granted", "granted")
        denied_text = _tr(self._locale, "Not Granted", "not_granted")
        ok_style = "color: #34C759; font-weight: 600; font-size: 12px;"
        fail_style = "color: #FF3B30; font-weight: 600; font-size: 12px;"

        self.mic_status_value_label.setText(
            f"\u2713 {granted_text}" if mic_ok else f"\u2717 {denied_text}"
        )
        self.mic_status_value_label.setStyleSheet(ok_style if mic_ok else fail_style)

        self.ax_status_value_label.setText(
            f"\u2713 {granted_text}" if ax_ok else f"\u2717 {denied_text}"
        )
        self.ax_status_value_label.setStyleSheet(ok_style if ax_ok else fail_style)

        self.request_mic_button.setVisible(not mic_ok)
        self.permission_button.setVisible(not ax_ok)

    def _check_accessibility(self) -> None:
        is_accessibility_trusted(prompt=True)
        self._refresh_permission_status()

    def _request_microphone_permission(self) -> None:
        granted, detail = request_microphone_permission()
        self._refresh_permission_status()
        if granted:
            QMessageBox.information(self, "Talky", "Microphone permission granted.")
            return
        QMessageBox.warning(
            self,
            "Talky",
            "Microphone permission missing."
            + "\nSystem Settings > Privacy & Security > Microphone."
            + (f"\nDetails: {detail}" if detail else ""),
        )

    # -- Save / Reset --

    def _save_settings(self, *, quiet: bool = False, custom_llm_prompt: str = "") -> None:
        collected = self.collect_settings()

        hotkey_mode = collected["hotkey"]
        custom_hotkey = list(self._custom_hotkey_tokens)
        if hotkey_mode == "custom":
            valid, reason, normalized = self._validate_custom_hotkey(set(custom_hotkey))
            if not valid:
                if not quiet:
                    QMessageBox.warning(self, "Talky", reason)
                return
            custom_hotkey = normalized

        selected_mode = collected["mode"]
        selected_host = collected["ollama_host"]
        selected_model = collected["ollama_model"]
        ok, reason = self._validate_mode_ready(
            mode=selected_mode,
            ollama_host=selected_host,
            ollama_model=selected_model,
        )
        if not ok:
            if not quiet:
                QMessageBox.warning(self, "Talky", reason)
                current_idx = self._mode_combo.findData(self.controller.settings.mode)
                if current_idx >= 0:
                    self._mode_combo.setCurrentIndex(current_idx)
            return

        settings = AppSettings(
            custom_dictionary=self.controller.settings.custom_dictionary,
            hotkey=hotkey_mode,
            custom_hotkey=custom_hotkey,
            whisper_model=collected["whisper_model"],
            ollama_model=selected_model,
            ollama_host=selected_host,
            ui_locale=collected["ui_locale"],
            language=collected["language"],
            auto_paste_delay_ms=collected["auto_paste_delay_ms"],
            llm_debug_stream=collected["llm_debug_stream"],
            sample_rate=self.controller.settings.sample_rate,
            channels=self.controller.settings.channels,
            mode=selected_mode,
            cloud_api_url=collected["cloud_api_url"],
            cloud_api_key=collected["cloud_api_key"],
            custom_llm_prompt=custom_llm_prompt,
        )
        QTimer.singleShot(0, lambda s=settings, q=quiet: self._apply_settings_deferred(s, q))

    def _apply_settings_deferred(self, settings: AppSettings, quiet: bool) -> None:
        self.controller.update_settings(settings)
        self._refresh_permission_status()
        if not quiet:
            QMessageBox.information(
                self, "Talky", _tr(settings.ui_locale, "Settings saved.", "saved")
            )

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


# ---------------------------------------------------------------------------
# Dashboard window (4-tab SettingsWindow)
# ---------------------------------------------------------------------------

class SettingsWindow(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._locale = controller.settings.ui_locale
        self._fade_in_animation: QPropertyAnimation | None = None

        self.setWindowTitle("Talky Dashboard")
        self.resize(720, 580)

        close_shortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        close_shortcut.activated.connect(self.close)

        # ---- Segmented tab bar ----
        tab_bar_frame = QFrame()
        tab_bar_frame.setObjectName("SegmentedBar")
        tab_bar_layout = QHBoxLayout(tab_bar_frame)
        tab_bar_layout.setContentsMargins(3, 3, 3, 3)
        tab_bar_layout.setSpacing(1)

        self._tab_buttons: list[QPushButton] = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)

        tab_keys = [
            ("Home", "home"),
            ("History", "history"),
            ("Dictionary", "dictionary"),
            ("Prompt", "prompt"),
            ("Configs", "configs"),
        ]
        for i, (en, key) in enumerate(tab_keys):
            btn = QPushButton(_tr(self._locale, en, key))
            btn.setCheckable(True)
            btn.setObjectName("SegmentTab")
            self._tab_buttons.append(btn)
            self._tab_group.addButton(btn, i)
            tab_bar_layout.addWidget(btn)
        self._tab_buttons[0].setChecked(True)
        self._tab_keys = tab_keys

        # ---- Tab content ----
        self._stack = QStackedWidget()
        self._home_tab = HomeTab(controller, locale=self._locale)
        self._history_tab = HistoryTab(controller, locale=self._locale)
        self._dictionary_tab = DictionaryTab(controller, locale=self._locale)
        self._prompt_tab = PromptTab(controller, locale=self._locale)
        self._configs_tab = ConfigsTab(controller, locale=self._locale)

        self._stack.addWidget(self._home_tab)
        self._stack.addWidget(self._history_tab)
        self._stack.addWidget(self._dictionary_tab)
        self._stack.addWidget(self._prompt_tab)
        self._stack.addWidget(self._configs_tab)

        self._tab_group.idClicked.connect(self._on_tab_changed)

        # ---- Layout (native — no wrapper container) ----
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        tab_row = QHBoxLayout()
        tab_row.addStretch()
        tab_row.addWidget(tab_bar_frame)
        tab_row.addStretch()
        root.addLayout(tab_row)

        root.addWidget(self._stack, 1)

        self.setStyleSheet(NATIVE_STYLESHEET)

        self.controller.settings_updated.connect(self.load_from_settings)
        self.load_from_settings(self.controller.settings)

    def _on_tab_changed(self, tab_id: int) -> None:
        self._stack.setCurrentIndex(tab_id)
        if tab_id == 1:
            self._history_tab.refresh()
        elif tab_id == 2:
            self._dictionary_tab.refresh_from_settings(self.controller.settings)
        elif tab_id == 3:
            self._prompt_tab.load_from_settings(self.controller.settings)

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        for i, (en, key) in enumerate(self._tab_keys):
            self._tab_buttons[i].setText(_tr(self._locale, en, key))
        self._home_tab.update_locale(self._locale)
        self._dictionary_tab.refresh_from_settings(settings)
        self._prompt_tab.load_from_settings(settings)
        self._configs_tab.load_from_settings(settings)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._auto_save_configs()
        super().closeEvent(event)

    def _auto_save_configs(self) -> None:
        try:
            prompt = self._prompt_tab.collect_prompt()
            self._configs_tab._save_settings(quiet=True, custom_llm_prompt=prompt)  # noqa: SLF001
        except Exception:
            pass

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if alert_if_local_ollama_unready(self.controller.config_store):
            self.controller.update_settings(self.controller.config_store.load())
        self._configs_tab._refresh_permission_status()  # noqa: SLF001
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_in_animation = anim


# ---------------------------------------------------------------------------
# System tray
# ---------------------------------------------------------------------------

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
        self._start_external_show_signal_watcher()
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

    def _start_external_show_signal_watcher(self) -> None:
        self._signal_timer = QTimer()
        self._signal_timer.timeout.connect(self._check_external_show_signal)
        self._signal_timer.start(2000)

    def _check_external_show_signal(self) -> None:
        signal_path = Path.home() / ".talky" / "show_settings.signal"
        if signal_path.exists():
            try:
                signal_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.show_settings()

    def show_settings(self) -> None:
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def quit_app(self) -> None:
        self.dictionary_shortcut_listener.stop()
        if hasattr(self, "_signal_timer"):
            self._signal_timer.stop()
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
        if hasattr(self, "_signal_timer"):
            self._signal_timer.stop()
        self.controller.stop()
        self.tray.hide()
        if _restart_current_process("model_configured"):
            QApplication.quit()
            return
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


# ---------------------------------------------------------------------------
# Result popup
# ---------------------------------------------------------------------------

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
        self.setStyleSheet(NATIVE_STYLESHEET)

    def show_text(self, text: str, locale: str) -> None:
        self.title.setText(_tr(locale, "No Focus Target Detected", "popup_title"))
        self.subtitle.setText(
            _tr(locale, "Result is ready. Copy and paste manually.", "popup_subtitle")
        )
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


# ---------------------------------------------------------------------------
# Model download / setup
# ---------------------------------------------------------------------------

class _ModelDownloadThread(QThread):
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
        self.setStyleSheet(NATIVE_STYLESHEET)

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
