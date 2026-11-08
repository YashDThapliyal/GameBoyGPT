; matvec.asm - signed multiply and dot/matrix-vector kernels.
; V0 baseline: readable shift-and-add multiply, one call per MAC, generic 24-bit accumulation.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "matvec_vars", WRAM0
wMvBank:   ds 1
wMvPtr:    ds 2
wMvRows:   ds 1
wMvCols:   ds 1
wMvShift:  ds 1
wMvX:      ds 2
wMvY:      ds 2

SECTION "matvec_code", ROM0
; MulS8: a * c signed -> hl. Inputs in [-127,127]. Clobbers a, b, c, d, e.
MulS8::
    ld d, a
    xor c
    push af              ; sign in bit 7
    ld a, d
    bit 7, a
    jr z, .apos
    cpl
    inc a
.apos:
    ld e, a
    ld d, 0              ; de = |a|
    ld a, c
    bit 7, a
    jr z, .cpos
    cpl
    inc a
.cpos:
    ld c, a              ; c = |c|
    ld hl, 0
    ld b, 8
.bit:
    add hl, hl
    sla c
    jr nc, .skip
    add hl, de
.skip:
    dec b
    jr nz, .bit
    pop af
    bit 7, a
    ret z
    ld a, l              ; negate hl
    cpl
    ld l, a
    ld a, h
    cpl
    ld h, a
    inc hl
    ret

; ClearAcc: zero the accumulator. Clobbers a.
ClearAcc::
    xor a
    ldh [hAcc], a
    ldh [hAcc + 1], a
    ldh [hAcc + 2], a
    ret


; Dot: hl -> a[], de -> b[], b = count. hAcc = sum a[i]*b[i]. Returns hl, de advanced. Clobbers a, bc.
Dot::
    xor a
    ldh [hAcc], a
    ldh [hAcc + 1], a
    ldh [hAcc + 2], a
.loop:
    ld a, [hl+]
    ld c, a
    ld a, [de]
    inc de
    push hl
    push de
    push bc
    call MulS8
    ; 24-bit add of sign-extended product
    ld a, h
    rlca
    sbc a                ; a = $00 or $FF
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
    pop bc
    pop de
    pop hl
    dec b
    jr nz, .loop
    ret

; LoadTensor: hl -> tensor descriptor {bank, addr, rows, cols, shift}. Loads wMv* fields.
LoadTensor::
    ld a, [hl+]
    ld [wMvBank], a
    ld a, [hl+]
    ld [wMvPtr], a
    ld a, [hl+]
    ld [wMvPtr + 1], a
    ld a, [hl+]
    ld [wMvRows], a
    ld a, [hl+]
    ld [wMvCols], a
    ld a, [hl]
    ld [wMvShift], a
    ret

; MatVec: hl -> tensor, de -> x[], bc -> y[]. y = sat8(round_shift(W x, shift)). Clobbers everything.
MatVec::
    push bc
    push de
    call LoadTensor
    pop de
    pop bc
    ld a, e
    ld [wMvX], a
    ld a, d
    ld [wMvX + 1], a
    ld a, c
    ld [wMvY], a
    ld a, b
    ld [wMvY + 1], a
.row:
    ld a, [wMvBank]
    call BankSwitch
    call DotRow
    ld a, [wMvShift]
    ld c, a
    call RequantAcc
    ld c, a
    ld hl, wMvY
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld [hl], c
    inc hl
    ld a, l
    ld [wMvY], a
    ld a, h
    ld [wMvY + 1], a
    ld hl, wMvRows
    dec [hl]
    jr nz, .row
    ret

; DotRow: dot of the row at wMvPtr with wMvX; advances wMvPtr. Bank must be selected.
DotRow::
    ld hl, wMvPtr
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, [wMvX]
    ld e, a
    ld a, [wMvX + 1]
    ld d, a
    ld a, [wMvCols]
    ld b, a
    call Dot
    ld a, l
    ld [wMvPtr], a
    ld a, h
    ld [wMvPtr + 1], a
    ret
