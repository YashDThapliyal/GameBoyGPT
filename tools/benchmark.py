#!/usr/bin/env python3
"""Cycle benchmarks. Timing comes from PyBoy's T-cycle counter sampled by hooks on ROM labels (calibrated by
tests/test_smoke.py); nothing here uses host time. One emulator runs at a time. Raw traces go to reports/raw/.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, statistics, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]
from kernel_harness import KernelRig, CMD_GENERATE, CMD_STEP, CMD_DOT, CMD_MUL, CMD_MATVEC
from run_emulator import GB
from reference import game as g
from training import dataset as ds

HZ = 4194304
CSV_FIELDS = ("version,git_commit,rom_sha256,model_sha256,emulator,emulator_version,hardware_mode,workload,context_len,"
              "output_tokens,round,first_token_tcycles,decode_tcycles_total,decode_tcycles_median,decode_tcycles_p95,"
              "nominal_seconds_per_token,seconds_per_event,bank_switches,peak_wram_bytes,peak_sram_bytes,rom_bytes,"
              "token_match_baseline,heldout_nll,action_valid_rate,notes").split(",")
WORKLOADS = {
    "PROMPT_A": (g.FOREST, 0, g.LEFT, g.MOVE),      # forest, no key, LEFT
    "PROMPT_B": (g.CAVE, 2, g.SEARCH, g.KEY),       # cave, lantern (then key found), SEARCH
    "PROMPT_C": (g.TOWER, 2, g.FORWARD, g.WIN),     # tower, key, FORWARD
    "PROMPT_D": (g.RIVER, 0, g.RIGHT, g.MOVE),      # river, no inventory, RIGHT
}
PHASES = [("kv", "ForwardStep", "BlockAfterKV"), ("q", "BlockAfterKV", "PhAttn"), ("attention", "PhAttn", "PhProj"),
          ("proj_residual_norm", "PhProj", "PhFfn"), ("ffn_norm", "PhFfn", "PhOut"), ("output", "PhOut", "PickToken"),
          ("decode", "PickToken", "ProfileTokenEnd")]


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def pyboy_version() -> str:
    import importlib.metadata as md
    return md.version("pyboy")


def static_wram(map_path: Path) -> int:
    """Bytes allocated to WRAM0 by the linker, from its own map file."""
    text = map_path.read_text()
    m = re.search(r"WRAM0 bank #0:(.*?)(?:\n\n|\Z)", text, re.S)
    m2 = re.search(r"TOTAL EMPTY: \$([0-9a-f]+) bytes", m.group(1), re.I) if m else None
    return 0x2000 - int(m2.group(1), 16) if m2 else -1


def stack_peak(gb: GB) -> int:
    """High-water mark of the 256-byte stack region, from a fill pattern the harness wrote before the run."""
    base = gb.addr("wStackBottom")
    for i in range(0x100):
        if gb.mem[base + i] != 0xA5:
            return 0x100 - i
    return 0


class Timers:
    """Attach cycle-recording hooks. Hook callbacks read the emulator counter and add no emulated cycles."""

    def __init__(self, gb: GB):
        self.gb, self.log, self.labels = gb, [], []

    def on(self, *labels):
        for name in labels:
            if name in self.gb.syms and name not in self.labels:
                bank, addr = self.gb.syms[name]
                self.gb.pyboy.hook_register(bank, addr, lambda n: self.log.append((n, self.gb.cycles())), name)
                self.labels.append(name)

    def off(self):
        for name in self.labels:
            bank, addr = self.gb.syms[name]
            self.gb.pyboy.hook_deregister(bank, addr)
        self.labels = []

    def pairs(self, a: str, b: str) -> list[int]:
        out, start = [], None
        for n, c in self.log:
            if n == a:
                start = c
            elif n == b and start is not None:
                out.append(c - start)
                start = None
        return out


def bank_counter(gb: GB) -> int:
    b = gb.read("wMB_BankSwitches", 3)
    return b[0] | b[1] << 8 | b[2] << 16


def run_kernel_workload(rig: KernelRig, situation, prompt_override=None) -> dict:
    gb = rig.gb
    prompt = prompt_override or ds.prompt_ids(*situation)
    gb.write("wSeq", prompt)
    gb.write("wSeqLen", [len(prompt)])
    gb.write("wMB_Greedy", [1])
    gb.write("wStackBottom", [0xA5] * 0xF0)  # the live frames near the top are never scanned as free
    t = Timers(gb)
    t.on("ProfileTokenStart", "ProfileTokenEnd", *{x for p in PHASES for x in p[1:]})
    banks0 = bank_counter(gb)
    rig.run(CMD_GENERATE, max_frames=200000)
    t.off()
    per_token = t.pairs("ProfileTokenStart", "ProfileTokenEnd")
    phases = {name: sum(t.pairs(a, b)) for name, a, b in PHASES}
    n = gb.read1("wSeqLen")
    return {"tokens": gb.read("wSeq", n), "per_token": per_token, "phases": phases, "banks": bank_counter(gb) - banks0, "stack": stack_peak(gb)}


def fmt(v):
    return "NA" if v is None else v


def bench_variant(version: str, rounds: int, baseline_tokens: dict | None, quality: dict, nll: float | None) -> tuple[list[dict], dict]:
    rom = ROOT / "build" / version / "test.gb"
    game_rom = ROOT / "build" / version / "gameboygpt.gb"
    model_sha = sha(ROOT / "generated" / "model.bin")
    rows, raw = [], {"version": version, "workloads": {}}
    wram = static_wram(rom.with_suffix(".map"))
    wram_game = static_wram(game_rom.with_suffix(".map"))
    rig = KernelRig(version)
    for name, sit in WORKLOADS.items():
        for rnd in range(rounds):
            r = run_kernel_workload(rig, sit)
            tok = r["per_token"]
            match = None if baseline_tokens is None else baseline_tokens.get(name) == r["tokens"]
            rows.append(_row(version, game_rom, model_sha, name, len(r["tokens"]), rnd, tok, r["banks"], wram_game, r["stack"], match, nll, quality, "kernel mode: LCD off, IME off"))
            raw["workloads"].setdefault(name, []).append(r)
    # Context-length sensitivity: same prompt extended with fixed tokens, single step, no prior cache.
    fixed = ds.prompt_ids(*WORKLOADS["PROMPT_A"]) + [ds.STOI[w] for w in ("YOU", "TURN", "LEFT", "AND", "THE", "COLD", "ROOTS", "STIR", "YOU", "GO", "LEFT")]
    raw["context_step"] = {}
    for L in (4, 8, 16):
        cycles = []
        for _ in range(rounds):
            rig.gb.write("wSeq", fixed[:L])
            rig.gb.write("wSeqLen", [L])
            cycles.append(rig.run(CMD_STEP, max_frames=20000))
        raw["context_step"][L] = cycles
    # Kernel microbenchmarks at exact label boundaries.
    t = Timers(rig.gb)
    t.on("TestMulSite", "TestMulEnd", "TestDotSite", "TestDotEnd")
    for a, b in ((1, 1), (127, 127), (-127, 127), (85, 85), (-1, -1), (0, 0)):
        rig.run(CMD_MUL, [a & 255, b & 255])
    rig.gb.write("wTestA", [(i * 37 % 255) - 127 for i in range(64)])
    rig.gb.write("wTestB", [(i * 91 % 255) - 127 for i in range(64)])
    for n in (16, 32, 64):
        rig.run(CMD_DOT, [n])
    t.off()
    raw["micro"] = {"mul_tcycles": t.pairs("TestMulSite", "TestMulEnd"), "dot_16_32_64_tcycles": t.pairs("TestDotSite", "TestDotEnd")}
    # Real kernel on real weights: tensor index 2 (w_q) is 32x32 = 1024 MACs, tensor 7 (w_f2) is 32x64 = 2048 MACs.
    rig.gb.write("wTestA", [(i * 37 % 255) - 127 for i in range(64)])
    raw["micro"]["matvec_q_1024mac_tcycles"] = rig.run(CMD_MATVEC, [2])
    raw["micro"]["matvec_f2_2048mac_tcycles"] = rig.run(CMD_MATVEC, [7])
    rig.stop()
    raw["ux_mode"] = ux_mode(version, game_rom, rows, model_sha, wram_game, nll, quality, baseline_tokens)
    raw["rom_sha256"] = sha(game_rom)
    raw["model_sha256"] = model_sha
    (ROOT / "reports" / "raw").mkdir(parents=True, exist_ok=True)
    for name in WORKLOADS:
        (ROOT / "reports" / "raw" / f"trace_{version}_{name}.json").write_text(json.dumps(raw["workloads"][name], indent=0))
    return rows, raw


def _row(version, rom, model_sha, workload, ctx, rnd, per_token, banks, wram, stack, match, nll, quality, notes):
    first = per_token[0]
    rest = per_token[1:] or per_token
    total = sum(per_token)
    p95 = sorted(rest)[max(0, int(round(0.95 * (len(rest) - 1))))]
    return {"version": version, "git_commit": git_commit(), "rom_sha256": sha(rom), "model_sha256": model_sha, "emulator": "PyBoy",
            "emulator_version": pyboy_version(), "hardware_mode": "DMG (cgb=False)", "workload": workload, "context_len": ctx,
            "output_tokens": len(per_token), "round": rnd, "first_token_tcycles": first, "decode_tcycles_total": total,
            "decode_tcycles_median": int(statistics.median(rest)), "decode_tcycles_p95": p95,
            "nominal_seconds_per_token": round(total / len(per_token) / HZ, 6), "seconds_per_event": round(total / HZ, 6),
            "bank_switches": banks, "peak_wram_bytes": wram, "peak_sram_bytes": 0, "rom_bytes": Path(rom).stat().st_size,
            "token_match_baseline": fmt(match), "heldout_nll": fmt(nll), "action_valid_rate": fmt(quality.get("action")), "notes": f"{notes}; stack_peak={stack}"}


def ux_mode(version, rom, rows, model_sha, wram, nll, quality, baseline_tokens) -> dict:
    """Same model inside the real game loop: LCD on, VBlank ISR running, words drawn as they arrive."""
    seed = 7
    gb = GB(rom)
    gb.wait_state(1, 2000)
    gb.tick(5)
    gb.write("wMB_ForceSeed", [1])
    gb.write("wMB_Seed", [seed & 255, seed >> 8])
    gb.write("wMB_Greedy", [1])
    gb.press("start")
    gb.wait_state(3, 3000)
    w, s = g.gen_world(seed), None
    s = g.start(w)
    BUTTONS = {g.LEFT: ("up", "left"), g.RIGHT: ("up", "right"), g.FORWARD: ("down", "left"), g.SEARCH: ("down", "right")}
    events = []
    t = Timers(gb)
    t.on("ProfileTokenStart", "ProfileTokenEnd", "NarrateEvent", "ThinkingDone")
    for turn in range(5):
        a = g.next_action(w, s)
        s, out = g.step(w, s, a)
        for b in BUTTONS[a]:
            gb.press(b)
        n0 = len(t.log)
        banks0 = bank_counter(gb)
        gb.press("a")
        gb.wait_for(lambda: gb.read1("wMB_State") == 6, 400000)
        log = t.log[n0:]
        starts = [c for n, c in log if n == "ProfileTokenStart"]
        ends = [c for n, c in log if n == "ProfileTokenEnd"]
        per = [e - st for st, e in zip(starts, ends)]
        narr = [c for n, c in log if n == "NarrateEvent"][0]
        done = [c for n, c in log if n == "ThinkingDone"][0]
        frames = gb.read("wMB_EventFrames", 2)
        events.append({"turn": turn, "tokens": len(per), "tcycles_per_token": per, "event_tcycles": done - narr, "on_device_frames": frames[0] | frames[1] << 8,
                       "bank_switches": bank_counter(gb) - banks0})
        gb.tick(8)
        gb.press("a")
        if not s.done:
            gb.wait_state(3, 3000)
    t.off()
    gb.stop()
    return {"events": events}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["V0"])
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()
    quality = json.loads((ROOT / "reports" / "quality.json").read_text())
    nll = json.loads((ROOT / "checkpoints" / "release.report.json").read_text())["test_nll_quant"]
    q = {"action": quality["test_heldout_greedy"]["action"]}
    raw_path = ROOT / "reports" / "benchmark.json"
    db = json.loads(raw_path.read_text()) if raw_path.exists() else {"variants": {}}
    csv_path = ROOT / "reports" / "benchmark.csv"
    existing = list(csv.DictReader(open(csv_path))) if csv_path.exists() else []
    baseline = None
    if "V0" in db["variants"]:
        baseline = {k: v[0]["tokens"] for k, v in db["variants"]["V0"]["workloads"].items()}
    for v in a.variants:
        t0 = time.time()
        rows, raw = bench_variant(v, a.rounds, None if v == "V0" else baseline, q, nll)
        if v == "V0":
            baseline = {k: x[0]["tokens"] for k, x in raw["workloads"].items()}
            for r in rows:
                r["token_match_baseline"] = "SELF"
        existing = [r for r in existing if r["version"] != v] + rows
        db["variants"][v] = raw
        s = [r for r in rows if r["round"] == 0]
        print(v, f"{time.time() - t0:.0f}s host;", " ".join(f"{r['workload']}:{r['nominal_seconds_per_token']:.3f}s/tok,{r['seconds_per_event']:.2f}s/ev,match={r['token_match_baseline']}" for r in s), flush=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, CSV_FIELDS)
        w.writeheader()
        w.writerows(existing)
    raw_path.write_text(json.dumps(db, indent=1))


if __name__ == "__main__":
    main()
