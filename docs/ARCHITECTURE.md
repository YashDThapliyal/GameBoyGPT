# Architecture

```
 OFFLINE (Mac: Python, PyTorch)                    ON THE CARTRIDGE (SM83 assembly only)
 ------------------------------                    -------------------------------------
 training/dataset.py  grammar, splits              game.asm       world truth: rooms, items, lives
 training/train.py    float + QAT training            |  outcome token
 tools/export_weights.py  int8 blob with SHA-256   tokenizer.asm  <BOS> ROOM INV ACT OUT
 tools/rom_layout.py  weights -> ROM layout           |
 reference/fixed_point.py  independent integers    model.asm      forward pass
      |                         |                     |- matvec.asm     dot, matvec, multiply
      v  tests compare          |                     |- norm.asm       mean-absolute norm
 tools/benchmark.py  T-cycles   +-- bit-exact --->    |- attention.asm  scores, weights, values
 tools/compare.py    reports                          |- activation.asm ReLU
 tools/capture_demo.py                                |- quant.asm      round, saturate
                                                      v
                                                   sampler.asm    mask, argmax or sampling
                                                   ui.asm, video.asm  words on screen
```

**The boundary:** during a gameplay run no host code computes anything. The harness only presses buttons and reads memory. `src/selftest.asm` proves this directly: it needs no host and prints its verdict on screen.

## Source modules

| File | Role |
|---|---|
| `boot.asm` | Vectors, header, hardware init, entry dispatch |
| `video.asm` | VBlank ISR, shadow map, text primitives, palette fades, art loading |
| `input.asm` | Joypad sampling in the ISR, edge latch |
| `ui.asm` | State machine: TITLE, INTRO, MENU, PREFILL, GENERATING, REVEAL, UPDATE, ENDING, STATS |
| `game.asm` | Deterministic world, seeded generation, rules |
| `tokenizer.asm` | Prompt builder, word wrap, streaming narration |
| `model.asm` | Forward pass, tensor buffers, output layer |
| `matvec.asm` | Multiply variants, dot kernels, matvec |
| `attention.asm`, `norm.asm`, `activation.asm`, `quant.asm`, `sampler.asm` | One operation each |
| `bank.asm` | MBC5 switching, counted for instrumentation |
| `profile.asm` | Label markers for hooks, on-device frame timing |
| `debug.asm` | Mailbox at a fixed address. The game reads only the harness overrides (seed, greedy) |
| `testrom.asm` | Kernel test command loop, test build only |
| `selftest.asm` | Host-free verification, self-test build only |

Each routine's header states its inputs, outputs and clobbered registers.

## Why words appear one at a time

The main thread does inference and the VBlank ISR does everything visual. Kernels write into a WRAM shadow of the background map and set a dirty flag per row. The ISR uploads at most 4 rows per VBlank, so inference never waits on the PPU and the spinner stays alive during a long multiply. Each new token is appended to the shadow right after it's chosen, so the player reads the sentence as it's written.

Two bugs found by the emulator tests shaped this design. Six rows per VBlank overran mode 1 and dropped writes, which is why the limit is 4. And a shadow write must be marked dirty *after* the write: marking first let a VBlank upload the old value and clear the flag.

## Variant builds

`configs/*.yaml` choose assembler defines and the ROM layout, and `tools/build.py` builds three ROMs per variant: `gameboygpt.gb`, `test.gb` and optionally `selftest.gb`. All variants live in one source tree behind `IF DEF`, and every one can be built at any time. The git tag `baseline` also pins V0 as first measured.

## Risk register

| Risk | Outcome |
|---|---|
| Inference too slow | Baseline was already playable with patience; shipping build is about a word every two-thirds of a second |
| RAM overflow | About a third of WRAM is allocated, see [MEMORY_MAP.md](MEMORY_MAP.md) |
| Broken bank switching | Tensors are read from ROMX across layouts, with parity tests on each |
| Quantization-induced nonsense | Avoided with QAT, and all quality numbers come from the integer reference |
| Misleading benchmark timing | Cycle counter calibrated against hand-counted code, cross-checked with on-device frames and a second emulator |
| Static-text fallback | Weights-patch test and ROM string audit; capped events are counted and shown |
| Real-hardware behaviour | **Open: not tested on a physical DMG** |
