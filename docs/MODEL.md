# Model

A decoder-only causal transformer, trained offline with PyTorch and run in SM83 assembly from int8 weights in cartridge ROM.

| Parameter | Value |
|---|---|
| Layers | 1 |
| Hidden size `d` | 32 |
| Heads | 2 (width 16 each) |
| FFN width | 64 |
| Context | 16 tokens |
| Vocabulary | 95 tokens (see below) |
| Parameters | 14,784 int8 |

Vocabulary: 1 `<BOS>`, 8 rooms, 3 inventory codes, 4 actions, 11 outcomes, `<EOS>`, then 67 words.

## Forward pass for the last position `t`

| Step | Equation | Shape |
|---|---|---|
| Embed | `e[j] = sat8(tok[id[j]] + pos[j])` | 32 |
| Norm | `n[j] = norm(e[j])` | 32 |
| Keys, values | `K[j] = W_k n[j]`, `V[j] = W_v n[j]` | 32 each, split into 2 x 16 |
| Query | `q = W_q n[t]` | 32, split into 2 x 16 |
| Attention | `a = concat(attend(q_h, K[0..t]_h, V[0..t]_h))` | 32 |
| Residual | `x = sat8(e[t] + W_o a)` | 32 |
| Feed-forward | `x2 = sat8(x + W_f2 relu(W_f1 norm(x)))` | 64 inside, 32 out |
| Output | `logits = W_out norm(x2)` | 95 |

Exact rounding is in [NUMERICS.md](NUMERICS.md). Layers have no biases.

**Deviations from a textbook transformer, and why:** mean-absolute normalization instead of LayerNorm (no sqrt or division), a lookup-based softmax substitute (no exp or division), ReLU, untied output weights. Attention is real: scores depend on token-dependent queries and keys computed at runtime.

## Data and what the model is asked to do

Input is a symbolic prompt: `<BOS> ROOM INV ACT OUT`. The deterministic engine has already decided the outcome, so the model narrates what happened and can't change it. It continues with up to 10 words plus `<EOS>`.

Training sentences come from a grammar in `training/dataset.py` that composes an action clause, an outcome clause, room nouns, adjectives and inventory phrases. A sampled event looks like:

```
<BOS> <R_CAVE> <I_LAMP> <A_FORWARD> <O_MOVE>  ->  YOU PRESS ON AND YOUR LAMP SHOWS SILENT BATS
```

**At display time the only changes are a final full stop on `<EOS>` and a capital first letter.** Every word on screen is a token the model chose. Tokens are shown in lowercase, and the examples here use the uppercase vocabulary names. The title, intro lines, menu labels, goal hint and win/lose banners are static UI assets, not generated. The language is deliberately narrow: this is a grammar-learning model and not a general language model.

## Splits

Held-out data are withheld *situations* `(room, inventory, action, outcome)`, never seen in training with any wording. Six families are for validation and nine for test. Nearly all held-out situations are novel combinations of parts the model saw separately. `tools/generalization_study.py` runs a harder test with a fresh model that never sees 40% of all situations.

## Training

AdamW, gradient clipping at 1.0, cosine decay, 12,000 float steps then 8,000 quantization-aware steps with straight-through fake quantization that mirrors the integer rules. The checkpoint is selected by quantized validation NLL. Seeds are fixed and training runs single-threaded on CPU, because multithreaded runs produced different weights on the same seed. See `configs/release.yaml`.

A smaller candidate (d=16, 1 head, FFN 32, 5,344 params) reached similar NLL and also generated grammar-valid text on the reference. The d=32 model shipped because it met the spec's release target and the measured latency allowed it. The smaller model's on-device latency was not measured. Two layers would not have gained validity since one layer already reaches the limit of this test, so they were not pursued.

## Export

`tools/export_weights.py` writes `generated/model.bin`: magic `GBGT`, format version, geometry, a tensor table (name, rows, cols, shift), row-major int8 data, and a SHA-256 of everything before it. `from_blob` rejects a bad checksum, magic, or version. `tools/rom_layout.py` turns it into RGBDS data for a chosen layout. The ROM's own weight bytes are audited against the blob in `tests/test_generated_output.py`.
