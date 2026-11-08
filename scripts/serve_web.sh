#!/usr/bin/env bash
# Serves the browser handheld on this machine only.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8123}"
.venv/bin/python tools/build_web.py
echo "Open http://127.0.0.1:$PORT/"
exec .venv/bin/python -m http.server "$PORT" --bind 127.0.0.1 --directory web
