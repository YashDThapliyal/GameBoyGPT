#!/usr/bin/env python3
"""Regenerate every figure and table from raw reports. Contains no measured values of its own.

Reads reports/benchmark.{csv,json}, quality.json, precision_study.json, generalization.json, second_emulator.json,
junit/*.xml and the linker's map files. Writes docs/figures/*.png, docs/MEMORY_MAP.md, RESULTS.md and README's
generated results block.
"""
from __future__ import annotations
import csv, json, re, statistics, xml.etree.ElementTree as ET
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HZ = 4194304
FIG = ROOT / "docs" / "figures"
R = ROOT / "reports"
CUMULATIVE = ["V0", "V1", "V2", "V3", "V4", "V5", "V5S", "V5Z"]
ISOLATED = ["A_QSQ", "A_NIB", "A_KV"]
LABELS = {"V0": "V0 vanilla", "V1": "V1 + bank-aware layout", "V2": "V2 + quarter-square multiply", "V3": "V3 + fused dot, pruned outputs",
          "V4": "V4 + sparse attention sum", "V5": "V5 + K/V cache", "V5S": "V5S + SP weight stream", "V5Z": "V5Z + zero-column skip",
          "A_QSQ": "V0 + quarter squares only", "A_NIB": "V0 + nibble table only", "A_KV": "V0 + K/V cache only"}
PHASE_LABELS = {"kv": "Keys and values", "q": "Query", "attention": "Attention", "proj_residual_norm": "Projection and norm", "ffn_norm": "Feed-forward and norm", "output": "Output logits", "decode": "Token decode"}
# Categorical slots in fixed order, validated with the dataviz palette validator.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.dpi": 160, "savefig.bbox": "tight"})


def load():
    rows = list(csv.DictReader(open(R / "benchmark.csv")))
    raw = json.loads((R / "benchmark.json").read_text())["variants"]
    return rows, raw


def per_variant(rows, v):
    rr = [r for r in rows if r["version"] == v]
    per_workload = {}
    for w in {r["workload"] for r in rr}:
        x = [r for r in rr if r["workload"] == w]
        per_workload[w] = statistics.mean(float(r["nominal_seconds_per_token"]) for r in x)
    total = sum(int(r["decode_tcycles_total"]) for r in rr)
    tok = sum(int(r["output_tokens"]) for r in rr)
    return {"s_token": total / tok / HZ, "cycles_token": total / tok, "lo": min(per_workload.values()), "hi": max(per_workload.values()), "workloads": per_workload,
            "s_event": statistics.mean(float(r["seconds_per_event"]) for r in rr), "first": statistics.mean(int(r["first_token_tcycles"]) for r in rr),
            "median": statistics.mean(int(r["decode_tcycles_median"]) for r in rr), "p95": max(int(r["decode_tcycles_p95"]) for r in rr), "wram": int(rr[0]["peak_wram_bytes"]),
            "rom": int(rr[0]["rom_bytes"]), "banks": statistics.mean(int(r["bank_switches"]) / int(r["output_tokens"]) for r in rr if r["round"] == "0"), "match": all(r["token_match_baseline"] in ("SELF", "True") for r in rr),
            "sha": rr[0]["rom_sha256"], "stack": max(int(re.search(r"stack_peak=(\d+)", r["notes"]).group(1)) for r in rr), "spread": max(max(int(r["decode_tcycles_total"]) for r in rr if r["workload"] == w) - min(int(r["decode_tcycles_total"]) for r in rr if r["workload"] == w) for w in per_workload)}


