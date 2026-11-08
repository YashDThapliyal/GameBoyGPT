"""PyTorch training model mirroring the integer contract in reference/fixed_point.py (docs/NUMERICS.md).

With quant=False: float forward used for early training. With quant=True: straight-through fake
quantization of every activation, matching the integer rounding and saturation rules.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import torch
import torch.nn as nn
import torch.nn.functional as F

ACT_ONE = 16.0   # activations are int8 Q4
NORM_NUM = 512.0  # gain g = 512 / mean|x|, x' = x * g >> 5
ATTN_SHIFT = 6


@dataclass(frozen=True)
class Config:
    vocab: int = 95
    ctx: int = 16
    d: int = 32
    heads: int = 2
    ffn: int = 64
    layers: int = 1
    k: int = 0  # output bottleneck width; 0 means a full vocab x d head

    def as_dict(self):
        return asdict(self)


def ste_round(x):
    return x + (torch.round(x) - x).detach()


def fq_act(x):
    """Quantize to int8 Q4 with symmetric saturation, preserving gradients."""
    return ste_round(x * ACT_ONE).clamp(-127, 127) / ACT_ONE


def weight_shift(w: torch.Tensor) -> int:
    """Largest fractional bit count such that max|w| fits in +-127 (0..7). Shared with the exporter."""
    m = float(w.detach().abs().max())
    for s in range(7, -1, -1):
        if m * (1 << s) <= 127.0:
            return s
    return 0


def fq_weight(w):
    s = 1 << weight_shift(w)
    return ste_round(w * s).clamp(-127, 127) / s


class Linear(nn.Module):
    def __init__(self, n_in, n_out):
        super().__init__()
        self.w = nn.Parameter(torch.empty(n_out, n_in))
        nn.init.normal_(self.w, std=1.0 / n_in ** 0.5)

    def forward(self, x, quant):
        w = fq_weight(self.w) if quant else self.w
        return x @ w.T


def norm(x, quant):
    """Mean-absolute normalization: the integer-friendly stand-in for RMSNorm (no sqrt or divide)."""
    if not quant:
        m = x.abs().mean(-1, keepdim=True) * ACT_ONE
        return x * (NORM_NUM / m.clamp(min=NORM_NUM / 127)) / 32.0
    m = ste_round(x.abs().mean(-1, keepdim=True) * ACT_ONE)
    g = ste_round(NORM_NUM / m.clamp(min=1.0)).clamp(max=127.0)
    return fq_act(x * g / 32.0)


class Block(nn.Module):
    def __init__(self, c: Config):
        super().__init__()
        self.c = c
        self.q, self.k, self.v = Linear(c.d, c.d), Linear(c.d, c.d), Linear(c.d, c.d)
        self.o = Linear(c.d, c.d)
        self.f1, self.f2 = Linear(c.d, c.ffn), Linear(c.ffn, c.d)
        self.register_buffer("mask", torch.tril(torch.ones(c.ctx, c.ctx, dtype=torch.bool)))

    def forward(self, x, quant):
        B, T, D = x.shape
        act = fq_act if quant else (lambda t: t)
        c = self.c
        h = norm(x, quant)
        split = lambda t: t.view(B, T, c.heads, D // c.heads).transpose(1, 2)
        q, k, v = (split(act(l(h, quant))) for l in (self.q, self.k, self.v))
        qk = q @ k.transpose(-1, -2)  # real units; integer form sums q*k in Q8
        if quant:
            s = ste_round(qk * 256.0 / (1 << ATTN_SHIFT)).clamp(-127, 127)
        else:
            s = qk * 256.0 / (1 << ATTN_SHIFT)
        s = s.masked_fill(~self.mask[:T, :T], float("-inf"))
        w = F.softmax(s / 16.0, dim=-1)
        if quant:
            w = ste_round(w * 128.0) / 128.0
        a = act((w @ v).transpose(1, 2).reshape(B, T, D))
        x = act(x + act(self.o(a, quant)))
        n2 = norm(x, quant)
        f = F.relu(act(self.f1(n2, quant)))
        return act(x + act(self.f2(f, quant)))


class TinyTransformer(nn.Module):
    def __init__(self, c: Config):
        super().__init__()
        self.c = c
        self.tok = nn.Parameter(torch.randn(c.vocab, c.d) * 1.0)
        self.pos = nn.Parameter(torch.randn(c.ctx, c.d) * 0.5)
        self.blocks = nn.ModuleList(Block(c) for _ in range(c.layers))
        self.bottleneck = Linear(c.d, c.k) if c.k else None
        self.out = Linear(c.k or c.d, c.vocab)

    def forward(self, idx, quant=False):
        T = idx.shape[1]
        emb = lambda p: (ste_round(p * ACT_ONE).clamp(-127, 127) / ACT_ONE) if quant else p
        x = emb(self.tok)[idx] + emb(self.pos)[:T]
        x = fq_act(x) if quant else x
        for b in self.blocks:
            x = b(x, quant)
        z = norm(x, quant)
        if self.bottleneck is not None:
            z = self.bottleneck(z, quant)
            z = fq_act(z) if quant else z
        return self.out(z, quant)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())


class GruLm(nn.Module):
    """Comparison only, trained in float: a recurrent model has no attention or context cost, but the Game Boy engine does not implement it."""

    def __init__(self, vocab: int, d: int, k: int):
        super().__init__()
        self.tok = nn.Embedding(vocab, d)
        self.gru = nn.GRU(d, d, batch_first=True)
        self.bottleneck = nn.Linear(d, k)
        self.out = nn.Linear(k, vocab)

    def forward(self, idx, quant=False):
        h, _ = self.gru(self.tok(idx))
        return self.out(torch.relu(self.bottleneck(h)))

    def num_params(self):
        return sum(p.numel() for p in self.parameters())
