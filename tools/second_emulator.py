#!/usr/bin/env python3
"""Run a self-test ROM on SameBoy's headless tester (DMG model) and on PyBoy, and read the result off the screen.

Both emulators see only the ROM. The verdict and frame counts are computed on the emulated CPU and read back by
matching screen pixels against the project's own font, so this does not depend on either emulator's debug API.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import numpy as np
from PIL import Image
from make_art import font_tile

TESTER = ROOT / ".third_party" / "SameBoy" / "build" / "bin" / "tester" / "sameboy_tester"
CHARS = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GLYPHS = {c: (font_tile(c) == 3) for c in CHARS}


def read_row(img: np.ndarray, row: int) -> str:
    """img: 144x160 boolean ink mask. Unmatched tiles become '?'."""
    out = []
    for col in range(20):
        cell = img[row * 8 : row * 8 + 8, col * 8 : col * 8 + 8]
        out.append(next((c for c, g in GLYPHS.items() if np.array_equal(cell, g)), "?"))
    return "".join(out)


def parse_screen(path) -> dict:
    a = np.array(Image.open(path).convert("L"))
    if a.shape != (144, 160):
        raise ValueError(f"unexpected screenshot shape {a.shape}")
    ink = a < (int(a.min()) + int(a.max())) / 2
    frames = [int(read_row(ink, r)[2:7]) for r in range(4)]
    return {"frames": frames, "verdict": read_row(ink, 5)[2:15].strip()}


def run_sameboy(rom: Path, seconds: int) -> dict:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "selftest.gb"
        shutil.copy(rom, tmp)
        subprocess.run([TESTER, "--dmg", "--length", str(seconds), tmp], capture_output=True, text=True, timeout=1800)
        shot = tmp.with_suffix(".bmp")
        if not shot.exists():
            raise RuntimeError("SameBoy tester wrote no screenshot")
        result = parse_screen(shot)
        if rom.parent.exists():
            shutil.copy(shot, rom.with_suffix(".sameboy.bmp"))
    return result


def run_pyboy(rom: Path, seconds: int) -> dict:
    from run_emulator import GB
    gb = GB(rom)
    gb.tick(seconds * 60)
    gb.pyboy.tick(1, True)
    path = rom.with_suffix(".pyboy.png")
    gb.pyboy.screen.image.convert("RGB").save(path)
    gb.stop()
    return parse_screen(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["V0", "V5Z"])
    a = ap.parse_args()
    results = {}
    for v in a.variants:
        rom = ROOT / "build" / v / "selftest.gb"
        seconds = 320 if v == "V0" else 60
        results[v] = {"sameboy": run_sameboy(rom, seconds), "pyboy": run_pyboy(rom, seconds)}
        print(v, results[v], flush=True)
    (ROOT / "reports" / "second_emulator.json").write_text(json.dumps(results, indent=1))
    ok = all(r[e]["verdict"] == "SELFTEST PASS" for r in results.values() for e in r)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
