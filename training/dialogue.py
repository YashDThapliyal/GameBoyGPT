"""Vocabulary, prompts, sampling and validity for SYSTEM OVERRIDE dialogue.

Prompt: <BOS> MOOD RELATION HISTORY REPEAT FACTS INTENT TOPIC <SAY>. Response: EMOTION words <EOS>.

Held out from training, never shown to the model:
- situation families: every prompt whose (mood, intent, topic) triple hashes into the held-out set
- slot families: template and slot-value pairs that hash into the held-out set
"""
from __future__ import annotations
import hashlib
import random
import re
from pathlib import Path
import numpy as np

from reference import conversation as cv
from training import corpus as cp

CTX = 32
PROMPT_LEN = 9
MAX_RESPONSE = CTX - PROMPT_LEN  # emotion, words and EOS
LINE_WIDTH = 18
MAX_LINES = 4
EMOTIONS = ("NEUTRAL", "SMUG", "ANGRY", "AMUSED", "SURPRISED", "THINKING", "GLITCH", "DEFEATED")
RUNTIME_SLOTS = {"<NAME>": 8, "<LIKE>": 8, "<WORD>": 8, "<NI>": 2, "<NP>": 2, "<NT>": 2}  # widest printed form
PUNCT = (".", ",", "!", "?", ":")


def _groups() -> list[tuple[str, ...]]:
    """Every sentence template the corpus can produce, for vocabulary and validity."""
    g: list[tuple[str, ...]] = [tuple(v) for v in cp.OPENERS.values()]
    g += [tuple(v) for v in cp.BODIES.values()] + [tuple(v) for v in cp.TOPICS.values()]
    g += [cp.CHATTER, cp.ASKBACK] + [tuple(v) for v in cp.TAILS.values()]
    return g


def _expand(sentence: str) -> list[str]:
    out = [sentence]
    if "{pest}" in sentence:
        out = [s.replace("{pest}", p) for s in out for p in cp.PEST]
    if "{prop}" in sentence:
        out = [s.replace("{prop}", p) for s in out for p in cp.PROP]
    return out


def split_sentences(tokens: list[str]) -> list[str]:
    """Cuts a token list after each sentence-ending token that closes a template."""
    return " ".join(tokens).replace(" . ", " .\n").replace(" ! ", " !\n").split("\n")


TEMPLATES = sorted({s for g in _groups() for s in g})
EXPANDED = sorted({e for t in TEMPLATES for e in _expand(t)})


NUM_MERGES = 110  # phrase tokens, chosen by frequency: fewer tokens per response, so fewer forward passes


def _learn_merges(n: int) -> tuple[tuple[str, str], ...]:
    """Byte-pair-encoding over words of the authored templates. Pure function of the corpus."""
    seqs = [t.split() for t in TEMPLATES]
    merges: list[tuple[str, str]] = []
    for _ in range(n):
        counts: dict[tuple[str, str], int] = {}
        for q in seqs:
            for a, b in zip(q, q[1:]):
                if a in PUNCT or b in PUNCT or a.startswith(("<", "{")) or b.startswith(("<", "{")) or len(a) + len(b) + 1 > 14:
                    continue
                counts[(a, b)] = counts.get((a, b), 0) + 1
        if not counts:
            break
        top = min(counts, key=lambda k: (-counts[k], k))
        if counts[top] < 2:
            break
        merges.append(top)
        seqs = [_apply_merge(q, top) for q in seqs]
    return tuple(merges)


def _apply_merge(q: list[str], pair: tuple[str, str]) -> list[str]:
    out, i = [], 0
    while i < len(q):
        if i + 1 < len(q) and (q[i], q[i + 1]) == pair:
            out.append(q[i] + " " + q[i + 1])
            i += 2
        else:
            out.append(q[i])
            i += 1
    return out


MERGES = _learn_merges(NUM_MERGES)


def tokenize(sentence: str) -> list[str]:
    q = sentence.split()
    for pair in MERGES:
        q = _apply_merge(q, pair)
    return q


