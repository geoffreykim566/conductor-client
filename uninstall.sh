#!/bin/bash
set -euo pipefail

APP_SUPPORT="$HOME/Library/Application Support/Conductor"
CONFIG_FILE="$APP_SUPPORT/config.json"
SERVER="https://askconductor.ai"

echo ""
echo "Conductor Uninstaller"
echo "---------------------"
echo "This will remove:"
echo "  • /Applications/Conductor.app"
echo "  • $APP_SUPPORT  (chat history, config, and API key)"
echo ""
read -r -p "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

# Notify the server before wiping local files so the device_id is still readable.
# IP-based rate limits are intentionally left intact — they live in a separate
# table keyed by IP, not device UUID, so reinstalling doesn't reset the cap.
if [ -f "$CONFIG_FILE" ] && command -v python3 &>/dev/null; then
  DEVICE_ID=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('device_id',''))" "$CONFIG_FILE" 2>/dev/null || true)
  if [ -n "$DEVICE_ID" ]; then
    curl -sf -X DELETE "$SERVER/v1/me" \
      -H "X-Conductor-Id: $DEVICE_ID" \
      -H "Content-Type: application/json" \
      --max-time 5 >/dev/null 2>&1 || true
    echo "✓ Notified server"
  fi
fi

if [ -d "/Applications/Conductor.app" ]; then
  rm -rf "/Applications/Conductor.app"
  echo "✓ Removed /Applications/Conductor.app"
else
  echo "  Skipped: /Applications/Conductor.app not found"
fi

if [ -d "$APP_SUPPORT" ]; then
  rm -rf "$APP_SUPPORT"
  echo "✓ Removed $APP_SUPPORT"
else
  echo "  Skipped: $APP_SUPPORT not found"
fi

echo ""
echo "Conductor has been uninstalled."
