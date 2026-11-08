; video.asm - VBlank ISR, shadow background map, tile loading, text primitives.
; Screen writes go to a WRAM shadow. The ISR uploads dirty rows so inference never waits on the PPU.
INCLUDE "constants.inc"

DEF UPLOAD_ROWS_PER_VBLANK EQU 4 ; ~640 T each; more than 4 can overrun mode 1 (4560 T) with the scan and OAM copy

SECTION "video_vars", WRAM0
wBgMap::    ds SCREEN_W * SCREEN_H
wDirty::    ds SCREEN_H
wOam::      ds 8             ; two sprites: cursor, spinner

SECTION "video_hram", HRAM
hDirtyAny:: ds 1
hFrames::   ds 2             ; free-running LCD frame counter
hVbFlag::   ds 1
hSpin::     ds 1             ; nonzero animates the spinner sprite

SECTION "isr", ROM0
VBlankIsr::
    push af
    push bc
    push de
    push hl
    ld hl, hFrames
    inc [hl]
    jr nz, .nocarry
    inc hl
    inc [hl]
.nocarry:
IF DEF(SP_STREAM)
    ; A row with interrupts held off can delay this ISR past mode 1, so VRAM and OAM are only touched
    ; while LY says there is room. Dirty rows simply wait for the next frame.
    ldh a, [rLY]
    cp 144
    jr c, .joy
    cp 148
    jr nc, .joy
ENDC
    ldh a, [hDirtyAny]
    or a
    jr z, .oam
    ld hl, wDirty
    ld c, 0
    ld b, UPLOAD_ROWS_PER_VBLANK
.scan:
    ld a, [hl]
    or a
    jr z, .next
IF DEF(SP_STREAM)
    ldh a, [rLY]
    cp 150
    jr nc, .joy
ENDC
    xor a
    ld [hl], a
    push hl
    call UploadRow
    pop hl
    dec b
    jr z, .oam           ; budget spent: remaining rows wait for next VBlank
.next:
    inc hl
    inc c
    ld a, c
    cp SCREEN_H
    jr nz, .scan
    xor a
    ldh [hDirtyAny], a
.oam:
    ld hl, wOam
    ld de, $FE00
    REPT 8
    ld a, [hl+]
    ld [de], a
    inc e
    ENDR
    ldh a, [hSpin]
    or a
    jr z, .joy
    ldh a, [hFrames]
    and 8
    ld a, TILE_SPIN0
    jr z, .s0
    inc a
.s0:
    ld [wOam + 6], a
.joy:
    call ReadJoypad
    ld a, 1
    ldh [hVbFlag], a
    pop hl
    pop de
    pop bc
    pop af
    reti

; UploadRow: c = row. Clobbers a, de, hl. 20 tiles in about 400 T-cycles.
UploadRow:
    ld h, 0
    ld l, c
    add hl, hl
    add hl, hl
    ld d, h
    ld e, l
    add hl, hl
    add hl, hl
    add hl, de           ; hl = row * 20
    ld de, wBgMap
    add hl, de
    push hl
    ld h, 0
    ld l, c
    REPT 5
    add hl, hl
    ENDR
    ld de, $9800
    add hl, de
    ld d, h
    ld e, l              ; de = $9800 + row * 32
    pop hl
    REPT SCREEN_W
    ld a, [hl+]
    ld [de], a
    inc e
    ENDR
    ret

SECTION "video_code", ROM0
; WaitLcdOff: turns the LCD off during VBlank if it is on. Clobbers a.
WaitLcdOff::
    ldh a, [rLCDC]
    bit 7, a
    ret z
.w:
    ldh a, [rLY]
    cp 144
    jr c, .w
    xor a
    ldh [rLCDC], a
    ret

; WaitVBlank: sleeps until the next VBlank ISR has run. Clobbers a.
WaitVBlank::
    xor a
    ldh [hVbFlag], a
.h:
    halt
    ldh a, [hVbFlag]
    or a
    jr z, .h
    ret

; WaitFrames: b = frames. Clobbers a, b.
WaitFrames::
    call WaitVBlank
    dec b
    jr nz, WaitFrames
    ret

; MemCopy: hl=src de=dst bc=len. Clobbers a, bc, de, hl.
MemCopy::
    inc b
    inc c
    jr .test
.loop:
    ld a, [hl+]
    ld [de], a
    inc de
.test:
    dec c
    jr nz, .loop
    dec b
    jr nz, .loop
    ret

; VideoInit: LCD must be off. Loads font/UI/inverse tiles, clears map, enables VBlank.
VideoInit::
    ld hl, FontTiles
    ld de, $8000
    ld bc, 120 * 16      ; font + UI + inverse font are contiguous in ROM0
    call MemCopy
    ld a, PAL_NORMAL
    ldh [rBGP], a
    ld a, OBJ_PAL
    ldh [rOBP0], a
    ldh [rOBP1], a
    xor a
    ldh [rSCX], a
    ldh [rSCY], a
    ; hide all OAM entries
    ld hl, $FE00
    ld b, 160
.oam:
    ld [hl+], a
    dec b
    jr nz, .oam
    call ClearShadow
    call UploadAllNow
    ld a, 1
    ldh [rIE], a
    xor a
    ldh [rIF], a
    ld a, LCDC_ON
    ldh [rLCDC], a
    ei
    ret

