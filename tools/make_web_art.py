#!/usr/bin/env python3
"""The website's pixel art, drawn by this script: console shell, controls, backdrop and icon. One art pixel equals one LCD pixel."""
from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_robot import frame

OUT = ROOT / "web" / "assets"
INK = (35, 38, 31, 255)
CREAM = (230, 223, 202, 255)
CREAM_HI = (244, 238, 220, 255)
CREAM_LO = (191, 184, 160, 255)
CREAM_DEEP = (158, 151, 128, 255)
BEZEL = (78, 80, 72, 255)
BEZEL_HI = (101, 104, 94, 255)
OLIVE = (107, 122, 63, 255)
DARK = (46, 48, 42, 255)
DARK_HI = (78, 80, 72, 255)
MAGENTA = (140, 37, 89, 255)
MAGENTA_HI = (176, 62, 118, 255)
MAGENTA_LO = (81, 18, 47, 255)
CLEAR = (0, 0, 0, 0)
LCD_SHADES = ((196, 207, 161, 255), (139, 149, 109, 255), (77, 83, 60, 255), (31, 31, 31, 255))
BACK_FAR = (33, 61, 45, 255)
BACK_NEAR = (38, 69, 51, 255)
BACK_TREE = (22, 43, 32, 255)
CLOUD = (44, 76, 57, 255)
SHELL_W, SHELL_H = 192, 318
TILE_W, TILE_H = 320, 96


