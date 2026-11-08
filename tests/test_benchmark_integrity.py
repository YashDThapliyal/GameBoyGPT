"""The benchmark report must be internally consistent. Fails on nonsense, never repairs it."""
import csv
import hashlib
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]
from benchmark import CSV_FIELDS, HZ
from workloads import WORKLOADS

CSV_PATH = ROOT / "reports" / "benchmark.csv"
pytestmark = pytest.mark.skipif(not CSV_PATH.exists(), reason="run make benchmark first")


def rows():
    return list(csv.DictReader(open(CSV_PATH)))


def test_schema_exact():
    assert list(rows()[0].keys()) == CSV_FIELDS


def test_values_are_physically_possible():
    for r in rows():
        assert len(r["rom_sha256"]) == 64 and len(r["model_sha256"]) == 64
        for f in ("first_token_tcycles", "total_tcycles", "output_tokens", "wram_bytes", "rom_bytes"):
            assert int(r[f]) > 0, f
        assert int(r["wram_bytes"]) <= 0x1E00, "stack and mailbox own the last 512 bytes"
        assert int(r["rom_bytes"]) % 32768 == 0
        assert abs(int(r["total_tcycles"]) / HZ - float(r["seconds_per_response"])) < 1e-3
        assert r["emulator"] == "PyBoy" and "cgb=False" in r["hardware_mode"]
        assert 0 < int(r["stack_peak_bytes"]) < 0xF0


def test_every_speed_variant_is_output_identical_to_the_baseline_and_the_reference():
    for r in rows():
        assert r["token_match_baseline"] in ("SELF", "True"), (r["version"], r["workload"])
        assert r["matches_reference"] == "True", (r["version"], r["workload"])


def test_every_variant_ran_every_workload_on_one_model():
    rs = rows()
    assert len({r["model_sha256"] for r in rs}) == 1
    for v in {r["version"] for r in rs}:
        assert {r["workload"] for r in rs if r["version"] == v} == set(WORKLOADS)


def test_rom_hashes_in_report_match_built_roms():
    for r in rows():
        for name, field in (("gameboygpt.gb", "rom_sha256"), ("test.gb", "test_rom_sha256")):
            rom = ROOT / "build" / r["version"] / name
            if rom.exists():
                assert hashlib.sha256(rom.read_bytes()).hexdigest() == r[field], (r["version"], name)
