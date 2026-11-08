; Minimal DMG ROM: known instruction sequence used for boot smoke and cycle calibration.
SECTION "hdr", ROM0[$100]
    nop
    jp Start
    ds $150 - @, 0
SECTION "main", ROM0[$150]
Start::
    di
    ld sp, $DFFF
Mark0::
    nop              ; 4
    ld a, 1          ; 8
    ld hl, $C000     ; 12
    ld [hl+], a      ; 8
    ld a, [hl]       ; 8
    add a            ; 4
    push hl          ; 16
    pop hl           ; 12
    call Fn          ; 24 + 16
Mark1::
    nop
Done::
    jr Done
Fn:
    ret
