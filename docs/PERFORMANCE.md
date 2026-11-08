# Performance experiments

One experiment per optimization, in the order they were applied. Every variant generates the same tokens as V0. The method is in [BENCHMARK_METHOD.md](BENCHMARK_METHOD.md), and current measurements are in [RESULTS.md](../RESULTS.md). "Step" is the gain over the previous row.

| Variant | Hypothesis | Step | Decision |
|---|---|---:|---|
| V0 vanilla | The baseline | 7.163 s/token | Kept, as the baseline |
| V1 bank-aware layout | Fewer bank switches matter | 1.00x (0.11%) | Kept. Harmless, but near zero |
| V2 quarter-square multiply | Table lookup beats shift-and-add | 1.76x | Kept |
| V3 fused dot, output pruning | Calling a multiply per MAC is the overhead | 1.85x | Kept |
| V4 sparse attention sum | Attention is memory-bound | 1.02x | Kept, but it missed the hypothesis |
| V5 K/V cache | Recomputing keys and values dominates | 2.54x | Kept |
| V5S SP weight stream | `pop` beats two reloads per weight | 1.09x | Kept, with a hardware caveat |
| V5Z zero-column skip | ReLU makes `x = 0` common | 1.06x | Kept, shipping build |

Together, V5Z is 9.69x faster than V0. V0 recomputes every key and value for each token, which inflates that figure. Against V0 with only the K/V cache added, V5Z is 4.16x faster, which is the fairer number for the kernel work alone.

## V1: Bank-aware layout

Tensors moved from linker-floated sections to banks filled in consumption order, and redundant bank writes are now skipped. The model no longer fits one bank, so 2 switches per token remain, down from 895. Saved: 0.11%.

**Why so little:** the bank routine costs on the order of a hundred T-cycles and V1 still calls it (it returns early when the bank is already selected), while a V0 token takes 30 million. Bank scheduling would matter for a model that crosses banks inside a hot loop, and no tensor here does.

## V2: Multiply alternatives

Three multiplies with the same interface, each dropped into V0 and timed:

| Multiply | Mul, T-cycles | Whole model vs V0 | Table |
|---|---:|---:|---:|
| Shift and add | 520-588 | 1.00x | None |
| 4-bit nibble table | about 400 | 1.20x | 4 KiB |
| Quarter squares | 196, constant | 1.76x | 1 KiB |

The nibble table lost on both speed and size. It still has to handle signs and shift 16 bits by four, while quarter squares need neither: biasing both inputs by 128 makes the carry of the 9-bit sum select the table page.

## V3: Fused kernels

A per-MAC cost of 464 T-cycles fell to 253 by removing the call, pushes and memory-based loop state. `x` is held biased in HRAM, so each MAC reads it with an immediate address and needs no pointer. Weights are stored biased in ROM. Each element has its own unrolled block, which is why bank 0 usage grows from 8.7 KB in V2 to 14.9 KB in V5Z. Output rows for tokens the mask can never choose are not computed, which saves 55 of 196 rows.

## V4: Sparse attention

The spec's hypothesis was that streaming attention would reduce peak RAM. It didn't. The max-subtract weights need every score before any weight is known, and an exact result can't avoid that, so the score vector stays. This variant instead changes the sum from column-wise to position-wise and skips weights that rounded to zero. WRAM went **up** by 32 bytes for accumulators, and speed improved 1.02x. Attention was only 2.4% of V0's cycles, so even a much better kernel couldn't do much. This is not FlashAttention.

## V5: K/V cache

In a one-layer model, `K[j]` and `V[j]` depend only on token `j` and its position, so recomputing them is pure waste. V0 spent 63.9% of its cycles there. This was by far the cheapest change: a few lines, no extra RAM (the buffer had to exist anyway to hold values until weights were known), and token cost stops growing with context. Alone on V0 it gives 2.33x, and in sequence 2.54x. It's a fixed-capacity buffer and not PagedAttention.

## V5S: Weights through the stack pointer

`pop bc` reads two weights in 12 T-cycles and keeps both in registers, so each is loaded once. Per-MAC cost fell from 253 to 232. Interrupts are held off for one row at a time and nothing is ever pushed while SP points into ROM. Since a VBlank can now start late, the ISR checks LY before touching VRAM or OAM and leaves dirty rows for the next frame. The cost is that screen updates can lag by a few frames during inference; nothing is corrupted. The size of that lag wasn't measured.

**Caveat:** Elyan Labs warn about this technique under active interrupts, and their SP kernel is unverified on hardware. Ours passes on SameBoy but hasn't run on a physical DMG either.

## V5Z: Zero-column skip

58.1% of `f` is exactly zero after ReLU, measured across all situations on the reference (`tools/sparsity_study.py`). Each block in the 64-wide kernel now tests for the biased zero first. Dense vectors get slower (213 to 227 T-cycles per MAC on the dense microbenchmark) while real inference gets faster, because real activations are sparse. Only the 64-wide kernel pays for the test.

## Where the time goes now

| Phase | V0 | V5Z |
|---|---:|---:|
| Keys and values | 63.9% | 19.5% |
| Query | 2.8% | 7.6% |
| Attention | 2.4% | 7.1% |
| Projection and norm | 2.9% | 8.6% |
| Feed-forward and norm | 11.1% | 24.5% |
| Output logits | 16.8% | 31.9% |
| Token decode | 0.1% | 0.7% |

The output layer is now the largest phase, because the larger vocabulary means 141 rows per token. That's the direct cost of the richer story.

## Precision study (V6)

Studied on the reference only, with no ROM built and no retraining. Weights rounded to 5 bits stayed 100% strict-valid on this checkpoint, with 87.1% token agreement with the 8-bit model. At 4 bits validity fell to 71%, and at 3 bits to 0%. Packing to 5 bits would save an estimated 5.4 KB but needs an unpack step, and it wouldn't be faster with these kernels. Since this ROM has room, it wasn't worth building. A lower-precision result is not an output-identical speed claim: its tokens differ.

## Not attempted

V7 (ternary or codebook weights) and V8 (automatic configuration search).

## Ideas with measured motivation

The output layer is the largest cost, and at each position most words are impossible by grammar. A finite-state mask could prune many rows, but it would change which tokens can be chosen, so it would need its own reference and quality gates. Compiling weights into per-row code might also be substantially faster at the price of hundreds of KB of ROM; that's an untested estimate.
