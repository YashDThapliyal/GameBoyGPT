"""Zero-fake audit: real on-device narration, parity with the reference, no canned text."""
import dataclasses
import shutil
import pytest
from run_emulator import load_symbols
from story_harness import *

ROUTES = {
    "crown": ["Follow the light", "Take the lamp", "Enter the cave", "Light the lamp", "Take the key", "Pray at the altar", "Use the key", "Sneak past him", "Take the crown"],
    "freed": ["Hear the voice", "Free the prisoner", "Enter the cave", "Call for help", "Take the key", "Walk on", "Use the key", "Wake him", "Free him"],
    "ring": ["Hear the voice", "Take his ring", "Wade the shallows", "Walk on", "Climb the wall", "Wake him", "Show the ring"],
}


def play(rom, route, greedy, seed):
    gb = boot(rom, seed, greedy)
    s = st.State()
    narr = seed or 1
    turns = []
    for label in route:
        options = st.available(s)
        i = next(n for n, c in enumerate(options) if c.label == label)
        s, situation = situation_after(s, options[i])
        want = fp.generate(MODEL, ds.prompt_ids(*situation), greedy=greedy, rng=narr)
        narr = want["rng"]
        choose(gb, i)
        turns.append((situation, want))
        assert event_tokens(gb) == want["tokens"], situation
        assert visible_text(gb) == render(want["generated"])
        assert_clean_screen(gb)
        next_page(gb)
    return gb, s, turns


@pytest.mark.parametrize("name,greedy,seed", [("crown", True, 7), ("crown", False, 321), ("freed", False, 9001), ("ring", False, 55)])
def test_full_journey_to_the_ending_matches_reference(name, greedy, seed):
    gb, s, turns = play(ROM, ROUTES[name], greedy, seed)
    assert st.BY_ID[s.scene].ending and gb.read1("wMB_State") == ST_ENDING
    for situation, want in turns:
        assert ds.check_sentence(situation, [t for t in want["generated"] if t != ds.EOS])["strict"], situation
    assert gb.read1("wMB_Fallbacks") == 0 and gb.read1("wMB_Placeholder") == 0
    gb.press("a")
    gb.wait_state(ST_TITLE, 2000)
    gb.stop()


def test_same_menu_different_choice_differs_because_input_differs():
    results = {}
    options = st.available(st.State())
    for i in range(2):
        gb = boot()
        choose(gb, i)
        results[i] = event_tokens(gb)
        assert results[i][1] == ds.STOI[f"<B_{options[i].beat}>"]
        gb.stop()
    assert results[0][:ds.PROMPT_LEN] != results[1][:ds.PROMPT_LEN] and results[0][ds.PROMPT_LEN:] != results[1][ds.PROMPT_LEN:]


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
    low = rom.lower()
    for phrase in ("you follow the", "the bridge breaks", "your key opens", "the crown is yours", "he laughs and"):
        assert phrase.encode() not in low, "narration must not exist as stored sentences"


def test_output_changes_when_rom_weights_are_patched(tmp_path):
    """If narration were canned, patching the output-projection weights could not change it. It must, predictably."""
    syms = load_symbols(ROM.with_suffix(".sym"))
    bank, addr = syms["DataOut"]
    off = bank * 0x4000 + addr - 0x4000
    rom = bytearray(ROM.read_bytes())
    biased = rom[off:off + 32] != bytes(v & 0xFF for v in MODEL.w_out[0])
    option = st.available(st.State())[0]
    _, situation = situation_after(st.State(), option)
    original = fp.generate(MODEL, ds.prompt_ids(*situation))["tokens"]
    row = original[ds.PROMPT_LEN]  # the first word it would have said: swing that row's weights hard
    patched_rows = [list(r) for r in MODEL.w_out]
    for c in range(32):
        v = -MODEL.w_out[row][c]
        patched_rows[row][c] = v
        rom[off + row * 32 + c] = (v + 128) & 0xFF if biased else v & 0xFF
    patched = tmp_path / "patched.gb"
    patched.write_bytes(rom)
    shutil.copy(ROM.with_suffix(".sym"), patched.with_suffix(".sym"))
    expected = fp.generate(dataclasses.replace(MODEL, w_out=tuple(map(tuple, patched_rows))), ds.prompt_ids(*situation))["tokens"]
    assert original != expected, "patch must matter to the reference"
    gb = boot(patched)
    choose(gb, 0)
    assert event_tokens(gb) == expected
    gb.stop()
