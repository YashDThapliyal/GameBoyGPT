"""Narration language for the branching story: vocabulary, grammar, validity oracle and held-out splits.

A prompt is <BOS> BEAT FLAGS FATE. The model continues with one or two short sentences and <EOS>. The story graph in
reference/story.py decides what happens; this grammar defines the ways of telling it that the model is trained on.
Every word on screen is a model token. The display adds only capital letters at sentence starts.
"""
from __future__ import annotations
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reference import story as st

CTX = 24
PROMPT_LEN = 4
MAX_GEN = CTX - PROMPT_LEN  # includes EOS
SCREEN_COLS, SCREEN_LINES = 18, 4

# What each choice does, in words. Beats that end the game carry the whole epilogue.
BEAT_TEXT = {
    "SEE_RUINS": "you follow the light to old ruins .",
    "HEAR_VOICE": "you follow the voice into the marsh .",
    "TAKE_LAMP": "you take the lamp .",
    "TAKE_SWORD": "you take the sword .",
    "FREE_PRISONER": "you free him and he joins you .",
    "TAKE_RING": "you take his ring and leave him .",
    "LEAVE_PRISONER": "you leave him to the mud .",
    "CROSS_BRIDGE": "the bridge breaks and you fall .",
    "WADE_RIVER": "you wade the cold water .",
    "ENTER_CAVE": "you enter the cave .",
    "LIGHT_LAMP": "your lamp shows a hidden door .",
    "CREEP_DARK": "you fall in the dark .",
    "FRIEND_LEADS": "he leads you to a door .",
    "LEAVE_CAVE": "you turn back .",
    "TAKE_KEY": "you take the key .",
    "OPEN_CHEST": "it bites but you get the key .",
    "PRAY": "you pray and feel calm .",
    "BURN_RING": "the ring burns your hand and is gone .",
    "TAKE_BLADE": "you take the blade and it cuts you .",
    "PASS_SHRINE": "you walk past the altar .",
    "OPEN_GATE": "your key opens the gate .",
    "FORCE_GATE": "you force the bars and bleed .",
    "FRIEND_LIFTS": "he lifts you over the wall .",
    "CLIMB_WALL": "you climb the wall and fall hard .",
    "SNEAK": "you creep past him and he sleeps on .",
    "SNEAK_CURSED": "the ring burns and he wakes .",
    "WAKE": "you wake him and he looks at you .",
    "STRIKE": "your blow only angers him .",
    "ASK_CROWN": "he laughs and lifts his axe .",
    "FIGHT_SWORD": "he falls but you bleed .",
    "FRIEND_HOLDS": "your friend holds him and falls .",
    "FLEE": "you run and never look back . the tower still waits .",
    "FREE_GUARDIAN": "you break his chains . he bows and the tower is free .",
    "SHOW_RING": "he kneels to the ring . now you guard the tower forever .",
    "RUN_STAIRS": "the stairs crumble and you fall into the dark forever .",
    "YIELD": "you kneel . he chains you to the wall beside him .",
    "TAKE_CROWN": "the crown is yours . you are king of an empty tower .",
    "BREAK_CROWN": "you break the crown and the mist lifts at last .",
}
# What the next scene shows. Where a choice is dangerous, this is the omen that warns about it.
ARRIVAL = {
    "ruins": "a lamp and a sword lie here .",
    "pit": "a prisoner begs in the mud .",
    "fork": "the old bridge groans .",
    "cave": "the dark hides a drop .",
    "vault": "the chest has teeth .",
    "shrine": "the altar blade bleeds .",
    "gate": "the bars are sharp .",
    "hall": "his hand rests on an axe .",
    "talk": "his eyes go to the crown .",
    "duel": "the stairs crumble behind him .",
    "top": "the crown glows .",
}
DEATH_CLAUSE = "the mist takes you ."
SYNONYMS = {"old": ["old", "ancient"], "dark": ["dark", "black"], "cold": ["cold", "icy"], "sharp": ["sharp", "cruel"],
            "take": ["take", "grab"], "walk": ["walk", "slip"], "groans": ["groans", "sags"],
            "bleeds": ["bleeds", "weeps"], "glows": ["glows", "shines"], "calm": ["calm", "safe"], "hurt": ["hurt", "cut"]}
BEAT_NEXT = {c.beat: c.next for s in st.SCENES for c in s.choices}
FLAG_SETS = sorted({f for _, f, _ in st.narration_situations()})
LIVE, DYING = 0, 1

BEAT_TOK = [f"<B_{b}>" for b in st.BEATS]
FLAG_TOK = [f"<F_{f}>" for f in FLAG_SETS]
FATE_TOK = ["<LIVE>", "<DYING>"]
_phrases = list(BEAT_TEXT.values()) + list(ARRIVAL.values()) + [DEATH_CLAUSE, "look .", "he warns ."]
_words = sorted({w for p in _phrases for w in p.split()} | {a for v in SYNONYMS.values() for a in v})
VOCAB = ["<BOS>"] + BEAT_TOK + FLAG_TOK + FATE_TOK + ["<EOS>"] + _words
STOI = {w: i for i, w in enumerate(VOCAB)}
BOS, EOS = STOI["<BOS>"], STOI["<EOS>"]
FIRST_GEN = EOS


def situations() -> list[tuple[str, int, int]]:
    """(beat, flags after, fate) for everything the game can ask the narrator to tell."""
    out = set()
    for beat, flags, wounds in st.narration_situations():
        out.add((beat, flags, DYING if wounds >= st.MAX_WOUNDS else LIVE))
    return sorted(out)


