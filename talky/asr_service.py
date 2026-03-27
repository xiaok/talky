from __future__ import annotations

import sys
from pathlib import Path

from talky.runtime_setup import ensure_local_whisper_runtime


def _prepend_talky_extra_site_packages() -> None:
    """Allow a slim PyInstaller .app to load mlx/numpy from a user-managed tree."""
    extra = Path.home() / ".talky" / "extra-site-packages"
    if extra.is_dir():
        s = str(extra.resolve())
        if s not in sys.path:
            sys.path.insert(0, s)


def is_whisper_model_cached(model_name: str) -> bool:
    """Check whether the Whisper model is locally available (works for both paths and HF repos)."""
    raw = (model_name or "").strip() or "./local_whisper_model"
    if raw.startswith(("/", "./", "../", "~")):
        resolved = Path(raw).expanduser()
        if not resolved.is_absolute():
            candidates = [
                (Path.home() / ".talky" / resolved).resolve(),
                (Path.cwd() / resolved).resolve(),
            ]
        else:
            candidates = [resolved]
        return any(p.exists() for p in candidates)
    # HuggingFace repo ID — check local cache
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    snapshots = cache_dir / f"models--{raw.replace('/', '--')}" / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


class MlxWhisperASR:
    """Local Whisper ASR via mlx_whisper. Heavy deps load only on transcribe / warm_up."""

    def __init__(self, model_name: str, language: str = "zh") -> None:
        self.model_name = model_name
        self.language = language

    def is_model_available(self) -> bool:
        try:
            self._resolve_model_reference()
            return True
        except FileNotFoundError:
            return False

    def _resolve_model_reference(self) -> str:
        """Resolve model name to a local path or HuggingFace repo id.

        For paths (starting with /, ./, ../, ~) searches ~/.talky/<path> then CWD.
        For bare names (e.g. 'mlx-community/whisper-large-v3-mlx') returns as-is.
        Raises FileNotFoundError with search details when a path-like value is missing.
        """
        raw_value = (self.model_name or "").strip() or "./local_whisper_model"
        if not raw_value.startswith(("/", "./", "../", "~")):
            return raw_value

        resolved = Path(raw_value).expanduser()
        if not resolved.is_absolute():
            candidates = [
                (Path.home() / ".talky" / resolved).resolve(),
                (Path.cwd() / resolved).resolve(),
            ]
        else:
            candidates = [resolved]

        for path in candidates:
            if path.exists():
                return str(path)

        searched = "\n  ".join(str(p) for p in candidates)
        raise FileNotFoundError(
            f"Whisper model path not found. Searched:\n  {searched}\n"
            "Set 'Whisper Model' to a valid absolute path or Hugging Face repo id "
            "(e.g. mlx-community/whisper-large-v3-mlx)."
        )

    def transcribe(self, audio_path: Path, initial_prompt: str) -> str:
        mlx_whisper, _ = self._load_runtime(require_numpy=False)
        audio = self._load_audio_waveform(audio_path)

        model_ref = self._resolve_model_reference()
        kwargs = {"initial_prompt": initial_prompt, "language": self.language}
        try:
            result = mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=model_ref,
                **kwargs,
            )
        except TypeError:
            result = mlx_whisper.transcribe(audio, model_ref, **kwargs)
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return text.strip()

    def warm_up(self) -> None:
        mlx_whisper, np = self._load_runtime(require_numpy=True)

        model_ref = self._resolve_model_reference()
        # Use in-memory silent waveform to avoid depending on ffmpeg for warm-up.
        silent = np.zeros(8000, dtype=np.float32)  # 0.5s @ 16k
        kwargs = {"initial_prompt": "", "language": self.language}
        try:
            mlx_whisper.transcribe(
                silent,
                path_or_hf_repo=model_ref,
                **kwargs,
            )
        except TypeError:
            mlx_whisper.transcribe(silent, model_ref, **kwargs)

    def _load_runtime(self, *, require_numpy: bool) -> tuple[object, object | None]:
        """Load local Whisper runtime; auto-bootstrap ~/.talky/extra-site-packages once."""
        _prepend_talky_extra_site_packages()
        try:
            import mlx_whisper

            np_module = None
            if require_numpy:
                import numpy as np

                np_module = np
            return mlx_whisper, np_module
        except Exception as first_exc:
            ok, detail = ensure_local_whisper_runtime()
            if ok:
                _prepend_talky_extra_site_packages()
                try:
                    import mlx_whisper

                    np_module = None
                    if require_numpy:
                        import numpy as np

                        np_module = np
                    return mlx_whisper, np_module
                except Exception as second_exc:
                    raise RuntimeError(
                        "Local Whisper runtime is unavailable after auto-install. "
                        f"Details: {second_exc}. "
                        "You can run manually: "
                        "`python3 -m pip install --target ~/.talky/extra-site-packages "
                        "numpy mlx mlx-whisper` then restart Talky."
                    ) from second_exc
            raise RuntimeError(
                "Local Whisper runtime is unavailable. "
                f"Auto-install failed: {detail}. "
                "You can run manually: "
                "`python3 -m pip install --target ~/.talky/extra-site-packages "
                "numpy mlx mlx-whisper` then restart Talky."
            ) from first_exc

    def _load_audio_waveform(self, audio_path: Path):
        """Load wav into float32 waveform to avoid ffmpeg runtime dependency."""
        try:
            import soundfile as sf
        except Exception as exc:
            raise RuntimeError(
                "Cannot load audio waveform: soundfile is unavailable."
            ) from exc

        audio, _sample_rate = sf.read(str(audio_path), dtype="float32")
        if hasattr(audio, "ndim") and audio.ndim > 1:
            audio = audio[:, 0]
        return audio
