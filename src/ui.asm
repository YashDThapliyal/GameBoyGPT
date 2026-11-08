; ui.asm - UX state machine: BOOT TITLE INTRO MENU PREFILL GENERATING REVEAL UPDATE ENDING STATS.
INCLUDE "constants.inc"
IF !DEF(TEST_ROM)

SECTION "ui_vars", WRAM0
wMenuSel::   ds 1
wTextRowN::  ds 1          ; current row inside the text box
wTextColN::  ds 1
wSaved::     ds SCREEN_W * 10
wSavedSpr::  ds 8
wEndFlag::   ds 1

SECTION "ui_strings", ROM0
StrSub1:   db "A TINY TRANSFORMER", 0
StrSub2:   db "STORY", 0
StrStart:  db "PRESS START", 0
StrIntro1: db "THE TOWER WAITS", 0
StrIntro2: db "PAST THE MIST.", 0
StrIntro3: db "FIND A LAMP.", 0
StrIntro4: db "FIND THE KEY.", 0
StrAsk:    db "WHAT WILL YOU DO?", 0
StrItem0:  db "GO LEFT", 0
StrItem1:  db "GO RIGHT", 0
StrItem2:  db "GO ON", 0
StrItem3:  db "SEARCH", 0
StrHint:   db "A CHOOSE START INFO", 0
StrThink1: db "THE CARTRIDGE IS", 0
StrThink2: db "THINKING", 0
StrWord:   db "TOKEN", 0
StrMore:   db "A CONTINUE", 0
StrWin:    db "THE TOWER IS YOURS", 0
StrLose:   db "THE MIST TAKES YOU", 0
StrAgain:  db "A NEW RUN", 0
RoomNames:
    dw .r0, .r1, .r2, .r3, .r4, .r5, .r6, .r7
.r0: db "DARK FOREST", 0
.r1: db "BLACK MARSH", 0
.r2: db "COLD RIVER", 0
.r3: db "OLD RUINS", 0
.r4: db "PALE SHRINE", 0
.r5: db "DEEP CAVE", 0
.r6: db "IRON GATE", 0
.r7: db "THE TOWER", 0

SECTION "ui_code", ROM0
; SetState: a = ST_*. Mirrors state to mailbox.
SetState::
    ld [wMB_State], a
    ret

GameMain::
    call TitleScreen
    call NewRun
.turn:
    call ActionMenu
    call PlayTurn
    ld a, [wEndFlag]
    or a
    jr z, .turn
    call EndingScreen
    jr GameMain

; ---- Title ----------------------------------------------------------------
TitleScreen:
    ld a, ST_TITLE
    call SetState
    call ScreenOff
    call ClearShadow
    ld hl, TitleInfo
    ld b, SCREEN_H
    call LoadArt
    ld hl, StrSub1
    ld b, 14
    ld c, 1
    call PrintInvAt
    ld hl, StrSub2
    ld b, 15
    ld c, 7
    call PrintInvAt
    ld a, TILE_CHIP
    ld [wBgMap + 15 * SCREEN_W + 5], a
    ld [wBgMap + 15 * SCREEN_W + 13], a
    call ScreenOn
.wait:
    call WaitVBlank
    ldh a, [hFrames]
    and 32
    jr z, .show
    ld b, 16
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    jr .poll
.show:
    ld b, 16
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    ld hl, StrStart
    ld b, 16
    ld c, 4
    call PrintInvAt
.poll:
    call ConsumePressed
    bit PAD_START, a
    jr z, .wait
    ret

; ---- Run setup ------------------------------------------------------------
NewRun::
    ld a, ST_INTRO
    call SetState
    ld a, [wMB_ForceSeed]
    or a
    jr z, .entropy
    ld a, [wMB_Seed]
    ld e, a
    ld a, [wMB_Seed + 1]
    ld d, a
    jr .gen
.entropy:
    ldh a, [rDIV]
    ld e, a
    ldh a, [hFrames]
    ld d, a
.gen:
    call GenWorld
    ; Narration RNG is separate from world RNG, so sampling can never change game truth.
    ld a, [wRng]
    xor $A5
    ld [wNarrRng], a
    ld a, [wRng + 1]
    xor $A5
    ld [wNarrRng + 1], a
    xor a
    ld [wEndFlag], a
    ld [wMenuSel], a
    ld [wOutcome], a
    ld [wAction], a
    call SyncMailbox
    call LoadRoomScreen
    call ClearText
    ld hl, StrIntro1
    ld b, TEXT_ROW
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrIntro2
    ld b, TEXT_ROW + 1
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrIntro3
    ld b, TEXT_ROW + 2
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrIntro4
    ld b, TEXT_ROW + 3
    ld c, TEXT_COL
    jp PrintAt

