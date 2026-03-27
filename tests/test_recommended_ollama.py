from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from talky.recommended_ollama import (
    load_recommended_ollama_config,
    recommended_model_name,
    reset_recommended_ollama_cache,
)


def test_builtin_default():
    cfg = load_recommended_ollama_config(force_reload=True)
    assert cfg.model == "qwen3.5:9b"
    assert "qwen3.5:9b" in cfg.pull_command_resolved()


def test_local_json_overrides_model(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    talky_dir = tmp_path / ".talky"
    talky_dir.mkdir()
    (talky_dir / "recommended_ollama.json").write_text(
        json.dumps(
            {
                "model": "llama3.2:latest",
                "library_url": "https://ollama.com/library/llama3.2",
                "pull_command": "ollama pull llama3.2:latest",
            }
        ),
        encoding="utf-8",
    )
    reset_recommended_ollama_cache()
    cfg = load_recommended_ollama_config(force_reload=True)
    assert cfg.model == "llama3.2:latest"
    assert cfg.library_url.startswith("https://")
    assert cfg.pull_command_resolved() == "ollama pull llama3.2:latest"


def test_local_file_wins_over_remote_url(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "TALKY_RECOMMENDED_OLLAMA_JSON_URL",
        "https://example.invalid/talky-ollama.json",
    )
    talky_dir = tmp_path / ".talky"
    talky_dir.mkdir()
    (talky_dir / "recommended_ollama.json").write_text(
        '{"model": "from-file:7b"}',
        encoding="utf-8",
    )

    remote_payload = json.dumps({"model": "from-remote:9b"}).encode()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return remote_payload

    reset_recommended_ollama_cache()
    with patch("talky.recommended_ollama.urllib.request.urlopen", return_value=_Resp()):
        cfg = load_recommended_ollama_config(force_reload=True)

    assert cfg.model == "from-file:7b"


def test_recommended_model_name_alias():
    reset_recommended_ollama_cache()
    assert recommended_model_name() == load_recommended_ollama_config().model
