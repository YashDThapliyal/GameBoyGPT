#!/usr/bin/env python3
"""Quality metrics computed on the INTEGER reference, plus conditioning ablations."""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from training import dataset as ds
from reference import fixed_point as fp
from export_weights import quantize, from_blob


def score(m, sits, greedy=True, samples=1, seed=7) -> dict:
    keys = ("strict", "event", "closing")
    tot = dict.fromkeys(keys, 0)
    capped, n, uniq, examples, bad = 0, 0, set(), [], []
    rng = seed
    for s in sits:
        for _ in range(samples):
            r = fp.generate(m, ds.prompt_ids(*s), greedy=greedy, rng=rng)
            rng = r["rng"]
            ids = [t for t in r["generated"] if t != ds.EOS]
            c = ds.check_sentence(s, ids)
            for k in keys:
                tot[k] += c[k]
            capped += r["capped"]
            n += 1
            uniq.add(tuple(ids))
            text = " ".join(ds.VOCAB[i] for i in ids)
            if len(examples) < 6:
                examples.append((s[0], s[1], s[2], text))
            if not c["strict"] and len(bad) < 8:
                bad.append((s[0], s[1], s[2], text))
    return {**{k: tot[k] / n for k in keys}, "capped": capped / n, "n": n, "unique": len(uniq), "examples": examples, "failures": bad}


def conditioning_ablation(m, sits) -> dict:
    """Does the text change when only the event, or only the carried items, change?"""
    rnd = random.Random(3)
    beats = sorted({s[0] for s in sits})
    beat_changed = flag_changed = flag_pairs = 0
    for s in sits:
        base = fp.generate(m, ds.prompt_ids(*s))["generated"]
        other = rnd.choice([b for b in beats if b != s[0]])
        beat_changed += base != fp.generate(m, ds.prompt_ids(other, s[1], s[2]))["generated"]
        same_beat = [x for x in sits if x[0] == s[0] and x[2] == s[2] and x[1] != s[1]]
        if same_beat:
            alt = rnd.choice(same_beat)
            flag_pairs += 1
            flag_changed += base != fp.generate(m, ds.prompt_ids(*alt))["generated"]
    return {"beat_changed_rate": beat_changed / len(sits), "flags_changed_rate": flag_changed / max(flag_pairs, 1), "n": len(sits), "flag_pairs": flag_pairs}


def novelty(m, sits, train_rows) -> dict:
    train_seqs = {tuple(r[ds.PROMPT_LEN:-1]) for r in train_rows}
    train_full = {tuple(r[:-1]) for r in train_rows}
    outs = [(s, tuple(t for t in fp.generate(m, ds.prompt_ids(*s))["generated"] if t != ds.EOS)) for s in sits]
    return {"text_seen_in_train_for_any_prompt": sum(o in train_seqs for _, o in outs) / len(outs),
            "exact_prompt_plus_text_in_train": sum((*ds.prompt_ids(*s), *o) in train_full for s, o in outs) / len(outs)}


def untrained_baseline(sits) -> dict:
    """Same architecture and integer engine with random weights: the floor trained quality is measured against."""
    import tempfile, torch
    from training.model import Config, TinyTransformer
    torch.manual_seed(1234)
    model = TinyTransformer(Config(vocab=len(ds.VOCAB), ctx=ds.CTX))
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "untrained.pt"
        torch.save({"state": model.state_dict(), "model": model.c.as_dict()}, p)
        return score(quantize(p), sits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=str(ROOT / "checkpoints" / "release.pt"))
    ap.add_argument("--blob")
    ap.add_argument("--out")
    a = ap.parse_args()
    m = from_blob(Path(a.blob).read_bytes()) if a.blob else quantize(Path(a.ckpt))
    sits = ds.situations()
    test = sorted(ds.TEST_FAMILIES)
    heldout = sorted(ds.VAL_FAMILIES | ds.TEST_FAMILIES)
    report = {
        "all_greedy": score(m, sits), "test_heldout_greedy": score(m, test), "heldout_all_greedy": score(m, heldout),
        "all_sampled": score(m, sits, greedy=False, samples=3), "test_heldout_sampled": score(m, test, greedy=False, samples=30),
        "untrained_all_greedy": untrained_baseline(sits),
        "conditioning": conditioning_ablation(m, sits),
        "novelty_test": novelty(m, test, ds.make_split(60000, 1, 1234)["train"]),
    }
    print(json.dumps(report, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
