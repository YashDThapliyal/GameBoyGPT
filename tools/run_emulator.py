#!/usr/bin/env python3
"""PyBoy harness: symbol lookup, mailbox access, button input, screenshots. DMG mode is forced (cgb=False)."""
from __future__ import annotations
import io
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import os
os.environ.setdefault("PYSDL2_DLL_PATH", "")
from pyboy import PyBoy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_BOOT_FRAMES = 2000


def load_symbols(sym_path: Path) -> dict[str, tuple[int, int]]:
    """Parse rgblink's .sym into name -> (bank, address)."""
    syms = {}
    for bank, addr, name in re.findall(r"^([0-9a-f]{2}):([0-9a-f]{4}) (\S+)", Path(sym_path).read_text(), re.M):
        syms[name] = (int(bank, 16), int(addr, 16))
    return syms


class GB:
    def __init__(self, rom: str | Path, sym: str | Path | None = None, ram_file=None):
        """ram_file: an open binary file with the cartridge RAM. "auto" lets PyBoy keep <rom>.ram beside the ROM, as a battery would.
        Without either, every run starts with a blank cartridge."""
        rom = Path(rom)
        self.rom = rom
        self.syms = load_symbols(Path(sym) if sym else rom.with_suffix(".sym"))
        ram = None if ram_file == "auto" else ram_file if ram_file is not None else io.BytesIO(bytes(0x2000))
        self.pyboy = PyBoy(str(rom), window="null", cgb=False, sound_emulated=False, log_level="ERROR", ram_file=ram)
        self.mem = self.pyboy.memory

    def addr(self, name: str) -> int:
        return self.syms[name][1]

    def read(self, name: str, n: int = 1, offset: int = 0) -> list[int]:
        a = self.addr(name) + offset
        return [self.mem[a + i] for i in range(n)]

    def read1(self, name: str) -> int:
        return self.mem[self.addr(name)]

    def write(self, name: str, data, offset: int = 0) -> None:
        a = self.addr(name) + offset
        for i, v in enumerate(data):
            self.mem[a + i] = int(v) & 0xFF

    def cycles(self) -> int:
        return self.pyboy._cycles()

    def tick(self, n: int = 1) -> None:
        self.pyboy.tick(n, False)

    def wait_for(self, predicate, max_frames: int = 200000, step: int = 1) -> int:
        """Advance until predicate() is true; raises on timeout so tests can never hang silently."""
        for f in range(0, max_frames, step):
            if predicate():
                return f
            self.pyboy.tick(step, False)
        raise TimeoutError(f"condition not met after {max_frames} frames; PC={self.pyboy.register_file.PC:04X}")

    def wait_state(self, state: int, max_frames: int = 200000) -> int:
        return self.wait_for(lambda: self.read1("wMB_State") == state, max_frames)

    def press(self, button: str, settle: int = 4) -> None:
        self.pyboy.button(button, 3)
        self.pyboy.tick(settle + 3, False)

    def screenshot(self, path: str | Path):
        self.pyboy.tick(1, True)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img = self.pyboy.screen.image.copy()
        img.save(path)
        return img

    def header_cgb_flag(self) -> int:
        return self.rom.read_bytes()[0x143]

    def stop(self, save: bool = False) -> None:
        """save=True writes cartridge RAM to <rom>.ram, as a battery would keep it."""
        self.pyboy.stop(save=save)
