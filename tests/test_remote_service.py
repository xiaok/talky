from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytest.importorskip("urllib.request")

from talky.remote_service import verify_cloud_server


def test_verify_cloud_server_empty_url():
    ok, err, data = verify_cloud_server("", "")
    assert ok is False
    assert "empty" in err.lower()
    assert data is None


def test_verify_cloud_server_ok():
    payload = json.dumps(
        {
            "status": "ok",
            "whisper_model": "mlx-community/whisper-large-v3-mlx",
            "llm_model": "qwen3.5:9b",
        }
    ).encode()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return payload

    with patch("talky.remote_service.urllib.request.urlopen", return_value=_Resp()):
        ok, err, data = verify_cloud_server("http://127.0.0.1:8000", "sk-test")

    assert ok is True
    assert err == ""
    assert data is not None
    assert data["llm_model"] == "qwen3.5:9b"


def test_verify_cloud_server_degraded_status():
    payload = json.dumps(
        {"status": "degraded", "whisper_model": "w", "llm_model": "", "detail": "x"}
    ).encode()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return payload

    with patch("talky.remote_service.urllib.request.urlopen", return_value=_Resp()):
        ok, err, _ = verify_cloud_server("http://h", "k")

    assert ok is False
    assert "x" in err or "not ready" in err.lower()


def test_verify_cloud_server_missing_llm_field():
    payload = json.dumps(
        {"status": "ok", "whisper_model": "w-only"}
    ).encode()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return payload

    with patch("talky.remote_service.urllib.request.urlopen", return_value=_Resp()):
        ok, err, _ = verify_cloud_server("http://h", "")

    assert ok is False
    assert "LLM" in err
