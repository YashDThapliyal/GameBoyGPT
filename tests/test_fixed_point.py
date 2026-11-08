"""Hand-computed contract checks for the integer reference, plus blob round trip and determinism."""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from reference import fixed_point as fp
from export_weights import quantize, to_blob, from_blob
from training import dataset as ds


@pytest.mark.parametrize("v,s,e", [(5, 1, 3), (-5, 1, -2), (3, 1, 2), (-3, 1, -1), (-1, 1, 0), (1, 1, 1), (7, 0, 7), (-128, 3, -16), (-127, 7, -1), (63, 7, 0), (64, 7, 1)])
def test_round_half_up(v, s, e):
    assert fp.rshift_round(v, s) == e


def test_saturation_is_symmetric():
    assert fp.sat8(200) == 127 and fp.sat8(-200) == -127 and fp.sat8(-127) == -127 and fp.sat8(0) == 0


def test_luts_are_in_multiply_range():
    assert fp.EXP_LUT[0] == 127 and all(0 <= v <= 127 for v in fp.EXP_LUT)
    assert all(1 <= v <= 127 for v in fp.RECIP_LUT) and all(1 <= v <= 127 for v in fp.NORM_LUT)
    assert fp.NORM_LUT[16] == 32 and fp.NORM_LUT[0] == 127


def test_norm_targets_unit_mean_abs():
    x = [64, -64] * 16
    out = fp.norm(x)
    assert out == [16, -16] * 16
    assert fp.norm([0] * 32) == [0] * 32


def test_attention_weights_sum_close_to_one():
    w = fp.attention_weights([5])
    assert w == [126]
    w = fp.attention_weights([3] * 16)
    assert w == [8] * 16 and sum(w) == 128
    w = fp.attention_weights([100, -100, 100])
    assert w[1] == 0 and w[0] == w[2]


def test_attend_single_key_returns_value_scaled():
    assert fp.attend([1, 1], [[1, 1]], [[64, -64]]) == [63, -63]


@pytest.fixture(scope="module")
def model():
    return quantize(ROOT / "checkpoints" / "release.pt")


def test_blob_round_trip_and_checksum(model):
    blob = to_blob(model)
    assert from_blob(blob) == model
    bad = bytearray(blob)
    bad[100] ^= 1
    with pytest.raises(ValueError):
        from_blob(bytes(bad))


def test_generation_deterministic_and_causal(model):
    p = ds.prompt_ids(0, 0, 0, 0)
    a = fp.generate(model, p)
    assert a == fp.generate(model, p)
    assert len(a["tokens"]) <= model.ctx
    # Causality: logits at position t depend only on tokens up to t.
    assert fp.step(model, a["tokens"][:6])[0] == fp.step(model, a["tokens"][:6])[0]
    lg7 = fp.step(model, a["tokens"][:7])[0]
    assert lg7 != fp.step(model, a["tokens"][:6])[0]


def test_action_token_changes_logits(model):
    a = fp.step(model, ds.prompt_ids(0, 0, 0, 0))[0]
    b = fp.step(model, ds.prompt_ids(0, 0, 1, 0))[0]
    assert a != b
