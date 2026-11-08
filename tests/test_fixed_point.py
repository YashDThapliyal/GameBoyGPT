"""Hand-computed contract checks for the integer reference, plus blob round trip and determinism."""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from reference import fixed_point as fp
from export_weights import to_blob, from_blob
from reference import conversation as cv
from training import dialogue as dl


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


def test_repetition_penalty_lowers_only_words_already_used():
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    logits = [0] * m.vocab
    word = m.first_word + 3
    out = fp.penalized(m, logits, [m.first_emotion, m.eos + 1, word, word])
    assert out[word] == -2 * m.rep_penalty and out[m.first_emotion] == 0 and out[m.eos + 1] == 0


def test_first_token_is_always_an_emotion_and_generation_is_deterministic():
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    p = dl.prompt_ids(cv.Situation("SMUG", "PEST", "NEW", "ONCE", "NONE", "GREET", "NONE"))
    a, b = fp.generate(m, p, greedy=False, rng=77), fp.generate(m, p, greedy=False, rng=77)
    assert a == b and m.first_emotion <= a["generated"][0] < m.eos
    assert all(t >= m.eos for t in a["generated"][1:])


def test_cached_step_equals_full_recompute():
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    p = dl.prompt_ids(cv.Situation("ANGRY", "ENEMY", "RUDE", "AGAIN", "BOTH", "INSULT", "NONE")) + [m.first_emotion, m.first_word, m.first_word + 5]
    cache = fp.Cache()
    for n in range(1, len(p) + 1):
        assert fp.step(m, p[:n], cache)[0] == fp.step(m, p[:n])[0]


def test_blob_round_trip():
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    assert from_blob(to_blob(m)) == m
