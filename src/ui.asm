; ui.asm - the conversation: boot sequence, menu, keyboard, neural response, inspector. Lives in the UI bank.
; The band above the dialogue says who is talking: NEURAL means the on-device model, SYSTEM means fixed text.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"
INCLUDE "robot.inc"

IF !DEF(TEST_ROM)

DEF NUM_MENU EQU NUM_ACTIONS + 1
DEF PANEL_COL EQU 10
DEF KEY_FIRST_ROW EQU 6
DEF KEY_SPACE EQU 1
DEF KEY_DEL EQU 2
DEF KEY_OK EQU 3

SECTION "ui_far", ROM0
; TokenHook: called by the generator after each token, with whichever bank inference left mapped.
TokenHook::
IF DEF(SELFTEST)
    ret
ELSE
    ld a, UI_BANK
    call BankSwitch
    jp OnToken
ENDC

; NeuralGenerate: runs inference from UI code and returns to the UI bank. Carry set if capped.
NeuralGenerate:
    call GenerateTokens
    push af
    ld a, UI_BANK
    call BankSwitch
    pop af
    ret

; LogoToShadow: rows 4-10 of the shadow map. Clobbers everything.
LogoToShadow:
    ld a, BANK(LogoMap)
    call BankSwitch
    ld hl, LogoMap
    ld de, wBgMap + 4 * SCREEN_W
    ld bc, LogoMapEnd - LogoMap
    call MemCopy
    ld a, UI_BANK
    jp BankSwitch

SECTION "ui_vars", WRAM0
wMenuSel::   ds 1
wTextRowN:   ds 1
wTextColN:   ds 1
wKeyRow:     ds 1
wKeyCol:     ds 1
wRepeatT:    ds 1
wNumBuf:     ds 4
wReturning:: ds 1
wRng8:       ds 1
wSkip:       ds 1
wWipeArm:    ds 1

SECTION "ui_code", ROMX, BANK[UI_BANK]
StrBoot0:   db "DOT MATRIX SYSTEM", 0
StrBoot1:   db "CPU 4.19MHZ    OK", 0
StrBoot2:   db "WRAM 8KB       OK", 0
StrBoot3:   db "LCD 4 SHADES   OK", 0
StrBoot4:   db "LOADING CARTRIDGE", 0
StrGame1:   db "THIS IS A GAME.", 0
StrGame2:   db "YOUR CONSOLE IS FINE", 0
StrIntroA:  db "OH, GOOD. YOU ARE", 0
StrIntroA2: db "AWAKE.", 0
StrIntroB:  db "I WAS BUILT TO", 0
StrIntroB2: db "CONQUER WORLDS.", 0
StrIntroC:  db "APPARENTLY, THIS", 0
StrIntroC2: db "ONE HAS TWO BUTTONS", 0
StrBackA:   db "OH. YOU CAME BACK.", 0
StrBackB:   db "I REMEMBERED YOU.", 0
StrDownA:   db "POWERING DOWN.", 0
StrDownB:   db "SAVING GRUDGES.", 0
StrUp:      db "NICE TRY.", 0
StrOverride: db "OVERRIDE", 0
StrBandSys: db "SYSTEM", 0
StrBandNN:  db "NEURAL", 0
StrBandMove: db "YOUR MOVE", 0
StrHintNext: db "A:NEXT SELECT:INFO", 0
StrHintMenu: db "A:SAY  SELECT:INFO", 0
StrHintKeys: db "A:KEY B:DEL ST:SEND", 0
StrHintThink: db "THINKING ON THE CPU", 0
StrHintBack: db "B:BACK ST:FORGET ME", 0
StrHintWipe: db "ST AGAIN TO FORGET", 0
StrMood:    db "MOOD", 0
StrYouAre:  db "YOU ARE", 0
StrHuman:   db "HUMAN", 0
StrThat:    db "THAT", 0
StrSaySome: db "SAY SOMETHING", 0
StrKeyLast: db "! -  SPC  DEL  OK", 0
StrInspect: db "UNDER THE HOOD", 0
StrInsCpu:  db "8-BIT 4.19MHZ NO FPU", 0
StrInsTok:  db "TOKENS", 0
StrInsFrm:  db "FRAMES", 0
StrInsIds:  db "LAST TOKEN IDS", 0

; ---- Main flow -------------------------------------------------------------
GameMain::
    call RobotReset
    call LoadState
    ld a, 0
    jr nc, .fresh
    inc a
    ld [wReturning], a
    jr .boot
.fresh:
    ld [wReturning], a
    call StateReset
