"""Exporter contract: real weights, checksummed blob, every shift in range, geometry as documented."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import json
from export_weights import from_blob, to_blob, quantize
from reference import fixed_point as fp
from training import dataset as ds

BLOB = ROOT / "generated" / "model.bin"


def test_committed_blob_matches_the_committed_checkpoint():
    assert from_blob(BLOB.read_bytes()) == quantize(ROOT / "checkpoints" / "release.pt")


def test_geometry_and_parameter_count_match_the_on_screen_claim():
    m = from_blob(BLOB.read_bytes())
    fields = ("tok", "pos", "w_q", "w_k", "w_v", "w_o", "w_f1", "w_f2", "w_out")
    params = sum(len(getattr(m, f)) * len(getattr(m, f)[0]) for f in fields)
    assert f"Model: {params} params" in (ROOT / "generated" / "V0" / "luts.asm").read_text()
    assert (m.d, m.heads, m.head_dim, m.ctx) == (32, 2, 16, ds.CTX)
    assert len(m.w_out) == len(ds.VOCAB) and m.eos == ds.EOS == m.first_gen


def test_all_weights_in_multiply_range():
    m = from_blob(BLOB.read_bytes())
    for f in ("tok", "pos", "w_q", "w_k", "w_v", "w_o", "w_f1", "w_f2", "w_out"):
        assert all(-127 <= v <= 127 for row in getattr(m, f) for v in row), f
    for s in (m.s_q, m.s_k, m.s_v, m.s_o, m.s_f1, m.s_f2, m.s_out):
        assert 0 <= s <= 7


def test_accumulators_cannot_overflow_their_stated_width():
    worst_dot = 64 * 127 * 127
    assert worst_dot + (1 << 6) < 1 << 23, "24-bit accumulator"
    assert (32 * 127 * 127 + 8) >> fp.LOGIT_SHIFT < 1 << 15, "int16 logits"
    # Sparse aggregation uses 16-bit accumulators: bound sum(w') over every reachable raw-weight sum.
    worst = 0
    for s in range(127, 127 * ds.CTX + 1):
        r = fp.RECIP_LUT[s >> fp.RECIP_SHIFT]
        # sum of (w*r+64)>>7 is at most (s*r + 64*CTX) / 128
        worst = max(worst, (s * r + 64 * ds.CTX) // 128)
    assert worst * 127 + 64 < 1 << 15, worst
