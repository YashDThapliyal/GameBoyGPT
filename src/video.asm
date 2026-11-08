; video.asm - VBlank ISR, shadow background map, tile loading, text primitives.
; Screen writes go to a WRAM shadow. The ISR uploads dirty rows so inference never waits on the PPU.
INCLUDE "constants.inc"

DEF UPLOAD_ROWS_PER_VBLANK EQU 4 ; ~640 T each; more than 4 can overrun mode 1 (4560 T) with the scan and OAM copy

SECTION "video_vars", WRAM0
wBgMap::    ds SCREEN_W * SCREEN_H
wDirty::    ds SCREEN_H

SECTION "oam_shadow", WRAM0, ALIGN[8]
wOam::      ds 160           ; robot 0-31, cursor 32

SECTION "video_hram", HRAM
hDirtyAny:: ds 1
hFrames::   ds 2             ; free-running LCD frame counter
hVbFlag::   ds 1
hOamDirty:: ds 1
hDmaRoutine:: ds 8           ; OAM DMA must run from HRAM: the CPU cannot read ROM or WRAM during the transfer

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
    ; A row with interrupts held off can delay this ISR past mode 1, so VRAM and OAM are only touched
    ; while LY says there is room. Dirty rows and sprites simply wait for the next frame.
    ldh a, [rLY]
    cp 144
    jr c, .anim
    cp 148
    jr nc, .anim
    ldh a, [hOamDirty]
    or a
    jr z, .rows
    xor a
    ldh [hOamDirty], a
    ld a, HIGH(wOam)
    call hDmaRoutine
.rows:
    ldh a, [hDirtyAny]
    or a
    jr z, .anim
    ld hl, wDirty
    ld c, 0
    ld b, UPLOAD_ROWS_PER_VBLANK
.scan:
    ld a, [hl]
    or a
    jr z, .next
    ldh a, [rLY]
    cp 150
    jr nc, .anim
    xor a
    ld [hl], a
    push hl
    call UploadRow
    pop hl
    dec b
    jr z, .anim          ; budget spent: remaining rows wait for next VBlank
.next:
    inc hl
    inc c
    ld a, c
    cp SCREEN_H
    jr nz, .scan
    xor a
    ldh [hDirtyAny], a
.anim:
    call AnimTick        ; after the uploads: a rebuild costs more than VBlank has left, and shows next frame
    call ReadJoypad
    ld a, 1
    ldh [hVbFlag], a
    pop hl
    pop de
    pop bc
    pop af
    reti

; Copied to hDmaRoutine. a = source page.
DmaTemplate:
    ldh [rDMA], a
    ld a, 40
.w:
    dec a
    jr nz, .w
    ret
DmaTemplateEnd:

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

; VideoInit: LCD must be off. Loads font, UI, inverse font and robot tiles, clears map and sprites, enables VBlank.
VideoInit::
    ld hl, DmaTemplate
    ld de, hDmaRoutine
    ld bc, DmaTemplateEnd - DmaTemplate
    call MemCopy
    ld a, BANK(FontTiles)
    call BankSwitch
    ld hl, FontTiles
    ld de, $9000
    ld bc, TILE_INV * 16
    call MemCopy
    ld de, $8800         ; hl continues into the inverse font
    ld bc, (TILE_LOGO - TILE_INV) * 16
    call MemCopy
    ld a, BANK(RobotTiles)
    call BankSwitch
    ld hl, RobotTiles
    ld de, $8000
    ld bc, RobotTilesEnd - RobotTiles
    call MemCopy
    ld a, BANK(LogoTiles)
    call BankSwitch
    ld hl, LogoTilesLow
    ld de, $9000 + 64 * 16
    ld bc, LogoTiles - LogoTilesLow
    call MemCopy
    ld hl, LogoTiles
    ld de, $8800 + (TILE_LOGO - TILE_INV) * 16
    ld bc, LogoTilesEnd - LogoTiles
    call MemCopy
    ld a, PAL_NORMAL
    ldh [rBGP], a
    ld a, OBJ_PAL
    ldh [rOBP0], a
    ldh [rOBP1], a
    xor a
    ldh [rSCX], a
    ldh [rSCY], a
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
    ld b, 160
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
    ld a, 1
    ldh [hOamDirty], a
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

; PrintDec16: de = value, hl = shadow ptr. Five digits, advances hl. Clobbers a, bc, de.
PrintDec16::
    ld bc, -10000
    call .digit
    ld bc, -1000
    call .digit
    ld bc, -100
    call .digit
    ld bc, -10
    call .digit
    ld bc, -1
.digit:
    ld a, -1
    push hl
    ld h, d
    ld l, e
.sub:
    inc a
    ld d, h
    ld e, l
    add hl, bc
    jr c, .sub
    pop hl
    add '0' - $20
    ld [hl+], a
    ret

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
