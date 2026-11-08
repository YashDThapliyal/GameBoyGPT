; robot.asm - the portrait: 32 sprites in 8x16 mode, animated from the VBlank ISR so it stays alive during inference.
; No bank switching here: tables are in ROM0 and tiles were loaded once at boot.
INCLUDE "constants.inc"
INCLUDE "robot.inc"

DEF ROBOT_X EQU 4
DEF ROBOT_Y EQU 0

SECTION "robot_vars", WRAM0
wRobotOn::   ds 1
wExpr::      ds 1            ; EXPR_*
wThink::     ds 1            ; nonzero while the model is working towards its first word
wTalk::      ds 1            ; frames of mouth movement left
wShake::     ds 1            ; frames of horizontal shake left
wGlitch::    ds 1            ; frames of glitch left
wRiseY::     ds 1            ; pixels below the resting position, for the intro
wCursorX::   ds 1            ; sprite 32, 0 hides it
wCursorY::   ds 1
wCursorTile:: ds 1
wBlinkT:     ds 1
wBlinkLeft:  ds 1
wShown:      ds 7            ; eye, mouth, x offset, y offset, row jitter seed, cursor x, cursor y

SECTION "robot_code", ROM0
; RobotReset: neutral face, nothing animating. Clobbers a.
RobotReset::
    xor a
    ld [wExpr], a
    ld [wThink], a
    ld [wTalk], a
    ld [wShake], a
    ld [wGlitch], a
    ld [wRiseY], a
    ld [wCursorX], a
    ld [wBlinkLeft], a
    ld a, 90
    ld [wBlinkT], a
    ld a, $FF
    ld [wShown], a       ; forces a rebuild
    ret

; AnimTick: one frame of animation, from the ISR. Decides what should show and rebuilds the sprites only if it changed.
AnimTick::
    ld a, [wRobotOn]
    or a
    jp z, CursorOnly
    ld a, [wExpr]
    add a
    ld e, a
    ld d, 0
    ld hl, RobotExpr
    add hl, de
    ld a, [hl+]
    ld b, a              ; b = eye
    ld c, [hl]           ; c = mouth
    ld a, [wThink]
    or a
    jr z, .noThink
    ld b, EYE_THINK
.noThink:
    ; blink
    ld hl, wBlinkT
    dec [hl]
    jr nz, .noNewBlink
    ldh a, [rDIV]
    and 127
    add 70
    ld [hl], a
    ld a, 5
    ld [wBlinkLeft], a
.noNewBlink:
    ld a, [wBlinkLeft]
    or a
    jr z, .noBlink
    dec a
    ld [wBlinkLeft], a
    ld a, [wExpr]
    cp EXPR_DEFEATED
    jr z, .noBlink
    ld b, EYE_BLINK
.noBlink:
    ; talking
    ld a, [wTalk]
    or a
    jr z, .noTalk
    dec a
    ld [wTalk], a
    ldh a, [hFrames]
    and 4
    ld c, MOUTH_TALK1
    jr z, .noTalk
    ld c, MOUTH_TALK2
.noTalk:
    ld d, 0              ; d = x offset
    ld e, 0              ; e = jitter seed, nonzero tears rows sideways
    ld a, [wGlitch]
    or a
    jr z, .noGlitch
    dec a
    ld [wGlitch], a
    ld b, EYE_GLITCH
    ld c, MOUTH_GLITCH
    ldh a, [hFrames]
    and 3
    jr nz, .keepSeed
    ldh a, [rDIV]
    or 1
    ld [wShown + 4], a
.keepSeed:
    ld a, [wShown + 4]
    ld e, a
.noGlitch:
    ld a, [wShake]
    or a
    jr z, .noShake
    dec a
    ld [wShake], a
    ldh a, [hFrames]
    and 2
    ld d, 2
    jr z, .noShake
    ld d, -2
