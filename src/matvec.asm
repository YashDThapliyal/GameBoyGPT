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
wMvEntry:  ds 2

SECTION "matvec_code", ROM0
; MulS8: a * c signed -> hl. Inputs in [-127,127]. Clobbers a, b, c, d, e.
MulS8::
IF DEF(MUL_QSQ)
    ; ab = q(a+b) - q(a-b), q(n) = floor(n^2/4). Biased inputs make the 9-bit sum a page select by carry.
    xor $80
    ld b, a
    ld a, c
    xor $80
    ld c, a
    add b
    ld l, a
    ld a, HIGH(QTab)
    adc 0
    ld h, a
    ld e, [hl]
    inc h
    inc h
    ld d, [hl]
    ld a, b
    sub c
    ld l, a
    ld a, HIGH(QTab) + 1
    sbc 0
    ld h, a
    ld a, e
    sub [hl]
    ld e, a
    inc h
    inc h
    ld a, d
    sbc [hl]
    ld h, a
    ld l, e
    ret
ELIF DEF(MUL_NIBBLE)
    ; |a| * |c| = T[|a|][c_hi] << 4 + T[|a|][c_lo]. 4 KiB table, one entry per (7-bit, 4-bit) pair.
    ld d, a
    xor c
    push af
    ld a, d
    bit 7, a
    jr z, .apos
    cpl
    inc a
.apos:
    ld d, a              ; |a|
    ld a, c
    bit 7, a
    jr z, .cpos
    cpl
    inc a
.cpos:
    ld c, a              ; |c|
    ; h = base + (|a| >> 4), l = (|a| << 4) | n
    ld a, d
    swap a
    ld d, a
    and $0F
    add HIGH(NibTab)
    ld h, a
    ld a, d
    and $F0
    ld e, a              ; e = |a| low nibble << 4
    ld a, c
    swap a
    and $0F              ; c_hi
    or e
    ld l, a
    ld b, [hl]           ; low byte of the high-nibble product
    ld d, h              ; save page
    ld a, h
    add 8
    ld h, a
    ld h, [hl]
    ld l, b              ; hl = T[|a|][c_hi]
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    push hl
    ld h, d
    ld a, c
    and $0F
    or e
    ld l, a
    ld b, [hl]
    ld a, h
    add 8
    ld h, a
    ld d, [hl]
    ld e, b              ; de = T[|a|][c_lo]
    pop hl
    add hl, de
    pop af
    bit 7, a
    ret z
    ld a, l
    cpl
    ld l, a
    ld a, h
    cpl
    ld h, a
    inc hl
    ret
ELSE
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
ENDC

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

IF DEF(FAST_DOT)
; ---- Fused dot kernels: inlined quarter-square MAC, x held biased in HRAM, biased weights in ROM ----
; One unrolled block per element so the x address is an immediate. Weight stream in bc, acc in hAcc+2:d:e.
SECTION "fast_hram", HRAM
hXb:: ds 64                 ; biased x, end-aligned: x[0] at hXb + 64 - n

SECTION "fast_code", ROM0
MACRO QMAC                  ; \1 = x slot; \2 = 1 if the stream holds raw signed values
    ld a, [bc]
    IF \2
    xor $80
    ENDC
    ld l, a
    ldh a, [hXb + \1]
    add l
    ld l, a
    ld a, HIGH(QTab)
    adc 0
    ld h, a
    ld a, [hl]
    add e
    ld e, a
    inc h
    inc h
    ld a, [hl]
    adc d
    ld d, a
    jr nc, :+
    ldh a, [hAcc + 2]
    inc a
    ldh [hAcc + 2], a
:
    ld a, [bc]
    IF \2
    xor $80
    ENDC
    ld l, a
    ldh a, [hXb + \1]
    sub l
    ld l, a
    ld a, HIGH(QTab) + 1
    sbc 0
    ld h, a
    ld a, e
    sub [hl]
    ld e, a
    inc h
    inc h
    ld a, d
    sbc [hl]
    ld d, a
    jr nc, :+
    ldh a, [hAcc + 2]
    dec a
    ldh [hAcc + 2], a
