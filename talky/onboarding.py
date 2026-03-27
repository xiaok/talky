from __future__ import annotations

import enum
import locale

from talky.models import AppSettings, detect_ollama_model
from talky.permissions import check_ollama_reachable, is_ollama_installed


class OllamaStatus(enum.Enum):
    READY = "ready"
    NOT_INSTALLED = "not_installed"
    NOT_RUNNING = "not_running"
    NO_MODEL = "no_model"


def run_preflight_check() -> OllamaStatus:
    """Check Ollama installation, service, and model availability."""
    installed = is_ollama_installed()
    reachable, _ = check_ollama_reachable()
    if not installed and not reachable:
        return OllamaStatus.NOT_INSTALLED
    if not reachable:
        return OllamaStatus.NOT_RUNNING
    if not detect_ollama_model():
        return OllamaStatus.NO_MODEL
    return OllamaStatus.READY


def detect_system_locale() -> str:
    """Return 'zh' if macOS system language is Chinese, else 'en'."""
    try:
        lang, _ = locale.getlocale()
        if lang and lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"


# ---------------------------------------------------------------------------
# i18n helpers for the onboarding wizard
# ---------------------------------------------------------------------------

_WIZARD_ZH = {
    "window_title": "Talky 设置向导",
    "welcome": "Talky 需要 Ollama 来处理语音文本",
    "run_local": "在本机运行",
    "run_local_desc": "在这台 Mac 上安装 Ollama",
    "connect_remote": "连接远端",
    "connect_remote_desc": "使用局域网内另一台设备的 Ollama",
    "install_title": "请先下载安装 Ollama",
    "go_download": "下载 Ollama",
    "recheck_install": "我已安装，重新检测",
    "remote_title": "连接远端 Ollama",
    "remote_host": "Ollama 地址",
    "test_connection": "检测连接",
    "connection_ok": "连接成功",
    "connection_fail": "连接失败",
    "select_model": "选择模型",
    "model_title": "下载 AI 模型",
    "model_subtitle": "Talky 推荐使用 <b>{model}</b>，点击下方按钮即可开始下载。",
    "or_manual": "或手动运行：",
    "recommended": "推荐模型",
    "copy_command": "复制",
    "open_terminal": "在终端中下载",
    "open_terminal_hint": "已在终端中开始下载，请等待下载完成后点击下方按钮",
    "copied_hint": "已复制！请打开终端粘贴运行",
    "recheck_model": "我已下载，重新检测",
    "recheck_no_model": "未检测到模型，请等待下载完成后重试",
    "open_library": "在 Ollama 页面打开",
    "complete_title": "一切就绪！",
    "complete_msg": "按住 Fn 键即可开始语音输入",
    "done": "完成",
    "next": "下一步",
    "back": "上一步",
    "whisper_title": "下载语音识别模型",
    "whisper_subtitle": "Talky 需要 Whisper 模型来将语音转为文字。",
    "whisper_download": "下载模型（约 3 GB）",
    "whisper_i_have": "我已有模型",
    "whisper_path_placeholder": "路径或 HuggingFace 仓库 ID",
    "whisper_confirm": "确认",
    "whisper_downloading": "正在下载模型… 首次下载约需 3–5 分钟。",
    "whisper_preparing": "正在准备运行环境…",
    "whisper_done": "下载完成！",
    "whisper_failed": "下载失败",
}


def _wiz_tr(loc: str, en: str, key: str) -> str:
    if loc == "zh":
        return _WIZARD_ZH.get(key, en)
    return en


# ---------------------------------------------------------------------------
# OnboardingWizard
# ---------------------------------------------------------------------------

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from talky.config_store import AppConfigStore


def _apply_ollama_host_env_from_settings(settings: AppSettings) -> None:
    import os

    host = (settings.ollama_host or "http://127.0.0.1:11434").strip().rstrip("/")
    if not host:
        host = "http://127.0.0.1:11434"
    os.environ["OLLAMA_HOST"] = host