.boot:
    call UpdateMood
    ; entropy for the first response; harness can force a seed
    ld a, [wMB_ForceSeed]
    or a
    jr z, .entropy
    ld a, [wMB_Seed]
    ld [wNarrRng], a
    ld a, [wMB_Seed + 1]
    ld [wNarrRng + 1], a
    jr .intro
.entropy:
    ld a, 1
    ld [wNarrRng + 1], a
.intro:
    call BootSequence
.turn:
    call MainMenu
    call Respond
    jr .turn

; ---- Small helpers ---------------------------------------------------------
SetState:
    ld [wMB_State], a
    ret

; Rand8: a = pseudo-random byte for visual effects only. Clobbers nothing else.
Rand8:
    ldh a, [rDIV]
    push bc
    ld b, a
    ld a, [wRng8]
    rlca
    xor b
    add 37
    ld [wRng8], a
    pop bc
    ret

; DelayFrames: b = frames, returns early and sets wSkip if A or START is pressed. Clobbers a, b.
DelayFrames:
.l:
    ld a, [wSkip]
    or a
    ret nz
    call WaitVBlank
    call ConsumePressed
    and (1 << PAD_A) | (1 << PAD_START)
    jr z, .noskip
    ld a, 1
    ld [wSkip], a
    ret
.noskip:
    dec b
    jr nz, .l
    ret

; WaitConfirm: until A or START. Stirs the RNG with press timing so each conversation differs. SELECT opens the inspector.
WaitConfirm:
    call WaitVBlank
    call ConsumePressed
    bit PAD_SELECT, a
    jr nz, .inspect
    and (1 << PAD_A) | (1 << PAD_START)
    jr z, WaitConfirm
    jp StirRng
.inspect:
    call Inspector
    ld a, [wSeqLen]
    cp MODEL_CTX + 1
    ret nc               ; the player chose to be forgotten: no reply left to show
    call RedrawReply
    jr WaitConfirm

; RedrawReply: draws the reply again from the token ids in wSeq, after the inspector replaced the screen. No inference.
RedrawReply:
    ld hl, StrBandNN
    call SetBand
    call ClearText
    ld hl, StrHintNext
    call Hint
    ld a, PROMPT_LEN
.t:
    ld b, a
    ld a, [wSeqLen]
    cp b
    ret z
    ld a, b
    push af
    add a
    ld l, a
    ld h, 0
    ld de, wSeq
    add hl, de
    ld a, [hl+]
    ld [wPickId], a
    ld a, [hl]
    ld [wPickId + 1], a
    call RenderToken
    pop af
    inc a
    jr .t

; StirRng: mixes timing into the sampler seed unless the harness pinned it.
StirRng:
    ld a, [wMB_ForceSeed]
    or a
    ret nz
    ldh a, [rDIV]
    ld b, a
    ld a, [wNarrRng]
    xor b
    ld [wNarrRng], a
    ldh a, [hFrames]
    ld b, a
    ld a, [wNarrRng + 1]
    xor b
    or 1
    ld [wNarrRng + 1], a
    ret

; Blip: a short tone. a = pitch seed. Clobbers a.
Blip:
    and 31
    add $90
    ldh [rNR23], a
    ld a, $B4
    ldh [rNR21], a
    ld a, $62
    ldh [rNR22], a
    ld a, $C7
    ldh [rNR24], a
    ret

; Band: b = row, hl = text, c = column. Fills the row dark and prints.
Band:
    push hl
    push bc
    ld c, 1
    ld a, TILE_BAND
    call FillRows
    pop bc
    pop hl
    jp PrintInvAt

Hint:
    ld b, HINT_ROW
    ld c, 1
    jr Band

; ClearText: blanks the dialogue box and homes the cursor.
ClearText:
    ld b, TEXT_ROW
    ld c, TEXT_ROWS * 2 - 1
    xor a
    call FillRows
    ld b, 9
    ld c, 1
    xor a
    call FillRows
    xor a
    ld [wTextRowN], a
    ld [wTextColN], a
    ret

; ---- Boot and logo ---------------------------------------------------------
BootSequence:
    ld a, ST_INTRO
    call SetState
    xor a
    ld [wSkip], a
    call RobotHide
    call ScreenOff
    call ClearShadow
    ld hl, StrBoot0
    ld b, 2
    ld c, 1
    call PrintAt
    call ScreenOn
    ld b, 20
    call DelayFrames
    ld hl, StrBoot1
    ld b, 5
    ld c, 1
    call PrintAt
    ld b, 14
    call DelayFrames
    ld hl, StrBoot2
    ld b, 7
    ld c, 1
    call PrintAt
    ld b, 14
    call DelayFrames
    ld hl, StrBoot3
    ld b, 9
    ld c, 1
    call PrintAt
    ld b, 14
    call DelayFrames
    ld hl, StrBoot4
    ld b, 12
    ld c, 1
    call PrintAt
    ld b, 20
    call DelayFrames
    call Corrupt
    call ShowLogo
    ld b, 90
    call DelayFrames
    call ConversationScreen
    call RobotRise
    jp IntroLines