; LoadRoomScreen: rebuilds the entire screen for wRoom behind a fade.
LoadRoomScreen::
    call ScreenOff
    call ClearShadow
    ld a, [wRoom]
    ld c, a
    add a
    add a
    add c
    add c                ; room * 6
    ld c, a
    ld b, 0
    ld hl, SceneTable
    add hl, bc
    ld b, 6
    call LoadArt
    call DrawBand
    call DrawStatus
    ld b, RULE_ROW
    ld c, 1
    ld a, TILE_RULE
    call FillRows
    call ScreenOn
    ret

; DrawBand: room name and lives on the dark band under the scene.
DrawBand::
    ld b, BAND_ROW
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    ld a, [wRoom]
    add a
    ld e, a
    ld d, 0
    ld hl, RoomNames
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld b, BAND_ROW
    ld c, 1
    call PrintInvAt
    ld a, [wLives]
    or a
    ret z
    ld d, a
    ld hl, wBgMap + BAND_ROW * SCREEN_W + 18
.hearts:
    ld [hl], TILE_HEART
    dec hl
    dec d
    jr nz, .hearts
    ret

; DrawStatus: LAMP 0 KEY 0 TURN 00 on the inverse status row.
DrawStatus::
    ld b, STATUS_ROW
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    ld hl, wBgMap + STATUS_ROW * SCREEN_W + 1
    ld a, [wHasLamp]
    or a
    jr z, .nl
    ld [hl], TILE_LAMP
.nl:
    inc hl
    ld a, [wHasKey]
    or a
    jr z, .nk
    ld [hl], TILE_KEY
.nk:
    ld hl, StrTurnLbl
    ld b, STATUS_ROW
    ld c, 12
    call PrintInvAt
    ld a, [wTurn]
    ld hl, wBgMap + STATUS_ROW * SCREEN_W + 17
    call PrintDec2Inv
    ld b, STATUS_ROW
    jp MarkRow
StrTurnLbl: db "TURN", 0

; PrintDec2Inv: a = value, hl = shadow ptr, inverse digits.
PrintDec2Inv:
    ld b, 0
.t:
    cp 10
    jr c, .u
    sub 10
    inc b
    jr .t
.u:
    ld c, a
    ld a, b
    call .digit
    ld a, c
.digit:
    add TILE_INV + 27    ; INV_CHARS: space, A-Z, then 0-9
    ld [hl+], a
    ret

; ClearText: blanks the story box and resets the wrap cursor.
ClearText::
    ld b, TEXT_ROW
    ld c, TEXT_ROWS
    xor a
    call FillRows
    xor a
    ld [wTextRowN], a
    ld [wTextColN], a
    ret

; ClearMenu: blanks rows MENU_ROW..MENU_ROW+3.
ClearMenu::
    ld b, MENU_ROW
    ld c, 4
    xor a
    jp FillRows

; ---- Action menu ----------------------------------------------------------
ActionMenu:
    ld a, ST_MENU
    call SetState
    call ClearMenu
    ld hl, StrAsk
    ld b, MENU_ROW
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrItem0
    ld b, MENU_ROW + 1
    ld c, 2
    call PrintAt
    ld hl, StrItem1
    ld b, MENU_ROW + 1
    ld c, 11
    call PrintAt
    ld hl, StrItem2
    ld b, MENU_ROW + 2
    ld c, 2
    call PrintAt
    ld hl, StrItem3
    ld b, MENU_ROW + 2
    ld c, 11
    call PrintAt
    ld hl, StrHint
    ld b, MENU_ROW + 3
    ld c, 0
    call PrintAt
    call ConsumePressed
.loop:
    call WaitVBlank
    call PlaceCursor
    call ConsumePressed
    ld b, a
    bit PAD_START, b
    jr z, .nostart
    push bc
    call StatsScreen
    pop bc
    ld a, [wEndFlag]
    cp 2
    jr nz, .loop
    xor a
    ld [wEndFlag], a      ; new run requested from the stats page
    call NewRun
    jr ActionMenu
.nostart:
    ld a, [wMenuSel]
    ld c, a
    bit PAD_LEFT, b
    jr z, .a1
    res 0, c
.a1:
    bit PAD_RIGHT, b
    jr z, .a2
    set 0, c
.a2:
    bit PAD_UP, b
    jr z, .a3
    res 1, c
.a3:
    bit PAD_DOWN, b
    jr z, .a4
    set 1, c
.a4:
    ld a, c
    ld [wMenuSel], a
    bit PAD_A, b
    jr z, .loop
    ld [wAction], a
    ; hide cursor
    xor a
    ld [wOam], a
    ret

; PlaceCursor: animated arrow sprite beside the selected item.
PlaceCursor:
    ld a, [wMenuSel]
    ld b, a
    and 2
    add a
    add a                ; 0 or 8
    add 16 + (MENU_ROW + 1) * 8
    ld [wOam], a
    ld a, b
    and 1
    ld a, 8 + 8
    jr z, .l
    ld a, 8 + 8 + 72
