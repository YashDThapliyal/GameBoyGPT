; tokenizer.asm - symbolic prompt formatter and narration wiring.
; Prompt: <BOS> ROOM INV ACT OUT. Ids follow training/dataset.py's vocabulary order.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "tok_code", ROM0
IF !DEF(TEST_ROM)
; BuildPrompt: wSeq/wSeqLen from authoritative game state: <BOS> BEAT FLAGS FATE. Clobbers a, de, hl, b.
BuildPrompt::
    ld hl, wSeq
    xor a
    ld [hl+], a          ; <BOS> is id 0
    ld a, [wBeatTok]
    ld [hl+], a
    push hl
    ld a, [wFlags]
    ld e, a
    ld d, 0
    ld hl, FlagTokens
    add hl, de
    ld a, [hl]
    pop hl
    ld [hl+], a
    ld a, [wFate]
    add TOK_FATE0
    ld [hl+], a
    ld a, PROMPT_LEN
    ld [wSeqLen], a
    ; mirror the exact input ids for replay traces (instrumentation only)
    ld hl, wSeq
    ld de, wMB_LastTokens
    ld b, PROMPT_LEN
.mirror:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .mirror
    ret

; NarrateEvent: runs the neural model on the Game Boy CPU and streams words into the story box.
NarrateEvent::
    call ThinkingPanel
    call BuildPrompt
    call ModelReset
    call EventTimerStart
    ld a, ST_GENERATING
    call SetState
    xor a
    call ThinkingProgress
    call GenerateTokens
    jr nc, .ok
    ; Token cap reached without EOS: never hidden, counted and visibly elided.
    ld hl, wMB_Fallbacks
    inc [hl]
    ld hl, wTotalFallbacks
    inc [hl]
    ld a, '.'
    call AppendRaw
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
    ; mirror sequence for the harness
    ld a, [wMB_NumTokens]
    add PROMPT_LEN - 1
    ld e, a
    ld d, 0
    ld hl, wMB_LastTokens
    add hl, de
    ld [hl], b
    ld a, b
    cp TOK_EOS
    call nz, AppendWord
    ld a, [wMB_NumTokens]
    jp ThinkingProgress

; AppendWord: a = token id above <EOS>. Wraps at TEXT_WIDTH. A full stop sticks to the word before it and
; makes the next letter a capital. Clobbers everything.
AppendWord:
    sub TOK_FIRST_GEN
    ld l, a
    ld h, 0
    add hl, hl           ; 16-bit: the word table is larger than 128 entries
    ld de, WordPtrs
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a              ; hl = word
    ld a, [hl]
    cp '.'
    jr nz, .word
    call AppendRaw
    ld a, 1
    ld [wCapNext], a
    ret
.word:
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

; AppendRaw: a = ASCII at the text cursor. Clobbers a, bc, de, hl.
AppendRaw:
    ld c, a
    ld a, [wTextRowN]
    cp TEXT_ROWS
    ret nc               ; never draw past the story box, even for an ungrammatical event
    ld a, [wCapNext]
    or a
    ld a, c
    jr z, .plain
    cp 'a'
    jr c, .plain
    sub 'a' - 'A'
    ld c, a
    xor a
    ld [wCapNext], a
    ld a, c
.plain:
    sub $20
    push af
    ld a, [wTextRowN]
    add a                ; double-spaced lines
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
