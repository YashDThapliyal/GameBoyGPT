"""Every SM83 kernel against the independent integer reference: edge cases plus seeded random vectors."""
import random
import pytest
from kernel_harness import *
from reference import fixed_point as fp
from export_weights import from_blob

VARIANT = "V0"
EDGES = [-127, -126, -64, -1, 0, 1, 2, 63, 64, 126, 127]


@pytest.fixture(scope="module")
def rig(request):
    r = KernelRig(getattr(request, "param", VARIANT))
    yield r
    r.stop()


@pytest.fixture(scope="module")
def model():
    return from_blob((ROOT / "generated" / "model.bin").read_bytes())


def rand_vec(rnd, n, lo=-127, hi=127):
    return [rnd.randint(lo, hi) for _ in range(n)]


def test_mul_edges_and_random(rig):
    pairs = [(a, b) for a in EDGES for b in EDGES]
    rnd = random.Random(1)
    pairs += [(rnd.randint(-127, 127), rnd.randint(-127, 127)) for _ in range(300)]
    for a, b in pairs:
        rig.run(CMD_MUL, [a & 255, b & 255])
        lo, hi = rig.gb.read("wMB_Args", 2, 2)
        v = lo | hi << 8
        v = v - 65536 if v > 32767 else v
        assert v == a * b, (a, b)


@pytest.mark.parametrize("n", [1, 2, 16, 32, 64])
def test_dot_random_and_extremes(rig, n):
    rnd = random.Random(n)
    cases = [([127] * n, [127] * n), ([-127] * n, [127] * n), ([-127] * n, [-127] * n), ([0] * n, [127] * n)]
    cases += [(rand_vec(rnd, n), rand_vec(rnd, n)) for _ in range(20)]
    for a, b in cases:
        rig.gb.write("wTestA", a)
        rig.gb.write("wTestB", b)
        rig.run(CMD_DOT, [n])
        lo, mi, hi = rig.gb.read("wMB_Args", 3, 1)
        v = lo | mi << 8 | hi << 16
        v = v - (1 << 24) if v >= 1 << 23 else v
        assert v == fp.dot(a, b)


def test_requant_boundaries(rig):
    rnd = random.Random(5)
    vals = [0, 1, -1, 63, 64, 65, -63, -64, -65, 127, 128, -127, -128, -129, 16255, 16256, -16256, -16257, 8388607, -8388608, 1032256, -1032256]
    vals += [rnd.randint(-1100000, 1100000) for _ in range(200)]
    for v in vals:
        for s in (0, 1, 4, 5, 6, 7):
            if abs(v) + (1 << max(s - 1, 0)) >= 1 << 23:
                continue
            u = v & 0xFFFFFF
            rig.run(CMD_REQUANT, [u & 255, u >> 8 & 255, u >> 16, s])
            got = s8(rig.gb.read("wMB_Args", 1, 4)[0])
            assert got == fp.sat8(fp.rshift_round(v, s)), (v, s)


def test_satadd_and_relu(rig):
    rnd = random.Random(9)
    for _ in range(40):
        a, b = rand_vec(rnd, 32), rand_vec(rnd, 32)
        a[0], b[0], a[1], b[1], a[2], b[2] = 127, 127, -127, -127, 127, -127
        rig.gb.write("wTestA", a)
        rig.gb.write("wTestB", b)
        rig.run(CMD_SATADD)
        assert [s8(x) for x in rig.gb.read("wTestOut", 32)] == fp.add_sat(a, b)
    v = rand_vec(rnd, 64)
    rig.gb.write("wTestA", v)
    rig.run(CMD_RELU, [64])
    assert [s8(x) for x in rig.gb.read("wTestA", 64)] == fp.relu(v)


def test_norm(rig):
    rnd = random.Random(11)
    cases = [[0] * 32, [127] * 32, [-127] * 32, [1] + [0] * 31, [1] * 32, [16, -16] * 16]
    cases += [rand_vec(rnd, 32, -m, m) for m in (1, 2, 5, 20, 60, 127) for _ in range(8)]
    for x in cases:
        rig.gb.write("wTestA", x)
        rig.run(CMD_NORM)
        assert [s8(v) for v in rig.gb.read("wTestOut", 32)] == fp.norm(x)


def test_attention_weights(rig):
    rnd = random.Random(13)
    cases = [[0], [127], [-127], [127, -127], [5] * 16, [127] + [-127] * 15, list(range(-8, 8))]
    cases += [rand_vec(rnd, rnd.randint(1, 16), -m, m) for m in (2, 10, 40, 127) for _ in range(20)]
    for sc in cases:
        rig.gb.write("wScore", sc)
        rig.run(CMD_WEIGHTS, [len(sc)])
        assert rig.gb.read("wWeight", len(sc)) == fp.attention_weights(sc)


@pytest.mark.parametrize("L", [1, 2, 5, 16])
def test_attend_head(rig, L):
    rnd = random.Random(L)
    hd = 16
    for head in (0, 1):
        for mag in (20, 127):
            q = rand_vec(rnd, hd, -mag, mag)
            K = [rand_vec(rnd, 32, -mag, mag) for _ in range(16)]
            V = [rand_vec(rnd, 32) for _ in range(16)]
            rig.gb.write("wTestA", q)
            rig.gb.write("wKCache", [x for r in K for x in r])
            rig.gb.write("wVCache", [x for r in V for x in r])
            rig.run(CMD_ATTEND, [L, head * hd])
            lo, hi = head * hd, (head + 1) * hd
            want = fp.attend(q, [k[lo:hi] for k in K[:L]], [v[lo:hi] for v in V[:L]])
            assert [s8(x) for x in rig.gb.read("wTestOut", hd)] == want


@pytest.mark.parametrize("idx,name,shift,n_in", [(2, "w_q", "s_q", 32), (3, "w_k", "s_k", 32), (4, "w_v", "s_v", 32), (5, "w_o", "s_o", 32), (6, "w_f1", "s_f1", 32), (7, "w_f2", "s_f2", 64)])
def test_matvec_real_weights_from_rom(rig, model, idx, name, shift, n_in):
    rnd = random.Random(idx)
    W, s = getattr(model, name), getattr(model, shift)
    for x in ([127] * n_in, [-127] * n_in, rand_vec(rnd, n_in), rand_vec(rnd, n_in)):
        rig.gb.write("wTestA", x)
        rig.run(CMD_MATVEC, [idx])
        assert [s8(v) for v in rig.gb.read("wTestOut", len(W))] == fp.matvec(W, x, s)


def test_argmax_and_sampling(rig, model):
    rnd = random.Random(17)
    rng = 0xACE1
    for trial in range(60):
        hi = 30000 if trial % 2 else 200
        logits = [rnd.randint(-hi, hi) for _ in range(95)]
        if trial % 5 == 0:  # create ties and near-ties around the top
            top = max(logits[27:])
            for i in rnd.sample(range(27, 95), 6):
                logits[i] = top - rnd.randint(0, model.sample_margin)
        rig.gb.write("wLogits", [b for v in logits for b in ((v & 255), (v >> 8) & 255)])
        rig.run(CMD_SAMPLE, [0])
        assert rig.gb.read("wMB_Args", 1, 1)[0] == fp.argmax_masked(model, logits)
        rig.gb.write("wNarrRng", [rng & 255, rng >> 8])
        rig.run(CMD_SAMPLE, [1])
        want, rng2 = fp.sample_masked(model, logits, rng)
        assert rig.gb.read("wMB_Args", 1, 1)[0] == want
        assert rig.gb.read("wNarrRng", 2) == [rng2 & 255, rng2 >> 8]
        rng = rng2
