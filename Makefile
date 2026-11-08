PY := .venv/bin/python
# Benchmarked variants in cumulative order, then the isolated A/B toggles.
SHIP := V5Z
CUMULATIVE := V0 V1 V2 V3 V4 V5 V5S V5Z
ISOLATED := A_QSQ A_NIB A_KV
VARIANTS := $(CUMULATIVE) $(ISOLATED)
TESTER := .third_party/SameBoy/build/bin/tester/sameboy_tester
.PHONY: all bootstrap smoke train export art rom variants sameboy verify verify-all second-emulator play demo benchmark compare report dataset quality clean
all: rom verify
bootstrap:
	tools/bootstrap.sh
smoke:
	$(PY) -m pytest tests/test_smoke.py -q
dataset:
	$(PY) -c "from training.dataset import write_assets; from pathlib import Path; write_assets(Path('assets/data'))"
train:
	$(PY) training/train.py --config configs/release.yaml
	$(MAKE) export
export:
	$(PY) tools/export_weights.py
art:
	$(PY) tools/make_art.py
variants: art
	$(PY) tools/build.py $(VARIANTS)
	$(PY) tools/build.py V0 $(SHIP) --selftest
rom: variants
	cp build/$(SHIP)/gameboygpt.gb build/gameboygpt.gb
	cp build/$(SHIP)/gameboygpt.sym build/gameboygpt.sym
	cp build/V0/gameboygpt.gb build/gameboygpt_v0.gb
	cp build/V0/gameboygpt.sym build/gameboygpt_v0.sym
	mkdir -p release
	cp build/gameboygpt.gb build/gameboygpt_v0.gb release/
	cd release && shasum -a 256 gameboygpt.gb gameboygpt_v0.gb > SHA256SUMS
	cat release/SHA256SUMS
sameboy:
	test -x $(TESTER) || { git clone https://github.com/LIJI32/SameBoy .third_party/SameBoy && git -C .third_party/SameBoy checkout ea667ad && $(MAKE) -C .third_party/SameBoy tester CONF=release; }
# Host-only suites, then the full ROM suite on baseline and shipping build, then the kernel+parity suite on every variant.
verify:
	$(PY) -m pytest tests/test_smoke.py tests/test_dataset.py tests/test_fixed_point.py tests/test_game_state.py tests/test_export.py tests/test_benchmark_integrity.py -q
	mkdir -p reports/junit
	for v in V0 $(SHIP); do GBGPT_VARIANT=$$v $(PY) -m pytest tests/test_rom_game.py tests/test_buttons.py tests/test_generated_output.py tests/test_kernel_vectors.py tests/test_model_parity.py -q --junitxml=reports/junit/$$v.xml || exit 1; done
	for v in $(filter-out V0 $(SHIP),$(VARIANTS)); do GBGPT_VARIANT=$$v $(PY) -m pytest tests/test_kernel_vectors.py tests/test_model_parity.py -q --junitxml=reports/junit/$$v.xml || exit 1; done
second-emulator: sameboy
	$(PY) tools/second_emulator.py --variants V0 $(SHIP)
play: rom
	SDL_RENDER_SCALE_QUALITY=nearest $(PY) -m pyboy build/gameboygpt.gb --window SDL2 --scale 4 --dmg
# Fails if any event is not real generation: the capture script asserts token parity with the reference.
demo: rom
	$(PY) tools/capture_demo.py
benchmark:
	$(PY) tools/benchmark.py --variants $(if $(BASELINE),V0,$(VARIANTS)) --rounds 3
quality:
	$(PY) training/evaluate.py --blob generated/model.bin --out reports/quality.json > /dev/null
compare:
	$(PY) tools/compare.py
report: compare
	$(PY) tools/render_dashboard.py
clean:
	rm -rf build generated/V* generated/A_*