def prompt_ids(beat: str, flags: int, fate: int) -> list[int]:
    return [BOS, STOI[f"<B_{beat}>"], STOI[f"<F_{flags}>"], STOI[FATE_TOK[fate]]]


def _expand(clause: str) -> list[list[str]]:
    """Every wording of a clause. At most two words vary, so options stay meaningful and bounded."""
    words = clause.split()
    slots = [SYNONYMS.get(w, [w]) for w in words]
    varying = [i for i, s in enumerate(slots) if len(s) > 1][:2]
    fixed = [s[0] for s in slots]
    res = []
    for combo in itertools.product(*(slots[i] for i in varying)):
        cur = list(fixed)
        for i, w in zip(varying, combo):
            cur[i] = w
        res.append(cur)
    return res


def _omen_forms(clause: str, flags: int) -> list[list[str]]:
    """The same news told differently depending on what you carry, so the model has to read the flags."""
    if flags & st.LAMP:
        prefix = ["look", "."]
    elif flags & st.FRIEND:
        prefix = ["he", "warns", "."]
    else:
        prefix = []
    return [prefix + w for w in _expand(clause)]


def sentences(beat: str, flags: int, fate: int) -> list[list[str]]:
    """All narrations the grammar considers true for this situation."""
    openers = _expand(BEAT_TEXT[beat])
    nxt = BEAT_NEXT[beat]
    if fate == DYING:
        closers = [DEATH_CLAUSE.split()]
    elif st.BY_ID[nxt].ending:
        return openers
    else:
        closers = _omen_forms(ARRIVAL[nxt], flags)
    return [a + b for a in openers for b in closers]


def lines_needed(words: list[str]) -> int:
    """Lines used by the ROM's greedy word wrap. A full stop sticks to the word before it, in the 19th column if needed."""
    lines, col = 1, 0
    for w in words:
        if w == ".":
            col += 1
            continue
        need = len(w) + (1 if col else 0)
        if col + need > SCREEN_COLS:
            lines, col = lines + 1, len(w)
        else:
            col += need
    return lines


_SITUATIONS = situations()
_rnd = random.Random(20261108)
_shuffled = list(_SITUATIONS)
_rnd.shuffle(_shuffled)
# Held-out families: never present in training in any wording. They are (beat, flags) combinations, so a model passes
# only by combining an event it knows with carried items it has seen on other events.
_live = [s for s in _shuffled if s[2] == LIVE and len({x for x in _SITUATIONS if x[0] == s[0]}) > 1]
VAL_FAMILIES = set(_live[:12])
TEST_FAMILIES = set(_live[12:32])


def encode(situation, sentence) -> list[int]:
    return prompt_ids(*situation) + [STOI[w] for w in sentence] + [EOS]


def make_split(n_train: int, n_eval: int, seed: int, train_on_all: bool = False) -> dict[str, list[list[int]]]:
    """train_on_all is for the shipping model, which must narrate every reachable situation. Generalization is
    measured separately, on a sibling model trained with the held-out families removed."""
    rnd = random.Random(seed)
    train_sits = _SITUATIONS if train_on_all else [s for s in _SITUATIONS if s not in VAL_FAMILIES and s not in TEST_FAMILIES]

    def sample(pool, n):
        return [encode(pool[i % len(pool)], rnd.choice(sentences(*pool[i % len(pool)]))) for i in range(n)]

    return {"train": sample(train_sits, n_train), "val": sample(sorted(VAL_FAMILIES), n_eval), "test": sample(sorted(TEST_FAMILIES), n_eval)}


def to_arrays(rows, ctx=CTX):
    """x,y arrays; targets before the prompt ends and after EOS are ignored (-1)."""
    import numpy as np
    x = np.full((len(rows), ctx), EOS, dtype=np.int64)
    y = np.full((len(rows), ctx), -1, dtype=np.int64)
    for i, r in enumerate(rows):
        x[i, : len(r)] = r
        y[i, PROMPT_LEN - 1 : len(r) - 1] = r[PROMPT_LEN:]
    return x, y


def check_sentence(situation, ids: list[int]) -> dict[str, bool]:
    """strict: exact member of the grammar. event: opens by telling what actually happened.
    closing: ends with the right omen, death or epilogue for the situation."""
    words = [VOCAB[i] for i in ids]
    valid = sentences(*situation)
    openers = _expand(BEAT_TEXT[situation[0]])
    return {"strict": words in valid, "event": any(words[: len(o)] == o for o in openers),
            "closing": any(words[-len(s) + len(openers[0]):] == s[len(openers[0]):] for s in valid) if len(valid[0]) > len(openers[0]) else any(words == o for o in openers)}


def write_assets(path: Path, n_train: int = 60000, n_eval: int = 4000, seed: int = 1234) -> None:
    path.mkdir(parents=True, exist_ok=True)
    split = make_split(n_train, n_eval, seed)
    for name, rows in split.items():
        with open(path / f"{name}.jsonl", "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    (path / "vocab.json").write_text(json.dumps(VOCAB, indent=0))


if __name__ == "__main__":
    all_s = [(s, x) for s in _SITUATIONS for x in sentences(*s)]
    print("vocab", len(VOCAB), "control", FIRST_GEN, "words", len(VOCAB) - FIRST_GEN, "situations", len(_SITUATIONS), "sentences", len(all_s))
    print("longest tokens", max(len(x) for _, x in all_s), "limit", MAX_GEN - 1)
    bad = sorted({(s[0], s[1] & 5, s[2], lines_needed(x)) for s, x in all_s if lines_needed(x) > SCREEN_LINES})
    print("over 4 lines:", len(bad), bad[:16])
