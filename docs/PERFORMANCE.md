# Performance experiments

One experiment per optimization, in the order they were applied. Every variant generates the same tokens as V0 on the same weights. The method is in [BENCHMARK_METHOD.md](BENCHMARK_METHOD.md) and all current numbers are in [RESULTS.md](../RESULTS.md). The numbers below V6T are from the old adventure model only where stated; do not reuse them for this model.

## What carried over from v0.3.1

V0 to V5Z are the same kernels, re-measured on the new model. They were extended for 16-bit token ids, 32 positions and a `DotW12`/`DotW8` entry point, and every kernel test re-runs on all variants. Their rationale is unchanged and is written up in [history/v0.3.1/PERFORMANCE.md](history/v0.3.1/PERFORMANCE.md).

## The new bottleneck, and what the study did about it

A larger vocabulary is what the character most needs, and in v0.3.1 output was already the biggest phase. Scoring about 700 words at d=32 costs about 22,000 multiplies per token, more than the rest of the block combined. Two changes follow from that.

**Low-rank head.** `d -> k -> vocabulary` turns `d x V` multiplies into `k x (d + V)`. The scaling study trained k = 8, 12, 16, 32 and full. This is a model change, not an output-preserving one, so it had to pass on quality: see the study table in RESULTS.md.

**Row pruning at the first token.** The first token is always an emotion, so only 8 rows are scored for it.

## V6T: head tables

**Hypothesis.** The head has hundreds of rows but only k inputs, and those inputs stay the same for the whole pass. So multiplying by a table beats computing each product: build `entry[w + 128] = w * z + 32768` for each input once per token, then each MAC is one lookup.

**Cost.** A table build is 256 entries at about 72 T-cycles. For k=16 that's about 295,000 T-cycles per token, and about 8 KB of scratch RAM. Work RAM can't spare that, so tables live in cartridge RAM bank 1, enabled only during the pass. The saves are in bank 0.

**Why it stays exact.** The table holds the true product plus a constant, and `k x 32768` is removed from the sum. The test suite compares every allowed logit, tokens and the checksum with the reference.

**Why only the head.** The other layers have about as many rows as inputs. A table for each of 32 inputs would cost more than the multiplies it saves. The rest of the block is untouched, and that's what now limits speed.

**Caveat.** It needs a cartridge with RAM. A real one holds RAM enabled for part of every token, which is why saves are in another bank with a checksum. Never tested on hardware.

## Not built

INT4 or mixed-precision weights, weight clustering and codebook arithmetic. The profile doesn't show a phase they'd help without giving up head tables, which need byte weights in a 256-entry index. They would also change tokens, so they'd need new quality gates rather than an equivalence test. Attention-specific work wasn't attempted either: attention is a small share of the time.

## Measured against the projection

See RESULTS.md for V6T's measured seconds per token next to the study's projection for the same configuration.
