from __future__ import annotations

import json
import os
import threading
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


def check_microphone_granted() -> tuple[bool, str]:
    """
    Check microphone permission status without forcing prompt when possible.
    """
    try:
        import AVFoundation  # type: ignore[import-not-found]

        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        authorized = int(status) == int(
            getattr(AVFoundation, "AVAuthorizationStatusAuthorized", 3)
        )
        if authorized:
            return True, ""
        return False, "Microphone permission not granted."
    except Exception:
        # Fallback path when AVFoundation bindings are unavailable.
        try:
            import sounddevice as sd

            stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
            stream.start()
            stream.stop()
            stream.close()
            return True, ""
        except Exception as exc:
            return False, f"Microphone permission not granted: {exc}"


def request_microphone_permission() -> tuple[bool, str]:
    """
    Trigger microphone permission prompt and return latest grant status.
    """
    try:
        import AVFoundation  # type: ignore[import-not-found]

        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        not_determined = int(status) == int(
            getattr(AVFoundation, "AVAuthorizationStatusNotDetermined", 0)
        )
        authorized = int(status) == int(
            getattr(AVFoundation, "AVAuthorizationStatusAuthorized", 3)
        )
        if authorized:
            return True, ""
        if not not_determined:
            return False, "Microphone permission not granted."

        event = threading.Event()
        granted_holder = {"granted": False}

        def _handler(granted: bool) -> None:
            granted_holder["granted"] = bool(granted)
            event.set()

        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeAudio,
            _handler,
        )
        event.wait(timeout=5.0)
        if granted_holder["granted"]:
            return True, ""
        return False, "Microphone permission not granted."
    except Exception:
        # Fallback path: touching input stream may trigger system prompt.
        try:
            import sounddevice as sd

            stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
            stream.start()
            stream.stop()
            stream.close()
            return True, ""
        except Exception as exc:
            return False, f"Microphone permission not granted: {exc}"


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
