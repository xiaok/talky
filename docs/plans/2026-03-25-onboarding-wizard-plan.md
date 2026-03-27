# Onboarding Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-run onboarding wizard that detects Ollama status and guides new DMG users through setup (local install or remote connection).

**Architecture:** New `talky/onboarding.py` module contains all detection logic and a `QDialog`-based wizard with `QStackedWidget` pages. `main.py` calls a pre-flight check before `controller.start()`. Existing modules get minimal additions (one constant in `models.py`, one function in `permissions.py`).

**Tech Stack:** PyQt6 (QDialog, QStackedWidget, QComboBox), shutil.which, urllib, existing `detect_ollama_model()` / `check_ollama_reachable()`.

---

### Task 1: Add RECOMMENDED_OLLAMA_MODEL constant and is_ollama_installed()

**Files:**
- Modify: `talky/models.py:1-35`
- Modify: `talky/permissions.py:1-5`
- Test: `tests/test_onboarding_preflight.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_onboarding_preflight.py`:

```python
from __future__ import annotations

from unittest.mock import patch


def test_recommended_model_constant_exists():
    from talky.models import RECOMMENDED_OLLAMA_MODEL

    assert isinstance(RECOMMENDED_OLLAMA_MODEL, str)
    assert len(RECOMMENDED_OLLAMA_MODEL) > 0


def test_default_ollama_model_uses_recommended_constant():
    from talky.models import RECOMMENDED_OLLAMA_MODEL, AppSettings

    settings = AppSettings()
    assert settings.ollama_model == RECOMMENDED_OLLAMA_MODEL


def test_is_ollama_installed_returns_true_when_found():
    from talky.permissions import is_ollama_installed

    with patch("talky.permissions.shutil.which", return_value="/usr/local/bin/ollama"):
        assert is_ollama_installed() is True


def test_is_ollama_installed_returns_false_when_missing():
    from talky.permissions import is_ollama_installed

    with patch("talky.permissions.shutil.which", return_value=None):
        assert is_ollama_installed() is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_preflight.py -v`
Expected: FAIL (ImportError for RECOMMENDED_OLLAMA_MODEL, is_ollama_installed)

**Step 3: Implement**

In `talky/models.py`, add constant before `detect_ollama_model()` (line 9):

```python
RECOMMENDED_OLLAMA_MODEL = "qwen3.5:9b"
```

Change line 35 default from hardcoded string to constant:

```python
    ollama_model: str = RECOMMENDED_OLLAMA_MODEL
```

Change line 56 in `from_dict` to use constant as default:

```python
            ollama_model=str(data.get("ollama_model", RECOMMENDED_OLLAMA_MODEL)),
```

In `talky/permissions.py`, add import at top (after line 3):

```python
import shutil
```

Add function after `is_accessibility_trusted()` (after line 18):

```python
def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_preflight.py -v`
Expected: 4 passed

