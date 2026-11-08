"""The benchmark report must be internally consistent. Fails on nonsense, never repairs it."""
import csv
import json
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from benchmark import CSV_FIELDS, HZ, WORKLOADS

CSV_PATH = ROOT / "reports" / "benchmark.csv"
pytestmark = pytest.mark.skipif(not CSV_PATH.exists(), reason="run make benchmark first")


def rows():
    return list(csv.DictReader(open(CSV_PATH)))


def test_schema_exact():
    assert list(rows()[0].keys()) == CSV_FIELDS


def test_values_are_physically_possible():
    for r in rows():
        assert len(r["rom_sha256"]) == 64 and len(r["model_sha256"]) == 64
        for f in ("first_token_tcycles", "decode_tcycles_total", "decode_tcycles_median", "decode_tcycles_p95", "output_tokens", "peak_wram_bytes", "rom_bytes"):
            assert int(r[f]) > 0, f
        assert int(r["peak_wram_bytes"]) <= 8192
        assert int(r["peak_sram_bytes"]) == 0
        assert int(r["rom_bytes"]) % 32768 == 0
        secs = int(r["decode_tcycles_total"]) / HZ
        assert abs(secs - float(r["seconds_per_event"])) < 1e-3
        assert r["emulator"] == "PyBoy" and "cgb=False" in r["hardware_mode"]


def test_every_speed_variant_is_output_identical_to_the_baseline():
    for r in rows():
        assert r["token_match_baseline"] in ("SELF", "True"), (r["version"], r["workload"])


def test_three_rounds_per_workload_per_variant_and_same_model():
    rs = rows()
    assert len({r["model_sha256"] for r in rs}) == 1
    for v in {r["version"] for r in rs}:
        for w in WORKLOADS:
            assert sorted(r["round"] for r in rs if r["version"] == v and r["workload"] == w) == ["0", "1", "2"]


def test_rom_hashes_in_report_match_built_roms():
    import hashlib
    for r in rows():
        rom = ROOT / "build" / r["version"] / "gameboygpt.gb"
        if rom.exists():
            assert hashlib.sha256(rom.read_bytes()).hexdigest() == r["rom_sha256"], r["version"]
