"""Shared helpers for playing the story ROM from tests and tools: boot, choose by index, read tokens and text."""
from __future__ import annotations
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from run_emulator import GB
from export_weights import from_blob
from reference import fixed_point as fp, story as st
from training import dataset as ds

VARIANT = os.environ.get("GBGPT_VARIANT", "V0")
ROM = ROOT / "build" / VARIANT / "gameboygpt.gb"
ST_TITLE, ST_INTRO, ST_MENU, ST_GENERATING, ST_REVEAL, ST_ENDING, ST_STATS = 1, 2, 3, 5, 6, 8, 9
SCENE_INDEX = {s.id: i for i, s in enumerate(st.SCENES)}
MODEL = from_blob((ROOT / "generated" / "model.bin").read_bytes())


def boot(rom=ROM, seed: int = 7, greedy: bool = True, sym=None) -> GB:
    gb = GB(rom, sym or Path(rom).with_suffix(".sym"))
    gb.wait_state(ST_TITLE, 2000)
    gb.tick(5)
    gb.write("wMB_ForceSeed", [1])
    gb.write("wMB_Seed", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1 if greedy else 0])
    gb.press("start")
    gb.wait_state(ST_INTRO, 3000)
    gb.press("a")
    gb.wait_state(ST_MENU, 600)
    return gb


def select(gb: GB, index: int) -> None:
    """Move the pointer to a menu row from wherever it is."""
    while gb.read1("wMenuSel") > index:
        gb.press("up")
    while gb.read1("wMenuSel") < index:
        gb.press("down")


def choose(gb: GB, index: int) -> None:
    select(gb, index)
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_REVEAL, 400000)
    gb.tick(8)


def next_page(gb: GB) -> None:
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") in (ST_MENU, ST_ENDING), 3000)


def event_tokens(gb: GB) -> list[int]:
    return gb.read("wMB_LastTokens", ds.PROMPT_LEN + gb.read1("wMB_NumTokens"))


def visible_text(gb: GB) -> str:
    rows = []
    for r in (8, 10, 12, 14):
        rows.append("".join(chr(t + 0x20) if t < 96 else "?" for t in gb.read("wBgMap", 19, r * 20 + 1)).rstrip())
    return " ".join(x for x in rows if x)


def render(tokens: list[int]) -> str:
    """What the ROM should draw for these ids: sentence case, full stops attached."""
    out, cap = "", True
    for t in tokens:
        if t == ds.EOS:
            continue
        w = ds.VOCAB[t].lower()
        if w == ".":
            out += "."
            cap = True
            continue
        if cap:
            w = w[0].upper() + w[1:]
            cap = False
        out += (" " if out else "") + w
    return out


def assert_clean_screen(gb: GB) -> None:
    gb.tick(8)
    for row in range(18):
        assert [gb.mem[0x9800 + row * 32 + c] for c in range(20)] == gb.read("wBgMap", 20, row * 20), f"row {row}"


def situation_after(state: st.State, choice: st.Choice) -> tuple[st.State, tuple[str, int, int]]:
    n = st.step(state, choice)
    fate = ds.DYING if n.wounds >= st.MAX_WOUNDS else ds.LIVE
    return n, (choice.beat, n.flags, fate)
