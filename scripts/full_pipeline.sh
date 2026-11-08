#!/usr/bin/env bash
# End-to-end regeneration of every artifact, in dependency order. Stops at the first failure.
set -euo pipefail
PY=.venv/bin/python
echo "== sparsity"; $PY tools/sparsity_study.py
echo "== build"; make rom
echo "== verify"; make verify
echo "== second emulator"; make second-emulator
echo "== commit code state for benchmark provenance"; git add -A; git commit -qm "chore: pipeline state before measurement" || true
echo "== benchmark"; make benchmark
echo "== integrity"; $PY -m pytest tests/test_benchmark_integrity.py -q
echo "== demo"; make demo
echo "== report"; make report
echo "PIPELINE OK"