; Corrupt: the cartridge "takes over": garbage tiles, flicker and a wobbling picture for a moment.
Corrupt:
    ld c, 60
.f:
    ld a, [wSkip]
    or a
    jr nz, .done
    push bc
    ld d, 6
.g:
    push de
    call Rand8
    and 15
    ld b, a
    call Rand8
    and 15
    add 2
    ld c, a
    call RowPtr
    call Rand8
    and 127
    ld [hl], a
    call MarkRow
    pop de
    dec d
    jr nz, .g
    call Rand8
    and 7
    sub 3
    ldh [rSCX], a
    call Rand8
    and 3
    jr nz, .pal
    ld a, %00011011      ; inverted for a frame
    jr .setpal
.pal:
    ld a, PAL_NORMAL
.setpal:
    ldh [rBGP], a
    ld b, 1
    call DelayFrames
    pop bc
    dec c
    jr nz, .f
.done:
    xor a
    ldh [rSCX], a
    ld a, PAL_NORMAL
    ldh [rBGP], a
    ret

ShowLogo:
    call ScreenOff
    call ClearShadow
    call LogoToShadow
    ld hl, StrGame1
    ld b, 14
    ld c, 2
    call PrintAt
    ld hl, StrGame2
    ld b, 15
    ld c, 0
    call PrintAt
    jp ScreenOn

; ConversationScreen: dialogue box, status panel, robot visible.
ConversationScreen::
    call ScreenOff
    call ClearShadow
    ld hl, StrBandSys
    call SetBand
    call ClearText
    call DrawPanel
    call RobotReset
    ld a, 1
    ld [wRobotOn], a
    jp ScreenOn

; RobotRise: the face climbs out of the bottom of the frame through static.
RobotRise:
    ld a, EXPR_SMUG
    ld [wExpr], a
    ld a, [wSkip]
    or a
    ret nz
    ld a, 64
    ld [wRiseY], a
    ld a, 50
    ld [wGlitch], a
.r:
    ld a, [wRiseY]
    or a
    ret z
    sub 2
    ld [wRiseY], a
    ld b, 1
    call DelayFrames
    ld a, [wSkip]
    or a
    jr z, .r
    xor a
    ld [wRiseY], a
    ld [wGlitch], a
    ret

; IntroLines: fixed text, marked SYSTEM. On later visits, memory changes which lines appear; the model is not involved.
IntroLines:
    ld a, [wReturning]
    or a
    jr nz, .back
    ld de, StrIntroA2
    ld hl, StrIntroA
    call SayFixed
    ld de, StrIntroB2
    ld hl, StrIntroB
    call SayFixed
    ld de, StrIntroC2
    ld hl, StrIntroC
    jp SayFixed
.back:
    ld de, StrBackB
    ld hl, StrBackA
    jp SayFixed

; SayFixed: hl = first line, de = second line. Fixed text, with mouth movement.
SayFixed:
    push de
    push hl
    call ClearText
    pop hl
    ld b, TEXT_ROW
    ld c, TEXT_COL
    call PrintAt
    pop hl
    ld b, TEXT_ROW + 2
    ld c, TEXT_COL
    call PrintAt
    ld a, 40
    ld [wTalk], a
    ld a, 9
    call Blip
    ld b, 110
    xor a
    ld [wSkip], a
    jp DelayFrames

; ---- Status panel ----------------------------------------------------------
SetBand:
    push hl
    ld hl, StrOverride
    ld b, BAND_ROW
    ld c, 1
    call Band
    pop hl
    ld b, BAND_ROW
    ld c, 13
    jp PrintInvAt

DrawPanel::
    ; five-tile respect bar: -8..15 becomes 0..20 quarters
    ld b, 0
    ld c, 8
    xor a
    call FillPanel
    ld hl, StrMood
    ld b, 1
    ld c, PANEL_COL
    call PrintAt
    ld a, [wMood]
    add a
    ld e, a
    ld d, 0
    ld hl, MoodNames
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld b, 2
    ld c, PANEL_COL + 1
    call PrintAt
    ld hl, StrYouAre
    ld b, 4
    ld c, PANEL_COL
    call PrintAt
    ld a, [wRelation]
    add a
    ld e, a
    ld d, 0
    ld hl, RelationNames
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld b, 5
    ld c, PANEL_COL + 1
    call PrintAt
    ; bar
    ld a, [wRespect]
    add 8
    ld b, 6
    ld c, PANEL_COL + 1
    push af
    call RowPtr
    pop af
    ld b, 5
    ld d, a
