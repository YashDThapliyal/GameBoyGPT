"""Plays the real ROM from tests and tools: boot, quick actions, the on-screen keyboard, reading text and tokens."""
from __future__ import annotations
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from run_emulator import GB
from export_weights import from_blob
from reference import conversation as cv
from training import dialogue as dl

VARIANT = os.environ.get("GBGPT_VARIANT", "V6T")
ROM = ROOT / "build" / VARIANT / "gameboygpt.gb"
ST_INTRO, ST_MENU, ST_KEYBOARD, ST_THINKING, ST_STREAMING, ST_READ, ST_INSPECT, ST_POWERDOWN = 1, 2, 3, 4, 5, 6, 7, 8
MODEL = from_blob((ROOT / "generated" / "model.bin").read_bytes())
KEYS = ["ABCDEFGHIJ", "KLMNOPQRST", "UVWXYZ',.?", "0123456789", "!-"]
TEXT_ROWS = (10, 12, 14, 16)


def to_menu(gb: GB, limit: int = 3000) -> None:
    """Skips whatever fixed text is showing."""
    for _ in range(limit // 10):
        if gb.read1("wMB_State") == ST_MENU:
            gb.tick(12)
            return
        gb.press("a")
    raise TimeoutError("never reached the menu")


def boot(rom=ROM, ram_file=None, greedy: bool = False, seed: int = 0x1234) -> GB:
    gb = GB(rom, Path(rom).with_suffix(".sym"), ram_file=ram_file)
    gb.wait_for(lambda: gb.read("wMB_Magic", 4) == [71, 66, 71, 84], 400)
    to_menu(gb)
    pin(gb, seed, greedy)
    return gb


def pin(gb: GB, seed: int, greedy: bool = False) -> None:
    gb.write("wMB_ForceSeed", [1])
    gb.write("wNarrRng", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1 if greedy else 0])


def select(gb: GB, index: int) -> None:
    while gb.read1("wMenuSel") != index:
        cur = gb.read1("wMenuSel")
        if cur // 2 != index // 2:
            gb.press("down")
        else:
            gb.press("right")


def wait_response(gb: GB, limit: int = 60000) -> None:
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_READ, limit)
    gb.tick(10)


def action(gb: GB, index: int) -> None:
    select(gb, index)
    gb.press("a")
    wait_response(gb)


def next_page(gb: GB) -> None:
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") in (ST_MENU, ST_POWERDOWN), 500)
    if gb.read1("wMB_State") == ST_MENU:
        gb.tick(12)


def goto_key(gb: GB, row: int, col: int) -> None:
    while gb.read1("wKeyRow") != row:
        gb.press("down")
    while gb.read1("wKeyCol") != col:
        gb.press("right")


def open_keyboard(gb: GB) -> None:
    select(gb, cv.ACTIONS.__len__())
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_KEYBOARD, 300)
    gb.tick(30)


def type_text(gb: GB, text: str) -> None:
    for ch in text:
        if ch == " ":
            gb.press("select")
            continue
        row = next(i for i, keys in enumerate(KEYS) if ch in keys)
        goto_key(gb, row, KEYS[row].index(ch))
        gb.press("a")


def say(gb: GB, text: str) -> None:
    open_keyboard(gb)
    type_text(gb, text)
    gb.press("start")
    wait_response(gb)


def generated(gb: GB) -> list[int]:
    n = gb.read1("wSeqLen")
    raw = gb.read("wSeq", n * 2)
    return [raw[i] | raw[i + 1] << 8 for i in range(dl.PROMPT_LEN * 2, n * 2, 2)]


def prompt(gb: GB) -> list[int]:
    raw = gb.read("wSeq", dl.PROMPT_LEN * 2)
    return [raw[i] | raw[i + 1] << 8 for i in range(0, dl.PROMPT_LEN * 2, 2)]


def rom_rng(gb: GB) -> int:
    lo, hi = gb.read("wNarrRng", 2)
    return lo | hi << 8


def screen_text(gb: GB) -> str:
    rows = []
    for r in TEXT_ROWS:
        rows.append("".join(chr(t + 0x20) if t < 64 else "?" for t in gb.read("wBgMap", 18, r * 20 + 1)).rstrip())
    return " ".join(x for x in rows if x)


def assert_vram_matches_shadow(gb: GB) -> None:
    gb.tick(8)
    for row in range(18):
        assert [gb.mem[0x9800 + row * 32 + c] for c in range(20)] == gb.read("wBgMap", 20, row * 20), f"row {row}"