class OnboardingWizard(QDialog):
    """Multi-page setup wizard shown on first launch or when Ollama is missing."""

    def __init__(
        self,
        config_store,  # AppConfigStore
        ollama_status: OllamaStatus,
        locale: str = "en",
        parent=None,
    ):
        super().__init__(parent)
        self._config_store = config_store
        self._locale = locale
        self._selected_model: str = ""
        self._selected_host: str = "http://127.0.0.1:11434"
        self._selected_mode: str = "local"

        self.setWindowTitle(_wiz_tr(locale, "Talky Setup Wizard", "window_title"))
        self.setFixedSize(520, 480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        from talky.ui import IOS26_STYLESHEET
        self.setStyleSheet(IOS26_STYLESHEET)

        self.stack = QStackedWidget()
        self._build_page0_mode_selection()   # 0
        self._build_page1_local_install()    # 1
        self._build_page2_remote_config()    # 2
        self._build_page3_model_prep()       # 3
        self._build_page4_whisper_setup()    # 4
        self._build_page5_complete()         # 5

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        start_page = {
            OllamaStatus.NOT_INSTALLED: 0,
            OllamaStatus.NOT_RUNNING: 1,
            OllamaStatus.NO_MODEL: 3,
            OllamaStatus.READY: 0,
        }.get(ollama_status, 0)
        if ollama_status == OllamaStatus.READY:
            QTimer.singleShot(0, self._goto_all_set)
        else:
            self.stack.setCurrentIndex(start_page)

    # -- Page 0: Mode Selection ------------------------------------------------

    def _build_page0_mode_selection(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)

        # --- Header ---
        title = QLabel(_wiz_tr(self._locale, "Talky Setup", "window_title"))
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            _wiz_tr(
                self._locale,
                "Talky needs Ollama to process voice text",
                "welcome",
            )
        )
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        # --- Option 1: Run locally (desc above button) ---
        local_desc = QLabel(
            _wiz_tr(self._locale, "Install Ollama on this Mac", "run_local_desc")
        )
        local_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # TODO(DMG/visual): #555 on dark sheet — very low contrast; align desc/subtitle
        # colors with IOS26_STYLESHEET / design tokens before release build.
        local_desc.setStyleSheet("color: #555; font-size: 13px;")
        local_desc.setWordWrap(True)
        layout.addWidget(local_desc)
        layout.addSpacing(6)

        local_btn = QPushButton(
            _wiz_tr(self._locale, "Run locally", "run_local")
        )
        local_btn.setObjectName("PrimaryButton")
        local_btn.setMinimumHeight(44)
        local_btn.clicked.connect(self._choose_local_mode)
        layout.addWidget(local_btn)
        layout.addSpacing(20)

        # --- Option 2: Connect remote (desc above button) ---
        remote_desc = QLabel(
            _wiz_tr(
                self._locale,
                "Use Ollama on another device in LAN",
                "connect_remote_desc",
            )
        )
        remote_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        remote_desc.setStyleSheet("color: #555; font-size: 13px;")
        remote_desc.setWordWrap(True)
        layout.addWidget(remote_desc)
        layout.addSpacing(6)

        remote_btn = QPushButton(
            _wiz_tr(self._locale, "Connect remote", "connect_remote")
        )
        remote_btn.setObjectName("SecondaryButton")
        remote_btn.setMinimumHeight(44)
        remote_btn.clicked.connect(self._choose_remote_mode)
        layout.addWidget(remote_btn)

        self.stack.addWidget(page)

    # -- Page 1: Local Install Guide -------------------------------------------

    def _build_page1_local_install(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)

        layout.addStretch()

        title = QLabel(
            _wiz_tr(
                self._locale,
                "Please download and install Ollama first",
                "install_title",
            )
        )
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)
        layout.addSpacing(20)

        dl_btn = QPushButton(
            _wiz_tr(self._locale, "Download Ollama", "go_download")
        )
        dl_btn.setObjectName("PrimaryButton")
        dl_btn.setMinimumHeight(44)
        dl_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
        )
        layout.addWidget(dl_btn)
        layout.addSpacing(10)

        recheck_btn = QPushButton(
            _wiz_tr(self._locale, "I've installed, re-check", "recheck_install")
        )
        recheck_btn.setObjectName("SecondaryButton")
        recheck_btn.setMinimumHeight(40)
        recheck_btn.clicked.connect(self._recheck_install)
        layout.addWidget(recheck_btn)
        layout.addSpacing(8)

        self._install_status_label = QLabel("")
        self._install_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._install_status_label.setWordWrap(True)
        self._install_status_label.setStyleSheet("font-size: 12px; color: #FF3B30;")
        self._install_status_label.setFixedHeight(36)
        layout.addWidget(self._install_status_label)

        layout.addStretch()
        self.stack.addWidget(page)

    def _recheck_install(self) -> None:
        self._selected_mode = "local"
        reachable, _ = check_ollama_reachable()
        if reachable:
            from talky.models import list_ollama_models
            models = list_ollama_models()
            if models:
                self._selected_model = models[0]
                self._goto_all_set()
            else:
                self.stack.setCurrentIndex(3)
        else:
            self._install_status_label.setText(
                _wiz_tr(
                    self._locale,
                    "Ollama is not reachable yet. Please make sure it is installed and running.",
                    "connection_fail",
                )
            )

    # -- Page 2: Remote Config -------------------------------------------------

    def _build_page2_remote_config(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(
            _wiz_tr(self._locale, "Connect to Remote Ollama", "remote_title")
        )
        title.setObjectName("CardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(10)

        host_label = QLabel(
            _wiz_tr(self._locale, "Ollama Host", "remote_host")
        )
        layout.addWidget(host_label)

        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("http://192.168.1.x:11434")
        layout.addWidget(self._host_input)
        layout.addSpacing(10)

        test_btn = QPushButton(
            _wiz_tr(self._locale, "Test Connection", "test_connection")
        )
        test_btn.setObjectName("PrimaryButton")
        test_btn.clicked.connect(self._test_remote_connection)
        layout.addWidget(test_btn)

        self._remote_status_label = QLabel("")
        self._remote_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._remote_status_label.setWordWrap(True)
        layout.addWidget(self._remote_status_label)

        # Model combo (hidden until connection succeeds)
        model_label = QLabel(
            _wiz_tr(self._locale, "Select Model", "select_model")
        )
        self._remote_model_label = model_label
        model_label.setVisible(False)
        layout.addWidget(model_label)

        self._remote_model_combo = QComboBox()
        self._remote_model_combo.setVisible(False)
        layout.addWidget(self._remote_model_combo)

        self._remote_next_btn = QPushButton(
            _wiz_tr(self._locale, "Next", "next")
        )
        self._remote_next_btn.setObjectName("PrimaryButton")
        self._remote_next_btn.setEnabled(False)
        self._remote_next_btn.setVisible(False)
        self._remote_next_btn.clicked.connect(self._remote_next)
        layout.addWidget(self._remote_next_btn)

        self.stack.addWidget(page)

    def _test_remote_connection(self) -> None:
        from talky.models import list_ollama_models

        host = self._host_input.text().strip()
        if not host:
            host = "http://127.0.0.1:11434"
        models = list_ollama_models(host)
        if models:
            self._selected_host = host.rstrip("/")
            self._remote_status_label.setText(
                _wiz_tr(self._locale, "Connection OK", "connection_ok")
            )
            self._remote_model_combo.clear()
            self._remote_model_combo.addItems(models)
            self._remote_model_combo.setVisible(True)
            self._remote_model_label.setVisible(True)
            self._remote_next_btn.setEnabled(True)
            self._remote_next_btn.setVisible(True)
        else:
            self._remote_status_label.setText(
                _wiz_tr(self._locale, "Connection failed", "connection_fail")
            )
            self._remote_model_combo.setVisible(False)
            self._remote_model_label.setVisible(False)
            self._remote_next_btn.setEnabled(False)
            self._remote_next_btn.setVisible(False)

    def _remote_next(self) -> None:
        self._selected_mode = "remote"
        self._selected_model = self._remote_model_combo.currentText()
        self._goto_all_set()

    # -- Page 3: Model Preparation ---------------------------------------------

    def _build_page3_model_prep(self) -> None:
        from talky.recommended_ollama import load_recommended_ollama_config

        rec = load_recommended_ollama_config()
        rec_model = rec.model

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)

        # --- Title + subtitle ---
        title = QLabel(
            _wiz_tr(self._locale, "Download AI Model", "model_title")
        )
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle_text = _wiz_tr(
            self._locale,
            f"Talky recommends <b>{rec_model}</b> — click the button below to start downloading.",
            "model_subtitle",
        ).format(model=rec_model)
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        # --- Primary action: one-click download ---
        self._pull_cmd = rec.pull_command_resolved()
        open_lib_btn = None
        if rec.library_url:
            open_lib_btn = QPushButton(
                _wiz_tr(self._locale, "View on Ollama.com", "open_library")
            )
            open_lib_btn.setObjectName("SecondaryButton")
            open_lib_btn.setMinimumHeight(40)
            lib_url = rec.library_url

            def _open_lib() -> None:
                QDesktopServices.openUrl(QUrl(lib_url))

            open_lib_btn.clicked.connect(_open_lib)
            layout.addWidget(open_lib_btn)
            layout.addSpacing(8)

        open_term_btn = QPushButton(
            _wiz_tr(self._locale, "Download in Terminal", "open_terminal")
        )
        open_term_btn.setObjectName("PrimaryButton")
        open_term_btn.setMinimumHeight(44)
        open_term_btn.clicked.connect(self._open_terminal_pull)
        layout.addWidget(open_term_btn)
        layout.addSpacing(12)

        # --- Manual command (right below the primary button) ---
        cmd_row = QHBoxLayout()
        cmd_label = QLabel(
            f'<span style="color:#888; font-size:12px;">'
            f'{_wiz_tr(self._locale, "Or run manually:", "or_manual")}</span>'
            f'  <code style="background:#f0f0f0; padding:2px 6px; border-radius:4px;">'
            f'{self._pull_cmd}</code>'
        )
        cmd_label.setTextFormat(Qt.TextFormat.RichText)
        cmd_row.addWidget(cmd_label, 1)

        copy_btn = QPushButton(
            _wiz_tr(self._locale, "Copy", "copy_command")
        )
        copy_btn.setFixedWidth(60)
        copy_btn.setStyleSheet(
            "font-size: 12px; padding: 4px 8px; border-radius: 8px; "
            "background: rgba(0,0,0,0.06); border: 1px solid rgba(0,0,0,0.1);"
        )
        copy_btn.clicked.connect(self._copy_and_show_hint)
        cmd_row.addWidget(copy_btn)
        layout.addLayout(cmd_row)

        # Status feedback (appears after clicking download, copy or re-check)
        self._model_status_label = QLabel("")
        self._model_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._model_status_label.setWordWrap(True)
        self._model_status_label.setStyleSheet("color: #666; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self._model_status_label)
        layout.addSpacing(24)

        # --- Secondary: re-check after download finishes ---
        recheck_btn = QPushButton(
            _wiz_tr(self._locale, "I've downloaded, re-check", "recheck_model")
        )
        recheck_btn.setObjectName("SecondaryButton")
        recheck_btn.setMinimumHeight(40)
        recheck_btn.clicked.connect(self._recheck_models)
        layout.addWidget(recheck_btn)

        # --- Existing-models dropdown (hidden until models found) ---
        self._model_combo_label = QLabel(
            _wiz_tr(self._locale, "Select Model", "select_model")
        )
        layout.addWidget(self._model_combo_label)

        self._model_combo = QComboBox()
        layout.addWidget(self._model_combo)

        self._model_next_btn = QPushButton(
            _wiz_tr(self._locale, "Next", "next")
        )
        self._model_next_btn.setObjectName("PrimaryButton")
        self._model_next_btn.clicked.connect(self._model_next)
        layout.addWidget(self._model_next_btn)

        # Keep references for visibility toggling
        self._recommended_widgets = [subtitle]
        if open_lib_btn is not None:
            self._recommended_widgets.append(open_lib_btn)
        self._recommended_widgets.extend([open_term_btn, recheck_btn])
        self._recommended_label = subtitle  # kept for _refresh_model_combo compat
        self._pull_cmd_label = cmd_label

        # Populate with current models
        self._refresh_model_combo()

        self.stack.addWidget(page)

    def _refresh_model_combo(self) -> None:
        from talky.models import list_ollama_models

        models = list_ollama_models()
        self._model_combo.clear()
        has_models = bool(models)
        if has_models:
            self._model_combo.addItems(models)
        # Show download flow or model-selection flow
        for w in self._recommended_widgets:
            w.setVisible(not has_models)
        self._pull_cmd_label.setVisible(not has_models)
        self._model_status_label.setVisible(not has_models)
        self._model_combo.setVisible(has_models)
        self._model_combo_label.setVisible(has_models)
        self._model_next_btn.setVisible(has_models)

    def _open_terminal_pull(self) -> None:
        """Open Terminal.app and run the ollama pull command."""
        import subprocess

        script = f'tell application "Terminal" to do script "{self._pull_cmd}"'
        subprocess.Popen(["osascript", "-e", script])  # noqa: S603, S607
        self._model_status_label.setText(
            _wiz_tr(
                self._locale,
                "Download started in Terminal. Click re-check when done.",
                "open_terminal_hint",
            )
        )

    def _copy_and_show_hint(self) -> None:
        """Copy pull command to clipboard and show feedback."""
        import pyperclip

        pyperclip.copy(self._pull_cmd)
        self._model_status_label.setText(
            _wiz_tr(
                self._locale,
                "Copied! Open Terminal and paste to run.",
                "copied_hint",
            )
        )

    def _model_next(self) -> None:
        self._selected_model = self._model_combo.currentText()
        self._goto_all_set()

    def _recheck_models(self) -> None:
        from talky.models import list_ollama_models

        models = list_ollama_models()
        if models:
            self._model_combo.clear()
            self._model_combo.addItems(models)
            self._refresh_model_combo()
            self._selected_model = models[0]
            self._goto_all_set()
        else:
            self._model_status_label.setText(
                _wiz_tr(
                    self._locale,
                    "No models found yet. Please wait for download to finish and try again.",
                    "recheck_no_model",
                )
            )

    # -- Page 4: Whisper Setup -------------------------------------------------

    _WHISPER_HF_REPO = "mlx-community/whisper-large-v3-mlx"

    def _build_page4_whisper_setup(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)

        title = QLabel(
            _wiz_tr(self._locale, "Download Speech Model", "whisper_title")
        )
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            _wiz_tr(
                self._locale,
                "Talky needs a Whisper model to convert speech to text.",
                "whisper_subtitle",
            )
        )
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        self._whisper_dl_btn = QPushButton(
            _wiz_tr(self._locale, "Download Model (~3 GB)", "whisper_download")
        )
        self._whisper_dl_btn.setObjectName("PrimaryButton")
        self._whisper_dl_btn.setMinimumHeight(44)
        self._whisper_dl_btn.clicked.connect(self._whisper_start_download)
        layout.addWidget(self._whisper_dl_btn)
        layout.addSpacing(10)

        self._whisper_have_btn = QPushButton(
            _wiz_tr(self._locale, "I have a model", "whisper_i_have")
        )
        self._whisper_have_btn.setObjectName("SecondaryButton")
        self._whisper_have_btn.setMinimumHeight(40)
        self._whisper_have_btn.clicked.connect(self._whisper_toggle_custom)
        layout.addWidget(self._whisper_have_btn)
        layout.addSpacing(8)

        custom_row = QHBoxLayout()
        self._whisper_custom_input = QLineEdit()
        self._whisper_custom_input.setPlaceholderText(
            _wiz_tr(self._locale, "Path or HuggingFace repo ID", "whisper_path_placeholder")
        )
        self._whisper_custom_confirm = QPushButton(
            _wiz_tr(self._locale, "Confirm", "whisper_confirm")
        )
        self._whisper_custom_confirm.setObjectName("SecondaryButton")
        self._whisper_custom_confirm.clicked.connect(self._whisper_confirm_custom)
        custom_row.addWidget(self._whisper_custom_input, 1)
        custom_row.addWidget(self._whisper_custom_confirm)
        self._whisper_custom_widget = QWidget()
        self._whisper_custom_widget.setLayout(custom_row)
        self._whisper_custom_widget.setVisible(False)
        layout.addWidget(self._whisper_custom_widget)

        self._whisper_progress_bar = QProgressBar()
        self._whisper_progress_bar.setRange(0, 100)
        self._whisper_progress_bar.setValue(0)
        self._whisper_progress_bar.setTextVisible(False)
        self._whisper_progress_bar.setFixedHeight(6)
        self._whisper_progress_bar.setStyleSheet(
            "QProgressBar { background: #E5E5EA; border: none; border-radius: 3px; }"
            "QProgressBar::chunk { background: #ED4A20; border-radius: 3px; }"
        )
        self._whisper_progress_bar.setVisible(False)
        layout.addWidget(self._whisper_progress_bar)
        layout.addSpacing(6)

        self._whisper_status_label = QLabel("")
        self._whisper_status_label.setStyleSheet("font-size: 12px; color: #86868B;")
        self._whisper_status_label.setWordWrap(True)
        self._whisper_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._whisper_status_label.setVisible(False)
        layout.addWidget(self._whisper_status_label)

        layout.addStretch()
        self.stack.addWidget(page)

    def _whisper_toggle_custom(self) -> None:
        visible = not self._whisper_custom_widget.isVisible()
        self._whisper_custom_widget.setVisible(visible)
        if visible:
            self._whisper_custom_input.setFocus()

    def _whisper_confirm_custom(self) -> None:
        value = self._whisper_custom_input.text().strip()
        if not value:
            return
        s = self._config_store.load()
        s.whisper_model = value
        self._config_store.save(s)
        self.stack.setCurrentIndex(5)

    def _whisper_start_download(self) -> None:
        from talky.ui import _ModelDownloadThread

        self._whisper_dl_btn.setEnabled(False)
        self._whisper_have_btn.setEnabled(False)
        self._whisper_custom_widget.setVisible(False)
        self._whisper_progress_bar.setVisible(True)
        self._whisper_progress_bar.setRange(0, 100)
        self._whisper_progress_bar.setValue(0)
        self._whisper_in_runtime_prep = False
        self._whisper_status_label.setVisible(True)
        self._whisper_status_label.setStyleSheet("font-size: 12px; color: #86868B;")
        self._whisper_status_label.setText(
            _wiz_tr(
                self._locale,
                "Downloading model… First download takes about 3–5 minutes.",
                "whisper_downloading",
            )
        )

        self._whisper_dl_thread = _ModelDownloadThread(self._WHISPER_HF_REPO, self)
        self._whisper_dl_thread.finished.connect(self._whisper_download_finished)
        self._whisper_dl_thread.failed.connect(self._whisper_download_failed)
        self._whisper_dl_thread.start()

        self._whisper_poll_timer = QTimer(self)
        self._whisper_poll_timer.timeout.connect(self._whisper_poll_progress)
        self._whisper_poll_timer.start(500)

    def _whisper_poll_progress(self) -> None:
        t = self._whisper_dl_thread
        if t is None:
            return
        if t.preparing_runtime:
            if not self._whisper_in_runtime_prep:
                self._whisper_progress_bar.setRange(0, 0)
                self._whisper_in_runtime_prep = True
            self._whisper_status_label.setText(
                _wiz_tr(self._locale, "Preparing runtime environment…", "whisper_preparing")
            )
            return
        total = t.dl_total
        downloaded = t.dl_bytes
        if total <= 0:
            return
        pct = min(int(downloaded * 100 / total), 100)
        self._whisper_progress_bar.setValue(pct)
        dl_gb = downloaded / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        self._whisper_status_label.setText(
            f"Downloading… {dl_gb:.1f} GB / {total_gb:.1f} GB ({pct}%)"
        )

    def _whisper_download_finished(self, _path: str) -> None:
        if hasattr(self, "_whisper_poll_timer"):
            self._whisper_poll_timer.stop()
        self._whisper_progress_bar.setRange(0, 100)
        self._whisper_progress_bar.setValue(100)
        self._whisper_status_label.setText(
            _wiz_tr(self._locale, "Download complete!", "whisper_done")
        )
        self._whisper_status_label.setStyleSheet("font-size: 12px; color: #34C759;")
        s = self._config_store.load()
        s.whisper_model = self._WHISPER_HF_REPO
        self._config_store.save(s)
        QTimer.singleShot(1000, lambda: self.stack.setCurrentIndex(5))

    def _whisper_download_failed(self, error: str) -> None:
        if hasattr(self, "_whisper_poll_timer"):
            self._whisper_poll_timer.stop()
        self._whisper_progress_bar.setRange(0, 100)
        self._whisper_status_label.setText(
            _wiz_tr(self._locale, "Download failed", "whisper_failed") + f": {error}"
        )
        self._whisper_status_label.setStyleSheet("font-size: 12px; color: #FF3B30;")
        self._whisper_dl_btn.setEnabled(True)
        self._whisper_have_btn.setEnabled(True)

    # -- Page 5: Complete ------------------------------------------------------

    def _build_page5_complete(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(
            _wiz_tr(self._locale, "All set!", "complete_title")
        )
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(10)

        msg = QLabel(
            _wiz_tr(
                self._locale,
                "Hold the Fn key to start voice input.",
                "complete_msg",
            )
        )
        msg.setObjectName("WindowSubtitle")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)
        layout.addSpacing(20)

        done_btn = QPushButton(
            _wiz_tr(self._locale, "Done", "done")
        )
        done_btn.setObjectName("PrimaryButton")
        done_btn.clicked.connect(self._finish)
        layout.addWidget(done_btn)

        self.stack.addWidget(page)

    # -- Whisper gate before "All set!" ----------------------------------------

    def _goto_all_set(self) -> None:
        """Save Ollama settings, check Whisper, then route to the right page."""
        try:
            settings = self._config_store.load()
        except Exception:
            settings = AppSettings()
        settings.ollama_model = self._selected_model
        settings.ollama_host = self._selected_host
        settings.mode = self._selected_mode
        self._config_store.save(settings)

        from talky.asr_service import is_whisper_model_cached

        if is_whisper_model_cached(settings.whisper_model):
            self.stack.setCurrentIndex(5)
        else:
            self.stack.setCurrentIndex(4)

    # -- Finish ----------------------------------------------------------------

    def _finish(self) -> None:
        self.accept()

    def _choose_local_mode(self) -> None:
        self._selected_mode = "local"
        self.stack.setCurrentIndex(1)

    def _choose_remote_mode(self) -> None:
        self._selected_mode = "remote"
        self.stack.setCurrentIndex(2)


class RemoteOllamaConnectDialog(QDialog):
    """Returning-user flow: configure LAN Ollama (e.g. Mac mini) when no local binary is found."""

    def __init__(self, config_store: AppConfigStore, locale: str = "en", parent=None) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._locale = locale
        zh = locale == "zh"
        self.setWindowTitle("Talky")
        self.setMinimumWidth(440)

        from talky.ui import IOS26_STYLESHEET

        self.setStyleSheet(IOS26_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel(
            _wiz_tr(locale, "Connect to Remote Ollama", "remote_title")
        )
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        hint = QLabel(
            "例如 Mac mini 的地址：http://192.168.x.x:11434"
            if zh
            else "Example: Ollama on a Mac mini — http://192.168.x.x:11434"
        )
        hint.setWordWrap(True)
        hint.setObjectName("WindowSubtitle")
        layout.addWidget(hint)

        layout.addWidget(QLabel(_wiz_tr(locale, "Ollama Host", "remote_host")))
        self._host_input = QLineEdit()
        s = config_store.load()
        self._host_input.setText((s.ollama_host or "").strip() or "http://192.168.1.10:11434")
        self._host_input.setPlaceholderText("http://192.168.1.10:11434")
        layout.addWidget(self._host_input)

        test_btn = QPushButton(_wiz_tr(locale, "Test Connection", "test_connection"))
        test_btn.setObjectName("PrimaryButton")
        test_btn.clicked.connect(self._on_test)
        layout.addWidget(test_btn)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._model_label = QLabel(_wiz_tr(locale, "Select Model", "select_model"))
        self._model_label.setVisible(False)
        layout.addWidget(self._model_label)

        self._model_combo = QComboBox()
        self._model_combo.setVisible(False)
        layout.addWidget(self._model_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(False)
        self._ok_btn.setText("保存并继续" if zh else "Save & continue")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("取消" if zh else "Cancel")
        layout.addWidget(buttons)

    def _on_test(self) -> None:
        from talky.models import list_ollama_models

        host = self._host_input.text().strip()
        if not host:
            host = "http://127.0.0.1:11434"
        host = host.rstrip("/")
        models = list_ollama_models(host)
        zh = self._locale == "zh"
        if models:
            self._status.setText(_wiz_tr(self._locale, "Connection OK", "connection_ok"))
            self._status.setStyleSheet("color: #1a7f37; font-size: 12px;")
            self._model_combo.clear()
            self._model_combo.addItems(models)
            self._model_combo.setVisible(True)
            self._model_label.setVisible(True)
            self._ok_btn.setEnabled(True)
        else:
            self._status.setText(
                _wiz_tr(self._locale, "Connection failed", "connection_fail")
                + (" — 请检查 IP、端口与 Mac mini 上的 Ollama 是否已运行。" if zh else " — check IP/port and that Ollama is running on the remote Mac.")
            )
            self._status.setStyleSheet("color: #b00020; font-size: 12px;")
            self._model_combo.clear()
            self._model_combo.setVisible(False)
            self._model_label.setVisible(False)
            self._ok_btn.setEnabled(False)

    def _on_ok(self) -> None:
        if not self._ok_btn.isEnabled():
            return
        host = self._host_input.text().strip().rstrip("/")
        if not host:
            host = "http://127.0.0.1:11434"
        model = self._model_combo.currentText()
        if not model:
            return
        settings = self._config_store.load()
        settings.ollama_host = host
        settings.ollama_model = model
        settings.mode = "remote"
        self._config_store.save(settings)
        _apply_ollama_host_env_from_settings(settings)
        self.accept()


def show_returning_user_prompt(
    status: OllamaStatus,
    *,
    locale: str = "en",
    config_store: AppConfigStore,
) -> bool:
    """Show blocking prompts that loop until Ollama is ready. Returns True if resolved."""
    import subprocess

    from talky.macos_ui import activate_foreground_app, prepare_qt_modal_for_macos
    from talky.models import list_ollama_models
    from talky.recommended_ollama import load_recommended_ollama_config

    activate_foreground_app()
    zh = locale == "zh"

    # --- Step 1: No local Ollama binary and localhost unreachable → download, remote, or quit ---
    if status == OllamaStatus.NOT_INSTALLED:
        while True:
            box = QMessageBox()
            box.setWindowTitle("Talky")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(
                "本机未检测到 Ollama（或未连上）。若 Ollama 在另一台 Mac（如 Mac mini）上，请点「连接远端」。"
                if zh
                else "Ollama was not found on this Mac (or localhost is unreachable). "
                "If Ollama runs on another Mac (e.g. Mac mini), choose Connect remote."
            )
            box.setInformativeText(
                "连接远端：输入 Mac mini 的局域网地址（如 http://192.168.1.10:11434）。\n"
                "在本机安装：访问 ollama.com/download。"
                if zh
                else "Remote: enter your Mac mini's URL (e.g. http://192.168.1.10:11434).\n"
                "Local install: ollama.com/download."
            )
            remote_btn = box.addButton(
                "连接远端" if zh else "Connect remote",
                QMessageBox.ButtonRole.AcceptRole,
            )
            dl_btn = box.addButton(
                "下载 Ollama" if zh else "Download Ollama",
                QMessageBox.ButtonRole.ActionRole,
            )
            quit_btn = box.addButton("退出" if zh else "Quit", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(remote_btn)
            prepare_qt_modal_for_macos(box)
            box.exec()
            clicked = box.clickedButton()
            if clicked == quit_btn:
                return False
            if clicked == dl_btn:
                QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
                return False
            if clicked == remote_btn:
                dlg = RemoteOllamaConnectDialog(config_store, locale=locale)
                prepare_qt_modal_for_macos(dlg)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    continue
                settings = config_store.load()
                _apply_ollama_host_env_from_settings(settings)
                status = run_preflight_check()
                if status == OllamaStatus.READY:
                    return True
                if status == OllamaStatus.NO_MODEL:
                    break
                if status == OllamaStatus.NOT_RUNNING:
                    break
                activate_foreground_app()
                QMessageBox.warning(
                    None,
                    "Talky",
                    "仍无法连接远端 Ollama，请检查地址与网络后重试。"
                    if zh
                    else "Still cannot reach remote Ollama. Check the URL and network, then try again.",
                )
                continue

    # --- Step 2: Ollama not running → loop until running ---
    while True:
        reachable, _ = check_ollama_reachable()
        if reachable:
            break
        box = QMessageBox()
        box.setWindowTitle("Talky")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Ollama 未启动。" if zh else "Ollama is not running.")
        box.setInformativeText(
            "请先启动 Ollama 应用，然后点击下方按钮。" if zh
            else "Please start the Ollama app first, then click the button below."
        )
        recheck_btn = box.addButton(
            "Ollama 已启动，重新检测" if zh else "Ollama is running, re-check",
            QMessageBox.ButtonRole.AcceptRole,
        )
        quit_btn = box.addButton("退出" if zh else "Quit", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(recheck_btn)
        prepare_qt_modal_for_macos(box)
        box.exec()
        if box.clickedButton() == quit_btn:
            return False

    # --- Step 3: No model → loop until model exists ---
    models = list_ollama_models()
    if models:
        return True

    rec = load_recommended_ollama_config()
    pull_cmd = rec.pull_command_resolved()
    rec_model = rec.model
    while True:
        box = QMessageBox()
        box.setWindowTitle("Talky")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("未检测到可用模型。" if zh else "No models detected.")
        box.setInformativeText(
            f"请先下载模型，或点击「在终端中下载」自动执行。\n\n推荐模型：{rec_model}" if zh
            else f"Please download a model first, or click below to auto-download.\n\nRecommended: {rec_model}"
        )
        term_btn = box.addButton(
            "在终端中下载" if zh else "Download in Terminal",
            QMessageBox.ButtonRole.ActionRole,
        )
        recheck_btn = box.addButton(
            "已下载，重新检测" if zh else "I've downloaded, re-check",
            QMessageBox.ButtonRole.AcceptRole,
        )
        quit_btn = box.addButton("退出" if zh else "Quit", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(recheck_btn)
        prepare_qt_modal_for_macos(box)
        box.exec()
        clicked = box.clickedButton()
        if clicked == quit_btn:
            return False
        if clicked == term_btn:
            script = f'tell application "Terminal" to do script "{pull_cmd}"'
            subprocess.Popen(["osascript", "-e", script])  # noqa: S603, S607
            continue
        # recheck
        models = list_ollama_models()
        if models:
            return True
