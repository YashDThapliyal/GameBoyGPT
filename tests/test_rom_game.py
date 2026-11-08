"""ROM boots in DMG mode, and the assembly story engine tracks reference/story.py through every kind of path."""
import random
import pytest
from story_harness import *


def test_header_is_dmg_mbc5_with_valid_checksum():
    rom = ROM.read_bytes()
    assert rom[0x143] == 0x00, "CGB flag must be clear"
    assert rom[0x147] == 0x19, "MBC5"
    chk = 0
    for b in rom[0x134:0x14D]:
        chk = (chk - b - 1) & 0xFF
    assert chk == rom[0x14D]
    assert len(rom) == 32768 << rom[0x148], "declared ROM size must match the file"


def assert_state(gb, s):
    assert gb.read1("wMB_Room") == SCENE_INDEX[s.scene]
    assert gb.read1("wMB_Inv") == s.flags
    assert gb.read1("wMB_Lives") == s.wounds
    assert gb.read1("wMB_Turn") == s.turn


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_random_playthroughs_match_reference(seed):
    gb = boot(greedy=True, seed=seed)
    rnd = random.Random(seed)
    s = st.State()
    while not st.BY_ID[s.scene].ending:
        options = st.available(s)
        assert gb.read1("wNumChoices") == len(options)
        i = rnd.randrange(len(options))
        s = st.step(s, options[i])
        choose(gb, i)
        assert_state(gb, s)
        assert_clean_screen(gb)
        next_page(gb)
    assert gb.read1("wMB_State") == ST_ENDING
    gb.stop()


def test_menu_only_offers_what_you_have_earned():
    """Same scene, different earlier choice, different menu: the lamp is what opens the cave."""
    def reach_cave(first):
        gb = boot()
        s = st.State()
        for label in first:
            options = st.available(s)
            i = next(n for n, c in enumerate(options) if c.label == label)
            s = st.step(s, options[i])
            choose(gb, i)
            next_page(gb)
        return gb, s
    with_lamp, a = reach_cave(["Follow the light", "Take the lamp", "Enter the cave"])
    with_sword, b = reach_cave(["Follow the light", "Take the sword", "Enter the cave"])
    assert a.scene == b.scene == "cave"
    assert "Light the lamp" in [c.label for c in st.available(a)]
    assert "Light the lamp" not in [c.label for c in st.available(b)]
    assert with_lamp.read1("wNumChoices") == len(st.available(a))
    assert with_sword.read1("wNumChoices") == len(st.available(b))
    assert with_lamp.read("wChoices", 2) != with_sword.read("wChoices", 2)
    with_lamp.stop()
    with_sword.stop()


def test_three_wounds_end_the_run_in_the_rom():
    gb = boot()
    s = st.State()
    route = ["Hear the voice", "Leave him", "Cross the bridge", "Take the blade", "Force the bars"]
    route_alt = ["Follow the light", "Take the sword", "Cross the bridge", "Pray at the altar", "Force the bars", "Strike him", "Fight on"]
    for label in route_alt:
        options = st.available(s)
        i = next(n for n, c in enumerate(options) if c.label == label)
        s = st.step(s, options[i])
        choose(gb, i)
        assert_state(gb, s)
        next_page(gb)
        if st.BY_ID[s.scene].ending:
            break
    assert s.scene == st.DEATH_SCENE and gb.read1("wMB_State") == ST_ENDING
    gb.stop()
