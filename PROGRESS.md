# Progress: SYSTEM OVERRIDE (branch `system-override`)
Status: IN PROGRESS. v0.3.1 stays tagged and reproducible, see below.
Physical hardware: not tested at any point in this project.

## Phase log
| Phase | State | Acceptance evidence |
|---|---|---|
| 0 Baseline | DONE | `make all` green on v0.3.1 (47 tests on V0 and V5Z, 25 on the rest), self-test ROM PASS on SameBoy and PyBoy, `scripts/reproduce_v031.sh` rebuilds both ROMs from the tag with matching SHA-256 |

## Baseline at the start of this work (v0.3.1, commit 310913e)
Model 21,504 params, vocab 196, ctx 24. V0 7.163 s/token, V5Z 0.739 s/token, 11.27 s/event. WRAM 3,545 bytes.
Archived: `release/v0.3.1/` (ROMs, model, hashes), `docs/history/v0.3.1/` (results, report, measurements).

## Reusable from v0.3.1
Kept as is: multiply and dot kernels, quarter squares, SP weight stream, zero-column skip, K/V cache, norm, attention, requantization, bank switching, VBlank upload discipline, mailbox, PyBoy harness, kernel test ROM, self-test ROM, second-emulator check, variant build system, reference.
Replaced: story engine, story UI, scene art, adventure dataset.
Extended: 16-bit token ids, output bottleneck, sampler, cartridge RAM.

## v0.3.1 progress log, kept for history
# Progress
Status: VERIFIED_RELEASE (emulator; physical hardware not tested)
Hardware: macOS / Apple Silicon / 18 GB
Toolchain: see toolchain.lock
Model: 1 layer, d=32, 2 heads, FFN 64, ctx 24, vocab 196, 21,504 params, hash in VERIFY.md
ROM: MBC5, 65,536 bytes, 0 SRAM. Hashes in RESULTS.md and release/SHA256SUMS
Last passing checkpoint: cp9-release
Measured baseline: see RESULTS.md (V0)
Measured optimized: see RESULTS.md (V5Z)
Next action: player feedback on the story, then optional Phase 10, physical DMG with an MBC5 flash cartridge
Known risks: SP-stream kernel not tested on silicon. V5 is the fallback.

## Checkpoints
cp0 bootstrap, cp1 game shell, cp2 training, cp3 fixed point, cp4 real inference, cp5 playable, cp6 baseline, cp7 optimization, cp8 report, cp9 release.

## Not done
V6 in ROM (reference study only), V7, V8, human rating study, physical hardware.

## Design change after v0.2.1
The room maze was replaced by an authored branching story (reference/story.py). The model narrates; it does not invent plot.
