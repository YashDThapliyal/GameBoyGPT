# Performance experiments

One experiment per optimization, in the order they were applied. Every variant generates the same tokens as V0. The method is in [BENCHMARK_METHOD.md](BENCHMARK_METHOD.md), and current measurements are in [RESULTS.md](../RESULTS.md). "Step" is the gain over the previous row.

| Variant | Hypothesis | Step | Decision |
|---|---|---:|---|
| V0 vanilla | The baseline | 5.805 s/token | Kept, frozen, tag `baseline` |
| V1 bank-aware layout | Fewer bank switches matter | 1.00x (0.13%) | Kept. Harmless, but near zero |
| V2 quarter-square multiply | Table lookup beats shift-and-add | 1.76x | Kept |
| V3 fused dot, output pruning | Calling a multiply per MAC is the overhead | 1.81x | Kept |
| V4 sparse attention sum | Attention is memory-bound | 1.02x | Kept, but it missed the hypothesis |
| V5 K/V cache | Recomputing keys and values dominates | 2.43x | Kept |
| V5S SP weight stream | `pop` beats two reloads per weight | 1.09x | Kept, with a hardware caveat |
| V5Z zero-column skip | ReLU makes `x = 0` common | 1.07x | Kept, shipping build |

## V1: Bank-aware layout

Tensors moved from linker-floated sections across banks to one bank, and redundant bank writes are now skipped. Bank switches per token fell from 779.8 to 0.0. Saved: 0.13%.

**Why so little:** the bank routine costs on the order of a hundred T-cycles and V1 still calls it (it returns early when the bank is already selected), while a V0 token takes 24 million. The model also fits in one bank. Bank scheduling would matter for a model that spans several banks in a hot loop, and this one doesn't.

## V2: Multiply alternatives

Three multiplies with the same interface, each dropped into V0 and timed:

| Multiply | Mul, T-cycles | Whole model vs V0 | Table |
|---|---:|---:|---:|
| Shift and add | 520-588 | 1.00x | None |
| 4-bit nibble table | about 400 | 1.20x | 4 KiB |
| Quarter squares | 196, constant | 1.76x | 1 KiB |

The nibble table lost on both speed and size. It still has to handle signs and shift 16 bits by four, while quarter squares need neither: biasing both inputs by 128 makes the carry of the 9-bit sum select the table page.

## V3: Fused kernels

A per-MAC cost of 464 T-cycles fell to 254 by removing the call, pushes and memory-based loop state. `x` is held biased in HRAM, so each MAC reads it with an immediate address and needs no pointer. Weights are stored biased in ROM. Each element has its own unrolled block, which is why bank 0 usage grows from 9.8 KB in V2 to 15.9 KB in V5Z. Output rows for tokens the mask can never choose are not computed, which saves 27 of 95 rows.

## V4: Sparse attention

The spec's hypothesis was that streaming attention would reduce peak RAM. It didn't. The max-subtract weights need every score before any weight is known, and an exact result can't avoid that, so the 16-byte score vector stays. This variant instead changes the sum from column-wise to position-wise and skips weights that rounded to zero. WRAM went **up** by 32 bytes for accumulators, and speed improved 1.02x. Attention was only 2.5% of V0's cycles, so even a much better kernel couldn't do much. This is not FlashAttention.

## V5: K/V cache

In a one-layer model, `K[j]` and `V[j]` depend only on token `j` and its position, so recomputing them is pure waste. V0 spent 66.6% of its cycles there. This was by far the cheapest change: a few lines, no extra RAM (the buffer had to exist anyway to hold values until weights were known), and token cost stops growing with context. Alone on V0 it gives 2.31x, and in sequence 2.43x. It's a fixed-capacity buffer and not PagedAttention.

## V5S: Weights through the stack pointer

`pop bc` reads two weights in 12 T-cycles and keeps both in registers, so each is loaded once. Per-MAC cost fell from 254 to 232. Interrupts are held off for one row at a time and nothing is ever pushed while SP points into ROM. Since a VBlank can now start late, the ISR checks LY before touching VRAM or OAM and leaves dirty rows for the next frame. The cost is that screen updates can lag by a few frames during inference; nothing is corrupted. The size of that lag wasn't measured.

**Caveat:** Elyan Labs warn about this technique under active interrupts, and their SP kernel is unverified on hardware. Ours passes on SameBoy but hasn't run on a physical DMG either.

## V5Z: Zero-column skip

62% of `f` is exactly zero after ReLU, measured across all situations on the reference (`tools/sparsity_study.py`). Each block in the 64-wide kernel now tests for the biased zero first. Dense vectors get slower (213 to 227 T-cycles per MAC on the dense microbenchmark) while real inference gets faster, because real activations are sparse. Only the 64-wide kernel pays for the test.

## Where the time goes now

| Phase | V0 | V5Z |
|---|---:|---:|
| Keys and values | 66.6% | 26.9% |
| Query | 3.4% | 8.9% |
| Attention | 2.5% | 7.3% |
| Projection and norm | 3.6% | 10.1% |
| Feed-forward and norm | 13.7% | 28.5% |
| Output logits | 10.0% | 18.0% |
| Token decode | under 0.1% | 0.4% |

## Precision study (V6)

Studied on the reference only, with no ROM built and no retraining. Weights rounded to 4 bits stayed 100% strict-valid on this checkpoint, with 17.7% token agreement with the 8-bit model. At 3 bits validity collapsed to 5.3%. Packing would save an estimated 5.6 KB but needs an unpack step, and it wouldn't be faster with these kernels. Since this ROM has room, it wasn't worth building. A 4-bit result is not an output-identical speed claim: its tokens differ.

## Not attempted

V7 (ternary or codebook weights) and V8 (automatic configuration search).

## Ideas with measured motivation

The largest remaining phases are all dense matvecs. Compiling weights into per-row code (shift-and-add for each constant) might be substantially faster at the price of hundreds of KB of ROM; that's an untested estimate. A finite-state grammar mask could prune more output rows, but it would change which tokens can be chosen, so it would need its own reference and quality gates.
