# Progress
Status: VERIFIED_RELEASE (emulator; physical hardware not tested)
Hardware: macOS / Apple Silicon / 18 GB
Toolchain: see toolchain.lock
Model: 1 layer, d=32, 2 heads, FFN 64, ctx 16, vocab 95, 14,784 params, blob sha256 2e2ca73681900e21385eeef725f07d31a29dad347b3878b9ed1ad9f40cb153d2
ROM: MBC5, 65,536 bytes, 0 SRAM. Hashes in RESULTS.md and release/SHA256SUMS
Last passing checkpoint: cp9-release
Measured baseline: see RESULTS.md (V0)
Measured optimized: see RESULTS.md (V5Z)
Next action: optional Phase 10, physical DMG with an MBC5 flash cartridge
Known risks: SP-stream kernel not tested on silicon. V5 is the fallback.

## Checkpoints
cp0 bootstrap, cp1 game shell, cp2 training, cp3 fixed point, cp4 real inference, cp5 playable, cp6 baseline, cp7 optimization, cp8 report, cp9 release.

## Not done
V6 in ROM (reference study only), V7, V8, human rating study, physical hardware.
