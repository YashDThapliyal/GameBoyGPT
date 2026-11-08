#!/usr/bin/env python3
"""Generate all original 2-bit art procedurally and pack it as RGBDS data.

No external art or font is used: every pixel is produced by this script, which is the
licence audit for assets/tiles/. Shades: 0 lightest .. 3 darkest (BGP=$E4).
Outputs generated/assets.asm, generated/robot.inc and PNG previews in assets/tiles/.
"""
from __future__ import annotations
import random
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
GEN, PREVIEW = ROOT / "generated", ROOT / "assets" / "tiles"
# Background tile numbers. With LCDC.4 clear, 0-127 are at $9000 and 128-255 at $8800; sprites keep $8000-$87FF to themselves.
FIRST_UI_TILE, FIRST_INV_TILE, FIRST_LOGO_TILE = 96, 128, 168
FIRST_LOGO_LOW, LOGO_LOW_SLOTS = 64, 32
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
    for rows in (  # band icons for the other things you can carry: sword, friend, ring, then a spare
        ["######..", "#####.:#", "####.:##", "#.#.:###", "##..####", "##.#####", "#.######", "########"],
        ["###..###", "###..###", "########", "##....##", "#......#", "#.#..#.#", "###..###", "##.##.##"],
        ["###..###", "##.##.##", "#.####.#", "#.####.#", "#.####.#", "##.##.##", "###..###", "########"],
        ["########"] * 8,
    ):
        t.append(tile_from(rows))
    t.append(tile_from(["........", "........", "........", "........", "........", "........", "########", "########"]))  # text cursor
    while len(t) < FIRST_INV_TILE - FIRST_UI_TILE:
        t.append(tile_from(["........"] * 8))
    return t


def rect(img, x0, y0, x1, y1, shade):
    img[y0:y1, x0:x1] = shade


def big_text(img, text, x, y, scale, ink, shadow, step=None):
    for i, ch in enumerate(text):
        g = glyph_rows(ch, True)
        gx = x + i * (step or 7 * scale)
        for gy in range(8):
            for gxx in range(8):
                if g[gy, gxx]:
                    rect(img, gx + gxx * scale + 1, y + gy * scale + 1, gx + gxx * scale + scale + 1, y + gy * scale + scale + 1, shadow)
        for gy in range(8):
            for gxx in range(8):
                if g[gy, gxx]:
                    rect(img, gx + gxx * scale, y + gy * scale, gx + gxx * scale + scale, y + gy * scale + scale, ink)


def logo_screen() -> np.ndarray:
    """SYSTEM OVERRIDE, full width, with a few torn scanlines. 160 x 56."""
    img = np.zeros((56, 160), dtype=int)
    big_text(img, "SYSTEM", 24, 3, 3, 3, 3, step=19)
    big_text(img, "OVERRIDE", 4, 30, 3, 3, 3, step=19)
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


def robot_cells(sets: dict[str, np.ndarray], row: int) -> dict[str, list[np.ndarray]]:
    return {k: [v[row * 16:row * 16 + 16, c * 8:c * 8 + 8] for c in range(8)] for k, v in sets.items()}


class SpriteTiles:
    """8x16 cells, deduplicated including X flips. Index is the even tile number of the pair."""

    def __init__(self) -> None:
        self.data: list[bytes] = []
        self.index: dict[bytes, tuple[int, int]] = {}

    def add(self, cell: np.ndarray) -> tuple[int, int]:
        raw = encode(cell[:8]) + encode(cell[8:])
        if raw not in self.index:
            flip = encode(cell[:8, ::-1]) + encode(cell[8:, ::-1])
            n = len(self.data) * 2
            self.index[raw] = (n, 0)
            self.index.setdefault(flip, (n, 0x20))
            self.data.append(raw)
        return self.index[raw]


