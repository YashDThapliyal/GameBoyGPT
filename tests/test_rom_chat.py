"""The whole experience on the real ROM: every response must be exactly what the integer reference generates."""
import re
import shutil
import pytest
from chat_harness import *
from reference import fixed_point as fp


def slots_of(s: cv.State) -> dict[str, str]:
    return {"<NAME>": s.name or "HUMAN", "<LIKE>": s.like or "THAT", "<WORD>": s.word or "THAT", "<NI>": str(s.insults), "<NP>": str(s.praises), "<NT>": str(s.turns)}


def squeeze(t: str) -> str:
    return re.sub(r"\s+([.,!?:])", r"\1", t)


class Tracker:
    """The reference's view of the same conversation."""

    def __init__(self):
        self.state = cv.State()

    def expect(self, gb, parsed: cv.Parsed, seed: int) -> None:
        before, self.state = self.state, cv.apply_turn(self.state, parsed)
        sit = cv.situation(before, self.state)
        ids = dl.prompt_ids(sit)
        assert prompt(gb) == ids, sit
        want = fp.generate(MODEL, ids, greedy=False, rng=seed)
        assert generated(gb) == want["generated"], sit
        assert rom_rng(gb) == want["rng"]
        lines = screen_text(gb)
        full = squeeze(dl.render(want["generated"], slots_of(self.state)))
        assert full.endswith(squeeze(lines)) and len(lines) >= min(len(full), 40), (lines, full)  # long responses scroll in the box
        assert_vram_matches_shadow(gb)


def test_cartridge_header_declares_dmg_mbc5_ram_battery():
    rom = ROM.read_bytes()
    assert rom[0x143] & 0x80 == 0, "no CGB flag"
    assert rom[0x147] == 0x1B and rom[0x149] == 0x03


def test_boots_through_intro_to_menu_on_its_own():
    gb = GB(ROM)
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_MENU, 2000)
    assert gb.read1("wRobotOn") == 1
    gb.stop()


@pytest.mark.parametrize("index", range(len(cv.ACTIONS)))
def test_each_quick_action_generates_the_reference_response(index):
    seed = 0x2000 + index * 91
    gb = boot(seed=seed)
    action(gb, index)
    Tracker().expect(gb, cv.Parsed(cv.ACTION_INTENT[index], "NONE"), seed)
    gb.stop()


def test_a_long_conversation_stays_bit_exact_and_on_screen():
    gb = boot()
    t = Tracker()
    plan = [1, 1, 2, 3, 4, 0, 5, 1, 2, 0, 3, 4]
    for i, a in enumerate(plan):
        seed = 0x3100 + i * 3
        pin(gb, seed)
        action(gb, a)
        t.expect(gb, cv.Parsed(cv.ACTION_INTENT[a], "NONE"), seed)
        next_page(gb)
    assert gb.read1("wMB_Fallbacks") == 0
    gb.stop()


def test_free_text_reaches_the_prompt_and_facts_persist():
    gb = boot()
    t = Tracker()
    for i, text in enumerate(("MY NAME IS BOB", "I LIKE PIZZA", "WHAT IS YOUR CPU", "WILL YOU MARRY ME", "YOU ARE DUMB")):
        seed = 0x4000 + i * 7
        pin(gb, seed)
        say(gb, text)
        t.expect(gb, cv.parse(text), seed)
        next_page(gb)
    assert t.state.name == "BOB" and t.state.like == "PIZZA" and t.state.word == "DUMB"
    assert bytes(gb.read("wName", 3)) == b"BOB" and bytes(gb.read("wWord", 4)) == b"DUMB"
    gb.stop()


def test_keyboard_edits_caps_and_backs_out():
    gb = boot()
    open_keyboard(gb)
    type_text(gb, "AB")
    assert gb.read1("wInputLen") == 2
    gb.press("b")
    assert gb.read1("wInputLen") == 1 and gb.read1("wInput") == ord("A")
    gb.press("b")
    assert gb.read1("wInputLen") == 0
    for _ in range(40):
        gb.press("select")
    assert gb.read1("wInputLen") == cv.MAX_INPUT
    for _ in range(cv.MAX_INPUT):
        gb.press("b")
    gb.press("b")  # B on an empty line goes back
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_MENU, 300)
    assert gb.read1("wTurns") == 0, "backing out must not count as a turn"
    gb.stop()


def test_cursor_wraps_in_all_directions():
    gb = boot()
    open_keyboard(gb)
    gb.press("left")
    assert gb.read1("wKeyCol") == 9
    gb.press("right")
    assert gb.read1("wKeyCol") == 0
    gb.press("up")
    assert gb.read1("wKeyRow") == 4
    gb.press("down")
    assert gb.read1("wKeyRow") == 0
    gb.stop()


def test_third_shutdown_plays_power_down_and_memory_survives():
    gb = boot()
    t = Tracker()
    for i in range(3):
        seed = 0x5000 + i
        pin(gb, seed)
        action(gb, cv.ACTIONS.index("SHUT DOWN"))
        t.expect(gb, cv.Parsed("SHUTDOWN", "NONE"), seed)
        if i < 2:
            next_page(gb)
    assert gb.read1("wMood") == 5
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_POWERDOWN, 200)
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_MENU, 4000)
    assert gb.read1("wShutdowns") == 0 and gb.read1("wTurns") == 3 and gb.read1("wAnger") == 5
    gb.stop()


