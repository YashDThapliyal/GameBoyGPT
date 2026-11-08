#!/usr/bin/env bash
# One-command check of this release: rebuilds from source, runs every test, compares hashes, runs the second emulator
# and the browser test. Stops at the first failure. Does not retrain or re-benchmark; see VERIFY.md for those.
set -euo pipefail
cd "$(dirname "$0")/.."
EXPECTED="$(mktemp)"
cp release/SHA256SUMS "$EXPECTED"
uv sync --python 3.12
echo "== build every variant and run all tests"
make all
echo "== rebuilt ROMs must equal the published ROMs"
diff "$EXPECTED" release/SHA256SUMS
rm -f "$EXPECTED"
echo "== model blob must match the report"
.venv/bin/python -m pytest tests/test_benchmark_integrity.py -q
echo "== self-test ROM on SameBoy and PyBoy"
make second-emulator
echo "== browser handheld, real ROM in WebAssembly"
(cd web && npm install --silent && npx playwright install chromium ffmpeg)
make web-test
echo "VERIFY OK"
