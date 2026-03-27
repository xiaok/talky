"""Recommended Ollama model for onboarding — overridable without shipping a new app build.

Merge order (each step overlays the previous):
1. Built-in default from ``talky.models.RECOMMENDED_OLLAMA_MODEL``
2. JSON from URL in env ``TALKY_RECOMMENDED_OLLAMA_JSON_URL`` (optional; 8s timeout; silent skip on failure)
3. Local file ``~/.talky/recommended_ollama.json`` (optional; wins over URL for any field it sets)

Remote/local JSON schema (same shape)::

    {
      "model": "qwen3.5:9b",
      "library_url": "https://ollama.com/library/qwen3",
      "pull_command": "ollama pull qwen3.5:9b"
    }

``model`` is required in overrides when you replace the whole payload; partial merges only apply
keys that are present. ``library_url`` and ``pull_command`` are optional; if ``pull_command`` is
omitted, the UI uses ``ollama pull <model>``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from talky.models import RECOMMENDED_OLLAMA_MODEL

_ENV_JSON_URL = "TALKY_RECOMMENDED_OLLAMA_JSON_URL"
_LOCAL_REL = Path(".talky") / "recommended_ollama.json"
_USER_AGENT = "Talky/1.0 (recommended-ollama-config)"


class RecommendedOllamaConfig:
    __slots__ = ("model", "library_url", "pull_command")

    def __init__(
        self,
        *,
        model: str,
        library_url: str = "",
        pull_command: str = "",
    ) -> None:
        self.model = model.strip() or RECOMMENDED_OLLAMA_MODEL
        self.library_url = (library_url or "").strip()
        self.pull_command = (pull_command or "").strip()

    def pull_command_resolved(self) -> str:
        if self.pull_command:
            return self.pull_command
        return f"ollama pull {self.model}"


_cached: RecommendedOllamaConfig | None = None


def _builtin() -> RecommendedOllamaConfig:
    return RecommendedOllamaConfig(model=RECOMMENDED_OLLAMA_MODEL)


def _parse_overlay(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    m = data.get("model") or data.get("model_name")
    if isinstance(m, str) and m.strip():
        out["model"] = m.strip()
    u = data.get("library_url") or data.get("ollama_library_url")
    if isinstance(u, str):
        out["library_url"] = u.strip()
    p = data.get("pull_command") or data.get("pull")
    if isinstance(p, str):
        out["pull_command"] = p.strip()
    return out


def _merge(base: RecommendedOllamaConfig, overlay: dict[str, str]) -> RecommendedOllamaConfig:
    if not overlay:
        return base
    model = overlay.get("model", base.model)
    lib = overlay.get("library_url", base.library_url)
    pull = overlay.get("pull_command", base.pull_command)
    return RecommendedOllamaConfig(model=model, library_url=lib, pull_command=pull)


def _fetch_url_json(url: str) -> dict[str, str] | None:
    req = urllib.request.Request(
        url=url.strip(),
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        return _parse_overlay(data)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None


def _load_local_file(path: Path) -> dict[str, str] | None:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return _parse_overlay(data)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def load_recommended_ollama_config(*, force_reload: bool = False) -> RecommendedOllamaConfig:
    """Load merged recommended Ollama config (cached for the process unless force_reload)."""
    global _cached
    if _cached is not None and not force_reload:
        return _cached

    spec = _builtin()
    url = os.environ.get(_ENV_JSON_URL, "").strip()
    if url:
        remote = _fetch_url_json(url)
        if remote:
            spec = _merge(spec, remote)

    local_path = Path.home() / _LOCAL_REL
    local = _load_local_file(local_path)
    if local:
        spec = _merge(spec, local)

    _cached = spec
    return spec


def reset_recommended_ollama_cache() -> None:
    """Test hook: clear process cache so the next load re-reads env/file/URL."""
    global _cached
    _cached = None


def recommended_model_name() -> str:
    return load_recommended_ollama_config().model
