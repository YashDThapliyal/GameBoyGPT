"""The SM83 parser and conversation memory against reference/conversation.py on thousands of inputs."""
import os
import random
import pytest
from kernel_harness import *
from reference import conversation as cv
from training import dialogue as dl

PHRASES = ["YOU ARE DUMB", "I LOVE YOU", "MY NAME IS ALEXANDRIA", "CALL ME BOB", "I LIKE PIZZA", "IM TIRED", "I AM HUNGRY", "I AM DUMB", "WHAT IS YOUR CPU",
           "WHY", "BYE BYE", "HELLO", "CAN YOU THINK", "YOU ARE NOT STUPID", "YOU ARE NOT COOL", "WILL YOU MARRY ME", "XQZ", "12345", "", " ", "...", "I", "I LIKE",
           "MY NAME IS", "MY NAME IS THE", "CALL ME DUMB", "I LIKE YOU", "A1B2 C3", "DON'T DO THAT", "IT'S FINE", "TELL ME A JOKE", "HOW", "ARE YOU TRAPPED", "WHAT ABOUT THE WEATHER",
           "SUPERCALIFRAGILISTIC", "ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN", "PIZZA PIZZA", "WHAT", "IS IT", "DO YOU LIKE GAMES", "I HATE MATH", "BEAT ME NOW OFF",
           "YOU'RE A TOY", "POWER", "WHEN IS DINNER", "THE THE THE", "RAM ROM", "MY NAME IS MY NAME", "I LOVE PIZZA AND TACOS"]


def random_text(rnd):
    words = sorted(set(cv.CUES) | set(cv.TOPIC_OF) | set(cv.STOP_WORDS) | set(cv.NEGATIONS)) + ["PIZZA", "XYZZY", "BOB", "NN", "Q1", "7", "AAAAAAAAAAAAA"]
    n = rnd.randint(1, 10)
    return rnd.choice(("", "", "I ", "MY NAME IS ", "I LIKE ", "CALL ME ")) + rnd.choice((" ", ", ", ". ", "' ", " - ")).join(rnd.choice(words) for _ in range(n))


@pytest.fixture(scope="module")
def rig():
    r = KernelRig(os.environ.get("GBGPT_VARIANT", "V6T"))
    yield r
    r.stop()


def text_at(gb, name):
    out = ""
    for c in gb.read(name, cv.SLOT_LEN + 1):
        if c == 0:
            break
        out += chr(c)
    return out


def rom_parse(rig, text):
    data = text[:cv.MAX_INPUT]
    rig.gb.write("wInput", [ord(c) for c in data] + [0])
    rig.gb.write("wInputLen", [len(data)])
    rig.run(CMD_PARSE)
    return cv.Parsed(cv.INTENTS[rig.gb.read1("wParsedIntent")], cv.TOPICS[rig.gb.read1("wParsedTopic")], text_at(rig.gb, "wParsedWord"), text_at(rig.gb, "wParsedName"), text_at(rig.gb, "wParsedLike"))


def test_parser_on_authored_phrases(rig):
    for t in PHRASES:
        assert rom_parse(rig, t) == cv.parse(t), t


def test_parser_on_random_inputs(rig):
    rnd = random.Random(99)
    for _ in range(1500):
        t = random_text(rnd)
        assert rom_parse(rig, t) == cv.parse(t), t


def test_state_and_prompt_parity_over_long_conversations(rig):
    rnd = random.Random(7)
    for convo in range(6):
        rig.run(CMD_RESET)
        s = cv.State()
        for turn in range(60):
            text = random_text(rnd) if rnd.random() < 0.5 else rnd.choice(PHRASES)
            p = rom_parse(rig, text)
            before, s = s, cv.apply_turn(s, p)
            rig.run(CMD_TURN)
            sit = cv.situation(before, s)
            assert read_ids(rig.gb, dl.PROMPT_LEN) == dl.prompt_ids(sit), (convo, turn, text, sit)
            assert rig.gb.read1("wAnger") == s.anger and s8(rig.gb.read1("wRespect")) == s.respect and rig.gb.read1("wBored") == s.bored
            assert rig.gb.read1("wInsults") == s.insults and rig.gb.read1("wPraises") == s.praises and rig.gb.read1("wTurns") == s.turns
            assert text_at(rig.gb, "wName") == s.name and text_at(rig.gb, "wLike") == s.like and text_at(rig.gb, "wWord") == s.word
            if s.shutdowns >= cv.SHUTDOWN_LIMIT:
                s = cv.after_power_down(s)
                rig.gb.write("wShutdowns", [0])
                rig.gb.write("wBored", [0])
                rig.gb.write("wAnger", [5])
