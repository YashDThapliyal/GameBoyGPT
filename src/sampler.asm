; sampler.asm - decoding over wLogits: rows allowed at this position, repetition penalty, argmax and seeded sampling.
; Matches reference/fixed_point.py: allowed_rows, penalized, argmax_range, sample_range.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "sampler_vars", WRAM0
wNarrRng::   ds 2
wPickId::    ds 2
wGenStart::  ds 1
wBestLeft:   ds 2             ; rows remaining when the best row was found
wCandId:     ds SAMPLE_CANDS * 2
wCandW:      ds SAMPLE_CANDS
wCandN:      ds 1
wWeightSum:  ds 2

SECTION "sampler_code", ROM0
; RowRange: -> hl = first allowed logit, bc = allowed rows. Clobbers a.
RowRange:
    ld a, [wRowMode]
    or a
    jr nz, .later
    ld hl, wLogits + TOK_FIRST_EMOTION * 2
    ld bc, TOK_EOS - TOK_FIRST_EMOTION
    ret
.later:
    ld hl, wLogits + TOK_EOS * 2
    ld bc, MODEL_VOCAB - TOK_EOS
    ret

; RowEnd: -> de = one past the last allowed id. Clobbers nothing else.
RowEnd:
    ld a, [wRowMode]
    or a
    ld de, TOK_EOS
    ret z
    ld de, MODEL_VOCAB
    ret

; ArgmaxRange: -> wPickId = best id, ties to the lowest. de = its logit, high byte biased by $80. Clobbers everything.
ArgmaxRange::
    call RowRange
    ld a, c
    ld [wBestLeft], a
    ld a, b
    ld [wBestLeft + 1], a
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    xor $80
    ld d, a
.loop:
    dec bc
    ld a, b
    or c
    jr z, .done
    ld a, [hl+]
    push af
    ld a, [hl+]
    xor $80
    cp d
    jr c, .lower
    jr nz, .take
    pop af
    push af
    cp e
    jr c, .lower
    jr z, .lower
    ld a, d
.take:
    ld d, a
    pop af
    ld e, a
    ld a, c
    ld [wBestLeft], a
    ld a, b
    ld [wBestLeft + 1], a
    jr .loop
.lower:
    pop af
    jr .loop
.done:
    push de
    call RowEnd
    ld a, [wBestLeft]
    ld c, a
    ld a, [wBestLeft + 1]
    ld b, a
    ld a, e
    sub c
    ld [wPickId], a
    ld a, d
    sbc b
    ld [wPickId + 1], a
    pop de
    ret

; ApplyPenalty: each generated word already in wSeq lowers its logit once per use. Clobbers everything.
ApplyPenalty::
    ld a, [wGenStart]
    ld b, a
.next:
    ld a, [wSeqLen]
    cp b
    ret z
    push bc
    ld l, b
    ld h, 0
    add hl, hl
    ld de, wSeq
    add hl, de
    ld a, [hl+]
    ld e, a
    ld d, [hl]
    ; id >= TOK_FIRST_WORD ?
    ld a, e
    sub LOW(TOK_FIRST_WORD)
    ld a, d
    sbc HIGH(TOK_FIRST_WORD)
    jr c, .skip
    ld h, d
    ld l, e
    add hl, hl
    ld de, wLogits
    add hl, de
    ld a, [hl]
    sub LOW(REP_PENALTY)
    ld [hl+], a
    ld a, [hl]
    sbc HIGH(REP_PENALTY)
    ld [hl], a
.skip:
    pop bc
    inc b
    jr .next

; SampleRange: softmax over the first candidates within SAMPLE_MARGIN of the best. -> wPickId. Clobbers everything.
SampleRange::
    call ArgmaxRange
    ; de = best (biased). Remember it, then threshold = best - margin. Thresholds cannot underflow: logits are about +-13000.
    ld a, e
    ld [wCandTop], a
    ld a, d
    ld [wCandTop + 1], a
    ld a, e
    sub LOW(SAMPLE_MARGIN)
    ld e, a
    ld a, d
    sbc HIGH(SAMPLE_MARGIN)
    ld d, a
    xor a
    ld [wCandN], a
    ld [wWeightSum], a
    ld [wWeightSum + 1], a
    call RowRange
.scan:
    ld a, [hl+]
    push af
    ld a, [hl+]
    xor $80
    cp d
    jr c, .below
    jr nz, .cand
    pop af
    push af
    cp e
    jr c, .below
.cand:
    ; a = candidate high (biased) in most paths: reload it from memory to keep this simple
    pop af
    push bc
    push de
    push hl
    dec hl
    ld d, [hl]
    dec hl
    ld e, [hl]
    ; delta = top - logit
    ld a, d
    xor $80
    ld d, a
    ld a, [wCandTop]
    sub e
    ld e, a
    ld a, [wCandTop + 1]
    sbc d
    ld d, a
    call CandWeight      ; a = weight
    ld hl, wWeightSum
    ld c, a
    add [hl]
    ld [hl+], a
    ld a, [hl]
    adc 0
    ld [hl], a
    ; store the weight
    ld a, [wCandN]
    ld e, a
    ld d, 0
    ld hl, wCandW
    add hl, de
    ld [hl], c
    pop hl               ; hl -> next logit
    pop de
    pop bc               ; bc = rows left including this one
    push hl
    push de
    ; id = end - left
    push bc
    call RowEnd
    pop bc
    ld a, e
    sub c
    ld e, a
    ld a, d
    sbc b
    ld d, a
    ld a, [wCandN]
    add a
    ld l, a
    ld h, 0
    push bc
    ld bc, wCandId
    add hl, bc
    pop bc
    ld a, e
    ld [hl+], a
    ld [hl], d
    pop de
    pop hl
    ld a, [wCandN]
    inc a
    ld [wCandN], a
    cp SAMPLE_CANDS
    jr z, .pick
    jr .next
