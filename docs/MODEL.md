# Model

A decoder-only causal transformer, trained offline with PyTorch and run in SM83 assembly from int8 weights in cartridge ROM.

| Parameter | Value |
|---|---|
| Layers | 1 |
| Hidden size `d` | 32 |
| Heads | 2 (width 16 each) |
| FFN width | 64 |
| Context | 24 tokens |
| Vocabulary | 196 tokens (see below) |
| Parameters | 21,504 int8 |

Vocabulary: 1 `<BOS>`, the event tokens, one token per reachable combination of carried items, 2 fate tokens, `<EOS>`, then 141 words.

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
| Output | `logits = W_out norm(x2)` | 196 |

Exact rounding is in [NUMERICS.md](NUMERICS.md). Layers have no biases.

**Deviations from a textbook transformer, and why:** mean-absolute normalization instead of LayerNorm (no sqrt or division), a lookup-based softmax substitute (no exp or division), ReLU, untied output weights. Attention is real: scores depend on token-dependent queries and keys computed at runtime.

## Data and what the model is asked to do

Input is a symbolic prompt: `<BOS> EVENT ITEMS FATE`. The deterministic story engine has already decided what happened, so the model narrates it and can't change it. It continues with up to 19 tokens plus `<EOS>`.

Training sentences come from `training/dataset.py`, which pairs a line about what just happened with the arrival text of the next scene. A sampled event looks like:

```
<BOS> <B_LIGHT_LAMP> <F_1> <LIVE>  ->  YOUR LAMP SHOWS A HIDDEN DOOR . LOOK . THE CHEST HAS TEETH .
```

- **The items change the words:** with the lamp the arrival opens "Look.", and with a friend "He warns."
- **Danger is in the text:** the arrival line is the omen for that scene's dangerous choice.
- **Wording varies:** synonym slots give each situation several valid wordings, and near-top sampling picks among them.

**At display time the only change is capital letters at sentence starts.** Every word and full stop on screen is a token the model chose. Tokens are shown in lowercase. The title, intro lines, place names, choice labels and ending names are static UI assets, not generated.

**What this is not.** The plot and the sentences are authored. The model learned this language; it doesn't invent story. "Coherence" here comes from the authored structure and a model reliable enough to reproduce it.

## Splits

There are two models, because a shipping model should know every line while a generalization test must not.

- **Shipping model** (`configs/release.yaml`): trained on every reachable situation. It must be strict-valid on all of them.
- **Sibling model** (`configs/heldout.yaml`): identical recipe, with 32 situations withheld. Each is a known event with a combination of items never seen with that event. It is measured and never shipped.

## Training

AdamW, gradient clipping at 1.0, cosine decay, 20,000 float steps then 12,000 quantization-aware steps with straight-through fake quantization that mirrors the integer rules. The checkpoint is selected by quantized validation NLL. Seeds are fixed and training runs single-threaded on CPU, because multithreaded runs produced different weights on the same seed.

**Why this size.** The width stayed at 32 and the depth at one layer, because the first candidate at that size reached 98.6% strict validity greedy on the new language and more training closed the gap. Growth went only where the task needed it: a larger vocabulary and longer context. A second layer would also have needed engine work and more time per word, so it wasn't pursued.

## Export

`tools/export_weights.py` writes `generated/model.bin`: magic `GBGT`, format version, geometry, a tensor table (name, rows, cols, shift), row-major int8 data, and a SHA-256 of everything before it. `from_blob` rejects a bad checksum, magic, or version. `tools/rom_layout.py` turns it into RGBDS data for a chosen layout. The ROM's own weight bytes are audited against the blob in `tests/test_generated_output.py`.
