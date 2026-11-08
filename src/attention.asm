; attention.asm - single-query multi-head causal attention over cached keys/values.
; Scores -> max-subtract -> ExpLut -> reciprocal normalization -> weighted value sum.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "attn_vars", WRAM0
wScore::     ds MODEL_CTX     ; int8 scores (vanilla: full vector kept)
wWeight::    ds MODEL_CTX     ; normalized Q7 weights
wAttnL::     ds 1             ; number of positions attended (t+1)
wAttnHead::  ds 1             ; head byte offset: 0 or MODEL_HEAD_DIM
wAttnOut:    ds 2
wAttnQ:      ds 2

SECTION "attn_code", ROM0
; KVRowPtr: a = position, hl = page-base of cache (K or V). -> hl = base + a*MODEL_D. Clobbers a, de.
KVRowPtr::
    ld d, h
    ld e, l
    ld l, a
    ld h, 0
    REPT 5
    add hl, hl
    ENDR
    add hl, de
    ret

; AttendHead: de -> q head vector (MODEL_HEAD_DIM), bc -> output head vector, a = head offset.
; Uses wKCache/wVCache and wAttnL. Clobbers everything.
AttendHead::
    ld [wAttnHead], a
    ld a, e
    ld [wAttnQ], a
    ld a, d
    ld [wAttnQ + 1], a
    ld a, c
    ld [wAttnOut], a
    ld a, b
    ld [wAttnOut + 1], a
IF DEF(FAST_DOT)
    ; scores via the fused kernel: q is biased into the HRAM slots once
    ld a, MODEL_HEAD_DIM
    call LoadXBiased
    xor a
.fscore:
    push af
    ld hl, wKCache
    call KVRowPtr
    ld a, [wAttnHead]
    ld e, a
    ld d, 0
    add hl, de
    ld b, h
    ld c, l
    xor a
    ldh [hAcc + 2], a
    ld d, a
    ld e, a
    call DotRaw16
    ld c, ATTN_SHIFT
    call RequantAcc
    ld c, a
    pop af
    ld hl, wScore
    ld e, a
    ld d, 0
    add hl, de
    ld [hl], c
    inc a
    ld hl, wAttnL
    cp [hl]
    jr nz, .fscore
ELSE
    ; scores
    xor a
.score:
    push af
    ld hl, wKCache
    call KVRowPtr
    ld a, [wAttnHead]
    ld e, a
    ld d, 0
    add hl, de
    ld a, [wAttnQ]
    ld e, a
    ld a, [wAttnQ + 1]
    ld d, a
    ld b, MODEL_HEAD_DIM
    call Dot
    ld c, ATTN_SHIFT
    call RequantAcc
    ld c, a
    pop af
    ld hl, wScore
    ld e, a
    ld d, 0
    add hl, de
    ld [hl], c
    inc a
    ld hl, wAttnL
    cp [hl]
    jr nz, .score
ENDC
    call ScoresToWeights
IF DEF(ATTN_SPARSE)
    jp AggregateSparse
ENDC
    ; value aggregation, one output element at a time
    ld b, 0              ; b = element index
.elem:
    push bc
    call ClearAcc
    xor a
.pos:
    push af
    ; v = V[pos][head + elem]
    ld hl, wVCache
    call KVRowPtr
    ld a, [wAttnHead]
    pop de               ; d = pos
    pop bc
    push bc
    push de
    add b
    ld e, a
    ld d, 0
    add hl, de
    ld c, [hl]           ; c = value
    pop af               ; a = pos
    push af
    ld hl, wWeight
    ld e, a
    ld d, 0
    add hl, de
    ld a, [hl]           ; a = weight
    call MulS8
    ; accumulate
    ld a, h
    rlca
    sbc a
    ld b, a
    ldh a, [hAcc]
    add l
    ldh [hAcc], a
    ldh a, [hAcc + 1]
    adc h
    ldh [hAcc + 1], a
    ldh a, [hAcc + 2]
    adc b
    ldh [hAcc + 2], a
    pop af
    inc a
    ld hl, wAttnL
    cp [hl]
    jr nz, .pos
    ld c, W_SHIFT
    call RequantAcc
    ld c, a
    ld hl, wAttnOut
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    pop de               ; d = elem (from pushed bc: b)
    push de
    ld a, d
    add l
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld [hl], c
    pop bc
    inc b
    ld a, b
    cp MODEL_HEAD_DIM
    jr nz, .elem
    ret

; ScoresToWeights: wScore[0..L) -> wWeight[0..L). Clobbers everything.
ScoresToWeights::
    ; max
    ld hl, wScore
    ld a, [wAttnL]
    ld b, a
    ld c, $81            ; running max, signed
.max:
    ld a, [hl+]
    ; signed compare a > c
    xor $80
    ld e, a
    ld a, c
    xor $80
    cp e                 ; carry if biased c < biased a
    jr nc, .nomax
    ld a, e
    xor $80
    ld c, a
