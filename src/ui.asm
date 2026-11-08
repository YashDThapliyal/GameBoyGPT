; ui.asm - UX state machine: TITLE INTRO MENU PREFILL GENERATING REVEAL UPDATE ENDING STATS.
; One job per screen: read the story, press A, then choose. Text is double-spaced in a bold font.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"
IF !DEF(TEST_ROM)

SECTION "ui_vars", WRAM0
wMenuSel::   ds 1
wTextRowN::  ds 1          ; current line inside the story box
wTextColN::  ds 1
wCapNext::   ds 1
wMenuRow:    ds 1
wSaved::     ds SCREEN_W * SCREEN_H
wEndFlag::   ds 1

SECTION "ui_strings", ROM0
StrSub1:   db "A TINY TRANSFORMER", 0
StrSub2:   db "STORY", 0
StrStart:  db "PRESS START", 0
StrIntro1: db "The crown waits in", 0
StrIntro2: db "the old tower.", 0
StrIntro3: db "Choose with care.", 0
StrIntro4: db "Read the signs.", 0
StrChipA:  db "A", 0
StrChipSe: db "SELECT", 0
StrChoose: db "choose", 0
StrNext:   db "next", 0
StrWrite:  db "Writing", 0
StrAgain:  db "new run", 0
StrNew:    db "new", 0
StrBack:   db "back", 0
StrEnding: db "ENDING", 0
StrFound:  db "Found", 0
StrOf:     db "of", 0
StrAct:    db "ACT", 0

SECTION "ui_code", ROM0
; SetState: a = ST_*. Mirrors state to mailbox.
SetState::
    ld [wMB_State], a
    ret

GameMain::
    call TitleScreen
    call NewRun
.turn:
    call ChoiceMenu
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
    ld a, ST_UPDATE
    call SetState
    ; Narration seed. World truth has no randomness, so this only changes the wording.
    ld a, [wMB_ForceSeed]
    or a
    jr z, .entropy
    ld a, [wMB_Seed]
    ld e, a
    ld a, [wMB_Seed + 1]
    ld d, a
    jr .seed
.entropy:
    ldh a, [rDIV]
    ld e, a
    ldh a, [hFrames]
    ld d, a
.seed:
    ld a, d
    or e
    jr nz, .nz
    inc e
.nz:
    ld a, e
    ld [wNarrRng], a
    ld a, d
    ld [wNarrRng + 1], a
    call StartStory
    xor a
    ld [wEndFlag], a
    ld [wMenuSel], a
    call SyncMailbox
    call LoadRoomScreen
    call ClearText
    ld hl, StrIntro1
    ld b, TEXT_ROW
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrIntro2
    ld b, TEXT_ROW + 2
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrIntro3
    ld b, TEXT_ROW + 4
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrIntro4
    ld b, TEXT_ROW + 6
    ld c, TEXT_COL
    call PrintAt
    ld a, ST_INTRO
    call SetState
    jp WaitNext

; LoadRoomScreen: rebuilds the entire screen for wRoom behind a fade.
LoadRoomScreen::
    call ScreenOff
    call ClearShadow
    call CurrentArt
    ld [wPrevArt], a
    ld c, a
    add a
    add a
    add c
    add c                ; art * 6
    ld c, a
    ld b, 0
    ld hl, SceneTable
    add hl, bc
    ld b, 6
    call LoadArt
    call DrawBand
    call DrawStatus
    call ScreenOn
    ret

; CurrentArt: -> a = scene image of the current scene. Clobbers de, hl.
CurrentArt:
    ld a, [wScene]
    call ScenePtr
    inc hl
    inc hl
    ld a, [hl]
    ret

