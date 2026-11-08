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
- **WRAM** is what the linker allocated, including the reserved stack and mailbox. Stack high-water is measured with a fill pattern.

## Workloads

| Name | Room | Inventory | Action | Outcome |
|---|---|---|---|---|
| PROMPT_A | Forest | None | LEFT | MOVE |
| PROMPT_B | Cave | Lamp and key | SEARCH | KEY |
| PROMPT_C | Tower | Lamp and key | FORWARD | WIN |
| PROMPT_D | River | None | RIGHT | MOVE |

These use greedy decoding, the same weights and 3 rounds each, with one emulator running at a time. The spec's PROMPT_B says "cave + lantern + SEARCH". The closest reachable situation has the key just found, so the inventory token already includes it. Events end at `<EOS>`, so output lengths are 9 to 11 tokens rather than the spec's 16-token cap.

Context lengths 4, 8 and 16 are measured as a single cold step. Longer-context decode is visible in per-token traces in `reports/raw/`.

## Fairness rules

- Every variant is the same model, the same weights and the same numeric semantics. The harness records `token_match_baseline` per row, and `tests/test_benchmark_integrity.py` fails on a mismatch.
- V0 isn't deliberately crippled: it's simple code with a call per multiply and full K/V recomputation, as a straightforward port would be. It does *not* compute the block at earlier positions, which a framework-style forward would do.
- No comparisons with other projects' numbers: they use different models and hardware.
- Output pruning doesn't skip work a variant needs: masked rows can't affect output, and logits for generatable tokens are compared bit for bit.

Missing values are written as `NA`. The harness won't produce zeros in their place.
