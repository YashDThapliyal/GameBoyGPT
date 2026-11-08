#!/usr/bin/env python3
"""Generate all original 2-bit art procedurally and pack it as RGBDS data.

No external art or font is used: every pixel is produced by this script, which is the
licence audit for assets/tiles/. Shades: 0 lightest .. 3 darkest (BGP=$E4).
Outputs generated/assets.asm, generated/assets.inc and PNG previews in assets/tiles/.
"""
from __future__ import annotations
import random
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GEN, PREVIEW = ROOT / "generated", ROOT / "assets" / "tiles"
SCENE_W, SCENE_H = 160, 48
FIRST_UI_TILE, FIRST_INV_TILE, FIRST_SCENE_TILE = 96, 116, 156
TITLE_FIRST_TILE = 156
ART_TILE_BUDGET = 100
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32
PREVIEW_RGB = [(224, 232, 208), (160, 176, 136), (84, 104, 80), (24, 32, 28)]

# 5x7 glyphs drawn for this project, emboldened below; ASCII $20..$5F.
GLYPHS = {
    " ": "00 00 00 00 00 00 00", "!": "04 04 04 04 04 00 04", '"': "0A 0A 00 00 00 00 00",
    "#": "0A 1F 0A 0A 1F 0A 00", "$": "04 0F 14 0E 05 1E 04", "%": "19 19 02 04 08 13 13",
    "&": "0C 12 14 08 15 12 0D", "'": "04 04 08 00 00 00 00", "(": "02 04 08 08 08 04 02",
    ")": "08 04 02 02 02 04 08", "*": "00 15 0E 1F 0E 15 00", "+": "00 04 04 1F 04 04 00",
    ",": "00 00 00 00 04 04 08", "-": "00 00 00 1F 00 00 00", ".": "00 00 00 00 00 0C 0C",
    "/": "01 01 02 04 08 10 10", "0": "0E 11 13 15 19 11 0E", "1": "04 0C 04 04 04 04 0E",
    "2": "0E 11 01 06 08 10 1F", "3": "1F 02 04 02 01 11 0E", "4": "02 06 0A 12 1F 02 02",
    "5": "1F 10 1E 01 01 11 0E", "6": "06 08 10 1E 11 11 0E", "7": "1F 01 02 04 08 08 08",
    "8": "0E 11 11 0E 11 11 0E", "9": "0E 11 11 0F 01 02 0C", ":": "00 0C 0C 00 0C 0C 00",
    ";": "00 0C 0C 00 0C 04 08", "<": "02 04 08 10 08 04 02", "=": "00 00 1F 00 1F 00 00",
    ">": "08 04 02 01 02 04 08", "?": "0E 11 01 02 04 00 04", "@": "0E 11 17 15 17 10 0E",
    "A": "0E 11 11 1F 11 11 11", "B": "1E 11 11 1E 11 11 1E", "C": "0E 11 10 10 10 11 0E",
    "D": "1C 12 11 11 11 12 1C", "E": "1F 10 10 1E 10 10 1F", "F": "1F 10 10 1E 10 10 10",
    "G": "0E 11 10 17 11 11 0F", "H": "11 11 11 1F 11 11 11", "I": "0E 04 04 04 04 04 0E",
    "J": "07 02 02 02 02 12 0C", "K": "11 12 14 18 14 12 11", "L": "10 10 10 10 10 10 1F",
    "M": "11 1B 15 15 11 11 11", "N": "11 19 15 13 11 11 11", "O": "0E 11 11 11 11 11 0E",
    "P": "1E 11 11 1E 10 10 10", "Q": "0E 11 11 11 15 12 0D", "R": "1E 11 11 1E 14 12 11",
    "S": "0F 10 10 0E 01 01 1E", "T": "1F 04 04 04 04 04 04", "U": "11 11 11 11 11 11 0E",
    "V": "11 11 11 11 11 0A 04", "W": "11 11 11 15 15 1B 11", "X": "11 11 0A 04 0A 11 11",
    "Y": "11 11 11 0A 04 04 04", "Z": "1F 01 02 04 08 10 1F", "[": "0E 08 08 08 08 08 0E",
    "\\": "10 10 08 04 02 01 01", "]": "0E 02 02 02 02 02 0E", "^": "04 0E 15 04 04 04 04",
    "_": "00 00 00 00 00 00 1F", "`": "08 04 00 00 00 00 00",
    # Lowercase: x-height of 5 rows, row 7 is available for descenders, so lines read with visible gaps.
    "a": "00 00 0E 01 0F 11 0F", "b": "10 10 1E 11 11 11 1E", "c": "00 00 0E 11 10 11 0E", "d": "01 01 0F 11 11 11 0F",
    "e": "00 00 0E 11 1F 10 0E", "f": "06 09 08 1C 08 08 08", "g": "00 00 0F 11 11 0F 01 0E", "h": "10 10 16 19 11 11 11",
    "i": "04 00 0C 04 04 04 0E", "j": "02 00 06 02 02 12 0C", "k": "10 10 12 14 18 14 12", "l": "0C 04 04 04 04 04 0E",
    "m": "00 00 1A 15 15 11 11", "n": "00 00 16 19 11 11 11", "o": "00 00 0E 11 11 11 0E", "p": "00 00 1E 11 11 11 1E 10",
    "q": "00 00 0F 11 11 11 0F 01", "r": "00 00 16 19 10 10 10", "s": "00 00 0F 10 0E 01 1E", "t": "08 08 1C 08 08 09 06",
    "u": "00 00 11 11 11 13 0D", "v": "00 00 11 11 11 0A 04", "w": "00 00 11 11 15 15 0A", "x": "00 00 11 0A 04 0A 11",
    "y": "00 00 11 11 11 0F 01 0E", "z": "00 00 1F 02 04 08 1F", "{": "02 04 04 08 04 04 02", "|": "04 04 04 04 04 04 04",
    "}": "08 04 04 02 04 04 08", "~": "00 00 08 15 02 00 00", "\x7f": "00 00 00 00 00 00 00",
}
INV_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/-"


