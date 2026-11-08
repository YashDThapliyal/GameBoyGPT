"""Input and UX behaviour: menu navigation, stats overlay, new run path, and screen integrity across many turns."""
import os
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from run_emulator import GB
from reference import game as g

ROM = ROOT / "build" / os.environ.get("GBGPT_VARIANT", "V0") / "gameboygpt.gb"
ST_TITLE, ST_MENU, ST_REVEAL, ST_STATS = 1, 3, 6, 9


@pytest.fixture
def gb():
    b = GB(ROM)
    b.wait_state(ST_TITLE, 2000)
    b.tick(5)
    b.write("wMB_ForceSeed", [1])
    b.write("wMB_Seed", [7, 0])
    b.write("wMB_Greedy", [1])
    b.press("start")
    b.wait_state(ST_MENU, 3000)
    yield b
    b.stop()


def test_dpad_moves_selection_in_a_grid(gb):
    sel = lambda: gb.read1("wMenuSel")
    gb.press("right"); assert sel() == 1
    gb.press("down"); assert sel() == 3
    gb.press("left"); assert sel() == 2
    gb.press("up"); assert sel() == 0
    gb.press("up"); assert sel() == 0, "selection clamps instead of wrapping"


def test_held_button_does_not_repeat_confirm(gb):
    gb.pyboy.button_press("a")
    gb.tick(4)
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_REVEAL, 400000)
    turn = gb.read1("wMB_Turn")
    gb.tick(30)  # still held: the reveal page must wait for a new press
    assert gb.read1("wMB_State") == ST_REVEAL and gb.read1("wMB_Turn") == turn
    gb.pyboy.button_release("a")
    gb.tick(4)


def test_stats_overlay_restores_screen_and_new_run_resets(gb):
    gb.press("a")
    gb.wait_state(ST_REVEAL, 400000)
    gb.tick(8)
    gb.press("a")
    gb.wait_state(ST_MENU, 3000)
    gb.tick(8)
    before = gb.read("wBgMap", 360)
    gb.press("start")
    gb.wait_state(ST_STATS, 60)
    gb.tick(8)
    gb.press("b")
    gb.wait_state(ST_MENU, 60)
    gb.tick(8)
    assert gb.read("wBgMap", 360) == before
    assert gb.read1("wMB_Turn") == 1
    gb.press("start")
    gb.wait_state(ST_STATS, 60)
    gb.press("select")
    gb.wait_for(lambda: gb.read1("wMB_Turn") == 0, 600)
    w = g.gen_world(7)
    gb.wait_state(ST_MENU, 3000)
    assert gb.read1("wMB_Room") == g.FOREST and gb.read1("wLives") == g.START_LIVES
    assert gb.read("wExits", 24) == [x for e in w.exits for x in e]
