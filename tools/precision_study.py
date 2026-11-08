#!/usr/bin/env python3
"""V6 research: weight precision sweep on the integer reference, with no retraining.

Rounds every w_* weight to n significant bits (values stay on the same int8 grid). Quality is measured by
strict validity and token disagreement. Packed ROM size is an arithmetic estimate; no ROM is built here, and
the shipping engine stores whole bytes, so these variants would not run faster on the same kernels.
"""
from __future__ import annotations
import dataclasses, json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from export_weights import from_blob
from reference import fixed_point as fp
from training import dataset as ds
WEIGHT_FIELDS = ("w_q", "w_k", "w_v", "w_o", "w_f1", "w_f2", "w_out")


def reduce_bits(tensor, bits):
    step = 1 << (8 - bits)
    clamp = lambda v: max(-127, min(127, v))
    return tuple(tuple(clamp(((v + step // 2) // step) * step) for v in row) for row in tensor)


def main():
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    sits = [s for s in ds.situations() if ds.sentences(*s)]
    test = [s for s in sits if s in ds.TEST_FAMILIES]
    base = {s: fp.generate(m, ds.prompt_ids(*s))["generated"] for s in sits}
    weights = sum(len(getattr(m, f)) * len(getattr(m, f)[0]) for f in WEIGHT_FIELDS)
    embed = sum(len(getattr(m, f)) * len(getattr(m, f)[0]) for f in ("tok", "pos"))
    rows = []
    for bits in (8, 7, 6, 5, 4, 3):
        m2 = dataclasses.replace(m, **{f: reduce_bits(getattr(m, f), bits) for f in WEIGHT_FIELDS})
        ok = same = capped = heldout_ok = 0
        for s in sits:
            r = fp.generate(m2, ds.prompt_ids(*s))
            ids = [t for t in r["generated"] if t != ds.EOS]
            valid = ds.check_sentence(s, ids)["strict"]
            ok += valid
            heldout_ok += valid and s in test
            same += r["generated"] == base[s]
            capped += r["capped"]
        rows.append({"weight_bits": bits, "strict_valid": ok / len(sits), "heldout_test_strict_valid": heldout_ok / len(test), "token_agreement": same / len(sits),
                     "cap_rate": capped / len(sits), "estimated_packed_rom_bytes": embed + (weights * bits + 7) // 8})
        print(rows[-1], flush=True)
    (ROOT / "reports" / "precision_study.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
