; convo.asm - conversation memory, deterministic. Same rules as reference/conversation.py apply_turn and the mood functions.
; None of this changes a model weight. It decides which structured prompt the model receives.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "convo_vars", WRAM0
wStateStart::
wAnger::       ds 1
wRespect::     ds 1          ; signed
wBored::       ds 1
wInsults::     ds 1
wPraises::     ds 1
wTurns::       ds 1
wShutdowns::   ds 1
wLastIntent::  ds 1
wLastTopic::   ds 1
wTopicCursor:: ds 1
wName::        ds SLOT_LEN + 1
wLike::        ds SLOT_LEN + 1
wWord::        ds SLOT_LEN + 1
wStateEnd::
wRepeat::      ds 1          ; 1 if this turn repeated the previous intent
wMood::        ds 1
wRelation::    ds 1

SECTION "convo_code", ROMX, BANK[UI_BANK]
; StateReset: a brand new relationship.
StateReset::
    ld hl, wStateStart
    ld b, wStateEnd - wStateStart
    xor a
.c:
    ld [hl+], a
    dec b
    jr nz, .c
    ld a, 2
    ld [wAnger], a
    ld a, 255
    ld [wLastIntent], a
    ret

; ClampAdd: a = value, b = signed delta, c = maximum, with a floor of 0. -> a.
ClampAdd:
    add b
    bit 7, a
    jr z, .notNeg
    xor a
    ret
.notNeg:
    cp c
    ret c
    ld a, c
    ret

; SatInc: hl -> counter, saturating at 99.
SatInc:
    ld a, [hl]
    cp 99
    ret z
    inc [hl]
    ret

; ApplyTurn: wParsedIntent and friends -> memory for this turn, then mood, relation and repeat. Clobbers everything.
ApplyTurn::
    ld a, [wParsedIntent]
    ld c, a
    ld a, [wLastIntent]
    cp c
    ld a, 0
    jr nz, .notRep
    inc a
.notRep:
    ld [wRepeat], a
    ; effects
    ld a, c
    add a
    add c
    ld e, a
    ld d, 0
    ld hl, IntentEffects
    add hl, de
    ld a, [hl+]
    ld b, a
    push hl
    ld a, [wAnger]
    ld c, 15
    call ClampAdd
    ld [wAnger], a
    pop hl
    ld a, [hl+]
    ld b, a
    push hl
    ; respect is -8..15
    ld a, [wRespect]
    add b
    bit 7, a
    jr z, .rPos
    cp -8
    jr nc, .rSet
    ld a, -8
    jr .rSet
.rPos:
    cp 15
    jr c, .rSet
    ld a, 15
.rSet:
    ld [wRespect], a
    pop hl
    ld b, [hl]           ; bored delta
    ld a, [wRepeat]
    or a
    jr z, .notBoredRep
    ld b, 2
    jr .boredApply
.notBoredRep:
    dec b
.boredApply:
    ld a, [wBored]
    ld c, 7
    call ClampAdd
    ld [wBored], a
    ; counters
    ld a, [wParsedIntent]
    cp INTENT_INSULT
    jr nz, .ni
    ld hl, wInsults
    call SatInc
.ni:
    ld a, [wParsedIntent]
    cp INTENT_PRAISE
    jr nz, .np
    ld hl, wPraises
    call SatInc
.np:
    ld hl, wTurns
    call SatInc
    ld a, [wParsedIntent]
    cp INTENT_SHUTDOWN
    jr z, .sd
    xor a
    ld [wShutdowns], a
    jr .sdDone
.sd:
    ld hl, wShutdowns
    inc [hl]
.sdDone:
    ; topic
    ld a, [wParsedTopic]
    ld b, a
    or a
    jr nz, .topicDone
    ld a, [wParsedIntent]
    cp INTENT_FOLLOW
    jr nz, .notFollow
    ld a, [wLastTopic]
    ld b, a
    jr .topicDone
.notFollow:
    cp INTENT_TALK
    jr z, .rotate
    cp INTENT_QUESTION
    jr nz, .topicDone
.rotate:
    ld a, [wTopicCursor]
    inc a
    cp NUM_GENERAL_TOPICS + 1
    jr c, .curOk
    xor a
.curOk:
    ld [wTopicCursor], a
    or a
    jr z, .topicDone
    add FIRST_GENERAL_TOPIC - 1
    ld b, a
.topicDone:
    ld a, b
    ld [wLastTopic], a
    ld a, [wParsedIntent]
    ld [wLastIntent], a
    ; facts
    ld a, [wParsedName]
    or a
    jr z, .noName
    ld hl, wParsedName
    ld de, wName
    call CopySlot
.noName:
    ld a, [wParsedLike]
    or a
    jr z, .noLike
    ld hl, wParsedLike
    ld de, wLike
    call CopySlot
.noLike:
    ; only this turn's word, so an old one can't turn up in a later reply
    ld hl, wParsedWord
    ld de, wWord
    call CopySlot
    call UpdateMood
    ret

CopySlot:
    ld b, SLOT_LEN + 1
.c:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .c
    ret

; UpdateMood: wMood, wRelation from memory.
UpdateMood::
    ld a, [wRespect]
    bit 7, a
    jr z, .relPos
    cp -2
    ld b, 0
    jr c, .relSet        ; -3 or lower is ENEMY
    ld b, 1
    jr .relSet
