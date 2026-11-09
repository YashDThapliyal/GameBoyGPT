PY := .venv/bin/python
# Benchmarked variants in cumulative order, then the isolated A/B toggles.
SHIP := V6T
CUMULATIVE := V0 V1 V2 V3 V4 V5 V5S V5Z V6T
ISOLATED := A_QSQ A_NIB A_KV
VARIANTS := $(CUMULATIVE) $(ISOLATED)
TESTER := .third_party/SameBoy/build/bin/tester/sameboy_tester
.PHONY: all bootstrap smoke train study export art rom variants sameboy verify second-emulator play web web-art web-test demo demo-short gif benchmark report evaluate clean
all: rom verify
bootstrap:
	tools/bootstrap.sh
smoke:
	$(PY) -m pytest tests/test_smoke.py -q
train:
	$(PY) training/train.py --config configs/release.yaml
	$(MAKE) export
study:
	$(PY) tools/scaling_study.py --all
export:
	$(PY) tools/export_weights.py
art:
	$(PY) tools/make_art.py
variants: art
	$(PY) tools/build.py $(VARIANTS)
	$(PY) tools/build.py V0 $(SHIP) --selftest
rom: variants
	cp build/$(SHIP)/gameboygpt.gb build/system_override.gb
	cp build/$(SHIP)/gameboygpt.sym build/system_override.sym
	cp build/V0/gameboygpt.gb build/system_override_v0.gb
	mkdir -p release
	cp build/system_override.gb build/system_override_v0.gb release/
	cd release && shasum -a 256 system_override.gb system_override_v0.gb > SHA256SUMS
	cat release/SHA256SUMS
sameboy:
	test -x $(TESTER) || { git clone https://github.com/LIJI32/SameBoy .third_party/SameBoy && git -C .third_party/SameBoy checkout ea667ad && $(MAKE) -C .third_party/SameBoy tester CONF=release; }
# Host-only suites, then the full ROM suite on baseline and shipping build, then the kernel+parity suite on every variant.
verify:
	$(PY) -m pytest tests/test_smoke.py tests/test_conversation.py tests/test_fixed_point.py tests/test_export.py tests/test_benchmark_integrity.py -q
	mkdir -p reports/junit
	for v in V0 $(SHIP); do GBGPT_VARIANT=$$v $(PY) -m pytest tests/test_kernel_vectors.py tests/test_model_parity.py tests/test_parser_rom.py tests/test_rom_chat.py -q --junitxml=reports/junit/$$v.xml || exit 1; done
	for v in $(filter-out V0 $(SHIP),$(VARIANTS)); do GBGPT_VARIANT=$$v $(PY) -m pytest tests/test_kernel_vectors.py tests/test_model_parity.py -q --junitxml=reports/junit/$$v.xml || exit 1; done
second-emulator: sameboy
	$(PY) tools/second_emulator.py --variants V0 $(SHIP)
play: rom
	SDL_RENDER_SCALE_QUALITY=nearest $(PY) -m pyboy build/system_override.gb --window SDL2 --scale 4 --dmg
web: rom
	scripts/serve_web.sh
web-art:
	$(PY) tools/make_web_art.py
web-test:
	$(PY) tools/build_web.py
	node tests/web/e2e.mjs
demo:
	$(PY) tools/build_web.py
	node tools/capture_demo.mjs
gif:
	$(PY) tools/build_web.py
	node tools/capture_gif.mjs
demo-short:
	$(PY) tools/make_short_demo.py
benchmark:
	$(PY) tools/benchmark.py --variants $(VARIANTS) --game V0 $(SHIP)
evaluate:
	$(PY) training/evaluate.py --out reports/evaluation.json > /dev/null
report:
	$(PY) tools/report.py
clean:
	rm -rf build generated/V* generated/A_*
