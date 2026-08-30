#!/usr/bin/with-contenv bashio
set -euo pipefail

export DISPLAY=:99
PROFILE_DIR=/data/chromium-profile
mkdir -p "$PROFILE_DIR"

cleanup() {
  echo "[INFO] Stopping browser services..."
  kill "${BOT_PID:-}" "${NOVNC_PID:-}" "${VNC_PID:-}" "${CHROME_PID:-}" "${OPENBOX_PID:-}" "${XVFB_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

Xvfb :99 -screen 0 1280x900x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 1

openbox-session >/tmp/openbox.log 2>&1 &
OPENBOX_PID=$!

chromium-browser \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --disable-background-networking \
  --disable-component-update \
  --disable-features=Translate,OptimizationHints \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir="$PROFILE_DIR" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --window-size=1280,900 \
  --start-maximized \
  "https://www.aliexpress.com/p/coin-pc-index/index.html" \
  >/tmp/chromium.log 2>&1 &
CHROME_PID=$!

sleep 3
x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 -quiet >/tmp/x11vnc.log 2>&1 &
VNC_PID=$!

# noVNC is exposed only through Home Assistant Ingress.
novnc_server --listen 8099 --vnc localhost:5900 >/tmp/novnc.log 2>&1 &
NOVNC_PID=$!

python3 /bot.py &
BOT_PID=$!

wait "$BOT_PID"