; DrawBand: place name, carried items and remaining lives on the dark band under the scene.
DrawBand::
    ld b, BAND_ROW
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    ld a, [wScene]
    call ScenePtr
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld b, BAND_ROW
    ld c, 1
    call PrintInvAt
    ; one icon slot per item, so an item always appears in the same place
    ld a, [wFlags]
    ld b, a
    ld hl, wBgMap + BAND_ROW * SCREEN_W + 12
    ld c, TILE_LAMP
    bit 0, b
    call nz, .icon
    inc hl
    ld c, TILE_KEY
    bit 1, b
    call nz, .icon
    inc hl
    ld c, TILE_FRIEND
    bit 2, b
    call nz, .icon
    inc hl
    ld c, TILE_SWORD
    bit 3, b
    call nz, .icon
    inc hl
    ld c, TILE_RING
    bit 4, b
    call nz, .icon
    ld a, [wWounds]
    ld b, a
    ld a, MAX_WOUNDS
    sub b
    jr z, .done
    jr c, .done
    ld d, a
    ld hl, wBgMap + BAND_ROW * SCREEN_W + 19
.hearts:
    ld [hl], TILE_HEART
    dec hl
    dec d
    jr nz, .hearts
.done:
    ld b, BAND_ROW
    jp MarkRow
.icon:
    ld [hl], c
    ret

; DrawStatus: act and turn on the inverse status row.
DrawStatus::
    ld b, STATUS_ROW
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    ld hl, StrAct
    ld b, STATUS_ROW
    ld c, 1
    call PrintInvAt
    ld a, [wScene]
    call ScenePtr
    inc hl
    inc hl
    inc hl
    ld a, [hl]
    add TILE_INV + 27    ; acts are single digits
    ld [wBgMap + STATUS_ROW * SCREEN_W + 5], a
    ld hl, StrTurnLbl
    ld b, STATUS_ROW
    ld c, 11
    call PrintInvAt
    ld a, [wTurn]
    ld hl, wBgMap + STATUS_ROW * SCREEN_W + 16
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

; ClearBody: blanks everything between the band and the status bar.
ClearBody:
    ld b, BODY_ROW
    ld c, BODY_ROWS
    xor a
    jp FillRows

; ClearText: blanks the body and resets the story cursor.
ClearText::
    call ClearBody
    xor a
    ld [wTextRowN], a
    ld [wTextColN], a
    inc a
    ld [wCapNext], a
    ret

; ClearHint: blanks the hint row.
ClearHint:
    ld b, HINT_ROW
    ld c, 1
    xor a
    jp FillRows

; WaitNext: shows "A next" and waits for a fresh A or B press.
WaitNext:
    call ClearHint
    ld hl, StrChipA
    ld b, HINT_ROW
    ld c, 13
    call PrintInvAt
    ld hl, StrNext
    ld b, HINT_ROW
    ld c, 15
    call PrintAt
    call ConsumePressed
.w:
    call WaitVBlank
    call ConsumePressed
    and (1 << PAD_A) | (1 << PAD_B)
    jr z, .w
    ret

; ---- Choice menu ----------------------------------------------------------
; One choice per double-spaced row. Up and down move the pointer, A confirms.
ChoiceMenu:
    ld a, ST_MENU
    call SetState
    call CollectChoices
    xor a
    ld [wMenuSel], a
    call ClearBody
    call DrawChoices
    ld hl, StrChipA
    ld b, HINT_ROW
    ld c, 11
    call PrintInvAt
    ld hl, StrChoose
    ld b, HINT_ROW
    ld c, 13
    call PrintAt
    call ConsumePressed
.loop:
    call WaitVBlank
    call PlaceCursor
    call ConsumePressed
    ld b, a
    bit PAD_START, b
    jr z, .nostart
    call StatsScreen
    ld a, [wEndFlag]
    cp 2
    jr nz, .loop
    xor a
    ld [wEndFlag], a      ; new run requested from the stats page
    ld [wOam], a
    call NewRun
    jr ChoiceMenu
.nostart:
    ld a, [wMenuSel]
    ld c, a
    bit PAD_UP, b
    jr z, .a1
    or a
    jr z, .a1
    dec c
.a1:
    bit PAD_DOWN, b
    jr z, .a2
    ld a, [wNumChoices]
    dec a
    cp c
    jr z, .a2
    inc c
