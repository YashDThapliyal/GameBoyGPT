# Technical report

## The question

A Game Boy has an 8-bit CPU at 4.194304 MHz, no multiply instruction and 8 KiB of RAM. Can it run a real attention-based language model as part of an actual game, and which software changes make that faster?

Results below are from an emulated DMG, using PyBoy's cycle counter. As a check, SameBoy and PyBoy report identical LCD-frame counts from the ROM itself. No physical unit was tested. All numbers are in [RESULTS.md](RESULTS.md), which is generated from raw measurements.

## A game worth playing, and what the model does in it

The first version let the model narrate a maze of rooms. It was technically sound and made no sense to play: exits were arbitrary, and finding the lamp changed little. A bigger model wouldn't have fixed that, since at this size plot can't come from the model. So the game became a gamebook with an authored story graph (`reference/story.py`): 20 scenes across three acts, choices that depend on what you carry, and eight endings.

The engine decides what happens, then gives the model four symbolic tokens (`<BOS> EVENT ITEMS FATE`), and the model writes the passage. That split means narration can't break the rules, and the text can still matter: each arrival line warns about that scene's dangerous choice.

**What's authored and what's learned.** The sentences come from a hand-written language (`training/dataset.py`) of 141 words. The model learns it and reproduces it, varying wording by sampling. It produces every word on screen, computed on the emulated CPU, but it doesn't invent plot.

**Two models.** The shipping model trains on all 210 reachable situations and is 100% grammar-valid on them, greedy and sampled. To measure generalization, a sibling with the same recipe never sees 32 situations, each a known event with a combination of items it never saw on that event. It scored 100% on the 20 test situations and 99% over all 210. Untrained weights score 0%.

**Why the model didn't grow much.** The first candidate at the old width and depth already reached 98.6% strict validity on the new language. So growth went where the task required it: vocabulary from 95 to 196 and context from 16 to 24, which took parameters from 14,784 to 21,504 and cost time per word.

## Making the math fit

Everything is int8 in [-127, 127]. Removing -128 means `|x|` always fits in 7 bits and one multiply serves every operation. Three substitutions make the transformer integer-friendly, and QAT trains the weights under each one, so nothing is converted after the fact:

- **Normalization:** mean-absolute value and a gain table replace LayerNorm's square root and division.
- **Softmax:** max-subtract, an exponential table and a reciprocal table replace it, with the weights renormalized to sum to about 128.
- **Activation:** ReLU.

## Verification first

`reference/fixed_point.py` came before any assembly. It uses Python integers only, shares no code with the trainer, and defines every rounding and saturation rule. The kernels were then tested one at a time through a command loop in a test ROM: the harness writes inputs to WRAM, runs a command and compares memory to the reference. This caught problems immediately, including a clobbered register in the sampler.

Then the audits:

- Masked logits and token traces match the reference across 20 scenarios, greedy and sampled.
- Full journeys to three different endings match, including the on-screen text.
- Random playthroughs keep the ROM's story state identical to the reference's.
- Patching output weights inside the ROM changes narration to exactly what the reference predicts.
- A host-free self-test ROM reports the same verdict and frame counts on two emulators.

## The baseline

V0 is plain: shift-and-add multiply, a call per MAC, K and V recomputed every token. It's a straightforward port with no attempt at speed. It takes 7.2 s/token, or nearly two minutes per passage, and almost two-thirds of that goes on recomputing K and V. A speed-minded port would cache K and V from the start, so RESULTS.md also reports the gain against that stronger baseline.

## What made it faster

From 7.163 to 0.739 s/token, 9.69x, with identical tokens (4.16x against V0 with only the K/V cache added). Each experiment, including what didn't work, is in [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

The results didn't follow the spec's expectations. Bank layout, the headline idea going in, saved 0.11%. Streaming attention was meant to reduce RAM and instead added 32 bytes. The largest gains came from not doing work: not recomputing K and V, not computing rows the decoder can't choose, not multiplying by zero. The next came from plain kernel engineering: inline the MAC, keep operands where they're cheap to read. A 4 KiB nibble table lost to a 1 KiB quarter-square table on both speed and size.

## The game

Words reach the screen as they're generated. The main thread does inference while the VBlank ISR uploads dirty rows of a WRAM shadow map, so there's never a frozen screen, and the progress bar and token counter reflect real progress. The stats page shows seconds per token as timed on the device from LCD frames, and those frames agree with the emulator's cycle count to within 0.1%.

The story graph is searched exhaustively: no dead ends, no forced single choices, every ending reachable. Art and font are original and generated by a script.

## What went wrong along the way

Most of these were found by tests. The first and the last needed a person playing the game. All are now fixed and covered by tests or documented:

1. **A game that made no sense.** Playing the first version showed that it worked and wasn't fun. No test could catch that, and it's why the game was redesigned.
2. **Logic flaws in the story.** Graph tests found a choice that let you show a ring you never took, and scenes with one forced option, including a forced death.
3. **Dropped VRAM writes.** Uploading 6 rows per VBlank overran mode 1, which dropped the first characters of a row. The limit is now 4.
4. **A dirty-row race.** A direct shadow write after a row's dirty mark could be missed if a VBlank landed between them. The symptom appeared only on the fastest build, because timing changed, even though the bug was in every variant.
5. **A units bug in the sampling margin.** It made sampled text nonsense while greedy text looked perfect. The evaluator caught it.
6. **Non-reproducible training.** Multithreaded training on the same seed gave different weights. Training is now single-threaded and byte-reproducible, and everything was re-measured on the final weights.
7. **A misleading metric.** An early report called a 20.5% action score "close to chance." Untrained weights scored the same 20.5%, which exposed the real cause: WIN and LOSE sentences name no action, so they pass that check by default. The metric now excludes them.
8. **A hardware hazard, found by reading the code.** The LCD could be disabled right after a VBlank wait without re-checking LY. Doing that outside VBlank can damage a real screen. It now re-checks.
9. **An overflow in the word table.** With 141 words, the 8-bit table index wrapped, so "You" displayed as "Back". Tokens were right and only the display was wrong; comparing on-screen text with the reference caught it.
10. **A self-test time limit.** Longer passages made V0's self-test overrun its time limit, so the screen was read too early. The reader now refuses a screen with no verdict.
11. **An unreadable UI, twice.** The tests can't judge readability, and neither could small screenshots: a person playing in the real window could barely read it. The first fix added lowercase and a D-pad menu and it was still bad. What worked was copying what games of the era do: a bold font with 2-pixel strokes, text on every other row, and one job per screen. Inverse letters also needed a dark margin above and below to keep their outline. A wrong table stride during this work wrote stray bytes over the selection variable, and scripted input caught it.

## Limitations and future work

- Run it on a physical DMG with a flash cartridge. The SP-stream kernel is the part most in need of that.
- Measure power, which an emulator can't do.
- Add more story. There's plenty of ROM and RAM left, and time per word is the constraint.
- Try compiled weights and a grammar mask, as described in the performance doc.
- Give the model some memory of earlier passages, so that it can refer back to them.
- Run a human rating study. None was done.

## Prior art

See [docs/PRIOR_ART.md](docs/PRIOR_ART.md). gbc-transformer and ChatGBC run far more ambitious language tasks on the Game Boy Color, and Elyan Labs' work prompted the `pop` experiment. Attention comes from Vaswani et al. and the small-language framing from TinyStories (Eldan & Li). Numbers across projects aren't comparable, so none are compared.
