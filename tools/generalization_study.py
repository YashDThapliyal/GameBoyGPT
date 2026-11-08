#!/usr/bin/env python3
"""Harder held-out test than the release split: train on 60% of situations, score on the unseen 40%.

Uses the release architecture and training recipe but is not the shipping checkpoint. Validity is measured
on the integer reference. Run: python tools/generalization_study.py
"""
from __future__ import annotations
import json, random, tempfile
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import yaml
from training import dataset as ds, train as tr
from training.evaluate import score
from export_weights import quantize

HOLDOUT_FRACTION = 0.4
SEED = 77


def main():
    sits = [s for s in ds.situations() if ds.sentences(*s)]
    rnd = random.Random(SEED)
    held = set(rnd.sample(sits, int(len(sits) * HOLDOUT_FRACTION)))
    ds.VAL_FAMILIES, ds.TEST_FAMILIES = set(list(held)[:len(held) // 4]), set(list(held)[len(held) // 4:])
    cfg = yaml.safe_load(open(ROOT / "configs" / "release.yaml"))
    cfg["out"] = "checkpoints/generalization.pt"
    cfg["eval_every"] = 5000
    report = tr.run(cfg)
    m = quantize(ROOT / cfg["out"])
    test = sorted(ds.TEST_FAMILIES)
    train = [s for s in sits if s not in held]
    res = {"holdout_fraction": HOLDOUT_FRACTION, "n_situations": len(sits), "n_test_situations": len(test), "n_val_situations": len(ds.VAL_FAMILIES),
           "test_nll_quant": report["test_nll_quant"], "train_situations_greedy": score(m, train), "test_situations_greedy": score(m, test), "test_situations_sampled": score(m, test, greedy=False, samples=3)}
    print(json.dumps({k: res[k] for k in res if "situations_" not in k}), {k: {a: b for a, b in res[k].items() if a != "examples"} for k in res if "situations_" in k})
    (ROOT / "reports" / "generalization.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
