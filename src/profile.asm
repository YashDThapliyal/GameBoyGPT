; profile.asm - zero-overhead markers for emulator cycle hooks, plus on-device frame timing for the stats screen.
INCLUDE "constants.inc"

SECTION "profile_vars", WRAM0
wEventStartFrames: ds 2
wLastEventFrames:: ds 2
wLastEventTokens:: ds 1
wTotalFallbacks::  ds 1
wEventBankStart:   ds 2
wLastEventBanks::  ds 2

SECTION "profile_code", ROM0
; Harness hooks fire on these labels. Each is a bare ret, so instrumentation does not depend on host code.
ProfileTokenStart::
    ret
ProfileTokenEnd::
    ret
ProfileStepKVDone::
    ret

; EventTimerStart / EventTimerStop: LCD-frame timing visible on real hardware.
EventTimerStart::
    ldh a, [hFrames]
    ld [wEventStartFrames], a
    ldh a, [hFrames + 1]
    ld [wEventStartFrames + 1], a
    ld a, [wMB_BankSwitches]
    ld [wEventBankStart], a
    ld a, [wMB_BankSwitches + 1]
    ld [wEventBankStart + 1], a
    ret

EventTimerStop::
    ld a, [wEventStartFrames]
    ld c, a
    ldh a, [hFrames]
    sub c
    ld [wLastEventFrames], a
    ld [wMB_EventFrames], a
    ld a, [wEventStartFrames + 1]
    ld c, a
    ldh a, [hFrames + 1]
    sbc c
    ld [wLastEventFrames + 1], a
    ld [wMB_EventFrames + 1], a
    ld a, [wEventBankStart]
    ld c, a
    ld a, [wMB_BankSwitches]
    sub c
    ld [wLastEventBanks], a
    ld a, [wEventBankStart + 1]
    ld c, a
    ld a, [wMB_BankSwitches + 1]
    sbc c
    ld [wLastEventBanks + 1], a
    ret
