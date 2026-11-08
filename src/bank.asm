; bank.asm - MBC5 ROM banking. Always resident in bank 0. ISRs never touch the switchable window.
INCLUDE "constants.inc"

SECTION "bank_vars", HRAM
hCurBank:: ds 1

SECTION "bank_code", ROM0
; BankSwitch: a = target ROM bank (1-255). Preserves all but flags. Counts switches for benchmarks.
; Writing the register when already selected is skipped only by callers that want that: the
; vanilla baseline deliberately keeps this plain, unconditional behaviour.
BankSwitch::
IF DEF(BANK_SKIP)
    push hl
    ld hl, hCurBank
    cp [hl]
    pop hl
    ret z
ENDC
    ldh [hCurBank], a
    ld [MBC5_ROMB0], a
    push hl
    ld hl, wMB_BankSwitches
    inc [hl]
    jr nz, .done
    inc hl
    inc [hl]
    jr nz, .done
    inc hl
    inc [hl]
.done:
    pop hl
    ret
