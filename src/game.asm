; game.asm - deterministic world. Truth lives here; the neural model only narrates outcomes.
; Exact behaviour is mirrored by reference/game.py and checked by tests/test_rom_game.py.
INCLUDE "constants.inc"

SECTION "game_vars", WRAM0, ALIGN[8]
wRng::       ds 2            ; little-endian LFSR state
wRoom::      ds 1
wLives::     ds 1
wHasKey::    ds 1
wHasLamp::   ds 1
wTurn::      ds 1
wLampRoom::  ds 1
wAction::    ds 1
wOutcome::   ds 1
wPrevRoom::  ds 1
wCycle::     ds 7
wExits::     ds 8 * 3        ; [room][L,R,F]

SECTION "game_code", ROM0
; RngByte: advances the LFSR eight bits; returns low byte in a. Preserves bc, de, hl.
RngByte::
    push bc
    ld a, [wRng]
    ld c, a
    ld a, [wRng + 1]
    ld b, a
    REPT 8
    srl b
    rr c
    jr nc, :+
    ld a, b
    xor $B4
    ld b, a
:
    ENDR
    ld a, c
    ld [wRng], a
    ld a, b
    ld [wRng + 1], a
    ld a, c
    pop bc
    ret

; ModC: a = a mod c. Clobbers flags.
ModC:
    cp c
    ret c
    sub c
    jr ModC

; ExitPtr: a = room, b = dir -> hl = &wExits[room][dir]. Clobbers a.
ExitPtr:
    ld h, a
    add a
    add h                ; room * 3
    add b
    add LOW(wExits)
    ld l, a
    ld a, HIGH(wExits)
    adc 0
    ld h, a
    ret

; GenWorld: de = seed. Builds wCycle, wLampRoom, wExits and resets the run. Clobbers everything.
GenWorld::
    ld a, d
    or e
    jr nz, .seeded
    ld e, 1
.seeded:
    ld a, e
    ld [wRng], a
    ld a, d
    ld [wRng + 1], a
    ; cycle = FOREST, shuffled(MARSH RIVER RUINS SHRINE CAVE), GATE
    ld hl, wCycle
    xor a
    ld b, 7
.init:
    ld [hl+], a
    inc a
    dec b
    jr nz, .init
    ; Fisher-Yates over wCycle[1..5]: i = 4..1 indexes order[]
    ld b, 4
.shuffle:
    call RngByte
    ld c, b
    inc c
    call ModC            ; j
    ; swap order[b], order[a]
    ld hl, wCycle + 1
    add l
    ld l, a
    ld d, h
    ld e, l              ; de = &order[j]
    ld hl, wCycle + 1
    ld a, b
    add l
    ld l, a              ; hl = &order[i]
    ld a, [de]
    ld c, [hl]
    ld [hl], a
    ld a, c
    ld [de], a
    dec b
    jr nz, .shuffle
    ; cave index
    ld hl, wCycle
    ld c, 0
.find:
    ld a, [hl+]
    cp ROOM_CAVE
    jr z, .found
    inc c
    jr .find
.found:
    push bc              ; c = cave index
    call RngByte
    call ModC
    ld hl, wCycle
    add l
    ld l, a
    ld a, [hl]
    ld [wLampRoom], a
    ; exits: clear to wall
    ld hl, wExits
    ld b, 8 * 3
    ld a, WALL
.wall:
    ld [hl+], a
    dec b
    jr nz, .wall
    ; for i in 0..6
    ld c, 0
.each:
    call BuildExitsFor
    inc c
    ld a, c
    cp 7
    jr nz, .each
    ld a, ROOM_FOREST
    ld [wExits + ROOM_GATE * 3 + ACT_LEFT], a
    pop bc               ; c = cave index
    ld a, c
    cp 2
    jr c, .noback
    dec c
    ld hl, wCycle
    ld a, l
    add c
    ld l, a
    ld a, [hl]
    ld b, ACT_RIGHT
    call ExitPtr
    ld [hl], ROOM_FOREST
.noback:
    ; run state
    ld a, ROOM_FOREST
    ld [wRoom], a
    ld a, START_LIVES
    ld [wLives], a
    xor a
    ld [wHasKey], a
    ld [wHasLamp], a
    ld [wTurn], a
    ret

; BuildExitsFor: c = cycle index. Preserves c. Clobbers a, b, de, hl.
BuildExitsFor:
    ld hl, wCycle
    ld a, l
    add c
    ld l, a
    ld d, [hl]           ; d = room
    ; forward
    ld a, c
    cp 6
    ld e, ROOM_TOWER
    jr z, .fw
    inc hl
    ld e, [hl]