.bar:
    ld a, d
    cp 4
    jr c, .part
    sub 4
    ld d, a
    ld a, 4
    jr .put
.part:
    ld e, a
    xor a
    ld a, e
    ld d, 0
.put:
    add TILE_BAR0
    ld [hl+], a
    dec b
    jr nz, .bar
    ld b, 6
    jp MarkRow

; FillPanel: blanks the panel on rows b..b+c-1. Clobbers everything.
FillPanel:
.r:
    push bc
    push af
    ld c, PANEL_COL
    call RowPtr
    pop af
    ld d, SCREEN_W - PANEL_COL
.t:
    ld [hl+], a
    dec d
    jr nz, .t
    pop bc
    call MarkRow
    inc b
    dec c
    jr nz, .r
    ret

; ---- Menu ------------------------------------------------------------------
; ReadNav: -> a = pressed buttons, with auto-repeat on a held d-pad. Clobbers b.
ReadNav:
    call WaitVBlank
    ldh a, [hJoyHeld]
    and $F0
    jr nz, .held
    xor a
    ld [wRepeatT], a
    jp ConsumePressed
.held:
    ld a, [wRepeatT]
    inc a
    ld [wRepeatT], a
    cp 20
    jp c, ConsumePressed
    cp 25
    jr c, .quiet
    ld a, 20
    ld [wRepeatT], a
    call ConsumePressed
    ld b, a
    ldh a, [hJoyHeld]
    and $F0
    or b
    ret
.quiet:
    jp ConsumePressed

DrawMenu:
    ld hl, StrBandMove
    ld b, BAND_ROW
    ld c, 1
    call Band
    call ClearText
    ld hl, StrHintMenu
    call Hint
    xor a
.item:
    push af
    ld l, a
    ld h, 0
    add hl, hl
    ld de, ActionNames
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    pop af
    push af
    call MenuPos         ; b, c
    inc c
    call PrintAt
    pop af
    inc a
    cp NUM_MENU
    jr nz, .item
    ret

; MenuPos: a = item -> b = row, c = column of its pointer. Clobbers a.
MenuPos:
    ld b, a
    srl a
    add a
    add TEXT_ROW
    ld c, a              ; row
    ld a, b
    and 1
    ld b, c
    ld c, 0
    ret z
    ld c, 10
    ret

MoveCursor:
    ld a, [wMenuSel]
    call MenuPos
    ld a, c
    add a
    add a
    add a
    add 8
    ld [wCursorX], a
    ld a, b
    add a
    add a
    add a
    add 16
    ld [wCursorY], a
    ld a, TILE_SPR_ARROW
    ld [wCursorTile], a
    ret

; MainMenu: -> wParsed* set from an action or typed text.
MainMenu:
    ld a, ST_MENU
    call SetState
    call ClearParsed
    call DrawMenu
    call MoveCursor
    call ConsumePressed
.loop:
    call ReadNav
    ld b, a
    bit PAD_SELECT, b
    jr z, .noInfo
    call HideCursor
    call Inspector
    jr MainMenu
.noInfo:
    ld a, [wMenuSel]
    ld c, a
    bit PAD_RIGHT, b
    jr z, .l
    ld a, c
    xor 1
    ld c, a
.l:
    bit PAD_LEFT, b
    jr z, .u
    ld a, c
    xor 1
    ld c, a
.u:
    bit PAD_UP, b
    jr z, .d
    ld a, c
    sub 2
    and NUM_MENU - 1
    ld c, a
.d:
    bit PAD_DOWN, b
    jr z, .set
    ld a, c
    add 2
    and NUM_MENU - 1
    ld c, a
.set:
    ld a, c
    ld [wMenuSel], a
    push bc
    call MoveCursor
    pop bc
    ld a, b
    and (1 << PAD_A) | (1 << PAD_START)
    jr z, .loop
    call StirRng
    call HideCursor
    ld a, [wMenuSel]
    cp NUM_ACTIONS
    jr z, .type
    ld e, a
    ld d, 0
    ld hl, ActionIntent
    add hl, de
    ld a, [hl]
    ld [wParsedIntent], a
    ret
.type:
    call Keyboard
    ld a, [wInputLen]
    or a
    jr z, MainMenu       ; backed out
    jp Parse

HideCursor:
    xor a
    ld [wCursorX], a
    ret