; ClearShadow: blanks the whole shadow map and sprites.
ClearShadow::
    ld hl, wBgMap
    ld bc, SCREEN_W * SCREEN_H
.c:
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .c
    ld hl, wOam
    ld b, 8
.o:
    ld [hl+], a
    dec b
    jr nz, .o
    ret

; UploadAllNow: LCD off only. Copies the shadow to VRAM and clears dirty flags.
UploadAllNow::
    ld c, 0
.r:
    call UploadRow
    inc c
    ld a, c
    cp SCREEN_H
    jr nz, .r
    ld hl, wDirty
    ld b, SCREEN_H
    xor a
.d:
    ld [hl+], a
    dec b
    jr nz, .d
    ldh [hDirtyAny], a
    ret

; ScreenOff / ScreenOn bracket full-screen rebuilds with a short palette fade.
ScreenOff::
    ld a, %11111001
    ldh [rBGP], a
    ld b, 3
    call WaitFrames
    ld a, %11111110
    ldh [rBGP], a
    ld b, 3
    call WaitFrames
    ld a, %11111111
    ldh [rBGP], a
    call WaitVBlank
    di
    jp WaitLcdOff         ; re-checks LY: disabling the LCD outside VBlank can damage a real DMG screen

ScreenOn::
    call UploadAllNow
    ld hl, wOam
    ld de, $FE00
    ld b, 8
.o:
    ld a, [hl+]
    ld [de], a
    inc e
    dec b
    jr nz, .o
    xor a
    ldh [rIF], a
    ld a, LCDC_ON
    ldh [rLCDC], a
    ei
    ld a, %11111110
    ldh [rBGP], a
    ld b, 3
    call WaitFrames
    ld a, %11111001
    ldh [rBGP], a
    ld b, 3
    call WaitFrames
    ld a, PAL_NORMAL
    ldh [rBGP], a
    ret

; LoadArt: LCD off. hl -> {db bank, count; dw tiles, map}; b = map rows to install from row 0.
; Tiles load at TILE_ART. Clobbers everything.
LoadArt::
    ld a, [hl+]
    push bc
    call BankSwitch
    ld a, [hl+]          ; tile count
    ld c, a
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a              ; de = tiles
    ld a, [hl+]
    ld b, [hl]
    push af              ; low byte of map
    push bc              ; b = high byte of map, c = count
    ; copy count*16 bytes
    ld h, d
    ld l, e
    ld de, $8000 + TILE_ART * 16
    ld b, 0
    REPT 4
    sla c
    rl b
    ENDR
    call MemCopy
    pop bc
    pop af
    ld l, a
    ld h, b              ; hl = map
    pop bc               ; b = rows
    ld de, wBgMap
.rows:
    ld c, SCREEN_W
.cols:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .cols
    dec b
    jr nz, .rows
    ret

; RowPtr: b=row c=col -> hl = shadow pointer. Clobbers a, de.
RowPtr::
    ld h, 0
    ld l, b
    add hl, hl
    add hl, hl
    ld d, h
    ld e, l
    add hl, hl
    add hl, hl
    add hl, de
    ld de, wBgMap
    add hl, de
    ld e, c
    ld d, 0
    add hl, de
    ret

; MarkRow: b = row. Preserves all registers except flags.
MarkRow::
    push af
    push hl
    ld h, HIGH(wDirty)
    ld a, LOW(wDirty)
    add b
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld [hl], 1
    ld a, 1
    ldh [hDirtyAny], a
    pop hl
    pop af
    ret

; FillRows: b=first row, c=row count, a=tile. Clobbers a, bc, de, hl.
FillRows::
    ld d, a
.r:
    push bc
    push de
    ld c, 0
    call RowPtr
    pop de
    ld a, d
    ld e, SCREEN_W
.t:
    ld [hl+], a
    dec e
    jr nz, .t
    call MarkRow
    pop bc
    inc b
    dec c
    jr nz, .r
    ret

; PrintAt: hl=NUL string (ROM0), b=row, c=col. Normal ink. Clobbers a, de, hl. Preserves bc.
PrintAt::
    push hl
    call RowPtr
    pop de
.l:
    ld a, [de]
    or a
    jr z, .e
    sub $20
    ld [hl+], a
    inc de
    jr .l
.e:
    jp MarkRow

; PrintInvAt: as PrintAt but with the inverse (light on dark) font.
PrintInvAt::
    push hl
    call RowPtr
    pop de
.l:
    ld a, [de]
    or a
    jr z, .e
    push hl
    sub $20
    ld hl, InvMap
    add l
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld a, [hl]
    pop hl
    ld [hl+], a
    inc de
    jr .l
.e:
    jp MarkRow

; PrintDec2: a=0..99, hl=shadow ptr; advances hl. tile font. Clobbers a, b.
PrintDec2::
    ld b, 0
.t:
    cp 10
    jr c, .u
    sub 10
    inc b
    jr .t
.u:
    push af
    ld a, b
    add '0' - $20
    ld [hl+], a
    pop af
    add '0' - $20
    ld [hl+], a
    ret
