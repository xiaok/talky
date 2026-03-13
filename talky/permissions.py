from __future__ import annotations

import json
import os
import urllib.request


def is_accessibility_trusted(prompt: bool = False) -> bool:
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: prompt}))
    except Exception:
        return False


def check_ollama_reachable() -> tuple[bool, str]:
    try:
        import ollama

        ollama.list()
        return True, ""
    except Exception as exc:
        try:
            host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
            request = urllib.request.Request(  # noqa: S310
                url=f"{host}/api/tags",
                headers={"Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, dict) and "models" in data:
                return True, ""
            return False, "Ollama /api/tags response format is invalid."
        except Exception:
            return False, f"Ollama service unavailable: {exc}"
