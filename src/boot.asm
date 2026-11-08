; boot.asm - vectors, cartridge header, hardware init, entry dispatch.
INCLUDE "constants.inc"

SECTION "vec_vblank", ROM0[$40]
    jp VBlankIsr
SECTION "vec_stat", ROM0[$48]
    reti
SECTION "vec_timer", ROM0[$50]
    reti
SECTION "vec_serial", ROM0[$58]
    reti
SECTION "vec_joypad", ROM0[$60]
    reti

SECTION "header", ROM0[$100]
    nop
    jp Boot
    ds $150 - @, 0          ; rgbfix fills logo, title, MBC, checksums

SECTION "boot", ROM0
Boot::
    di
    ld sp, wStackTop
    call WaitLcdOff
    xor a
    ldh [rNR52], a          ; APU off: no audio in this build, saves battery on real units
    ; Clear WRAM ($C000-$DFFF) and HRAM
    ld hl, $C000
    ld bc, $2000
.clr:
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .clr
    ld hl, $FF80
    ld b, $7F
    xor a
.clrh:
    ld [hl+], a
    dec b
    jr nz, .clrh
    ld a, 1
    call BankSwitch
    call DebugInit
IF DEF(TEST_ROM)
    jp TestMain
ELSE
    call VideoInit
    jp GameMain
ENDC

SECTION "stack", WRAM0[$DE00]
wStackBottom:: ds $100
wStackTop::
