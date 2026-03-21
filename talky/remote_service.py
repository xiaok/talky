"""Cloud processing client — sends audio to Talky Cloud server."""

from __future__ import annotations

import json
import urllib.request
import uuid
from pathlib import Path

# Cloudflare WAF / bot rules often block urllib's default User-Agent (Python-urllib/...).
_DEFAULT_USER_AGENT = "Talky/1.0 (macOS; Cloud)"


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
        try:
            req = urllib.request.Request(
                url=f"{self.api_url}/api/health",
                headers={"User-Agent": _DEFAULT_USER_AGENT},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
        except Exception:
            return False


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