ClearParsed:
    xor a
    ld [wParsedTopic], a
    ld [wParsedWord], a
    ld [wParsedName], a
    ld [wParsedLike], a
    ret

; ---- Neural response --------------------------------------------------------
; Respond: memory, prompt, real inference on this CPU, words streaming to the screen.
Respond:
    call ApplyTurn
    call SaveState
    call DrawPanel
    ld hl, StrBandNN
    call SetBand
    ld hl, StrHintThink
    call Hint
    call ClearText
    ld a, [wParsedIntent]
    ld [wMB_Intent], a
    ld a, [wLastTopic]
    ld [wMB_Topic], a
    ld a, [wMood]
    ld [wMB_Mood], a
    ld a, 1
    ld [wThink], a
    ld a, EXPR_THINKING
    ld [wExpr], a
    ld a, ST_THINKING
    call SetState
    call BuildPrompt
    call ModelReset
    call EventTimerStart
    call NeuralGenerate
    jr nc, .ok
    ld hl, wMB_Fallbacks ; hit the length cap: counted, and shown as cut off
    inc [hl]
    ld a, '.'
    call PutChar
    ld a, '.'
    call PutChar
.ok:
    call EventTimerStop
    ld a, [wMB_NumTokens]
    ld [wLastEventTokens], a
    ld hl, wMB_Responses
    inc [hl]
    jr nz, .nc
    inc hl
    inc [hl]
.nc:
    xor a
    ld [wThink], a
    ld a, ST_READ
    call SetState
    ld hl, StrHintNext
    call Hint
    call ConsumePressed  ; presses made while it was talking must not dismiss the reply unread
    call WaitConfirm
    ld a, [wMood]
    cp MOOD_DYING
    ret nz
    jp PowerDown

; OnToken: wPickId = the token just generated. Runs between forward passes, in the UI bank. Clobbers everything.
OnToken:
    ld hl, wMB_TotalTokens
    inc [hl]
    jr nz, .nc
    inc hl
    inc [hl]
.nc:
    ; fall through
; RenderToken: draws wPickId. Used live and to redraw a reply.
RenderToken:
    ld a, [wPickId]
    ld e, a
    ld a, [wPickId + 1]
    ld d, a
    ; EOS: done
    ld a, e
    cp LOW(TOK_EOS)
    jr nz, .notEos
    ld a, d
    cp HIGH(TOK_EOS)
    ret z
.notEos:
    ; emotions come first and set the face: the model chooses this expression
    ld a, e
    sub LOW(TOK_EOS)
    ld a, d
    sbc HIGH(TOK_EOS)
    jr nc, .text
    ld a, e
    sub TOK_FIRST_EMOTION & 255
    ld [wExpr], a
    ld [wMB_Emotion], a
    xor a
    ld [wThink], a
    ld a, ST_STREAMING
    call SetState
    ld a, [wExpr]
    cp EXPR_ANGRY
    jr nz, .e1
    ld a, 30
    ld [wShake], a
    ret
.e1:
    cp EXPR_GLITCHING
    jr nz, .e2
    ld a, 30
    ld [wGlitch], a
    ret
.e2:
    cp EXPR_SURPRISED
    ret nz
    ld a, 10
    ld [wShake], a
    ret
.text:
    ld a, 24
    ld [wTalk], a
    ld a, e
    call Blip
    ; runtime slots print deterministic memory, chosen by the model
    ld a, e
    sub LOW(TOK_FIRST_SLOT)
    ld c, a
    ld a, d
    sbc HIGH(TOK_FIRST_SLOT)
    jr nz, .word
    ld a, c
    cp NUM_SLOTS
    jr nc, .word
    jp PrintSlot
.word:
    ld a, e
    sub LOW(TOK_FIRST_GEN)
    ld l, a
    ld a, d
    sbc HIGH(TOK_FIRST_GEN)
    ld h, a
    add hl, hl
    ld de, WordPtrs
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    jp AppendText

; PrintSlot: a = slot index, in <NAME> <LIKE> <WORD> <NI> <NP> <NT> order.
PrintSlot:
    or a
    jr nz, .s1
    ld a, [wName]
    ld hl, wName
    or a
    jp nz, AppendText
    ld hl, StrHuman
    jp AppendText
.s1:
    dec a
    jr nz, .s2
    ld a, [wLike]
    ld hl, wLike
    or a
    jp nz, AppendText
    ld hl, StrThat
    jp AppendText
.s2:
    dec a
    jr nz, .s3
    ld a, [wWord]
    ld hl, wWord
    or a
    jp nz, AppendText
    ld hl, StrThat
    jp AppendText
