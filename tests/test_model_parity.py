"""End-to-end: logits and token traces on the SM83 equal the integer reference, bit for bit."""
import random
import pytest
from kernel_harness import *
from reference import fixed_point as fp
from reference import game as g
from export_weights import from_blob
from training import dataset as ds

VARIANT = "V0"


@pytest.fixture(scope="module")
def rig():
    r = KernelRig(VARIANT)
    yield r
    r.stop()


@pytest.fixture(scope="module")
def model():
    return from_blob((ROOT / "generated" / "model.bin").read_bytes())


def load_seq(rig, seq):
    rig.gb.write("wSeq", list(seq))
    rig.gb.write("wSeqLen", [len(seq)])


def read_logits(rig):
    raw = rig.gb.read("wLogits", 190)
    vals = [raw[i] | raw[i + 1] << 8 for i in range(0, 190, 2)]
    return [v - 65536 if v > 32767 else v for v in vals]


def scenarios(n, seed):
    sits = [s for s in ds.situations() if ds.sentences(*s)]
    heldout = [s for s in sits if s in ds.VAL_FAMILIES | ds.TEST_FAMILIES]
    rnd = random.Random(seed)
    rest = rnd.sample([s for s in sits if s not in heldout], max(0, n - len(heldout)))
    return (heldout + rest)[:n]


def test_step_logits_bit_exact(rig, model):
    rnd = random.Random(21)
    seqs = [ds.prompt_ids(*s) for s in scenarios(6, 2)]
    seqs += [[rnd.randrange(95) for _ in range(L)] for L in (1, 2, 8, 16)]  # adversarial token streams, max length
    for seq in seqs:
        load_seq(rig, seq)
        rig.run(CMD_STEP)
        assert read_logits(rig) == fp.step(model, seq)[0]


@pytest.mark.parametrize("greedy", [True, False])
def test_generation_token_parity_20_scenarios(rig, model, greedy):
    for i, s in enumerate(scenarios(20, 3)):
        prompt = ds.prompt_ids(*s)
        rng = 0x1234 + i * 77
        want = fp.generate(model, prompt, greedy=greedy, rng=rng)
        load_seq(rig, prompt)
        rig.gb.write("wMB_Greedy", [1 if greedy else 0])
        rig.gb.write("wNarrRng", [rng & 255, rng >> 8])
        rig.run(CMD_GENERATE, max_frames=40000)
        n = rig.gb.read1("wSeqLen")
        assert rig.gb.read("wSeq", n) == want["tokens"], s
        assert rig.gb.read("wMB_LogitSum", 2) == [want["logit_sums"][-1] & 255, want["logit_sums"][-1] >> 8]
        assert bool(rig.gb.read("wMB_Args", 1)[0]) == want["capped"]
        if not greedy:
            assert rig.gb.read("wNarrRng", 2) == [want["rng"] & 255, want["rng"] >> 8]
