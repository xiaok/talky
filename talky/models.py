from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any


RECOMMENDED_OLLAMA_MODEL = "qwen3.5:9b"


def detect_ollama_model(host: str = "") -> str:
    """Query Ollama for installed models and return the first one found."""
    host = (host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
    try:
        req = urllib.request.Request(
            url=f"{host}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        if models:
            return str(models[0].get("name", ""))
    except Exception:
        pass
    return ""


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


@dataclass(slots=True)
class AppSettings:
    custom_dictionary: list[str] = field(default_factory=list)
    hotkey: str = "fn"  # "fn" or "right_option"
    custom_hotkey: list[str] = field(default_factory=list)
    whisper_model: str = "./local_whisper_model"
    ollama_model: str = RECOMMENDED_OLLAMA_MODEL
    ollama_host: str = "http://127.0.0.1:11434"
    ui_locale: str = "en"  # "en" or "mixed"
    language: str = "zh"
    auto_paste_delay_ms: int = 120
    llm_debug_stream: bool = False
    sample_rate: int = 16000
    channels: int = 1
    mode: str = "local"  # "local" | "cloud"
    cloud_api_url: str = ""
    cloud_api_key: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            custom_dictionary=list(data.get("custom_dictionary", [])),
            hotkey=str(data.get("hotkey", "fn")),
            custom_hotkey=list(data.get("custom_hotkey", [])),
            whisper_model=str(
                data.get("whisper_model", "./local_whisper_model")
            ),
            ollama_model=str(data.get("ollama_model", RECOMMENDED_OLLAMA_MODEL)),
            ollama_host=str(data.get("ollama_host", "http://127.0.0.1:11434")).rstrip("/"),
            ui_locale=str(data.get("ui_locale", "en")),
            language=str(data.get("language", "zh")),
            auto_paste_delay_ms=int(data.get("auto_paste_delay_ms", 120)),
            llm_debug_stream=bool(data.get("llm_debug_stream", False)),
            sample_rate=int(data.get("sample_rate", 16000)),
            channels=int(data.get("channels", 1)),
            mode=str(data.get("mode", "local")),
            cloud_api_url=str(data.get("cloud_api_url", "")),
            cloud_api_key=str(data.get("cloud_api_key", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
