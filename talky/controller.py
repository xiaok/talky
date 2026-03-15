from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlparse
from pathlib import Path

import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal

from talky.asr_service import MlxWhisperASR
from talky.config_store import AppConfigStore
from talky.dictionary_corrector import apply_phonetic_dictionary, normalize_person_pronouns
from talky.dictionary_entries import (
    extract_person_terms,
    extract_terms,
    parse_dictionary_entries,
)
from talky.focus import get_frontmost_app, has_focus_target
from talky.hotkey import HoldToTalkHotkey
from talky.history_store import HistoryStore
from talky.llm_service import OllamaTextCleaner
from talky.models import AppSettings
from talky.paster import ClipboardPaster
from talky.permissions import check_ollama_reachable
from talky.prompting import build_asr_initial_prompt
from talky.recorder import AudioRecorder
from talky.text_guard import (
    collapse_duplicate_output,
    enforce_pronoun_consistency,
    enforce_source_boundaries,
)

_OPENCC_SIMPLIFIER = None
_MIN_RECORD_DURATION_S = 0.30
_MIN_RECORD_RMS = 0.003
_HOTKEY_COOLDOWN_S = 0.45


def normalize_to_simplified_chinese(text: str) -> str:
    global _OPENCC_SIMPLIFIER
    if not text:
        return text
    if _OPENCC_SIMPLIFIER is None:
        try:
            from opencc import OpenCC
        except Exception:
            return text
        _OPENCC_SIMPLIFIER = OpenCC("t2s")
    try:
        return _OPENCC_SIMPLIFIER.convert(text)
    except Exception:
        return text


