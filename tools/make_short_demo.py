#!/usr/bin/env python3
"""Cuts the full demo down for sharing. Waits play faster with a label on screen. Replies, the cover and the takeover stay at real speed.
A frame counts as waiting when the console's bottom band reads THINKING ON THE CPU, which only the ROM can put there."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "docs" / "demo" / "system_override_demo.mp4"
SHORT = ROOT / "docs" / "demo" / "system_override_short.mp4"
LABEL = ROOT / "build" / "demo_label.png"
W, H, FPS = 1280, 720, 10
BAND = (160, 396, 476, 408)  # x0, y0, x1, y1 of the LCD's hint band at this viewport
THINKING_SAMPLE_SEC = 11.0   # a frame known to show the band while it's writing
MATCH = 14.0                 # mean absolute difference that still counts as the same band
SPEED = 8.0
INTRO_END_SEC = 7.0          # after the cold open: booting and skipping the intro is also a wait
POWER_DOWN_WAIT_SEC = (66.5, 70.7)  # the fade and logo, once POWERING DOWN has had time to be read
MIN_RUN_SEC = 0.6


def frames() -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(FULL), "-vf", f"fps={FPS},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W)


def waiting_mask(video: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = BAND
    template = video[int(THINKING_SAMPLE_SEC * FPS), y0:y1, x0:x1].astype(float)
    return np.array([np.abs(f[y0:y1, x0:x1].astype(float) - template).mean() < MATCH for f in video])


def segments(mask: np.ndarray) -> list[tuple[float, float, bool]]:
    out: list[list] = []
    for i, wait in enumerate(mask):
        if out and out[-1][2] == bool(wait):
            out[-1][1] = (i + 1) / FPS
        else:
            out.append([i / FPS, (i + 1) / FPS, bool(wait)])
    merged: list[list] = []
    for seg in out:
        if merged and (seg[1] - seg[0] < MIN_RUN_SEC or merged[-1][2] == seg[2]):
            merged[-1][1] = seg[1]
        else:
            merged.append(seg)
    return [tuple(s) for s in merged]


def make_label() -> None:
    LABEL.parent.mkdir(exist_ok=True)
    img = Image.new("RGBA", (214, 34), (31, 31, 31, 255))
    font = ImageFont.load_default(size=20)
    ImageDraw.Draw(img).text((12, 6), f"Waits sped up {SPEED:.0f}x", font=font, fill=(196, 207, 161, 255))
    img.save(LABEL)


def main() -> None:
    video = frames()
    mask = waiting_mask(video)
    cold_open = json.loads((ROOT / "docs" / "demo" / "demo_tokens.json").read_text())["coldOpenSeconds"]
    first_frame = int(cold_open * FPS)
    mask[first_frame:first_frame + int(INTRO_END_SEC * FPS)] = True
    mask[:first_frame] = False
    mask[int(POWER_DOWN_WAIT_SEC[0] * FPS):int(POWER_DOWN_WAIT_SEC[1] * FPS)] = True
    parts, labels, clock = [], [], 0.0
    filters = []
    for i, (start, end, wait) in enumerate(segments(mask)):
        rate = SPEED if wait else 1.0
        filters.append(f"[0:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{rate}[s{i}]")
        parts.append(f"[s{i}]")
        length = (end - start) / rate
        if wait:
            labels.append(f"between(t,{clock:.3f},{clock + length:.3f})")
        clock += length
    make_label()
    graph = ";".join(filters) + f";{''.join(parts)}concat=n={len(parts)}:v=1[cut];[cut][1:v]overlay=24:{H - 58}:enable='{'+'.join(labels)}'[out]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(FULL), "-i", str(LABEL), "-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(SHORT)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(SHORT), "-vf", "fps=10,scale=480:-1:flags=neighbor,split[a][b];[a]palettegen=max_colors=32[p];[b][p]paletteuse=dither=none", str(SHORT.with_suffix(".gif"))], check=True)
    print(f"{clock:.1f} s, {len(parts)} segments, {sum(mask) / FPS:.1f} s of waiting in the original")
    if len(sys.argv) > 1:
        for s in segments(mask):
            print(s)


if __name__ == "__main__":
    main()
