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
DEF rBGP   EQU $FF47
DEF rOBP0  EQU $FF48
DEF rOBP1  EQU $FF49
DEF rWY    EQU $FF4A
DEF rWX    EQU $FF4B
DEF rIE    EQU $FFFF
DEF rNR52  EQU $FF26

DEF MBC5_ROMB0 EQU $2000

DEF LCDC_ON    EQU %10010011   ; LCD on, BG on, OBJ on, tiles at $8000, map $9800
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

; Tile index layout (LCDC.4=1: unsigned from $8000)
DEF TILE_UI        EQU 96
DEF TILE_RULE      EQU TILE_UI+0
DEF TILE_HEART     EQU TILE_UI+1
DEF TILE_KEY       EQU TILE_UI+2
DEF TILE_LAMP      EQU TILE_UI+3
DEF TILE_BAND      EQU TILE_UI+4
DEF TILE_BAR0      EQU TILE_UI+5    ; +0..+4 = 0/4..4/4 filled
DEF TILE_CURSOR    EQU TILE_UI+10
DEF TILE_ARROW     EQU TILE_UI+11
DEF TILE_SPIN0     EQU TILE_UI+12
DEF TILE_SPIN1     EQU TILE_UI+13
DEF TILE_CHIP      EQU TILE_UI+14
DEF TILE_SWORD     EQU TILE_UI+16
DEF TILE_FRIEND    EQU TILE_UI+17
DEF TILE_RING      EQU TILE_UI+18
DEF TILE_INV       EQU 116
DEF TILE_ART       EQU 156

; Screen layout, rows of the 20x18 background
DEF SCREEN_W    EQU 20
DEF SCREEN_H    EQU 18
DEF BAND_ROW    EQU 6
DEF BODY_ROW    EQU 7     ; rows 7..16 belong to whichever screen is showing
DEF BODY_ROWS   EQU 10
DEF TEXT_ROW    EQU 8     ; story lines sit on every other row, like the text boxes of the era
DEF TEXT_ROWS   EQU 4
DEF TEXT_COL    EQU 1
DEF TEXT_WIDTH  EQU 18
DEF HINT_ROW    EQU 16
DEF STATUS_ROW  EQU 17

; UX state machine values, mirrored to the debug mailbox
DEF ST_BOOT       EQU 0
DEF ST_TITLE      EQU 1
DEF ST_INTRO      EQU 2
DEF ST_MENU       EQU 3
DEF ST_PREFILL    EQU 4
DEF ST_GENERATING EQU 5
DEF ST_REVEAL     EQU 6
DEF ST_UPDATE     EQU 7
DEF ST_ENDING     EQU 8
DEF ST_STATS      EQU 9
DEF ST_ERROR      EQU 10

; Switch the $4000 window. Clobbers a. Counts every switch for instrumentation.
MACRO SWITCH_BANK ; \1 = bank value or register-loadable operand
    ld a, \1
    call BankSwitch
ENDM

ENDC
