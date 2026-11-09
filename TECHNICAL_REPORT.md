# Technical report: SYSTEM OVERRIDE

All numbers are from [RESULTS.md](RESULTS.md), measured on emulators. Nothing here ran on a physical console.

## The goal

Make something a person who doesn't care about ML would enjoy: a character on a 1989 handheld who answers you, with dialogue that really is generated on the 8-bit CPU. The honest version of that sentence sets the design: the model must really generate each token, and the game must not imply it understands more than it does.

## From narrator to character

The previous project, an adventure game, had a 21,504-parameter model that narrated an authored story. Its vocabulary of 196 tokens couldn't carry a character. Personality needs words: a villain who can only say 100 things is a jukebox.

So the design questions were how large a vocabulary this CPU can score, and how to keep the wait tolerable.

## Keeping the wait tolerable

Three decisions, none of them about arithmetic:

1. **Stream.** Words appear as they're generated, so a 13-second reply reads as slow typing rather than a frozen screen.
2. **React first.** The first generated token is an emotion, so the face changes after 1.49 s, before any words. Only 8 output rows are scored for it.
3. **Stay alive.** The robot blinks, bobs and moves its mouth from the VBlank handler, which keeps running during inference. Sprites made this cheap.

Phrase tokens help too. Byte-pair encoding over the corpus's words makes "i have" one token, so a reply takes fewer forward passes.

## The scaling study

Twelve configurations trained on the previous version of the corpus, before its rewrite, from 40K to 392K parameters, including a GRU. The result was clearer than expected: **past about 46K parameters, size stopped helping**. Held-out loss was 0.500 at 46,352 parameters and stayed between 0.490 and 0.502 all the way to 392,416, which would take a projected 223 s per response. For a corpus this narrow, what limits quality is the corpus, not the model. Larger candidates only cost time, and those with d above 32 also don't fit the HRAM-based kernels.

The informative axis was the output bottleneck: k=8 gave 93.0% valid on held-out situations, k=12 96.8%, k=16 99.2%. k=16 is where the curve flattens, so it shipped. The GRU reached similar validity but a worse loss (0.585) and, with its float weights and no engine, wasn't a real alternative.

This is a warning about the study's generality: a larger and less compositional corpus might well reward a larger model. This study can't say.

## Engine changes

- **16-bit token ids.** The vocabulary is 720. Embeddings are pinned to whole banks, so `id >> 9` selects the bank.
- **Low-rank head.** `d x V` multiplies become `k x (d + V)`.
- **Head tables (V6T).** After the bottleneck, the head has 656 rows and only 16 inputs. Building a 256-entry table per input costs about 72 T-cycles an entry, and then each MAC is one lookup instead of a quarter-square pair. Result: 1.29x overall, bit-identical. The output head went from 51.2% of cycles to 37.2%. The tables take one 8 KB bank of cartridge RAM. The study projected 0.79 s/token and the kernel measured 0.90, so the projection was about 12% optimistic.
- **Sampling.** Softmax at temperature 1 over candidates near the best, using the same exponential lookup as attention, plus a repetition penalty. The old rule was uniform among 4 candidates, too crude for a model with many valid next words.

Everything else was reused unchanged. Re-measured on this model, V0 to V5Z scale about as they did before, with the output head now the clear bottleneck.

## Memory

Deterministic rules track anger, respect, boredom, insult and praise counts, repeats, the last topic, a name and a like. They compress to five prompt tokens. The model then decides whether to use them, and it does so selectively: it mentions a count or complains about repetition far more often when memory says to (rates in RESULTS.md, 0% otherwise). State persists in battery-backed cartridge RAM with a checksum, and a corrupt save is rejected. This is never described as learning, because it isn't.

## Input

The on-screen keyboard is real, and the parser behind it is honest about being keywords. It maps words to 13 cue classes and 13 topics, recognizes two sentence openings, and flips insult and praise under negation. If nothing matches, the model is told so, and its replies for that case admit it and echo the longest unknown word. On 10 unsupported requests, 7 reached that path; the other 3 hit a cue word by accident ("WHO WON THE GAME" got an identity line). That's the expected failure of keyword rules, and it's documented, not fixed: more rules only move the boundary.

## Correctness

The integer reference shares no code with the trainer. Tests compare the ROM with it at each level: multiply, dot, requantization, norm, attention, logits at every position, greedy and sampled tokens, RNG state and a logit checksum. All 12 builds pass. The parser and memory are compared with their reference on thousands of inputs. Whole conversations through the real menu and keyboard must produce the reference's prompts, tokens and on-screen text. The browser test does the same against WebAssembly.

Testing found real bugs. A macro operator-precedence error in V6T's first version picked wrong table pages, and the token comparison caught it at once. Code review found stale button presses dismissing replies unread, and a forget command that left the old mood behind. The browser test found that Enter could turn the console off when the power button had focus.

## The browser handheld

A presentation layer. `web/` is plain ES modules with no build step, around [binjgb](https://github.com/binji/binjgb), chosen because it's MIT licensed, actively maintained, ships WebAssembly and exposes memory reads for the technical panel. WasmBoy (GPL-3.0, last pushed in 2023) was the alternative checked. The JavaScript moves bytes: ROM in, joypad in, frames and audio out, memory read for the panel. It can't generate text, and the browser test proves the tokens came from the ROM.

Scaling is to whole device pixels, so LCD pixels stay square. The panel's live values come from emulated WRAM, and its benchmark numbers are labelled as such.

## What didn't work, or wasn't done

- A bigger model didn't help on this corpus.
- V1, V4, V5S and V5Z are each small. V1 is 1.00x, V4 1.02x.
- INT4, clustering and codebooks weren't built. The profile gives no reason to, and they'd change tokens.
- The parser's misrouting remains.
- No physical hardware test. The SP weight stream and head tables are the riskiest parts on silicon. A person hasn't judged whether it's funny over a long session.
