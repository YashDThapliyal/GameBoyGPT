#!/usr/bin/env bash
# One-command check of this release: rebuilds from source, runs every test, compares hashes, runs the second emulator.
# Stops at the first failure. Does not retrain and does not re-benchmark; see VERIFY.md for those.
set -euo pipefail
cd "$(dirname "$0")/.."
cp release/SHA256SUMS /tmp/gbgpt_expected_sums.$$
uv sync --python 3.12
echo "== build every variant and run all tests"
make all
echo "== rebuilt ROMs must equal the published ROMs"
diff /tmp/gbgpt_expected_sums.$$ release/SHA256SUMS
rm -f /tmp/gbgpt_expected_sums.$$
echo "== model blob must match the checkpoint and the report"
.venv/bin/python -m pytest tests/test_export.py tests/test_benchmark_integrity.py -q
echo "== self-test ROM on SameBoy and PyBoy"
make second-emulator
echo "VERIFY OK"
