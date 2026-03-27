"""Shared pytest hooks."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_recommended_ollama_cache() -> None:
    from talky.recommended_ollama import reset_recommended_ollama_cache

    reset_recommended_ollama_cache()
    yield
    reset_recommended_ollama_cache()