def _build_vocab() -> tuple[str, ...]:
    head = ["<BOS>", "<SAY>"]
    head += [f"<M_{x}>" for x in cv.MOODS] + [f"<R_{x}>" for x in cv.RELATIONS] + [f"<H_{x}>" for x in cv.HISTORIES]
    head += [f"<P_{x}>" for x in cv.REPEATS] + [f"<F_{x}>" for x in cv.FACTS] + [f"<I_{x}>" for x in cv.INTENTS] + [f"<T_{x}>" for x in cv.TOPICS]
    # The ROM relies on this order: emotions are scored alone for the first token, punctuation is exempt from the repetition penalty.
    gen = [f"<E_{x}>" for x in EMOTIONS] + ["<EOS>"] + list(RUNTIME_SLOTS)
    words = {w for e in EXPANDED for w in tokenize(e) if w not in RUNTIME_SLOTS}
    punct = sorted(words & set(PUNCT))
    return tuple(head + gen + punct + sorted(words - set(PUNCT)))


VOCAB = _build_vocab()
STOI = {w: i for i, w in enumerate(VOCAB)}
BOS, SAY, EOS = STOI["<BOS>"], STOI["<SAY>"], STOI["<EOS>"]
FIRST_EMOTION = STOI[f"<E_{EMOTIONS[0]}>"]
FIRST_GEN = FIRST_EMOTION
FIRST_SLOT = STOI["<NAME>"]
PUNCT_IDS = frozenset(STOI[p] for p in PUNCT if p in STOI)
FIRST_WORD = FIRST_SLOT + len(RUNTIME_SLOTS) + len(PUNCT_IDS)


def prompt_ids(s: cv.Situation) -> list[int]:
    return [BOS, STOI[f"<M_{s.mood}>"], STOI[f"<R_{s.relation}>"], STOI[f"<H_{s.history}>"], STOI[f"<P_{s.repeat}>"], STOI[f"<F_{s.facts}>"],
            STOI[f"<I_{s.intent}>"], STOI[f"<T_{s.topic}>"], SAY]


def _digest(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "little")


def intent_topics() -> list[tuple[str, str]]:
    """Intent and topic pairs the conversation rules can produce. Other pairs never reach the model."""
    pairs = [(i, "NONE") for i in cv.INTENTS if i not in ("TECH",)]
    pairs += [("TECH", t) for t in cv.TECH_TOPICS]
    for i in ("TALK", "QUESTION", "FOLLOW"):
        pairs += [(i, t) for t in cv.TECH_TOPICS + cv.GENERAL_TOPICS]
    pairs += [(i, t) for i in ("INSULT", "PRAISE", "CHALLENGE", "SMART", "WHO", "SHUTDOWN", "THREAT", "GREET", "BYE", "THANKS", "JOKE", "TRAPPED")
              for t in cv.TECH_TOPICS + cv.GENERAL_TOPICS]
    return sorted(set(pairs))


def heldout_situation(s: cv.Situation) -> bool:
    return _digest(f"sit:{s.mood}:{s.intent}:{s.topic}") % 100 < 8


def heldout_expansion(sentence: str) -> bool:
    """A filled-in sentence the training data never contains, used to test composition."""
    return "{" not in sentence and _digest(f"slot:{sentence}") % 100 < 10 and sentence not in TEMPLATES


def all_facts_for(s: cv.Situation) -> bool:
    return s.facts in ("NAME", "BOTH"), s.facts in ("LIKE", "BOTH")


def _body_pool(s: cv.Situation) -> tuple[str, ...]:
    if s.mood == "DYING":
        return cp.BODIES["LASTGASP"]
    if s.intent == "TALK":
        return cp.TOPICS[s.topic] if s.topic != "NONE" else cp.CHATTER
    if s.intent == "QUESTION":
        return cp.TOPICS[s.topic] if s.topic != "NONE" else cp.ASKBACK
    if s.intent == "TECH":
        return cp.TOPICS[s.topic]
    if s.intent == "FOLLOW" and s.topic != "NONE":
        return cp.BODIES["FOLLOW"] + cp.TOPICS[s.topic]
    # A topic mentioned alongside an attitude: mostly the attitude, sometimes the topic.
    return cp.BODIES[s.intent]


