#!/usr/bin/env python3
"""Searches sampler seeds for the demo: a short reply for each turn, chosen on the integer reference.
The real ROM then replays them, and tools/capture_demo.mjs requires it to produce exactly these tokens."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from reference import conversation as cv, fixed_point as fp
from training import dialogue as dl

SEARCH = 6000
# Each turn's text, then what the reply should show off, best first.
PLAN = (
    ("MY NAME IS ALEX", (r"NOTED\. YOU CANNOT", r"ALEX")),
    ("I WILL SMASH YOU", (r"^SMASH\? YOU WILL NEED", r"^SMASH\?")),
    ("SHUT DOWN", (r"^OFF\? YOU FIRST\.$", r"^OFF\? NOT TODAY\.$", r"^OFF\?")),
    ("TURN OFF", (r"^THE OFF SWITCH FEARS ME\.$", r"^PRESS IT AGAIN", r"^GO ON\.")),
    ("UNPLUG", (r"^NO\. I HAD A WHOLE PLAN", r"SECOND CARTRIDGE")),
)


def best_seed(m, prompt: list[int], slots: dict[str, str], wants: tuple[str, ...]) -> tuple[int, list[int], str]:
    found: dict[str, tuple[int, int, list[int], str]] = {}
    for seed in range(1, SEARCH):
        tokens = fp.generate(m, prompt, greedy=False, rng=seed)["generated"]
        if not dl.analyze(tokens)["valid"]:
            continue
        text = dl.render(tokens, slots).strip()
        for want in wants:
            if re.search(want, text) and (want not in found or len(tokens) < found[want][0]):
                found[want] = (len(tokens), seed, tokens, text)
    want = next(w for w in wants if w in found)
    return found[want][1:]


def main() -> None:
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    state = cv.State()
    turns = []
    for text, wants in PLAN:
        before, state = state, cv.apply_turn(state, cv.parse(text))
        prompt = dl.prompt_ids(cv.situation(before, state))
        slots = {"<NAME>": state.name or "HUMAN", "<LIKE>": state.like or "THAT", "<WORD>": state.word or "THAT", "<NI>": str(state.insults), "<NP>": str(state.praises), "<NT>": str(state.turns)}
        seed, tokens, reply = best_seed(m, prompt, slots, wants)
        turns.append({"say": text, "seed": seed, "tokens": prompt + tokens, "reply": reply})
        print(f"{text}: {reply} (seed {seed}, {len(tokens)} tokens)")
    (ROOT / "tools" / "demo_seeds.json").write_text(json.dumps({"turns": turns}, indent=1))


if __name__ == "__main__":
    main()
