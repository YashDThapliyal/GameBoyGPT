"""The narrative event language: vocabulary, grammar, validity oracle and held-out splits.

A prompt is <BOS> ROOM INV ACT OUT and the model continues with up to MAX_GEN word tokens and <EOS>.
Every narrated word comes directly from a model token; no words are added at render time except the
final full stop on <EOS>. The grammar exists to generate training data and to score validity.
"""
from __future__ import annotations
import itertools
import json
import random
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reference import game as g

CTX = 16
PROMPT_LEN = 5
MAX_GEN = CTX - PROMPT_LEN  # includes EOS
ROOM_NOUNS = {
    g.FOREST: ["FERNS", "ROOTS"], g.MARSH: ["REEDS", "LEECHES"], g.RIVER: ["STONES", "RAPIDS"],
    g.RUINS: ["ARCHES", "COLUMNS"], g.SHRINE: ["CANDLES", "IDOLS"], g.CAVE: ["BATS", "ROCKS"],
    g.GATE: ["BARS", "CHAINS"], g.TOWER: ["BONES", "SHADOWS"],
}
ADJS = ["DARK", "WET", "COLD", "PALE", "SILENT"]
VERBS = ["STIR", "WAIT", "LOOM", "SIGH"]
ACT_CLAUSES = {
    g.LEFT: [["YOU", "TURN", "LEFT"], ["YOU", "GO", "LEFT"]],
    g.RIGHT: [["YOU", "TURN", "RIGHT"], ["YOU", "GO", "RIGHT"]],
    g.FORWARD: [["YOU", "PRESS", "ON"], ["YOU", "WALK", "ON"]],
    g.SEARCH: [["YOU", "SEARCH"], ["YOU", "LOOK"]],
}
FUNCTION_WORDS = """AND THE A YOUR BUT IS NO UNDER BY NOTHING FIND ONLY LAMP KEY SHOWS HUMS STOP PATH LOCKED
NEED BITE HURT OPENS TURNS CLIMB FALL TAKE GATE SLEEPS GUARDIAN WAKES STAIRS""".split()
SPECIALS = ["<BOS>", "<EOS>"]
ROOM_TOK = [f"<R_{r}>" for r in g.ROOMS]
INV_TOK = ["<I_NONE>", "<I_LAMP>", "<I_BOTH>"]
ACT_TOK = [f"<A_{a}>" for a in g.ACTIONS]
OUT_TOK = [f"<O_{o}>" for o in g.OUTCOMES]
_words = sorted({w for v in ROOM_NOUNS.values() for w in v} | set(ADJS) | set(VERBS) | set(FUNCTION_WORDS)
                | {w for v in ACT_CLAUSES.values() for c in v for w in c})
# <EOS> sits just before the words so the generation mask is the contiguous id range FIRST_GEN..VOCAB-1.
VOCAB = ["<BOS>"] + ROOM_TOK + INV_TOK + ACT_TOK + OUT_TOK + ["<EOS>"] + _words
STOI = {w: i for i, w in enumerate(VOCAB)}
BOS, EOS = STOI["<BOS>"], STOI["<EOS>"]
FIRST_GEN = EOS
NUM_WORDS_LONGEST = max(len(w) for w in _words)


def prompt_ids(room: int, inv: int, act: int, out: int) -> list[int]:
    return [BOS, STOI[ROOM_TOK[room]], STOI[INV_TOK[inv]], STOI[ACT_TOK[act]], STOI[OUT_TOK[out]]]


def _room_phrases(room: int) -> list[list[str]]:
    return [[a, n] for a in ADJS for n in ROOM_NOUNS[room]]


