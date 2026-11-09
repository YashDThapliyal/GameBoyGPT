#!/usr/bin/env python3
"""Copies the shipping ROM into web/rom and writes build.json: symbol addresses, vocabulary and measured numbers for the panel."""
from __future__ import annotations
import csv, hashlib, json, re, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from run_emulator import load_symbols
from training import dialogue as dl

WATCHED = ("wMenuSel", "wMB_State", "wMB_Mood", "wMB_Emotion", "wMB_Responses", "wMB_TotalTokens", "wLastEventFrames", "wLastEventTokens", "wSeq", "wSeqLen", "wInput", "wInputLen",
           "wShutdowns", "wName", "wLike", "wWord", "wInsults", "wPraises", "wCandId", "wCandW", "wCandN", "wPickId", "wE", "wQ", "wA", "wF", "wX2", "wZ")
RACE_WATCHED = ("wMenuSel", "wMB_State", "wSeq", "wSeqLen", "wMB_ForceSeed", "wNarrRng")


LADDER = (("V0", "Plain code"), ("V2", "Table-based multiply"), ("V3", "Fused dot product, row pruning"), ("V5", "Cached attention"), ("V5Z", "Weight stream, zero skipping"), ("V6T", "Per-token head tables"))


def speed_ladder() -> list[dict[str, float | str]]:
    """Mean seconds per token for each cumulative build, from the recorded benchmark."""
    rows = list(csv.DictReader((ROOT / "reports" / "benchmark.csv").open()))
    def mean_for(version: str) -> float:
        values = [float(r["seconds_per_token"]) for r in rows if r["version"] == version]
        return sum(values) / len(values)
    return [{"label": label, "seconds": mean_for(version)} for version, label in LADDER]


def speed_steps() -> list[dict[str, float | str]]:
    """Recorded seconds per reply for each cumulative build, and the gain over the build before it."""
    rows = list(csv.DictReader((ROOT / "reports" / "benchmark.csv").open()))
    order = ("V0", "V1", "V2", "V3", "V4", "V5", "V5S", "V5Z", "V6T")
    def mean_for(version: str) -> float:
        values = [float(r["seconds_per_response"]) for r in rows if r["version"] == version]
        return sum(values) / len(values)
    seconds = [mean_for(version) for version in order]
    return [{"id": version, "seconds": now, "gain": (seconds[i - 1] / now) if i else 1.0} for i, (version, now) in enumerate(zip(order, seconds))]


def memory_map(syms: dict, map_text: str, wram: int, model_bytes: int, rom_bytes: int) -> dict[str, list[dict[str, int | str]]]:
    """Real sizes from the build's symbols and map file, for the About page."""
    addr = lambda name: syms[name][1]
    cache = addr("wE") - addr("wKCache")
    activations = addr("wScore") - addr("wE")
    scores = addr("wCacheLen") - addr("wLogits")
    used_rom = sum(int(n) for n in re.findall(r"ROM[0X]: (\d+) bytes used", map_text))
    sram = int(re.search(r"SRAM: (\d+) bytes used", map_text).group(1))
    tables = 16 * 512
    return {
        "wram": [{"label": "Attention cache", "bytes": cache}, {"label": "Token scores", "bytes": scores}, {"label": "Activations", "bytes": activations}, {"label": "Game", "bytes": wram - cache - scores - activations}, {"label": "Free", "bytes": 8192 - wram}],
        "rom": [{"label": "Weights", "bytes": model_bytes}, {"label": "Code and art", "bytes": used_rom - model_bytes}, {"label": "Free", "bytes": rom_bytes - used_rom}],
        "cart": [{"label": "Head tables", "bytes": tables}, {"label": "Your save", "bytes": sram - tables}, {"label": "Unused", "bytes": 32768 - sram}],
    }


def main() -> None:
    build = ROOT / "build" / "V6T"
    rom = build / "gameboygpt.gb"
    out = ROOT / "web" / "rom"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(rom, out / "system_override.gb")
    syms = load_symbols(rom.with_suffix(".sym"))
    baseline_rom = build.parent / "V0" / "gameboygpt.gb"
    shutil.copy(baseline_rom, out / "system_override_v0.gb")
    baseline_syms = load_symbols(baseline_rom.with_suffix(".sym"))
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    map_text = rom.with_suffix(".map").read_text()
    wram = int(re.search(r"WRAM0: (\d+) bytes used", map_text).group(1))
    measured = None
    summary = ROOT / "reports" / "benchmark_summary.json"
    if summary.exists():
        s = json.loads(summary.read_text())
        baseline = json.loads((ROOT / "reports" / "benchmark.json").read_text())["game"]["V0"]
        measured = {"secondsPerToken": s["ship"]["game_seconds_per_token"], "secondsPerResponse": s["ship"]["game_seconds_per_response"], "baselineSecondsPerResponse": baseline["seconds_per_response"], "baselineSecondsPerToken": baseline["seconds_per_token"], "firstWordSeconds": s["ship"]["first_word_s"], "baselineFirstWordSeconds": baseline["first_word_s"], "speedup": s["ship"]["speedup_vs_v0"], "speedupVsCached": s["ship"]["speedup_vs_v0_kv"]}
    meta = {"rom": "system_override.gb", "sha256": hashlib.sha256(rom.read_bytes()).hexdigest(), "romBytes": rom.stat().st_size, "wramBytes": wram, "params": m.params, "vocabSize": m.vocab, "ctx": m.ctx,
            "d": m.d, "k": len(m.w_b), "promptLen": dl.PROMPT_LEN, "vocab": list(dl.VOCAB), "addresses": {k: syms[k][1] for k in WATCHED}, "debug": {k: syms[k][1] for k in ("wMB_ForceSeed", "wNarrRng", "wTurns", "wReturning", "wMenuSel", "wRobotOn")}, "measured": measured,
            "ladder": speed_ladder() if summary.exists() else None, "steps": speed_steps() if summary.exists() else None, "memory": memory_map(syms, map_text, wram, (ROOT / "generated" / "model.bin").stat().st_size, rom.stat().st_size),
            "race": {"rom": "system_override_v0.gb", "addresses": {k: baseline_syms[k][1] for k in RACE_WATCHED}}}
    (out / "build.json").write_text(json.dumps(meta))
    print("web rom", meta["sha256"][:16], "wram", wram)


if __name__ == "__main__":
    main()
