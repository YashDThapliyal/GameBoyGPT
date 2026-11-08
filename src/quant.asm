; quant.asm - accumulator and fixed-point requantization. Semantics: docs/NUMERICS.md.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "acc_hram", HRAM
hAcc:: ds 3                 ; 24-bit signed accumulator, little-endian

SECTION "quant_code", ROM0
; RsAcc: round-half-up arithmetic shift of hAcc by c bits. Returns b:d:e (24-bit signed). Clobbers a, c.
RsAcc::
    ldh a, [hAcc]
    ld e, a
    ldh a, [hAcc + 1]
    ld d, a
    ldh a, [hAcc + 2]
    ld b, a
    ld a, c
    or a
    ret z
    ; rounding constant 1 << (c-1) into h:l
    push hl
    ld hl, 1
    dec a
    jr z, .added
.mk:
    add hl, hl
    dec a
    jr nz, .mk
.added:
    ld a, e
    add l
    ld e, a
    ld a, d
    adc h
    ld d, a
    ld a, b
    adc 0
    ld b, a
    pop hl
.shift:
    sra b
    rr d
    rr e
    dec c
    jr nz, .shift
    ret

; Sat8: b:d:e signed 24-bit -> a clamped to [-127, 127]. Preserves all else.
Sat8::
    ld a, b
    or d
    jr nz, .notpos
    ld a, e
    cp 128
    ret c
    ld a, 127
    ret
.notpos:
    ld a, b
    and d
    inc a
    jr nz, .far          ; b,d not both $FF
    ld a, e
    cp $81
    ret nc
    ld a, $81
    ret
.far:
    bit 7, b
    ld a, 127
    ret z
    ld a, $81
    ret

; RequantAcc: c = shift. a = sat8(round_shift(acc, c)). Clobbers b, c, d, e.
RequantAcc::
    call RsAcc
    jr Sat8

; SatAdd: hl -> a[], de -> b[], bc -> out[], all MODEL_D long. out = sat8(a + b). Clobbers everything.
SatAdd::
    ld a, MODEL_D
    ldh [hLoop], a
.loop:
    ld a, [de]
    inc de
    push de
    ld e, a
    rlca
    sbc a
    ld d, a              ; de = sign-extended b
    ld a, [hl+]
    push hl
    ld l, a
    rlca
    sbc a
    ld h, a              ; hl = sign-extended a
    add hl, de
    ; clamp hl
    ld a, h
    or a
    jr nz, .neg
    ld a, l
    cp 128
    jr c, .store
    ld a, 127
    jr .store
.neg:
    ld a, h
    inc a
    ld a, l
    jr nz, .bigneg       ; h is neither 0 nor $FF cannot occur for int8 sums, kept for safety
    cp $81
    jr nc, .store
.bigneg:
    ld a, $81
.store:
    ld [bc], a
    inc bc
    pop hl
    pop de
    ldh a, [hLoop]
    dec a
    ldh [hLoop], a
    jr nz, .loop
    ret

SECTION "quant_hram", HRAM
hLoop:: ds 1
