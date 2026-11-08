# Release checklist

Run from a clean clone with RGBDS and uv installed:

```
uv sync --python 3.12
(cd web && npm install)
make train           # only if retraining; hashes will change
make study           # the scaling study; about an hour
make all             # builds every variant, runs the full test suite
make second-emulator
make benchmark
make evaluate
make report
make web-test
make demo
```

- [ ] All tests pass on every variant
- [ ] `SELFTEST PASS` on SameBoy and PyBoy, with matching frames
- [ ] Every CSV row has `token_match_baseline` of `SELF` or `True` and `matches_reference` of `True`
- [ ] Browser tokens equal the reference
- [ ] Demo tokens equal the reference for its pinned seeds
- [ ] `scripts/reproduce_v031.sh` still reproduces v0.3.1
- [ ] Claims say "emulator" and "narrow domain". Memory is never called learning. Prior art is cited