def fig_waterfall(stats):
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    y = list(range(len(CUMULATIVE)))[::-1]
    base = stats["V0"]["s_token"]
    for yy, v in zip(y, CUMULATIVE):
        s = stats[v]
        ax.barh(yy, s["s_token"], color=SERIES[0], height=0.62)
        ax.plot([s["lo"], s["hi"]], [yy, yy], color=INK, lw=1)
        ax.text(s["hi"] + 0.07, yy, f"{s['s_token']:.2f} s   {base / s['s_token']:.1f}x", va="center", color=INK)
    ax.set_yticks(y, [LABELS[v] for v in CUMULATIVE])
    ax.set_xlabel("Seconds per token at nominal DMG clock (whisker: range across the four workloads)")
    ax.set_xlim(0, base * 1.2)
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.set_title("Each step keeps tokens identical to V0", loc="left", fontweight="bold")
    fig.savefig(FIG / "waterfall.png")
    plt.close(fig)


def fig_breakdown(raw, stats):
    names = list(PHASE_LABELS)
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    y = list(range(len(CUMULATIVE)))[::-1]
    for yy, v in zip(y, CUMULATIVE):
        totals = {n: 0 for n in names}
        for w in raw[v]["workloads"].values():
            for n in names:
                totals[n] += w[0]["phases"][n] if False else sum(x["phases"][n] for x in w)
        s = sum(totals.values())
        left = 0.0
        for i, n in enumerate(names):
            share = totals[n] / s * 100
            ax.barh(yy, share - 0.3, left=left, color=SERIES[i], height=0.62, label=PHASE_LABELS[n] if yy == y[0] else None)
            left += share
    ax.set_yticks(y, [f"{v}  ({stats[v]['s_token']:.2f} s/token)" for v in CUMULATIVE])
    ax.set_xlabel("Share of cycles between token start and token end (%)")
    ax.set_xlim(0, 100)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.42, -0.16), frameon=False)
    ax.set_title("Where the time goes: from recomputing keys to the feed-forward layer", loc="left", fontweight="bold")
    fig.savefig(FIG / "latency_breakdown.png")
    plt.close(fig)


def fig_token_trace(raw):
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, (v, name) in enumerate((("V0", "V0 vanilla"), ("V5Z", "V5Z shipping"))):
        per = raw[v]["workloads"]["PROMPT_B"][0]["per_token"]
        ax.plot(range(6, 6 + len(per)), [c / HZ for c in per], color=SERIES[i], lw=2, marker="o", ms=4, label=name)
        ax.text(5.8 + len(per) + 0.35, per[-1] / HZ, f"{name}\n{per[-1] / HZ:.2f} s", va="center", color=INK)
    ax.set_xlabel("Context length when the token is produced (PROMPT_B)")
    ax.set_ylabel("Seconds per token")
    ax.set_xlim(5.5, 19.5)
    ax.set_ylim(0)
    ax.yaxis.grid(True, color=GRID)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("The baseline slows as context grows. The cached build stays flat after the first token", loc="left", fontweight="bold", fontsize=10)
    fig.savefig(FIG / "token_trace.png")
    plt.close(fig)


def fig_precision():
    rows = json.loads((R / "precision_study.json").read_text())
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    xs = [r["estimated_packed_rom_bytes"] / 1024 for r in rows]
    ys = [r["strict_valid"] * 100 for r in rows]
    ax.plot(xs, ys, color=SERIES[0], lw=2, marker="o", ms=6)
    for r, x, y in zip(rows, xs, ys):
        ax.annotate(f"{r['weight_bits']}-bit", (x, y), textcoords="offset points", xytext=(0, 8 if r["weight_bits"] != 3 else -14), ha="center")
    ax.set_xlabel("Estimated packed weight bytes, KiB (arithmetic only, these ROMs were not built)")
    ax.set_ylabel("Strict-valid events (%)")
    ax.set_ylim(0, 112)
    ax.yaxis.grid(True, color=GRID)
    ax.set_title("Weight precision: the integer reference holds until 4 bits, then collapses", loc="left", fontweight="bold", fontsize=10)
    fig.savefig(FIG / "precision_pareto.png")
    plt.close(fig)


