#!/usr/bin/env python3
"""Quantize a checkpoint into the versioned model blob, RGBDS tensors and word strings.

Blob header: magic "GBGT", format_version, then a JSON-free tensor table
(name[8], rows u16, cols u16, shift u8), then row-major int8 data, then sha256 of everything before it.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import torch
from training import dataset as ds
from training.model import weight_shift
from reference.fixed_point import IntModel

FORMAT_VERSION = 1
MAGIC = b"GBGT"
TENSORS = ("tok", "pos", "w_q", "w_k", "w_v", "w_o", "w_f1", "w_f2", "w_out")
SAMPLE_MARGIN_REAL = 0.7  # logits within this many nats of the best are candidates


def _q(t: torch.Tensor, shift: int) -> list[list[int]]:
    v = (t * (1 << shift)).round().clamp(-127, 127).to(torch.int64)
    return v.tolist()


def quantize(ckpt_path: Path) -> IntModel:
    ck = torch.load(ckpt_path, weights_only=False)
    st, c = ck["state"], ck["model"]
    assert c["layers"] == 1, "the SM83 engine implements one block"
    block = "blocks.0."
    raw = {"w_q": st[block + "q.w"], "w_k": st[block + "k.w"], "w_v": st[block + "v.w"], "w_o": st[block + "o.w"],
           "w_f1": st[block + "f1.w"], "w_f2": st[block + "f2.w"], "w_out": st["out.w"]}
    shifts = {k: weight_shift(v) for k, v in raw.items()}
    q = {k: tuple(map(tuple, _q(v, shifts[k]))) for k, v in raw.items()}
    margin = round(SAMPLE_MARGIN_REAL * (1 << shifts["w_out"]))  # logit = Sum>>4, so one nat is 2^s_out units
    return IntModel(d=c["d"], heads=c["heads"], ctx=c["ctx"], first_gen=ds.FIRST_GEN, eos=ds.EOS, sample_margin=margin,
                    tok=tuple(map(tuple, _q(st["tok"], 4))), pos=tuple(map(tuple, _q(st["pos"], 4))),
                    **q, **{"s_" + k[2:]: v for k, v in shifts.items()})


def to_blob(m: IntModel) -> bytes:
    body = bytearray(MAGIC + struct.pack("<HBBBBBB", FORMAT_VERSION, m.d, m.heads, m.ctx, m.first_gen, m.eos, len(TENSORS)))
    body += struct.pack("<H", m.sample_margin)
    data = bytearray()
    for name in TENSORS:
        t = getattr(m, name)
        shift = 4 if name in ("tok", "pos") else getattr(m, "s_" + name[2:])
        body += name.encode().ljust(8, b"\0") + struct.pack("<HHB", len(t), len(t[0]), shift)
        for row in t:
            data += bytes(v & 0xFF for v in row)
    payload = bytes(body + data)
    return payload + hashlib.sha256(payload).digest()


def from_blob(blob: bytes) -> IntModel:
    payload, digest = blob[:-32], blob[-32:]
    if hashlib.sha256(payload).digest() != digest:
        raise ValueError("model blob checksum mismatch")
    if payload[:4] != MAGIC:
        raise ValueError("bad magic")
    ver, d, heads, ctx, first_gen, eos, n = struct.unpack_from("<HBBBBBB", payload, 4)
    if ver != FORMAT_VERSION:
        raise ValueError(f"unsupported format {ver}")
    margin = struct.unpack_from("<H", payload, 12)[0]
    off, table = 14, []
    for _ in range(n):
        name = payload[off:off + 8].rstrip(b"\0").decode()
        rows, cols, shift = struct.unpack_from("<HHB", payload, off + 8)
        table.append((name, rows, cols, shift))
        off += 13
    fields, shifts = {}, {}
    for name, rows, cols, shift in table:
        fields[name] = tuple(tuple(b - 256 if b > 127 else b for b in payload[off + r * cols : off + (r + 1) * cols]) for r in range(rows))
        off += rows * cols
        shifts[name] = shift
    return IntModel(d=d, heads=heads, ctx=ctx, first_gen=first_gen, eos=eos, sample_margin=margin, **fields,
                    **{"s_" + k[2:]: v for k, v in shifts.items() if k.startswith("w_")})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=str(ROOT / "checkpoints" / "release.pt"))
    ap.add_argument("--out", default=str(ROOT / "generated" / "model.bin"))
    a = ap.parse_args()
    m = quantize(Path(a.ckpt))
    blob = to_blob(m)
    Path(a.out).parent.mkdir(exist_ok=True)
    Path(a.out).write_bytes(blob)
    assert from_blob(blob) == m
    sha = hashlib.sha256(blob).hexdigest()
    print(f"blob {len(blob)} bytes sha256 {sha}")
    print({k: getattr(m, k) for k in ("s_q", "s_k", "s_v", "s_o", "s_f1", "s_f2", "s_out", "sample_margin")})


if __name__ == "__main__":
    main()
