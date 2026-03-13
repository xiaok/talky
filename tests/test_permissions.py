from __future__ import annotations

import importlib
import io
import json
import sys
import types

import pytest


def _load_permissions_with_fake_ollama(list_impl):
    fake_ollama = types.SimpleNamespace(list=list_impl)
    sys.modules["ollama"] = fake_ollama
    sys.modules.pop("talky.permissions", None)
    return importlib.import_module("talky.permissions")


def test_check_ollama_reachable_sdk_success() -> None:
    permissions = _load_permissions_with_fake_ollama(lambda: {"models": []})

    ok, error = permissions.check_ollama_reachable()

    assert ok is True
    assert error == ""


def test_check_ollama_reachable_http_fallback_when_sdk_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_list():
        raise RuntimeError("sdk 502")

    permissions = _load_permissions_with_fake_ollama(broken_list)

    class _Resp:
        def __init__(self) -> None:
            self._buf = io.BytesIO(json.dumps({"models": []}).encode("utf-8"))

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            del exc_type, exc, tb
            return False

    monkeypatch.setattr(
        permissions.urllib.request,
        "urlopen",
        lambda request, timeout=10: _Resp(),  # noqa: ANN001, ARG005
    )

    ok, error = permissions.check_ollama_reachable()

    assert ok is True
    assert error == ""


def test_check_ollama_reachable_reports_unavailable_when_all_fail() -> None:
    def broken_list():
        raise RuntimeError("sdk 502")

    permissions = _load_permissions_with_fake_ollama(broken_list)
    permissions.urllib.request.urlopen = lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: ARG005
        RuntimeError("http failed")
    )

    ok, error = permissions.check_ollama_reachable()

    assert ok is False
    assert "Ollama service unavailable" in error