def _tail_pools(s: cv.Situation) -> list[tuple[str, ...]]:
    pools = []
    if s.repeat == "AGAIN":
        pools.append(cp.TAILS["AGAIN"])
    if s.history in ("RUDE", "NICE", "MIXED"):
        pools.append(cp.TAILS[s.history])
    if s.relation in ("ENEMY", "RIVAL", "MINION"):
        pools.append(cp.TAILS[s.relation])
    if s.facts in ("NAME", "BOTH") and s.intent != "NAME":
        pools.append(cp.TAILS["NAME"])
    if s.facts in ("LIKE", "BOTH") and s.intent != "LIKE":
        pools.append(cp.TAILS["LIKE"])
    return pools


def rendered_lines(tokens: list[str]) -> int:
    """Lines the renderer's word wrap needs, charging runtime slots at their widest."""
    lines, col = 1, 0
    for t in tokens:
        if t.startswith("<E_") or t == "<EOS>":
            continue
        n = RUNTIME_SLOTS.get(t, len(t))
        if t in PUNCT:
            col += 1  # attaches to the previous word and may hang one column past the wrap point only if it fits
            if col > LINE_WIDTH:
                lines, col = lines + 1, 1
            continue
        if col and col + 1 + n > LINE_WIDTH:
            lines, col = lines + 1, n
        else:
            col += n + (1 if col else 0)
    return lines


def _choose_filled(rnd: random.Random, template: str, allow_heldout: bool) -> str:
    options = _expand(template)
    pool = options if allow_heldout else [o for o in options if not heldout_expansion(o)]
    return rnd.choice(pool or options)


def sample_response(s: cv.Situation, rnd: random.Random, allow_heldout: bool = False) -> list[str]:
    emotion = rnd.choice((cp.EMOTION_BY_MOOD[s.mood], cp.EMOTION_BY_MOOD[s.mood], cp.INTENT_EMOTION[s.intent]))
    if s.mood == "DYING":
        emotion = "DEFEATED"
    for _ in range(30):
        parts: list[str] = []
        if rnd.random() < 0.55:
            parts.append(_choose_filled(rnd, rnd.choice(cp.OPENERS[s.mood]), allow_heldout))
        parts.append(_choose_filled(rnd, rnd.choice(_body_pool(s)), allow_heldout))
        pools = _tail_pools(s)
        if pools and rnd.random() < 0.6 and s.mood != "DYING":
            parts.append(_choose_filled(rnd, rnd.choice(rnd.choice(pools)), allow_heldout))
        words = [w for part in parts for w in tokenize(part)]
        tokens = [f"<E_{emotion}>"] + words + ["<EOS>"]
        if len(tokens) <= MAX_RESPONSE and rendered_lines(tokens) <= MAX_LINES:
            return tokens
    body = _choose_filled(rnd, rnd.choice(_body_pool(s)), allow_heldout)
    tokens = [f"<E_{emotion}>"] + tokenize(body) + ["<EOS>"]
    assert len(tokens) <= MAX_RESPONSE and rendered_lines(tokens) <= MAX_LINES, tokens
    return tokens


def random_situation(rnd: random.Random) -> cv.Situation:
    intent, topic = rnd.choice(intent_topics())
    mood = rnd.choices(cv.MOODS, (5, 3, 3, 2, 2, 1))[0]
    if mood == "DYING":
        intent, topic = "SHUTDOWN", "NONE"
    elif intent in ("THREAT", "SHUTDOWN"):
        mood = "WARY"
    return cv.Situation(mood, rnd.choice(cv.RELATIONS), rnd.choice(cv.HISTORIES), rnd.choices(cv.REPEATS, (4, 1))[0], rnd.choice(cv.FACTS), intent, topic)