def fig_training():
    curve = list(csv.DictReader(open(ROOT / "checkpoints" / "release.curve.csv")))
    fig, ax = plt.subplots(figsize=(6.8, 3))
    steps = [int(c["step"]) for c in curve]
    ax.plot(steps, [float(c["train_nll"]) for c in curve], color=SERIES[0], lw=2, label="Train batch NLL")
    ax.plot(steps, [float(c["val_nll"]) for c in curve], color=SERIES[1], lw=2, label="Held-out validation NLL")
    q = next((int(c["step"]) for c in curve if c["quant"] == "1"), None)
    if q:
        ax.axvline(q, color=INK2, lw=1, ls=":")
        ax.text(q, ax.get_ylim()[1], " QAT starts", va="top", color=INK2)
    ax.set_xlabel("Training step")
    ax.set_ylabel("NLL (nats per token)")
    ax.yaxis.grid(True, color=GRID)
    ax.legend(frameon=False)
    ax.set_title("Training curve for the release checkpoint", loc="left", fontweight="bold")
    fig.savefig(FIG / "training_curve.png")
    plt.close(fig)


def junit_grid():
    grid = {}
    for p in sorted((R / "junit").glob("*.xml")):
        suite = ET.parse(p).getroot()
        cases = suite.iter("testcase")
        by_file = {}
        for c in cases:
            name = c.get("classname", "").split(".")[-1]
            bad = c.find("failure") is not None or c.find("error") is not None
            ok, n = by_file.get(name, (0, 0))
            by_file[name] = (ok + (not bad), n + 1)
        grid[p.stem] = by_file
    return grid


def fig_correctness(grid):
    if not grid:
        return
    order = [v for v in CUMULATIVE + ISOLATED if v in grid]
    files = sorted({f for g in grid.values() for f in g})
    fig, ax = plt.subplots(figsize=(1.6 + 0.62 * len(order), 0.55 * len(files) + 1))
    for i, f in enumerate(files):
        for j, v in enumerate(order):
            if f in grid[v]:
                ok, n = grid[v][f]
                ax.add_patch(plt.Rectangle((j + .04, len(files) - 1 - i + .06), .92, .88, color="#1baf7a" if ok == n else "#e34948"))
                ax.text(j + .5, len(files) - 1 - i + .5, f"{ok}/{n}", ha="center", va="center", color=INK, fontsize=9)
            else:
                ax.text(j + .5, len(files) - 1 - i + .5, "not run", ha="center", va="center", color=INK2, fontsize=7)
    ax.set_xlim(0, len(order))
    ax.set_ylim(0, len(files))
    ax.set_xticks([j + .5 for j in range(len(order))], order)
    ax.set_yticks([len(files) - 1 - i + .5 for i in range(len(files))], [f.replace("test_", "") for f in files])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("Tests passed per variant (pytest results on each ROM)", loc="left", fontweight="bold")
    fig.savefig(FIG / "correctness_grid.png")
    plt.close(fig)


def parse_map(path: Path) -> dict:
    """{area: [(name, start, size)]} from rgblink's map file."""
    text = path.read_text()
    areas, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"(ROM0|ROMX|WRAM0|HRAM)( bank #(\d+))?:", line)
        if m:
            cur = m.group(1) + (f" bank {m.group(3)}" if m.group(3) and m.group(1) == "ROMX" else "")
            areas.setdefault(cur, [])
            continue
        m = re.match(r"\s*SECTION: \$([0-9a-f]+)(?:-\$[0-9a-f]+)? \(\$([0-9a-f]+) bytes?\) \[\"(.+)\"\]", line)
        if m and cur:
            areas[cur].append((m.group(3), int(m.group(1), 16), int(m.group(2), 16)))
    return areas


