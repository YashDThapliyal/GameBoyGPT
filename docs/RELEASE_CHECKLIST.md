# Release checklist

Run from a clean clone with RGBDS and uv installed:

```
uv sync --python 3.12
make all          # builds every variant, runs the full test suite
make second-emulator
make benchmark
make quality
make demo
make report       # figures, RESULTS.md, memory map, dashboard
```

- [ ] All tests pass on every variant
- [ ] `SELFTEST PASS` on SameBoy and PyBoy, with matching frames
- [ ] Every CSV row's `token_match_baseline` is `SELF` or `True`
- [ ] README's generated block matches RESULTS.md
- [ ] Claims say "emulator" and "tiny causal transformer"; prior art is cited
- [ ] `NOTICE.md` is current; no third-party art, no Nintendo marks
- [ ] Not done for this release: physical DMG run
