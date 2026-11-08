#!/usr/bin/env python3
"""Searches sampler seeds for the demo: short responses where the second visibly remembers the first.
The search runs on the integer reference. The chosen seeds are then replayed by the real ROM, which must produce those tokens."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from reference import conversation as cv, fixed_point as fp
from training import dialogue as dl


def main() -> None:
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    s0 = cv.State()
    s1 = cv.apply_turn(s0, cv.Parsed("INSULT", "NONE"))
    s2 = cv.apply_turn(s1, cv.Parsed("INSULT", "NONE"))
    p1, p2 = dl.prompt_ids(cv.situation(s0, s1)), dl.prompt_ids(cv.situation(s1, s2))
    slot = {"<NI>": "2"}
    best1, best2 = [], []
    for seed in range(1, 6000):
        a = fp.generate(m, p1, greedy=False, rng=seed)["generated"]
        an = dl.analyze(a)
        if an["valid"] and 6 <= len(a) <= 11 and an["lines"] <= 3 and an["emotion"] in ("ANGRY", "SMUG"):
            best1.append((len(a), seed, dl.render(a)))
        b = fp.generate(m, p2, greedy=False, rng=seed)["generated"]
        bn = dl.analyze(b)
        if bn["valid"] and dl.STOI["<NI>"] in b and len(b) <= 13 and bn["lines"] <= 4 and bn["emotion"] == "ANGRY":
            best2.append((len(b), seed, dl.render(b, slot)))
    best1.sort()
    best2.sort()
    print("first:", *best1[:16], sep="\n")
    print("second:", *best2[:16], sep="\n")
    if len(sys.argv) >= 3:
        (ROOT / "tools" / "demo_seeds.json").write_text(json.dumps({"first": int(sys.argv[1]), "second": int(sys.argv[2])}))


if __name__ == "__main__":
    main()