:
    inc bc
ENDM

IF DEF(SP_STREAM)
; Weight stream through SP: pop reads two biased weights in 12 T and keeps both in registers, so each is
; loaded once instead of twice. Interrupts are held off for the row only, and nothing is ever pushed while
; SP points into ROM. An interrupt arriving mid-row is serviced by the ei at the row's end.
MACRO QMACS                 ; \1 = x slot; \2 = register holding the weight
    ldh a, [hXb + \1]
    add \2
    ld l, a
    ld a, HIGH(QTab)
    adc 0
    ld h, a
    ld a, [hl]
    add e
    ld e, a
    inc h
    inc h
    ld a, [hl]
    adc d
    ld d, a
    jr nc, :+
    ldh a, [hAcc + 2]
    inc a
    ldh [hAcc + 2], a
:
    ldh a, [hXb + \1]
    sub \2
    ld l, a
    ld a, HIGH(QTab) + 1
    sbc 0
    ld h, a
    ld a, e
    sub [hl]
    ld e, a
    inc h
    inc h
    ld a, d
    sbc [hl]
    ld d, a
    jr nc, :+
    ldh a, [hAcc + 2]
    dec a
    ldh [hAcc + 2], a
:
ENDM

SECTION "sp_vars", WRAM0
wSaveSP: ds 2

SECTION "sp_code", ROM0
; DotEnter: hl = DotW* entry, bc -> weights, d=e=hAcc+2=0. -> hAcc = sum, bc advanced.
DotEnter::
    di
    ld [wSaveSP], sp
    ld d, h
    ld e, l
    ld h, b
    ld l, c
    ld sp, hl
    ld h, d
    ld l, e
    ld de, 0
    jp hl

IF DEF(ZERO_SKIP)
; ReLU leaves most of the 64-wide input at exactly zero, and x = 0 makes every product zero. The biased
; zero is $80, so each block tests that first and skips its two table lookups. Only the 64-wide kernel
; pays for the test: the narrower vectors are rarely zero.
MACRO QMACZ                 ; \1 = x slot; \2 = register holding the weight
    ldh a, [hXb + \1]
    cp $80
    jr z, .skip\@
    add \2
    ld l, a
    ld a, HIGH(QTab)
    adc 0
    ld h, a
    ld a, [hl]
    add e
    ld e, a
    inc h
    inc h
    ld a, [hl]
    adc d
    ld d, a
    jr nc, :+
    ldh a, [hAcc + 2]
    inc a
    ldh [hAcc + 2], a
:
    ldh a, [hXb + \1]
    sub \2
    ld l, a
    ld a, HIGH(QTab) + 1
    sbc 0
    ld h, a
    ld a, e
    sub [hl]
    ld e, a
    inc h
    inc h
    ld a, d
    sbc [hl]
    ld d, a
    jr nc, .skip\@
    ldh a, [hAcc + 2]
    dec a
    ldh [hAcc + 2], a
.skip\@:
ENDM

DotW64::
    FOR I, 0, 64, 2
    pop bc
    QMACZ I, c
    QMACZ I + 1, b
    ENDR
    jp DotFinish
DotW32::
    FOR I, 32, 48, 2
    pop bc
    QMACS I, c
    QMACS I + 1, b
    ENDR
ELSE
DotW64::
    FOR I, 0, 32, 2
    pop bc
    QMACS I, c
    QMACS I + 1, b
    ENDR
DotW32::
    FOR I, 32, 48, 2
    pop bc
    QMACS I, c
    QMACS I + 1, b
    ENDR
ENDC
DotW16::
    FOR I, 48, 52, 2
    pop bc
    QMACS I, c
    QMACS I + 1, b
    ENDR
