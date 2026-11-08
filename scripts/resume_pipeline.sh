#!/usr/bin/env bash
# Second half of full_pipeline.sh: everything after the test suite has passed.
set -euo pipefail
PY=.venv/bin/python
[ "${SKIP_SECOND_EMULATOR:-0}" = 1 ] || { echo "== second emulator"; make second-emulator; }
echo "== commit code state for benchmark provenance"; git add -A; git commit -qm "chore: pipeline state before measurement" || true
echo "== benchmark"; make benchmark
echo "== integrity"; $PY -m pytest tests/test_benchmark_integrity.py -q
echo "== demo"; make demo
echo "== report"; make report
echo "PIPELINE OK"
