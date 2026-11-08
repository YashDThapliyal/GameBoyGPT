#!/usr/bin/env python3
"""Scripted play of the shipping ROM. Saves real emulator screenshots, a real-time GIF and a replay trace.

Exits nonzero if any event differs from the integer reference, or any cap was hit, so `make demo` can't succeed on
canned or broken narration.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]
from PIL import Image, ImageDraw
from story_harness import MODEL, ST_ENDING, ST_GENERATING, ST_INTRO, ST_MENU, ST_REVEAL, ST_TITLE, boot, ds, event_tokens, fp, render, situation_after, st
from run_emulator import GB

FIG = ROOT / "docs" / "figures"
SHIP = ROOT / "build" / "gameboygpt.gb"
BASE = ROOT / "build" / "gameboygpt_v0.gb"
SCALE, GIF_STEP = 3, 6  # 6 LCD frames at 59.73 Hz is 100.5 ms: the GIF's 100 ms delay is real time within 0.5%
SEED = 321
GIF_TURNS = 3
ROUTE = ["Follow the light", "Take the lamp", "Enter the cave", "Light the lamp", "Take the key", "Pray at the altar", "Use the key", "Wake him", "Free him"]
OTHER_ROUTE = ["Hear the voice", "Take his ring", "Wade the shallows", "Walk on", "Climb the wall", "Wake him", "Show the ring"]


class Recorder:
    def __init__(self, gb: GB):
        self.gb, self.frames, self.on = gb, [], True

    def advance(self, n: int) -> None:
        for _ in range(0, n, GIF_STEP):
            self.gb.pyboy.tick(GIF_STEP, True)
            if self.on:
                self.frames.append(self.gb.pyboy.screen.image.convert("RGB").resize((320, 288), Image.NEAREST))

    def until(self, pred, limit: int = 20000) -> None:
        for _ in range(limit):
            if pred():
                return
            self.advance(GIF_STEP)
        sys.exit("DEMO FAILED: script stalled")

    def press(self, b: str) -> None:
        self.gb.pyboy.button(b, 3)
        self.advance(12)


def shot(gb: GB, name: str) -> Image.Image:
    gb.pyboy.tick(1, True)
    img = gb.pyboy.screen.image.convert("RGB").resize((160 * SCALE, 144 * SCALE), Image.NEAREST)
    img.save(FIG / f"screen_{name}.png")
    return img


def play(route: list[str], seed: int, greedy: bool, record: bool) -> tuple[list[dict], GB, Recorder]:
    """Plays a route from power-on, checking every event against the reference."""
    gb = GB(SHIP)
    r = Recorder(gb)
    r.on = record
    gb.wait_state(ST_TITLE, 2000)
    gb.write("wMB_ForceSeed", [1])
    gb.write("wMB_Seed", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1 if greedy else 0])
    r.advance(90)
    shot(gb, "title") if record else None
    r.press("start")
    r.until(lambda: gb.read1("wMB_State") == ST_INTRO)
    r.advance(60)
    shot(gb, "intro") if record else None
    r.press("a")
    r.until(lambda: gb.read1("wMB_State") == ST_MENU)
    r.advance(40)
    shot(gb, "menu") if record else None
    s = st.State()
    narr = seed or 1
    trace = []
    for turn, label in enumerate(route):
        options = st.available(s)
        i = [c.label for c in options].index(label)
        s, situation = situation_after(s, options[i])
        want = fp.generate(MODEL, ds.prompt_ids(*situation), greedy=greedy, rng=narr)
        narr = want["rng"]
        r.on = record and turn < GIF_TURNS
        while gb.read1("wMenuSel") < i:
            r.press("down")
        r.press("a")
        if record and turn == 1:
            r.until(lambda: gb.read1("wMB_NumTokens") >= 4 and gb.read1("wMB_State") == ST_GENERATING)
            shot(gb, "thinking")
        r.until(lambda: gb.read1("wMB_State") == ST_REVEAL)
        r.advance(40)
        got = event_tokens(gb)
        if got != want["tokens"]:
            sys.exit(f"DEMO FAILED: ROM tokens {got} != reference {want['tokens']}")
        frames = gb.read("wMB_EventFrames", 2)
        ids = [t for t in got[ds.PROMPT_LEN:] if t != ds.EOS]
        trace.append({"turn": turn + 1, "place": st.BY_ID[s.scene].title, "choice": label, "beat": options[i].beat, "input_ids": got[:ds.PROMPT_LEN], "generated_ids": got[ds.PROMPT_LEN:],
                      "text": render(got[ds.PROMPT_LEN:]), "on_device_frames": frames[0] | frames[1] << 8, "strict_valid": ds.check_sentence(situation, ids)["strict"]})
        if record and turn == 1:
            shot(gb, "narrative")
        r.on = record and turn < GIF_TURNS
        r.press("a")
        r.until(lambda: gb.read1("wMB_State") in (ST_MENU, ST_ENDING))
        if record and turn == 3:
            gb.tick(20)
            shot(gb, "items_change_choices")
            gb.press("select")
            gb.tick(14)
            shot(gb, "stats_ship")
            gb.press("b")
            gb.tick(10)
    if gb.read1("wMB_Fallbacks") or gb.read1("wMB_Placeholder"):
        sys.exit("DEMO FAILED: cap or placeholder used")
    if not st.BY_ID[s.scene].ending:
        sys.exit("DEMO FAILED: route does not reach an ending")
    gb.tick(20)
    return trace, gb, r


def baseline_stats() -> None:
    gb = boot(BASE, SEED, True)
    s = st.State()
    for _ in range(3):
        option = st.available(s)[0]
        s = st.step(s, option)
        gb.press("a")
        gb.wait_state(ST_REVEAL, 400000)
        gb.tick(10)
        gb.press("a")
        gb.wait_state(ST_MENU, 3000)
        gb.tick(4)
    gb.tick(20)
    gb.press("select")
    gb.tick(14)
    shot(gb, "stats_v0")
    gb.stop()


def hero() -> None:
    """A plain original frame around a real screenshot. It is labelled, and it is not a picture of hardware."""
    shot_img = Image.open(FIG / "screen_narrative.png")
    W, H = shot_img.width + 96, shot_img.height + 130
    img = Image.new("RGB", (W, H), (196, 196, 188))
    d = ImageDraw.Draw(img)
    d.rectangle((24, 24, W - 24, shot_img.height + 72), fill=(82, 84, 96))
    img.paste(shot_img, (48, 48))
    d.text((48, shot_img.height + 84), "Emulator screenshot (PyBoy, DMG mode). Text generated by the on-cartridge transformer.", fill=(30, 30, 30))
    img.save(FIG / "hero.png")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    trace, gb, r = play(ROUTE, SEED, False, True)
    shot(gb, "ending")
    gb.stop()
    if not r.frames:
        sys.exit("DEMO FAILED: no frames captured")
    label = Image.new("RGB", (320, 288 + 18), (20, 20, 20))
    sha = hashlib.sha256(SHIP.read_bytes()).hexdigest()[:12]
    frames = []
    for f in r.frames:
        canvas = label.copy()
        canvas.paste(f, (0, 0))
        ImageDraw.Draw(canvas).text((4, 291), f"PyBoy DMG emulator, real time  rom {sha}", fill=(220, 220, 210))
        frames.append(canvas.quantize(8))
    frames[0].save(FIG / "demo.gif", save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=True)
    other, gb2, _ = play(OTHER_ROUTE, SEED + 1, False, False)
    gb2.stop()
    baseline_stats()
    hero()
    out = {"rom_sha256": hashlib.sha256(SHIP.read_bytes()).hexdigest(), "seed": SEED, "journey": trace, "other_journey": other}
    (ROOT / "reports" / "demo_trace.json").write_text(json.dumps(out, indent=1))
    for t in trace + other:
        print(f"{t['turn']:2} {t['place']:11} {t['choice']:19} {t['text']}")
    if not all(t["strict_valid"] for t in trace + other):
        sys.exit("DEMO FAILED: invalid event")


if __name__ == "__main__":
    main()
