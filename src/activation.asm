; activation.asm - ReLU over a vector.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "activation_code", ROM0
; Relu: hl -> vec, b = length. In place, values below zero become 0. Clobbers a, b, hl.
Relu::
    ld a, [hl]
    bit 7, a
    jr z, .keep
    xor a
    ld [hl], a
.keep:
    inc hl
    dec b
    jr nz, Relu
    ret
