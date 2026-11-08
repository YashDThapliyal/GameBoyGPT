; norm.asm - mean-absolute normalization: m = (sum|x| + d/2) >> log2 d; g = NormLut[m]; x' = sat8((x*g + 16) >> 5).
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "norm_vars", WRAM0
wNormSrc: ds 2
wNormDst: ds 2
wNormG:   ds 1
wNormN:   ds 1

SECTION "norm_code", ROM0
; Norm: de -> in[MODEL_D], bc -> out[MODEL_D]. In and out may alias. Clobbers everything.
Norm::
    ld a, e
    ld [wNormSrc], a
    ld a, d
    ld [wNormSrc + 1], a
    ld a, c
    ld [wNormDst], a
    ld a, b
    ld [wNormDst + 1], a
    ; sum of magnitudes, starting from the rounding term d/2
    ld hl, MODEL_D / 2
    ld b, MODEL_D
.sum:
    ld a, [de]
    inc de
    bit 7, a
    jr z, .pos
    cpl
    inc a
.pos:
    add l
    ld l, a
    jr nc, .nc
    inc h
.nc:
    dec b
    jr nz, .sum
    ; hl >> 5 for d = 32
    REPT 5
    srl h
    rr l
    ENDR
    ld a, l
    ld hl, NormLut
    add l
    ld l, a
    ld a, [hl]
    ld [wNormG], a
    ld a, MODEL_D
    ld [wNormN], a
.each:
    ld hl, wNormSrc
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, [hl+]
    push af
    ld a, l
    ld [wNormSrc], a
    ld a, h
    ld [wNormSrc + 1], a
    ld a, [wNormG]
    ld c, a
    pop af
    call MulS8
    ld de, 16
    add hl, de
    REPT 5
    sra h
    rr l
    ENDR
    call SatHL
    ld c, a
    ld hl, wNormDst
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld [hl], c
    inc hl
    ld a, l
    ld [wNormDst], a
    ld a, h
    ld [wNormDst + 1], a
    ld hl, wNormN
    dec [hl]
    jr nz, .each
    ret

; SatHL: hl signed -> a in [-127,127]. Preserves hl.
SatHL::
    ld a, h
    or a
    jr nz, .neg
    ld a, l
    cp 128
    ret c
    ld a, 127
    ret
.neg:
    inc a
    jr nz, .far
    ld a, l
    cp $81
    ret nc
    ld a, $81
    ret
.far:
    bit 7, h
    ld a, 127
    ret z
    ld a, $81
    ret