.a2:
    ld a, c
    ld [wMenuSel], a
    bit PAD_A, b
    jr z, .loop
    xor a
    ld [wOam], a          ; hide the pointer
    ld a, [wMenuSel]
    ld e, a
    ld d, 0
    ld hl, wChoices
    add hl, de
    ld a, [hl]
    jp ApplyChoice

; DrawChoices: every visible choice on its row. Clobbers everything.
DrawChoices:
    xor a
.item:
    ld c, a
    ld a, [wNumChoices]
    cp c
    ret z
    ret c
    ld a, c
    push af
    ld e, a
    ld d, 0
    ld hl, wChoices
    add hl, de
    ld a, [hl]
    call ChoicePtr
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    pop af
    push af
    add a
    add TEXT_ROW
    ld b, a
    ld c, 2
    call PrintAt
    pop af
    inc a
    jr .item

; PlaceCursor: bobbing pointer sprite beside the selected choice.
PlaceCursor:
    ld a, [wMenuSel]
    add a
    add TEXT_ROW
    add a
    add a
    add a                ; row * 8
    add 16
    ld [wOam], a
    ld c, 8 + 7
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
    ; ChoiceMenu has applied the choice, so the screen can show where you are now.
    call CurrentArt
    ld b, a
    ld a, [wPrevArt]
    cp b
    jr z, .same
    call LoadRoomScreen
    jr .ready
.same:
    call DrawBand
    call DrawStatus
.ready:
    call ClearText
    call NarrateEvent     ; PREFILL -> GENERATING: writes words into the story box
    ld a, ST_REVEAL
    call SetState
    ; an ending scene has no choices
    ld a, [wScene]
    call ScenePtr
    ld de, 6
    add hl, de
    ld a, [hl]
    cp 255
    jr z, .wait
    ld a, 1
    ld [wEndFlag], a
.wait:
    jp WaitNext

; ThinkingPanel: honest progress on the hint row, under the words as they appear.
ThinkingPanel::
    ld a, ST_PREFILL
    call SetState
    call ClearHint
    ld hl, StrWrite
    ld b, HINT_ROW
    ld c, TEXT_COL
    call PrintAt
    ; spinner sprite at the end of the bar
    ld a, 16 + HINT_ROW * 8
    ld [wOam + 4], a
    ld a, 8 + 18 * 8
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

; ThinkingProgress: a = tokens generated so far. Bar of 8 tiles, 4 ticks each, driven by real progress.
ThinkingProgress::
    add a                ; tokens * 2 ticks: the longest event fills the 32-tick bar
    ld b, a
    ld hl, wBgMap + HINT_ROW * SCREEN_W + 9
    ld c, 8
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
    ld b, HINT_ROW
    jp MarkRow

; ---- Ending ---------------------------------------------------------------
EndingScreen:
    ld a, ST_ENDING
    call SetState
    ; which ending is this, and how many have you seen?
    ld a, [wScene]
    call ScenePtr
    ld de, 6
    add hl, de
    ld c, [hl]           ; ending index
    ld b, 1
    ld a, c
    or a
    jr z, .bit0
.shift:
    sla b
    dec a
    jr nz, .shift
.bit0:
    ld a, [wEndMask]
    or b
    ld [wEndMask], a
    push bc
    call ClearBody
    ld hl, StrEnding
    ld b, 9
    ld c, 1
    call PrintAt
    pop bc
    ld a, c
    add a
    ld e, a
    ld d, 0
    ld hl, EndingNames
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld b, 11
    ld c, 1
    call PrintAt
    ld hl, StrFound
    ld b, 14
    ld c, 1
    call PrintAt
    ; population count of the mask, shown as "n of 8"
    ld a, [wEndMask]
    ld c, a
    ld b, 8
    xor a
.pop:
    srl c
    adc 0
    dec b
    jr nz, .pop
    add '0' - $20
    ld [wBgMap + 14 * SCREEN_W + 7], a
    ld hl, StrOf
    ld b, 14
    ld c, 9
    call PrintAt
    ld a, NUM_ENDINGS + '0' - $20
    ld [wBgMap + 14 * SCREEN_W + 12], a
    ld b, 14
    call MarkRow
    ld hl, StrChipA
    ld b, HINT_ROW
    ld c, 10
    call PrintInvAt
    ld hl, StrAgain
    ld b, HINT_ROW
    ld c, 12
    call PrintAt
    call ConsumePressed
