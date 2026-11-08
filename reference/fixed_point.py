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
SAMPLE_CANDIDATES = 12
EXP_LUT = tuple(round(127 * math.exp(-d / 16)) for d in range(128))
RECIP_LUT = tuple(min(127, round(2 ** 14 / (16 * i + 8))) for i in range(256))
RECIP_SHIFT = 4  # 32 positions x 127 fits an 8-bit index after this shift
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
    r = RECIP_LUT[sum(raw) >> RECIP_SHIFT]
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
    """Quantized weights: int lists plus each tensor's right shift (its fractional bits).

    Token ids: [prompt tokens] [8 emotions] EOS [slots] [punctuation] [words]. w_b is the output bottleneck."""
    d: int
    heads: int
    ctx: int
    first_emotion: int
    eos: int
    first_word: int
    sample_margin: int
    rep_penalty: int
    tok: tuple
    pos: tuple
    w_q: tuple
    w_k: tuple
    w_v: tuple
    w_o: tuple
    w_f1: tuple
    w_f2: tuple
    w_b: tuple
    w_out: tuple
    s_q: int
    s_k: int
    s_v: int
    s_o: int
    s_f1: int
    s_f2: int
    s_b: int
    s_out: int

    @property
    def head_dim(self) -> int:
        return self.d // self.heads

    @property
    def vocab(self) -> int:
        return len(self.w_out)

    @property
    def num_emotions(self) -> int:
        return self.eos - self.first_emotion

    @property
    def params(self) -> int:
        tensors = (self.tok, self.pos, self.w_q, self.w_k, self.w_v, self.w_o, self.w_f1, self.w_f2, self.w_b, self.w_out)
        return sum(len(t) * len(t[0]) for t in tensors)


def embed(m: IntModel, tok: int, pos: int) -> list[int]:
    return add_sat(m.tok[tok], m.pos[pos])


def key_value(m: IntModel, n) -> tuple[list[int], list[int]]:
    return matvec(m.w_k, n, m.s_k), matvec(m.w_v, n, m.s_v)


def allowed_rows(m: IntModel, generated_count: int) -> range:
    """The first generated token is an emotion; every later token is EOS, a slot or a word."""
    return range(m.first_emotion, m.eos) if generated_count == 0 else range(m.eos, m.vocab)


class Cache:
    """K and V of past positions. They depend only on token and position, so the result equals a full recompute."""

    def __init__(self):
        self.kv: list[tuple[list[int], list[int]]] = []


def step(m: IntModel, tokens: list[int], cache: Cache | None = None) -> tuple[list[int], dict]:
    """Forward pass for the last position. Returns logits for every row and the intermediate tensors."""
    cache = cache if cache is not None else Cache()
    while len(cache.kv) < len(tokens):
        p = len(cache.kv)
        cache.kv.append(key_value(m, norm(embed(m, tokens[p], p))))
    e = embed(m, tokens[-1], len(tokens) - 1)
    n = norm(e)
    kv = cache.kv[:len(tokens)]
    q = matvec(m.w_q, n, m.s_q)
    hd = m.head_dim
    a: list[int] = []
    for h in range(m.heads):
        lo, hi = h * hd, (h + 1) * hd
        a += attend(q[lo:hi], [k[lo:hi] for k, _ in kv], [v[lo:hi] for _, v in kv])
    o = matvec(m.w_o, a, m.s_o)
    x = add_sat(e, o)
    n2 = norm(x)
    f = relu(matvec(m.w_f1, n2, m.s_f1))
    o2 = matvec(m.w_f2, f, m.s_f2)
    x2 = add_sat(x, o2)
    n3 = norm(x2)
    z = matvec(m.w_b, n3, m.s_b)
    logits = [rshift_round(dot(row, z), LOGIT_SHIFT) for row in m.w_out]
    return logits, {"e": e, "n": n, "q": q, "k": kv[-1][0], "v": kv[-1][1], "a": a, "o": o, "x": x, "n2": n2, "f": f, "o2": o2, "x2": x2, "n3": n3, "z": z}


def penalized(m: IntModel, logits: list[int], generated: list[int]) -> list[int]:
    """Repetition control: each earlier use of a word lowers its score. Punctuation, slots and control tokens are exempt."""
    out = list(logits)
    for t in generated:
        if t >= m.first_word:
            out[t] -= m.rep_penalty
    return out


def argmax_range(logits, rows: range) -> int:
    best = rows[0]
    for i in rows:
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


def sample_range(m: IntModel, logits, rows: range, rng: int) -> tuple[int, int]:
    """Softmax sampling at temperature 1 over the first candidates within sample_margin of the best.

    Each candidate weighs ExpLut[(best - logit) * 16 >> s_out], the same exponential attention uses."""
    top = logits[argmax_range(logits, rows)]
    cands = [i for i in rows if logits[i] >= top - m.sample_margin][:SAMPLE_CANDIDATES]
    weights = [EXP_LUT[sample_index(m, top - logits[i])] for i in cands]
    rng, b = rng_byte(rng)
    pick = (b * sum(weights)) >> 8
    for c, w in zip(cands, weights):
        if pick < w:
            return c, rng
        pick -= w
    raise AssertionError("pick is always below the sum of the weights")


def sample_index(m: IntModel, delta: int) -> int:
    return min(127, (delta >> (m.s_out - 4)) if m.s_out >= 4 else (delta << (4 - m.s_out)))


def generate(m: IntModel, prompt: list[int], greedy: bool = True, rng: int = 1) -> dict:
    """Autoregressive generation up to the context limit. A capped response is reported, never hidden."""
    tokens, trace, generated = list(prompt), [], []
    cache = Cache()
    capped = True
    while len(tokens) < m.ctx:
        logits, _ = step(m, tokens, cache)
        rows = allowed_rows(m, len(generated))
        trace.append(sum(logits[i] for i in rows) & 0xFFFF)
        adjusted = penalized(m, logits, generated)
        if greedy:
            t = argmax_range(adjusted, rows)
        else:
            t, rng = sample_range(m, adjusted, rows, rng)
        tokens.append(t)
        generated.append(t)
        if t == m.eos:
            capped = False
            break
    return {"tokens": tokens, "generated": generated, "capped": capped, "logit_sums": trace, "rng": rng}
