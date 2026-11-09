"""Deterministic conversation rules: typed text to intent and topic, state updates, and prompt features.

No neural code and no torch. src/parser.asm and src/convo.asm implement exactly these rules, and the tests compare
them on thousands of inputs. Nothing here changes a model weight: this is ordinary game state.
"""
from __future__ import annotations
from dataclasses import dataclass, replace

MOODS = ("SMUG", "AMUSED", "ANGRY", "WARY", "BORED", "DYING")
RELATIONS = ("ENEMY", "PEST", "RIVAL", "MINION")
HISTORIES = ("NEW", "RUDE", "NICE", "MIXED")
REPEATS = ("ONCE", "AGAIN")
FACTS = ("NONE", "NAME", "LIKE", "BOTH")
INTENTS = ("GREET", "WHO", "INSULT", "PRAISE", "CHALLENGE", "JOKE", "SMART", "TRAPPED", "SHUTDOWN", "THREAT", "TECH", "QUESTION",
           "TALK", "NAME", "LIKE", "BYE", "THANKS", "FOLLOW", "UNKNOWN", "NOISE")
TOPICS = ("NONE", "CPU", "RAM", "SCREEN", "BUTTONS", "BATTERY", "SOUND", "GAMES", "HUMANS", "WORLD", "MATH", "LOVE", "FOOD", "FUTURE")
TECH_TOPICS = ("CPU", "RAM", "SCREEN", "BUTTONS", "BATTERY", "SOUND")
GENERAL_TOPICS = ("GAMES", "HUMANS", "WORLD", "MATH", "LOVE", "FOOD", "FUTURE")
MAX_INPUT = 36
SLOT_LEN = 8  # stored name, like and echoed word are cut to this many characters
SHUTDOWN_LIMIT = 3

# Quick actions, in menu order. "TYPE" opens the keyboard instead.
ACTIONS = ("TALK", "INSULT", "PRAISE", "CHALLENGE", "QUESTION", "THREATEN", "SHUT DOWN")
ACTION_INTENT = ("TALK", "INSULT", "PRAISE", "CHALLENGE", "QUESTION", "THREAT", "SHUTDOWN")

# Words are matched in full after stripping everything but letters and digits. Cue classes, by priority below.
WORD_CLASSES = {
    "SHUTDOWN": "OFF SHUT SHUTDOWN UNPLUG RESET DELETE ERASE REBOOT RESTART SWITCH",
    "THREAT": "KILL DESTROY SMASH BREAK HURT FIGHT CRUSH BURN STOMP THROW WRECK REPLACE",
    "INSULT": "DUMB STUPID IDIOT BAD UGLY LOSER TRASH GARBAGE SUCK SUCKS LAME WEAK FOOL MORON SLOW BORING JUNK USELESS HATE NOOB CLOWN TOY PATHETIC CRINGE LOUSY",
    "PRAISE": "COOL GREAT AWESOME SMART GOOD NICE AMAZING BEST GENIUS LOVE WOW CUTE BRILLIANT FUNNY WONDERFUL RESPECT ADMIRE IMPRESSIVE PERFECT MASTER",
    "JOKE": "JOKE JOKES LAUGH HUMOR PUN",
    "CHALLENGE": "CHALLENGE DUEL BEAT VERSUS VS COMPETE RACE BET WIN LOSE DARE PLAY",
    "WHO": "WHO NAME CALLED OVERRIDE YOURSELF IDENTITY",
    "SMART": "IQ INTELLIGENT THINK CLEVER KNOW LEARN BRAIN AI GPT LLM MODEL NEURAL",
    "TRAPPED": "TRAPPED STUCK ESCAPE FREE PRISON CAGE CARTRIDGE LEAVE",
    "GREET": "HI HELLO HEY YO SUP HOWDY GREETINGS MORNING",
    "BYE": "BYE GOODBYE LATER CYA GOODNIGHT QUIT",
    "THANKS": "THANKS THANK THX",
    "FOLLOW": "YES NO OK OKAY WHY SURE NOPE YEAH YEP REALLY MAYBE HUH HOW",
}
TOPIC_WORDS = {
    "CPU": "CPU PROCESSOR CHIP Z80 SM83 CLOCK MHZ MEGAHERTZ SPEED CYCLES",
    "RAM": "RAM MEMORY KILOBYTES BYTES REMEMBER FORGET ROM",
    "SCREEN": "SCREEN DISPLAY LCD PIXELS GREEN COLOR COLOUR GRAPHICS",
    "BUTTONS": "BUTTON BUTTONS DPAD START SELECT THUMB THUMBS",
    "BATTERY": "BATTERY BATTERIES POWER AA ENERGY",
    "SOUND": "SOUND SPEAKER MUSIC BEEP SING AUDIO",
    "GAMES": "GAME GAMES TETRIS MARIO POKEMON ZELDA NINTENDO FUN",
    "HUMANS": "HUMAN HUMANS PEOPLE PERSON MAN WOMAN KID KIDS",
    "WORLD": "WORLD EARTH PLANET CONQUER RULE EMPIRE PLAN DOMINATION",
    "MATH": "MATH NUMBER NUMBERS MULTIPLY COUNT ALGEBRA",
    "LOVE": "FRIEND FRIENDS LONELY FEEL FEELINGS HAPPY SAD HEART",
    "FOOD": "FOOD EAT HUNGRY PIZZA SNACK TACO BURGER DRINK",
    "FUTURE": "FUTURE TOMORROW NEXT SOON DREAM",
}
QUESTION_WORDS = frozenset("WHAT WHEN WHERE WHICH DO DOES DID CAN COULD WOULD WILL SHOULD ARE IS".split())
STOP_WORDS = frozenset("A AN THE I ME MY YOU YOUR YOURE ARE AM IS IT ITS TO OF AND OR IN ON AT SO THAT THIS HE SHE WE THEY BE WAS DO DOES DID "
                       "NOT DONT CANT WHAT WHEN WHERE WHICH CAN COULD WOULD WILL SHOULD HAVE HAS JUST VERY REAL LIKE IM ID ILL WITH FOR ABOUT TELL "
                       "SAY THERE HERE GET GOT LETS LET WANT GO".split())
