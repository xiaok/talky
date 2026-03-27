from __future__ import annotations

import importlib
import json
import sys
import types

import pytest


def test_check_ollama_reachable_http_success(monkeypatch: pytest.MonkeyPatch) -> None:
    permissions = importlib.import_module("talky.permissions")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            del exc_type, exc, tb
            return False

        def read(self) -> bytes:
            return json.dumps({"models": []}).encode("utf-8")

    monkeypatch.setattr(
        permissions.urllib.request,
        "urlopen",
        lambda request, timeout=8: _Resp(),  # noqa: ANN001, ARG005
    )
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")

    ok, error = permissions.check_ollama_reachable()

    assert ok is True
    assert error == ""


def test_check_ollama_reachable_reports_unavailable_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permissions = importlib.import_module("talky.permissions")

    monkeypatch.setattr(
        permissions.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("connection refused")),  # noqa: ARG005
    )
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")

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
