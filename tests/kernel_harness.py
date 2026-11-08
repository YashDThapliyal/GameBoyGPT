"""Drive the test ROM's command loop: write inputs, run one kernel, read outputs and exact T-cycles."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from run_emulator import GB

CMD_MUL, CMD_DOT, CMD_REQUANT, CMD_NORM, CMD_ATTEND, CMD_MATVEC, CMD_STEP, CMD_GENERATE, CMD_SATADD, CMD_RELU, CMD_WEIGHTS, CMD_SAMPLE = range(1, 13)


def s8(b: int) -> int:
    return b - 256 if b > 127 else b


class KernelRig:
    def __init__(self, variant: str = "V0"):
        self.gb = GB(ROOT / "build" / variant / "test.gb")
        self.gb.wait_for(lambda: self.gb.read1("wMB_State") == 1, 2000)

    def run(self, cmd: int, args=(), max_frames: int = 20000) -> int:
        """Execute a command; returns elapsed T-cycles between dispatch entry and exit."""
        gb = self.gb
        gb.write("wMB_Args", list(args))
        gb.write("wMB_Cmd", [cmd])
        marks = {}
        seq = (gb.read1("wMB_CmdSeq") + 1) & 0xFF
        bank, addr = gb.syms["Dispatch"]
        ebank, eaddr = gb.syms["TestDispatchEnd"]
        gb.pyboy.hook_register(bank, addr, lambda _: marks.setdefault("start", gb.cycles()), None)
        gb.pyboy.hook_register(ebank, eaddr, lambda _: marks.setdefault("end", gb.cycles()), None)
        gb.write("wMB_CmdSeq", [seq])
        gb.wait_for(lambda: gb.read1("wMB_CmdDone") == seq, max_frames)
        gb.pyboy.hook_deregister(bank, addr)
        gb.pyboy.hook_deregister(ebank, eaddr)
        return marks["end"] - marks["start"]

    def stop(self):
        self.gb.stop()