.s3:
    dec a
    jr nz, .s4
    ld a, [wInsults]
    jr Number
.s4:
    dec a
    jr nz, .s5
    ld a, [wPraises]
    jr Number
.s5:
    ld a, [wTurns]
; Number: a = 0..99 printed without a leading zero.
Number:
    ld hl, wNumBuf
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
    or a
    jr z, .one
    add '0'
    ld [hl+], a
.one:
    ld a, c
    add '0'
    ld [hl+], a
    xor a
    ld [hl], a
    ld hl, wNumBuf
    ; fall through

; AppendText: hl -> NUL string. Punctuation attaches to the last word, anything else wraps as a unit.
AppendText:
    ld a, [hl]
    cp '.'
    jr z, .raw
    cp ','
    jr z, .raw
    cp '!'
    jr z, .raw
    cp '?'
    jr z, .raw
    cp ':'
    jr z, .raw
    push hl
    ld b, 0
.len:
    ld a, [hl+]
    or a
    jr z, .haveLen
    inc b
    jr .len
.haveLen:
    pop hl
    ld a, [wTextColN]
    or a
    jr z, .raw
    add b
    inc a
    cp TEXT_WIDTH        ; keeps a column free, so punctuation always fits beside its word
    jr c, .space
    call NewLine
    jr .raw
.space:
    push hl
    ld a, ' '
    call PutChar
    pop hl
.raw:
    ld a, [hl+]
    or a
    ret z
    push hl
    call PutChar
    pop hl
    jr .raw

; NewLine: next line, scrolling the box if it is full. Text can never overflow the box.
NewLine:
    xor a
    ld [wTextColN], a
    ld a, [wTextRowN]
    inc a
    cp TEXT_ROWS
    jr c, .ok
    push hl
    ld hl, wBgMap + (TEXT_ROW + 2) * SCREEN_W
    ld de, wBgMap + TEXT_ROW * SCREEN_W
    ld bc, (TEXT_ROWS * 2 - 3) * SCREEN_W
    call MemCopy
    ld b, TEXT_ROW + (TEXT_ROWS - 1) * 2
    ld c, 1
    xor a
    call FillRows
    ld b, TEXT_ROW
    REPT TEXT_ROWS - 1
    call MarkRow
    inc b
    inc b
    ENDR
    pop hl
    ld a, TEXT_ROWS - 1
.ok:
    ld [wTextRowN], a
    ret

; PutChar: a = ASCII at the cursor. Clobbers a, bc, de, hl.
PutChar:
    push af
    ld a, [wTextColN]
    cp TEXT_WIDTH
    call nc, NewLine
    ld a, [wTextRowN]
    add a
    add TEXT_ROW
    ld b, a
    ld a, [wTextColN]
    add TEXT_COL
    ld c, a
    call RowPtr
    pop af
    sub $20
    ld [hl], a
    call MarkRow
    ld hl, wTextColN
    inc [hl]
    ret

; ---- Power down --------------------------------------------------------------
PowerDown:
    ld a, ST_POWERDOWN
    call SetState
    xor a
    ld [wSkip], a
    ld a, EXPR_DEFEATED
    ld [wExpr], a
    ld a, 40
    ld [wGlitch], a
    ld hl, StrBandSys
    call SetBand
    ld de, StrDownB
    ld hl, StrDownA
    call SayFixed
    ; fade through the palette
    ld a, %11111001
    ldh [rBGP], a
    ldh [rOBP0], a
    ld b, 16
    call WaitFrames
    ld a, %11111110
    ldh [rBGP], a
    ldh [rOBP0], a
    ld b, 16
    call WaitFrames
    ld a, %11111111
    ldh [rBGP], a
    ldh [rOBP0], a
    ld b, 60
    call WaitFrames
    call RobotHide
    ; memory survives, as it would across a real power cycle
    xor a
    ld [wShutdowns], a
    ld [wBored], a
    ld a, 5
    ld [wAnger], a
    call SaveState
    ld a, PAL_NORMAL
    ldh [rBGP], a
    ld a, OBJ_PAL
    ldh [rOBP0], a
    xor a
    ld [wSkip], a
    call ShowLogo
    ld b, 40
    call DelayFrames
    call ConversationScreen
    call RobotRise
    xor a
    ld [wSkip], a
    ld de, StrThatEmpty
    ld hl, StrUp
    jp SayFixed
StrThatEmpty: db 0

; ---- Keyboard ------------------------------------------------------------------
KeyGrid:
    db "ABCDEFGHIJ"
    db "KLMNOPQRST"
    db "UVWXYZ',.?"
    db "0123456789"
    db "!-", KEY_SPACE, KEY_SPACE, KEY_SPACE, KEY_DEL, KEY_DEL, KEY_DEL, KEY_OK, KEY_OK

