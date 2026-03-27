from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

from talky.version_checker import CURRENT_BUILD_ID, CURRENT_VERSION

_LOCK = threading.Lock()
_HOOKS_INSTALLED = False
_SETTINGS_SUPPLIER: Callable[[], object | None] | None = None


def error_report_path() -> Path:
    return Path.home() / ".talky" / "logs" / "error-msg.md"


def append_error_report(
    message: str,
    *,
    source: str,
    exc: BaseException | None = None,
    settings: object | None = None,
) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    pkg = _detect_package_name()
    exe = sys.executable
    section = [
        f"## {ts} | {source}",
        "",
        f"- version: `{CURRENT_VERSION}`",
        f"- build_id: `{CURRENT_BUILD_ID}`",
        f"- package: `{pkg}`",
        f"- executable: `{exe}`",
    ]
    settings_line = _format_settings(settings)
    if settings_line:
        section.append(settings_line)
    section.extend(
        [
            "",
            "### Error",
            "```text",
            message.strip() or "(empty message)",
            "```",
        ]
    )
    if exc is not None:
        section.extend(
            [
                "",
                "### Traceback",
                "```text",
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(),
                "```",
            ]
        )
    section.append("")
    payload = "\n".join(section) + "\n"

    try:
        path = error_report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(payload)
    except Exception:
        pass


def install_exception_report_hooks(
    settings_supplier: Callable[[], object | None] | None = None,
) -> None:
    global _HOOKS_INSTALLED, _SETTINGS_SUPPLIER
    if _HOOKS_INSTALLED:
        return
    _SETTINGS_SUPPLIER = settings_supplier
    _HOOKS_INSTALLED = True

    previous_excepthook = sys.excepthook
    previous_threading_hook = getattr(threading, "excepthook", None)

    def _handle_main(exc_type, exc_value, exc_tb):  # noqa: ANN001
        append_error_report(
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).strip(),
            source="sys.excepthook",
            exc=exc_value,
            settings=_safe_settings(),
        )
        previous_excepthook(exc_type, exc_value, exc_tb)

    def _handle_thread(args):  # noqa: ANN001
        append_error_report(
            "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                )
            ).strip(),
            source=f"threading.excepthook:{args.thread.name}",
            exc=args.exc_value,
            settings=_safe_settings(),
        )
        if previous_threading_hook is not None:
            previous_threading_hook(args)

    sys.excepthook = _handle_main
    if previous_threading_hook is not None:
        threading.excepthook = _handle_thread


def _safe_settings() -> object | None:
    if _SETTINGS_SUPPLIER is None:
        return None
    try:
        return _SETTINGS_SUPPLIER()
    except Exception:
        return None


def _detect_package_name() -> str:
    exe = Path(sys.executable)
    for parent in exe.parents:
        if parent.name.endswith(".app"):
            return parent.name
    return exe.name


def _format_settings(settings: object | None) -> str:
    if settings is None:
        return ""
    try:
        mode = getattr(settings, "mode", None)
        hotkey = getattr(settings, "hotkey", None)
        whisper_model = getattr(settings, "whisper_model", None)
        ollama_model = getattr(settings, "ollama_model", None)
        ollama_host = getattr(settings, "ollama_host", None)
        return (
            "- settings: "
            f"`mode={mode}` "
            f"`hotkey={hotkey}` "
            f"`whisper_model={whisper_model}` "
            f"`ollama_model={ollama_model}` "
            f"`ollama_host={ollama_host}`"
        )
    except Exception:
        return ""