def sentences(room: int, inv: int, act: int, out: int) -> list[list[str]]:
    """All narrations the grammar considers true for this situation."""
    a_clauses = ACT_CLAUSES[act]
    nouns = ROOM_NOUNS[room]
    res: list[list[str]] = []
    if out == g.MOVE:
        for c in a_clauses:
            if inv == 0:
                res += [c + ["AND", "THE", a, n, v] for a, n in _room_phrases(room) for v in VERBS]
            elif inv == 1:
                res += [c + ["AND", "YOUR", "LAMP", "SHOWS", a, n] for a, n in _room_phrases(room)]
            else:
                res += [c + ["AND", "YOUR", "KEY", "HUMS", "BY", a, n] for a, n in _room_phrases(room)]
    elif out == g.BLOCK:
        for c in a_clauses:
            res += [c + ["BUT", "THE", n, "STOP", "YOU"] for n in nouns]
            res += [c + ["BUT", "NO", "PATH", "IS", "BY", "THE", n] for n in nouns]
    elif out == g.DARK:
        for c in a_clauses:
            res += [c + ["BUT", "YOU", "NEED", "A", "LAMP"], c + ["BUT", "THE", "DARK", "BATS", "STOP", "YOU"]]
    elif out == g.LOCKED:
        for c in a_clauses:
            res += [c + ["BUT", "THE", "GATE", "IS", "LOCKED"], c + ["BUT", "YOU", "NEED", "THE", "KEY"]]
    elif out == g.LAMP:
        res += [c + ["AND", "FIND", "A", "LAMP", "UNDER", "THE", n] for c in a_clauses for n in nouns]
    elif out == g.KEY:
        res += [c + ["AND", "FIND", "A", "KEY", "UNDER", "THE", a, n] for c in a_clauses for a in ADJS for n in nouns]
    elif out == g.NOTHING:
        res += [c + ["BUT", "FIND", "ONLY", a, n] for c in a_clauses for a, n in _room_phrases(room)]
        res += [["YOU", "SEARCH", "THE", n, "BUT", "FIND", "NOTHING"] for n in nouns]
    elif out == g.HURT:
        if room == g.TOWER:
            res += [c + ["AND", "THE", "GUARDIAN", "WAKES"] for c in a_clauses]
        else:
            for c in a_clauses:
                res += [c + ["AND", "THE", n, "HURT", "YOU"] for n in nouns]
                res += [c + ["AND", "THE", a, n, "BITE"] for a, n in _room_phrases(room)]
    elif out == g.OPEN:
        res += [c + ["AND", "YOUR", "KEY", "TURNS", "THE", "GATE", "OPENS"] for c in a_clauses]
    elif out == g.WIN:
        res += [["YOU", "CLIMB", "THE", a, "STAIRS", "AND", "THE", "GUARDIAN", "SLEEPS"] for a in ADJS]
    elif out == g.LOSE:
        res += [["YOU", "FALL", "AND", "THE", n, "TAKE", "YOU"] for n in nouns]
    for s in res:
        for w in s:
            assert w in STOI, w
        assert len(s) + 1 <= MAX_GEN, s
    return res


def situations() -> list[tuple[int, int, int, int]]:
    """Every (room, inv, act, out) the engine can actually produce."""
    out_set = set()
    for seed in range(0, 65536, 11):
        w = g.gen_world(seed)
        rnd = random.Random(seed)
        s = g.start(w)
        for _ in range(60):
            a = rnd.randrange(4)
            s2, o = g.step(w, s, a)
            out_set.add((s2.room, g.inv_code(s2), a, o))
            s = s2
            if s.done:
                break
    out_set |= _analytic_situations()
    return sorted(out_set)


def _analytic_situations():
    """Reachable combinations too rare for random walks to always hit (e.g. tower rows)."""
    res = set()
    for room, inv in itertools.product(range(8), range(3)):
        lamp_key_ok = room != g.CAVE or inv > 0
        if room == g.TOWER:
            if inv == 2:
                res |= {(room, 2, g.LEFT, g.BLOCK), (room, 2, g.RIGHT, g.BLOCK), (room, 2, g.SEARCH, g.HURT),
                        (room, 2, g.FORWARD, g.WIN), (room, 2, g.FORWARD, g.OPEN), (room, 2, g.SEARCH, g.LOSE)}
            continue
        if not lamp_key_ok:
            continue
        for a in (g.LEFT, g.RIGHT, g.FORWARD):
            res |= {(room, inv, a, g.MOVE), (room, inv, a, g.BLOCK)}
        res.add((room, inv, g.SEARCH, g.NOTHING))
    return res


# Held-out families: never present in training, in any variation. Spec section 4.4.
VAL_FAMILIES = {
    (g.RIVER, 0, g.SEARCH, g.NOTHING), (g.SHRINE, 1, g.LEFT, g.MOVE), (g.MARSH, 0, g.RIGHT, g.BLOCK),
    (g.CAVE, 2, g.FORWARD, g.MOVE), (g.GATE, 1, g.RIGHT, g.MOVE), (g.FOREST, 2, g.SEARCH, g.NOTHING),
}
TEST_FAMILIES = {
    (g.FOREST, 2, g.RIGHT, g.MOVE), (g.RUINS, 1, g.SEARCH, g.NOTHING), (g.RIVER, 1, g.FORWARD, g.BLOCK),
    (g.SHRINE, 0, g.RIGHT, g.MOVE), (g.CAVE, 1, g.LEFT, g.MOVE), (g.GATE, 2, g.LEFT, g.BLOCK),
    (g.MARSH, 2, g.FORWARD, g.MOVE), (g.TOWER, 2, g.LEFT, g.BLOCK), (g.RUINS, 0, g.LEFT, g.MOVE),
}


