from __future__ import annotations

import enum
import locale

from talky.models import detect_ollama_model
from talky.permissions import check_ollama_reachable, is_ollama_installed


class OllamaStatus(enum.Enum):
    READY = "ready"
    NOT_INSTALLED = "not_installed"
    NOT_RUNNING = "not_running"
    NO_MODEL = "no_model"


def run_preflight_check() -> OllamaStatus:
    """Check Ollama installation, service, and model availability."""
    if not is_ollama_installed():
        reachable, _ = check_ollama_reachable()
        if not reachable:
            return OllamaStatus.NOT_INSTALLED
    reachable, _ = check_ollama_reachable()
    if not reachable:
        return OllamaStatus.NOT_RUNNING
    if not detect_ollama_model():
        return OllamaStatus.NO_MODEL
    return OllamaStatus.READY


def detect_system_locale() -> str:
    """Return 'zh' if macOS system language is Chinese, else 'en'."""
    try:
        lang, _ = locale.getdefaultlocale()
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
    "go_download": "前往下载",
    "recheck_install": "我已安装，重新检测",
    "remote_title": "连接远端 Ollama",
    "remote_host": "Ollama 地址",
    "test_connection": "检测连接",
    "connection_ok": "连接成功",
    "connection_fail": "连接失败",
    "select_model": "选择模型",
    "model_title": "准备模型",
    "recommended": "推荐模型",
    "copy_command": "复制命令",
    "recheck_model": "我已下载，重新检测",
    "complete_title": "一切就绪！",
    "complete_msg": "按住 Fn 键即可开始语音输入",
    "done": "完成",
    "next": "下一步",
    "back": "上一步",
}


def _wiz_tr(loc: str, en: str, key: str) -> str:
    if loc == "zh":
        return _WIZARD_ZH.get(key, en)
    return en


