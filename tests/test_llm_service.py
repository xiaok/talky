from __future__ import annotations

import importlib
import sys
import types

import pytest


def _load_llm_service_with_fake_ollama(chat_impl, generate_impl=None):
    if generate_impl is None:
        generate_impl = lambda **kwargs: None  # noqa: E731, ANN001

    def _client_factory(host=None):  # noqa: ANN001
        return types.SimpleNamespace(chat=chat_impl, generate=generate_impl)

    fake_ollama = types.SimpleNamespace(Client=_client_factory)
    sys.modules["ollama"] = fake_ollama
    sys.modules.pop("talky.llm_service", None)
    return importlib.import_module("talky.llm_service")


def test_clean_uses_content_stream_when_available() -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "整理后", "thinking": "internal"}},
            {"message": {"content": "文本", "thinking": ""}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    assert result == "整理后文本"


def test_clean_is_silent_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "整理后", "thinking": "internal"}},
            {"message": {"content": "文本", "thinking": ""}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    captured = capsys.readouterr()
    assert result == "整理后文本"
    assert captured.out == ""


def test_clean_prints_stream_when_debug_enabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "整理后", "thinking": "internal"}},
            {"message": {"content": "文本", "thinking": ""}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy", debug_stream=True)

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    captured = capsys.readouterr()
    assert result == "整理后文本"
    assert "internal" in captured.out
    assert "整理后文本" in captured.out


def test_clean_never_returns_thinking_fallback() -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "", "thinking": "建议你先..."}},
            {"message": {"content": "", "thinking": "再优化..."}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="你来操作", dictionary_terms=[])

    assert result == "你来操作"


def test_warm_up_uses_short_chat_request() -> None:
    captured = {}

    def chat_impl(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {"message": {"content": "ok"}}

    def generate_impl(**kwargs):  # noqa: ANN003
        del kwargs
        raise AssertionError("warm_up should not use ollama.generate")

    llm_service = _load_llm_service_with_fake_ollama(chat_impl, generate_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")
    cleaner.warm_up()

    assert captured["model"] == "dummy"
    assert captured["think"] is False
    assert captured["stream"] is False
    assert captured["messages"] == [{"role": "user", "content": "ping"}]


def test_clean_falls_back_to_http_when_sdk_chat_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        raise RuntimeError("sdk unavailable")

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")
    monkeypatch.setattr(
        cleaner,
        "_chat_via_http",
        lambda **kwargs: [  # noqa: ANN003
            {"message": {"content": "fallback result", "thinking": ""}}
        ],
    )

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    assert result == "fallback result"
