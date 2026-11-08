#!/usr/bin/env python3
"""Build a variant's game ROM and test ROM. Variants are configs/V*.yaml: defines plus ROM layout.

    build/<variant>/gameboygpt.gb, test.gb (+ .sym, .map)
"""
from __future__ import annotations
import argparse, hashlib, subprocess, sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIX = ["-v", "-p", "0xFF", "-m", "MBC5+RAM+BATTERY", "-r", "2", "-t", "SYSOVERRIDE", "-n", "1", "-k", "HB", "-l", "0x33"]


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"{' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")


def selftest_source(gen):
    """Expected tokens come from the integer reference at build time, for the benchmark workloads."""
    sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
    from workloads import WORKLOADS
    from export_weights import from_blob
    from reference import fixed_point as fp
    from training import dialogue as ds
    m = from_blob((ROOT / "generated" / "model.bin").read_bytes())
    lines = ['SECTION "selftest_cases", ROM0', "SelfTestCases::"]
    for sit in WORKLOADS.values():
        t = fp.generate(m, ds.prompt_ids(sit))["tokens"]
        lines.append(f"    db {len(t)}\n    dw " + ",".join(map(str, t + [0] * (m.ctx - len(t)))))
    (gen / "selftest_cases.asm").write_text("\n".join(lines) + "\n")
    with open(gen / "model_constants.inc", "a") as f:
        f.write(f"DEF SELFTEST_CASES EQU {len(WORKLOADS)}\n")


def build_rom(name, cfg, test, selftest=False):
    out = ROOT / "build" / name
    gen = ROOT / "generated" / name
    obj = out / ("obj_selftest" if selftest else "obj_test" if test else "obj")
    obj.mkdir(parents=True, exist_ok=True)
    layout = cfg.get("layout", "naive")
    cmd = [sys.executable, ROOT / "tools" / "rom_layout.py", "--layout", layout, "--outdir", gen]
    if cfg.get("biased"):
        cmd.append("--biased")
    if cfg.get("tables"):
        cmd += ["--tables", *cfg["tables"]]
    run(cmd)
    if selftest:
        selftest_source(gen)
    defs = []
    if selftest:
        defs += ["-D", "SELFTEST"]
    for d in cfg.get("defines", []):
        defs += ["-D", d]
    defs += ["-D", f'VARIANT_NAME="{cfg.get("display", name)}"']
    if test:
        defs += ["-D", "TEST_ROM"]
    sources = sorted(p for p in (ROOT / "src").glob("*.asm") if not p.name.startswith(".")) + [ROOT / "generated" / "assets.asm", gen / "weights.asm", gen / "luts.asm"]
    if selftest:
        sources.append(gen / "selftest_cases.asm")
    objs = []
    for s in sources:
        o = obj / (s.stem + ".o")
        run(["rgbasm", "-E", "-I", ROOT / "src" / "include", "-I", ROOT / "generated", "-I", gen, *defs, "-o", o, s])
        objs.append(o)
    rom = out / ("selftest.gb" if selftest else "test.gb" if test else "gameboygpt.gb")
    run(["rgblink", "-w", "-p", "0xFF", "-m", rom.with_suffix(".map"), "-n", rom.with_suffix(".sym"), "-o", rom, *objs])
    run(["rgbfix", *FIX, rom])
    return rom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variants", nargs="+")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    for v in a.variants:
        cfg = yaml.safe_load(open(ROOT / "configs" / f"{v}.yaml")) or {}
        for test in (False, True):
            rom = build_rom(v, cfg, test)
            print(rom.relative_to(ROOT), rom.stat().st_size, hashlib.sha256(rom.read_bytes()).hexdigest()[:16])
        if a.selftest:
            build_rom(v, cfg, False, True)


if __name__ == "__main__":
    main()