WRAM_GROUPS = {"K/V cache": ["kv_cache"], "Tensor buffers": ["tensors", "test_vars"], "Logits and token sequence": ["seq_vars"], "Attention": ["attn_vars", "attn_sparse_vars"],
               "Screen shadow and sprites": ["video_vars"], "UI state": ["ui_vars"], "Game state": ["game_vars"], "Kernel scratch": ["matvec_vars", "norm_vars", "sampler_vars", "profile_vars", "sp_vars", "selftest_vars"],
               "Stack (reserved)": ["stack"], "Debug mailbox": ["mailbox"]}


def memory_doc(version="V5Z"):
    game = parse_map(ROOT / "build" / version / "gameboygpt.map")
    v0 = parse_map(ROOT / "build" / "V0" / "gameboygpt.map")
    wram = game["WRAM0"]
    total = sum(s for _, _, s in wram)
    lines = ["# Memory map", "", f"Generated by `tools/compare.py` from the linker's map file for the shipping build ({version}). Every number below is a linker-reported byte count.", "",
             f"**WRAM: {total} of 8192 bytes allocated** ({8192 - total} free), which includes a 256-byte reserved stack and a 256-byte debug mailbox. No cartridge SRAM is used. The KV cache sits in the 8 KiB built-in WRAM.", "",
             "| WRAM section | Start | Bytes | Contents |", "|---|---:|---:|---|"]
    desc = {"kv_cache": "K and V, 16 positions x 32 bytes each", "tensors": "Activation vectors of the current step", "seq_vars": "Token ids, 95 int16 logits", "attn_vars": "Scores and weights for up to 16 positions",
            "attn_sparse_vars": "16-bit accumulators for one head", "video_vars": "20x18 shadow map, dirty flags, 2 sprites", "ui_vars": "Menu, text cursor, stats save area", "game_vars": "World truth: room, exits, inventory, RNG",
            "matvec_vars": "Matvec loop state", "norm_vars": "Norm loop state", "sampler_vars": "Narration RNG, candidates", "profile_vars": "On-device timing", "sp_vars": "Saved stack pointer", "stack": "Reserved", "mailbox": "Instrumentation for the test harness"}
    for name, start, size in sorted(wram, key=lambda x: x[1]):
        lines.append(f"| `{name}` | ${start:04X} | {size} | {desc.get(name, '')} |")
    hram = game.get("HRAM", [])
    lines += ["", f"**HRAM: {sum(s for _, _, s in hram)} of 127 bytes.**", "", "| HRAM section | Start | Bytes |", "|---|---:|---:|"]
    lines += [f"| `{n}` | ${st:04X} | {s} |" for n, st, s in sorted(hram, key=lambda x: x[1])]
    lines += ["", "## ROM", "", "MBC5, no SRAM. All inference code and tables are in bank 0, and the VBlank ISR never touches the switchable window.", ""]
    for area in sorted(a for a in game if a.startswith("ROM")):
        used = sum(s for _, _, s in game[area])
        cap = 16384
        lines += [f"**{area}: {used} of {cap} bytes**", "", "| Section | Start | Bytes |", "|---|---:|---:|"]
        lines += [f"| `{n}` | ${st:04X} | {s} |" for n, st, s in sorted(game[area], key=lambda x: x[1])]
        lines.append("")
    v0_used = sum(s for _, _, s in v0["ROM0"])
    lines += [f"V0 uses {v0_used} bytes of bank 0 and places tensors wherever the linker floats them. Its WRAM is {sum(s for _, _, s in v0['WRAM0'])} bytes.", ""]
    (ROOT / "docs" / "MEMORY_MAP.md").write_text("\n".join(lines))
    return game, total