.l:
    ld c, a
    ldh a, [hFrames]
    and 16
    jr z, .n
    inc c
.n:
    ld a, c
    ld [wOam + 1], a
    ld a, TILE_CURSOR
    ld [wOam + 2], a
    xor a
    ld [wOam + 3], a
    ret

; ---- Turn -----------------------------------------------------------------
PlayTurn:
    ld a, ST_UPDATE
    call SetState
    call GameStep
    ; Room changed? show the new place before narrating the arrival.
    ld a, [wRoom]
    ld b, a
    ld a, [wPrevRoom]
    cp b
    jr z, .same
    call LoadRoomScreen
    jr .ready
.same:
    call DrawBand
    call DrawStatus
.ready:
    call ClearText
    call ClearMenu
    call NarrateEvent     ; PREFILL -> GENERATING: writes words into the story box
    ld a, ST_REVEAL
    call SetState
    call DrawStatus
    ld a, [wOutcome]
    cp OUT_WIN
    jr z, .end
    cp OUT_LOSE
    jr z, .end
    jr .wait
.end:
    ld a, 1
    ld [wEndFlag], a
.wait:
    call ClearMenu
    ld hl, StrMore
    ld b, MENU_ROW + 1
    ld c, TEXT_COL + 2
    call PrintAt
    ld a, TILE_ARROW
    ld [wBgMap + (MENU_ROW + 1) * SCREEN_W + TEXT_COL], a
    call ConsumePressed
.w:
    call WaitVBlank
    call ConsumePressed
    and (1 << PAD_A) | (1 << PAD_B)
    jr z, .w
    ret

; ThinkingPanel: draws the honest progress panel in the menu area.
ThinkingPanel::
    ld a, ST_PREFILL
    call SetState
    call ClearMenu
    ld hl, StrThink1
    ld b, MENU_ROW
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrThink2
    ld b, MENU_ROW + 1
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrWord
    ld b, MENU_ROW + 3
    ld c, TEXT_COL
    call PrintAt
    ; spinner sprite
    ld a, 16 + (MENU_ROW + 1) * 8
    ld [wOam + 4], a
    ld a, 8 + 11 * 8
    ld [wOam + 5], a
    ld a, TILE_SPIN0
    ld [wOam + 6], a
    ld a, 1
    ldh [hSpin], a
    ret

; ThinkingDone: removes spinner.
ThinkingDone::
    xor a
    ldh [hSpin], a
    ld [wOam + 4], a
    ret

; ThinkingProgress: a = tokens generated so far, c = cap. Draws bar and counter from real progress.
ThinkingProgress::
    push af
    ld b, a
    ld hl, wBgMap + (MENU_ROW + 2) * SCREEN_W + TEXT_COL
    ; bar: 16 tiles, each 4 ticks. filled ticks = tokens * 64 / cap (cap <= 16: cap 11 -> *6 approx)
    ld a, b
    add a
    add a
    add b
    add b                ; tokens * 6 ticks, 11 tokens fill 66/64
    ld b, a
    ld c, 16
.bar:
    ld a, b
    cp 4
    jr c, .part
    sub 4
    ld b, a
    ld a, TILE_BAR0 + 4
    jr .put
.part:
    add TILE_BAR0
    ld b, 0
.put:
    ld [hl+], a
    dec c
    jr nz, .bar
    pop af
    ld hl, wBgMap + (MENU_ROW + 3) * SCREEN_W + TEXT_COL + 6
    call PrintDec2
    ld b, MENU_ROW + 2
    call MarkRow
    inc b
    jp MarkRow

; ---- Ending ---------------------------------------------------------------
EndingScreen:
    ld a, ST_ENDING
    call SetState
    call ClearMenu
    ld a, [wOutcome]
    cp OUT_WIN
    ld hl, StrWin
    jr z, .p
    ld hl, StrLose
.p:
    ld b, MENU_ROW
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrAgain
    ld b, MENU_ROW + 2
    ld c, TEXT_COL
    call PrintAt
    call ConsumePressed
.w:
    call WaitVBlank
    call ConsumePressed
    bit PAD_A, a
    jr z, .w
    ret

; ---- Stats overlay --------------------------------------------------------
StatsScreen::
    ld a, ST_STATS
    call SetState
    ; save rows 7..16, then draw
    ld hl, wBgMap + TEXT_ROW * SCREEN_W
    ld de, wSaved
    ld bc, SCREEN_W * 10
    call MemCopy
    ld a, [wOam]
    ld [wSavedSpr], a
    xor a
    ld [wOam], a
    ld b, TEXT_ROW
    ld c, 10
    xor a
    call FillRows
    call DrawStats