DotW12::
    FOR I, 52, 56, 2
    pop bc
    QMACS I, c
    QMACS I + 1, b
    ENDR
DotW8::
    FOR I, 56, 64, 2
    pop bc
    QMACS I, c
    QMACS I + 1, b
    ENDR
DotFinish:
    ld hl, sp + 0
    ld b, h
    ld c, l              ; bc = next weight
    ld a, e
    ldh [hAcc], a
    ld a, d
    ldh [hAcc + 1], a
    ld a, [wSaveSP]
    ld l, a
    ld a, [wSaveSP + 1]
    ld h, a
    ld sp, hl
    ei
    ret
ELSE
; DotEnter: hl = DotW* entry. Same contract as the SP form, without touching IME.
DotEnter::
    jp hl

; DotW64/32/16: bc -> biased weights, hXb end-aligned. -> hAcc = sum. bc advanced. Clobbers a, de, hl.
DotW64::
    FOR I, 0, 32
    QMAC I, 0
    ENDR
DotW32::
    FOR I, 32, 48
    QMAC I, 0
    ENDR
DotW16::
    FOR I, 48, 52
    QMAC I, 0
    ENDR
DotW12::
    FOR I, 52, 56
    QMAC I, 0
    ENDR
DotW8::
    FOR I, 56, 64
    QMAC I, 0
    ENDR
    ld a, e
    ldh [hAcc], a
    ld a, d
    ldh [hAcc + 1], a
    ret
ENDC

; DotRaw16: bc -> raw signed 16 values (keys in WRAM), q already in hXb+48.. -> hAcc.
DotRaw16::
    FOR I, 48, 64
    QMAC I, 1
    ENDR
    ld a, e
    ldh [hAcc], a
    ld a, d
    ldh [hAcc + 1], a
    ret

; LoadXBiased: de -> x[], a = n (<= 64). Copies to the end of hXb with the sign bit flipped. Clobbers a, b, c, de.
LoadXBiased::
    ld b, a
    ld a, LOW(hXb) + 64
    sub b
    ld c, a
.l:
    ld a, [de]
    inc de
    xor $80
    ldh [c], a
    inc c
    dec b
    jr nz, .l
    ret

SECTION "matvec_code2", ROM0
; MatVec: hl -> tensor, de -> x[], bc -> y[]. Same result as the V0 path. Clobbers everything.
MatVec::
    push bc
    push de
    call LoadTensor
    pop de
    ld a, [wMvCols]
    call LoadXBiased
    pop de               ; de = y
    ld a, e
    ld [wMvY], a
    ld a, d
    ld [wMvY + 1], a
    ld a, [wMvBank]
    call BankSwitch
    ld a, [wMvCols]
    call DotEntryFor     ; hl = entry
    ld a, l
    ld [wMvEntry], a
    ld a, h
    ld [wMvEntry + 1], a
    ld a, [wMvPtr]
    ld c, a
    ld a, [wMvPtr + 1]
    ld b, a
.row:
    xor a
    ldh [hAcc + 2], a
    ld d, a
    ld e, a
    ld hl, wMvEntry
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    call DotEnter
    push bc
    ld a, [wMvShift]
    ld c, a
    call RequantAcc
    ld hl, wMvY
    ld c, [hl]
    inc hl
    ld b, [hl]
    ld [bc], a
    inc bc
    ld a, b
    ld [hl-], a
    ld [hl], c
    pop bc
    ld hl, wMvRows
    dec [hl]
    jr nz, .row
    ret

; DotEntryFor: a = n -> hl = dot kernel entry.
DotEntryFor::
    cp 64
    ld hl, DotW64
    ret z
    cp 32
    ld hl, DotW32
    ret z
    ld hl, DotW16
    ret

; DotWStream: for callers streaming their own rows: bc = weights, n set by LoadXBiased.
ELSE
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
ENDC

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
