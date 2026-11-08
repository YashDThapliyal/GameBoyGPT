#!/usr/bin/env python3
"""What the integer reference generates for the browser test's conversation. The browser must match it exactly."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from reference import conversation as cv, fixed_point as fp
from training import dialogue as dl

PLAN = [{"action": 1, "seed": 0x2345}, {"action": 1, "seed": 0x3456}, {"action": 2, "seed": 0x4567}]


def main() -> None:
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    s = cv.State()
    out = []
    for step in PLAN:
        before, s = s, cv.apply_turn(s, cv.Parsed(cv.ACTION_INTENT[step["action"]], "NONE"))
        prompt = dl.prompt_ids(cv.situation(before, s))
        out.append({**step, "tokens": prompt + fp.generate(m, prompt, greedy=False, rng=step["seed"])["generated"]})
    (ROOT / "tests" / "web" / "expected.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
