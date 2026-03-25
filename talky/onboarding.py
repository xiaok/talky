from __future__ import annotations

import locale


def detect_system_locale() -> str:
    """Return 'zh' if macOS system language is Chinese, else 'en'."""
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"
