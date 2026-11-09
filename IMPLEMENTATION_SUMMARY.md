# Implementation summary

SYSTEM OVERRIDE, on branch `system-override`. Not merged and not pushed. Nothing was published. Measurements are in [RESULTS.md](RESULTS.md), and every one comes from an emulator.

## Acceptance criteria

| # | Criterion | State | Evidence |
|---|---|---|---|
| 1 | Boots in DMG emulation | Met | PyBoy (`cgb=False`), SameBoy `--dmg` (self-test ROM), binjgb. `test_cartridge_header...` |
| 2 | Polished, animated character | Met technically; taste is yours to judge | 8 expressions, idle, blink, talk, think, glitch, shake. `assets/tiles/robot_expressions.png` |
| 3 | Actions and custom text | Met | `tests/test_rom_chat.py` |
| 4 | Real neural dialogue on the Game Boy | Met | `tests/test_neural_genuine.py`: patching weights changes the words, and the ROM holds no corpus sentences |
| 5 | Responses depend on input and state | Met | RESULTS.md: conditioning, field sensitivity and memory rates |
| 6 | Numerical verification | Met | Kernels, logits, tokens and RNG against the reference on 12 builds |
| 7 | Responsive and usable | Met by measurement; "feels good" is yours to judge | First word 2.40 s, 0.93 s per word. Input and animation stay live |
| 8 | Browser shell runs and controls the real ROM | Met | `tests/web/e2e.mjs`: tokens in WebAssembly equal the reference |
| 9 | Benchmark suite | Met | `tools/benchmark.py`, `reports/`, integrity test |
| 10 | Reproducible builds, docs | Met on this machine | `scripts/verify_release.sh`. Only macOS on Apple Silicon was tried |
| 11 | Existing work preserved | Met | Tag `v0.3.1`, archive, `scripts/reproduce_v031.sh` |
| 12 | Claims supported by evidence | Met as far as checked | [VERIFY.md](VERIFY.md) maps each claim to a test |

## Delivered

ROM and baseline ROM in `release/`; SM83 source in `src/`; corpus and training in `training/`; weights in `generated/model.bin` and `checkpoints/release.pt`; robot art in `tools/make_robot.py` and `assets/tiles/`; browser handheld in `web/`; tests in `tests/`; benchmarks and the study in `tools/` and `reports/`; screenshots and demo in `docs/`; documents listed in the [README](README.md).

## Decisions made without asking

- **The goal replaced the planned richer lines for the adventure.** That work wasn't done, since the adventure is no longer the product. The old game remains on its tag.
- **The reference images** look like fan art of an existing comic character. They steered general proportions only. The robot is an original design, and the images stay out of version control and out of the ZIP. Check that the robot looks sufficiently different to you before publishing.
- **The model is smaller than the goal's suggested sizes,** at 44,288 parameters rather than 50K to 300K. The study found larger models didn't help on this corpus and cost far more time.
- **The shell is a homage to the 1989 hardware, drawn as pixel art with its own wordmark.** It uses no Nintendo logos, and the page credits the Game Boy by name and says the project is unaffiliated. You chose to keep it, knowing that credit and being non-commercial do not rule out a takedown request.
- **Added cartridge RAM** for saves and head tables, so a physical cartridge would need MBC5 with 32 KB of RAM and a battery.
- **The demo's sampler seeds were chosen,** as [docs/DEMO.md](docs/DEMO.md) says.

## Remaining issues

- Never run on a physical console. The SP weight stream and head tables are the riskiest parts.
- The full game has run on PyBoy and binjgb only. SameBoy ran only the self-test ROM.
- The parser misroutes some unsupported input (3 of 10 in the evaluation set).
- A few replies are ungrammatical (0.2% to 0.3% in sampling), and valid replies can still be non sequiturs. No automatic check catches those.
- Audio was never listened to. It's a short blip per word.
- The demo runs about 77 s at real speed, well over the original 20 to 30 s target.
- Whether it's funny over a long session is unknown. That needs a person.
- The ZIP's `.git` directory contains your commit email, if you share it.