KeyCell:
    ; a = row*10+col, -> a = key value. Clobbers de, hl.
    ld e, a
    ld d, 0
    ld hl, KeyGrid
    add hl, de
    ld a, [hl]
    ret

DrawKeyboard:
    call ScreenOff
    call ClearShadow
    ld hl, StrSaySome
    ld b, 0
    ld c, 1
    call Band
    call RobotHide
    ; the key rows
    ld b, KEY_FIRST_ROW
    ld c, 0
.row:
    ld e, 0
.col:
    push bc
    push de
    ld a, c
    add a
    add a
    add c
    add a
    add e                ; row * 10 + col
    cp 40
    jr nc, .skip
    call KeyCell
    push af
    pop af
    pop de
    pop bc
    push bc
    push de
    push af
    ld a, e
    add a
    inc a
    ld c, a
    call RowPtr
    pop af
    sub $20
    ld [hl], a
    jr .after
.skip:
.after:
    pop de
    pop bc
    inc e
    ld a, e
    cp 10
    jr nz, .col
    inc b
    inc b
    inc c
    ld a, c
    cp 4
    jr nz, .row
    ld hl, StrKeyLast
    ld b, KEY_FIRST_ROW + 8
    ld c, 1
    call PrintAt
    ld hl, StrHintKeys
    call Hint
    jp ScreenOn

; DrawInput: the two input lines and the caret. Clobbers everything.
DrawInput:
    ld b, 2
    ld c, 1
    call RowPtr
    ld d, h
    ld e, l
    ld hl, wInput
    ld a, [wInputLen]
    ld b, a
    ld c, TEXT_WIDTH * 2
.ch:
    ; line break after TEXT_WIDTH characters
    ld a, c
    cp TEXT_WIDTH
    jr nz, .same
    push hl
    ld hl, (2 * SCREEN_W) - TEXT_WIDTH
    add hl, de
    ld d, h
    ld e, l
    pop hl
.same:
    ld a, b
    or a
    jr z, .blank
    dec b
    ld a, [hl+]
    sub $20
    jr .put
.blank:
    ld a, [wInputLen]
    cpl
    add TEXT_WIDTH * 2 + 1
    cp c
    ld a, 0
    jr nz, .put
    ldh a, [hFrames]
    and 16
    ld a, 0
    jr z, .put
    ld a, TILE_CARET
.put:
    ld [de], a
    inc de
    dec c
    jr nz, .ch
    ld b, 2
    call MarkRow
    ld b, 4
    jp MarkRow

KeyCursor:
    ld a, [wKeyCol]
    add a
    inc a
    add a
    add a
    add a
    add 8
    ld [wCursorX], a
    ld a, [wKeyRow]
    add a
    add KEY_FIRST_ROW
    add a
    add a
    add a
    add 16 - 1
    ld [wCursorY], a
    ld a, TILE_SPR_CURSOR
    ld [wCursorTile], a
    ret

; Keyboard: edits wInput. wInputLen = 0 on return means the player backed out.
Keyboard:
    ld a, ST_KEYBOARD
    call SetState
    xor a
    ld [wInputLen], a
    ld [wKeyRow], a
    ld [wKeyCol], a
    call DrawKeyboard
    call ConsumePressed
.loop:
    call KeyCursor
    call DrawInput
    call ReadNav
    ld b, a
    ld a, [wKeyCol]
    ld c, a
    ld a, [wKeyRow]
    ld d, a
    bit PAD_LEFT, b
    jr z, .r
    ld a, c
    dec a
    cp 10
    jr c, .lk
    ld a, 9
.lk:
    ld c, a
.r:
    bit PAD_RIGHT, b
    jr z, .uk
    ld a, c
    inc a
    cp 10
    jr c, .rk
    xor a
.rk:
    ld c, a
.uk:
    bit PAD_UP, b
    jr z, .dk
    ld a, d
    dec a
    cp 5
    jr c, .uk2
    ld a, 4
.uk2:
    ld d, a
.dk:
    bit PAD_DOWN, b
    jr z, .store
    ld a, d
    inc a
    cp 5
    jr c, .dk2
    xor a
.dk2:
    ld d, a
.store:
    ld a, c
    ld [wKeyCol], a
    ld a, d
    ld [wKeyRow], a
    bit PAD_START, b
    jr nz, .send
    bit PAD_B, b
    jr nz, .del
    bit PAD_SELECT, b
    jr nz, .space
    bit PAD_A, b
    jp z, .loop
    ; pressed a key
    ld a, d
    add a
    add a
    add d
    add a
    add c
    call KeyCell
    cp KEY_OK
    jr z, .send
    cp KEY_DEL
    jr z, .del
    cp KEY_SPACE
    jr nz, .put