# Bold glyphs whose automatic emboldening would fill in their counters, drawn by hand on the 6-wide grid.
BOLD_OVERRIDES = {
    "M": ["110001", "111011", "111111", "110101", "110001", "110001", "110001"],
    "W": ["110001", "110001", "110001", "110101", "111111", "111011", "110001"],
    "N": ["110011", "111011", "111011", "110111", "110111", "110011", "110011"],
    "G": ["011110", "110011", "110000", "110111", "110011", "110011", "011111"],
    "V": ["110011", "110011", "110011", "110011", "011110", "011110", "001100"],
    "m": ["000000", "000000", "111110", "110101", "110101", "110101", "110101"],
    "w": ["000000", "000000", "110101", "110101", "110101", "110101", "011110"],
    "0": ["011110", "110011", "110011", "110011", "110011", "110011", "011110"],
}


def glyph_rows(ch: str, bold: bool = True) -> np.ndarray:
    """8x8 boolean glyph, 2-pixel vertical strokes so text survives scaling. Rows 0-6, descenders in row 7."""
    out = np.zeros((8, 8), bool)
    if ch in BOLD_OVERRIDES:
        for y, row in enumerate(BOLD_OVERRIDES[ch]):
            for x, c in enumerate(row):
                out[y, x + 1] = c == "1"
        return out
    for y, hx in enumerate(GLYPHS[ch].split()):
        v = int(hx, 16)
        v6 = v << 1 | v
        for x in range(6):
            out[y, x + 1] = bool(v6 & (1 << (5 - x)))
    return out


def font_tile(ch: str, ink: int = 3, paper: int = 0) -> np.ndarray:
    return np.where(glyph_rows(ch), ink, paper)


def inverse_tile(ch: str) -> np.ndarray:
    """Light-on-dark capital, 6 pixels tall with dark margins, so its outline holds against any neighbouring row."""
    g = glyph_rows(ch)
    out = np.full((8, 8), 3)
    for y, src in enumerate((0, 1, 2, 3, 4, 6)):
        out[y + 1] = np.where(g[src], 0, 3)
    return out


