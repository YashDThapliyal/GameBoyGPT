# Progress: SYSTEM OVERRIDE (branch `system-override`)
Status: released on `main`, published on GitHub and live at https://gameboygpt.vercel.app. v0.3.1 stays tagged and reproducible, see below.
Physical hardware: not tested at any point in this project.

## Phase log
| Phase | State | Acceptance evidence |
|---|---|---|
| 0 Baseline | DONE | `make all` green on v0.3.1, self-test PASS on SameBoy and PyBoy, `scripts/reproduce_v031.sh` matches hashes |
| 1 Character | DONE | `tools/make_robot.py`, 8 expressions, sprite animation; `assets/tiles/robot_expressions.png` |
| 2 Interaction | DONE | `tests/test_rom_chat.py` (actions, keyboard, memory, saves), `tests/test_parser_rom.py` |
| 3 Scaling study | DONE | `tools/scaling_study.py`, `reports/study/`, table in RESULTS.md |
| 4 Integration | DONE | `generated/model.bin`, 16-bit ids, low-rank head, `tests/test_neural_genuine.py` |
| 5 Numerical verification | DONE | `tests/test_kernel_vectors.py`, `tests/test_model_parity.py` on all 12 builds |
| 6 Playable | DONE | `tests/test_rom_chat.py`; human judgement of fun still open |
| 7 Browser | DONE | `tests/web/e2e.mjs`: tokens in WebAssembly equal the reference |
| 8 Optimization | DONE | V6T head tables, 1.29x, bit-exact |
| 9 Benchmarks, evaluation | DONE | `reports/benchmark.csv`, `reports/evaluation.json`, RESULTS.md |
| 10 Polish | DONE | Demo, screenshots, docs |

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
