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
| Kernel | LCD off, IME off, test ROM, greedy decoding, the 4 prompts in `tools/workloads.py` | Variant comparison, phases, context-length table |
| Game | The real ROM through its real menu: LCD on, VBlank and animation on, words drawn, sampled decoding with pinned seeds | "Inside the real game" table |

Each game-mode response is also compared with the integer reference, so the timing can't describe a wrong answer.

## Metric definitions

A token's cycles run from `ProfileTokenStart` to `ProfileTokenEnd`: the whole forward pass, logit checksum, decode and writing the token. The UI hook is outside this window in kernel mode, where it's a bare `ret`, and also in game mode. Game-mode latencies run from `BuildPrompt` to each token's end, so they include the UI hook between tokens and the VBlank handler.

- **First token** is the emotion token. It includes all 9 prompt positions, and only 8 output rows are scored.
- **First word** is the second token: the first text on screen.
- **Seconds per token** excludes the first token, since prompt processing is a separate cost.
- **Seconds per response** is the whole response, from the confirming press's prompt to `<EOS>`.
- **WRAM** is what the linker allocated. The stack and mailbox are reserved on top of it. Stack high-water is measured with a fill pattern.

## Determinism

Runs are deterministic, so one round per workload suffices. To confirm, `make benchmark` can be rerun and the CSV compared. Because responses end at `<EOS>`, output lengths vary by workload but not by variant: every variant must generate the same tokens or the report is rejected by `tests/test_benchmark_integrity.py`.

## Scaling study projections

`tools/scaling_study.py` projects cost as `MACs x 232 T + rows x 170 T`, with the head term replaced by `76 T` per MAC and table-build cost for candidates that could use head tables. The 232 comes from the measured V5S kernel and the 76 and 170 from the kernel listings. Only the shipped model was measured, and its measured speed is given next to the projection in [PERFORMANCE.md](PERFORMANCE.md).