def tile_from(rows: list[str]) -> np.ndarray:
    """Hand-drawn 8x8 tile: '.'=0 ':'=1 '+'=2 '#'=3."""
    m = {".": 0, ":": 1, "+": 2, "#": 3}
    return np.array([[m[c] for c in r] for r in rows])


def ui_tiles() -> list[np.ndarray]:
    t = [
        tile_from(["........", "........", "........", "########", "++++++++", "........", "........", "........"]),  # rule
        tile_from(["########", "##.#.###", "#.....##", "#.....##", "##...###", "###.####", "########", "########"]),  # heart
        tile_from(["########", "##..####", "#.##.###", "##..####", "###.####", "###..###", "###.####", "########"]),  # key
        tile_from(["###..###", "##....##", "##.++.##", "##.++.##", "##....##", "###..###", "##....##", "########"]),  # lamp
        tile_from(["########"] * 8),  # band solid
    ]
    for fill in range(5):  # progress bar 0/4 .. 4/4
        rows = []
        for y in range(8):
            if y in (0, 7):
                rows.append("########")
            else:
                rows.append("".join("#" if x < fill * 2 else ":" for x in range(8)))
        t.append(tile_from(rows))
    t.append(tile_from(["........", ".##.....", ".####...", ".######.", ".######.", ".####...", ".##.....", "........"]))  # cursor
    t.append(tile_from(["........", "........", "#######.", ".#####..", "..###...", "...#....", "........", "........"]))  # continue arrow
    for rows in (  # spinner: real progress marker frames animated by the VBlank ISR while the CPU computes
        ["...##...", "...##...", "........", ".#....#.", ".#....#.", "........", "...++...", "...++..."],
        [".....##.", ".....##.", "........", "#......:", "#......:", "........", ".++.....", ".++....."],
    ):
        t.append(tile_from(rows))
    t.append(tile_from(["###..###", "#..##..#", "#.#..#.#", ".#.##.#.", ".#.##.#.", "#.#..#.#", "#..##..#", "###..###"]))  # chip glyph
    t.append(tile_from([":::::::#", ":::::::#", ":::::::#", ":::::::#", ":::::::#", ":::::::#", ":::::::#", ":::::::#"]))  # panel edge
    for rows in (  # D-pad direction marks for the action menu: left, right, up, down
        ["........", "...##...", "..###...", ".######.", ".######.", "..###...", "...##...", "........"],
        ["........", "...##...", "...###..", ".######.", ".######.", "...###..", "...##...", "........"],
        ["...##...", "..####..", ".######.", "...##...", "...##...", "...##...", "...##...", "........"],
        ["...##...", "...##...", "...##...", "...##...", ".######.", "..####..", "...##...", "........"],
    ):
        t.append(tile_from(rows))
    assert len(t) == FIRST_INV_TILE - FIRST_UI_TILE
    return t


def sky(h: int, w: int, top: float, bottom: float, shade_hi: int = 1, shade_lo: int = 0) -> np.ndarray:
    """Ordered-dither vertical gradient between two shades."""
    img = np.full((h, w), shade_lo)
    for y in range(h):
        level = top + (bottom - top) * y / max(1, h - 1)
        for x in range(w):
            if level > BAYER[y % 4, x % 4]:
                img[y, x] = shade_hi
    return img


def disc(img, cx, cy, r, shade):
    yy, xx = np.ogrid[: img.shape[0], : img.shape[1]]
    img[(xx - cx) ** 2 + (yy - cy) ** 2 <= r * r] = shade


def rect(img, x0, y0, x1, y1, shade):
    img[max(0, y0) : max(0, y1), max(0, x0) : max(0, x1)] = shade


