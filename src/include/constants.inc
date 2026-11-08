; Hardware registers and project-wide constants. Written for this project from Pan Docs.
IF !DEF(CONSTANTS_INC)
DEF CONSTANTS_INC EQU 1

DEF rP1    EQU $FF00
DEF rDIV   EQU $FF04
DEF rIF    EQU $FF0F
DEF rLCDC  EQU $FF40
DEF rSTAT  EQU $FF41
DEF rSCY   EQU $FF42
DEF rSCX   EQU $FF43
DEF rLY    EQU $FF44
DEF rDMA   EQU $FF46
DEF rBGP   EQU $FF47
DEF rOBP0  EQU $FF48
DEF rOBP1  EQU $FF49
DEF rWY    EQU $FF4A
DEF rWX    EQU $FF4B
DEF rIE    EQU $FFFF
DEF rNR21  EQU $FF16
DEF rNR22  EQU $FF17
DEF rNR23  EQU $FF18
DEF rNR24  EQU $FF19
DEF rNR50  EQU $FF24
DEF rNR51  EQU $FF25
DEF rNR52  EQU $FF26

DEF MBC5_RAMG  EQU $0000
DEF MBC5_ROMB0 EQU $2000
DEF MBC5_RAMB  EQU $4000

DEF LCDC_ON    EQU %10000111   ; LCD on, BG on, OBJ on, 8x16 sprites, BG tiles at $9000/$8800, map $9800
DEF PAL_NORMAL EQU %11100100
DEF OBJ_PAL    EQU %11100100

; Joypad bits in hJoyHeld / hJoyPressed
DEF PAD_A      EQU 0
DEF PAD_B      EQU 1
DEF PAD_SELECT EQU 2
DEF PAD_START  EQU 3
DEF PAD_RIGHT  EQU 4
DEF PAD_LEFT   EQU 5
DEF PAD_UP     EQU 6
DEF PAD_DOWN   EQU 7

; Background tiles: 0-127 at $9000, 128-255 at $8800. Sprites use $8000-$87FF alone.
DEF TILE_UI        EQU 96
DEF TILE_RULE      EQU TILE_UI+0
DEF TILE_BAND      EQU TILE_UI+4
DEF TILE_BAR0      EQU TILE_UI+5    ; +0..+4 = 0/4..4/4 filled
DEF TILE_CURSOR    EQU TILE_UI+10
DEF TILE_ARROW     EQU TILE_UI+11
DEF TILE_CARET     EQU TILE_UI+20
DEF TILE_INV       EQU 128
DEF TILE_LOGO      EQU 168

; Screen layout, rows of the 20x18 background. The robot covers rows 0-7 at the left.
DEF SCREEN_W    EQU 20
DEF SCREEN_H    EQU 18
DEF BAND_ROW    EQU 8
DEF TEXT_ROW    EQU 10    ; dialogue lines sit on every other row, clear of the band above
DEF TEXT_ROWS   EQU 4
DEF TEXT_COL    EQU 1
DEF TEXT_WIDTH  EQU 18
DEF HINT_ROW    EQU 17

; UX state machine values, mirrored to the debug mailbox
DEF ST_BOOT       EQU 0
DEF ST_INTRO      EQU 1
DEF ST_MENU       EQU 2
DEF ST_KEYBOARD   EQU 3
DEF ST_THINKING   EQU 4
DEF ST_STREAMING  EQU 5
DEF ST_READ       EQU 6
DEF ST_INSPECT    EQU 7
DEF ST_POWERDOWN  EQU 8
DEF ST_ERROR      EQU 10
DEF ST_SELFTEST_DONE EQU 11

; Switch the $4000 window. Clobbers a. Counts every switch for instrumentation.
MACRO SWITCH_BANK ; \1 = bank value or register-loadable operand
    ld a, \1
    call BankSwitch
ENDM

ENDC