def _copy_rom(tmp_path):
    rom = tmp_path / "game.gb"
    shutil.copy(ROM, rom)
    shutil.copy(ROM.with_suffix(".sym"), rom.with_suffix(".sym"))
    return rom


def test_memory_persists_through_cartridge_ram(tmp_path):
    rom = _copy_rom(tmp_path)
    gb = boot(rom=rom, ram_file="auto")
    say(gb, "MY NAME IS ADA")
    next_page(gb)
    action(gb, 1)
    gb.tick(60)
    turns, insults = gb.read1("wTurns"), gb.read1("wInsults")
    gb.stop(save=True)
    assert (tmp_path / "game.gb.ram").exists()
    second = GB(rom, ram_file="auto")
    second.wait_for(lambda: second.read1("wReturning") == 1, 300)
    assert second.read1("wTurns") == turns and second.read1("wInsults") == insults
    assert bytes(second.read("wName", 3)) == b"ADA"
    second.stop()


def test_corrupt_save_is_rejected(tmp_path):
    rom = _copy_rom(tmp_path)
    gb = boot(rom=rom, ram_file="auto")
    action(gb, 1)
    gb.tick(60)
    gb.stop(save=True)
    ram = tmp_path / "game.gb.ram"
    data = bytearray(ram.read_bytes())
    assert data[:4] == b"OVR1"
    data[10] ^= 0xFF
    ram.write_bytes(data)
    second = GB(rom, ram_file="auto")
    second.wait_for(lambda: second.read1("wMB_State") == ST_INTRO, 300)
    second.tick(30)
    assert second.read1("wReturning") == 0 and second.read1("wTurns") == 0
    second.stop()


def test_inspector_shows_the_generated_ids():
    gb = boot()
    action(gb, 0)
    ids = generated(gb)
    gb.press("select")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_INSPECT, 300)
    gb.tick(30)
    row = "".join(chr(t + 0x20) if t < 64 else "?" for t in gb.read("wBgMap", 20, 9 * 20))
    assert row.split()[:2] == [f"{ids[0]:03d}", f"{ids[1]:03d}"]
    gb.press("b")
    gb.wait_for(lambda: gb.read1("wMB_State") != ST_INSPECT, 300)
    gb.stop()


def test_input_stays_live_and_animation_runs_during_inference():
    gb = boot()
    select(gb, 1)
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_THINKING, 200)
    f0 = gb.read("hFrames", 2)
    gb.tick(90)
    f1 = gb.read("hFrames", 2)
    assert f0 != f1, "frames keep counting during inference"
    gb.pyboy.button("up", 3)
    gb.tick(6)
    assert gb.read1("wMB_State") in (ST_THINKING, ST_STREAMING, ST_READ)
    wait_response(gb)
    gb.stop()


def test_response_depends_on_conversation_state_at_equal_seed():
    def run(setup):
        gb = boot()
        for a in setup:
            action(gb, a)
            next_page(gb)
        pin(gb, 0x7777)
        action(gb, 0)
        out = prompt(gb), generated(gb)
        gb.stop()
        return out
    calm, rude = run([]), run([1, 1, 1])
    assert calm[0] != rude[0]


def test_presses_during_generation_do_not_dismiss_the_reply():
    gb = boot()
    select(gb, 1)
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_THINKING, 200)
    for button in ("a", "start", "select", "a"):
        gb.press(button)
    wait_response(gb)
    gb.tick(30)
    assert gb.read1("wMB_State") == ST_READ
    assert screen_text(gb)
    gb.stop()


def test_inspector_at_the_reply_comes_back_to_the_same_reply():
    gb = boot()
    action(gb, 1)
    text, expr = screen_text(gb), gb.read1("wExpr")
    gb.press("select")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_INSPECT, 300)
    gb.tick(20)
    gb.press("b")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_READ, 300)
    gb.tick(30)
    assert screen_text(gb) == text and gb.read1("wExpr") == expr
    assert_vram_matches_shadow(gb)
    next_page(gb)
    assert gb.read1("wMB_State") == ST_MENU
    gb.stop()


def test_forgetting_the_player_resets_memory_and_stays_forgotten(tmp_path):
    rom = _copy_rom(tmp_path)
    gb = boot(rom=rom, ram_file="auto")
    for _ in range(3):
        action(gb, cv.ACTIONS.index("SHUT DOWN"))
        if gb.read1("wMood") != 5:
            next_page(gb)
    assert gb.read1("wMood") == 5
    gb.press("select")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_INSPECT, 300)
    gb.tick(20)
    gb.press("start")
    gb.tick(10)
    gb.press("start")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_MENU, 600)
    assert gb.read1("wTurns") == 0 and gb.read1("wMood") == 0 and gb.read1("wRelation") == 1
    gb.stop(save=True)
    second = GB(rom, ram_file="auto")
    second.wait_for(lambda: second.read1("wMB_State") == ST_INTRO, 300)
    second.tick(30)
    assert second.read1("wReturning") == 0
    second.stop()