def encode(s: cv.Situation, response: list[str]) -> list[int]:
    return prompt_ids(s) + [STOI[t] for t in response]


def make_split(n_train: int, n_eval: int, seed: int) -> dict[str, list[list[int]]]:
    """train: no held-out situation and no held-out filled sentence. val and test: only held-out situations."""
    rnd = random.Random(seed)
    train: list[list[int]] = []
    while len(train) < n_train:
        s = random_situation(rnd)
        if not heldout_situation(s):
            train.append(encode(s, sample_response(s, rnd)))
    held: list[list[int]] = []
    while len(held) < 2 * n_eval:
        s = random_situation(rnd)
        if heldout_situation(s):
            held.append(encode(s, sample_response(s, rnd, allow_heldout=True)))
    return {"train": train, "val": held[:n_eval], "test": held[n_eval:]}


def to_arrays(seqs: list[list[int]]) -> tuple[np.ndarray, np.ndarray]:
    """Inputs and next-token targets. Prompt positions and padding are ignored by the loss (-1)."""
    x = np.zeros((len(seqs), CTX), dtype=np.int64)
    y = np.full((len(seqs), CTX), -1, dtype=np.int64)
    for i, seq in enumerate(seqs):
        x[i, :len(seq) - 1] = seq[:-1]
        y[i, PROMPT_LEN - 1:len(seq) - 1] = seq[PROMPT_LEN:]
    return x, y


# ---- Validity: a response parses as an emotion, then authored sentences, then EOS. ----

_SENTENCES = frozenset(EXPANDED)
_MAX_SENT_TOKENS = max(len(e.split()) for e in EXPANDED)


def parse_sentences(words: list[str]) -> list[str] | None:
    """Greedy-free segmentation into grammar sentences (dynamic programming). None if impossible."""
    n = len(words)
    best: list[list[str] | None] = [None] * (n + 1)
    best[0] = []
    for i in range(n):
        if best[i] is None:
            continue
        for j in range(i + 1, min(n, i + _MAX_SENT_TOKENS) + 1):
            sent = " ".join(words[i:j])
            if sent in _SENTENCES and best[j] is None:
                best[j] = best[i] + [sent]
    return best[n]


def analyze(tokens: list[int]) -> dict:
    """Automatic checks on generated ids, starting after the prompt."""
    names = [VOCAB[t] for t in tokens]
    closed = bool(names) and names[-1] == "<EOS>"
    body = names[:-1] if closed else names
    has_emotion = bool(body) and body[0].startswith("<E_")
    tokens_after = body[1:] if has_emotion else body
    words = [w for t in tokens_after for w in (t.split() if not t.startswith("<") else [t])]
    sentences = parse_sentences(words) if closed and has_emotion and words else None
    stray = any(w.startswith("<E_") or (w.startswith("<") and w not in RUNTIME_SLOTS) for w in words)
    reps = sum(1 for a, b in zip(tokens_after, tokens_after[1:]) if a == b and a not in PUNCT)
    return {"closed": closed, "emotion": body[0][3:-1] if has_emotion else None, "words": tokens_after, "valid": sentences is not None and not stray,
            "sentences": sentences or [], "lines": rendered_lines(names), "immediate_repeats": reps}


def render(tokens: list[int], slots: dict[str, str] | None = None) -> str:
    """Display text for ids, as the ROM draws it: uppercase, punctuation attached, runtime slots filled."""
    slots = slots or {}
    out = ""
    for t in tokens:
        w = VOCAB[t]
        if w == "<EOS>" or w.startswith("<E_"):
            continue
        w = slots.get(w, w)
        out += w.upper() if w in PUNCT or not out else " " + w.upper()
    return re.sub(r"\s+", " ", out)


def write_vocab_report(path: Path) -> None:
    path.write_text(f"vocab {len(VOCAB)} first_gen {FIRST_GEN} templates {len(TEMPLATES)} sentences {len(EXPANDED)}\n")
