; game.asm - the branching story engine. Truth lives here; the neural model only narrates what happened.
; Tables come from reference/story.py via tools/rom_layout.py, so ROM and reference cannot drift apart.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

IF !DEF(TEST_ROM)
SECTION "game_vars", WRAM0
wScene::      ds 1
wFlags::      ds 1
wWounds::     ds 1
wTurn::       ds 1
wPrevArt::    ds 1
wBeatTok::    ds 1           ; token id of what just happened
wFate::       ds 1           ; 1 if this choice killed the player
wChoiceId::   ds 1
wNumChoices:: ds 1
wChoices::    ds MAX_CHOICES ; ids of the choices visible now
wEndMask::    ds 1           ; endings seen since power-on

SECTION "game_code", ROM0
; ScenePtr: a = scene -> hl = its record. Clobbers a, de.
ScenePtr::
    ld l, a
    ld h, 0
    ld d, h
    ld e, l
    add hl, hl
    add hl, hl
    add hl, hl
    ld a, l
    sub e
    ld l, a
    ld a, h
    sbc d
    ld h, a              ; scene * 7
    ld de, StoryScenes
    add hl, de
    ret

; ChoicePtr: a = choice id -> hl = its record. Clobbers a, de.
ChoicePtr::
    ld l, a
    ld h, 0
    ld d, h
    ld e, l
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, de           ; id * 9
    ld de, StoryChoices
    add hl, de
    ret

; StartStory: resets the run to the first scene. Clobbers a.
StartStory::
    ld a, SCENE_START
    ld [wScene], a
    xor a
    ld [wFlags], a
    ld [wWounds], a
    ld [wTurn], a
    ld [wFate], a
    ld [wBeatTok], a
    ld [wChoiceId], a
    ret

; CollectChoices: fills wChoices with the choices the current flags allow. Clobbers everything.
CollectChoices::
    ld a, [wScene]
    call ScenePtr
    inc hl
    inc hl
    inc hl
    inc hl               ; skip title, art, act
    ld a, [hl+]
    ld b, a              ; number of authored choices
    ld c, [hl]           ; first choice id
    xor a
    ld [wNumChoices], a
    ld a, b
    or a
    ret z
.next:
    push bc
    ld a, c
    call ChoicePtr
    inc hl
    inc hl               ; skip label
    ld a, [wFlags]
    ld e, a
    ld a, [hl+]          ; requires
    ld d, a
    and e
    cp d
    jr nz, .skip
    ld a, [hl]           ; forbids
    and e
    jr nz, .skip
    pop bc
    push bc
    ld hl, wChoices
    ld a, [wNumChoices]
    add l
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld [hl], c
    ld hl, wNumChoices
    inc [hl]
.skip:
    pop bc
    inc c
    dec b
    jr nz, .next
    ret

; ApplyChoice: a = choice id. Updates flags and wounds, moves to the next scene, sets beat and fate.
ApplyChoice::
    ld [wChoiceId], a
    call ChoicePtr
    inc hl
    inc hl
    inc hl
    inc hl               ; sets
    ld a, [wFlags]
    or [hl]
    inc hl
    ld e, a              ; flags | sets
    ld a, [hl+]          ; clears
    cpl
    and e
    ld [wFlags], a
    ld a, [wWounds]
    add [hl]
    inc hl
    ld [wWounds], a
    ld d, [hl]           ; next scene
    inc hl
    ld a, [hl]
    ld [wBeatTok], a
    ld a, [wWounds]
    cp MAX_WOUNDS
    ld a, 0
    jr c, .alive
    ld d, SCENE_DEATH
    inc a
.alive:
    ld [wFate], a
    ld a, d
    ld [wScene], a
    ld hl, wTurn
    inc [hl]
    ; fall through
; SyncMailbox: mirrors game truth for the harness. Clobbers a.
SyncMailbox::
    ld a, [wTurn]
    ld [wMB_Turn], a
    ld a, [wScene]
    ld [wMB_Room], a
    ld a, [wWounds]
    ld [wMB_Lives], a
    ld a, [wFlags]
    ld [wMB_Inv], a
    ld a, [wChoiceId]
    ld [wMB_Action], a
    ld a, [wBeatTok]
    ld [wMB_Outcome], a
    ret
ENDC