def robot_asm(preview: Path) -> list[str]:
    import make_robot as mr
    spr = SpriteTiles()
    eyes = list(dict.fromkeys(e for e, _ in mr.EXPRESSIONS.values())) + ["blink"]
    mouths = list(dict.fromkeys(m for _, m in mr.EXPRESSIONS.values())) + ["talk1", "talk2"]
    base = mr.frame("neutral", "grin")
    fixed = {r: [spr.add(base[r * 16:r * 16 + 16, c * 8:c * 8 + 8]) for c in range(8)] for r in (0, 3)}
    eye_rows = [[spr.add(mr.frame(e, "grin")[16:32, c * 8:c * 8 + 8]) for c in range(8)] for e in eyes]
    mouth_rows = [[spr.add(mr.frame("neutral", m)[32:48, c * 8:c * 8 + 8]) for c in range(8)] for m in mouths]
    cursor = spr.add(np.array([[3 if (y in (0, 9) or x in (0, 7)) and y <= 9 else 0 for x in range(8)] for y in range(16)]))
    arrow = spr.add(np.array([[3 if y < 8 and x < 7 and abs(y - 3.5) < (7 - x) * 0.6 else 0 for x in range(8)] for y in range(16)]))
    if len(spr.data) * 2 > 128:
        raise SystemExit(f"robot uses {len(spr.data) * 2} sprite tiles, budget 128")
    print("robot sprite tiles:", len(spr.data) * 2)
    def row(cells):
        return "    db " + ",".join(f"{t},{a}" for t, a in cells)
    out = ['SECTION "robot_gfx", ROMX', "RobotTiles::", db(b"".join(spr.data)), "RobotTilesEnd::",
           'SECTION "robot_tables", ROM0', "RobotRow0::", row(fixed[0]), "RobotRow3::", row(fixed[3]), "RobotEyes::"]
    out += [row(r) for r in eye_rows] + ["RobotMouths::"] + [row(r) for r in mouth_rows]
    table = [(eyes.index(e), mouths.index(m)) for e, m in mr.EXPRESSIONS.values()]
    out += ["RobotExpr::", "    db " + ",".join(f"{e},{m}" for e, m in table)]
    constants = {"EYE_BLINK": eyes.index("blink"), "EYE_THINK": eyes.index("thinking"), "EYE_GLITCH": eyes.index("glitch"),
                 "MOUTH_TALK1": mouths.index("talk1"), "MOUTH_TALK2": mouths.index("talk2"), "MOUTH_GLITCH": mouths.index("noise"),
                 "NUM_EYES": len(eyes), "NUM_MOUTHS": len(mouths), "TILE_SPR_CURSOR": cursor[0], "TILE_SPR_ARROW": arrow[0], "NUM_ROBOT_TILES": len(spr.data) * 2}
    constants |= {f"EXPR_{n.upper()}": i for i, n in enumerate(mr.EXPRESSIONS)}
    (GEN / "robot.inc").write_text("".join(f"DEF {k} EQU {v}\n" for k, v in constants.items()))
    mr.preview(preview)
    return out


def build() -> None:
    GEN.mkdir(exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for old in PREVIEW.glob("scene_*.png"):
        old.unlink()
    chars = [chr(c) for c in range(0x20, 0x60)]
    font = b"".join(encode(font_tile(chr(c))) for c in range(0x20, 0x80))
    ui = b"".join(encode(t) for t in ui_tiles())
    inv = b"".join(encode(inverse_tile(c)) for c in INV_CHARS)
    inv_map = bytes((FIRST_INV_TILE + INV_CHARS.index(c)) if c in INV_CHARS else FIRST_INV_TILE for c in chars)
    out = ["; AUTOGENERATED by tools/make_art.py. All art is original and procedurally drawn.", ""]
    out += ['SECTION "font_tiles", ROMX', "FontTiles::", db(font), "UiTiles::", db(ui), "InvTiles::", db(inv), 'SECTION "inv_map", ROM0', "InvMap::", db(inv_map), ""]
    out += robot_asm(PREVIEW / "robot_expressions.png")
    img = logo_screen()
    save_preview(img, "logo")
    # Lowercase is never printed, so the logo reuses those 32 slots as well as the free block at $8800.
    tiles, tm = to_tiles(img, 0, LOGO_LOW_SLOTS + 256 - FIRST_LOGO_TILE, "logo")
    print("logo tiles:", len(tiles))
    tm = [FIRST_LOGO_LOW + i if i < LOGO_LOW_SLOTS else FIRST_LOGO_TILE + i - LOGO_LOW_SLOTS for i in tm]
    out += ['SECTION "logo_gfx", ROMX', "LogoTilesLow::", db(b"".join(tiles[:LOGO_LOW_SLOTS])), "LogoTiles::", db(b"".join(tiles[LOGO_LOW_SLOTS:])), "LogoTilesEnd::",
            "LogoMap::", db(bytes(tm)), "LogoMapEnd::", ""]
    (GEN / "assets.asm").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    build()
