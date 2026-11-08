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
from reference import game as g
from export_weights import quantize, from_blob


def score(m, sits, greedy=True, samples=1, seed=7) -> dict:
    keys = ("strict", "action", "room", "outcome")
    tot = dict.fromkeys(keys, 0)
    capped, n, uniq, examples = 0, 0, set(), []
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
            if len(examples) < 4:
                examples.append((ds.ROOM_TOK[s[0]], ds.INV_TOK[s[1]], ds.ACT_TOK[s[2]], ds.OUT_TOK[s[3]], " ".join(ds.VOCAB[i] for i in ids)))
    return {**{k: tot[k] / n for k in keys}, "capped": capped / n, "n": n, "unique": len(uniq), "examples": examples}


def action_ablation(m, sits) -> dict:
    """Do generated events change when ONLY the action token changes, and does shuffling it break validity?"""
    changed = total = shuffled_ok = 0
    rnd = random.Random(3)
    for s in sits:
        a = fp.generate(m, ds.prompt_ids(*s))["generated"]
        other = rnd.choice([x for x in range(4) if x != s[2]])
        b = fp.generate(m, ds.prompt_ids(s[0], s[1], other, s[3]))["generated"]
        changed += a != b
        total += 1
        shuffled_ok += ds.check_sentence(s, [t for t in b if t != ds.EOS])["action"]
    return {"changed_rate": changed / total, "wrong_action_token_scores_action_ok": shuffled_ok / total, "n": total}


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
    model = TinyTransformer(Config(vocab=len(ds.VOCAB)))
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
    sits = [s for s in ds.situations() if ds.sentences(*s)]
    heldout = [s for s in sits if s in ds.VAL_FAMILIES | ds.TEST_FAMILIES]
    test = [s for s in sits if s in ds.TEST_FAMILIES]
    train = [s for s in sits if s not in ds.VAL_FAMILIES | ds.TEST_FAMILIES]
    report = {
        "all_greedy": score(m, sits), "test_heldout_greedy": score(m, test), "heldout_all_greedy": score(m, heldout),
        "all_sampled": score(m, sits, greedy=False, samples=3), "test_heldout_sampled": score(m, test, greedy=False, samples=30),
        "untrained_all_greedy": untrained_baseline(sits),
        "action_ablation": action_ablation(m, sits),
        "novelty_test": novelty(m, test, ds.make_split(48000, 1, 1234)["train"]),
    }
    print(json.dumps(report, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