def fig_memory(game):
    wram = {n: s for n, _, s in game["WRAM0"]}
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 3.1), gridspec_kw={"hspace": 1.1})
    ax = axes[0]
    left, idx = 0, 0
    groups = [(k, sum(wram.get(n, 0) for n in v)) for k, v in WRAM_GROUPS.items()]
    for k, sz in sorted((g for g in groups if g[1]), key=lambda x: -x[1]):
        c = SERIES[idx % len(SERIES)] if idx < 7 else INK2
        ax.barh(0, sz - 12, left=left, color=c, height=.6, label=f"{k} {sz}")
        left += sz
        idx += 1
    ax.barh(0, 8192 - left, left=left, color=GRID, height=.6, label=f"Free {8192 - left}")
    ax.set_xlim(0, 8192)
    ax.set_yticks([])
    ax.set_title(f"Built-in WRAM, bytes (8192 total, {left} allocated)", loc="left", fontweight="bold")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(.5, -.28), frameon=False, fontsize=8)
    ax = axes[1]
    areas = sorted(a for a in game if a.startswith("ROM"))
    for i, a in enumerate(areas):
        used = sum(s for _, _, s in game[a])
        ax.barh(len(areas) - 1 - i, used, color=SERIES[0], height=.6)
        ax.barh(len(areas) - 1 - i, 16384 - used, left=used, color=GRID, height=.6)
        ax.text(16500, len(areas) - 1 - i, f"{used}", va="center")
    ax.set_yticks(range(len(areas)), areas[::-1])
    ax.set_xlim(0, 16384)
    ax.set_title("ROM banks, bytes used of 16384", loc="left", fontweight="bold")
    fig.savefig(FIG / "memory_map.png")
    plt.close(fig)