def encode(situation, sentence) -> list[int]:
    return prompt_ids(*situation) + [STOI[w] for w in sentence] + [EOS]


def make_split(n_train: int, n_eval: int, seed: int) -> dict[str, list[list[int]]]:
    rnd = random.Random(seed)
    sits = [s for s in situations() if sentences(*s)]
    train_sits = [s for s in sits if s not in VAL_FAMILIES and s not in TEST_FAMILIES]
    val_sits = [s for s in sits if s in VAL_FAMILIES]
    test_sits = [s for s in sits if s in TEST_FAMILIES]
    assert len(val_sits) >= 3 and len(test_sits) >= 3

    def sample(pool, n):
        out = []
        for i in range(n):
            s = pool[i % len(pool)]  # balance across situations, not across their sentence counts
            out.append(encode(s, rnd.choice(sentences(*s))))
        return out

    return {"train": sample(train_sits, n_train), "val": sample(val_sits, n_eval), "test": sample(test_sits, n_eval)}


def pad_id() -> int:
    return EOS


def to_arrays(rows, ctx=CTX):
    """x,y arrays; targets before the prompt ends and after EOS are ignored (-1)."""
    import numpy as np
    x = np.full((len(rows), ctx), pad_id(), dtype=np.int64)
    y = np.full((len(rows), ctx), -1, dtype=np.int64)
    for i, r in enumerate(rows):
        x[i, : len(r)] = r
        y[i, PROMPT_LEN - 1 : len(r) - 1] = r[PROMPT_LEN:]
    return x, y


def check_sentence(situation, ids: list[int]) -> dict[str, bool]:
    """Validity oracle over generated ids (without the trailing EOS).

    strict: exact member of the grammar for this situation.
    action: uses this action's clause. room: mentions only nouns from the right room.
    outcome: has the outcome's signature words. """
    room, inv, act, out = situation
    words = [VOCAB[i] for i in ids]
    strict = words in sentences(*situation)
    action = any(words[: len(c)] == c for c in ACT_CLAUSES[act]) or out in (g.WIN, g.LOSE)
    all_nouns = {n for v in ROOM_NOUNS.values() for n in v}
    allowed = set(ROOM_NOUNS[room]) | ({"BATS"} if out == g.DARK else set())
    room_ok = not any(w in all_nouns and w not in allowed for w in words)
    signature = {g.MOVE: {"AND"}, g.BLOCK: {"BUT"}, g.DARK: {"LAMP", "DARK"}, g.LOCKED: {"LOCKED", "NEED"}, g.LAMP: {"LAMP"},
                 g.KEY: {"KEY"}, g.NOTHING: {"NOTHING", "ONLY"}, g.HURT: {"HURT", "BITE", "WAKES"}, g.OPEN: {"OPENS"},
                 g.WIN: {"CLIMB"}, g.LOSE: {"FALL"}}[out]
    return {"strict": strict, "action": action, "room": room_ok, "outcome": any(w in signature for w in words)}


def write_assets(path: Path, n_train=48000, n_eval=4000, seed=1234) -> None:
    path.mkdir(parents=True, exist_ok=True)
    split = make_split(n_train, n_eval, seed)
    for name in split:
        with open(path / f"{name}.jsonl", "w") as f:
            for row in split[name]:
                f.write(json.dumps(row) + "\n")
    (path / "vocab.json").write_text(json.dumps(VOCAB, indent=0))


if __name__ == "__main__":
    sits = situations()
    print("vocab", len(VOCAB), "first_gen", FIRST_GEN, "longest word", NUM_WORDS_LONGEST, "situations", len(sits))
    print("no-sentence situations:", [s for s in sits if not sentences(*s)])
    print("sentence counts sample:", sum(len(sentences(*s)) for s in sits))
    print("max words:", max(len(x) for s in sits for x in sentences(*s)))