.fw:
    ld a, d
    ld b, ACT_FORWARD
    push de
    call ExitPtr
    pop de
    ld [hl], e
    ld b, ACT_LEFT
    call .side
    ld b, ACT_RIGHT
.side:
    call RngByte
    and 3
    ld e, a              ; roll
    call RngByte
    push bc
    ld c, 7
    call ModC
    pop bc
    ld hl, wCycle
    add l
    ld l, a
    ld a, [hl]           ; target
    cp d
    jr z, .wall          ; target == room
    ld h, a
    ld a, e
    or a
    ld a, h
    jr nz, .set
.wall:
    ld a, WALL
.set:
    push af
    ld a, d
    push de
    call ExitPtr
    pop de
    pop af
    ld [hl], a
    ret

; GameStep: wAction = action. Updates truth and sets wOutcome. Clobbers everything.
GameStep::
    ld a, [wRoom]
    ld [wPrevRoom], a
    cp ROOM_TOWER
    jr nz, .notower
    ld a, [wAction]
    cp ACT_FORWARD
    ld b, OUT_WIN
    jp z, .set
    cp ACT_SEARCH
    ld b, OUT_HURT
    jp z, .set
    ld b, OUT_BLOCK
    jp .set
.notower:
    ld a, [wAction]
    cp ACT_SEARCH
    jr nz, .move
    ; search
    ld a, [wRoom]
    ld c, a
    ld a, [wLampRoom]
    cp c
    jr nz, .nolamp
    ld a, [wHasLamp]
    or a
    jr nz, .nolamp
    ld a, 1
    ld [wHasLamp], a
    ld b, OUT_LAMP
    jr .set
.nolamp:
    ld a, c
    cp ROOM_CAVE
    jr nz, .nokey
    ld a, [wHasKey]
    or a
    jr nz, .nokey
    ld a, 1
    ld [wHasKey], a
    ld b, OUT_KEY
    jr .set
.nokey:
    ld b, OUT_NOTHING
    ld a, c
    cp ROOM_RUINS
    jr nz, .set
    call RngByte
    and 7
    jr nz, .set
    ld b, OUT_HURT
    jr .set
.move:
    ld b, a              ; dir
    ld a, [wRoom]
    call ExitPtr
    ld a, [hl]
    ld c, a              ; target
    cp WALL
    ld b, OUT_BLOCK
    jr z, .set
    cp ROOM_CAVE
    jr nz, .notdark
    ld a, [wHasLamp]
    or a
    ld b, OUT_DARK
    jr z, .set
.notdark:
    ld a, [wRoom]
    cp ROOM_GATE
    jr nz, .notgate
    ld a, [wAction]
    cp ACT_FORWARD
    jr nz, .notgate
    ld a, [wHasKey]
    or a
    ld b, OUT_LOCKED
    jr z, .set
    ld a, ROOM_TOWER
    ld [wRoom], a
    ld b, OUT_OPEN
    jr .set
.notgate:
    ld a, c
    cp ROOM_MARSH
    jr z, .hazard
    cp ROOM_RIVER
    jr nz, .go
.hazard:
    call RngByte
    and 7
    ld b, OUT_HURT
    jr z, .set
.go:
    ld a, c
    ld [wRoom], a
    ld b, OUT_MOVE
.set:
    ld a, b
    cp OUT_HURT
    jr nz, .store
    ld hl, wLives
    dec [hl]
    jr nz, .store
    ld a, OUT_LOSE
.store:
    ld [wOutcome], a
    ld hl, wTurn
    inc [hl]
    ; fall through
; SyncMailbox: mirrors game truth to the debug mailbox. Clobbers a.
SyncMailbox::
    ld a, [wTurn]
    ld [wMB_Turn], a
    ld a, [wRoom]
    ld [wMB_Room], a
    ld a, [wLives]
    ld [wMB_Lives], a
    call InvCode
    ld [wMB_Inv], a
    ld a, [wAction]
    ld [wMB_Action], a
    ld a, [wOutcome]
    ld [wMB_Outcome], a
    ret

; InvCode: a = 0 none, 1 lamp, 2 lamp+key.
InvCode::
    ld a, [wHasKey]
    or a
    jr z, .k
    ld a, 2
    ret
.k:
    ld a, [wHasLamp]
    ret
