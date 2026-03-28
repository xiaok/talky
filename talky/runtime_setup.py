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

_STANDALONE_PYTHON_DIR = Path.home() / ".talky" / "python"

# Standalone CPython builds from astral-sh/python-build-standalone (Apple Silicon).
# Update the mapping when the bundled app's Python version changes.
_STANDALONE_PYTHON_URLS: dict[tuple[int, int], str] = {
    (3, 12): (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        "20250317/cpython-3.12.9+20250317-aarch64-apple-darwin-install_only.tar.gz"
    ),
    (3, 13): (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        "20250317/cpython-3.13.2+20250317-aarch64-apple-darwin-install_only.tar.gz"
    ),
}


def install_local_whisper_runtime() -> tuple[bool, str]:
    """Install local Whisper runtime deps into ~/.talky/extra-site-packages."""
    py = _find_python3()
    if not py:
        ok, result = _download_standalone_python()
        if not ok:
            return False, f"no compatible python available ({result})"
        py = result
        # Bootstrap pip for the freshly downloaded standalone Python.
        subprocess.run(
            [py, "-m", "ensurepip", "--upgrade"],
            check=False, capture_output=True, text=True,
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


def _download_standalone_python() -> tuple[bool, str]:
    """Download a standalone CPython to ~/.talky/python/ for pip-installing native packages.

    Returns (True, python_binary_path) on success, (False, error_detail) on failure.
    """
    import platform
    import ssl
    import tarfile
    import tempfile
    import urllib.request

    target_bin = _STANDALONE_PYTHON_DIR / "bin" / "python3"
    if target_bin.exists():
        return True, str(target_bin)

    if platform.machine() != "arm64":
        return False, "auto-download only available on Apple Silicon Macs"

    key = (sys.version_info.major, sys.version_info.minor)
    url = _STANDALONE_PYTHON_URLS.get(key)
    if not url:
        return False, f"no standalone Python {key[0]}.{key[1]} download available"

    # PyInstaller bundles lack system SSL certs; use certifi if available.
    try:
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_ctx = ssl.create_default_context()

    parent = _STANDALONE_PYTHON_DIR.parent  # ~/.talky
    parent.mkdir(parents=True, exist_ok=True)

    if _STANDALONE_PYTHON_DIR.exists():
        shutil.rmtree(_STANDALONE_PYTHON_DIR, ignore_errors=True)

    tmp_file = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tmp_path = Path(tmp_file.name)
    tmp_file.close()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=180, context=ssl_ctx) as resp:  # noqa: S310
            with tmp_path.open("wb") as f:
                shutil.copyfileobj(resp, f)

        with tarfile.open(str(tmp_path), "r:gz") as tar:
            try:
                tar.extractall(path=str(parent), filter="tar")
            except TypeError:
                tar.extractall(path=str(parent))

        if target_bin.exists():
            return True, str(target_bin)
        return False, "extraction succeeded but python binary not found"
    except Exception as exc:
        if _STANDALONE_PYTHON_DIR.exists():
            shutil.rmtree(_STANDALONE_PYTHON_DIR, ignore_errors=True)
        return False, f"download failed: {exc}"
    finally:
        tmp_path.unlink(missing_ok=True)


def _find_python3() -> str | None:
    required = (sys.version_info.major, sys.version_info.minor)
    required_str = f"{required[0]}.{required[1]}"
    home = Path.home()
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
        # MacPorts
        f"/opt/local/bin/python{required_str}",
        "/opt/local/bin/python3",
        # Talky-managed standalone Python
        str(_STANDALONE_PYTHON_DIR / "bin" / f"python{required_str}"),
        str(_STANDALONE_PYTHON_DIR / "bin" / "python3"),
    ]

    # Dynamic discovery: pyenv, mise, asdf
    for base_dir in (
        home / ".pyenv" / "versions",
        home / ".local" / "share" / "mise" / "installs" / "python",
        home / ".asdf" / "installs" / "python",
    ):
        if not base_dir.is_dir():
            continue
        try:
            for entry in sorted(base_dir.iterdir(), reverse=True):
                if entry.name.startswith(required_str) and entry.is_dir():
                    candidate = entry / "bin" / "python3"
                    if candidate.exists():
                        preferred.append(str(candidate))
        except OSError:
            continue

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