.relPos:
    ld b, 1
    cp 3
    jr c, .relSet
    ld b, 2
    cp 8
    jr c, .relSet
    ld b, 3
.relSet:
    ld a, b
    ld [wRelation], a
    ld a, [wShutdowns]
    cp SHUTDOWN_LIMIT
    ld b, MOOD_DYING
    jr nc, .set
    ld a, [wLastIntent]
    cp INTENT_THREAT
    ld b, MOOD_WARY
    jr z, .set
    cp INTENT_SHUTDOWN
    jr z, .set
    ld a, [wAnger]
    cp 8
    ld b, MOOD_ANGRY
    jr nc, .set
    ld a, [wBored]
    cp 4
    ld b, MOOD_BORED
    jr nc, .set
    ld a, [wLastIntent]
    ld b, MOOD_AMUSED
    cp INTENT_JOKE
    jr z, .set
    cp INTENT_PRAISE
    jr z, .set
    ld a, [wRespect]
    bit 7, a
    ld b, MOOD_SMUG
    jr nz, .set
    cp 5
    jr c, .set
    ld b, MOOD_AMUSED
.set:
    ld a, b
    ld [wMood], a
    ret

; BuildPrompt: wSeq/wSeqLen from memory. <BOS> MOOD RELATION HISTORY REPEAT FACTS INTENT TOPIC <SAY>. Clobbers everything.
BuildPrompt::
    ld hl, wSeq
    ld de, TOK_BOS
    call .put
    ld a, [wMood]
    ld de, TOK_M0
    call .putA
    ld a, [wRelation]
    ld de, TOK_R0
    call .putA
    ; history: 0 NEW, 1 RUDE, 2 NICE, 3 MIXED
    ld a, [wPraises]
    cp 2
    ld a, 0
    jr c, .np
    ld a, 2
.np:
    ld b, a
    ld a, [wInsults]
    cp 2
    ld a, b
    jr c, .ni
    inc a
.ni:
    ld de, TOK_H0
    call .putA
    ld a, [wRepeat]
    ld de, TOK_P0
    call .putA
    ; facts: 0 NONE, 1 NAME, 2 LIKE, 3 BOTH
    ld a, [wLike]
    or a
    ld a, 0
    jr z, .nl
    ld a, 2
.nl:
    ld b, a
    ld a, [wName]
    or a
    ld a, b
    jr z, .nn
    inc a
.nn:
    ld de, TOK_F0
    call .putA
    ld a, [wLastIntent]
    ld de, TOK_I0
    call .putA
    ld a, [wLastTopic]
    ld de, TOK_T0
    call .putA
    ld de, TOK_SAY
    call .put
    ld a, PROMPT_LEN
    ld [wSeqLen], a
    ret
.putA:
    add e
    ld e, a
    ld a, d
    adc 0
    ld d, a
.put:
    ld a, e
    ld [hl+], a
    ld a, d
    ld [hl+], a
    ret

; ---- Cartridge RAM. Enabled only for the few cycles it is used. ----
DEF SAVE_SIZE EQU wStateEnd - wStateStart
SECTION "sram", SRAM[$A000]
sMagic:  ds 4
sState:  ds SAVE_SIZE
sCheck:  ds 1

SECTION "save_code", ROMX, BANK[UI_BANK]
SaveMagic: db "OVR1"

; SaveState: writes memory and a checksum to cartridge RAM. Clobbers everything.
SaveState::
    ld a, $0A
    ld [MBC5_RAMG], a
    xor a
    ld [MBC5_RAMB], a
    ld hl, SaveMagic
    ld de, sMagic
    ld b, 4
.m:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .m
    ld hl, wStateStart
    ld de, sState
    ld b, SAVE_SIZE
    ld c, $5A
.s:
    ld a, [hl+]
    ld [de], a
    inc de
    add c
    ld c, a
    dec b
    jr nz, .s
    ld a, c
    ld [sCheck], a
    xor a
    ld [MBC5_RAMG], a
    ret

; LoadState: -> carry set if a valid save was restored. A bad save starts fresh. Clobbers everything.
LoadState::
    ld a, $0A
    ld [MBC5_RAMG], a
    xor a
    ld [MBC5_RAMB], a
    ld hl, SaveMagic
    ld de, sMagic
    ld b, 4
.m:
    ld a, [de]
    cp [hl]
    jr nz, .bad
    inc de
    inc hl
    dec b
    jr nz, .m
    ld hl, sState
    ld b, SAVE_SIZE
    ld c, $5A
.sum:
    ld a, [hl+]
    add c
    ld c, a
    dec b
    jr nz, .sum
    ld a, [sCheck]
    cp c
    jr nz, .bad
    ld hl, sState
    ld de, wStateStart
    ld b, SAVE_SIZE
.s:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .s
    xor a
    ld [MBC5_RAMG], a
    scf
    ret
.bad:
    xor a
    ld [MBC5_RAMG], a
    and a
    ret

; WipeSave: forgets the player, then starts a new relationship. Clobbers everything.
WipeSave::
    ld a, $0A
    ld [MBC5_RAMG], a
    xor a
    ld [MBC5_RAMB], a
    ld [sMagic], a
    ld [MBC5_RAMG], a
    call StateReset
    jp UpdateMood