.below:
    pop af
.next:
    dec bc
    ld a, b
    or c
    jr nz, .scan
.pick:
    ; rng_byte on the 16-bit LFSR
    ld a, [wNarrRng]
    ld c, a
    ld a, [wNarrRng + 1]
    ld b, a
    REPT 8
    srl b
    rr c
    jr nc, :+
    ld a, b
    xor $B4
    ld b, a
:
    ENDR
    ld a, c
    ld [wNarrRng], a
    ld a, b
    ld [wNarrRng + 1], a
    ; pick = (byte * sum) >> 8, kept in h:l after shifting through e:h:l
    ld a, [wWeightSum]
    ld e, a
    ld a, [wWeightSum + 1]
    ld d, a              ; de = sum
    ld b, c              ; b = byte
    ld hl, 0
    ld c, 0              ; c:h:l = 24-bit product
    REPT 8
    add hl, hl
    rl c
    sla b
    jr nc, :+
    add hl, de
    jr nc, :+
    inc c
:
    ENDR
    ld l, h
    ld h, c              ; hl = pick
    ; walk the candidates
    ld de, wCandW
    ld b, 0
.walk:
    ld a, [de]
    inc de
    ld c, a
    ld a, h
    or a
    jr nz, .past
    ld a, l
    cp c
    jr c, .found
.past:
    ld a, l
    sub c
    ld l, a
    ld a, h
    sbc 0
    ld h, a
    inc b
    jr .walk
.found:
    ld l, b
    ld h, 0
    add hl, hl
    ld de, wCandId
    add hl, de
    ld a, [hl+]
    ld [wPickId], a
    ld a, [hl]
    ld [wPickId + 1], a
    ret

; CandWeight: de = logit distance from the best. -> a = ExpLut[min(127, delta * 16 >> SHIFT_OUT)]. Clobbers de, hl.
CandWeight:
    ld h, d
    ld l, e
IF SHIFT_OUT >= 4
    REPT SHIFT_OUT - 4
    srl h
    rr l
    ENDR
ELSE
    REPT 4 - SHIFT_OUT
    add hl, hl
    ENDR
ENDC
    ld a, h
    or a
    jr nz, .far
    ld a, l
    cp 128
    jr c, .ok
.far:
    ld a, 127
.ok:
    ld hl, ExpLut
    add l
    ld l, a
    ld a, [hl]
    ret

; GenerateTokens: wSeq/wSeqLen hold the prompt. Appends tokens up to the context cap or EOS, calling the UI hook
; after each. Returns carry set if capped without EOS. Clobbers everything.
GenerateTokens::
    xor a
    ld [wMB_NumTokens], a
    ld a, [wSeqLen]
    ld [wGenStart], a
.next:
    ld a, [wSeqLen]
    cp MODEL_CTX
    jr z, .capped
    ld a, [wMB_NumTokens]
    or a
    jr z, .mode
    ld a, 1
.mode:
    ld [wRowMode], a
    call ProfileTokenStart
    call ForwardStep
    call PickToken
    ; append to wSeq
    ld a, [wSeqLen]
    ld l, a
    ld h, 0
    add hl, hl
    ld de, wSeq
    add hl, de
    ld a, [wPickId]
    ld [hl+], a
    ld a, [wPickId + 1]
    ld [hl], a
    ld hl, wSeqLen
    inc [hl]
    ld hl, wMB_NumTokens
    inc [hl]
    call ProfileTokenEnd
    call TokenHook
    ld a, [wPickId]
    cp LOW(TOK_EOS)
    jr nz, .next
    ld a, [wPickId + 1]
    cp HIGH(TOK_EOS)
    jr nz, .next
    and a                ; clear carry: finished with EOS
    ret
.capped:
    scf
    ret

; PickToken: greedy or sampled per wMB_Greedy; records the checksum of the unpenalized allowed logits. -> wPickId.
PickToken::
    call LogitChecksum
    call ApplyPenalty
    ld a, [wMB_Greedy]
    or a
    jp z, SampleRange
    jp ArgmaxRange

; LogitChecksum: 16-bit wrapping sum of the allowed logits into wMB_LogitSum.
LogitChecksum:
    call RowRange
    ld de, 0
.l:
    ld a, [hl+]
    add e
    ld e, a
    ld a, [hl+]
    adc d
    ld d, a
    dec bc
    ld a, b
    or c
    jr nz, .l
    ld a, e
    ld [wMB_LogitSum], a
    ld a, d
    ld [wMB_LogitSum + 1], a
    ret

SECTION "sampler_vars2", WRAM0
wCandTop: ds 2
