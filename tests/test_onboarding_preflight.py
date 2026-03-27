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

    with (
        patch("talky.permissions.shutil.which", return_value=None),
        patch("talky.permissions.os.path.isfile", return_value=False),
    ):
        assert is_ollama_installed() is False


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

    with patch("locale.getlocale", return_value=("zh_CN", "UTF-8")):
        assert detect_system_locale() == "zh"


def test_detect_system_locale_en():
    from talky.onboarding import detect_system_locale

    with patch("locale.getlocale", return_value=("en_US", "UTF-8")):
        assert detect_system_locale() == "en"


def test_detect_system_locale_none():
    from talky.onboarding import detect_system_locale

    with patch("locale.getlocale", return_value=(None, None)):
        assert detect_system_locale() == "en"


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
