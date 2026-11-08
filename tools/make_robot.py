#!/usr/bin/env python3
"""OVERRIDE, the robot: original 64x64 pixel art, drawn by this script. Shades 0 (paper, transparent) .. 3 (ink).

The body is 8 x 4 sprites in 8x16 mode. Eyes live in sprite row 1 and mouths in row 2, so any eye set can pair with
any mouth set. Cells are deduplicated, including horizontal mirrors, so most of the face costs half its tiles.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_RGB = np.array([(224, 232, 208), (160, 176, 136), (84, 104, 80), (24, 32, 28)], dtype=np.uint8)
W, H = 64, 64
PX = {".": 0, ":": 1, "+": 2, "#": 3, " ": -1}


def poly(img: np.ndarray, points: list[tuple[int, int]], shade: int, mirror: bool = True) -> None:
    for pts in ([points, [(W - 1 - x, y) for x, y in points]] if mirror else [points]):
        canvas = Image.new("L", (W, H), 0)
        ImageDraw.Draw(canvas).polygon(pts, fill=1, outline=1)
        img[np.array(canvas) == 1] = shade


def rect(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, shade: int, mirror: bool = True) -> None:
    img[y0:y1 + 1, x0:x1 + 1] = shade
    if mirror:
        img[y0:y1 + 1, W - 1 - x1:W - x0] = shade


def outline(mask: np.ndarray, img: np.ndarray) -> None:
    """Ink on every shape pixel that touches empty space: the chunky silhouette."""
    edge = np.zeros_like(mask)
    edge[1:, :] |= ~mask[:-1, :]
    edge[:-1, :] |= ~mask[1:, :]
    edge[:, 1:] |= ~mask[:, :-1]
    edge[:, :-1] |= ~mask[:, 1:]
    edge[0, :] = edge[-1, :] = True
    edge[:, 0] = edge[:, -1] = True
    img[mask & edge] = 3


def base() -> np.ndarray:
    """Everything except the eyes and the mouth interior. -1 is empty, resolved to transparent at the end."""
    img = np.full((H, W), -1)
    # shoulders and chest, cut off by the dialogue box
    poly(img, [(2, 63), (2, 56), (7, 51), (20, 49), (31, 49), (31, 63)], 2)
    poly(img, [(11, 63), (13, 55), (31, 53), (31, 63)], 1)
    # neck
    rect(img, 22, 44, 31, 51, 3)
    # horns: short, swept back, set wide on the helmet. They are the silhouette's signature.
    poly(img, [(1, 1), (4, 1), (13, 13), (7, 18), (3, 14)], 2)
    poly(img, [(2, 2), (4, 3), (9, 12), (6, 13)], 1)
    # ear pods
    poly(img, [(0, 22), (6, 21), (6, 35), (2, 35), (0, 33)], 2)
    # head: flat crown, wide cheeks, a jaw that tapers to a heavy chin
    poly(img, [(14, 3), (31, 3), (31, 52), (20, 52), (13, 47), (7, 36), (6, 16)], 1)
    # upper plate shading: a light dome over a darker lower face
    poly(img, [(14, 3), (31, 3), (31, 14), (9, 15)], 0)
    poly(img, [(7, 33), (13, 33), (19, 49), (20, 52), (13, 47)], 2)
    # central crest with a notch
    poly(img, [(27, 0), (31, 0), (31, 16), (29, 13), (27, 5)], 2)
    mask = img != -1
    outline(mask, img)
    # crest detail and a ridge line
    rect(img, 30, 1, 31, 5, 0)
    rect(img, 14, 15, 31, 15, 2)
    # brow plate: sits over the visor, its lower edge is drawn by each eye set
    rect(img, 9, 16, 31, 19, 2)
    # visor recess
    poly(img, [(9, 20), (31, 20), (31, 31), (12, 31), (9, 28)], 3)
    # cheek rivets
    rect(img, 9, 33, 10, 34, 3)
    # mouth recess
    poly(img, [(15, 35), (31, 35), (31, 47), (19, 47), (15, 42)], 3)
    # ear pod bolt
    rect(img, 2, 26, 4, 29, 3)
    rect(img, 3, 27, 3, 28, 0)
    # chest emblem: half a chevron, mirrored into a downward arrow
    poly(img, [(24, 56), (31, 61), (31, 63), (24, 59)], 3)
    return img


def stamp(img: np.ndarray, x: int, y: int, rows: list[str], mirror: bool = True) -> None:
    for j, row in enumerate(rows):
        for i, c in enumerate(row):
            if c == " ":
                continue
            img[y + j, x + i] = PX[c]
            if mirror:
                img[y + j, W - 1 - x - i] = PX[c]


# Left eye drawn at x=11, y=17, 20 wide and 15 tall: rows 0-2 cover the brow, the rest the visor. Mirrored unless paired.
EYES = {
    "neutral": ['                    ', '                    ', '                    ', '                    ', '  ...               ', '  ......            ', '  .........         ', '  ...........       ', '   ..........       ', '    ......          ', '                    '],
    "smug": ['                    ', '                    ', '                    ', '   #################', '   #################', '  ............      ', '  ............      ', '   ..........       ', '                    ', '                    ', '                    '],
    "angry": ['###                 ', '######              ', ' ########           ', '   ########         ', '.. ...  #########   ', '......    #######   ', '.........   #####   ', '............  ###   ', ' ...........        ', '    ......          ', '                    '],
    "amused": ["                    ", "                    ", "                    ", "                    ", "     .....          ",
               "   .........        ", "  ...      ...      ", "  ..        ..      ", "                    ", "                    ", "                    "],
    "surprised": ['                    ', '                    ', '    .........       ', '   ...........      ', '  .............     ', '  ....####.....     ', '  ....####.....     ', '  ....####.....     ', '  .............     ', '   ...........      ', '    .........       '],
    "thinking": ["                    ", "                    ", "                    ", "  ...........       ", "  ...##.......      ",
                 "  ...##.......      ", "  ............      ", "   ..........       ", "                    ", "                    ", "                    "],
    "blink": ["                    ", "                    ", "                    ", "                    ", "                    ",
              "                    ", "  ...........       ", "                    ", "                    ", "                    ", "                    "],
    "dead": ["                    ", "                    ", "                    ", "   ..       ..      ", "    ..     ..       ",
             "      .. ..         ", "       ...          ", "      .. ..         ", "    ..     ..       ", "   ..       ..      ", "                    "],
}
# Left half of the mouth, x=16, y=35, 16 wide and 13 tall. Teeth are paper on the ink recess.
MOUTHS = {
    "flat": ["                ", "                ", "                ", "                ", "                ", "      ..........", "      ..........", "                ", "                ", "                ", "                ", "                ", "                "],
    "grin": ["                ", "                ", "...............#", ".. .. .. .. .. .", ".. .. .. .. .. .", ".. .. .. .. .. .",
             " .. .. .. .. .. ", "  ..............", "                ", "                ", "                ", "                ", "                "],
    "talk1": ["                ", "                ", "    ............", "                ", "                ", "                ",
              "    ............", "                ", "                ", "                ", "                ", "                ", "                "],
    "talk2": ["                ", "   .............", "                ", "     +++++++++++", "     +++++++++++", "     +++++++++++",
              "     +++++++++++", "     +++++++++++", "                ", "   .............", "                ", "                ", "                "],
    "angry": ["                ", "                ", " ...............", " . .. .. .. .. ..", " . .. .. .. .. ..", " ...............",
              "                ", "                ", "                ", "                ", "                ", "                ", "                "],
    "laugh": ["...............#", ".. .. .. .. .. .", ".. .. .. .. .. .", "                ", "   :::::::::::::", "   +++++++++++++",
              "    ++++++++++++", "      ++++++++++", "         +++++++", "                ", "                ", "                ", "                "],
    "ooh": ["                ", "                ", "                ", "           .....", "         ...    ", "         ..  +++",
            "         ..  +++", "         ...    ", "           .....", "                ", "                ", "                ", "                "],
    "frown": ["                ", "                ", "                ", "                ", "           .....", "       .........",
              "    .....       ", "   ...          ", "                ", "                ", "                ", "                ", "                "],
    "noise": ["                ", " .. .  ... . ...", "   ..  .   ..  .", ". . ... . ..  . ", " ..  . ..  ...  ", ".  .. .  . . .. ",
              " ... . .. .  . .", "  .   ...  . .. ", "                ", "                ", "                ", "                ", "                "],
}
GLITCH_EYES_RIGHT = ["                    ", "                    ", "                    ", " . ... ..  .        ", "  .. . ...  ..      ", " ..  ... . .        ",
                     "   ... . .. ..      ", " .  .. ..  .        ", "                    ", "                    ", "                    "]

EXPRESSIONS = {  # eye set, mouth set
    "neutral": ("neutral", "grin"), "smug": ("smug", "smirk"), "angry": ("angry", "angry"), "amused": ("amused", "laugh"),
    "surprised": ("surprised", "ooh"), "thinking": ("thinking", "flat"), "glitching": ("glitch", "noise"), "defeated": ("dead", "frown"),
}


def clear_visor(img: np.ndarray) -> None:
    poly(img, [(9, 20), (31, 20), (31, 31), (12, 31), (9, 28)], 3)
    rect(img, 9, 16, 31, 19, 2)


def clear_mouth(img: np.ndarray) -> None:
    poly(img, [(15, 35), (31, 35), (31, 47), (19, 47), (15, 42)], 3)


def with_eyes(img: np.ndarray, name: str) -> np.ndarray:
    out = img.copy()
    clear_visor(out)
    if name == "glitch":
        stamp(out, 11, 17, EYES["neutral"])
        stamp(out, 33, 17, GLITCH_EYES_RIGHT, mirror=False)
    else:
        stamp(out, 11, 17, EYES[name])
    return out


def with_mouth(img: np.ndarray, name: str) -> np.ndarray:
    out = img.copy()
    clear_mouth(out)
    if name == "smirk":
        # one side of the grin climbs the cheek, the only asymmetric mouth
        for x in range(20, 48):
            lift = max(0, x - 30) // 3
            for y in range(41 - lift, 46 - lift):
                out[y, x] = 3 if (x % 3 == 2 and 41 - lift < y < 45 - lift) else 0
    else:
        stamp(out, 16, 35, [r.ljust(16)[:16] for r in MOUTHS[name]])
    return out


def resolve(img: np.ndarray) -> np.ndarray:
    return np.where(img < 0, 0, img)


def frame(eyes: str, mouth: str) -> np.ndarray:
    return resolve(with_mouth(with_eyes(base(), eyes), mouth))


def preview(path: Path) -> None:
    names = list(EXPRESSIONS)
    scale = 5
    sheet = np.zeros((2 * (H + 8), 4 * (W + 8)), dtype=int)
    for i, n in enumerate(names):
        e, m = EXPRESSIONS[n]
        y, x = (i // 4) * (H + 8) + 4, (i % 4) * (W + 8) + 4
        sheet[y:y + H, x:x + W] = frame(e, m)
    Image.fromarray(PREVIEW_RGB[sheet]).resize((sheet.shape[1] * scale, sheet.shape[0] * scale), Image.NEAREST).save(path)


if __name__ == "__main__":
    out = ROOT / "assets" / "tiles"
    out.mkdir(parents=True, exist_ok=True)
    preview(out / "robot_expressions.png")
    print(out / "robot_expressions.png")