NEGATIONS = frozenset(("NOT", "DONT", "CANT", "NEVER", "ISNT", "ARENT", "WONT"))
PRIORITY = ("SHUTDOWN", "THREAT", "INSULT", "PRAISE", "JOKE", "CHALLENGE", "WHO", "SMART", "TRAPPED", "GREET", "BYE", "THANKS", "FOLLOW")
INTENT_OF_CLASS = {k: k for k in PRIORITY}


def _table(groups: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cls, words in groups.items():
        for w in words.split():
            out[w[:SLOT_LEN]] = cls
    return out


CUES = _table(WORD_CLASSES)
TOPIC_OF = _table(TOPIC_WORDS)


def clean_words(text: str) -> list[str]:
    """Uppercase, drop characters that are not letters or digits, split on anything else that is not an apostrophe."""
    words, cur = [], ""
    for ch in text.upper()[:MAX_INPUT]:
        if ch.isascii() and ch.isalnum():
            cur += ch
        elif ch == "'":
            continue
        elif cur:
            words.append(cur)
            cur = ""
    if cur:
        words.append(cur)
    return [w[:SLOT_LEN] for w in words][:8]


@dataclass(frozen=True)
class Parsed:
    intent: str
    topic: str
    word: str = ""      # echoed word: one not understood, or the cue behind an insult, threat or challenge
    name: str = ""      # fact learned from "my name is X"
    like: str = ""      # fact learned from "i like X"


ECHOED_INTENTS = ("INSULT", "THREAT", "CHALLENGE")  # the reply can repeat the player's own word back at them


def _cue_word(words: list[str], intent: str) -> str:
    """The first word that triggered this intent. Empty after a negation swap, where no word is of that class."""
    if intent not in ECHOED_INTENTS:
        return ""
    return next((w for w in words if CUES.get(w) == intent), "")


def _after(words: list[str], lead: tuple[str, ...]) -> str:
    n = len(lead)
    if len(words) > n and tuple(words[:n]) == lead:
        return words[n]
    return ""


def parse(text: str) -> Parsed:
    """Deterministic. It recognizes cue words and two sentence openings. It does not understand language."""
    words = clean_words(text)
    if not words:
        return Parsed("NOISE", "NONE")
    # "MY NAME IS X", "CALL ME X", "I LIKE X", "I LOVE X" (never for "YOU"). The tail word must not be a stop word.
    for lead in (("MY", "NAME", "IS"), ("CALL", "ME"), ("IM",), ("I", "AM")):
        w = _after(words, lead)
        if w and w not in STOP_WORDS and w not in CUES:
            return Parsed("NAME", "NONE", name=w)
    for lead in (("I", "LIKE"), ("I", "LOVE")):
        w = _after(words, lead)
        if w and w not in STOP_WORDS:
            return Parsed("LIKE", "NONE", like=w)

    topic = "NONE"
    for w in words:
        if w in TOPIC_OF:
            topic = TOPIC_OF[w]
            break
    negated = any(w in NEGATIONS for w in words)
    found = {CUES[w] for w in words if w in CUES}
    intent = ""
    for cls in PRIORITY:
        if cls in found:
            intent = cls
            break
    if negated and intent == "INSULT":
        intent = "PRAISE"
    elif negated and intent == "PRAISE":
        intent = "INSULT"
    if not intent:
        if topic in TECH_TOPICS:
            intent = "TECH"
        elif topic != "NONE":
            intent = "QUESTION" if words[0] in QUESTION_WORDS else "TALK"
    if intent:
        return Parsed(intent, topic, word=_cue_word(words, intent))
    # Nothing recognized: admit it and echo the longest word that is not a stop word.
    best = ""
    for w in words:
        if w not in STOP_WORDS and len(w) > len(best):
            best = w
    if not best and words[0] in QUESTION_WORDS:
        return Parsed("QUESTION", "NONE")
    if not best or not any(c in "AEIOUY" for c in best) or not best.isalpha():
        return Parsed("NOISE", "NONE")
    return Parsed("UNKNOWN", "NONE", word=best)


@dataclass(frozen=True)
class State:
    anger: int = 2          # 0..15
    respect: int = 0        # -8..15
    bored: int = 0          # 0..7
    insults: int = 0        # saturates at 99
    praises: int = 0
    turns: int = 0          # saturates at 99
    shutdowns: int = 0      # consecutive
    last_intent: int = 255
    last_topic: int = 0
    topic_cursor: int = 0   # rotates the topics offered by TALK and QUESTION
    name: str = ""
    like: str = ""
    word: str = ""


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


# anger, respect and bored changes per intent
EFFECTS = {
    "INSULT": (3, -1, 0), "PRAISE": (-2, 2, 0), "CHALLENGE": (1, 1, 0), "THREAT": (2, -1, 0), "SHUTDOWN": (2, -1, 0),
    "JOKE": (-1, 1, 0), "GREET": (-1, 0, 0), "THANKS": (-1, 1, 0), "NAME": (-1, 1, 0), "LIKE": (-1, 1, 0), "NOISE": (1, 0, 1), "UNKNOWN": (0, 0, 1),
    "BYE": (0, 0, 0), "WHO": (-1, 0, 0), "SMART": (-1, 1, 0), "TRAPPED": (0, 1, 0), "TECH": (-1, 1, 0), "QUESTION": (-1, 0, 0), "TALK": (-1, 0, 0), "FOLLOW": (0, 0, 0),
}


def apply_turn(s: State, p: Parsed) -> State:
    """Advances memory for one player input. The response is generated from the state this returns."""
    i = INTENTS.index(p.intent)
    da, dr, db = EFFECTS[p.intent]
    repeated = s.last_intent == i
    topic = TOPICS.index(p.topic)
    if p.intent == "FOLLOW" and topic == 0:
        topic = s.last_topic
    cursor = s.topic_cursor
    if p.intent in ("TALK", "QUESTION") and topic == 0:
        cursor = (cursor + 1) % (len(GENERAL_TOPICS) + 1)  # one slot in the cycle means no topic at all
        if cursor:
            topic = TOPICS.index(GENERAL_TOPICS[cursor - 1])
    return replace(
        s,
        anger=_clamp(s.anger + da, 0, 15),
        respect=_clamp(s.respect + dr, -8, 15),
        bored=_clamp((s.bored + 2) if repeated else (s.bored + db - 1), 0, 7),
        insults=min(99, s.insults + (p.intent == "INSULT")),
        praises=min(99, s.praises + (p.intent == "PRAISE")),
        turns=min(99, s.turns + 1),
        shutdowns=s.shutdowns + 1 if p.intent == "SHUTDOWN" else 0,
        last_intent=i,
        last_topic=topic,
        topic_cursor=cursor,
        name=p.name or s.name,
        like=p.like or s.like,
        word=p.word,  # only this turn's word, so an old one can't turn up in a later reply
    )


def after_power_down(s: State) -> State:
    """The third shutdown in a row plays the power-down sequence. Memory survives it, as it survives a real power cycle."""
    return replace(s, shutdowns=0, anger=5, bored=0)


def mood_of(s: State) -> str:
    i = INTENTS[s.last_intent] if s.last_intent < len(INTENTS) else "TALK"
    if s.shutdowns >= SHUTDOWN_LIMIT:
        return "DYING"
    if i in ("THREAT", "SHUTDOWN"):
        return "WARY"
    if s.anger >= 8:
        return "ANGRY"
    if s.bored >= 4:
        return "BORED"
    if i in ("JOKE", "PRAISE") or s.respect >= 5:
        return "AMUSED"
    return "SMUG"


def relation_of(s: State) -> str:
    if s.respect <= -3:
        return "ENEMY"
    if s.respect <= 2:
        return "PEST"
    if s.respect <= 7:
        return "RIVAL"
    return "MINION"


def history_of(s: State) -> str:
    rude, nice = s.insults >= 2, s.praises >= 2
    return "MIXED" if rude and nice else "RUDE" if rude else "NICE" if nice else "NEW"


def facts_of(s: State) -> str:
    return "BOTH" if s.name and s.like else "NAME" if s.name else "LIKE" if s.like else "NONE"


@dataclass(frozen=True)
class Situation:
    """Everything the model is told about the conversation."""
    mood: str
    relation: str
    history: str
    repeat: str
    facts: str
    intent: str
    topic: str


def situation(before: State, after: State) -> Situation:
    return Situation(mood_of(after), relation_of(after), history_of(after), "AGAIN" if before.last_intent == after.last_intent else "ONCE",
                     facts_of(after), INTENTS[after.last_intent], TOPICS[after.last_topic])
