#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "==> Talky one-click start"

print_repo_version() {
  if ! command -v git >/dev/null 2>&1; then
    echo "==> Version: unknown (git not found)"
    return
  fi
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "==> Version: unknown (not a git repo)"
    return
  fi

  local commit_id commit_date
  commit_id="$(git rev-parse --short HEAD 2>/dev/null || true)"
  commit_date="$(
    git show -s --date=format:%Y-%m-%d --format=%cd HEAD 2>/dev/null || true
  )"

  if [[ -n "$commit_id" && -n "$commit_date" ]]; then
    echo "==> Version: ${commit_date}+${commit_id}"
    return
  fi
  if [[ -n "$commit_id" ]]; then
    echo "==> Version: unknown-date+${commit_id}"
    return
  fi
  echo "==> Version: unknown"
}

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

print_repo_version
auto_update_repo
echo "==> Running version after update check:"
print_repo_version

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed. Please install Python 3 first."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi

source ".venv/bin/activate"

resolve_ollama_host() {
  python - <<'PY'
import json
from pathlib import Path

config_path = Path.home() / ".talky" / "settings.json"
host = "http://127.0.0.1:11434"
if config_path.exists():
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        host = str(data.get("ollama_host", host)).strip() or host
    except Exception:
        pass
print(host.rstrip("/"))
PY
}

is_local_ollama_host() {
  python - <<'PY'
import os
from urllib.parse import urlparse

host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip() or "http://127.0.0.1:11434"
parsed = urlparse(host if "://" in host else f"http://{host}")
hostname = (parsed.hostname or "").lower()
print("1" if hostname in {"127.0.0.1", "localhost", "::1"} else "0")
PY
}

is_first_run_without_host_config() {
  python - <<'PY'
import json
from pathlib import Path

config_path = Path.home() / ".talky" / "settings.json"
if not config_path.exists():
    print("1")
    raise SystemExit
try:
    data = json.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    print("1")
    raise SystemExit
host = str(data.get("ollama_host", "")).strip()
print("1" if not host else "0")
PY
}

write_ollama_host_config() {
  local host_value="$1"
  OLLAMA_HOST_INPUT="$host_value" python - <<'PY'
import json
import os
from pathlib import Path
from urllib.parse import urlparse

raw = (os.environ.get("OLLAMA_HOST_INPUT", "") or "").strip()
if not raw:
    raw = "http://127.0.0.1:11434"
value = raw if "://" in raw else f"http://{raw}"
parsed = urlparse(value)
if not parsed.netloc:
    value = "http://127.0.0.1:11434"
value = value.rstrip("/")

config_path = Path.home() / ".talky" / "settings.json"
data = {}
if config_path.exists():
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
data["ollama_host"] = value
config_path.parent.mkdir(parents=True, exist_ok=True)
config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(value)
PY
}

run_ollama_host_wizard() {
  echo ""
  echo "==> First-run Ollama host setup"
  echo "Local Ollama is unavailable or has no model."
  echo "Select Ollama mode:"
  echo "  1) Local host (http://127.0.0.1:11434)"
  echo "  2) Remote LAN host (http://<LAN_IP>:11434)"
  while true; do
    printf "Enter choice [1/2]: "
    read -r choice
    if [[ "$choice" == "1" ]]; then
      local saved
      saved="$(write_ollama_host_config "http://127.0.0.1:11434")"
      echo "==> Saved ollama_host: $saved"
      break
    fi
    if [[ "$choice" == "2" ]]; then
      printf "Enter remote Ollama host (example: http://192.168.1.100:11434): "
      read -r remote_host
      local saved
      saved="$(write_ollama_host_config "$remote_host")"
      echo "==> Saved ollama_host: $saved"
      break
    fi
    echo "Invalid choice. Please enter 1 or 2."
  done
  echo ""
}

refresh_ollama_mode_env() {
  OLLAMA_HOST="$(resolve_ollama_host)"
  export OLLAMA_HOST
  IS_LOCAL_OLLAMA="$(is_local_ollama_host)"
  export IS_LOCAL_OLLAMA

  if [[ "$IS_LOCAL_OLLAMA" == "1" ]]; then
    # Local mode: avoid proxy interference for localhost access.
    unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY all_proxy ALL_PROXY
    export NO_PROXY=localhost,127.0.0.1,::1
    echo "==> Ollama host: $OLLAMA_HOST (mode: local)"
    return
  fi

  REMOTE_OLLAMA_HOST="$(
    python - <<'PY'
import os
from urllib.parse import urlparse

host = os.environ.get("OLLAMA_HOST", "").strip()
parsed = urlparse(host if "://" in host else f"http://{host}")
print((parsed.hostname or "").strip())
PY
  )"
  if [[ -n "${REMOTE_OLLAMA_HOST:-}" ]]; then
    if [[ -n "${NO_PROXY:-}" ]]; then
      export NO_PROXY="${NO_PROXY},${REMOTE_OLLAMA_HOST},localhost,127.0.0.1"
    else
      export NO_PROXY="${REMOTE_OLLAMA_HOST},localhost,127.0.0.1"
    fi
  fi
  echo "==> Ollama host: $OLLAMA_HOST (mode: remote)"
}

FIRST_RUN_NO_HOST_CONFIG="$(is_first_run_without_host_config)"
WIZARD_USED="0"
refresh_ollama_mode_env

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

mkdir -p ".logs"

ensure_local_ollama_ready() {
  if [[ "$IS_LOCAL_OLLAMA" != "1" ]]; then
    return
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    if [[ "$FIRST_RUN_NO_HOST_CONFIG" == "1" && "$WIZARD_USED" == "0" ]]; then
      run_ollama_host_wizard
      WIZARD_USED="1"
      refresh_ollama_mode_env
      return
    fi
    echo "Error: ollama command not found."
    echo "Please install Ollama first: https://ollama.com/download"
    exit 1
  fi

  if ! pgrep -x "ollama" >/dev/null 2>&1; then
    echo "==> Starting Ollama service..."
    nohup ollama serve >".logs/ollama.log" 2>&1 &
    sleep 2
  fi
}

resolve_model_name() {
python - <<'PY'
import json
import os
import urllib.request
from pathlib import Path

host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
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
    request = urllib.request.Request(  # noqa: S310
        url=f"{host}/api/tags",
        headers={"Content-Type": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    for item in payload.get("models", []):
        name = str(item.get("name", "")).strip()
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
}

ensure_local_ollama_ready
MODEL_NAME="$(resolve_model_name)"

if [[ -z "$MODEL_NAME" && "$IS_LOCAL_OLLAMA" == "1" && "$FIRST_RUN_NO_HOST_CONFIG" == "1" && "$WIZARD_USED" == "0" ]]; then
  run_ollama_host_wizard
  WIZARD_USED="1"
  refresh_ollama_mode_env
  ensure_local_ollama_ready
  MODEL_NAME="$(resolve_model_name)"
fi

if [[ -z "$MODEL_NAME" ]]; then
  echo "Error: no Ollama model found from host: $OLLAMA_HOST"
  echo "Please ensure Ollama is reachable and has at least one model, for example:"
  echo "  ollama pull <your-model>"
  echo "Then re-run start_talky.command."
  exit 1
fi

echo "==> Using Ollama model: $MODEL_NAME"

echo "==> Launching Talky..."
exec python main.py