def rounded(size: tuple[int, int], tl: int, tr: int, br: int, bl: int) -> Image.Image:
    """A hard-edged mask with a separate radius per corner."""
    w, h = size
    mask = Image.new("1", size, 0)
    px = mask.load()
    corners = ((tl, tl, tl), (tr, w - 1 - tr, tr), (br, w - 1 - br, h - 1 - br), (bl, bl, h - 1 - bl))
    for y in range(h):
        for x in range(w):
            inside = True
            for i, (r, cx, cy) in enumerate(corners):
                in_corner = (x < cx if i in (0, 3) else x > cx) and (y < cy if i in (0, 1) else y > cy)
                if in_corner and (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                    inside = False
            px[x, y] = 1 if inside else 0
    return mask


def fill_mask(img: Image.Image, mask: Image.Image, at: tuple[int, int], colour: tuple[int, int, int, int]) -> None:
    img.paste(colour, at, mask)


def shell() -> Image.Image:
    img = Image.new("RGBA", (SHELL_W, SHELL_H), CLEAR)
    fill_mask(img, rounded((SHELL_W, SHELL_H), 5, 5, 34, 5), (0, 0), INK)
    fill_mask(img, rounded((SHELL_W - 2, SHELL_H - 2), 4, 4, 33, 4), (1, 1), CREAM_LO)
    fill_mask(img, rounded((SHELL_W - 5, SHELL_H - 6), 4, 4, 31, 4), (1, 1), CREAM)
    d = ImageDraw.Draw(img)
    d.line((5, 1, SHELL_W - 7, 1), fill=CREAM_HI)
    d.line((1, 5, 1, SHELL_H - 9), fill=CREAM_HI)
    # the seam across the top, and its two notches
    d.line((1, 10, SHELL_W - 4, 10), fill=CREAM_DEEP)
    d.line((1, 11, SHELL_W - 4, 11), fill=CREAM_HI)
    for x in (11, SHELL_W - 13):
        d.line((x, 1, x, 10), fill=CREAM_DEEP)
    # the bezel
    fill_mask(img, rounded((176, 160), 4, 4, 24, 4), (8, 17), INK)
    fill_mask(img, rounded((174, 158), 3, 3, 23, 3), (9, 18), BEZEL)
    d.line((13, 18, 178, 18), fill=BEZEL_HI)
    for y in (21, 23):
        d.line((16, y, 66, y), fill=OLIVE)
        d.line((126, y, 176, y), fill=OLIVE)
    # the lcd's frame. The real canvas sits on top of this.
    d.rectangle((15, 26, 176, 171), fill=INK)
    # wells under the controls
    d.ellipse((12, 207, 73, 268), fill=CREAM_LO)
    d.line(((128, 247), (162, 231)), fill=CREAM_LO, width=34)
    d.ellipse((111, 230, 145, 264), fill=CREAM_LO)
    d.ellipse((145, 214, 179, 248), fill=CREAM_LO)
    # the speaker: six slanted slots
    for i in range(6):
        x = 134 + i * 7
        d.line(((x, 310 - i), (x + 14, 276 - i)), fill=CREAM_DEEP, width=3)
        d.line(((x + 2, 310 - i), (x + 16, 276 - i)), fill=INK, width=1)
    # anything that strayed past the rounded edge goes back to clear
    img.putalpha(rounded((SHELL_W, SHELL_H), 5, 5, 34, 5).convert("L").point(lambda v: 255 if v else 0))
    return img


def dpad() -> Image.Image:
    img = Image.new("RGBA", (51, 53), CLEAR)
    d = ImageDraw.Draw(img)
    for dy, colour in ((2, INK), (0, DARK)):
        d.rectangle((17, dy, 33, 50 + dy), fill=colour)
        d.rectangle((0, 17 + dy, 50, 33 + dy), fill=colour)
    d.line((18, 1, 32, 1), fill=DARK_HI)
    d.line((1, 18, 16, 18), fill=DARK_HI)
    d.line((34, 18, 49, 18), fill=DARK_HI)
    d.ellipse((20, 20, 30, 30), fill=INK)
    for rect in ((23, 7, 27, 11), (23, 39, 27, 43), (7, 23, 11, 27), (39, 23, 43, 27)):
        d.rectangle(rect, outline=INK)
    return img


def round_button() -> Image.Image:
    img = Image.new("RGBA", (26, 29), CLEAR)
    d = ImageDraw.Draw(img)
    d.ellipse((0, 3, 25, 28), fill=MAGENTA_LO)
    d.ellipse((0, 0, 25, 25), fill=MAGENTA)
    d.arc((3, 3, 22, 22), 190, 280, fill=MAGENTA_HI, width=2)
    return img


def pill() -> Image.Image:
    img = Image.new("RGBA", (26, 15), CLEAR)
    d = ImageDraw.Draw(img)
    d.line(((3, 11), (22, 4)), fill=INK, width=6)
    d.line(((3, 9), (22, 2)), fill=BEZEL, width=5)
    return img


def ridge(d: ImageDraw.ImageDraw, heights: list[int], colour: tuple[int, int, int, int]) -> None:
    for x, top in enumerate(heights):
        d.line((x, top, x, TILE_H), fill=colour)


def triangle_wave(x: int, period: int, height: int, phase: int = 0) -> int:
    t = (x + phase) % period
    half = period // 2
    return (t if t < half else period - t) * height // half


def landscape() -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), CLEAR)
    d = ImageDraw.Draw(img)
    # every wave period divides the tile width, so the tile repeats without a seam
    ridge(d, [76 - triangle_wave(x, 160, 44) - triangle_wave(x, 64, 12, 20) // 2 for x in range(TILE_W)], BACK_FAR)
    ridge(d, [84 - triangle_wave(x, 80, 22, 30) - triangle_wave(x, 32, 7) // 2 for x in range(TILE_W)], BACK_NEAR)
    for i, x in enumerate(range(6, TILE_W, 21)):
        h = (9, 14, 11, 16)[i % 4]
        base = TILE_H - 4
        for row in range(h):
            half = 1 + row // 2
            d.line((x - half, base - h + row, x + half, base - h + row), fill=BACK_TREE)
        d.rectangle((x, base, x + 1, TILE_H), fill=BACK_TREE)
    d.rectangle((0, TILE_H - 3, TILE_W, TILE_H), fill=BACK_TREE)
    return img


def cloud() -> Image.Image:
    img = Image.new("RGBA", (40, 13), CLEAR)
    d = ImageDraw.Draw(img)
    for rect in ((0, 8, 39, 12), (5, 5, 27, 8), (10, 2, 21, 5), (27, 6, 33, 8)):
        d.rectangle(rect, fill=CLOUD)
    return img


def robot_icon() -> Image.Image:
    art = frame("smug", "smirk")
    img = Image.new("RGBA", (64, 64), LCD_SHADES[0])
    px = img.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = LCD_SHADES[int(art[y, x])]
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, art in (("shell", shell()), ("dpad", dpad()), ("button", round_button()), ("pill", pill()), ("landscape", landscape()), ("cloud", cloud()), ("robot", robot_icon())):
        art.save(OUT / f"{name}.png", optimize=True)
    if len(sys.argv) < 2:
        return
    preview = Image.new("RGBA", (SHELL_W + 8, SHELL_H + 8), (28, 53, 39, 255))
    preview.alpha_composite(shell(), (4, 4))
    preview.alpha_composite(dpad(), (21, 216))
    preview.alpha_composite(round_button(), (120, 238))
    preview.alpha_composite(round_button(), (150, 222))
    preview.alpha_composite(pill(), (60, 280))
    preview.alpha_composite(pill(), (92, 280))
    preview.resize((preview.width * 2, preview.height * 2), Image.NEAREST).save(sys.argv[1])


if __name__ == "__main__":
    main()
