from __future__ import annotations

import array
import math
import tempfile
import time
import wave
from pathlib import Path

import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream: sd.InputStream | None = None
        self._chunks: list[array.array] = []
        self._active_sample_rate = float(sample_rate)
        self._last_duration_s = 0.0
        self._last_rms = 0.0

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def last_duration_s(self) -> float:
        return self._last_duration_s

    @property
    def last_rms(self) -> float:
        return self._last_rms

    def _append_chunk(self, indata) -> None:
        """Buffer one callback block (NumPy ndarray when available, else array/memoryview)."""
        if hasattr(indata, "__array_interface__"):
            contiguous = indata.reshape(-1) if hasattr(indata, "reshape") else indata
            chunk = array.array("f")
            chunk.frombytes(contiguous.astype("float32", copy=False).tobytes())
            self._chunks.append(chunk)
            return
        if isinstance(indata, array.array):
            self._chunks.append(array.array("f", indata))
            return
        try:
            self._chunks.append(array.array("f", indata))
        except (TypeError, ValueError):
            mv = memoryview(indata)
            if mv.format == "f" and mv.itemsize == 4:
                chunk = array.array("f")
                chunk.frombytes(mv.tobytes())
                self._chunks.append(chunk)
            else:
                raise

    def start(self) -> None:
        if self._stream is not None:
            return
        self._chunks.clear()
        self._last_duration_s = 0.0
        self._last_rms = 0.0

        def _callback(indata, frames: int, time_info: dict, status) -> None:
            del frames, time_info
            if status:
                # Keep the stream alive even if occasional status is present.
                pass
            self._append_chunk(indata)

        sample_rates = [float(self.sample_rate), self._default_input_sample_rate()]
        # De-duplicate while keeping order.
        unique_rates: list[float] = []
        for rate in sample_rates:
            if rate not in unique_rates:
                unique_rates.append(rate)

        last_exc: sd.PortAudioError | None = None
        for sample_rate in unique_rates:
            for retry in range(3):
                try:
                    self._stream = self._open_input_stream(_callback, sample_rate=sample_rate)
                    self._stream.start()
                    self._active_sample_rate = float(sample_rate)
                    return
                except sd.PortAudioError as exc:
                    last_exc = exc
                    if not self._is_recoverable_portaudio_error(exc):
                        raise
                    self._reset_portaudio()
                    time.sleep(0.2 + (retry * 0.1))
                    continue

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Failed to open input stream.")

    def _open_input_stream(self, callback, sample_rate: float):
        return sd.InputStream(
            samplerate=sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=callback,
        )

    def _default_input_sample_rate(self) -> float:
        try:
            default_input = sd.query_devices(kind="input")
            if isinstance(default_input, dict):
                value = default_input.get("default_samplerate")
                if value:
                    return float(value)
        except Exception:
            pass
        return float(self.sample_rate)

    def _is_recoverable_portaudio_error(self, exc: sd.PortAudioError) -> bool:
        message = str(exc).lower()
        return (
            "-10851" in message
            or "invalid property value" in message
            or "auhal" in message
            or "!obj" in message
        )

    def _reset_portaudio(self) -> None:
        terminate = getattr(sd, "_terminate", None)
        initialize = getattr(sd, "_initialize", None)
        if callable(terminate):
            try:
                terminate()
            except Exception:
                pass
        if callable(initialize):
            try:
                initialize()
            except Exception:
                pass

    def stop_and_dump_wav(self) -> Path:
        if self._stream is None:
            raise RuntimeError("Recorder is not running.")

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._chunks:
            raise RuntimeError("No audio captured.")

        full = array.array("f")
        for c in self._chunks:
            full.extend(c)

        n = len(full)
        self._last_duration_s = (
            float(n) / float(self._active_sample_rate) if self._active_sample_rate > 0 else 0.0
        )
        if n > 0:
            mean_sq = sum(x * x for x in full) / float(n)
            self._last_rms = math.sqrt(mean_sq)
        else:
            self._last_rms = 0.0

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = Path(tmp.name)
        tmp.close()

        pcm = array.array(
            "h",
            (int(max(-1.0, min(1.0, x)) * 32767.0) for x in full),
        )
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(int(round(self._active_sample_rate)))
            wf.writeframes(pcm.tobytes())

        self._chunks.clear()
        return path
