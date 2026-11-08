#!/usr/bin/env bash
# End-to-end regeneration of every artifact, in dependency order. Stops at the first failure.
set -euo pipefail
PY=.venv/bin/python
echo "== build"; make rom
echo "== verify"; rm -f reports/benchmark.csv reports/benchmark.json  # stale until re-measured, and the integrity test would rightly fail
make verify
echo "== second emulator"; make second-emulator
echo "== commit code state for benchmark provenance"; git add -A; git commit -qm "chore: pipeline state before measurement" || true
echo "== benchmark"; make benchmark
echo "== integrity"; $PY -m pytest tests/test_benchmark_integrity.py -q
echo "== demo"; make demo
echo "== report"; make report
echo "PIPELINE OK"
