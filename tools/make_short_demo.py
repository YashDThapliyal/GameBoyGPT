#!/usr/bin/env python3
"""Cuts the full demo into a short clip for sharing, using the moments the recorder logged, so captions land on what they describe.
Every beat has its own speed. The "Sped up" tag shows whenever anything does. The takeover stays at real speed, with a black beat before it."""
from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "docs" / "demo"
FULL = DEMO / "system_override_demo.mp4"
SHORT = DEMO / "system_override_short.mp4"
ART = ROOT / "build" / "demo_captions"
H = 720
END_CARD_SEC = 2.5
BLACK_BEAT_SEC = 0.9  # how long the fade lasts on screen, right before the scare
# From this logged moment until the next one, at this speed, with this caption.
BEATS = {
    "power": (6, None), "powered": (6, None), "typeName": (1, "name"), "waitName": (5, "name"), "readName": (1, None),
    "toSmash": (3, None), "typeSmash": (1, None), "waitSmash": (5, None), "coverOff": (1, None), "chipLive": (3, "inside"), "readSmash": (1, "inside"),
    "coverOn": (1, None), "toFlip0": (3, "off"), "flip0": (1, "off"), "waitFlip0": (5, "off"), "readFlip0": (1, "off"),
    "toFlip1": (3, None), "flip1": (1, None), "waitFlip1": (5, None), "readFlip1": (1, None),
    "toFlip2": (3, None), "flip2": (1, None), "waitFlip2": (5, None), "readFlip2": (1, None),
    "plug": (1, None), "fade": (None, None), "takeover": (1, None),
}


def main() -> None:
    subprocess.run(["node", "tools/render_demo_captions.mjs"], cwd=ROOT, check=True, capture_output=True)
    log = json.loads((DEMO / "demo_tokens.json").read_text())
    marks = log["timeline"]
    assert {m["name"] for m in marks} - {"end"} == set(BEATS), "the recorder and this edit disagree about the beats"
    filters, labels, clock, sped, captions = [], [], 0.0, [], {}
    for i, (now, after) in enumerate(zip(marks, marks[1:])):
        rate, caption = BEATS[now["name"]]
        start, end = now["seconds"], after["seconds"]
        rate = rate or (end - start) / BLACK_BEAT_SEC
        filters.append(f"[0:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{rate}[s{i}]")
        labels.append(f"[s{i}]")
        length = (end - start) / rate
        if rate > 1:
            sped.append(f"between(t,{clock:.3f},{clock + length:.3f})")
        if caption:
            first, _ = captions.get(caption, (clock, 0))
            captions[caption] = (first, clock + length)
        clock += length
    inputs = ["-i", str(FULL), "-loop", "1", "-t", str(END_CARD_SEC), "-framerate", "25", "-i", str(ART / "card.png"), "-i", str(ART / "speed.png")]
    filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=1,fps=25,format=yuv420p[cut]")
    filters.append(f"[cut][2:v]overlay=24:{H - 50}:enable='{'+'.join(sped)}'[v0]")
    last = "v0"
    for n, (name, (start, end)) in enumerate(captions.items(), start=3):
        inputs += ["-i", str(ART / f"{name}.png")]
        filters.append(f"[{last}][{n}:v]overlay=(W-w)/2:{H - 110}:enable='between(t,{start:.3f},{end:.3f})'[v{n}]")
        last = f"v{n}"
    filters.append("[1:v]fps=25,format=yuv420p[card]")
    filters.append(f"[{last}][card]concat=n=2:v=1[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(SHORT)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(SHORT), "-vf", "fps=10,scale=480:-1:flags=neighbor,split[a][b];[a]palettegen=max_colors=32[p];[b][p]paletteuse=dither=none", str(SHORT.with_suffix(".gif"))], check=True)
    print(f"{clock + END_CARD_SEC:.1f} s, {len(labels)} pieces, full video {log['seconds']:.1f} s")


if __name__ == "__main__":
    main()
