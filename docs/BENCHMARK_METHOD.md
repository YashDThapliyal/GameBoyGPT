# Benchmark method

## Clock

The primary clock is PyBoy's internal CPU cycle counter (`pyboy._cycles()`, a private API in PyBoy 2.9.0), sampled by hooks on ROM labels. Reported seconds are `T-cycles / 4,194,304`: **emulated DMG time, not host time and not physical hardware time**.

Three checks back it up:

1. **Hand count.** `tests/test_smoke.py` asserts the counter between two labels equals a hand-counted 112 T-cycle sequence.
2. **On-device frames.** The ROM counts LCD frames. In game mode, cycles / (frames x 70,224) is reported in RESULTS.md and sits close to 1.
3. **Second emulator.** The self-test ROM prints frames per workload, and SameBoy's headless tester in DMG mode reports the same numbers as PyBoy.

## Modes

| Mode | Setup | Used for |
|---|---|---|
| Kernel | LCD off, IME off, test ROM | Ablation table, phases, microbenchmarks |
| Game | LCD on, VBlank ISR on, words drawn, real input path | The "real game loop" table |

CPU work in a DMG isn't stalled by the PPU, so the gap between modes is ISR time plus word drawing. Kernel mode excludes those; game mode includes them.

## Metric definitions

A token's cycles run from `ProfileTokenStart` to `ProfileTokenEnd`: the whole forward pass, logit checksum, decode and writing the token. In game mode the UI hook is outside this window, while the "event" window in game mode spans `NarrateEvent` to `ThinkingDone` and includes UI drawing.

- **First token** includes prefill: all 5 prompt positions for cached builds.
- **Seconds per token** is total cycles over total tokens across all workloads and rounds.
- **WRAM** is what the linker allocated, including the reserved stack and mailbox. The CSV column `peak_wram_bytes` keeps the spec's name but holds this allocated figure, not a runtime high-water mark. Stack high-water is measured with a fill pattern, in both kernel mode (CSV notes) and the game loop (RESULTS.md).

## Workloads

| Name | Event | Items | Why |
|---|---|---|---|
| PROMPT_A | HEAR_VOICE | None | First choice in the story |
| PROMPT_B | LIGHT_LAMP | Lamp | The cave, the item that matters |
| PROMPT_C | TAKE_CROWN | Lamp, key | An ending |
| PROMPT_D | CROSS_BRIDGE | Friend | Hurt at the river, with a friend |

These use greedy decoding, the same weights and 3 rounds each, with one emulator running at a time. Runs are deterministic, so rounds confirm stability rather than sample a distribution. Events end at `<EOS>`, so output lengths vary by workload.

Context lengths 4, 8, 16 and 18 are measured as a single cold step. Longer-context decode is visible in per-token traces in `reports/raw/`.

## Fairness rules

- Every variant is the same model, the same weights and the same numeric semantics. The harness records `token_match_baseline` per row, and `tests/test_benchmark_integrity.py` fails on a mismatch.
- V0 is simple code with a call per multiply, full K/V recomputation and every output row. It makes no attempt at speed, and that inflates the headline ratio, so RESULTS.md also gives the ratio against V0 plus the K/V cache. V0 does *not* compute the block at earlier positions, which a framework-style forward would do.
- No comparisons with other projects' numbers: they use different models and hardware.
- Output pruning doesn't skip work a variant needs: masked rows can't affect output, and logits for generatable tokens are compared bit for bit.

Missing values are written as `NA`. The harness won't produce zeros in their place.