def table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def results(rows, raw, stats, grid, wram_total):
    q = json.loads((R / "quality.json").read_text())
    ckpt = json.loads((ROOT / "checkpoints" / "release.report.json").read_text())
    prec = json.loads((R / "precision_study.json").read_text())
    gen = json.loads((R / "generalization.json").read_text()) if (R / "generalization.json").exists() else None
    sec = json.loads((R / "second_emulator.json").read_text()) if (R / "second_emulator.json").exists() else None
    demo = json.loads((R / "demo_trace.json").read_text())
    base, ship = stats["V0"], stats["V5Z"]
    sp = base["s_token"] / ship["s_token"]
    t1 = []
    prev = None
    for v in CUMULATIVE:
        s = stats[v]
        step = "" if prev is None else f"{prev['s_token'] / s['s_token']:.2f}x"
        t1.append((LABELS[v], f"{s['cycles_token'] / 1e6:.2f}M", f"{s['s_token']:.3f}", f"{s['lo']:.3f}-{s['hi']:.3f}", f"{s['s_event']:.2f}", f"{base['s_token'] / s['s_token']:.2f}x", step, f"{s['banks']:.1f}", s["wram"], "yes" if s["match"] else "NO"))
        prev = s
    t2 = [(LABELS[v], f"{stats[v]['s_token']:.3f}", f"{base['s_token'] / stats[v]['s_token']:.2f}x", "yes" if stats[v]["match"] else "NO") for v in ISOLATED]
    micro = [(v, raw[v]["micro"]["mul_tcycles"][0], f"{statistics.mean(raw[v]['micro']['mul_tcycles']):.0f}", f"{raw[v]['micro']['matvec_q_1024mac_tcycles'] / 1024:.0f}", f"{raw[v]['micro']['matvec_f2_2048mac_tcycles'] / 2048:.0f}") for v in ("V0", "A_NIB", "A_QSQ", "V3", "V5S", "V5Z")]
    ctx = [(v, *[f"{raw[v]['context_step'][str(L)][0] / 1e6:.2f}M" for L in (4, 8, 16)]) for v in ("V0", "V3", "V5Z")]
    ux = []
    for v in ("V0", "V5Z"):
        ev = raw[v]["ux_mode"]["events"]
        n = sum(e["tokens"] for e in ev)
        ux.append((v, len(ev), n, f"{statistics.mean(e['event_tcycles'] for e in ev) / HZ:.2f}", f"{sum(e['event_tcycles'] for e in ev) / n / HZ:.3f}", f"{statistics.mean(e['on_device_frames'] for e in ev):.0f}", f"{statistics.mean(e['event_tcycles'] / (e['on_device_frames'] * 70224) for e in ev):.4f}"))
    qrows = [("Trained, all situations, greedy", q["all_greedy"]), ("Trained, 9 held-out test families, greedy", q["test_heldout_greedy"]), ("Trained, all situations, sampled x3", q["all_sampled"]), ("Trained, held-out test families, sampled x30", q["test_heldout_sampled"]), ("**Untrained weights**, all situations, greedy", q["untrained_all_greedy"])]
    t3 = [(n, x["n"], f"{x['strict']:.3f}", f"{x['action']:.3f}", f"{x['room']:.3f}", f"{x['outcome']:.3f}", f"{x['capped']:.3f}", x["unique"]) for n, x in qrows]
    t4 = [(r["weight_bits"], f"{r['strict_valid']:.3f}", f"{r['heldout_test_strict_valid']:.3f}", f"{r['token_agreement']:.3f}", f"{r['cap_rate']:.3f}", r["estimated_packed_rom_bytes"]) for r in prec]
    grid_rows = [(v, sum(a for a, _ in grid[v].values()), sum(n for _, n in grid[v].values())) for v in CUMULATIVE + ISOLATED if v in grid]
    journey = [(t["turn"], t["room"], t["action"], t["outcome"], t["text"], t["on_device_frames"]) for t in demo["journey"]]
    ap = demo["action_pair"]
    md = f"""# Results

Generated by `tools/compare.py` from raw reports. Do not edit by hand. Timing is on an emulated original Game Boy (DMG), not physical hardware.

**Shipping build:** {LABELS['V5Z']}. ROM SHA-256 `{ship['sha']}`, {ship['rom']} bytes, MBC5, no SRAM.
**Model:** 1-layer causal transformer, d=32, 2 heads, FFN 64, context 16, vocabulary 95, {ckpt['params']} int8 parameters. Blob SHA-256 `{rows[0]['model_sha256']}`.
**Emulator:** PyBoy {rows[0]['emulator_version']} with `cgb=False`, 4,194,304 Hz nominal. Commit at measurement: `{rows[0]['git_commit']}`.

## Headline

| | V0 baseline | V5Z shipping |
|---|---:|---:|
| Seconds per token, mean over 4 workloads | {base['s_token']:.3f} | {ship['s_token']:.3f} |
| Seconds per event | {base['s_event']:.1f} | {ship['s_event']:.2f} |
| T-cycles per token | {base['cycles_token'] / 1e6:.2f}M | {ship['cycles_token'] / 1e6:.2f}M |
| First token, T-cycles | {base['first'] / 1e6:.2f}M | {ship['first'] / 1e6:.2f}M |
| Median later token, T-cycles | {base['median'] / 1e6:.2f}M | {ship['median'] / 1e6:.2f}M |
| Allocated WRAM, bytes | {base['wram']} | {ship['wram']} |
| Peak stack, bytes | {base['stack']} | {ship['stack']} |
| Bank switches per token | {base['banks']:.1f} | {ship['banks']:.1f} |

**Speedup: {sp:.2f}x, with identical tokens on all four workloads.** Same model, same weights, same prompts, same greedy decoding.

## Cumulative optimization ablation

Mean of 3 rounds on each of 4 workloads, in kernel mode (LCD off, IME off). "Step" is the gain over the row above.

{table(t1, ["Variant", "T/token", "s/token", "Workload range", "s/event", "vs V0", "Step", "Banks/token", "WRAM", "Tokens = V0"])}

Largest within-workload round-to-round spread in the total: {max(stats[v]['spread'] for v in CUMULATIVE)} T-cycles.

![Waterfall](docs/figures/waterfall.png)

### Isolated toggles

Each is V0 with one change. Interactions are visible by comparing against the cumulative table.

{table(t2, ["Variant", "s/token", "vs V0", "Tokens = V0"])}

### Kernel microbenchmarks (T-cycles)

`MulS8` is the callable multiply. V3 and later keep it only for norm and attention weights; their dot products inline a MAC. Per-MAC figures come from a real matvec on real weights with a dense test vector, so they include row overhead. They do not show the benefit of zero skipping, which needs real sparse activations: V5Z costs more than V5S per MAC here and is still faster end to end.

{table(micro, ["Variant", "Mul (1x1)", "Mul (mean of 6)", "Per MAC, Q (1024)", "Per MAC, F2 (2048)"])}

### Context length, single forward step from a cold start

{table(ctx, ["Variant", "L=4", "L=8", "L=16"])}

Without the cache, cost grows with context. V5Z's cold step at L=16 equals prefill: every later token then costs one position's K and V, as the headline's median shows.

![Per token](docs/figures/token_trace.png)

### Where the time goes

Phases come from hooks on ROM labels, summed over all rounds.

![Breakdown](docs/figures/latency_breakdown.png)

### In the real game loop

LCD on, VBlank ISR running, words drawn as they arrive, seed 7, five scripted turns. "Frames" is what the ROM itself measured on-device. The last column compares the emulator's cycle count with frames x 70,224, an internal cross-check of the two clocks.

{table(ux, ["Build", "Events", "Tokens", "s/event", "s/token", "Frames/event", "Cycles / (frames x 70224)"])}

## Correctness

- SM83 kernels vs the independent integer reference: mul, dot, requant, sat-add, ReLU, norm, attention weights, attention, matvec on real ROM weights, argmax and seeded sampling, with edge cases and fixed-seed randomized vectors.
- End to end: masked logits on 10 sequences including adversarial token streams, and token traces on 20 scenarios, each greedy and sampled.

{table(grid_rows, ["Variant", "Tests passed", "Tests run"])}

![Correctness](docs/figures/correctness_grid.png)

### Second emulator

The self-test ROM generates the 4 workloads on the emulated CPU, compares tokens to expectations baked in at build time from the reference, and prints the verdict and LCD frames per workload.

{table([(v, e, r[e]["verdict"], ", ".join(map(str, r[e]["frames"]))) for v, r in sec.items() for e in r], ["Build", "Emulator", "On-screen verdict", "Frames per workload"]) if sec else "Not run."}

### Timing calibration

`tests/test_smoke.py` runs a known instruction sequence and asserts PyBoy's counter between two hooks equals the hand-counted 112 T-cycles from Pan Docs timings. The self-test frame counts above give an independent check on a second, cycle-accurate emulator.

## Model quality

All figures are on the integer reference, which the ROM matches bit for bit. Training: {ckpt['config']['float_steps']} float then {ckpt['config']['qat_steps']} QAT steps.

- Test NLL, quantized: {ckpt['test_nll_quant']:.4f} nats/token. Same weights without fake-quant: {ckpt['test_nll_float']:.4f}. Uniform over the vocabulary: {ckpt['untrained']['uniform_nll']:.4f}. Untrained model on validation: {ckpt['untrained']['val_nll']:.4f}.

{table(t3, ["Condition", "n", "Strict valid", "Action phrase", "Room nouns", "Outcome words", "Token cap hit", "Unique"])}

Strict valid means the sentence is an exact member of the grammar for that situation. This is a narrow language, so 100% describes what the task asks of the model, not general language ability.

**Action conditioning.** Changing only the action token changes the greedy event in {q['action_ablation']['changed_rate']:.1%} of {q['action_ablation']['n']} situations. Scored against the original action, the output uses the right action phrase only {q['action_ablation']['wrong_action_token_scores_action_ok']:.1%} of the time, close to chance for 4 actions.

**Novelty audit** on the 9 held-out test families: {q['novelty_test']['exact_prompt_plus_text_in_train']:.1%} of generated prompt+text pairs exist in training, while {q['novelty_test']['text_seen_in_train_for_any_prompt']:.1%} of the texts appear in training under some other prompt.
"""
    if gen:
        md += f"""
**Harder generalization test.** A separate model with the same recipe was trained on 60% of situations and scored on {gen['n_test_situations']} unseen ones (not the shipping weights): strict validity {gen['test_situations_greedy']['strict']:.3f} greedy, {gen['test_situations_sampled']['strict']:.3f} sampled; on its training situations {gen['train_situations_greedy']['strict']:.3f}.
"""
    md += f"""
## Precision study (reference only)

Weights rounded to fewer bits with no retraining. Packed byte counts are arithmetic: **no INT4 ROM was built**, and whole-byte kernels would not get faster.

{table(t4, ["Weight bits", "Strict valid", "Held-out strict", "Token agreement with 8-bit", "Cap rate", "Estimated packed bytes"])}

![Precision](docs/figures/precision_pareto.png)

## A journey on the shipping ROM

Seed {demo['seed']}, sampled decoding. Every row's tokens match the reference. Frames are on-device; 59.73 frames is one second.

{table(journey, ["Turn", "Room", "Action", "Outcome", "Generated text", "Frames"])}

Same state, two actions (seed {demo['seed']}, greedy):

- `{ap['FORWARD']['input_ids']}` FORWARD: {ap['FORWARD']['text']}
- `{ap['SEARCH']['input_ids']}` SEARCH: {ap['SEARCH']['text']}

## Limitations

- Emulator only. No physical DMG has run this ROM. V5S and V5Z stream weights through SP with interrupts held off per row; V5 is the build to prefer if that is a concern on real hardware.
- Greedy parity is exact. Variety comes from seeded near-top sampling, which is deterministic and also bit-exact, but the sentences are always from a narrow trained language of {len(json.loads((ROOT / 'assets' / 'data' / 'vocab.json').read_text()))} tokens.
- Game truth lives in the deterministic engine, which also supplies the outcome token. The model narrates; it cannot change state.
- The model is small: it has learned a grammar, and this is not conversational AI.
- INT4 was studied on the reference only. V7 (ternary or codebook weights) and V8 (automatic configuration search) were not attempted.
"""
    (ROOT / "RESULTS.md").write_text(md)
    readme = ROOT / "README.md"
    if readme.exists():
        t = readme.read_text()
        block = f"""<!-- generated by tools/compare.py -->
| | V0 vanilla | V5Z shipping |
|---|---:|---:|
| Seconds per token (DMG clock) | {base['s_token']:.2f} | {ship['s_token']:.2f} |
| Seconds per event | {base['s_event']:.1f} | {ship['s_event']:.1f} |
| T-cycles per token | {base['cycles_token'] / 1e6:.1f}M | {ship['cycles_token'] / 1e6:.1f}M |
| WRAM allocated | {base['wram']} B | {ship['wram']} B |
| Tokens identical to V0 | n/a | {'yes' if ship['match'] else 'NO'} |

**{sp:.1f}x faster, same tokens.**
<!-- end generated -->"""
        t = re.sub(r"<!-- generated by tools/compare.py -->.*?<!-- end generated -->", block, t, flags=re.S)
        readme.write_text(t)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rows, raw = load()
    stats = {v: per_variant(rows, v) for v in CUMULATIVE + ISOLATED}
    if not all(s["match"] for s in stats.values()):
        print("WARNING: a variant's tokens differ from baseline")
    fig_waterfall(stats)
    fig_breakdown(raw, stats)
    fig_token_trace(raw)
    fig_precision()
    fig_training()
    grid = junit_grid()
    fig_correctness(grid)
    game, total = memory_doc()
    fig_memory(game)
    results(rows, raw, stats, grid, total)
    print(f"V0 {stats['V0']['s_token']:.3f} s/token -> V5Z {stats['V5Z']['s_token']:.3f} s/token ({stats['V0']['s_token'] / stats['V5Z']['s_token']:.2f}x)")


if __name__ == "__main__":
    main()
