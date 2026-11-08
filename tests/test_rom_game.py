"""Phase 1 gate: ROM boots in DMG mode, and assembly world rules track reference/game.py exactly."""
import os
import random
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from run_emulator import GB
from reference import game as g

ROM = ROOT / "build" / os.environ.get("GBGPT_VARIANT", "V0") / "gameboygpt.gb"
ST_TITLE, ST_MENU, ST_REVEAL = 1, 3, 6
BUTTON_FOR_ACTION = {g.LEFT: ("up", "left"), g.RIGHT: ("up", "right"), g.FORWARD: ("down", "left"), g.SEARCH: ("down", "right")}


def boot(seed):
    gb = GB(ROM)
    gb.wait_state(ST_TITLE, 2000)
    gb.tick(5)
    gb.write("wMB_ForceSeed", [1])
    gb.write("wMB_Seed", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1])
    gb.press("start")
    gb.wait_state(ST_MENU, 3000)
    return gb


def act(gb, action):
    for b in BUTTON_FOR_ACTION[action]:
        gb.press(b)
    gb.press("a")
    gb.wait_state(ST_REVEAL, 200000)


def assert_vram_matches_shadow(gb):
    gb.tick(8)
    for row in range(18):
        vram = [gb.mem[0x9800 + row * 32 + c] for c in range(20)]
        assert vram == gb.read("wBgMap", 20, row * 20), f"row {row}"


def test_header_is_dmg_mbc5_with_valid_checksum():
    rom = ROM.read_bytes()
    assert rom[0x143] == 0x00, "CGB flag must be clear"
    assert rom[0x147] == 0x19, "MBC5"
    chk = 0
    for b in rom[0x134:0x14D]:
        chk = (chk - b - 1) & 0xFF
    assert chk == rom[0x14D]
    assert len(rom) == 32768 << rom[0x148], "declared ROM size must match the file"


@pytest.mark.parametrize("seed", [1, 7, 500, 4242, 60000])
def test_world_generation_matches_reference(seed):
    gb = boot(seed)
    w = g.gen_world(seed)
    assert gb.read("wCycle", 7) == list(w.cycle)
    assert gb.read("wLampRoom") == [w.lamp_room]
    assert gb.read("wExits", 24) == [x for e in w.exits for x in e]
    assert gb.read("wRng", 2) == [w.rng & 255, w.rng >> 8]
    gb.stop()


@pytest.mark.parametrize("seed", [3, 99])
def test_scripted_turns_match_reference_and_render_cleanly(seed):
    gb = boot(seed)
    w = g.gen_world(seed)
    s = g.start(w)
    rnd = random.Random(seed)
    turns = 0
    while not s.done and turns < 8:
        a = rnd.randrange(4)
        s, out = g.step(w, s, a)
        act(gb, a)
        turns += 1
        assert gb.read1("wMB_Room") == s.room
        assert gb.read1("wMB_Outcome") == out
        assert gb.read1("wMB_Lives") == s.lives
        assert gb.read1("wMB_Inv") == g.inv_code(s)
        assert gb.read1("wMB_Turn") == s.turn
        assert gb.read("wRng", 2) == [s.rng & 255, s.rng >> 8]
        assert_vram_matches_shadow(gb)
        gb.press("a")
        if not s.done:
            gb.wait_state(ST_MENU, 2000)
    assert turns >= 5 or s.done
    gb.stop()
