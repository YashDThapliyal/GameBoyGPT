"""Phase 0 gate: a minimal DMG ROM boots, and PyBoy's cycle counter agrees with a hand-counted sequence."""
import re, subprocess
from pathlib import Path
import pytest
from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "smoke"
# nop4 ld8 ld12 ld8 ld8 add4 push16 pop12 call24 ret16 (Pan Docs instruction timings)
HAND_COUNTED_TCYCLES = 4 + 8 + 12 + 8 + 8 + 4 + 16 + 12 + 24 + 16


@pytest.fixture(scope="module")
def rom():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["rgbasm", "-E", "-o", OUT / "smoke.o", ROOT / "tests" / "smoke.asm"])
    subprocess.check_call(["rgblink", "-o", OUT / "smoke.gb", "-n", OUT / "smoke.sym", OUT / "smoke.o"])
    subprocess.check_call(["rgbfix", "-v", "-p", "0", "-t", "SMOKE", OUT / "smoke.gb"])
    return OUT / "smoke.gb"


def test_boot_and_cycle_calibration(rom):
    syms = {m[1]: int(m[0], 16) for m in re.findall(r"00:([0-9a-f]{4}) (\w+)", (OUT / "smoke.sym").read_text())}
    gb = PyBoy(str(rom), window="null", cgb=False, sound_emulated=False)
    seen = {}
    gb.hook_register(0, syms["Mark0"], lambda n: seen.__setitem__(n, gb._cycles()), "m0")
    gb.hook_register(0, syms["Mark1"], lambda n: seen.__setitem__(n, gb._cycles()), "m1")
    gb.tick(120, False)
    gb.screen.image.save(OUT / "smoke.png")
    assert gb.memory[0xC000] == 1
    assert seen["m1"] - seen["m0"] == HAND_COUNTED_TCYCLES
    gb.stop(save=False)
