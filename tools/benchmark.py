#!/usr/bin/env python3
"""Cycle benchmarks. Timing comes from PyBoy's T-cycle counter sampled by hooks on ROM labels (calibrated by
tests/test_smoke.py); nothing here uses host time. Same weights, prompts and greedy decoding for every variant.

kernel mode: test ROM, LCD off, interrupts off. Pure inference.
game mode:   the real ROM through its real menu, with VBlank, animation and word drawing running.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, statistics, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]
from kernel_harness import KernelRig, CMD_GENERATE, CMD_STEP, CMD_PARSE, ids16, read_ids
from run_emulator import GB
from reference import conversation as cv, fixed_point as fp
from export_weights import from_blob
from training import dialogue as dl
from workloads import WORKLOADS

HZ = 4194304
FRAME_T = 70224
CSV_FIELDS = "version,git_commit,rom_sha256,model_sha256,emulator,hardware_mode,workload,round,prompt_len,output_tokens,first_token_tcycles,token_tcycles_median,token_tcycles_p95,total_tcycles,seconds_per_token,seconds_per_response,bank_switches,stack_peak_bytes,wram_bytes,sram_bytes,rom_bytes,token_match_baseline,matches_reference,mode".split(",")
PHASES = [("kv", "ForwardStep", "BlockAfterKV"), ("query", "BlockAfterKV", "PhAttn"), ("attention", "PhAttn", "PhProj"), ("projection_norm", "PhProj", "PhFfn"),
          ("feed_forward_norm", "PhFfn", "PhOut"), ("output_head", "PhOut", "PickToken"), ("decode", "PickToken", "ProfileTokenEnd")]


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def wram_bytes(map_path: Path) -> int:
    return int(re.search(r"WRAM0: (\d+) bytes used", map_path.read_text()).group(1))


def sram_bytes(map_path: Path) -> int:
    m = re.search(r"SRAM: (\d+) bytes used", map_path.read_text())
    return int(m.group(1)) if m else 0


def stack_peak(gb: GB) -> int:
    base = gb.addr("wStackBottom")
    for i in range(0x100):
        if gb.mem[base + i] != 0xA5:
            return 0x100 - i
    return 0


class Timers:
    """Cycle-recording hooks. Callbacks read the emulator counter and add no emulated cycles."""

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


def run_kernel(rig: KernelRig, sit: cv.Situation) -> dict:
    gb = rig.gb
    prompt = dl.prompt_ids(sit)
    gb.write("wSeq", ids16(prompt))
    gb.write("wSeqLen", [len(prompt)])
    gb.write("wMB_Greedy", [1])
    gb.write("wStackBottom", [0xA5] * 0xF0)
    t = Timers(gb)
    t.on("ProfileTokenStart", "ProfileTokenEnd", *{x for p in PHASES for x in p[1:]})
    banks0 = bank_counter(gb)
    rig.run(CMD_GENERATE, max_frames=400000)
    t.off()
    per = t.pairs("ProfileTokenStart", "ProfileTokenEnd")
    return {"tokens": read_ids(gb, gb.read1("wSeqLen")), "per_token": per, "phases": {n: sum(t.pairs(a, b)) for n, a, b in PHASES}, "banks": bank_counter(gb) - banks0, "stack": stack_peak(gb)}


def row(version, rom, model_sha, name, rnd, r, match, ref_ok, mode, map_path) -> dict:
    per = r["per_token"]
    rest = per[1:] or per
    total = sum(per)
    return {"version": version, "git_commit": git_commit(), "rom_sha256": sha(rom), "model_sha256": model_sha, "emulator": "PyBoy", "hardware_mode": "DMG (cgb=False)", "workload": name, "round": rnd,
            "prompt_len": dl.PROMPT_LEN, "output_tokens": len(per), "first_token_tcycles": per[0], "token_tcycles_median": int(statistics.median(rest)), "token_tcycles_p95": sorted(rest)[int(round(0.95 * (len(rest) - 1)))],
            "total_tcycles": total, "seconds_per_token": round(sum(rest) / len(rest) / HZ, 6), "seconds_per_response": round(total / HZ, 6), "bank_switches": r["banks"], "stack_peak_bytes": r["stack"],
            "wram_bytes": wram_bytes(map_path), "sram_bytes": sram_bytes(map_path), "rom_bytes": Path(rom).stat().st_size, "token_match_baseline": match, "matches_reference": ref_ok, "mode": mode}


def bench_variant(version: str, rounds: int, baseline: dict | None, model) -> tuple[list[dict], dict]:
    rom = ROOT / "build" / version / "test.gb"
    game = ROOT / "build" / version / "gameboygpt.gb"
    model_sha = sha(ROOT / "generated" / "model.bin")
    rows, raw = [], {"version": version, "workloads": {}}
    rig = KernelRig(version)
    for name, sit in WORKLOADS.items():
        want = fp.generate(model, dl.prompt_ids(sit))["tokens"]
        for rnd in range(rounds):
            r = run_kernel(rig, sit)
            match = "SELF" if baseline is None else baseline.get(name) == r["tokens"]
            rows.append(row(version, rom, model_sha, name, rnd, r, match, r["tokens"] == want, "kernel", game.with_suffix(".map")))
            raw["workloads"].setdefault(name, []).append(r)
    # One forward pass at each context length, same token stream, cold cache: cost as the conversation fills the context.
    stream = dl.prompt_ids(WORKLOADS["GREET"]) + list(range(dl.FIRST_WORD, dl.FIRST_WORD + dl.CTX))
    raw["context_step"] = {}
    for L in (9, 16, 24, dl.CTX):
        rig.gb.write("wSeq", ids16(stream[:L]))
        rig.gb.write("wSeqLen", [L])
        rig.gb.write("wRowMode", [1])
        raw["context_step"][L] = rig.run(CMD_STEP, max_frames=60000)
    # Typed input does not change the prompt length. Its cost is the parser, measured at each input length.
    raw["parser"] = {}
    for n in (0, 5, 18, cv.MAX_INPUT):
        text = ("PIZZA MARGHERITA WITH NO CHEESE PLEASE"[:n]).ljust(n)
        rig.gb.write("wInput", [ord(c) for c in text] + [0])
        rig.gb.write("wInputLen", [n])
        raw["parser"][n] = rig.run(CMD_PARSE)
    rig.stop()
    return rows, raw


def game_mode(version: str, model) -> dict:
    """The real ROM through its real menu. Sampled decoding, pinned seed. Latency runs from the confirming press to each token."""
    from chat_harness import action, boot, generated, next_page, pin, say
    rom = ROOT / "build" / version / "gameboygpt.gb"
    gb = boot(rom=rom)
    gb.write("wStackBottom", [0xA5] * 0xF0)
    t = Timers(gb)
    t.on("ProfileTokenStart", "ProfileTokenEnd", "BuildPrompt")
    events = []
    plan = [("action", 0), ("action", 1), ("action", 2), ("say", "MY NAME IS BOB"), ("action", 3), ("say", "WHAT IS YOUR CPU"), ("action", 4), ("say", "I WILL DESTROY YOU")] * 2
    state = cv.State()
    for i, (kind, what) in enumerate(plan):
        seed = 0x6100 + i * 13
        pin(gb, seed)
        n0 = len(t.log)
        banks0 = bank_counter(gb)
        if kind == "action":
            action(gb, what)
            parsed = cv.Parsed(cv.ACTION_INTENT[what], "NONE")
        else:
            say(gb, what)
            parsed = cv.parse(what)
        before, state = state, cv.apply_turn(state, parsed)
        want = fp.generate(model, dl.prompt_ids(cv.situation(before, state)), greedy=False, rng=seed)["generated"]
        log = t.log[n0:]
        start = next(c for n, c in log if n == "BuildPrompt")
        ends = [c for n, c in log if n == "ProfileTokenEnd"]
        starts = [c for n, c in log if n == "ProfileTokenStart"]
        per = [b - a for a, b in zip(starts, ends)]
        frames = gb.read("wLastEventFrames", 2)
        events.append({"input": str(what), "tokens": len(per), "first_token_s": (ends[0] - start) / HZ, "first_word_s": (ends[1] - start) / HZ if len(ends) > 1 else None, "response_s": (ends[-1] - start) / HZ,
                       "tcycles_per_token": per, "on_device_frames": frames[0] | frames[1] << 8, "bank_switches": bank_counter(gb) - banks0, "matches_reference": generated(gb) == want})
        next_page(gb)
    t.off()
    peak = stack_peak(gb)
    gb.stop()
    gen = [x for e in events for x in e["tcycles_per_token"][1:]]
    return {"events": events, "stack_peak": peak, "seconds_per_token": sum(gen) / len(gen) / HZ, "seconds_per_response": statistics.mean(e["response_s"] for e in events),
            "first_token_s": statistics.mean(e["first_token_s"] for e in events), "first_word_s": statistics.mean(e["first_word_s"] for e in events), "mean_tokens": statistics.mean(e["tokens"] for e in events),
            "all_match_reference": all(e["matches_reference"] for e in events)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["V0"])
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--game", nargs="*", default=["V6T"])
    a = ap.parse_args()
    model = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    raw_path = ROOT / "reports" / "benchmark.json"
    csv_path = ROOT / "reports" / "benchmark.csv"
    db = json.loads(raw_path.read_text()) if raw_path.exists() else {"variants": {}, "game": {}}
    existing = list(csv.DictReader(open(csv_path))) if csv_path.exists() else []
    baseline = {k: v[0]["tokens"] for k, v in db["variants"]["V0"]["workloads"].items()} if "V0" in db["variants"] else None
    for v in a.variants:
        rows, raw = bench_variant(v, a.rounds, None if v == "V0" else baseline, model)
        if v == "V0":
            baseline = {k: x[0]["tokens"] for k, x in raw["workloads"].items()}
        existing = [r for r in existing if r["version"] != v] + rows
        db["variants"][v] = raw
        print(v, " ".join(f"{r['workload']}:{r['seconds_per_token']:.3f}s/tok,{r['seconds_per_response']:.1f}s,match={r['token_match_baseline']},ref={r['matches_reference']}" for r in rows if r["round"] == 0), flush=True)
    for v in a.game:
        db["game"][v] = game_mode(v, model)
        g = db["game"][v]
        print("game", v, {k: g[k] for k in ("seconds_per_token", "seconds_per_response", "first_token_s", "first_word_s", "mean_tokens", "stack_peak", "all_match_reference")}, flush=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, CSV_FIELDS)
        w.writeheader()
        w.writerows(existing)
    raw_path.write_text(json.dumps(db, indent=1))


if __name__ == "__main__":
    main()
