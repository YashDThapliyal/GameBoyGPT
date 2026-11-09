# Verifying this release

This repository claims that a transformer runs on an emulated original Game Boy's CPU, writes a robot's dialogue there, matches an independent reference bit for bit, and runs the same way in a browser. Here is how to check each claim without trusting the author.

## Requirements

- macOS on Apple Silicon is the only platform this was run on. Linux should work but is **untested**.
- [RGBDS](https://rgbds.gbdev.io/) **v1.0.4**, [uv](https://docs.astral.sh/uv/) and Node 22. Other RGBDS versions may build working ROMs with different hashes.
- A C compiler and network access, for `make second-emulator` (it clones and builds SameBoy at commit `ea667ad`) and `npm install` (Playwright, and its Chromium if not already installed).

## One command

```
scripts/verify_release.sh
```

It rebuilds all 12 variants from source, runs every test, checks that rebuilt ROMs equal `release/`, runs the self-test ROM on SameBoy and PyBoy, and runs the browser test. It ends with `VERIFY OK` and stops at the first failure. It doesn't retrain or re-measure.

## Expected values

| Artifact | SHA-256 |
|---|---|
| `generated/model.bin` | `2cf8e1f52334cf64e08a7377d18f0fc5f3b8586521ae1f3a73b3e4827944448c` |
| `release/system_override.gb` | `958522e77e02470994f6b57ed22cd97b4d5192635a7584a824da4b9196bfb6f4` |
| `release/system_override_v0.gb` | `1964d2fc973691e6d47551d100b2dd9f2aeea23994a02cdcd23eae49c06c2dd5` |

## What to look at, by claim

| Claim | Where it's checked | How to challenge it |
|---|---|---|
| Dialogue is generated on the SM83 | `tests/test_neural_genuine.py` | Patch the weights in the ROM and the words change. The test does this to the head and to attention |
| No stored sentences | `test_rom_holds_no_authored_sentences_only_a_vocabulary` | Search the ROM yourself. Fixed interface lines are in `src/ui.asm`; words and short phrases are in the vocabulary table |
| Bit-exact arithmetic | `reference/fixed_point.py`, `tests/test_kernel_vectors.py`, `tests/test_model_parity.py` | The reference is plain Python integers, sharing no code with the trainer. Add your own vectors using `tests/kernel_harness.py` |
| The game shows what the model generated | `tests/test_rom_chat.py` | Plays the ROM through its menu and keyboard, and compares prompt, tokens, RNG state and on-screen text with the reference |
| The x-ray shows real candidates | `tests/web/e2e.mjs` | Each token that lands must be in the candidate list read from emulated memory at that moment |
| The race is a real comparison | `tests/web/e2e.mjs` | Runs both ROMs in two emulators with one seed, then requires identical tokens and at least a 5x gap in emulated time |
| Parser and memory are deterministic and match | `reference/conversation.py`, `tests/test_parser_rom.py` | Thousands of random inputs and long conversations |
| No host involvement | `src/selftest.asm`, `tools/second_emulator.py` | Run `build/V6T/selftest.gb` in any DMG emulator and read the verdict on screen |
| The browser runs the real ROM | `tests/web/e2e.mjs` | It compares tokens read from emulated RAM with the reference. No generation code exists in `web/js/`; read it, it's short |
| The timing is real | `tests/test_smoke.py`, `tools/benchmark.py` | `make benchmark` re-measures. The self-test ROM's frame counts on SameBoy equal PyBoy's |
| Tokens match across builds | `reports/benchmark.csv` | `tests/test_benchmark_integrity.py` fails on any mismatch |
| Held-out quality | `training/evaluate.py`, `reports/evaluation.json` | `make evaluate`. Read `training/corpus.py` to judge how narrow the task is |
| Memory is not learning | `src/convo.asm` | Weights are in ROM. Nothing can write to them |
| v0.3.1 is preserved | `scripts/reproduce_v031.sh` | Rebuilds the old ROMs from the tag and compares hashes |
| Training reproduces | `configs/release.yaml` | `make train`, then compare the blob hash. Byte equality isn't promised across machines or PyTorch builds |

## What this does not establish

- **Physical hardware.** Everything here ran on emulators. The SP weight stream and head tables are the parts most likely to matter on real silicon. Build V5 avoids both.
- **PPU timing.** PyBoy's memory reads don't model PPU access locks. SameBoy runs only the self-test ROM, not the whole game. The VBlank code was reviewed by reading it, which is not a hardware test.
- **General language ability.** The sentences are authored and the model recombines them. See [docs/EVALUATION.md](docs/EVALUATION.md).
- **Whether it's funny or readable.** Only a person can judge that.
