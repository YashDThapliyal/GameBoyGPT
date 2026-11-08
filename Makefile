PY := .venv/bin/python
.PHONY: bootstrap smoke
bootstrap:
	tools/bootstrap.sh
smoke:
	$(PY) -m pytest tests/test_smoke.py -q
