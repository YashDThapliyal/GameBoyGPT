#!/usr/bin/env python3
"""Phase 3 model scaling study. One process per candidate: trains, scores on held-out families, projects DMG cost.

    python tools/scaling_study.py NAME      train one candidate, writes reports/study/NAME.json
    python tools/scaling_study.py --all     run every candidate, a few at a time
Costs here are projections from MAC counts, calibrated on the measured V5Z kernel. The shipped model is measured on the ROM.
"""
from __future__ import annotations
import argparse, json, math, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import torch
import torch.nn.functional as F
from training import dialogue as dl
from training.model import Config, GruLm, TinyTransformer

OUT = ROOT / "reports" / "study"
CLOCK = 4194304
T_PER_MAC = 232     # measured V5S kernel, docs/PERFORMANCE.md
T_PER_ROW = 170     # entry, shift and store per output element, estimated from the kernel listing
CANDIDATES = {
    "d32_k8": dict(d=32, ffn=64, layers=1, k=8),
    "d32_k12": dict(d=32, ffn=64, layers=1, k=12),
    "d32_k16": dict(d=32, ffn=64, layers=1, k=16),
    "d32_full": dict(d=32, ffn=64, layers=1, k=0),
    "d32_f32_k12": dict(d=32, ffn=32, layers=1, k=12),
    "d32_L2_k12": dict(d=32, ffn=64, layers=2, k=12),
    "d64_k32": dict(d=64, ffn=128, layers=1, k=32),
    "d96_k32": dict(d=96, ffn=192, layers=1, k=32),
    "d128_k32": dict(d=128, ffn=256, layers=1, k=32),
    "d128_L2_k32": dict(d=128, ffn=256, layers=2, k=32),
    "gru64_k16": dict(gru=True, d=64, k=16),
}


def macs_per_token(c: dict, vocab_rows: int, position: float) -> dict:
    d, f, L, k = c["d"], c.get("ffn", 0), c.get("layers", 1), c.get("k", 0)
    if c.get("gru"):
        gen = 6 * d * d + d * k + vocab_rows * k
        return {"macs": gen, "rows": 3 * d + k + vocab_rows, "prompt_macs": 6 * d * d, "prompt_rows": 3 * d}
    hd = d // 2
    attn = int(2 * hd * position * 2)  # one dot per position plus value mixing, per head
    block = 2 * d * d + d * d + attn + d * d + d * f + int(f * d * 0.5)  # zero skip removes about half of the FFN-out work
    head = (d * k + vocab_rows * k) if k else vocab_rows * d
    return {"macs": L * block + head, "rows": L * (5 * d + f) + (k + vocab_rows if k else vocab_rows), "prompt_macs": L * 2 * d * d, "prompt_rows": L * 2 * d}


def projected(c: dict, tokens: float) -> dict:
    rows = len(dl.VOCAB) - dl.FIRST_GEN
    m = macs_per_token(c, rows, dl.PROMPT_LEN + tokens / 2)
    t_tok = m["macs"] * T_PER_MAC + m["rows"] * T_PER_ROW
    t_prompt = (m["prompt_macs"] * T_PER_MAC + m["prompt_rows"] * T_PER_ROW) * dl.PROMPT_LEN
    d = c["d"]
    feasible = []
    if not c.get("gru") and (d > 32 or c.get("ffn", 0) > 64):
        feasible.append("needs >64 bytes of HRAM input or a slower WRAM kernel")
    if not c.get("gru") and dl.CTX * d * 2 * c.get("layers", 1) > 4096:
        feasible.append("K/V cache alone exceeds half of WRAM")
    if c.get("gru"):
        feasible.append("engine not implemented; no reference or kernels")
    return {"s_per_token": t_tok / CLOCK, "first_token_s": (t_prompt + t_tok) / CLOCK, "s_per_response": (t_prompt + t_tok * tokens) / CLOCK,
            "macs_per_token": m["macs"], "blockers": feasible}


def nll(model, x, y, quant, bs=1024) -> float:
    total, count = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(x), bs):
            logits = model(x[i:i + bs], quant)
            mask = y[i:i + bs] >= 0
            total += F.cross_entropy(logits[mask], y[i:i + bs][mask], reduction="sum").item()
            count += mask.sum().item()
    return total / count


def generate(model, prompts: list[list[int]], quant: bool, rnd: np.random.Generator, margin: float = 2.2, penalty: float = 2.0) -> list[list[int]]:
    """Batched float rendition of the ROM's sampling rule, for comparing candidates only."""
    results = []
    with torch.no_grad():
        for i in range(0, len(prompts), 256):
            x = torch.tensor(prompts[i:i + 256])
            done = [[] for _ in range(len(x))]
            alive = np.ones(len(x), dtype=bool)
            for step in range(dl.MAX_RESPONSE):
                logits = model(x, quant)[:, -1].numpy().copy()
                logits[:, :dl.FIRST_GEN] = -1e9
                if step == 0:
                    logits[:, :dl.FIRST_EMOTION] = -1e9
                    logits[:, dl.FIRST_EMOTION + len(dl.EMOTIONS):] = -1e9
                else:
                    logits[:, dl.FIRST_EMOTION:dl.FIRST_EMOTION + len(dl.EMOTIONS)] = -1e9
                nxt = []
                for j in range(len(x)):
                    row = logits[j]
                    for t in done[j]:
                        if t >= dl.FIRST_WORD and t not in dl.PUNCT_IDS:
                            row[t] -= penalty
                    top = row.max()
                    cand = np.where(row >= top - margin)[0][:12]
                    p = np.exp(row[cand] - top)
                    t = int(rnd.choice(cand, p=p / p.sum()))
                    nxt.append(t)
                    if alive[j]:
                        done[j].append(t)
                        if t == dl.EOS:
                            alive[j] = False
                x = torch.cat([x, torch.tensor(nxt)[:, None]], 1)
                if not alive.any():
                    break
            results += done
    return results


