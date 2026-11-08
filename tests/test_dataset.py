"""Dataset integrity: vocabulary, held-out families absent from training, screen fit, oracle sanity."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from training import dataset as ds


def test_vocab_and_sequence_budget():
    assert len(ds.VOCAB) <= 255 and len(set(ds.VOCAB)) == len(ds.VOCAB)
    assert ds.VOCAB[ds.FIRST_GEN] == "<EOS>"
    assert all(len(ds.encode(s, x)) <= ds.CTX for s in ds.situations() for x in ds.sentences(*s))


def test_every_situation_has_narration_and_fits_the_story_box():
    for s in ds.situations():
        narrations = ds.sentences(*s)
        assert narrations, s
        for sentence in narrations:
            assert ds.lines_needed(sentence) <= ds.SCREEN_LINES, sentence


def test_heldout_families_never_in_training():
    split = ds.make_split(5000, 200, 1)
    prefix = lambda r: tuple(r[:ds.PROMPT_LEN])
    heldout = {tuple(ds.prompt_ids(*s)) for s in ds.VAL_FAMILIES | ds.TEST_FAMILIES}
    assert not {prefix(r) for r in split["train"]} & heldout
    assert len(ds.TEST_FAMILIES) >= 3


def test_shipping_split_covers_every_situation():
    split = ds.make_split(5000, 200, 1, train_on_all=True)
    assert {tuple(r[:ds.PROMPT_LEN]) for r in split["train"]} == {tuple(ds.prompt_ids(*s)) for s in ds.situations()}


def test_oracle_rejects_wrong_event_and_wrong_items():
    s = ("ENTER_CAVE", 0, ds.LIVE)
    good = [ds.STOI[w] for w in ds.sentences(*s)[0]]
    assert ds.check_sentence(s, good)["strict"]
    assert not ds.check_sentence(("WADE_RIVER", 0, ds.LIVE), good)["strict"]
    lit = ("ENTER_CAVE", 1, ds.LIVE)
    assert not ds.check_sentence(lit, good)["strict"], "with the lamp the narration must change"
