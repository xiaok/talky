#!/bin/zsh
#
# Talky Cloud — Start server + Cloudflare Tunnel
#
# Run this ON the Mac Mini. Starts both the FastAPI server
# and the cloudflared tunnel in parallel.
#
# Usage:
#   ./start_cloud.sh
#
# Prerequisites:
#   1. Run setup_tunnel.sh first (one-time setup)
#   2. Ollama must be running: ollama serve
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TUNNEL_NAME="talky-cloud"

echo "==> Talky Cloud Launcher"
echo "    Project: $PROJECT_DIR"

# Check Ollama
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "⚠  Ollama is not running. Start it first: ollama serve"
  exit 1
fi
echo "    Ollama: OK"

# Check cloudflared
if ! command -v cloudflared &>/dev/null; then
  echo "⚠  cloudflared not installed. Run setup_tunnel.sh first."
  exit 1
fi
echo "    cloudflared: OK"

cleanup() {
  echo ""
  echo "==> Shutting down..."
  kill $SERVER_PID 2>/dev/null || true
  kill $TUNNEL_PID 2>/dev/null || true
  wait 2>/dev/null
  echo "==> Done."
}
trap cleanup EXIT INT TERM

# Start FastAPI server
echo "==> Starting Talky Cloud server..."
cd "$PROJECT_DIR"
source .venv/bin/activate
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
python talky-server/main.py &
SERVER_PID=$!

sleep 3

if ! kill -0 $SERVER_PID 2>/dev/null; then
  echo "⚠  Server failed to start. Check logs above."
  exit 1
fi
echo "    Server PID: $SERVER_PID"

# Start Cloudflare Tunnel
echo "==> Starting Cloudflare Tunnel..."
cloudflared tunnel run "$TUNNEL_NAME" &
TUNNEL_PID=$!

sleep 2

if ! kill -0 $TUNNEL_PID 2>/dev/null; then
  echo "⚠  Tunnel failed to start. Run setup_tunnel.sh first."
  exit 1
fi
echo "    Tunnel PID: $TUNNEL_PID"

echo ""
echo "==========================================="
echo "  Talky Cloud is running!"
echo "  Press Ctrl+C to stop."
echo "==========================================="
echo ""

wait
