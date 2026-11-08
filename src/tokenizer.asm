; tokenizer.asm - symbolic prompt formatter and narration wiring.
; Prompt: <BOS> ROOM INV ACT OUT. Ids follow training/dataset.py's vocabulary order.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

DEF TOK_BOS   EQU 0
DEF TOK_ROOM0 EQU 1
DEF TOK_INV0  EQU 9
DEF TOK_ACT0  EQU 12
DEF TOK_OUT0  EQU 16

SECTION "tok_code", ROM0
; BuildPrompt: wSeq/wSeqLen from authoritative game state. Clobbers a, hl.
BuildPrompt::
    ld hl, wSeq
    ld a, TOK_BOS
    ld [hl+], a
    ld a, [wRoom]
    add TOK_ROOM0
    ld [hl+], a
    call InvCode
    add TOK_INV0
    ld [hl+], a
    ld a, [wAction]
    add TOK_ACT0
    ld [hl+], a
    ld a, [wOutcome]
    add TOK_OUT0
    ld [hl+], a
    ld a, 5
    ld [wSeqLen], a
    ret

IF !DEF(TEST_ROM)
; NarrateEvent: runs the neural model on the Game Boy CPU and streams words into the story box.
NarrateEvent::
    call ThinkingPanel
    call BuildPrompt
    call ModelReset
    call EventTimerStart
    ld a, ST_GENERATING
    call SetState
    xor a
    ld c, 11
    call ThinkingProgress
    call GenerateTokens
    jr nc, .ok
    ; Token cap reached without EOS: never hidden, counted and visibly elided.
    ld hl, wMB_Fallbacks
    inc [hl]
    ld hl, wTotalFallbacks
    inc [hl]
    ld a, '.'
    call AppendChar
.ok:
    call EventTimerStop
    ld a, [wMB_NumTokens]
    ld [wLastEventTokens], a
    ld hl, wMB_Events
    inc [hl]
    jp ThinkingDone

; TokenHook: a = new token id. Called by the generator after each token; preserves nothing.
TokenHook::
    ld b, a
    push bc
    ; mirror sequence for the harness
    ld a, [wMB_NumTokens]
    add 4
    ld e, a
    ld d, 0
    ld hl, wMB_LastTokens
    add hl, de
    ld [hl], b
    pop bc
    ld a, b
    cp TOK_EOS
    jr nz, .word
    ld a, '.'
    call AppendChar
    jr .prog
.word:
    call AppendWord
.prog:
    ld a, [wMB_NumTokens]
    ld c, 11
    jp ThinkingProgress

; AppendWord: a = token id >= first word. Wraps at TEXT_WIDTH. Clobbers everything.
AppendWord:
    sub TOK_FIRST_GEN
    add a
    ld e, a
    ld d, 0
    ld hl, WordPtrs
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a              ; hl = word
    ; length
    push hl
    ld b, 0
.len:
    ld a, [hl+]
    or a
    jr z, .haveLen
    inc b
    jr .len
.haveLen:
    ld a, [wTextColN]
    or a
    jr z, .noSpace
    add b
    inc a                ; col + space + word
    cp TEXT_WIDTH + 1
    jr c, .fits
    ld hl, wTextRowN
    inc [hl]
    xor a
    ld [wTextColN], a
    jr .noSpace
.fits:
    ld hl, wTextColN
    inc [hl]
.noSpace:
    pop de               ; de = word
.put:
    ld a, [de]
    or a
    ret z
    inc de
    push de
    call AppendRaw
    pop de
    jr .put

; AppendChar: a = ASCII, no wrapping (punctuation sticks to the word).
AppendChar:
    jr AppendRaw

; AppendRaw: a = ASCII at the text cursor. Clobbers a, bc, de, hl.
AppendRaw:
    sub $20
    push af
    ld a, [wTextRowN]
    add TEXT_ROW
    ld b, a
    ld a, [wTextColN]
    add TEXT_COL
    ld c, a
    call RowPtr
    pop af
    ld [hl], a
    call MarkRow
    ld hl, wTextColN
    inc [hl]
    ret
ENDC
