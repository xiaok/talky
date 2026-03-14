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


def test_check_microphone_granted_true_when_avfoundation_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permissions = importlib.import_module("talky.permissions")

    fake_av = types.SimpleNamespace(
        AVMediaTypeAudio="audio",
        AVAuthorizationStatusNotDetermined=0,
        AVAuthorizationStatusAuthorized=3,
        AVCaptureDevice=types.SimpleNamespace(
            authorizationStatusForMediaType_=lambda media: 3  # noqa: ARG005
        ),
    )
    monkeypatch.setitem(sys.modules, "AVFoundation", fake_av)

    ok, error = permissions.check_microphone_granted()

    assert ok is True
    assert error == ""


def test_check_microphone_granted_false_when_avfoundation_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permissions = importlib.import_module("talky.permissions")

    fake_av = types.SimpleNamespace(
        AVMediaTypeAudio="audio",
        AVAuthorizationStatusNotDetermined=0,
        AVAuthorizationStatusAuthorized=3,
        AVCaptureDevice=types.SimpleNamespace(
            authorizationStatusForMediaType_=lambda media: 2  # noqa: ARG005
        ),
    )
    monkeypatch.setitem(sys.modules, "AVFoundation", fake_av)

    ok, error = permissions.check_microphone_granted()

    assert ok is False
    assert "not granted" in error.lower()


def test_request_microphone_permission_requests_when_not_determined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permissions = importlib.import_module("talky.permissions")

    state = {"status": 0}

    def status_for_media_type(_media):
        return state["status"]

    def request_access(_media, handler):
        state["status"] = 3
        handler(True)

    fake_av = types.SimpleNamespace(
        AVMediaTypeAudio="audio",
        AVAuthorizationStatusNotDetermined=0,
        AVAuthorizationStatusAuthorized=3,
        AVCaptureDevice=types.SimpleNamespace(
            authorizationStatusForMediaType_=status_for_media_type,
            requestAccessForMediaType_completionHandler_=request_access,
        ),
    )
    monkeypatch.setitem(sys.modules, "AVFoundation", fake_av)

    ok, error = permissions.request_microphone_permission()

    assert ok is True
    assert error == ""
