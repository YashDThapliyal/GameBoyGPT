; selftest.asm - runs on any emulator or real unit with no host involvement. Generates fixed workloads, compares the
; tokens against expectations baked in from the integer reference, and prints the verdict on screen.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

IF DEF(SELFTEST)
DEF CASE_SIZE EQU 1 + MODEL_CTX * 2     ; length, then 16-bit ids

SECTION "selftest_vars", WRAM0
wStCase: ds 1
wStFail: ds 1

SECTION "selftest_code", ROM0
StrStPass: db "SELFTEST PASS", 0
StrStFail: db "SELFTEST FAIL", 0

SelfTestMain::
    ld a, ST_STREAMING
    ld [wMB_State], a
    ld a, 1
    ld [wMB_Greedy], a
    xor a
    ld [wStCase], a
    ld [wStFail], a
.case:
    ld a, [wStCase]
    call StCasePtr
    inc hl               ; skip length: the prompt is always first
    ld de, wSeq
    ld b, PROMPT_LEN * 2
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    ld a, PROMPT_LEN
    ld [wSeqLen], a
    call ModelReset
    call EventTimerStart
    call GenerateTokens
    call EventTimerStop
    ld a, [wStCase]
    call StCasePtr
    ld a, [wSeqLen]
    cp [hl]
    jr z, .lenok
    ld [wStFail], a
.lenok:
    ld a, [hl+]
    add a
    ld c, a              ; bytes to compare
    ld de, wSeq
.cmp:
    ld a, [de]
    cp [hl]
    jr z, .same
    ld a, 1
    ld [wStFail], a
.same:
    inc de
    inc hl
    dec c
    jr nz, .cmp
    ld a, [wStCase]
    ld b, a
    ld c, 2
    call RowPtr
    ld a, [wLastEventFrames]
    ld e, a
    ld a, [wLastEventFrames + 1]
    ld d, a
    call PrintDec16
    ld a, [wStCase]
    ld b, a
    call MarkRow
    ld a, [wStCase]
    inc a
    ld [wStCase], a
    cp SELFTEST_CASES
    jp nz, .case
    ld a, [wStFail]
    or a
    ld hl, StrStPass
    jr z, .show
    ld hl, StrStFail
.show:
    ld b, 5
    ld c, 2
    call PrintAt
    ld a, ST_SELFTEST_DONE
    ld [wMB_State], a
.idle:
    call WaitVBlank
    jr .idle

; StCasePtr: a = case -> hl. Clobbers a, de.
StCasePtr:
    ld hl, SelfTestCases
    ld de, CASE_SIZE
    or a
    ret z
.step:
    add hl, de
    dec a
    jr nz, .step
    ret
ENDC