class AppController(QObject):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    settings_updated = pyqtSignal(object)
    show_result_popup_signal = pyqtSignal(str)
    show_settings_window_signal = pyqtSignal()

    def __init__(self, config_store: AppConfigStore) -> None:
        super().__init__()
        self.config_store = config_store
        self.settings = self.config_store.load()
        self._apply_ollama_host_env()

        self.recorder = AudioRecorder(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
        )
        self.asr = MlxWhisperASR(
            model_name=self.settings.whisper_model,
            language=self.settings.language,
        )
        self.llm = OllamaTextCleaner(
            model_name=self.settings.ollama_model,
            debug_stream=self.settings.llm_debug_stream,
        )
        self.paster = ClipboardPaster(paste_delay_ms=self.settings.auto_paste_delay_ms)
        self.history_store = HistoryStore(
            Path(__file__).resolve().parent.parent / "history"
        )

        self._is_processing = False
        self._is_recording = False
        self.hotkey: HoldToTalkHotkey | None = None
        self._last_output_text = ""
        self._last_output_ts = 0.0
        self._hotkey_cooldown_until_ts = 0.0

    def start(self) -> None:
        self._start_hotkey()
        self._warm_up_models_async()

    def request_show_settings(self) -> None:
        self.show_settings_window_signal.emit()

    def stop(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
            self.hotkey = None

    def update_settings(self, new_settings: AppSettings) -> None:
        self.settings = new_settings
        self._apply_ollama_host_env()
        self.config_store.save(new_settings)
        self._rebuild_services()
        self._start_hotkey()
        self._warm_up_models_async()
        self.settings_updated.emit(new_settings)
        self.status_signal.emit("Settings saved.")

    def _rebuild_services(self) -> None:
        self._apply_ollama_host_env()
        self.recorder = AudioRecorder(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
        )
        self.asr = MlxWhisperASR(
            model_name=self.settings.whisper_model,
            language=self.settings.language,
        )
        self.llm = OllamaTextCleaner(
            model_name=self.settings.ollama_model,
            debug_stream=self.settings.llm_debug_stream,
        )
        self.paster = ClipboardPaster(paste_delay_ms=self.settings.auto_paste_delay_ms)

    def _apply_ollama_host_env(self) -> None:
        host = (self.settings.ollama_host or "http://127.0.0.1:11434").strip().rstrip("/")
        if not host:
            host = "http://127.0.0.1:11434"
        os.environ["OLLAMA_HOST"] = host

    def _is_local_ollama_host(self, host: str) -> bool:
        value = (host or "").strip()
        if not value:
            return True
        parsed = urlparse(value if "://" in value else f"http://{value}")
        hostname = (parsed.hostname or "").lower()
        return hostname in {"127.0.0.1", "localhost", "::1"}

    def _start_hotkey(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
        self.hotkey = HoldToTalkHotkey(
            key_mode=self.settings.hotkey,
            custom_keys=self.settings.custom_hotkey,
            on_press=self._on_hotkey_pressed,
            on_release=self._on_hotkey_released,
        )
        self.hotkey.start()
        if self.hotkey.using_fallback:
            self.status_signal.emit("Fn hook unavailable. Fallback to Right Option.")

    def _on_hotkey_pressed(self) -> None:
        if time.monotonic() < self._hotkey_cooldown_until_ts:
            return
        if self._is_processing or self._is_recording:
            return
        try:
            self.recorder.start()
            self._is_recording = True
            self.status_signal.emit("Recording started...")
        except sd.PortAudioError as exc:
            self.error_signal.emit(
                "Cannot start microphone. Grant access at "
                "System Settings > Privacy & Security > Microphone.\n"
                f"Details: {exc}"
            )
        except Exception as exc:
            self.error_signal.emit(f"Failed to start recording: {exc}")

    def _on_hotkey_released(self) -> None:
        if not self._is_recording:
            return
        try:
            wav_path = self.recorder.stop_and_dump_wav()
            self._is_recording = False
            duration_s = self.recorder.last_duration_s
            rms = self.recorder.last_rms
            if duration_s < _MIN_RECORD_DURATION_S:
                self.status_signal.emit(
                    f"Recording too short ({duration_s*1000:.0f}ms). Ignored."
                )
                wav_path.unlink(missing_ok=True)
                return
            if rms < _MIN_RECORD_RMS:
                self.status_signal.emit(
                    f"Audio too quiet (rms={rms:.4f}). Ignored."
                )
                wav_path.unlink(missing_ok=True)
                return
            self.status_signal.emit("Recording stopped. Processing...")
            self._is_processing = True
            worker = threading.Thread(
                target=self._process_pipeline,
                args=(wav_path,),
                daemon=True,
            )
            worker.start()
        except Exception as exc:
            self._is_recording = False
            self.error_signal.emit(f"Failed to stop recording: {exc}")
        finally:
            self._hotkey_cooldown_until_ts = time.monotonic() + _HOTKEY_COOLDOWN_S

    def _process_pipeline(self, wav_path: Path) -> None:
        try:
            ok, error = check_ollama_reachable()
            if not ok:
                host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
                if self._is_local_ollama_host(host):
                    guide = (
                        "\nRun: ollama serve and ensure model exists: "
                        + self.settings.ollama_model
                    )
                else:
                    guide = (
                        "\nCheck remote Ollama host and model on: "
                        + host
                        + "\nExpected model: "
                        + self.settings.ollama_model
                    )
                raise RuntimeError(
                    error
                    + guide
                )

            dictionary_entries = parse_dictionary_entries(self.settings.custom_dictionary)
            dict_terms = extract_terms(dictionary_entries)
            person_terms = extract_person_terms(dictionary_entries)
            asr_prompt = build_asr_initial_prompt(dict_terms)
            asr_start = time.perf_counter()
            raw_text = self.asr.transcribe(wav_path, initial_prompt=asr_prompt)
            asr_elapsed = time.perf_counter() - asr_start
            print(f"[Talky] ASR elapsed: {asr_elapsed:.2f}s")
            if not raw_text:
                raise RuntimeError("ASR returned empty text. Please retry.")
            corrected_raw_text = apply_phonetic_dictionary(raw_text, dict_terms)
            # Skip LLM for very short/noisy ASR outputs to avoid hallucinated expansions.
            if len(corrected_raw_text.replace(" ", "").strip()) < 2:
                self.status_signal.emit("ASR text too short. LLM step skipped.")
                return

            llm_start = time.perf_counter()
            final_text = self.llm.clean(
                raw_text=corrected_raw_text,
                dictionary_terms=dict_terms,
            )
            llm_elapsed = time.perf_counter() - llm_start
            print(f"[Talky] LLM elapsed: {llm_elapsed:.2f}s")
            final_text = apply_phonetic_dictionary(final_text, dict_terms)
            final_text = normalize_person_pronouns(final_text, person_terms)
            final_text = enforce_pronoun_consistency(corrected_raw_text, final_text)
            final_text = enforce_source_boundaries(corrected_raw_text, final_text)
            final_text = collapse_duplicate_output(final_text)
            # Keep cross-device output style stable by normalizing Chinese to Simplified.
            final_text = normalize_to_simplified_chinese(final_text)
            if not final_text:
                raise RuntimeError("LLM returned empty text. Please retry.")

            now = time.monotonic()
            if final_text == self._last_output_text and (now - self._last_output_ts) < 1.2:
                self.status_signal.emit("Duplicate output suppressed.")
                return
            self._last_output_text = final_text
            self._last_output_ts = now

            print(f"[Talky] Final text: {final_text}")
            history_path = self.history_store.append(final_text)
            print(f"[Talky] History appended: {history_path}")

            current_front_app = get_frontmost_app()
            if has_focus_target(current_front_app):
                self.paster.paste_text(final_text)
                self.status_signal.emit("Pasted to current focus target.")
            else:
                self.show_result_popup_signal.emit(final_text)
                self.status_signal.emit("No focus target detected. Showing floating panel.")
        except Exception as exc:
            self.error_signal.emit(f"Processing failed: {exc}")
        finally:
            self._is_processing = False
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _warm_up_models_async(self) -> None:
        worker = threading.Thread(target=self._warm_up_models, daemon=True)
        worker.start()

    def _warm_up_models(self) -> None:
        try:
            warm_asr_start = time.perf_counter()
            self.asr.warm_up()
            warm_asr_elapsed = time.perf_counter() - warm_asr_start
            print(f"[Talky] Whisper warm-up done: {warm_asr_elapsed:.2f}s")
        except Exception as exc:
            print(f"[Talky] Whisper warm-up failed: {exc}")

        try:
            warm_llm_start = time.perf_counter()
            self.llm.warm_up()
            warm_llm_elapsed = time.perf_counter() - warm_llm_start
            print(f"[Talky] Ollama warm-up done: {warm_llm_elapsed:.2f}s")
        except Exception as exc:
            print(f"[Talky][debug] Ollama warm-up skipped: {exc}")
