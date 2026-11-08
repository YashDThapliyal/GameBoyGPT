# Numeric contract

`reference/fixed_point.py` is the executable form of this document. It uses plain Python integers and shares no code with the trainer or the assembly. The SM83 kernels must match it bit for bit, and tests enforce that.

## Value ranges

Every weight and activation is an int8 in **[-127, 127]**. -128 never occurs, so `|x|` always fits in 7 bits and one signed multiply serves every op.

| Tensor | Format | Notes |
|---|---|---|
| Activations | Q4 (scale 1/16) | Range about +-7.9 |
| Embeddings `tok`, `pos` | Q4 | Added with saturation |
| Weights `w_*` | Per-tensor power of two `2^-s`, `s` in 0..7 | `s` is the largest value where `max|w| * 2^s <= 127` |
| Attention weights | Q7 unsigned, 0..127 | Sum is about 128 |
| Logits | int16 | Compared only with each other |

## Primitives

`rshift_round(v, s) = (v + (1 << (s-1))) >> s`, an arithmetic shift, so ties round up (towards +infinity). `s = 0` returns `v`.

`sat8(v)` clamps to [-127, 127].

`matvec(W, x, s)`: `y[i] = sat8(rshift_round(sum W[i][j] * x[j], s))`. Accumulators are 24-bit. The worst case is 64 x 127 x 127 = 1,032,256, well below 2^23, and `tests/test_export.py` checks this.

`add_sat(a, b)`: `sat8(a[i] + b[i])`.

## Normalization

Mean-absolute normalization replaces LayerNorm or RMSNorm because it needs no square root and no division at runtime:

```
m = (sum |x[i]| + d/2) >> log2(d)     d = 32
g = NormLut[m]                        NormLut[m] = min(127, round(512 / max(m, 1)))
x'[i] = sat8((x[i] * g + 16) >> 5)
```

This targets a mean magnitude of 16, which is 1.0 in Q4. The trainer uses the same rule under quantization-aware training, so the weights were trained for this operation rather than converted to it.

## Attention

For one query `q` over positions `j <= t`, per head of width 16:

```
s[j] = sat8(rshift_round(q . k[j], 6))
top  = max s[j]
w[j] = ExpLut[top - s[j]]  if top - s[j] < 128, else 0       ExpLut[d] = round(127 * exp(-d / 16))
r    = RecipLut[(sum w[j]) >> 4]                             RecipLut[i] = min(127, round(2^14 / (16i + 8)))
w'[j] = (w[j] * r + 64) >> 7
a[i] = sat8(rshift_round(sum w'[j] * v[j][i], 7))
```

- **What this is:** scaled dot-product attention with softmax replaced by a max-subtract exponential lookup and reciprocal normalization. It is not numerically equal to floating-point softmax.
- **Zero guard:** the maximum score always contributes `ExpLut[0] = 127`, so the sum is at least 127 and never zero.
- **Causality:** only `j <= t` are visited; there are no later tokens in the sequence during autoregressive generation.

## Output and decoding

```
logit[i] = rshift_round(W_out[i] . n3, 4)
```

The worst case fits in int16.

- **Mask:** only ids from `<EOS>` onward can be generated. Control tokens never appear in output.
- **Greedy:** the highest logit; ties resolve to the lowest id.
- **Sampling:** uniform over the first 4 ids (in id order) within `sample_margin` of the best logit. The margin is 0.7 nats, converted to logit units at export. The RNG is a 16-bit Galois LFSR with taps `$B400`, advanced 8 bits per pick, separate from the world's RNG so narration can't alter game truth.
- **Cap:** generation stops at context 24. An event that reaches the cap without `<EOS>` is counted in `wMB_Fallbacks`, which is visible on the stats screen as `Capped`.

## Output-preserving optimizations

Each of these changes how a value is computed, never the value. All are checked against the same reference.

| Optimization | Why the result is identical |
|---|---|
| Quarter-square multiply | `ab = floor((a+b)^2/4) - floor((a-b)^2/4)` holds for all integers, because `a+b` and `a-b` have the same parity |
| Biased inputs | `x + 128` and `w + 128` only make the 9-bit sum's carry select a table page |
| Output pruning | Masked rows can't affect masked argmax or sampling. Tests compare only masked logits |
| K/V cache | `K[j]` and `V[j]` depend only on token `j` and position `j` in a one-layer model |
| Sparse aggregation | `w' = 0` contributes nothing. The 16-bit accumulators are safe because the sum of `w'` is bounded (`tests/test_export.py`) |
| Zero-column skip | `x = 0` makes every product in that column 0 |
| SP stream | Reads the same bytes in the same order |
