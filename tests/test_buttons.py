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
ST_TITLE, ST_INTRO, ST_MENU, ST_REVEAL, ST_STATS = 1, 2, 3, 6, 9


@pytest.fixture
def gb():
    b = GB(ROM)
    b.wait_state(ST_TITLE, 2000)
    b.tick(5)
    b.write("wMB_ForceSeed", [1])
    b.write("wMB_Seed", [7, 0])
    b.write("wMB_Greedy", [1])
    b.press("start")
    b.wait_state(ST_INTRO, 3000)
    b.press("a")
    b.wait_state(ST_MENU, 600)
    yield b
    b.stop()


def test_each_direction_selects_the_action_drawn_on_that_side(gb):
    sel = lambda: gb.read1("wMenuSel")
    assert sel() == g.FORWARD, "a new run starts on AHEAD"
    for button, action in (("left", g.LEFT), ("right", g.RIGHT), ("down", g.SEARCH), ("up", g.FORWARD)):
        gb.press(button)
        assert sel() == action
        gb.press(button)
        assert sel() == action, "pressing again keeps the selection"


def test_selected_label_is_highlighted(gb):
    gb.press("down")
    gb.tick(6)
    row = gb.read("wBgMap", 6, 14 * 20 + 9)
    assert all(t >= 116 for t in row), "SEARCH is drawn in the inverse font"
    row = gb.read("wBgMap", 5, 10 * 20 + 9)
    assert all(t < 96 for t in row), "AHEAD is back to the normal font"


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
    gb.wait_state(ST_INTRO, 3000)
    gb.press("a")
    gb.wait_state(ST_MENU, 600)
    assert gb.read1("wMB_Room") == g.FOREST and gb.read1("wLives") == g.START_LIVES
    assert gb.read("wExits", 24) == [x for e in w.exits for x in e]


def test_stats_page_fits_and_story_lines_are_double_spaced(gb):
    gb.press("a")
    gb.wait_state(ST_REVEAL, 400000)
    gb.tick(8)
    for row in (9, 11, 13, 15):
        assert gb.read("wBgMap", 20, row * 20) == [0] * 20, f"row {row} must stay blank between story lines"
