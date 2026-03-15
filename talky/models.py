from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AppSettings:
    custom_dictionary: list[str] = field(default_factory=list)
    hotkey: str = "fn"  # "fn" or "right_option"
    custom_hotkey: list[str] = field(default_factory=list)
    whisper_model: str = "./local_whisper_model"
    ollama_model: str = "qwen3.5:9b"
    ollama_host: str = "http://127.0.0.1:11434"
    ui_locale: str = "en"  # "en" or "mixed"
    language: str = "zh"
    auto_paste_delay_ms: int = 120
    llm_debug_stream: bool = False
    sample_rate: int = 16000
    channels: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            custom_dictionary=list(data.get("custom_dictionary", [])),
            hotkey=str(data.get("hotkey", "fn")),
            custom_hotkey=list(data.get("custom_hotkey", [])),
            whisper_model=str(
                data.get("whisper_model", "./local_whisper_model")
            ),
            ollama_model=str(data.get("ollama_model", "qwen3.5:9b")),
            ollama_host=str(data.get("ollama_host", "http://127.0.0.1:11434")).rstrip("/"),
            ui_locale=str(data.get("ui_locale", "en")),
            language=str(data.get("language", "zh")),
            auto_paste_delay_ms=int(data.get("auto_paste_delay_ms", 120)),
            llm_debug_stream=bool(data.get("llm_debug_stream", False)),
            sample_rate=int(data.get("sample_rate", 16000)),
            channels=int(data.get("channels", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
