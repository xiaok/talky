from __future__ import annotations

import array
import importlib
import math
import sys
import types
import wave

import pytest


class _FakeStream:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        return

    def close(self) -> None:
        return


def _load_recorder_module(monkeypatch: pytest.MonkeyPatch):
    class _PortAudioError(Exception):
        pass

    fake_sd = types.SimpleNamespace(
        PortAudioError=_PortAudioError,
        InputStream=lambda **kwargs: _FakeStream(),  # noqa: ARG005
        query_devices=lambda kind=None: {"default_samplerate": 48000},  # noqa: ARG005
        _terminate=lambda: None,
        _initialize=lambda: None,
    )

    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    sys.modules.pop("talky.recorder", None)
    return importlib.import_module("talky.recorder")


def test_start_retries_after_recoverable_portaudio_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder_module = _load_recorder_module(monkeypatch)

    attempts = {"count": 0}
    stream = _FakeStream()

    def fake_input_stream(**kwargs):  # noqa: ANN003
        del kwargs
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise recorder_module.sd.PortAudioError(
                "Audio Unit: Invalid Property Value (-10851)"
            )
        return stream

    state = {"terminated": 0, "initialized": 0}
    monkeypatch.setattr(recorder_module.sd, "InputStream", fake_input_stream)
    monkeypatch.setattr(
        recorder_module.sd,
        "_terminate",
        lambda: state.__setitem__("terminated", state["terminated"] + 1),
        raising=False,
    )
    monkeypatch.setattr(
        recorder_module.sd,
        "_initialize",
        lambda: state.__setitem__("initialized", state["initialized"] + 1),
        raising=False,
    )
    monkeypatch.setattr(recorder_module.time, "sleep", lambda _: None)

    recorder = recorder_module.AudioRecorder()
    recorder.start()

    assert attempts["count"] == 2
    assert state["terminated"] == 1
    assert state["initialized"] == 1
    assert recorder.is_recording is True
    assert stream.started is True


def test_start_falls_back_to_default_input_sample_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder_module = _load_recorder_module(monkeypatch)

    attempts = {"count": 0}
    seen_rates: list[float] = []
    stream = _FakeStream()

    def fake_input_stream(**kwargs):  # noqa: ANN003
        attempts["count"] += 1
        samplerate = float(kwargs["samplerate"])
        seen_rates.append(samplerate)
        if samplerate == 16000.0:
            raise recorder_module.sd.PortAudioError(
                "Audio Unit: Invalid Property Value (-10851)"
            )
        return stream

    monkeypatch.setattr(recorder_module.sd, "InputStream", fake_input_stream)
    monkeypatch.setattr(recorder_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        recorder_module.sd,
        "query_devices",
        lambda kind=None: {"default_samplerate": 48000},  # noqa: ARG005
    )
    monkeypatch.setattr(recorder_module.time, "sleep", lambda _: None)

    recorder = recorder_module.AudioRecorder(sample_rate=16000)
    recorder.start()

    assert attempts["count"] >= 2
    assert 16000.0 in seen_rates
    assert 48000.0 in seen_rates
    assert recorder.is_recording is True
    assert stream.started is True


def test_start_raises_nonrecoverable_portaudio_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder_module = _load_recorder_module(monkeypatch)

    attempts = {"count": 0}

    def fake_input_stream(**kwargs):  # noqa: ANN003
        del kwargs
        attempts["count"] += 1
        raise recorder_module.sd.PortAudioError("Permission denied")

    monkeypatch.setattr(recorder_module.sd, "InputStream", fake_input_stream)

    recorder = recorder_module.AudioRecorder()
    with pytest.raises(recorder_module.sd.PortAudioError):
        recorder.start()

    assert attempts["count"] == 1


def test_stop_records_last_duration_and_rms(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder_module = _load_recorder_module(monkeypatch)

    recorder = recorder_module.AudioRecorder(sample_rate=16000, channels=1)
    recorder._stream = _FakeStream()
    recorder._active_sample_rate = 16000.0
    recorder._chunks = [array.array("f", [0.0, 0.5, -0.5, 0.0])]

    wav_path = recorder.stop_and_dump_wav()

    assert wav_path.exists()
    assert recorder.last_duration_s == pytest.approx(4 / 16000.0, rel=1e-6)
    expected_rms = math.sqrt(0.125)  # mean sq = (0+0.25+0.25+0)/4
    assert recorder.last_rms == pytest.approx(expected_rms, rel=1e-6)

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnframes() == 4
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2

    wav_path.unlink(missing_ok=True)
