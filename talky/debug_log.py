"""Append-only diagnostic log for remote debugging (e.g. Mac Mini DMG issues).

Writes to: ~/.talky/logs/debug.log

Users can send this file after reproducing a problem.
"""

from __future__ import annotations

import threading
import traceback
from datetime import datetime
from pathlib import Path

_LOG_LOCK = threading.Lock()


def debug_log_path() -> Path:
    return Path.home() / ".talky" / "logs" / "debug.log"


def append_debug_log(message: str, *, exc: BaseException | None = None) -> None:
    """Append one line (or block) with ISO timestamp. Thread-safe."""
    ts = datetime.now().isoformat(timespec="seconds")
    lines = [f"[{ts}] {message}"]
    if exc is not None:
        lines.append(f"[{ts}] exception: {exc!r}")
        lines.append(traceback.format_exc())
    block = "\n".join(lines) + "\n"
    try:
        path = debug_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(block)
            if path.stat().st_size > 512 * 1024:
                _trim_log(path)
    except Exception:
        pass


def _trim_log(path: Path) -> None:
    """Keep last ~400KB if log grows too large."""
    try:
        data = path.read_text(encoding="utf-8")
        if len(data) > 400_000:
            path.write_text(
                "[trimmed older lines]\n" + data[-400_000:],
                encoding="utf-8",
            )
    except Exception:
        pass
