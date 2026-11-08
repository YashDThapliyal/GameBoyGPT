#!/usr/bin/env bash
# Non-destructive environment check. Installs nothing unless INSTALL=1. Never asks for credentials.
set -u
fail=0
need() { if command -v "$1" >/dev/null 2>&1; then echo "ok    $1: $($1 --version 2>&1 | head -1)"; else echo "MISS  $1 ($2)"; fail=1; fi; }
uname -sm
need rgbasm  "brew install rgbds"
need rgblink "brew install rgbds"
need rgbfix  "brew install rgbds"
need uv      "https://docs.astral.sh/uv/"
if [ "${INSTALL:-0}" = 1 ]; then command -v rgbasm >/dev/null || brew install rgbds; fi
uv sync --python 3.12 || fail=1
.venv/bin/python -c "import torch,numpy;print('torch',torch.__version__,'mps',torch.backends.mps.is_available(),'numpy',numpy.__version__)" 2>/dev/null || fail=1
uv pip list 2>/dev/null | grep -i '^pyboy' || fail=1
df -h . | tail -1
exit $fail
