"""Cloud processing client — sends audio to Talky Cloud server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

# Cloudflare WAF / bot rules often block urllib's default User-Agent (Python-urllib/...).
_DEFAULT_USER_AGENT = "Talky/1.0 (macOS; Cloud)"


def verify_cloud_server(api_url: str, api_key: str) -> tuple[bool, str, dict[str, Any] | None]:
    """GET /api/health; returns (ok, error_message, payload).

    When the server has API keys configured, ``api_key`` must be valid.
    Requires status ok and non-empty whisper_model + llm_model in the JSON body.
    """
    base = (api_url or "").strip().rstrip("/")
    if not base:
        return False, "Cloud API URL is empty.", None

    headers: dict[str, str] = {"User-Agent": _DEFAULT_USER_AGENT}
    key = (api_key or "").strip()
    if key:
        headers["X-API-Key"] = key

    req = urllib.request.Request(
        url=f"{base}/api/health",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            data: dict[str, Any] = json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = exc.reason or str(exc)
        return False, f"HTTP {exc.code}: {detail}", None
    except Exception as exc:
        return False, str(exc) or "Connection failed.", None

    if data.get("status") != "ok":
        detail = data.get("detail", "Server is not ready.")
        return False, str(detail), None

    wm = data.get("whisper_model")
    lm = data.get("llm_model")
    if not wm or not isinstance(wm, str) or not wm.strip():
        return False, "Server did not report a Whisper (ASR) model.", None
    if not lm or not isinstance(lm, str) or not lm.strip():
        return False, "Server did not report an LLM model.", None

    return True, "", data


class CloudProcessService:
    """Sends audio to a remote Talky Cloud server for ASR + LLM processing."""

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def process(
        self, audio_path: Path, dictionary: list[str], language: str = "zh",
    ) -> str:
        url = f"{self.api_url}/api/process"
        body, boundary = _build_multipart(
            fields={
                "dictionary": json.dumps(dictionary),
                "language": language,
            },
            files={
                "audio": (audio_path.name, audio_path.read_bytes(), "audio/wav"),
            },
        )
        request = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-API-Key": self.api_key,
                "User-Agent": _DEFAULT_USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

        text = str(data.get("text", "")).strip()
        if not text:
            raw = str(data.get("raw", "")).strip()
            if raw:
                return raw
            error = data.get("error", "Cloud returned empty text")
            raise RuntimeError(error)
        return text

    def health_check(self) -> bool:
        ok, _, _ = verify_cloud_server(self.api_url, self.api_key)
        return ok


def _build_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode("utf-8") if isinstance(value, str) else value)
        parts.append(b"\r\n")
    for name, (filename, data, content_type) in files.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary
