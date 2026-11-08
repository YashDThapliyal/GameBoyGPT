"""Input and UX behaviour: menu movement, one job per screen, stats page, new run, and ending tracking."""
import pytest
from story_harness import *


@pytest.fixture
def gb():
    b = boot()
    yield b
    b.stop()


def test_up_and_down_move_the_pointer_and_stop_at_the_ends(gb):
    sel = lambda: gb.read1("wMenuSel")
    n = gb.read1("wNumChoices")
    assert sel() == 0
    gb.press("up")
    assert sel() == 0, "does not wrap upward"
    for i in range(1, n):
        gb.press("down")
        assert sel() == i
    gb.press("down")
    assert sel() == n - 1, "does not run off the list"


def test_choices_are_listed_on_double_spaced_rows(gb):
    gb.tick(8)
    options = st.available(st.State())
    for i, c in enumerate(options):
        drawn = "".join(chr(t + 0x20) for t in gb.read("wBgMap", len(c.label), (8 + 2 * i) * 20 + 2))
        assert drawn == c.label


def test_held_button_does_not_repeat_confirm(gb):
    gb.pyboy.button_press("a")
    gb.tick(4)
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_REVEAL, 400000)
    turn = gb.read1("wMB_Turn")
    gb.tick(30)  # still held: the story page must wait for a new press
    assert gb.read1("wMB_State") == ST_REVEAL and gb.read1("wMB_Turn") == turn
    gb.pyboy.button_release("a")
    gb.tick(4)


def test_stats_page_restores_screen_and_new_run_resets(gb):
    choose(gb, 0)
    next_page(gb)
    gb.tick(8)
    before = gb.read("wBgMap", 360)
    gb.press("start")
    gb.wait_state(ST_STATS, 60)
    gb.tick(14)
    assert gb.read("wBgMap", 360) != before
    gb.press("b")
    gb.wait_state(ST_MENU, 60)
    gb.tick(8)
    assert gb.read("wBgMap", 360) == before
    assert gb.read1("wMB_Turn") == 1
    gb.press("start")
    gb.wait_state(ST_STATS, 60)
    gb.press("select")
    gb.wait_for(lambda: gb.read1("wMB_Turn") == 0, 600)
    gb.wait_state(ST_INTRO, 3000)
    gb.press("a")
    gb.wait_state(ST_MENU, 600)
    assert gb.read1("wMB_Room") == SCENE_INDEX[st.START] and gb.read1("wFlags") == 0 and gb.read1("wWounds") == 0


def test_story_lines_keep_a_blank_row_between_them(gb):
    choose(gb, 0)
    for row in (9, 11, 13, 15):
        assert gb.read("wBgMap", 20, row * 20) == [0] * 20, f"row {row} must stay blank between story lines"


def test_endings_found_counts_across_runs(gb):
    def to_ending(labels):
        s = st.State()
        for label in labels:
            options = st.available(s)
            i = next(n for n, c in enumerate(options) if c.label == label)
            s = st.step(s, options[i])
            choose(gb, i)
            next_page(gb)
    flee = ["Hear the voice", "Leave him", "Wade the shallows", "Walk on", "Give up and flee"]
    to_ending(flee)
    assert gb.read1("wMB_State") == ST_ENDING
    gb.tick(10)
    assert bin(gb.read1("wEndMask")).count("1") == 1
    gb.press("a")
    gb.wait_state(ST_TITLE, 2000)
    gb.tick(5)
    gb.press("start")
    gb.wait_state(ST_INTRO, 3000)
    gb.press("a")
    gb.wait_state(ST_MENU, 600)
    to_ending(flee)
    assert bin(gb.read1("wEndMask")).count("1") == 1, "the same ending twice still counts once"
