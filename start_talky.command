#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "==> Talky one-click start"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi

source ".venv/bin/activate"

echo "==> Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

if [[ ! -d "local_whisper_model" ]]; then
  echo "==> local_whisper_model not found, downloading..."
  python download_model.py
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Error: ollama command not found. Install Ollama first."
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
from pathlib import Path

default_model = "qwen3.5:9b"
config_path = Path.home() / ".talky" / "settings.json"
if not config_path.exists():
    print(default_model)
else:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        print(str(data.get("ollama_model", default_model)))
    except Exception:
        print(default_model)
PY
)"

if ! ollama show "$MODEL_NAME" >/dev/null 2>&1; then
  echo "==> Pulling Ollama model: $MODEL_NAME"
  ollama pull "$MODEL_NAME"
fi

echo "==> Launching Talky..."
exec python main.py