def score(model, quant: bool, seed: int, train_seqs: set[tuple[int, ...]]) -> dict:
    rnd = np.random.default_rng(seed)
    import random
    r = random.Random(seed)
    sits = []
    while len(sits) < 400:
        s = dl.random_situation(r)
        if dl.heldout_situation(s):
            sits.append(s)
    prompts = [dl.prompt_ids(s) for s in sits]
    out = generate(model, prompts, quant, rnd)
    an = [dl.analyze(t) for t in out]
    filled = {tuple(t) for t in out}
    return {"valid": sum(a["valid"] for a in an) / len(an), "closed": sum(a["closed"] for a in an) / len(an), "mean_tokens": float(np.mean([len(t) for t in out])),
            "unique": len(filled) / len(out), "novel_of_valid": sum(1 for a, t in zip(an, out) if a["valid"] and tuple(t) not in train_seqs) / max(1, sum(a["valid"] for a in an)),
            "fit_screen": sum(a["lines"] <= dl.MAX_LINES for a in an) / len(an), "samples": [dl.render(t) for t in out[:6]]}


def run(name: str, n_train: int, float_steps: int, qat_steps: int, seed: int = 1234) -> dict:
    c = CANDIDATES[name]
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    rng = np.random.default_rng(seed)
    split = dl.make_split(n_train, 3000, seed)
    arrays = {k: tuple(map(torch.from_numpy, dl.to_arrays(v))) for k, v in split.items()}
    (xtr, ytr), (xva, yva), (xte, yte) = arrays["train"], arrays["val"], arrays["test"]
    if c.get("gru"):
        model, qat_steps, quantized = GruLm(len(dl.VOCAB), c["d"], c["k"]), 0, False
    else:
        model, quantized = TinyTransformer(Config(vocab=len(dl.VOCAB), ctx=dl.CTX, heads=2, **c)), True
    untrained_nll = nll(model, xva, yva, False)
    total = float_steps + qat_steps
    opt = torch.optim.AdamW(model.parameters(), lr=0.004 if not c.get("gru") else 0.003, weight_decay=0.001)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.02 + 0.98 * 0.5 * (1 + math.cos(math.pi * s / total)))
    t0 = time.time()
    best, best_state = float("inf"), None
    for step in range(total):
        quant = quantized and step >= float_steps
        idx = rng.integers(0, len(xtr), 256)
        logits = model(xtr[idx], quant)
        mask = ytr[idx] >= 0
        loss = F.cross_entropy(logits[mask], ytr[idx][mask])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if (step + 1) % 2000 == 0 or step + 1 == total:
            v = nll(model, xva, yva, quant)
            print(f"{name} {step + 1}/{total} q={int(quant)} train {loss.item():.3f} val {v:.3f} t={time.time() - t0:.0f}s", flush=True)
            if v < best and (quant or not quantized):
                best, best_state = v, {k: p.clone() for k, p in model.state_dict().items()}
    model.load_state_dict(best_state)
    train_set = {tuple(q[dl.PROMPT_LEN:]) for q in split["train"]}
    q = score(model, quantized, seed, train_set)
    rep = {"name": name, "config": c, "params": model.num_params(), "vocab": len(dl.VOCAB), "untrained_val_nll": untrained_nll, "uniform_nll": math.log(len(dl.VOCAB)),
           "val_nll": best, "test_nll": nll(model, xte, yte, quantized), "generation": q, "train_seconds": time.time() - t0,
           "projection": projected(c, q["mean_tokens"]), "precision": "8-bit QAT" if quantized else "float32"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(rep, indent=1))
    torch.save({"state": model.state_dict(), "model": c}, OUT / f"{name}.pt")
    print(json.dumps({k: rep[k] for k in ("name", "params", "val_nll", "test_nll")} | {"valid": q["valid"], "novel": q["novel_of_valid"], "unique": q["unique"], "s_tok": rep["projection"]["s_per_token"], "s_resp": rep["projection"]["s_per_response"]}), flush=True)
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--n-train", type=int, default=100000)
    ap.add_argument("--float-steps", type=int, default=16000)
    ap.add_argument("--qat-steps", type=int, default=10000)
    a = ap.parse_args()
    if a.name:
        run(a.name, a.n_train, a.float_steps, a.qat_steps)
        return
    pending = [n for n in CANDIDATES if not (OUT / f"{n}.json").exists()]
    running: list[subprocess.Popen] = []
    OUT.mkdir(parents=True, exist_ok=True)
    while pending or running:
        running = [p for p in running if p.poll() is None]
        while pending and len(running) < a.jobs:
            n = pending.pop(0)
            log = open(OUT / f"{n}.log", "w")
            running.append(subprocess.Popen([sys.executable, __file__, n, "--n-train", str(a.n_train), "--float-steps", str(a.float_steps), "--qat-steps", str(a.qat_steps)], stdout=log, stderr=subprocess.STDOUT))
        time.sleep(5)
    print("STUDY DONE")


if __name__ == "__main__":
    main()
