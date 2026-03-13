#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "==> Talky one-click start"

auto_update_repo() {
  if ! command -v git >/dev/null 2>&1; then
    return
  fi
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return
  fi
  if ! git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    echo "==> No upstream branch configured. Skip auto-update."
    return
  fi
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "==> Local changes detected. Skip auto-update to avoid conflicts."
    return
  fi

  echo "==> Checking for updates..."
  if ! git fetch --progress --prune; then
    echo "==> Update check failed (network or remote issue). Continue with local code."
    return
  fi

  local local_sha upstream_sha
  local_sha="$(git rev-parse HEAD)"
  upstream_sha="$(git rev-parse '@{u}')"
  if [[ "$local_sha" == "$upstream_sha" ]]; then
    echo "==> Already up to date."
    return
  fi

  echo "==> New version found. Updating..."
  if git pull --ff-only --progress; then
    echo "==> Update complete. Starting with latest code."
    return
  fi

  echo "==> Auto-update failed. Continue with local code."
}

auto_update_repo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed. Please install Python 3 first."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi

source ".venv/bin/activate"

# Force local Ollama path and bypass proxy for localhost access.
unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY all_proxy ALL_PROXY
export NO_PROXY=localhost,127.0.0.1
export OLLAMA_HOST=http://127.0.0.1:11434

deps_ready() {
  python - <<'PY'
import importlib.util
import sys

required = [
    "PyQt6",
    "pynput",
    "sounddevice",
    "soundfile",
    "numpy",
    "mlx_whisper",
    "ollama",
    "pyperclip",
]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    print("Missing modules:", ", ".join(missing))
    sys.exit(1)
PY
}

ensure_dependencies() {
  local dep_marker=".venv/.deps_ok"
  local dep_state
  dep_state="$(
    python - <<'PY'
from pathlib import Path
import hashlib
import sys

req = Path("requirements.txt")
text = req.read_text(encoding="utf-8") if req.exists() else ""
digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
print(f"{sys.version_info.major}.{sys.version_info.minor}-{digest}")
PY
  )"

  if [[ -f "$dep_marker" ]] && [[ "$(cat "$dep_marker" 2>/dev/null)" == "$dep_state" ]]; then
    return
  fi

  if deps_ready; then
    echo "$dep_state" > "$dep_marker"
    return
  fi

  echo "==> Installing dependencies (network required)..."
  if python -m pip install --retries 3 --timeout 30 -r requirements.txt; then
    echo "$dep_state" > "$dep_marker"
    return
  fi

  echo "Warning: dependency installation failed."
  if deps_ready; then
    echo "==> Existing local dependencies are usable. Continuing..."
    echo "$dep_state" > "$dep_marker"
    return
  fi

  echo "Error: required dependencies are missing and could not be installed."
  echo "Please check your network and re-run start_talky.command."
  exit 1
}

ensure_dependencies

if [[ ! -d "local_whisper_model" ]]; then
  echo "==> local_whisper_model not found, downloading..."
  python download_model.py
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Error: ollama command not found."
  echo "Please install Ollama first: https://ollama.com/download"
  exit 1
fi

mkdir -p ".logs"

if ! pgrep -x "ollama" >/dev/null 2>&1; then
  echo "==> Starting Ollama service..."
  nohup ollama serve >".logs/ollama.log" 2>&1 &
  sleep 2
fi

MODEL_NAME="$(
python - <<'PY'
import json
import subprocess
from pathlib import Path

config_path = Path.home() / ".talky" / "settings.json"
data = {}
if config_path.exists():
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

configured = str(data.get("ollama_model", "")).strip()

installed: list[str] = []
try:
    raw = subprocess.check_output(["ollama", "list"], text=True)
    for line in raw.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        name = line.split()[0].strip()
        if name:
            installed.append(name)
except Exception:
    installed = []

selected = ""
if configured and configured in installed:
    selected = configured
elif installed:
    selected = installed[0]
    data["ollama_model"] = selected
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

print(selected)
PY
)"

if [[ -z "$MODEL_NAME" ]]; then
  echo "Error: no Ollama model found."
  echo "Please pull any model first, for example:"
  echo "  ollama pull <your-model>"
  echo "Then re-run start_talky.command."
  exit 1
fi

echo "==> Using Ollama model: $MODEL_NAME"

echo "==> Launching Talky..."
exec python main.py