def hills(img, rnd, base, amp, shade, step=9):
    h, w = img.shape
    y, pts = base, []
    for x in range(0, w + step, step):
        pts.append(y)
        y = min(h, max(base - amp, y + rnd.randint(-3, 3)))
    for x in range(w):
        a, b = pts[x // step], pts[x // step + 1]
        top = a + (b - a) * (x % step) // step
        img[max(0, top) :, x] = shade


def pine(img, cx, base, height, shade):
    width = max(3, height // 3)
    for y in range(height):
        band = (y % 5) / 5 + y / height
        half = int(width * band * 0.9) + 1
        rect(img, cx - half, base - height + y, cx + half + 1, base - height + y + 1, shade)
    rect(img, cx - 1, base - 2, cx + 2, base + 1, shade)


def fog(img, y0, y1, level, shade):
    for y in range(y0, min(y1, img.shape[0])):
        for x in range(img.shape[1]):
            if level > BAYER[y % 4, x % 4] and (x * 3 + y * 7) % 11 > 2:
                img[y, x] = shade


def scene_forest(rnd):
    img = sky(SCENE_H, SCENE_W, 0.45, 0.0)
    disc(img, 124, 11, 7, 0)
    for x in range(0, SCENE_W, 8):
        pine(img, x + rnd.randint(-2, 2), 36, rnd.randint(16, 24), 1)
    fog(img, 26, 38, 0.5, 0)
    for x in range(-4, SCENE_W, 15):
        pine(img, x + rnd.randint(-3, 3), 44, rnd.randint(24, 36), 2)
    rect(img, 0, 42, SCENE_W, SCENE_H, 3)
    for x in range(4, SCENE_W, 34):
        pine(img, x + rnd.randint(-5, 5), 47, rnd.randint(34, 44), 3)
    return img


def scene_marsh(rnd):
    img = sky(SCENE_H, SCENE_W, 0.7, 0.1)
    hills(img, rnd, 24, 4, 1)
    fog(img, 20, 28, 0.6, 0)
    rect(img, 0, 28, SCENE_W, SCENE_H, 1)
    for y in range(28, SCENE_H, 3):
        for x in range(rnd.randint(0, 9), SCENE_W, rnd.randint(11, 19)):
            rect(img, x, y, x + rnd.randint(3, 9), y + 1, 0 if y < 37 else 2)
    tx = 112
    rect(img, tx, 8, tx + 3, 34, 3)
    for (dx, y, ln) in ((-9, 13, 9), (3, 10, 10), (-6, 19, 6), (3, 17, 7)):
        rect(img, tx + dx, y, tx + dx + ln, y + 1, 3)
        rect(img, tx + dx if dx < 0 else tx + dx + ln - 1, y - 3, (tx + dx if dx < 0 else tx + dx + ln - 1) + 1, y, 3)
    for x in range(2, SCENE_W, 5):
        if not 90 < x < 134 or rnd.random() < 0.2:
            h = rnd.randint(4, 14)
            rect(img, x, SCENE_H - h, x + 1, SCENE_H, 3)
            rect(img, x, SCENE_H - h - 2, x + 2, SCENE_H - h + 1, 3)
    return img


def scene_river(rnd):
    img = sky(SCENE_H, SCENE_W, 0.25, 0.0)
    hills(img, rnd, 18, 8, 2)
    hills(img, rnd, 24, 4, 3)
    rect(img, 0, 26, SCENE_W, SCENE_H, 1)
    for y in range(27, SCENE_H, 2):
        phase = rnd.randint(0, 20)
        period = 26 - (y - 27) // 2
        for x in range(phase - 30, SCENE_W, period):
            rect(img, x, y, x + period // 2, y + 1, 0 if (y // 2) % 2 else 2)
    for x in range(0, 30, 3):
        rect(img, x, 26 + (30 - x) // 2 - 6, x + 3, SCENE_H, 3)
    for x in range(128, SCENE_W, 3):
        rect(img, x, 30 + (SCENE_W - x) // 4 - 8, x + 3, SCENE_H, 3)
    return img


def scene_ruins(rnd):
    img = sky(SCENE_H, SCENE_W, 0.55, 0.05)
    hills(img, rnd, 34, 3, 1)
    for i, (x, top) in enumerate(((16, 12), (44, 24), (72, 8), (100, 8), (134, 28))):
        rect(img, x, top, x + 10, 42, 2)
        rect(img, x + 7, top, x + 10, 42, 3)
        rect(img, x + 2, top, x + 3, 42, 1)
        rect(img, x - 2, top - 3, x + 12, top, 3)
        if i == 1 or i == 4:
            for k in range(4):
                rect(img, x + k * 3, top - 4 - (k % 2) * 2, x + k * 3 + 2, top - 3, 3)
    rect(img, 68, 3, 114, 8, 3)
    rect(img, 72, 8, 110, 9, 2)
    rect(img, 0, 42, SCENE_W, SCENE_H, 3)
    for _ in range(26):
        x = rnd.randint(0, SCENE_W - 6)
        rect(img, x, 39 + rnd.randint(0, 2), x + rnd.randint(2, 6), 43, rnd.choice((2, 3)))
    return img


def scene_shrine(rnd):
    img = sky(SCENE_H, SCENE_W, 0.95, 0.5)
    for a in range(0, 64):
        t = a * np.pi / 64
        for r in range(14, 90, 4):
            x, y = int(80 + np.cos(t) * r), int(28 - np.sin(t) * r)
            if a % 8 < 3 and 0 <= x < SCENE_W and 0 <= y < SCENE_H:
                img[y, x] = 0
    disc(img, 80, 20, 10, 0)
    disc(img, 80, 20, 7, 1)
    disc(img, 80, 20, 4, 0)
    rect(img, 60, 34, 100, 38, 2)
    rect(img, 54, 38, 106, 42, 3)
    rect(img, 48, 42, 112, 48, 3)
    for x in (34, 118):
        rect(img, x, 8, x + 9, 44, 2)
        rect(img, x + 6, 8, x + 9, 44, 3)
        rect(img, x - 3, 5, x + 12, 8, 3)
    rect(img, 0, 44, SCENE_W, SCENE_H, 3)
    return img


def scene_cave(rnd):
    img = np.full((SCENE_H, SCENE_W), 3)
    disc(img, 80, 48, 44, 2)
    disc(img, 80, 50, 38, 1)
    fog(img, 12, SCENE_H, 0.55, 2)
    disc(img, 80, 54, 22, 3)
    for x in range(0, SCENE_W, 7):
        ln = rnd.randint(4, 20)
        for y in range(ln):
            half = max(0, (ln - y) // 5)
            rect(img, x - half, y, x + half + 1, y + 1, 3)
    for x in range(0, SCENE_W, 11):
        h = rnd.randint(3, 11)
        for y in range(h):
            half = y // 3
            rect(img, x - half, SCENE_H - h + y, x + half + 1, SCENE_H - h + y + 1, 3)
    for (x, y) in ((50, 8), (104, 14), (70, 5)):  # bats
        rect(img, x - 3, y, x + 4, y + 1, 0)
        rect(img, x - 5, y - 1, x - 3, y, 0)
        rect(img, x + 4, y - 1, x + 6, y, 0)
    return img


def scene_gate(rnd):
    img = sky(SCENE_H, SCENE_W, 0.6, 0.15)
    rect(img, 0, 16, SCENE_W, SCENE_H, 2)
    for y in range(16, SCENE_H, 4):  # masonry courses
        rect(img, 0, y, SCENE_W, y + 1, 3)
        for x in range((y // 4 % 2) * 6, SCENE_W, 12):
            rect(img, x, y, x + 1, y + 4, 3)
    for x in range(0, SCENE_W, 12):
        rect(img, x, 11, x + 7, 16, 2)
        rect(img, x + 5, 11, x + 7, 16, 3)
    for x in (42, 100):
        rect(img, x, 2, x + 18, SCENE_H, 2)
        rect(img, x + 13, 2, x + 18, SCENE_H, 3)
        rect(img, x + 2, 2, x + 3, SCENE_H, 1)
        for k in range(3):
            rect(img, x + k * 7, 0, x + k * 7 + 4, 3, 3)
        rect(img, x + 7, 12, x + 10, 19, 3)
    rect(img, 60, 18, 100, SCENE_H, 3)
    disc(img, 80, 24, 20, 3)
    for x in range(63, 98, 6):
        rect(img, x, 8, x + 2, SCENE_H, 1)
    for y in range(14, SCENE_H, 6):
        rect(img, 60, y, 100, y + 1, 1)
    yy, xx = np.ogrid[:SCENE_H, :SCENE_W]
    mask = ((xx - 80) ** 2 + (yy - 24) ** 2 > 400) & (yy < 24) & (xx > 60) & (xx < 100)
    img[mask] = 2
    return img


def scene_tower(rnd):
    img = sky(SCENE_H, SCENE_W, 0.9, 0.25)
    disc(img, 42, 15, 10, 0)
    disc(img, 46, 13, 8, 1)
    for _ in range(14):
        img[rnd.randint(0, 22), rnd.randint(0, SCENE_W - 1)] = 0
    hills(img, rnd, 40, 4, 2)
    x0 = 92
    rect(img, x0, 8, x0 + 22, SCENE_H, 2)
    rect(img, x0 + 15, 8, x0 + 22, SCENE_H, 3)
    rect(img, x0 + 3, 8, x0 + 4, SCENE_H, 1)
    rect(img, x0 - 3, 4, x0 + 25, 9, 3)
    for k in range(4):
        rect(img, x0 - 3 + k * 8, 0, x0 + 2 + k * 8, 4, 3)
    for y in (14, 26):
        rect(img, x0 + 8, y, x0 + 12, y + 6, 0)
    rect(img, 0, 44, SCENE_W, SCENE_H, 3)
    # the sleeping guardian: a hunched stone sentinel at the tower's foot
    disc(img, 74, 41, 8, 3)
    rect(img, 66, 41, 83, 45, 3)
    disc(img, 80, 37, 4, 3)
    rect(img, 80, 36, 82, 37, 1)
    return img


SCENES = [scene_forest, scene_marsh, scene_river, scene_ruins, scene_shrine, scene_cave, scene_gate, scene_tower]
SCENE_SEEDS = [11, 23, 37, 41, 53, 67, 71, 89]


def big_text(img, text, x, y, scale, ink, shadow):
    for i, ch in enumerate(text):
        g = glyph_rows(ch, True)
        gx = x + i * 7 * scale
        for gy in range(8):
            for gxx in range(8):
                if g[gy, gxx]:
                    rect(img, gx + gxx * scale + 1, y + gy * scale + 1, gx + gxx * scale + scale + 1, y + gy * scale + scale + 1, shadow)
        for gy in range(8):
            for gxx in range(8):
                if g[gy, gxx]:
                    rect(img, gx + gxx * scale, y + gy * scale, gx + gxx * scale + scale, y + gy * scale + scale, ink)


def title_screen() -> np.ndarray:
    rnd = random.Random(1989)
    img = np.full((144, 160), 3)
    night = sky(72, 160, 0.9, 0.35, 3, 2)
    img[0:72, :] = night
    disc(img, 112, 24, 15, 0)
    disc(img, 118, 21, 13, 2)
    for _ in range(4):
        x, y = rnd.randint(0, 159), rnd.randint(0, 50)
        if (x - 112) ** 2 + (y - 24) ** 2 > 330:
            img[y, x] = rnd.choice((0, 1))
    rect(img, 0, 60, 160, 72, 3)
    x0 = 36
    rect(img, x0, 12, x0 + 20, 72, 2)
    rect(img, x0 + 13, 12, x0 + 20, 72, 3)
    rect(img, x0 + 3, 12, x0 + 4, 72, 1)
    rect(img, x0 - 3, 8, x0 + 23, 13, 2)
    for k in range(4):
        rect(img, x0 - 3 + k * 8, 3, x0 + 2 + k * 8, 8, 2)
    rect(img, x0 + 7, 20, x0 + 11, 28, 0)
    rect(img, x0 + 7, 40, x0 + 11, 48, 0)
    big_text(img, "8-BIT", 44 - 8, 78, 2, 0, 2)
    for i, ch in enumerate("ADVENTURE"):
        g = glyph_rows(ch, True)
        for gy in range(8):
            for gx in range(8):
                if g[gy, gx]:
                    px, py = 8 + i * 16 + gx * 2, 96 + gy * 2
                    rect(img, px + 1, py + 1, px + 3, py + 3, 2)
        for gy in range(8):
            for gx in range(8):
                if g[gy, gx]:
                    px, py = 8 + i * 16 + gx * 2, 96 + gy * 2
                    rect(img, px, py, px + 2, py + 2, 0)
    return img


def encode(tile: np.ndarray) -> bytes:
    out = bytearray()
    for y in range(8):
        lo = hi = 0
        for x in range(8):
            v = int(tile[y, x])
            lo |= (v & 1) << (7 - x)
            hi |= (v >> 1) << (7 - x)
        out += bytes((lo, hi))
    return bytes(out)


def to_tiles(img: np.ndarray, first: int, limit: int, name: str) -> tuple[list[bytes], list[int]]:
    tiles: list[bytes] = []
    index: dict[bytes, int] = {}
    tilemap: list[int] = []
    for ty in range(img.shape[0] // 8):
        for tx in range(img.shape[1] // 8):
            b = encode(img[ty * 8 : ty * 8 + 8, tx * 8 : tx * 8 + 8])
            if b not in index:
                index[b] = len(tiles)
                tiles.append(b)
            tilemap.append(first + index[b])
    if len(tiles) > limit:
        raise SystemExit(f"{name}: {len(tiles)} unique tiles exceeds budget {limit}")
    return tiles, tilemap


def db(data: bytes) -> str:
    rows = []
    for i in range(0, len(data), 32):
        rows.append("    db " + ",".join(f"${b:02X}" for b in data[i : i + 32]))
    return "\n".join(rows) if rows else ""


def save_preview(img: np.ndarray, name: str) -> None:
    rgb = np.array(PREVIEW_RGB, dtype=np.uint8)[img]
    Image.fromarray(rgb).resize((img.shape[1] * 3, img.shape[0] * 3), Image.NEAREST).save(PREVIEW / f"{name}.png")


def build() -> None:
    GEN.mkdir(exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    chars = [chr(c) for c in range(0x20, 0x60)]
    font = b"".join(encode(font_tile(chr(c))) for c in range(0x20, 0x80))
    ui = b"".join(encode(t) for t in ui_tiles())
    inv = b"".join(encode(inverse_tile(c)) for c in INV_CHARS)
    inv_map = bytes((FIRST_INV_TILE + INV_CHARS.index(c)) if c in INV_CHARS else FIRST_INV_TILE for c in chars)
    out = ["; AUTOGENERATED by tools/make_art.py. All art is original and procedurally drawn.", ""]
    out += ['SECTION "font_tiles", ROM0', "FontTiles::", db(font), "UiTiles::", db(ui), "InvTiles::", db(inv), "InvMap::", db(inv_map), ""]
    table = ['SECTION "scene_table", ROM0', "SceneTable::"]
    sizes = []
    for i, fn in enumerate(SCENES):
        img = fn(random.Random(SCENE_SEEDS[i]))
        assert img.shape == (SCENE_H, SCENE_W)
        save_preview(img, f"scene_{i}_{fn.__name__[6:]}")
        tiles, tm = to_tiles(img, FIRST_SCENE_TILE, ART_TILE_BUDGET, fn.__name__)
        sizes.append(len(tiles))
        out += [f'SECTION "scene_{i}", ROMX', f"Scene{i}Tiles:", db(b"".join(tiles)), f"Scene{i}Map:", db(bytes(tm)), ""]
        table.append(f"    db BANK(Scene{i}Tiles), {len(tiles)}\n    dw Scene{i}Tiles, Scene{i}Map")
    img = title_screen()
    save_preview(img, "title")
    tiles, tm = to_tiles(img, TITLE_FIRST_TILE, ART_TILE_BUDGET, "title")
    out += ['SECTION "title_gfx", ROMX', "TitleTiles:", db(b"".join(tiles)), "TitleMap:", db(bytes(tm)), ""]
    table.append(f"TitleInfo::\n    db BANK(TitleTiles), {len(tiles)}\n    dw TitleTiles, TitleMap")
    (GEN / "assets.asm").write_text("\n".join(out + table) + "\n")
    print("scene unique tiles:", sizes, "title:", len(tiles))


if __name__ == "__main__":
    build()
