"""End to end: logits and token traces on the SM83 equal the integer reference, bit for bit."""
import os
import random
import pytest
from kernel_harness import *
from reference import conversation as cv, fixed_point as fp
from export_weights import from_blob
from training import dialogue as dl

VARIANT = os.environ.get("GBGPT_VARIANT", "V0")


@pytest.fixture(scope="module")
def rig():
    r = KernelRig(VARIANT)
    yield r
    r.stop()


@pytest.fixture(scope="module")
def model():
    return from_blob((ROOT / "generated" / "model.bin").read_bytes())


def load_seq(rig, seq):
    rig.gb.write("wSeq", ids16(seq))
    rig.gb.write("wSeqLen", [len(seq)])


def read_logits(rig, model):
    n = model.vocab
    raw = rig.gb.read("wLogits", n * 2)
    vals = [raw[i] | raw[i + 1] << 8 for i in range(0, n * 2, 2)]
    return [v - 65536 if v > 32767 else v for v in vals]


def scenarios(n, seed):
    """Half from situations the model never trained on, half from those it did."""
    rnd = random.Random(seed)
    held, rest = [], []
    while len(held) < n // 2 or len(rest) < n - n // 2:
        s = dl.random_situation(rnd)
        (held if dl.heldout_situation(s) else rest).append(s)
    return held[:n // 2] + rest[:n - n // 2]


def test_step_logits_bit_exact(rig, model):
    rnd = random.Random(21)
    seqs = [dl.prompt_ids(s) for s in scenarios(6, 2)]
    seqs += [[rnd.randrange(model.vocab) for _ in range(L)] for L in (1, 2, 8, 16, model.ctx)]  # adversarial streams, max length
    for seq in seqs:
        for mode in (0, 1):
            load_seq(rig, seq)
            rig.gb.write("wRowMode", [mode])
            rig.run(CMD_STEP)
            want = fp.step(model, seq)[0]
            got = read_logits(rig, model)
            for i in fp.allowed_rows(model, mode):
                assert got[i] == want[i], (i, mode)


@pytest.mark.parametrize("greedy", [True, False])
def test_generation_token_parity_20_scenarios(rig, model, greedy):
    for i, s in enumerate(scenarios(20, 3)):
        prompt = dl.prompt_ids(s)
        rng = 0x1234 + i * 77
        want = fp.generate(model, prompt, greedy=greedy, rng=rng)
        load_seq(rig, prompt)
        rig.gb.write("wMB_Greedy", [1 if greedy else 0])
        rig.gb.write("wNarrRng", [rng & 255, rng >> 8])
        rig.run(CMD_GENERATE, max_frames=40000)
        n = rig.gb.read1("wSeqLen")
        assert read_ids(rig.gb, n) == want["tokens"], s
        assert rig.gb.read("wMB_LogitSum", 2) == [want["logit_sums"][-1] & 255, want["logit_sums"][-1] >> 8]
        assert bool(rig.gb.read("wMB_Args", 1)[0]) == want["capped"]
        if not greedy:
            assert rig.gb.read("wNarrRng", 2) == [want["rng"] & 255, want["rng"] >> 8]
