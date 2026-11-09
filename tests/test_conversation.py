"""The deterministic conversation rules and the corpus, without any ROM or model."""
import random
from reference import conversation as cv
from training import corpus as cp, dialogue as dl


def test_cue_words_map_to_intents():
    cases = {"YOU ARE DUMB": "INSULT", "YOU ARE GREAT": "PRAISE", "HELLO THERE": "GREET", "WHO ARE YOU?": "WHO", "TELL ME A JOKE": "JOKE",
             "I WILL SHUT YOU DOWN": "SHUTDOWN", "I WILL DESTROY YOU": "THREAT", "ARE YOU TRAPPED": "TRAPPED", "CAN YOU THINK": "SMART",
             "I BET I CAN BEAT YOU": "CHALLENGE", "BYE": "BYE", "THANKS": "THANKS", "WHY": "FOLLOW", "WHAT IS YOUR CPU": "TECH"}
    for text, intent in cases.items():
        assert cv.parse(text).intent == intent, text


def test_negation_swaps_insult_and_praise():
    assert cv.parse("YOU ARE NOT STUPID").intent == "PRAISE"
    assert cv.parse("YOU ARE NOT COOL").intent == "INSULT"


def test_facts_are_learned_and_cut_to_slot_length():
    assert cv.parse("MY NAME IS ALEXANDRIA").name == "ALEXANDR"
    assert cv.parse("CALL ME BOB").name == "BOB"
    assert cv.parse("I LIKE PIZZA").like == "PIZZA"
    assert cv.parse("I LOVE YOU").intent == "PRAISE"


def test_unsupported_input_is_admitted_not_faked():
    p = cv.parse("WILL YOU MARRY ME")
    assert (p.intent, p.word) == ("UNKNOWN", "MARRY")
    assert cv.parse("XQZ").intent == "NOISE"
    assert cv.parse("12345").intent == "NOISE"
    assert cv.parse("").intent == "NOISE"
    assert cv.parse("   ...   ").intent == "NOISE"


def test_input_limits_never_raise():
    rnd = random.Random(1)
    for _ in range(3000):
        n = rnd.randint(0, 60)
        p = cv.parse("".join(rnd.choice("ABC XYZ01 ',.?!-") for _ in range(n)))
        assert p.intent in cv.INTENTS and len(p.word) <= cv.SLOT_LEN


def test_state_is_bounded_under_any_sequence():
    rnd = random.Random(2)
    s = cv.State()
    for _ in range(5000):
        s = cv.apply_turn(s, cv.Parsed(rnd.choice(cv.INTENTS[:-2]), "NONE"))
        assert 0 <= s.anger <= 15 and -8 <= s.respect <= 15 and 0 <= s.bored <= 7 and s.turns <= 99
        cv.situation(s, s)
        if s.shutdowns >= cv.SHUTDOWN_LIMIT:
            s = cv.after_power_down(s)


def test_state_changes_the_prompt():
    a = cv.State()
    b = cv.apply_turn(a, cv.Parsed("INSULT", "NONE"))
    c = cv.apply_turn(b, cv.Parsed("INSULT", "NONE"))
    d = cv.apply_turn(c, cv.Parsed("INSULT", "NONE"))
    assert cv.history_of(c) == "RUDE" and cv.mood_of(d) == "ANGRY"
    assert cv.situation(b, c).repeat == "AGAIN" and cv.situation(a, b).repeat == "ONCE"


def test_third_shutdown_in_a_row_is_the_last_gasp():
    s = cv.State()
    for _ in range(3):
        s = cv.apply_turn(s, cv.Parsed("SHUTDOWN", "NONE"))
    assert cv.mood_of(s) == "DYING"
    s2 = cv.after_power_down(s)
    assert cv.mood_of(s2) != "DYING" and s2.turns == s.turns


def test_every_corpus_response_fits_the_box_and_the_context():
    rnd = random.Random(3)
    for _ in range(4000):
        s = dl.random_situation(rnd)
        t = dl.sample_response(s, rnd, allow_heldout=True)
        assert len(t) <= dl.MAX_RESPONSE and dl.rendered_lines(t) <= dl.MAX_LINES
        a = dl.analyze([dl.STOI[x] for x in t])
        assert a["valid"] and a["closed"], t


def test_heldout_families_never_reach_training():
    split = dl.make_split(3000, 200, 5)
    forbidden = {tuple(dl.prompt_ids(cv.Situation(m, r, h, p, f, i, t)))
                 for m, r, h, p, f, i, t in {(s[0], s[1], s[2], s[3], s[4], s[5], s[6]) for s in []}}
    assert not forbidden
    inverse = {v: k for k, v in dl.STOI.items()}
    for q in split["train"]:
        s = cv.Situation(*[inverse[q[i]].split("_", 1)[1][:-1] for i in range(1, 8)])
        assert not dl.heldout_situation(s)
    for q in split["val"] + split["test"]:
        s = cv.Situation(*[inverse[q[i]].split("_", 1)[1][:-1] for i in range(1, 8)])
        assert dl.heldout_situation(s)


def test_vocabulary_order_the_rom_depends_on():
    assert dl.EOS == dl.FIRST_EMOTION + 8 and dl.FIRST_SLOT == dl.EOS + 1
    for w in dl.VOCAB[dl.FIRST_WORD:]:
        assert not w.startswith("<") and w not in dl.PUNCT


def test_authored_text_has_no_lowercase_only_tokens_the_font_cannot_draw():
    drawable = set(" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?:'-")
    for w in dl.VOCAB[dl.FIRST_WORD:]:
        assert set(w.upper()) <= drawable, w


def test_page_move_phrases_parse_to_the_intent_their_button_promises():
    """The page's quick moves are real typed text, so each one must survive the keyboard's charset and the parser."""
    import json
    import re
    from pathlib import Path
    moves = json.loads((Path(__file__).resolve().parent.parent / "web" / "moves.json").read_text())
    assert set(moves) == {"talk", "roast", "threaten", "challenge"}
    for phrases in moves.values():
        assert len(phrases) >= 3
        for phrase in phrases:
            assert re.fullmatch(r"[A-Z0-9',.?! -]+", phrase["say"]), phrase["say"]
            assert len(phrase["say"]) <= cv.MAX_INPUT, phrase["say"]
            assert cv.parse(phrase["say"]).intent == phrase["intent"], phrase["say"]
