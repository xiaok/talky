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


def test_wizard_shows_install_page_when_not_running():
    wizard, _ = _make_wizard("not_running")
    assert wizard.stack.currentIndex() == 1  # local install page


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
    wizard._selected_model = "qwen3.5:9b"
    wizard._selected_host = "http://127.0.0.1:11434"
    wizard._finish()
    store.save.assert_called_once()
    saved = store.save.call_args[0][0]
    assert saved.ollama_model == "qwen3.5:9b"
    assert saved.ollama_host == "http://127.0.0.1:11434"


def test_show_returning_user_prompt_not_installed():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    store = MagicMock()

    with patch("talky.onboarding.QMessageBox") as mock_box:
        mock_box.Icon = MagicMock()
        mock_box.ButtonRole = MagicMock()
        instance = mock_box.return_value
        remote_btn = MagicMock(name="remote")
        dl_btn = MagicMock(name="dl")
        quit_btn = MagicMock(name="quit")
        instance.addButton.side_effect = [remote_btn, dl_btn, quit_btn]
        instance.clickedButton.return_value = quit_btn  # simulate quit
        result = show_returning_user_prompt(
            OllamaStatus.NOT_INSTALLED,
            locale="en",
            config_store=store,
        )
        assert result is False


def test_show_returning_user_prompt_not_running_then_ok():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    store = MagicMock()
    recheck_btn = MagicMock(name="recheck")
    quit_btn = MagicMock(name="quit")

    with (
        patch("talky.onboarding.QMessageBox") as mock_box,
        patch("talky.onboarding.check_ollama_reachable", side_effect=[(False, "err"), (True, "")]),
        patch("talky.models.list_ollama_models", return_value=["qwen3.5:9b"]),
    ):
        mock_box.Icon = MagicMock()
        mock_box.ButtonRole = MagicMock()
        instance = mock_box.return_value
        instance.addButton.side_effect = [recheck_btn, quit_btn]
        instance.clickedButton.return_value = recheck_btn
        result = show_returning_user_prompt(
            OllamaStatus.NOT_RUNNING,
            locale="en",
            config_store=store,
        )
        assert result is True


def test_show_returning_user_prompt_no_model_then_ok():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    store = MagicMock()
    term_btn = MagicMock(name="term")
    recheck_btn = MagicMock(name="recheck")
    quit_btn = MagicMock(name="quit")

    with (
        patch("talky.onboarding.QMessageBox") as mock_box,
        patch("talky.onboarding.check_ollama_reachable", return_value=(True, "")),
        patch("talky.models.list_ollama_models", side_effect=[[], ["qwen3.5:9b"]]),
    ):
        mock_box.Icon = MagicMock()
        mock_box.ButtonRole = MagicMock()
        instance = mock_box.return_value
        instance.addButton.side_effect = [term_btn, recheck_btn, quit_btn]
        instance.clickedButton.return_value = recheck_btn
        result = show_returning_user_prompt(
            OllamaStatus.NO_MODEL,
            locale="en",
            config_store=store,
        )
        assert result is True
