"""Talky Cloud — FastAPI server for remote ASR + LLM processing.

Deploy on a Mac Mini (Apple Silicon) with Whisper and Ollama.
Clients send audio, receive cleaned text. No model downloads needed on client side.

Usage:
    cd talky
    python talky-server/main.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import mlx_whisper
import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from talky.dictionary_corrector import apply_phonetic_dictionary, normalize_person_pronouns
from talky.dictionary_entries import (
    extract_person_terms,
    extract_terms,
    parse_dictionary_entries,
)
from talky.llm_service import OllamaTextCleaner
from talky.models import detect_ollama_model
from talky.prompting import build_asr_initial_prompt
from talky.text_guard import (
    collapse_duplicate_output,
    enforce_pronoun_consistency,
    enforce_source_boundaries,
)

_SERVER_DIR = Path(__file__).resolve().parent
_API_KEYS_FILE = _SERVER_DIR / "api_keys.json"

WHISPER_MODEL = os.environ.get("TALKY_WHISPER_MODEL", "mlx-community/whisper-large-v3-mlx")
OLLAMA_MODEL = os.environ.get("TALKY_OLLAMA_MODEL", "")
DEFAULT_LANGUAGE = os.environ.get("TALKY_LANGUAGE", "zh")
SERVER_PORT = int(os.environ.get("TALKY_PORT", "8000"))

_gpu_semaphore = asyncio.Semaphore(1)

_opencc_simplifier = None


def _normalize_simplified(text: str) -> str:
    global _opencc_simplifier
    if not text:
        return text
    if _opencc_simplifier is None:
        try:
            from opencc import OpenCC
            _opencc_simplifier = OpenCC("t2s")
        except Exception:
            return text
    try:
        return _opencc_simplifier.convert(text)
    except Exception:
        return text


def _load_api_keys() -> dict[str, str]:
    if _API_KEYS_FILE.exists():
        with open(_API_KEYS_FILE) as f:
            return json.load(f)
    return {}


_api_keys: dict[str, str] = {}
_llm: OllamaTextCleaner | None = None
# Reported on /api/health for client startup checks (non-empty when server is usable).
_advertised_llm_model: str = ""


def _get_llm() -> OllamaTextCleaner:
    global _llm
    if _llm is None:
        model = OLLAMA_MODEL or detect_ollama_model()
        if not model:
            raise RuntimeError("No Ollama model found. Run: ollama pull <model>")
        _llm = OllamaTextCleaner(model_name=model)
        print(f"[Talky Cloud] LLM model: {model}")
    return _llm


def _verify_api_key(key: str) -> str:
    for user_id, stored_key in _api_keys.items():
        if stored_key == key:
            return user_id
    raise HTTPException(status_code=401, detail="Invalid API key")


def _run_pipeline(audio_bytes: bytes, dictionary: list[str], language: str) -> dict:
    """Full processing pipeline: audio bytes → cleaned text."""
    llm = _get_llm()

    audio_buf = io.BytesIO(audio_bytes)
    audio_np, _sr = sf.read(audio_buf, dtype="float32")
    if audio_np.ndim > 1:
        audio_np = audio_np[:, 0]

    entries = parse_dictionary_entries(dictionary)
    dict_terms = extract_terms(entries)
    person_terms = extract_person_terms(entries)
    asr_prompt = build_asr_initial_prompt(dict_terms)

    asr_start = time.perf_counter()
    kwargs = {"initial_prompt": asr_prompt, "language": language}
    try:
        result = mlx_whisper.transcribe(audio_np, path_or_hf_repo=WHISPER_MODEL, **kwargs)
    except TypeError:
        result = mlx_whisper.transcribe(audio_np, WHISPER_MODEL, **kwargs)
    raw_text = (result.get("text", "") if isinstance(result, dict) else str(result)).strip()
    asr_ms = int((time.perf_counter() - asr_start) * 1000)

    if not raw_text:
        return {"text": "", "raw": "", "asr_ms": asr_ms, "llm_ms": 0, "error": "ASR returned empty"}

    corrected = apply_phonetic_dictionary(raw_text, dict_terms)

    if len(corrected.replace(" ", "").strip()) < 2:
        return {"text": corrected, "raw": raw_text, "asr_ms": asr_ms, "llm_ms": 0}

    llm_start = time.perf_counter()
    final_text = llm.clean(raw_text=corrected, dictionary_terms=dict_terms)
    llm_ms = int((time.perf_counter() - llm_start) * 1000)

    final_text = apply_phonetic_dictionary(final_text, dict_terms)
    final_text = normalize_person_pronouns(final_text, person_terms)
    final_text = enforce_pronoun_consistency(corrected, final_text)
    final_text = enforce_source_boundaries(corrected, final_text)
    final_text = collapse_duplicate_output(final_text)
    final_text = _normalize_simplified(final_text)

    if not final_text:
        final_text = corrected

    print(f"[Talky Cloud] ASR={asr_ms}ms LLM={llm_ms}ms len={len(final_text)}")
    return {"text": final_text, "raw": raw_text, "asr_ms": asr_ms, "llm_ms": llm_ms}


def _warmup() -> None:
    try:
        silent = np.zeros(8000, dtype=np.float32)
        kwargs = {"initial_prompt": "", "language": DEFAULT_LANGUAGE}
        try:
            mlx_whisper.transcribe(silent, path_or_hf_repo=WHISPER_MODEL, **kwargs)
        except TypeError:
            mlx_whisper.transcribe(silent, WHISPER_MODEL, **kwargs)
        print("[Talky Cloud] Whisper warm-up done")
    except Exception as e:
        print(f"[Talky Cloud] Whisper warm-up failed: {e}")
    try:
        _get_llm().warm_up()
        print("[Talky Cloud] Ollama warm-up done")
    except Exception as e:
        print(f"[Talky Cloud] Ollama warm-up skipped: {e}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _api_keys
    _api_keys = _load_api_keys()
    key_count = len(_api_keys)
    print(f"[Talky Cloud] Loaded {key_count} API key(s)")
    if key_count == 0:
        print(f"[Talky Cloud] WARNING: No API keys in {_API_KEYS_FILE}")
        print("[Talky Cloud] Create api_keys.json: {\"user1\": \"sk-your-secret-key\"}")

    global _advertised_llm_model

    print(f"[Talky Cloud] Whisper model: {WHISPER_MODEL}")
    print("[Talky Cloud] Warming up models...")
    await asyncio.get_event_loop().run_in_executor(None, _warmup)
    if _llm is not None:
        _advertised_llm_model = (_llm.model_name or "").strip()
    else:
        _advertised_llm_model = (OLLAMA_MODEL or detect_ollama_model() or "").strip()
    print(f"[Talky Cloud] Ready on port {SERVER_PORT}")
    yield


app = FastAPI(title="Talky Cloud", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
async def health(x_api_key: str | None = Header(None, alias="X-API-Key")):
    """When api_keys.json has entries, clients must send a valid X-API-Key."""
    if _api_keys:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="API key required")
        _verify_api_key(x_api_key)

    wm = (WHISPER_MODEL or "").strip()
    lm = (_advertised_llm_model or "").strip()
    if not wm or not lm:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "whisper_model": wm,
                "llm_model": lm,
                "detail": "ASR or LLM model is not ready on this server",
            },
        )
    return {"status": "ok", "whisper_model": WHISPER_MODEL, "llm_model": _advertised_llm_model}


@app.post("/api/process")
async def process(
    audio: UploadFile = File(...),
    dictionary: str = Form(default="[]"),
    language: str = Form(default="zh"),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    user_id = _verify_api_key(x_api_key)
    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Audio file too small")

    try:
        dict_list = json.loads(dictionary)
        if not isinstance(dict_list, list):
            dict_list = []
    except json.JSONDecodeError:
        dict_list = []

    async with _gpu_semaphore:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_pipeline, audio_bytes, dict_list, language)

    result["user"] = user_id
    return JSONResponse(content=result)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
