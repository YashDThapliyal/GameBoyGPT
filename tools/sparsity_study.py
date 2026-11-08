#!/usr/bin/env python3
"""How often is the feed-forward activation exactly zero? Motivation for the zero-column skip (V5Z).

Runs greedy generation on the integer reference for every reachable situation and counts zeros in `f`
at every generated position. Writes reports/sparsity.json.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from reference import fixed_point as fp
from training import dataset as ds


def main():
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    zero = total = steps = 0
    sits = [s for s in ds.situations() if ds.sentences(*s)]
    for s in sits:
        tokens = fp.generate(m, ds.prompt_ids(*s))["tokens"]
        for n in range(ds.PROMPT_LEN, len(tokens)):
            f = fp.step(m, tokens[:n])[1]["f"]
            zero += sum(v == 0 for v in f)
            total += len(f)
            steps += 1
    res = {"situations": len(sits), "forward_steps": steps, "activations": total, "zero_share": zero / total}
    print(res)
    (ROOT / "reports" / "sparsity.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
