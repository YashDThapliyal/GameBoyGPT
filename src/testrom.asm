; testrom.asm - kernel test entry, only assembled into the test ROM (-D TEST_ROM). LCD off, interrupts off.
; The harness writes inputs into WRAM, bumps wMB_CmdSeq and waits for wMB_CmdDone.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

IF DEF(TEST_ROM)
SECTION "test_vars", WRAM0, ALIGN[8]
wTestA::   ds 256
wTestB::   ds 256
wTestOut:: ds 256

SECTION "test_code", ROM0
TestMain::
    ld a, LCDC_ON
    xor $80
    ldh [rLCDC], a
    xor a
    ldh [rIE], a
    ld [wMB_Greedy], a
    ld a, 1
    ld [wMB_State], a
TestWaitLoop:
    ld a, [wMB_CmdDone]
    ld b, a
    ld a, [wMB_CmdSeq]
    cp b
    jr z, TestWaitLoop
    call Dispatch
TestDispatchEnd::
    ld a, [wMB_CmdSeq]
    ld [wMB_CmdDone], a
    jr TestWaitLoop

Dispatch:
    ld a, [wMB_Cmd]
    add a
    ld e, a
    ld d, 0
    ld hl, .table
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    jp hl
.table:
    dw CmdNop, CmdMul, CmdDot, CmdRequant, CmdNorm, CmdAttend, CmdMatVec, CmdStep, CmdGenerate, CmdSatAdd, CmdRelu, CmdWeights, CmdSample, CmdParse, CmdTurn, CmdReset
CmdNop:
    ret
; 1: args[0]*args[1] -> args[2..3]
CmdMul:
    ld a, [wMB_Args + 1]
    ld c, a
    ld a, [wMB_Args]
TestMulSite::
    call MulS8
TestMulEnd::
    ld a, l
    ld [wMB_Args + 2], a
    ld a, h
    ld [wMB_Args + 3], a
    ret
; 2: dot(wTestA, wTestB, args[0]) -> hAcc copied to args[1..3]
CmdDot:
    ld hl, wTestA
    ld de, wTestB
    ld a, [wMB_Args]
    ld b, a
TestDotSite::
    call Dot
TestDotEnd::
    ldh a, [hAcc]
    ld [wMB_Args + 1], a
    ldh a, [hAcc + 1]
    ld [wMB_Args + 2], a
    ldh a, [hAcc + 2]
    ld [wMB_Args + 3], a
    ret
; 3: acc = args[0..2], shift = args[3] -> args[4]
CmdRequant:
    ld a, [wMB_Args]
    ldh [hAcc], a
    ld a, [wMB_Args + 1]
    ldh [hAcc + 1], a
    ld a, [wMB_Args + 2]
    ldh [hAcc + 2], a
    ld a, [wMB_Args + 3]
    ld c, a
    call RequantAcc
    ld [wMB_Args + 4], a
    ret
; 4: norm(wTestA) -> wTestOut
CmdNorm:
    ld de, wTestA
    ld bc, wTestOut
    jp Norm
; 5: q in wTestA[0..16), wKCache/wVCache preset, wAttnL = args[0], head offset args[1] -> wTestOut
CmdAttend:
    ld a, [wMB_Args]
    ld [wAttnL], a
    ld de, wTestA
    ld bc, wTestOut
    ld a, [wMB_Args + 1]
    jp AttendHead
; 6: tensor index args[0], x = wTestA -> wTestOut
CmdMatVec:
    ld a, [wMB_Args]
    ld e, a
    add a
    add e
    add a                ; *6
    ld e, a
    ld d, 0
    ld hl, TTok
    add hl, de
    ld de, wTestA
    ld bc, wTestOut
    jp MatVec
; 7: wSeq/wSeqLen/wRowMode preset -> wLogits
CmdStep:
    call ModelReset
    jp ForwardStep
; 8: wSeq/wSeqLen preset, wMB_Greedy, wNarrRng preset -> tokens
CmdGenerate:
    call ModelReset
    call GenerateTokens
    ld a, 0
    rla
    ld [wMB_Args], a     ; 1 if capped
    ret
; 9: satadd(wTestA, wTestB) -> wTestOut
CmdSatAdd:
    ld hl, wTestA
    ld de, wTestB
    ld bc, wTestOut
    jp SatAdd
; 10: relu in place on wTestA, length args[0]
CmdRelu:
    ld hl, wTestA
    ld a, [wMB_Args]
    ld b, a
    jp Relu
; 11: wScore preset, wAttnL = args[0] -> wWeight
CmdWeights:
    ld a, [wMB_Args]
    ld [wAttnL], a
    jp ScoresToWeights
; 12: wLogits and wRowMode preset; args[0] nonzero = sample -> args[1..2]
CmdSample:
    ld a, [wMB_Args]
    or a
    jr nz, .s
    call ArgmaxRange
    jr .out
.s:
    call SampleRange
.out:
    ld a, [wPickId]
    ld [wMB_Args + 1], a
    ld a, [wPickId + 1]
    ld [wMB_Args + 2], a
    ret
; 13: wInput/wInputLen preset -> wParsed*
CmdParse:
    ld a, UI_BANK
    call BankSwitch
    jp Parse
; 14: wParsed* preset -> memory, mood, relation, prompt in wSeq
CmdTurn:
    ld a, UI_BANK
    call BankSwitch
    call ApplyTurn
    jp BuildPrompt
; 15: a new relationship
CmdReset:
    ld a, UI_BANK
    call BankSwitch
    jp StateReset

TokenHook::
    ret
ENDC