.nomax:
    dec b
    jr nz, .max
    ; raw weights into wWeight, running 16-bit sum in de
    ld de, 0
    ld hl, wScore
    ld a, [wAttnL]
    ld b, a
.raw:
    ld a, c
    sub [hl]             ; top - s, always 0..254
    cp 128
    jr c, .lut
    xor a                ; contribution 0
    jr .have
.lut:
    push hl
    ld hl, ExpLut
    add l
    ld l, a
    ld a, [hl]
    pop hl
.have:
    push hl
    push de
    ld de, MODEL_CTX
    add hl, de           ; wWeight is directly after wScore
    pop de
    ld [hl], a
    pop hl
    add e
    ld e, a
    jr nc, .nc
    inc d
.nc:
    inc hl
    dec b
    jr nz, .raw
    ; idx = sum >> 4, r = RecipLut[idx]
    REPT 4
    srl d
    rr e
    ENDR
    ld d, HIGH(RecipLut)
    ld a, [de]
    ld c, a              ; c = r
    ; w' = (w*r + 64) >> 7
    ld hl, wWeight
    ld a, [wAttnL]
    ld b, a
.norm:
    push hl
    push bc
    ld a, [hl]
    call MulS8
    ld de, 64
    add hl, de
    add hl, hl           ; >> 7 == (<< 1) then take high byte; values are non-negative
    ld a, h
    pop bc
    pop hl
    ld [hl+], a
    dec b
    jr nz, .norm
    ret

IF DEF(ATTN_SPARSE)
SECTION "attn_sparse_vars", WRAM0, ALIGN[8]
wAcc16: ds MODEL_HEAD_DIM * 2

SECTION "attn_sparse_hram", HRAM
hWb:    ds 1                  ; biased weight of the current position
hLoopJ: ds 1
hLoopI: ds 1

SECTION "attn_sparse", ROM0
; AggregateSparse: position-wise sum into 16-bit accumulators, skipping weights that rounded to zero.
; Result is identical to the column-wise form: sum w' stays below 2^15 / 127, see docs/NUMERICS.md.
AggregateSparse:
    ld hl, wAcc16
    ld b, MODEL_HEAD_DIM * 2
    xor a
.clr:
    ld [hl+], a
    dec b
    jr nz, .clr
    ldh [hLoopJ], a
.pos:
    ldh a, [hLoopJ]
    ld hl, wWeight
    add l
    ld l, a
    jr nc, .ncw
    inc h
.ncw:
    ld a, [hl]
    or a
    jr z, .nextpos
    xor $80
    ldh [hWb], a
    ldh a, [hLoopJ]
    ld hl, wVCache
    call KVRowPtr
    ld a, [wAttnHead]
    ld e, a
    ld d, 0
    add hl, de
    ld d, h
    ld e, l              ; de -> V[j][head]
    ld bc, wAcc16
    ld a, MODEL_HEAD_DIM
    ldh [hLoopI], a
.elem:
    ; acc += q(v'+w') - q(v'-w'), two in-place 16-bit updates
    ldh a, [hWb]
    ld l, a
    ld a, [de]
    xor $80
    add l
    ld l, a
    ld a, HIGH(QTab)
    adc 0
    ld h, a
    ld a, [bc]
    add [hl]
    ld [bc], a
    inc c
    inc h
    inc h
    ld a, [bc]
    adc [hl]
    ld [bc], a
    dec c
    ldh a, [hWb]
    ld l, a
    ld a, [de]
    xor $80
    sub l
    ld l, a
    ld a, HIGH(QTab) + 1
    sbc 0
    ld h, a
    ld a, [bc]
    sub [hl]
    ld [bc], a
    inc c
    inc h
    inc h
    ld a, [bc]
    sbc [hl]
    ld [bc], a
    inc c
    inc de
    ldh a, [hLoopI]
    dec a
    ldh [hLoopI], a
    jr nz, .elem
.nextpos:
    ldh a, [hLoopJ]
    inc a
    ldh [hLoopJ], a
    ld hl, wAttnL
    cp [hl]
    jr nz, .pos
    ; requantize each accumulator: (acc + 64) >> 7 then sat8, shared helpers keep the semantics single-sourced
    ld hl, wAcc16
    ld a, MODEL_HEAD_DIM
    ldh [hLoopI], a
.out:
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a
    push hl
    ld a, e
    ldh [hAcc], a
    ld a, d
    ldh [hAcc + 1], a
    rlca
    sbc a
    ldh [hAcc + 2], a
    ld c, W_SHIFT
    call RequantAcc
    ld c, a
    ld hl, wAttnOut
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld [hl], c
    inc hl
    ld a, l
    ld [wAttnOut], a
    ld a, h
    ld [wAttnOut + 1], a
    pop hl
    ldh a, [hLoopI]
    dec a
    ldh [hLoopI], a
    jr nz, .out
    ret
ENDC