.w:
    call WaitVBlank
    call ConsumePressed
    bit PAD_A, a
    jr z, .w
    ret

; ---- Stats page, full screen. Values are timed on this device from LCD frames. ----
StatsScreen::
    ld a, ST_STATS
    call SetState
    xor a
    ld [wOam], a
    ld hl, wBgMap
    ld de, wSaved
    ld bc, SCREEN_W * SCREEN_H
    call MemCopy
    ld b, 0
    ld c, SCREEN_H
    xor a
    call FillRows
    call DrawStats
    call MarkAllRows
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
    ld de, wBgMap
    ld bc, SCREEN_W * SCREEN_H
    call MemCopy
    call MarkAllRows
    ld a, ST_MENU
    jp SetState

MarkAllRows:
    ld b, 0
    ld c, SCREEN_H
.m:
    call MarkRow
    inc b
    dec c
    jr nz, .m
    ret

StrS1: db "RUN STATS", 0
StrS5: db "Sec/event", 0
StrS6: db "Sec/word", 0
StrS7: db "Words", 0
StrS8: db "Bank sw", 0
StrS2: db "Events", 0
StrS3: db "Capped", 0

DrawStats::
    ld hl, StrS1
    ld b, 0
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrVariant
    ld b, 2
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrModelParams
    ld b, 4
    ld c, 0
    call PrintAt
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
    ld hl, StrS6
    ld b, 6
    ld c, TEXT_COL
    call PrintAt
    ld hl, StrS5
    ld b, 8
    ld c, TEXT_COL
    call PrintAt
    pop de
    ld hl, wBgMap + 8 * SCREEN_W + 12
    call PrintCenti
    pop hl
    ld a, [wLastEventTokens]
    or a
    jr z, .notok
    ld c, a
    call DivHLByC
.notok:
    ld d, h
    ld e, l
    ld hl, wBgMap + 6 * SCREEN_W + 12
    call PrintCenti
    ld hl, StrS7
    ld b, 10
    ld c, TEXT_COL
    call PrintAt
    ld a, [wLastEventTokens]
    ld hl, wBgMap + 10 * SCREEN_W + 15
    call PrintDec2
    ld hl, StrS8
    ld b, 12
    ld c, TEXT_COL
    call PrintAt
    ld a, [wLastEventBanks]
    ld e, a
    ld a, [wLastEventBanks + 1]
    ld d, a
    ld hl, wBgMap + 12 * SCREEN_W + 12
    call PrintDec16
    ld hl, StrS2
    ld b, 14
    ld c, TEXT_COL
    call PrintAt
    ld a, [wMB_Events]
    ld hl, wBgMap + 14 * SCREEN_W + 8
    call PrintDec2
    ld hl, StrS3
    ld b, 14
    ld c, 11
    call PrintAt
    ld a, [wTotalFallbacks]
    ld hl, wBgMap + 14 * SCREEN_W + 18
    call PrintDec2
    ld hl, StrChipSe
    ld b, 16
    ld c, 0
    call PrintInvAt
    ld hl, StrNew
    ld b, 16
    ld c, 7
    call PrintAt
    ld hl, StrChipA
    ld b, 16
    ld c, 12
    call PrintInvAt
    ld hl, StrBack
    ld b, 16
    ld c, 14
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

; PrintCenti: de = centiseconds, hl = shadow ptr; prints "ddd.dd" without leading zeros. Clobbers a, bc, de.
PrintCenti:
    push hl
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
    pop hl
    ; blank up to two leading zeros, keeping the digit before the point
    ld b, 2
.lead:
    ld a, [hl]
    cp '0' - $20
    ret nz
    xor a
    ld [hl+], a
    dec b
    jr nz, .lead
    ret

; PrintDec16: de = value, hl = shadow ptr. Five digits. Clobbers a, bc, de.
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
