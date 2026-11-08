PY := .venv/bin/python
ASMFLAGS := -I src/include -I generated -E
FIXFLAGS := -v -p 0xFF -m MBC5 -t GAMEBOYGPT -n 1 -k HB -l 0x33 -r 3
SOURCES := $(wildcard src/*.asm)
.PHONY: bootstrap smoke rom art
bootstrap:
	tools/bootstrap.sh
smoke:
	$(PY) -m pytest tests/test_smoke.py -q
art: generated/assets.asm
generated/assets.asm: tools/make_art.py
	$(PY) tools/make_art.py
rom: build/gameboygpt.gb
build/gameboygpt.gb: $(SOURCES) generated/assets.asm $(wildcard src/include/*.inc)
	mkdir -p build/obj
	for f in $(SOURCES) generated/assets.asm; do rgbasm $(ASMFLAGS) -o build/obj/$$(basename $$f .asm).o $$f || exit 1; done
	rgblink -w -p 0xFF -m build/gameboygpt.map -n build/gameboygpt.sym -o $@ build/obj/*.o
	rgbfix $(FIXFLAGS) $@
