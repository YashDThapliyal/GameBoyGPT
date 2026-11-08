"""Dataset integrity: vocab budget, held-out families absent from training, oracle sanity."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from training import dataset as ds


def test_vocab_and_sequence_budget():
    assert len(ds.VOCAB) <= 96 and len(set(ds.VOCAB)) == len(ds.VOCAB)
    assert ds.VOCAB[ds.FIRST_GEN] == "<EOS>"
    assert all(len(ds.encode(s, x)) <= ds.CTX for s in ds.situations() for x in ds.sentences(*s))


def test_heldout_families_never_in_training():
    split = ds.make_split(5000, 200, 1)
    prefix = lambda r: tuple(r[:ds.PROMPT_LEN])
    heldout = {tuple(ds.prompt_ids(*s)) for s in ds.VAL_FAMILIES | ds.TEST_FAMILIES}
    assert not {prefix(r) for r in split["train"]} & heldout
    assert {prefix(r) for r in split["test"]} == {tuple(ds.prompt_ids(*s)) for s in ds.TEST_FAMILIES if s in ds.situations()}
    assert len(ds.TEST_FAMILIES) >= 3


def test_oracle_rejects_wrong_room_and_action():
    s = (0, 0, 0, 0)
    good = [ds.STOI[w] for w in ds.sentences(*s)[0]]
    assert all(ds.check_sentence(s, good).values())
    assert not ds.check_sentence((1, 0, 0, 0), good)["room"]
    assert not ds.check_sentence((0, 0, 1, 0), good)["action"]
