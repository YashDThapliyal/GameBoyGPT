#!/usr/bin/env python3
"""Deterministic training: float warmup then quantization-aware fine-tuning. Bounded and CPU-only."""
from __future__ import annotations
import argparse, csv, json, math, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import torch
import torch.nn.functional as F
import yaml
from training import dataset as ds
from training.model import Config, TinyTransformer

ROOT = Path(__file__).resolve().parent.parent


def nll(model, x, y, quant, bs=1024):
    total, count = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(x), bs):
            logits = model(x[i:i + bs], quant)
            mask = y[i:i + bs] >= 0
            total += F.cross_entropy(logits[mask], y[i:i + bs][mask], reduction="sum").item()
            count += mask.sum().item()
    return total / count


def run(cfg: dict) -> dict:
    torch.manual_seed(cfg["seed"])
    torch.set_num_threads(cfg.get("threads", 4))
    rng = np.random.default_rng(cfg["seed"])
    split = ds.make_split(cfg["n_train"], cfg["n_eval"], cfg["seed"])
    arrays = {k: tuple(map(torch.from_numpy, ds.to_arrays(v))) for k, v in split.items()}
    (xtr, ytr), (xva, yva), (xte, yte) = arrays["train"], arrays["val"], arrays["test"]
    c = Config(vocab=len(ds.VOCAB), **cfg["model"])
    model = TinyTransformer(c)
    untrained = {"val_nll": nll(model, xva, yva, False), "uniform_nll": math.log(len(ds.VOCAB))}
    float_steps, qat_steps, bs = cfg["float_steps"], cfg["qat_steps"], cfg["batch"]
    total = float_steps + qat_steps
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.02 + 0.98 * 0.5 * (1 + math.cos(math.pi * s / total)))
    curve, best, best_state, t0 = [], float("inf"), None, time.time()
    for step in range(total):
        quant = step >= float_steps
        idx = rng.integers(0, len(xtr), bs)
        logits = model(xtr[idx], quant)
        mask = ytr[idx] >= 0
        loss = F.cross_entropy(logits[mask], ytr[idx][mask])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if (step + 1) % cfg["eval_every"] == 0 or step + 1 == total:
            v = nll(model, xva, yva, quant)
            curve.append({"step": step + 1, "quant": int(quant), "train_nll": loss.item(), "val_nll": v})
            print(f"step {step + 1} quant={int(quant)} train {loss.item():.4f} val {v:.4f} t={time.time() - t0:.0f}s", flush=True)
            if quant and v < best:
                best, best_state = v, {k: p.clone() for k, p in model.state_dict().items()}
    model.load_state_dict(best_state)
    report = {"config": cfg, "model": c.as_dict(), "params": model.num_params(), "untrained": untrained,
              "best_val_nll_quant": best, "test_nll_quant": nll(model, xte, yte, True),
              "test_nll_float": nll(model, xte, yte, False), "train_seconds": time.time() - t0}
    out = ROOT / cfg["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "model": c.as_dict(), "report": report, "vocab": ds.VOCAB}, out)
    with open(out.with_suffix(".curve.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, curve[0].keys())
        w.writeheader()
        w.writerows(curve)
    out.with_suffix(".report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("params", "best_val_nll_quant", "test_nll_quant", "test_nll_float", "untrained")}))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "release.yaml"))
    a = ap.parse_args()
    run(yaml.safe_load(open(a.config)))
