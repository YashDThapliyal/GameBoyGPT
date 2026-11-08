"""Phase 5 gate and zero-fake audit: real on-device narration, parity with the reference, no canned text."""
import hashlib
import os
import shutil
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from run_emulator import GB, load_symbols
from reference import fixed_point as fp, game as g
from export_weights import from_blob, to_blob
from training import dataset as ds
import dataclasses

VARIANT = os.environ.get("GBGPT_VARIANT", "V0")
ROM = ROOT / "build" / VARIANT / "gameboygpt.gb"
ST_TITLE, ST_MENU, ST_GENERATING, ST_REVEAL, ST_ENDING = 1, 3, 5, 6, 8
BUTTONS = {g.LEFT: ("left",), g.RIGHT: ("right",), g.FORWARD: ("up",), g.SEARCH: ("down",)}
MODEL = from_blob((ROOT / "generated" / "model.bin").read_bytes())


def start(rom, seed, greedy):
    gb = GB(rom, Path(rom).with_suffix(".sym"))
    gb.wait_state(ST_TITLE, 2000)
    gb.tick(5)
    gb.write("wMB_ForceSeed", [1])
    gb.write("wMB_Seed", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1 if greedy else 0])
    gb.press("start")
    gb.wait_state(ST_MENU, 3000)
    return gb


def choose(gb, action):
    for b in BUTTONS[action]:
        gb.press(b)
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_REVEAL, 400000)
    gb.tick(8)


def event_tokens(gb):
    n = gb.read1("wMB_NumTokens")
    return gb.read("wMB_LastTokens", 5 + n)


def visible_text(gb):
    rows = []
    for r in range(8, 12):
        rows.append("".join(chr(t + 0x20) if t < 96 else "?" for t in gb.read("wBgMap", 19, r * 20 + 1)).rstrip())
    return " ".join(x for x in rows if x)


def render(tokens):
    words = [ds.VOCAB[t].lower() for t in tokens if t != ds.EOS]
    return " ".join(words).capitalize() + "."


def assert_clean_screen(gb):
    for row in range(18):
        assert [gb.mem[0x9800 + row * 32 + c] for c in range(20)] == gb.read("wBgMap", 20, row * 20), f"row {row}"


@pytest.mark.parametrize("seed,greedy", [(7, True), (321, False), (9001, False)])
def test_full_journey_to_the_ending_matches_reference(seed, greedy):
    gb = start(ROM, seed, greedy)
    w = g.gen_world(seed)
    s = g.start(w)
    narr = w.rng ^ 0xA5A5
    turns = valid = 0
    while not s.done:
        a = g.next_action(w, s)
        s, out = g.step(w, s, a)
        situation = (s.room, g.inv_code(s), a, out)
        prompt = ds.prompt_ids(*situation)
        want = fp.generate(MODEL, prompt, greedy=greedy, rng=narr)
        narr = want["rng"]
        choose(gb, a)
        turns += 1
        assert gb.read1("wMB_Room") == s.room and gb.read1("wMB_Outcome") == out
        assert event_tokens(gb) == want["tokens"], situation
        assert visible_text(gb) == render(want["generated"])
        assert_clean_screen(gb)
        valid += ds.check_sentence(situation, [t for t in want["generated"] if t != ds.EOS])["strict"]
        gb.press("a")
        gb.wait_for(lambda: gb.read1("wMB_State") in (ST_MENU, ST_ENDING), 3000)
    assert turns >= 5
    assert valid == turns, "every narrated event must be grammar-valid"
    assert gb.read1("wMB_Fallbacks") == 0 and gb.read1("wMB_Placeholder") == 0
    assert gb.read1("wMB_State") == ST_ENDING
    gb.press("a")
    gb.wait_state(ST_TITLE, 2000)  # NEW RUN path returns to the title without a reset
    gb.stop()


def test_same_state_different_action_differs_because_input_differs():
    """Spec gate 5: same room+inventory, two actions, different inputs and different neural continuations."""
    seed = 7
    results = {}
    for action in (g.LEFT, g.RIGHT):
        gb = start(ROM, seed, True)
        w = g.gen_world(seed)
        s, out = g.step(w, g.start(w), action)
        choose(gb, action)
        results[action] = event_tokens(gb)
        assert results[action][3] == ds.STOI[ds.ACT_TOK[action]]
        gb.stop()
    assert results[g.LEFT][:5] != results[g.RIGHT][:5] and results[g.LEFT][5:] != results[g.RIGHT][5:]


def test_rom_contains_real_weights_and_no_canned_narration():
    rom = ROM.read_bytes()
    syms = load_symbols(ROM.with_suffix(".sym"))
    for name, label in (("tok", "DataTok"), ("pos", "DataPos"), ("w_q", "DataQ"), ("w_k", "DataK"), ("w_v", "DataV"),
                        ("w_o", "DataO"), ("w_f1", "DataF1"), ("w_f2", "DataF2"), ("w_out", "DataOut")):
        bank, addr = syms[label]
        off = bank * 0x4000 + addr - 0x4000
        flat = bytes(v & 0xFF for row in getattr(MODEL, name) for v in row)
        biased = bytes((v + 128) & 0xFF for row in getattr(MODEL, name) for v in row)
        assert rom[off:off + len(flat)] in (flat, biased), name
    for phrase in (b"you turn", b"and the", b"you look", b"but the", b"under the"):
        assert phrase not in rom.lower(), "narration must not exist as stored sentences"
    words_blob = sum(len(w) + 1 for w in ds.VOCAB[ds.FIRST_GEN:])
    assert words_blob < 700


def test_output_changes_when_rom_weights_are_patched(tmp_path):
    """If narration were canned, patching the output-projection weights could not change it. It must, predictably."""
    syms = load_symbols(ROM.with_suffix(".sym"))
    bank, addr = syms["DataOut"]
    off = bank * 0x4000 + addr - 0x4000
    rom = bytearray(ROM.read_bytes())
    row = 40  # a real word row: swing its weights hard
    biased = rom[off:off + 32] != bytes(v & 0xFF for v in MODEL.w_out[0])
    patched_rows = [list(r) for r in MODEL.w_out]
    for c in range(32):
        v = -MODEL.w_out[row][c]
        patched_rows[row][c] = v
        rom[off + row * 32 + c] = (v + 128) & 0xFF if biased else v & 0xFF
    patched = tmp_path / "patched.gb"
    patched.write_bytes(rom)
    shutil.copy(ROM.with_suffix(".sym"), patched.with_suffix(".sym"))
    m2 = dataclasses.replace(MODEL, w_out=tuple(map(tuple, patched_rows)))
    seed = 7
    w = g.gen_world(seed)
    s, out = g.step(w, g.start(w), g.FORWARD)
    prompt = ds.prompt_ids(s.room, g.inv_code(s), g.FORWARD, out)
    original = fp.generate(MODEL, prompt)["tokens"]
    expected = fp.generate(m2, prompt)["tokens"]
    assert original != expected, "patch must matter to the reference"
    gb = start(patched, seed, True)
    choose(gb, g.FORWARD)
    assert event_tokens(gb) == expected
    gb.stop()
