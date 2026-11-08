#!/usr/bin/env python3
"""Copies the shipping ROM into web/rom and writes build.json: symbol addresses, vocabulary and measured numbers for the panel."""
from __future__ import annotations
import hashlib, json, re, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from run_emulator import load_symbols
from training import dialogue as dl

WATCHED = ("wMenuSel", "wMB_State", "wMB_Mood", "wMB_Emotion", "wMB_Responses", "wMB_TotalTokens", "wLastEventFrames", "wLastEventTokens", "wSeq", "wSeqLen")


def main() -> None:
    build = ROOT / "build" / "V6T"
    rom = build / "gameboygpt.gb"
    out = ROOT / "web" / "rom"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(rom, out / "system_override.gb")
    syms = load_symbols(rom.with_suffix(".sym"))
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    map_text = rom.with_suffix(".map").read_text()
    wram = int(re.search(r"WRAM0: (\d+) bytes used", map_text).group(1))
    measured = None
    summary = ROOT / "reports" / "benchmark_summary.json"
    if summary.exists():
        s = json.loads(summary.read_text())
        measured = {"secondsPerToken": s["ship"]["game_seconds_per_token"], "secondsPerResponse": s["ship"]["game_seconds_per_response"]}
    meta = {"rom": "system_override.gb", "sha256": hashlib.sha256(rom.read_bytes()).hexdigest(), "romBytes": rom.stat().st_size, "wramBytes": wram, "params": m.params, "vocabSize": m.vocab, "ctx": m.ctx,
            "d": m.d, "k": len(m.w_b), "promptLen": dl.PROMPT_LEN, "vocab": list(dl.VOCAB), "addresses": {k: syms[k][1] for k in WATCHED}, "debug": {k: syms[k][1] for k in ("wMB_ForceSeed", "wNarrRng", "wTurns", "wReturning", "wMenuSel")}, "measured": measured}
    (out / "build.json").write_text(json.dumps(meta))
    print("web rom", meta["sha256"][:16], "wram", wram)


if __name__ == "__main__":
    main()
