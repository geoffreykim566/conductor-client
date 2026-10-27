#!/bin/bash
set -euo pipefail

AS="$HOME/Library/Application Support"
# Our data dir is "Conductor" when it carries our marker, else the bundle-id fallback.
if [ -f "$AS/Conductor/.conductor-logicpro" ]; then
  APP_SUPPORT="$AS/Conductor"
else
  APP_SUPPORT="$AS/com.conductor.logicpro"
fi
LEGACY_APP_SUPPORT="$AS/Conductor-v3"   # before v0.4.3; moved into APP_SUPPORT at launch
CONFIG_FILE="$APP_SUPPORT/config.json"
SERVER="https://api.askconductor.ai"

echo ""
echo "Conductor Uninstaller"
echo "---------------------"
echo "This will remove:"
echo "  • /Applications/Conductor.app"
echo "  • $APP_SUPPORT  (config.json: identity token + preferences; history.json: chat history)"
echo ""
read -r -p "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

# Notify the server before wiping local files so the identity token is still readable.
# IP-based rate limits are intentionally left intact — they live in a separate
# table keyed by IP, not the install's identity, so reinstalling doesn't reset the cap.
[ -f "$CONFIG_FILE" ] || CONFIG_FILE="$LEGACY_APP_SUPPORT/config.json"
if [ -f "$CONFIG_FILE" ] && command -v python3 &>/dev/null; then
  TOKEN=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('conductor_token',''))" "$CONFIG_FILE" 2>/dev/null || true)
  if [ -n "$TOKEN" ]; then
    curl -sf -X DELETE "$SERVER/v3/me" \
      -H "X-Conductor-Id: $TOKEN" \
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

for dir in "$APP_SUPPORT" "$LEGACY_APP_SUPPORT"; do
  if [ -d "$dir" ]; then
    rm -rf "$dir"
    echo "✓ Removed $dir"
  fi
done

echo ""
echo "Conductor has been uninstalled."