# ---------------------------------------------------------------------------
# OnboardingWizard
# ---------------------------------------------------------------------------

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


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

        self.setWindowTitle(_wiz_tr(locale, "Talky Setup Wizard", "window_title"))
        self.setMinimumSize(520, 420)

        # Apply iOS-style stylesheet
        from talky.ui import IOS26_STYLESHEET
        self.setStyleSheet(IOS26_STYLESHEET)

        # Build pages
        self.stack = QStackedWidget()
        self._build_page0_mode_selection()
        self._build_page1_local_install()
        self._build_page2_remote_config()
        self._build_page3_model_prep()
        self._build_page4_complete()

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        # Set starting page based on status
        start_page = {
            OllamaStatus.NOT_INSTALLED: 0,
            OllamaStatus.NOT_RUNNING: 1,
            OllamaStatus.NO_MODEL: 3,
            OllamaStatus.READY: 4,
        }.get(ollama_status, 0)
        self.stack.setCurrentIndex(start_page)

    # -- Page 0: Mode Selection ------------------------------------------------

    def _build_page0_mode_selection(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        layout.addSpacing(20)

        # Card: Run locally
        local_btn = QPushButton(
            _wiz_tr(self._locale, "Run locally", "run_local")
        )
        local_btn.setObjectName("PrimaryButton")
        local_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout.addWidget(local_btn)

        local_desc = QLabel(
            _wiz_tr(
                self._locale,
                "Install Ollama on this Mac",
                "run_local_desc",
            )
        )
        local_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        local_desc.setWordWrap(True)
        layout.addWidget(local_desc)
        layout.addSpacing(10)

        # Card: Connect remote
        remote_btn = QPushButton(
            _wiz_tr(self._locale, "Connect remote", "connect_remote")
        )
        remote_btn.setObjectName("SecondaryButton")
        remote_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        layout.addWidget(remote_btn)

        remote_desc = QLabel(
            _wiz_tr(
                self._locale,
                "Use Ollama on another device in LAN",
                "connect_remote_desc",
            )
        )
        remote_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        remote_desc.setWordWrap(True)
        layout.addWidget(remote_desc)

        self.stack.addWidget(page)

    # -- Page 1: Local Install Guide -------------------------------------------

    def _build_page1_local_install(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(
            _wiz_tr(
                self._locale,
                "Please download and install Ollama first",
                "install_title",
            )
        )
        title.setObjectName("CardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)
        layout.addSpacing(20)

        dl_btn = QPushButton(
            _wiz_tr(self._locale, "Go to Download", "go_download")
        )
        dl_btn.setObjectName("PrimaryButton")
        dl_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
        )
        layout.addWidget(dl_btn)
        layout.addSpacing(10)

        recheck_btn = QPushButton(
            _wiz_tr(self._locale, "I've installed, re-check", "recheck_install")
        )
        recheck_btn.setObjectName("SecondaryButton")
        recheck_btn.clicked.connect(self._recheck_install)
        layout.addWidget(recheck_btn)

        self._install_status_label = QLabel("")
        self._install_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._install_status_label.setWordWrap(True)
        layout.addWidget(self._install_status_label)

        self.stack.addWidget(page)

    def _recheck_install(self) -> None:
        reachable, _ = check_ollama_reachable()
        if reachable:
            from talky.models import list_ollama_models
            models = list_ollama_models()
            if models:
                self._selected_model = models[0]
                self.stack.setCurrentIndex(4)
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
        self._selected_model = self._remote_model_combo.currentText()
        self.stack.setCurrentIndex(4)

    # -- Page 3: Model Preparation ---------------------------------------------

    def _build_page3_model_prep(self) -> None:
        from talky.models import RECOMMENDED_OLLAMA_MODEL

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(
            _wiz_tr(self._locale, "Prepare Model", "model_title")
        )
        title.setObjectName("CardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(10)

        # Model combo (visible if local models exist)
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

        # Recommended model section (visible if no models)
        self._recommended_label = QLabel(
            _wiz_tr(self._locale, "Recommended model", "recommended")
            + f": {RECOMMENDED_OLLAMA_MODEL}"
        )
        self._recommended_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._recommended_label)

        cmd = f"ollama pull {RECOMMENDED_OLLAMA_MODEL}"
        self._pull_cmd_label = QLabel(f"<code>{cmd}</code>")
        self._pull_cmd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pull_cmd_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._pull_cmd_label)

        copy_btn = QPushButton(
            _wiz_tr(self._locale, "Copy Command", "copy_command")
        )
        copy_btn.setObjectName("SecondaryButton")
        copy_btn.clicked.connect(lambda: self._copy_pull_command(cmd))
        layout.addWidget(copy_btn)

        recheck_btn = QPushButton(
            _wiz_tr(self._locale, "I've downloaded, re-check", "recheck_model")
        )
        recheck_btn.setObjectName("SecondaryButton")
        recheck_btn.clicked.connect(self._recheck_models)
        layout.addWidget(recheck_btn)

        self._model_status_label = QLabel("")
        self._model_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._model_status_label.setWordWrap(True)
        layout.addWidget(self._model_status_label)

        # Populate with current models
        self._refresh_model_combo()

        self.stack.addWidget(page)

    def _refresh_model_combo(self) -> None:
        from talky.models import list_ollama_models

        models = list_ollama_models()
        self._model_combo.clear()
        if models:
            self._model_combo.addItems(models)
            self._model_combo.setVisible(True)
            self._model_combo_label.setVisible(True)
            self._model_next_btn.setVisible(True)
            self._recommended_label.setVisible(False)
            self._pull_cmd_label.setVisible(False)
        else:
            self._model_combo.setVisible(False)
            self._model_combo_label.setVisible(False)
            self._model_next_btn.setVisible(False)
            self._recommended_label.setVisible(True)
            self._pull_cmd_label.setVisible(True)

    @staticmethod
    def _copy_pull_command(cmd: str) -> None:
        import pyperclip
        pyperclip.copy(cmd)

    def _model_next(self) -> None:
        self._selected_model = self._model_combo.currentText()
        self.stack.setCurrentIndex(4)

    def _recheck_models(self) -> None:
        from talky.models import list_ollama_models

        models = list_ollama_models()
        if models:
            self._model_combo.clear()
            self._model_combo.addItems(models)
            self._refresh_model_combo()
            # Auto-advance if models found
            self._selected_model = models[0]
            self.stack.setCurrentIndex(4)
        else:
            self._model_status_label.setText(
                _wiz_tr(
                    self._locale,
                    "No models found yet. Please run the pull command.",
                    "connection_fail",
                )
            )

    # -- Page 4: Complete ------------------------------------------------------

    def _build_page4_complete(self) -> None:
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

    # -- Finish ----------------------------------------------------------------

    def _finish(self) -> None:
        from talky.models import AppSettings
        settings = AppSettings(
            ollama_model=self._selected_model,
            ollama_host=self._selected_host,
        )
        self._config_store.save(settings)
        self.accept()


def show_returning_user_prompt(status: OllamaStatus, locale: str = "en") -> None:
    """Show a brief non-blocking QMessageBox for returning users."""
    from talky.models import RECOMMENDED_OLLAMA_MODEL

    box = QMessageBox()
    box.setWindowTitle("Talky")
    box.setIcon(QMessageBox.Icon.Warning)

    if status == OllamaStatus.NOT_INSTALLED:
        if locale == "zh":
            box.setText("未检测到 Ollama，请安装后重启 Talky。")
            box.setInformativeText("访问 ollama.com/download 下载安装。")
        else:
            box.setText("Ollama not detected. Please install and restart Talky.")
            box.setInformativeText("Visit ollama.com/download to install.")
    elif status == OllamaStatus.NOT_RUNNING:
        if locale == "zh":
            box.setText("Ollama 未启动。")
            box.setInformativeText("请在终端运行：ollama serve")
        else:
            box.setText("Ollama is not running.")
            box.setInformativeText("Please run in terminal: ollama serve")
    elif status == OllamaStatus.NO_MODEL:
        cmd = f"ollama pull {RECOMMENDED_OLLAMA_MODEL}"
        if locale == "zh":
            box.setText("未检测到可用模型。")
            box.setInformativeText(f"请在终端运行：{cmd}")
        else:
            box.setText("No models detected.")
            box.setInformativeText(f"Please run in terminal: {cmd}")

    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
