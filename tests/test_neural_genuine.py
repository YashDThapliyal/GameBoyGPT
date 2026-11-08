"""Is the text really coming from the network in the ROM? Attack the ROM and see."""
import re
import shutil
import pytest
from chat_harness import *
from run_emulator import load_symbols
from reference import fixed_point as fp
from training import corpus as cp


def rom_offset(bank: int, addr: int) -> int:
    return addr if bank == 0 else bank * 0x4000 + (addr - 0x4000)


def fix_checksums(data: bytearray) -> None:
    x = 0
    for b in data[0x134:0x14D]:
        x = (x - b - 1) & 255
    data[0x14D] = x
    s = (sum(data) - data[0x14E] - data[0x14F]) & 0xFFFF
    data[0x14E], data[0x14F] = s >> 8, s & 255


def play(rom, seed=0x1111):
    gb = boot(rom=rom, seed=seed)
    action(gb, 1)
    out = generated(gb), screen_text(gb)
    gb.stop()
    return out


def test_patching_output_weights_changes_the_words(tmp_path):
    syms = load_symbols(ROM.with_suffix(".sym"))
    bank, addr = syms["DataOut"]
    data = bytearray(ROM.read_bytes())
    start = rom_offset(bank, addr)
    k = len(MODEL.w_b)
    for i in range(start + MODEL.eos * k, start + MODEL.vocab * k):
        data[i] = (data[i] * 7 + 13) & 255 or 1
    fix_checksums(data)
    patched = tmp_path / "patched.gb"
    patched.write_bytes(data)
    shutil.copy(ROM.with_suffix(".sym"), patched.with_suffix(".sym"))
    original, text = play(ROM)
    damaged, text2 = play(patched)
    assert original != damaged and text != text2


def test_patching_attention_weights_changes_the_words(tmp_path):
    syms = load_symbols(ROM.with_suffix(".sym"))
    bank, addr = syms["DataK"]
    data = bytearray(ROM.read_bytes())
    start = rom_offset(bank, addr)
    for i in range(start, start + MODEL.d * MODEL.d):
        data[i] = 255 - data[i] or 1
    fix_checksums(data)
    patched = tmp_path / "patched.gb"
    patched.write_bytes(data)
    shutil.copy(ROM.with_suffix(".sym"), patched.with_suffix(".sym"))
    assert play(ROM)[0] != play(patched)[0]


def test_rom_holds_no_authored_sentences_only_a_vocabulary():
    """Fixed interface lines exist, are listed in src/ui.asm and are marked SYSTEM on screen. Corpus sentences must not exist."""
    rom = ROM.read_bytes().decode("latin-1")
    for fixed in re.findall(r'db "([^"]+)", 0', (ROOT / "src" / "ui.asm").read_text()):
        rom = rom.replace(fixed, "")
    for sentence in dl.EXPANDED:
        words = sentence.upper().replace(" .", ".").replace(" ,", ",").replace(" !", "!").replace(" ?", "?")
        if len(sentence.split()) < 4:
            continue  # a short phrase token can legitimately equal a very short line
        assert words not in rom, sentence
        assert sentence.upper() not in rom, sentence


def test_longest_vocabulary_token_is_a_short_phrase():
    assert max(len(w) for w in dl.VOCAB[dl.FIRST_WORD:]) <= 16


def test_real_weights_are_in_the_rom():
    syms = load_symbols(ROM.with_suffix(".sym"))
    data = ROM.read_bytes()
    bank, addr = syms["DataTok"]
    start = rom_offset(bank, addr)
    assert list(data[start:start + 32]) == [v & 255 for v in MODEL.tok[0]]
    bank, addr = syms["DataOut"]
    start = rom_offset(bank, addr)
    k = len(MODEL.w_b)
    assert list(data[start + 800 % MODEL.vocab * k:start + 800 % MODEL.vocab * k + k]) == [(v + 128) & 255 for v in MODEL.w_out[800 % MODEL.vocab]]


def test_token_ids_are_inspectable_during_generation():
    gb = boot(greedy=True)
    select(gb, 1)
    gb.press("a")
    gb.wait_for(lambda: gb.read1("wMB_State") == ST_STREAMING, 2000)
    assert gb.read1("wSeqLen") == dl.PROMPT_LEN + 1
    wait_response(gb)
    assert generated(gb)[-1] == dl.EOS
    gb.stop()