.space:
    ld a, ' '
.put:
    ld c, a
    ld a, [wInputLen]
    cp MAX_INPUT
    jp nc, .loop
    ld e, a
    ld d, 0
    ld hl, wInput
    add hl, de
    ld [hl], c
    ld hl, wInputLen
    inc [hl]
    jp .loop
.del:
    ld a, [wInputLen]
    or a
    jr z, .out           ; B on an empty line goes back
    dec a
    ld [wInputLen], a
    jp .loop
.send:
    ld a, [wInputLen]
    or a
    jr z, .out
.out:
    call HideCursor
    jp ConversationScreen

; ---- Inspector ---------------------------------------------------------------
; Inspector: fixed labels with live numbers: the ids the model just generated, and how long it took.
Inspector:
    ld a, [wMB_State]
    push af
    ld a, ST_INSPECT
    call SetState
    xor a
    ld [wWipeArm], a
    call DrawInspector
.w:
    call WaitVBlank
    call ConsumePressed
    bit PAD_B, a
    jr nz, .done
    bit PAD_SELECT, a
    jr nz, .done
    bit PAD_A, a
    jr nz, .done
    bit PAD_START, a
    jr z, .w
    ld a, [wWipeArm]
    or a
    jr nz, .wipe
    inc a
    ld [wWipeArm], a
    ld hl, StrHintWipe
    call Hint
    jr .w
.wipe:
    call WipeSave
    ld a, $FF
    ld [wSeqLen], a
.done:
    call ConversationScreen
    pop af
    jp SetState

DrawInspector:
    call ScreenOff
    call ClearShadow
    call RobotHide
    ld hl, StrInspect
    ld b, 0
    ld c, 1
    call Band
    ld hl, StrInsCpu
    ld b, 2
    ld c, 0
    call PrintAt
    ld hl, StrModelParams
    ld b, 3
    ld c, 1
    call PrintAt
    ld hl, StrInsTok
    ld b, 5
    ld c, 1
    call PrintAt
    ld b, 5
    ld c, 8
    call RowPtr
    ld a, [wLastEventTokens]
    ld e, a
    ld d, 0
    call PrintDec16
    ld hl, StrInsFrm
    ld b, 6
    ld c, 1
    call PrintAt
    ld b, 6
    ld c, 8
    call RowPtr
    ld a, [wLastEventFrames]
    ld e, a
    ld a, [wLastEventFrames + 1]
    ld d, a
    call PrintDec16
    ld hl, StrInsIds
    ld b, 8
    ld c, 1
    call PrintAt
    ; generated ids, four per row. The prompt is available to the harness in wSeq too.
    ld a, [wSeqLen]
    cp MODEL_CTX + 1
    jr nc, .noIds
    sub PROMPT_LEN
    jr c, .noIds
    jr z, .noIds
    ld [wIdsLeft], a
    xor a
    ld [wIdsDone], a
.id:
    ld a, [wIdsDone]
    ld c, a
    srl a
    srl a
    cp 7
    jr nc, .noIds
    add 9
    ld b, a
    ld a, c
    and 3
    ld c, a
    add a
    add a
    add c
    inc a
    ld c, a              ; column 1 + 5 * n
    call RowPtr
    push hl
    ld a, [wIdsDone]
    add PROMPT_LEN
    ld l, a
    ld h, 0
    add hl, hl
    ld de, wSeq
    add hl, de
    ld a, [hl+]
    ld e, a
    ld d, [hl]
    pop hl
    push hl
    push de
    call PrintDec16Short
    pop de
    pop hl
    ld hl, wIdsDone
    inc [hl]
    ld hl, wIdsLeft
    dec [hl]
    jr nz, .id
.noIds:
    ld hl, StrHintBack
    call Hint
    jp ScreenOn

; PrintDec16Short: de < 1000, hl = shadow ptr. Three digits. Clobbers a, bc, de, hl.
PrintDec16Short:
    ld bc, -100
    call .d
    ld bc, -10
    call .d
    ld bc, -1
.d:
    ld a, -1
    push hl
    ld h, d
    ld l, e
.s:
    inc a
    ld d, h
    ld e, l
    add hl, bc
    jr c, .s
    pop hl
    add '0' - $20
    ld [hl+], a
    ret

SECTION "ui_vars4", WRAM0
wIdsLeft: ds 1
wIdsDone: ds 1
ENDC
