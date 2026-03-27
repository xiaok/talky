from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
import importlib.machinery
import sys
import glob

_INSTALL_LOCK = threading.Lock()
_EXTRA_SITE_PACKAGES = Path.home() / ".talky" / "extra-site-packages"
_RUNTIME_PACKAGES = ("numpy", "mlx", "mlx-whisper")


def install_local_whisper_runtime() -> tuple[bool, str]:
    """Install local Whisper runtime deps into ~/.talky/extra-site-packages."""
    py = _find_python3()
    if not py:
        return (
            False,
            "no compatible python found on PATH "
            f"(required {sys.version_info.major}.{sys.version_info.minor})",
        )

    _EXTRA_SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    cmd = [
        py,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(_EXTRA_SITE_PACKAGES),
        *_RUNTIME_PACKAGES,
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return False, f"failed to run installer: {exc}"

    if proc.returncode == 0:
        return True, "installed local whisper runtime"

    detail = (proc.stderr or proc.stdout or "").strip()
    if len(detail) > 600:
        detail = detail[-600:]
    return False, f"pip failed ({proc.returncode}): {detail or 'no details'}"


def ensure_local_whisper_runtime() -> tuple[bool, str]:
    """Best-effort installer for local Whisper runtime deps.

    Installs packages into ~/.talky/extra-site-packages so the frozen app can import
    compiled extensions from a normal site-packages layout.
    """
    with _INSTALL_LOCK:
        if _runtime_artifacts_present():
            return True, "local whisper runtime already present"

        _prune_incompatible_runtime_artifacts()
        ok, detail = install_local_whisper_runtime()
        if not ok:
            return False, detail
        if _runtime_artifacts_present():
            return True, detail
        return False, "installer exited successfully but runtime artifacts were not found"


def _find_python3() -> str | None:
    required = (sys.version_info.major, sys.version_info.minor)
    required_str = f"{required[0]}.{required[1]}"
    preferred = [
        f"python{required[0]}.{required[1]}",
        f"python{required[0]}",
        "python3",
        "/usr/bin/python3",
        # Common macOS install locations (GUI apps may have a minimal PATH).
        f"/opt/homebrew/bin/python{required_str}",
        "/opt/homebrew/bin/python3",
        f"/usr/local/bin/python{required_str}",
        "/usr/local/bin/python3",
        f"/Library/Frameworks/Python.framework/Versions/{required_str}/bin/python3",
    ]
    for name in preferred:
        p = shutil.which(name) if "/" not in name else name
        if not p or not Path(p).exists():
            continue
        try:
            probe = subprocess.run(
                [p, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                check=False,
                capture_output=True,
                text=True,
            )
            ver = (probe.stdout or "").strip()
            if ver == required_str:
                return p
        except Exception:
            continue
    return None


def _runtime_artifacts_present() -> bool:
    """Heuristic: check core runtime package folders in target site-packages."""
    if not _EXTRA_SITE_PACKAGES.is_dir():
        return False
    required_paths = (
        _EXTRA_SITE_PACKAGES / "numpy",
        _EXTRA_SITE_PACKAGES / "mlx",
        _EXTRA_SITE_PACKAGES / "mlx_whisper",
    )
    if not all(p.exists() for p in required_paths):
        return False

    # Ensure mlx core extension matches current interpreter ABI (e.g. cpython-312).
    mlx_dir = _EXTRA_SITE_PACKAGES / "mlx"
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    has_matching_core = any((mlx_dir / f"core{suffix}").exists() for suffix in suffixes)
    return has_matching_core


def _prune_incompatible_runtime_artifacts() -> None:
    """Remove stale ABI-mismatched mlx artifacts before reinstall."""
    if _runtime_artifacts_present():
        return
    patterns = [
        "mlx",
        "mlx_whisper",
        "mlx-*.dist-info",
        "mlx_whisper-*.dist-info",
        "mlx_metal-*.dist-info",
    ]
    for pattern in patterns:
        for entry in glob.glob(str(_EXTRA_SITE_PACKAGES / pattern)):
            p = Path(entry)
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
            except Exception:
                pass