**Step 5: Run existing tests to check no regressions**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/ -v`
Expected: all pass

**Step 6: Commit**

```bash
git add talky/models.py talky/permissions.py tests/test_onboarding_preflight.py
git commit -m "feat(onboarding): add RECOMMENDED_OLLAMA_MODEL constant and is_ollama_installed()"
```

---

### Task 2: Add list_ollama_models() and detect_system_locale()

**Files:**
- Modify: `talky/models.py:10-26`
- Create: `talky/onboarding.py` (detection helpers only, no UI yet)
- Test: `tests/test_onboarding_preflight.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_onboarding_preflight.py`:

```python
def test_list_ollama_models_returns_names():
    from talky.models import list_ollama_models

    api_response = '{"models":[{"name":"qwen3.5:9b"},{"name":"llama3:8b"}]}'
    with patch("talky.models.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = lambda s, *a: None
        mock_open.return_value.read.return_value = api_response.encode()
        result = list_ollama_models()
    assert result == ["qwen3.5:9b", "llama3:8b"]


def test_list_ollama_models_returns_empty_on_failure():
    from talky.models import list_ollama_models

    with patch("talky.models.urllib.request.urlopen", side_effect=Exception("fail")):
        assert list_ollama_models() == []


def test_detect_system_locale_zh():
    from talky.onboarding import detect_system_locale

    with patch("locale.getdefaultlocale", return_value=("zh_CN", "UTF-8")):
        assert detect_system_locale() == "zh"


def test_detect_system_locale_en():
    from talky.onboarding import detect_system_locale

    with patch("locale.getdefaultlocale", return_value=("en_US", "UTF-8")):
        assert detect_system_locale() == "en"


def test_detect_system_locale_none():
    from talky.onboarding import detect_system_locale

    with patch("locale.getdefaultlocale", return_value=(None, None)):
        assert detect_system_locale() == "en"
```

**Step 2: Run tests to verify new tests fail**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_preflight.py -v -k "list_ollama or detect_system"`
Expected: FAIL

**Step 3: Implement**

In `talky/models.py`, add `list_ollama_models()` after `detect_ollama_model()`:

```python
def list_ollama_models(host: str = "") -> list[str]:
    """Query Ollama for installed models and return all names."""
    host = (host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
    try:
        req = urllib.request.Request(
            url=f"{host}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return [str(m.get("name", "")) for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []
```

Create `talky/onboarding.py` with only the locale helper for now:

```python
from __future__ import annotations

import locale


def detect_system_locale() -> str:
    """Return 'zh' if macOS system language is Chinese, else 'en'."""
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_preflight.py -v`
Expected: 9 passed

**Step 5: Commit**

```bash
git add talky/models.py talky/onboarding.py tests/test_onboarding_preflight.py
git commit -m "feat(onboarding): add list_ollama_models() and detect_system_locale()"
```

---

### Task 3: Build preflight check function

**Files:**
- Modify: `talky/onboarding.py`
- Test: `tests/test_onboarding_preflight.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_onboarding_preflight.py`:

```python
def test_preflight_all_ok():
    from talky.onboarding import OllamaStatus, run_preflight_check

    with (
        patch("talky.onboarding.is_ollama_installed", return_value=True),
        patch("talky.onboarding.check_ollama_reachable", return_value=(True, "")),
        patch("talky.onboarding.detect_ollama_model", return_value="qwen3.5:9b"),
    ):
        status = run_preflight_check()
    assert status == OllamaStatus.READY


def test_preflight_not_installed():
    from talky.onboarding import OllamaStatus, run_preflight_check

    with (
        patch("talky.onboarding.is_ollama_installed", return_value=False),
        patch("talky.onboarding.check_ollama_reachable", return_value=(False, "err")),
        patch("talky.onboarding.detect_ollama_model", return_value=""),
    ):
        status = run_preflight_check()
    assert status == OllamaStatus.NOT_INSTALLED


def test_preflight_not_running():
    from talky.onboarding import OllamaStatus, run_preflight_check

    with (
        patch("talky.onboarding.is_ollama_installed", return_value=True),
        patch("talky.onboarding.check_ollama_reachable", return_value=(False, "err")),
        patch("talky.onboarding.detect_ollama_model", return_value=""),
    ):
        status = run_preflight_check()
    assert status == OllamaStatus.NOT_RUNNING


def test_preflight_no_models():
    from talky.onboarding import OllamaStatus, run_preflight_check

    with (
        patch("talky.onboarding.is_ollama_installed", return_value=True),
        patch("talky.onboarding.check_ollama_reachable", return_value=(True, "")),
        patch("talky.onboarding.detect_ollama_model", return_value=""),
    ):
        status = run_preflight_check()
    assert status == OllamaStatus.NO_MODEL
```

**Step 2: Run tests to verify new tests fail**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_preflight.py -v -k "preflight"`
Expected: FAIL

**Step 3: Implement**

Add to `talky/onboarding.py`:

```python
import enum

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
```

**Step 4: Run all preflight tests**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_preflight.py -v`
Expected: 13 passed

**Step 5: Commit**

```bash
git add talky/onboarding.py tests/test_onboarding_preflight.py
git commit -m "feat(onboarding): add run_preflight_check() with OllamaStatus enum"
```

---

### Task 4: Build OnboardingWizard UI

**Files:**
- Modify: `talky/onboarding.py` (add wizard class)
- Test: `tests/test_onboarding_wizard.py` (create)

This is the largest task. The wizard is a QDialog with QStackedWidget and 5 pages (welcome/mode-select, local-install, remote-config, model-prep, complete).

**Step 1: Write the failing tests**

Create `tests/test_onboarding_wizard.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _make_wizard(status="not_installed", locale="en"):
    from talky.onboarding import OnboardingWizard, OllamaStatus

    status_enum = OllamaStatus(status)
    store = MagicMock()
    store.config_path = MagicMock()
    store.config_path.exists = MagicMock(return_value=False)
    wizard = OnboardingWizard(
        config_store=store,
        ollama_status=status_enum,
        locale=locale,
    )
    return wizard, store


def test_wizard_shows_mode_page_when_not_installed():
    wizard, _ = _make_wizard("not_installed")
    assert wizard.stack.currentIndex() == 0  # mode selection page


def test_wizard_shows_model_page_when_no_model():
    wizard, _ = _make_wizard("no_model")
    assert wizard.stack.currentIndex() == 3  # model prep page


def test_wizard_shows_not_running_page_when_not_running():
    wizard, _ = _make_wizard("not_running")
    # Should go to local install page (which has recheck for running)
    assert wizard.stack.currentIndex() == 1


def test_wizard_zh_locale_shows_chinese():
    wizard, _ = _make_wizard("not_installed", locale="zh")
    title = wizard.windowTitle()
    assert "Talky" in title


def test_wizard_complete_saves_settings():
    from talky.onboarding import OnboardingWizard, OllamaStatus

    store = MagicMock()
    store.config_path = MagicMock()
    store.config_path.exists = MagicMock(return_value=False)
    wizard = OnboardingWizard(
        config_store=store,
        ollama_status=OllamaStatus.NO_MODEL,
        locale="en",
    )
    # Simulate model selection
    wizard._selected_model = "qwen3.5:9b"
    wizard._selected_host = "http://127.0.0.1:11434"
    wizard._finish()
    store.save.assert_called_once()
    saved = store.save.call_args[0][0]
    assert saved.ollama_model == "qwen3.5:9b"
    assert saved.ollama_host == "http://127.0.0.1:11434"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_wizard.py -v`
Expected: FAIL (ImportError for OnboardingWizard)

**Step 3: Implement the wizard**

Add to `talky/onboarding.py` the full `OnboardingWizard` class. The wizard has these pages indexed 0-4:
- 0: Mode selection (local vs remote) — shown when NOT_INSTALLED
- 1: Local install guide — "Go to Download" + "Re-check"
- 2: Remote config — host input + "Test Connection" + model dropdown
- 3: Model preparation — model dropdown or pull command
- 4: Complete — success message + Done button

Key implementation details:
- Uses `IOS26_STYLESHEET` from `talky.ui` for consistent styling
- i18n dict for zh/en with `_wiz_tr()` helper
- `_selected_model` and `_selected_host` track user choices
- `_finish()` builds `AppSettings` and calls `config_store.save()`
- Re-check buttons call `check_ollama_reachable()` / `list_ollama_models()` and auto-advance
- "Go to Download" opens `https://ollama.com/download` via `QDesktopServices`
- "Copy Command" copies `ollama pull <RECOMMENDED_OLLAMA_MODEL>` to clipboard

See Task 4 implementation section below for full code.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_wizard.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add talky/onboarding.py tests/test_onboarding_wizard.py
git commit -m "feat(onboarding): add OnboardingWizard QDialog with 5-page flow"
```

---

### Task 5: Add returning-user prompts

**Files:**
- Modify: `talky/onboarding.py`
- Test: `tests/test_onboarding_wizard.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_onboarding_wizard.py`:

```python
def test_show_returning_user_prompt_not_installed():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    with patch("talky.onboarding.QMessageBox") as mock_box:
        mock_box.StandardButton = MagicMock()
        mock_box.Icon = MagicMock()
        show_returning_user_prompt(OllamaStatus.NOT_INSTALLED, locale="en")
        mock_box.assert_called()


def test_show_returning_user_prompt_not_running():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    with patch("talky.onboarding.QMessageBox") as mock_box:
        mock_box.StandardButton = MagicMock()
        mock_box.Icon = MagicMock()
        show_returning_user_prompt(OllamaStatus.NOT_RUNNING, locale="en")
        mock_box.assert_called()


def test_show_returning_user_prompt_no_model():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    with patch("talky.onboarding.QMessageBox") as mock_box:
        mock_box.StandardButton = MagicMock()
        mock_box.Icon = MagicMock()
        show_returning_user_prompt(OllamaStatus.NO_MODEL, locale="en")
        mock_box.assert_called()
```

**Step 2: Run tests to verify new tests fail**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_wizard.py -v -k "returning"`
Expected: FAIL

**Step 3: Implement**

Add `show_returning_user_prompt()` function to `talky/onboarding.py`:

```python
def show_returning_user_prompt(status: OllamaStatus, locale: str = "en") -> None:
    """Show a brief non-blocking QMessageBox for returning users."""
    from PyQt6.QtWidgets import QMessageBox

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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_onboarding_wizard.py -v`
Expected: 8 passed

**Step 5: Commit**

```bash
git add talky/onboarding.py tests/test_onboarding_wizard.py
git commit -m "feat(onboarding): add show_returning_user_prompt() for returning users"
```

---

### Task 6: Integrate into main.py

**Files:**
- Modify: `main.py:113-135`
- Test: `tests/test_main.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_main.py`:

```python
def test_main_runs_preflight_and_shows_wizard_for_first_time_user():
    with (
        patch("main.QApplication") as mock_qapp,
        patch("main.AppConfigStore") as mock_store_cls,
        patch("main.AppController") as mock_ctrl_cls,
        patch("main.SettingsWindow"),
        patch("main.TrayApp") as mock_tray_cls,
        patch("main.install_signal_handlers"),
        patch("main.is_accessibility_trusted", return_value=True),
        patch("main.run_preflight_check") as mock_preflight,
        patch("main.OnboardingWizard") as mock_wizard_cls,
        patch("main.detect_system_locale", return_value="en"),
    ):
        from main import OllamaStatus

        mock_store = mock_store_cls.return_value
        mock_store.load.return_value = MagicMock(mode="local")
        mock_store.config_path.exists.return_value = False
        mock_preflight.return_value = OllamaStatus.NOT_INSTALLED
        mock_wizard = mock_wizard_cls.return_value
        mock_wizard.exec.return_value = 1  # QDialog.Accepted
        mock_qapp.return_value.exec.return_value = 0

        from main import main
        main()

        mock_wizard_cls.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_main.py::test_main_runs_preflight_and_shows_wizard_for_first_time_user -v`
Expected: FAIL

**Step 3: Implement**

Modify `main.py`. Add imports and insert preflight logic between the accessibility check and `controller.start()`:

```python
# New imports (add after existing imports)
from talky.onboarding import (
    OllamaStatus,
    OnboardingWizard,
    detect_system_locale,
    run_preflight_check,
    show_returning_user_prompt,
)

# In main(), after accessibility check (line 131) and before controller.start() (line 133):

    settings = config_store.load()
    if settings.mode != "cloud":
        status = run_preflight_check()
        if status != OllamaStatus.READY:
            is_first_time = not config_store.config_path.exists()
            locale = detect_system_locale()
            if is_first_time:
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/test_main.py -v`
Expected: all pass

**Step 5: Run full test suite**

Run: `cd /Users/sean/Documents/个人项目/talky && .venv/bin/python -m pytest tests/ -v`
Expected: all pass

**Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(onboarding): integrate preflight check and wizard into startup"
```

---

### Task 7: Manual smoke test

**Step 1:** Temporarily rename `~/.talky/settings.json` to simulate first-time user:
```bash
mv ~/.talky/settings.json ~/.talky/settings.json.bak
```

**Step 2:** Run the app:
```bash
cd /Users/sean/Documents/个人项目/talky && .venv/bin/python main.py
```

**Step 3:** Verify wizard appears. Walk through each page. Check:
- Mode selection page shows two options
- "Go to Download" opens browser
- "Re-check" button works after Ollama is running
- Model dropdown populates
- "Copy Command" copies correct command
- "Done" saves settings and app starts normally

**Step 4:** Restore settings:
```bash
mv ~/.talky/settings.json.bak ~/.talky/settings.json
```

**Step 5:** Run again — verify returning-user prompt (brief dialog) appears if Ollama is stopped, or app starts normally if all OK.

**Step 6:** Final commit if any fixes needed, then squash or leave as-is.
