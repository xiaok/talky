#!/bin/zsh
set -euo pipefail

#
# Talky Cloud — Cloudflare Tunnel Setup (Mac Mini)
#
# Run this script ON the Mac Mini where talky-server is deployed.
# Prerequisites: Homebrew installed, Cloudflare account created,
#                domain added to Cloudflare (nameservers pointed).
#
# Usage:
#   ./setup_tunnel.sh <subdomain.yourdomain.com>
#   Example: ./setup_tunnel.sh api.talky.app
#

TUNNEL_NAME="talky-cloud"
LOCAL_PORT="${TALKY_PORT:-8000}"
SUBDOMAIN="${1:-}"

if [[ -z "$SUBDOMAIN" ]]; then
  echo "Usage: $0 <subdomain.yourdomain.com>"
  echo "Example: $0 api.talky.app"
  exit 1
fi

echo "==> Talky Cloud Tunnel Setup"
echo "    Tunnel name : $TUNNEL_NAME"
echo "    Local port  : $LOCAL_PORT"
echo "    Public URL  : https://$SUBDOMAIN"
echo ""

# ---- Step 1: Install cloudflared ----
if ! command -v cloudflared &>/dev/null; then
  echo "==> Installing cloudflared via Homebrew..."
  brew install cloudflared
else
  echo "==> cloudflared already installed: $(cloudflared --version)"
fi

# ---- Step 2: Login to Cloudflare ----
CF_DIR="$HOME/.cloudflared"
if [[ ! -f "$CF_DIR/cert.pem" ]]; then
  echo "==> Logging in to Cloudflare (browser will open)..."
  cloudflared tunnel login
  echo "==> Login complete."
else
  echo "==> Already logged in to Cloudflare."
fi

# ---- Step 3: Create tunnel (if not exists) ----
EXISTING=$(cloudflared tunnel list --output json 2>/dev/null | python3 -c "
import json, sys
tunnels = json.load(sys.stdin)
for t in tunnels:
    if t.get('name') == '$TUNNEL_NAME':
        print(t['id'])
        break
" 2>/dev/null || echo "")

if [[ -n "$EXISTING" ]]; then
  TUNNEL_ID="$EXISTING"
  echo "==> Tunnel '$TUNNEL_NAME' already exists: $TUNNEL_ID"
else
  echo "==> Creating tunnel '$TUNNEL_NAME'..."
  cloudflared tunnel create "$TUNNEL_NAME"
  TUNNEL_ID=$(cloudflared tunnel list --output json | python3 -c "
import json, sys
tunnels = json.load(sys.stdin)
for t in tunnels:
    if t.get('name') == '$TUNNEL_NAME':
        print(t['id'])
        break
")
  echo "==> Tunnel created: $TUNNEL_ID"
fi

# ---- Step 4: Write config ----
CONFIG_FILE="$CF_DIR/config.yml"
echo "==> Writing config to $CONFIG_FILE ..."
cat > "$CONFIG_FILE" <<YAML
tunnel: $TUNNEL_ID
credentials-file: $CF_DIR/${TUNNEL_ID}.json

ingress:
  - hostname: $SUBDOMAIN
    service: http://localhost:$LOCAL_PORT
  - service: http_status:404
YAML
echo "    Done."

# ---- Step 5: Create DNS route ----
echo "==> Creating DNS route: $SUBDOMAIN -> tunnel $TUNNEL_NAME ..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$SUBDOMAIN" || true
echo "    DNS route configured."

# ---- Step 6: Test run ----
echo ""
echo "==========================================="
echo "  Setup complete!"
echo "==========================================="
echo ""
echo "To start the tunnel manually:"
echo "  cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "To install as a background service (auto-start on boot):"
echo "  sudo cloudflared service install"
echo ""
echo "Your Talky Cloud will be available at:"
echo "  https://$SUBDOMAIN"
echo ""
echo "Test it with:"
echo "  curl https://$SUBDOMAIN/api/health"
echo ""
echo "IMPORTANT: Make sure talky-server is running before starting the tunnel:"
echo "  cd ~/talky && source .venv/bin/activate && python talky-server/main.py"
echo ""