.noShake:
    ; slow idle bob
    ldh a, [hFrames + 0]
    and 32
    swap a
    srl a                ; 0 or 1
    ld h, a
    ld a, [wRiseY]
    add h
    ld h, a              ; h = y offset
    ; changed?
    ld a, [wShown]
    cp b
    jr nz, Rebuild
    ld a, [wShown + 1]
    cp c
    jr nz, Rebuild
    ld a, [wShown + 2]
    cp d
    jr nz, Rebuild
    ld a, [wShown + 3]
    cp h
    jr nz, Rebuild
    ld a, e
    or a
    jr nz, Rebuild
    jp CursorOnly

; Rebuild: b eye, c mouth, d x offset, h y offset, e jitter seed. Writes the 32 robot sprites.
Rebuild:
    ld a, b
    ld [wShown], a
    ld a, c
    ld [wShown + 1], a
    ld a, d
    ld [wShown + 2], a
    ld a, h
    ld [wShown + 3], a
    ld a, 1
    ldh [hOamDirty], a
    ; row pointers go on the stack, last row first
    push de
    push hl
    ld hl, RobotRow3
    push hl
    ld l, c
    ld h, 0
    REPT 4
    add hl, hl
    ENDR
    ld de, RobotMouths
    add hl, de
    push hl
    ld l, b
    ld h, 0
    REPT 4
    add hl, hl
    ENDR
    ld de, RobotEyes
    add hl, de
    push hl
    ld hl, RobotRow0
    push hl
    ; stack: row0, row1, row2, row3, y offset in h, jitter+x in de
    ld hl, sp + 8
    ld a, [hl+]          ; skip low of saved hl
    ld a, [hl+]          ; y offset
    add ROBOT_Y + 16
    ld b, a              ; b = sprite y
    ld a, [hl+]
    ld [wRowSeed], a     ; jitter seed
    ld a, [hl]
    ld [wRowX], a        ; x offset
    ld de, wOam
    ld a, 4
.rows:
    ld [wRowsToDo], a
    pop hl               ; this row's cells
    ld a, [wRowX]
    add ROBOT_X + 8
    ld c, a
    ; glitch: tear this row sideways by a little
    ld a, [wRowSeed]
    or a
    jr z, .noTear
    rlca
    ld [wRowSeed], a
    and 7
    sub 3
    add c
    ld c, a
.noTear:
    ld a, 8
.cells:
    push af
    ld a, b
    ld [de], a
    inc e
    ld a, c
    ld [de], a
    inc e
    ld a, [hl+]
    ld [de], a
    inc e
    ld a, [hl+]
    ld [de], a
    inc e
    ld a, c
    add 8
    ld c, a
    pop af
    dec a
    jr nz, .cells
    ld a, b
    add 16
    ld b, a
    ld a, [wRowsToDo]
    dec a
    jr nz, .rows
    pop hl
    pop de
    ; fall through
CursorOnly:
    ld a, [wCursorY]
    ld c, a
    ld a, [wShown + 6]
    cp c
    jr nz, .write
    ld a, [wCursorX]
    ld b, a
    ld a, [wShown + 5]
    cp b
    ret z
.write:
    ld a, [wCursorX]
    ld b, a
    ld [wShown + 5], a
    ld a, c
    ld [wShown + 6], a
    ld hl, wOam + 32 * 4
    ld a, b
    or a
    jr z, .hide
    ld a, c
    ld [hl+], a
    ld a, b
    ld [hl+], a
    ld a, [wCursorTile]
    ld [hl+], a
    xor a
    ld [hl], a
    jr .mark
.hide:
    xor a
    ld [hl+], a
    ld [hl+], a
.mark:
    ld a, 1
    ldh [hOamDirty], a
    ret

; RobotHide: turns all sprites off. Clobbers a, b, hl.
RobotHide::
    xor a
    ld [wRobotOn], a
    ld hl, wOam
    ld b, 32 * 4
.h:
    ld [hl+], a
    dec b
    jr nz, .h
    ld a, $FF
    ld [wShown], a
    ld a, 1
    ldh [hOamDirty], a
    ret

SECTION "robot_vars2", WRAM0
wRowSeed:  ds 1
wRowX:     ds 1
wRowsToDo: ds 1
