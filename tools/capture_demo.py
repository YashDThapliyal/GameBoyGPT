#!/usr/bin/env python3
"""Scripted play of the shipping ROM. Saves real emulator screenshots, a real-time GIF and a replay trace.

Exits nonzero if any event differs from the integer reference, or any placeholder or cap was hit, so
`make demo` can't succeed on canned or broken narration.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from PIL import Image, ImageDraw
from run_emulator import GB
from export_weights import from_blob
from reference import fixed_point as fp, game as g
from training import dataset as ds

FIG = ROOT / "docs" / "figures"
SHIP = ROOT / "build" / "gameboygpt.gb"
BASE = ROOT / "build" / "gameboygpt_v0.gb"
MODEL = from_blob((ROOT / "generated" / "model.bin").read_bytes())
BUTTONS = {g.LEFT: ("left",), g.RIGHT: ("right",), g.FORWARD: ("up",), g.SEARCH: ("down",)}
ST_TITLE, ST_MENU, ST_GEN, ST_REVEAL, ST_ENDING, ST_STATS = 1, 3, 5, 6, 8, 9
SCALE, GIF_STEP = 3, 6  # 6 LCD frames at 59.73 Hz is 100.5 ms: the GIF's 100 ms delay is real time within 0.5%
SEED = 321


class Recorder:
    def __init__(self, gb):
        self.gb, self.frames, self.on = gb, [], True

    def advance(self, n):
        for _ in range(0, n, GIF_STEP):
            self.gb.pyboy.tick(GIF_STEP, True)
            if self.on:
                self.frames.append(self.gb.pyboy.screen.image.convert("RGB").resize((320, 288), Image.NEAREST))

    def until(self, pred, limit=20000):
        for _ in range(limit):
            if pred():
                return
            self.advance(GIF_STEP)
        raise TimeoutError("demo script stalled")

    def press(self, b):
        self.gb.pyboy.button(b, 3)
        self.advance(12)


def shot(gb, name):
    gb.pyboy.tick(1, True)
    img = gb.pyboy.screen.image.convert("RGB").resize((160 * SCALE, 144 * SCALE), Image.NEAREST)
    img.save(FIG / f"screen_{name}.png")
    return img


def boot(rom, seed, greedy):
    gb = GB(rom)
    gb.wait_state(ST_TITLE, 2000)
    gb.tick(5)
    gb.write("wMB_ForceSeed", [1])
    gb.write("wMB_Seed", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1 if greedy else 0])
    return gb


def text(tokens):
    return " ".join(ds.VOCAB[t].lower() for t in tokens if t != ds.EOS).capitalize() + "."


def play_gif_run() -> list[dict]:
    gb = boot(SHIP, SEED, False)
    r = Recorder(gb)
    r.advance(90)
    shot(gb, "title")
    r.press("start")
    r.until(lambda: gb.read1("wMB_State") == ST_MENU)
    r.advance(60)
    shot(gb, "menu")
    w = g.gen_world(SEED)
    s = g.start(w)
    narr = w.rng ^ 0xA5A5
    trace = []
    turn = 0
    while not s.done:
        a = g.next_action(w, s)
        s, out = g.step(w, s, a)
        situation = (s.room, g.inv_code(s), a, out)
        want = fp.generate(MODEL, ds.prompt_ids(*situation), greedy=False, rng=narr)
        narr = want["rng"]
        r.on = turn < 3
        for b in BUTTONS[a]:
            r.press(b)
        r.press("a")
        if turn == 1:
            r.until(lambda: gb.read1("wMB_NumTokens") >= 4 and gb.read1("wMB_State") == ST_GEN)
            shot(gb, "thinking")
        r.until(lambda: gb.read1("wMB_State") == ST_REVEAL)
        r.advance(40)
        n = gb.read1("wMB_NumTokens")
        got = gb.read("wMB_LastTokens", 5 + n)
        if got != want["tokens"]:
            sys.exit(f"DEMO FAILED: ROM tokens {got} != reference {want['tokens']}")
        frames = gb.read("wMB_EventFrames", 2)
        trace.append({"turn": turn + 1, "room": g.ROOMS[s.room], "action": g.ACTIONS[a], "outcome": g.OUTCOMES[out], "input_ids": got[:5], "generated_ids": got[5:],
                      "text": text(got[5:]), "on_device_frames": frames[0] | frames[1] << 8, "strict_valid": ds.check_sentence(situation, [t for t in got[5:] if t != ds.EOS])["strict"]})
        if turn == 1:
            shot(gb, "narrative")
        if turn == 2:
            r.on = True
            r.advance(30)
            r.on = False
        turn += 1
        r.press("a")
        r.until(lambda: gb.read1("wMB_State") in (ST_MENU, ST_ENDING))
        if s.done:
            break
        if turn == 3:
            gb.tick(20)
            gb.press("start")
            gb.tick(12)
            shot(gb, "stats_ship")
            gb.press("b")
            gb.tick(10)
    gb.tick(20)
    shot(gb, "ending")
    if gb.read1("wMB_Fallbacks") or gb.read1("wMB_Placeholder"):
        sys.exit("DEMO FAILED: fallback or placeholder used")
    gb.stop()
    if not r.frames:
        sys.exit("DEMO FAILED: no frames captured")
    label = Image.new("RGB", (320, 288 + 18), (20, 20, 20))
    frames = []
    sha = hashlib.sha256(SHIP.read_bytes()).hexdigest()[:12]
    for f in r.frames:
        canvas = label.copy()
        canvas.paste(f, (0, 0))
        ImageDraw.Draw(canvas).text((4, 291), f"PyBoy DMG emulator, real time  rom {sha}", fill=(220, 220, 210))
        frames.append(canvas.quantize(8))
    frames[0].save(FIG / "demo.gif", save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=True)
    return trace


def baseline_stats():
    gb = boot(BASE, SEED, False)
    gb.press("start")
    gb.wait_state(ST_MENU, 3000)
    w = g.gen_world(SEED)
    s = g.start(w)
    for _ in range(3):
        a = g.next_action(w, s)
        s, _o = g.step(w, s, a)
        for b in BUTTONS[a]:
            gb.press(b)
        gb.press("a")
        gb.wait_state(ST_REVEAL, 400000)
        gb.tick(10)
        gb.press("a")
        gb.wait_state(ST_MENU, 3000)
    gb.tick(20)
    gb.press("start")
    gb.tick(12)
    shot(gb, "stats_v0")
    gb.stop()


def action_pair() -> dict:
    """Same seed and state, two actions, on the shipping ROM: inputs and neural outputs both recorded."""
    res = {}
    imgs = []
    for a in (g.FORWARD, g.SEARCH):
        gb = boot(SHIP, SEED, True)
        gb.press("start")
        gb.wait_state(ST_MENU, 3000)
        w = g.gen_world(SEED)
        s, out = g.step(w, g.start(w), a)
        for b in BUTTONS[a]:
            gb.press(b)
        gb.press("a")
        gb.wait_state(ST_REVEAL, 400000)
        gb.tick(10)
        n = gb.read1("wMB_NumTokens")
        got = gb.read("wMB_LastTokens", 5 + n)
        if got != fp.generate(MODEL, ds.prompt_ids(s.room, g.inv_code(s), a, out))["tokens"]:
            sys.exit("DEMO FAILED: action pair mismatch")
        res[g.ACTIONS[a]] = {"input_ids": got[:5], "generated_ids": got[5:], "text": text(got[5:]), "outcome": g.OUTCOMES[out], "room": g.ROOMS[s.room]}
        gb.pyboy.tick(1, True)
        imgs.append(gb.pyboy.screen.image.convert("RGB").resize((320, 288), Image.NEAREST))
        gb.stop()
    sheet = Image.new("RGB", (660, 288), (255, 255, 255))
    sheet.paste(imgs[0], (0, 0))
    sheet.paste(imgs[1], (340, 0))
    sheet.save(FIG / "action_pair.png")
    return res


def hero():
    """A plain original frame around a real screenshot. It is labelled, and it is not a picture of hardware."""
    shot_img = Image.open(FIG / "screen_narrative.png")
    W, H = shot_img.width + 96, shot_img.height + 130
    img = Image.new("RGB", (W, H), (196, 196, 188))
    d = ImageDraw.Draw(img)
    d.rectangle((24, 24, W - 24, shot_img.height + 72), fill=(82, 84, 96))
    img.paste(shot_img, (48, 48))
    d.text((48, shot_img.height + 84), "Emulator screenshot (PyBoy, DMG mode). Text generated by the on-cartridge transformer.", fill=(30, 30, 30))
    img.save(FIG / "hero.png")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    trace = play_gif_run()
    baseline_stats()
    pair = action_pair()
    hero()
    out = {"rom_sha256": hashlib.sha256(SHIP.read_bytes()).hexdigest(), "seed": SEED, "journey": trace, "action_pair": pair}
    (ROOT / "reports" / "demo_trace.json").write_text(json.dumps(out, indent=1))
    for t in trace:
        print(f"{t['turn']:2} {t['room']:7} {t['action']:7} {t['outcome']:7} {t['text']}")
    print(json.dumps(pair, indent=0))
    if not all(t["strict_valid"] for t in trace) or len(trace) < 5:
        sys.exit("DEMO FAILED: invalid event or journey shorter than 5 turns")


if __name__ == "__main__":
    main()
