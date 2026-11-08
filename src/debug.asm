; debug.asm - instrumentation mailbox at a fixed address, read by the PyBoy harness.
; The game never reads anything here except wMB_ForceSeed* and wMB_Greedy, which default to 0.
INCLUDE "constants.inc"

SECTION "mailbox", WRAM0[$DF00]
wMB_Magic::        ds 4     ; "GBGT" once booted
wMB_State::        ds 1     ; ST_* value
wMB_Phase::        ds 1     ; inference phase marker
wMB_Turn::         ds 1
wMB_Room::         ds 1
wMB_Lives::        ds 1
wMB_Inv::          ds 1
wMB_Action::       ds 1
wMB_Outcome::      ds 1
wMB_NumTokens::    ds 1     ; tokens generated in the current event
wMB_Fallbacks::    ds 1     ; events that hit the token cap without EOS
wMB_Events::       ds 1
wMB_ForceSeed::    ds 1     ; harness: nonzero uses wMB_Seed instead of DIV entropy
wMB_Seed::         ds 2
wMB_Greedy::       ds 1     ; harness: nonzero forces argmax decoding
wMB_Placeholder::  ds 1     ; nonzero if a static placeholder event was shown
wMB_BankSwitches:: ds 3
wMB_EventFrames::  ds 2     ; on-device timing of last event, in LCD frames
wMB_LastTokens::   ds 16    ; prompt + generated ids of the current event
wMB_LogitSum::     ds 2     ; 16-bit wrapping sum of the masked logits of the last step
wMB_Cmd::          ds 1     ; test ROM command
wMB_CmdSeq::       ds 1     ; harness increments to request execution
wMB_CmdDone::      ds 1     ; ROM copies wMB_CmdSeq when finished
wMB_Args::         ds 8     ; test ROM arguments

SECTION "debug_code", ROM0
DebugInit::
    ld hl, wMB_Magic
    ld a, 'G'
    ld [hl+], a
    ld a, 'B'
    ld [hl+], a
    ld a, 'G'
    ld [hl+], a
    ld a, 'T'
    ld [hl+], a
    ret