.w:
    call WaitVBlank
    call ConsumePressed
    ld b, a
    bit PAD_SELECT, b
    jr nz, .newrun
    and (1 << PAD_A) | (1 << PAD_B) | (1 << PAD_START)
    jr z, .w
    jr .restore
.newrun:
    ld a, 2
    ld [wEndFlag], a
.restore:
    ld hl, wSaved
    ld de, wBgMap + TEXT_ROW * SCREEN_W
    ld bc, SCREEN_W * 10
    call MemCopy
    ld a, [wSavedSpr]
    ld [wOam], a
    ld b, TEXT_ROW
    ld c, 10
.m:
    call MarkRow
    inc b
    dec c
    jr nz, .m
    ld a, ST_MENU
    jp SetState

; ---- Stats content (measured on this device from LCD frames; zero until an event has run) ----
StrS1: db "RUN STATS", 0
StrS2: db "EVENTS", 0
StrS3: db "CAP", 0
StrS4: db "MODEL 14784 PARAMS", 0
StrS5: db "SEC/EVENT", 0
StrS6: db "SEC/TOKEN", 0
StrS7: db "TOKENS", 0
StrS8: db "BANK SW", 0
StrS9: db "SEL NEW RUN  A BACK", 0

DrawStats::
    ld hl, StrVariant
    ld b, TEXT_ROW
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrS4
    ld b, TEXT_ROW + 1
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrS2
    ld b, TEXT_ROW + 2
    ld c, TEXT_COL
    call PrintAt
    ld a, [wMB_Events]
    ld hl, wBgMap + (TEXT_ROW + 2) * SCREEN_W + 8
    call PrintDec2
    ld hl, StrS3
    ld b, TEXT_ROW + 2
    ld c, 12
    call PrintAt
    ld a, [wTotalFallbacks]
    ld hl, wBgMap + (TEXT_ROW + 2) * SCREEN_W + 16
    call PrintDec2
    ; centiseconds = frames * 5 / 3 (nominal 60 Hz; the LCD's true rate differs by 0.4%)
    ld a, [wLastEventFrames]
    ld l, a
    ld a, [wLastEventFrames + 1]
    ld h, a
    ld d, h
    ld e, l
    add hl, hl
    add hl, hl
    add hl, de           ; frames * 5
    ld c, 3
    call DivHLByC
    push hl
    push hl
    ld hl, StrS5
    ld b, TEXT_ROW + 4
    ld c, TEXT_COL
    call PrintAt
    pop de
    ld hl, wBgMap + (TEXT_ROW + 4) * SCREEN_W + 11
    call PrintCenti
    pop hl
    ld a, [wLastEventTokens]
    or a
    jr z, .notok
    ld c, a
    call DivHLByC
.notok:
    push hl
    ld hl, StrS6
    ld b, TEXT_ROW + 5
    ld c, TEXT_COL
    call PrintAt
    pop de
    ld hl, wBgMap + (TEXT_ROW + 5) * SCREEN_W + 11
    call PrintCenti
    ld hl, StrS7
    ld b, TEXT_ROW + 6
    ld c, TEXT_COL
    call PrintAt
    ld a, [wLastEventTokens]
    ld hl, wBgMap + (TEXT_ROW + 6) * SCREEN_W + 14
    call PrintDec2
    ld hl, StrS8
    ld b, TEXT_ROW + 7
    ld c, TEXT_COL
    call PrintAt
    ld a, [wLastEventBanks]
    ld e, a
    ld a, [wLastEventBanks + 1]
    ld d, a
    ld hl, wBgMap + (TEXT_ROW + 7) * SCREEN_W + 11
    call PrintDec16
    ld hl, StrS9
    ld b, TEXT_ROW + 9
    ld c, 0
    jp PrintAt

; DivHLByC: hl = hl / c, unsigned, by restoring division. Clobbers a, b.
DivHLByC:
    xor a
    ld b, 16
.bit:
    add hl, hl
    rla
    jr c, .sub           ; 9th bit set: remainder certainly exceeds c
    cp c
    jr c, .next
.sub:
    sub c
    inc l
.next:
    dec b
    jr nz, .bit
    ret

; PrintCenti: de = centiseconds, hl = shadow ptr; prints ddd.dd with leading digits. Clobbers a, bc, de.
PrintCenti:
    call PrintDec16
    ; shift the last two digits right one cell to make room for the point
    dec hl
    ld a, [hl]
    inc hl
    ld [hl], a
    dec hl
    dec hl
    ld a, [hl]
    inc hl
    ld [hl], a
    dec hl
    ld [hl], '.' - $20
    ret

; PrintDec16: de = value, hl = shadow ptr. Five digits. Clobbers a, bc, de.
PrintDec16:
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
    ld a, '0' - $20 - 1
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
    ld [hl+], a
    ret

StrVariant: db VARIANT_NAME, 0

ENDC
