#!/usr/bin/env bash
# Home-screen entry. Termux:Widget runs ~/.shortcuts/Kit.
# Starts the real Python runtime if it is down, then opens the table in the browser.
set -euo pipefail

REPO="${KIT_REPO:-$HOME/dnd-solo}"
export KIT_HOME="${KIT_HOME:-$HOME/.kit-table}"
export KIT_TABLE_BIND=127.0.0.1
export KIT_TABLE_PORT="${KIT_TABLE_PORT:-8765}"
BASE="http://127.0.0.1:${KIT_TABLE_PORT}"

mkdir -p "$KIT_HOME"
cd "$REPO"

if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

if ! curl -sf -o /dev/null --max-time 2 "$BASE/api/health"; then
  # Loopback only. The save and the hidden state stay on the tablet.
  nohup python3 -m host.table serve >> "$KIT_HOME/server.log" 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -sf -o /dev/null --max-time 1 "$BASE/api/health"; then
      break
    fi
    sleep 0.4
  done
fi

if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "$BASE/"
else
  echo "Table is at $BASE/"
fi
