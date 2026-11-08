"""Independent, bit-exact integer reference of the Game Boy inference contract (docs/NUMERICS.md).

Pure-Python integers only; no torch or numpy, so it cannot silently share behaviour with the trainer.
Every activation and weight is in [-127, 127]. All functions are pure and return new lists.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

ATTN_SHIFT = 6
LOGIT_SHIFT = 4
NORM_SHIFT = 5
W_SHIFT = 7
SAMPLE_CANDIDATES = 4
EXP_LUT = tuple(round(127 * math.exp(-d / 16)) for d in range(128))
RECIP_LUT = tuple(min(127, round(2 ** 14 / (8 * i + 4))) for i in range(256))
NORM_LUT = tuple(min(127, round(512 / max(m, 1))) for m in range(128))


def sat8(v: int) -> int:
    return -127 if v < -127 else 127 if v > 127 else v


def rshift_round(v: int, s: int) -> int:
    """Round-half-up arithmetic shift. Python's >> floors, which is what the SM83 sign-extended shift does."""
    return (v + (1 << (s - 1))) >> s if s > 0 else v


def dot(a, b) -> int:
    return sum(x * y for x, y in zip(a, b, strict=True))


def matvec(w, x, shift: int) -> list[int]:
    return [sat8(rshift_round(dot(row, x), shift)) for row in w]


def add_sat(a, b) -> list[int]:
    return [sat8(x + y) for x, y in zip(a, b, strict=True)]


def norm(x) -> list[int]:
    d = len(x)
    log2d = d.bit_length() - 1
    assert 1 << log2d == d, "norm requires a power-of-two width"
    m = (sum(abs(v) for v in x) + (d >> 1)) >> log2d
    g = NORM_LUT[m]
    return [sat8((v * g + (1 << (NORM_SHIFT - 1))) >> NORM_SHIFT) for v in x]


def attention_weights(scores) -> list[int]:
    top = max(scores)
    raw = [EXP_LUT[top - s] if top - s < 128 else 0 for s in scores]
    r = RECIP_LUT[sum(raw) >> 3]
    return [(w * r + (1 << (W_SHIFT - 1))) >> W_SHIFT for w in raw]


def attend(q, keys, values) -> list[int]:
    """One head for one query over j<=t: scores, normalized weights, value aggregation."""
    scores = [sat8(rshift_round(dot(q, k), ATTN_SHIFT)) for k in keys]
    weights = attention_weights(scores)
    width = len(q)
    return [sat8(rshift_round(sum(w * v[i] for w, v in zip(weights, values)), W_SHIFT)) for i in range(width)]


def relu(x) -> list[int]:
    return [max(0, v) for v in x]


@dataclass(frozen=True)
class IntModel:
    """Quantized weights: int lists plus each tensor's right shift (its fractional bits)."""
    d: int
    heads: int
    ctx: int
    first_gen: int
    eos: int
    sample_margin: int
    tok: tuple
    pos: tuple
    w_q: tuple
    w_k: tuple
    w_v: tuple
    w_o: tuple
    w_f1: tuple
    w_f2: tuple
    w_out: tuple
    s_q: int
    s_k: int
    s_v: int
    s_o: int
    s_f1: int
    s_f2: int
    s_out: int

    @property
    def head_dim(self) -> int:
        return self.d // self.heads


def embed(m: IntModel, tok: int, pos: int) -> list[int]:
    return add_sat(m.tok[tok], m.pos[pos])


def key_value(m: IntModel, n) -> tuple[list[int], list[int]]:
    return matvec(m.w_k, n, m.s_k), matvec(m.w_v, n, m.s_v)


def step(m: IntModel, tokens: list[int]) -> tuple[list[int], dict]:
    """Forward pass for the last position, recomputing all keys and values. Returns logits and tensors."""
    es = [embed(m, t, p) for p, t in enumerate(tokens)]
    ns = [norm(e) for e in es]
    kv = [key_value(m, n) for n in ns]
    q = matvec(m.w_q, ns[-1], m.s_q)
    hd = m.head_dim
    a: list[int] = []
    for h in range(m.heads):
        lo, hi = h * hd, (h + 1) * hd
        a += attend(q[lo:hi], [k[lo:hi] for k, _ in kv], [v[lo:hi] for _, v in kv])
    o = matvec(m.w_o, a, m.s_o)
    x = add_sat(es[-1], o)
    n2 = norm(x)
    f = relu(matvec(m.w_f1, n2, m.s_f1))
    o2 = matvec(m.w_f2, f, m.s_f2)
    x2 = add_sat(x, o2)
    n3 = norm(x2)
    logits = [rshift_round(dot(row, n3), LOGIT_SHIFT) for row in m.w_out]
    return logits, {"e": es[-1], "n": ns[-1], "q": q, "k": kv[-1][0], "v": kv[-1][1], "a": a, "o": o, "x": x,
                    "n2": n2, "f": f, "o2": o2, "x2": x2, "n3": n3}


def argmax_masked(m: IntModel, logits) -> int:
    best = m.first_gen
    for i in range(m.first_gen, len(logits)):
        if logits[i] > logits[best]:  # strict: ties resolve to the lowest id
            best = i
    return best


def rng_byte(state: int) -> tuple[int, int]:
    for _ in range(8):
        lsb = state & 1
        state >>= 1
        if lsb:
            state ^= 0xB400
    return state, state & 0xFF


def sample_masked(m: IntModel, logits, rng: int) -> tuple[int, int]:
    """Near-top sampling: uniform over the first SAMPLE_CANDIDATES ids within sample_margin of the best."""
    top = logits[argmax_masked(m, logits)]
    cands = [i for i in range(m.first_gen, len(logits)) if logits[i] >= top - m.sample_margin][:SAMPLE_CANDIDATES]
    rng, b = rng_byte(rng)
    return cands[b % len(cands)], rng


def generate(m: IntModel, prompt: list[int], greedy: bool = True, rng: int = 1) -> dict:
    """Autoregressive generation up to the context limit. A capped event is reported, never hidden."""
    tokens, trace = list(prompt), []
    capped = True
    while len(tokens) < m.ctx:
        logits, _ = step(m, tokens)
        trace.append(sum(logits[m.first_gen:]) & 0xFFFF)
        if greedy:
            t = argmax_masked(m, logits)
        else:
            t, rng = sample_masked(m, logits, rng)
        if t == m.eos:
            capped = False
            tokens.append(t)
            break
        tokens.append(t)
    return {"tokens": tokens, "generated": tokens[len(prompt):], "capped": capped, "logit_sums": trace, "rng": rng}
