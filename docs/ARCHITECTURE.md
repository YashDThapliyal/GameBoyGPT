# Architecture

```
Player input            quick action, or text from the on-screen keyboard
      |
Parser (deterministic)  src/parser.asm: cue words -> intent, topic, facts. Admits what it doesn't know.
      |
Memory (deterministic)  src/convo.asm: anger, respect, boredom, counts, name, like. Saved to cartridge RAM.
      |
Prompt                  <BOS> MOOD RELATION HISTORY REPEAT FACTS INTENT TOPIC <SAY>   (9 tokens)
      |
Neural inference        src/model.asm, matvec.asm, attention.asm, norm.asm: one forward pass per token
      |
Decoding                src/sampler.asm: allowed rows, repetition penalty, seeded sampling
      |
Rendering               src/ui.asm: the emotion token sets the face, words stream into the box, slots print memory
```

## Which parts are neural

| Part | Neural? | Where |
|---|---|---|
| Every word in a box marked NEURAL | **Yes** | One forward pass per token, on the SM83 |
| Which face the robot reacts with | **Yes** | The first token is an emotion, chosen by the model |
| When a response ends, how long it is | **Yes** | `<EOS>` is a token |
| Whether it mentions your name or counts your insults | **Yes** | The model decides to emit the slot token |
| The value printed for a slot (`BOB`, `3`) | No | Printed from memory by the renderer |
| Typed text to intent and topic | No | Keyword rules, the same in `reference/conversation.py` and `src/parser.asm` |
| Mood, respect, counts, repeat detection | No | Fixed rules. These are state, never weight updates |
| Boot text, intro lines, power-down lines, menus | No | Fixed text. Dialogue from this source is marked SYSTEM |
| Blink, bob, shake, talk animation | No | VBlank handler |

The model never learns during play. It remembers you only in the sense that memory changes the prompt it is given.

## Source layout

| Path | Contents |
|---|---|
| `src/matvec.asm`, `attention.asm`, `norm.asm`, `quant.asm`, `activation.asm`, `model.asm`, `sampler.asm` | The inference engine. Selected by `IF DEF` from `configs/*.yaml` |
| `src/parser.asm`, `convo.asm` | Text rules and memory, including the save format |
| `src/ui.asm`, `robot.asm`, `video.asm`, `input.asm` | Screens, sprites, VBlank uploads, joypad |
| `src/testrom.asm`, `selftest.asm`, `debug.asm`, `profile.asm` | Test commands, standalone self-test, mailbox, timing labels |
| `reference/fixed_point.py`, `conversation.py` | The independent integer reference and rules. Pure Python integers, no torch |
| `training/corpus.py`, `dialogue.py`, `model.py`, `train.py`, `evaluate.py` | Corpus, vocabulary and splits, QAT model, training, evaluation |
| `tools/` | Art, weights, ROM layout, build, benchmarks, study, report, demo |
| `web/` | The browser handheld. Plain ES modules, no build step |
| `tests/` | Python tests against reference and ROM; `tests/web/` for the browser |

## Banks and timing

Bank 0 holds everything the engine and interrupt handler touch. Bank 1 holds the conversation code, and that code is only mapped between forward passes: `TokenHook` in bank 0 switches to it after each token, and the engine switches away again by itself. Bank 2 onward holds weights, with token embeddings pinned at `$4000` so `id >> 9` selects the bank.

During a weight stream SP points into ROM and interrupts are off for one row, about three scanlines. So the VBlank handler can start late. It reads LY first and skips VRAM and OAM work when there isn't room, leaving it for the next frame. Sprites rebuild after the uploads, since a rebuild costs more than VBlank has left and its result is shown next frame. Input and animation keep running throughout inference.

## Why sprites for the face

The robot is 32 sprites in 8x16 mode. Moving one sprite's Y is a bob, tearing rows sideways is a glitch, and swapping tile numbers in two sprite rows changes the eyes and mouth without touching the dialogue. Background tiles would have needed VRAM updates per frame and a whole-row upload per change. Eight sprites per row leaves the 10-per-line limit intact, and mirrored cells cut the tile count. Sprite tiles have `$8000`-`$87FF` to themselves because the background is set to the other tile addressing mode.
