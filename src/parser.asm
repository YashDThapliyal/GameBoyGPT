; parser.asm - typed text to intent, topic and facts. Same rules as reference/conversation.py parse().
; This recognizes cue words and two sentence openings. It does not understand language, and it says so when it fails.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

DEF MAX_WORDS EQU 8
DEF REC_SIZE EQU 11
DEF FLAG_STOP EQU 1
DEF FLAG_NEG EQU 2
DEF FLAG_QUESTION EQU 4

SECTION "parser_vars", WRAM0
wInput::     ds MAX_INPUT + 1
wInputLen::  ds 1
wWords:      ds MAX_WORDS * SLOT_LEN
wWordLen:    ds MAX_WORDS
wWordCue:    ds MAX_WORDS
wWordTopic:  ds MAX_WORDS
wWordFlags:  ds MAX_WORDS
wWordCount:  ds 1
wParsedIntent:: ds 1
wParsedTopic::  ds 1
wParsedWord::   ds SLOT_LEN + 1
wParsedName::   ds SLOT_LEN + 1
wParsedLike::   ds SLOT_LEN + 1

SECTION "parser_code", ROMX, BANK[UI_BANK]
; WordPtr: a = index -> hl = &wWords[a]. Clobbers a, de.
WordPtr:
    add a
    add a
    add a
    ld e, a
    ld d, 0
    ld hl, wWords
    add hl, de
    ret

; SplitWords: wInput -> wWords, cut to SLOT_LEN and MAX_WORDS. Apostrophes vanish, other non-alphanumerics separate.
SplitWords:
    ld hl, wWords
    ld bc, MAX_WORDS * SLOT_LEN + MAX_WORDS
.clr:
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .clr
    xor a
    ld [wWordCount], a
    ld a, [wInputLen]
    cp MAX_INPUT + 1
    jr c, .lenok
    ld a, MAX_INPUT
.lenok:
    ld c, a              ; c = characters left
    ld de, wInput
    ld b, 0              ; b = letters in the current word
.loop:
    ld a, c
    or a
    jr z, .end
    dec c
    ld a, [de]
    inc de
    cp '\''
    jr z, .loop
    cp '0'
    jr c, .sep
    cp '9' + 1
    jr c, .char
    cp 'A'
    jr c, .sep
    cp 'Z' + 1
    jr nc, .sep
.char:
    push af
    ld a, [wWordCount]
    cp MAX_WORDS
    jr nc, .full
    ld a, b
    cp SLOT_LEN
    jr nc, .full
    push de
    ld a, [wWordCount]
    call WordPtr
    ld e, b
    ld d, 0
    add hl, de
    pop de
    pop af
    ld [hl], a
    inc b
    jr .loop
.full:
    pop af
    ld a, b
    cp SLOT_LEN
    jr nc, .loop
    inc b
    jr .loop
.sep:
    call .close
    jr .loop
.end:
    call .close
    ret
; closes the word in progress
.close:
    ld a, b
    or a
    ret z
    ld b, 0
    push hl
    push de
    ld a, [wWordCount]
    cp MAX_WORDS
    jr nc, .over
    ld e, a
    ld d, 0
    ld hl, wWordLen
    add hl, de
    ; length of the stored word
    push hl
    call WordPtr
    ld d, 0
.count:
    ld a, [hl+]
    or a
    jr z, .counted
    inc d
    ld a, d
    cp SLOT_LEN
    jr nz, .count
.counted:
    pop hl
    ld [hl], d
    ld hl, wWordCount
    inc [hl]
.over:
    pop de
    pop hl
    ret

; LookupWords: fills cue, topic and flags for each word from ParserWords.
LookupWords:
    xor a
.each:
    ld b, a
    ld a, [wWordCount]
    cp b
    ret z
    push bc
    ld a, b
    call WordPtr
    ld d, h
    ld e, l              ; de = word
    ld hl, ParserWords
.rec:
    ; end of table?
    ld a, h
    cp HIGH(ParserWordsEnd)
    jr nz, .cmp
    ld a, l
    cp LOW(ParserWordsEnd)
    jr z, .none
.cmp:
    push hl
    push de
    ld b, SLOT_LEN
.c:
    ld a, [de]
    cp [hl]
    jr nz, .diff
    inc de
    inc hl
    dec b
    jr nz, .c
    pop de
    pop de               ; discard the saved record pointer: hl points at the fields
    pop bc
    push bc
    push hl
    ld a, b
    ld c, a
    ld b, 0
    ld a, [hl+]
    ld hl, wWordCue
    add hl, bc
    ld [hl], a
    pop hl
    inc hl
    push hl
    ld a, [hl]
    ld hl, wWordTopic
    add hl, bc
    ld [hl], a
    pop hl
    inc hl
    ld a, [hl]
    ld hl, wWordFlags
    add hl, bc
    ld [hl], a
    jr .nextWord
.diff:
    pop de
    pop hl
    ld bc, REC_SIZE
    add hl, bc
    jr .rec
.none:
    pop bc
    push bc
    ld c, b
    ld b, 0
    xor a
    ld hl, wWordCue
    add hl, bc
    ld [hl], a
    ld hl, wWordTopic
    add hl, bc
    ld [hl], a
    ld hl, wWordFlags
    add hl, bc
    ld [hl], a
.nextWord:
    pop bc
    ld a, b
    inc a
    jr .each

; PrefixIs: hl -> NUL-separated lead words (terminated by an empty word). -> a = index after the lead if all match, or 0.
; Lead strings are padded to SLOT_LEN by comparing with the zero-filled word buffer.
PrefixIs:
    ld b, 0              ; word index
.word:
    ld a, [hl]
    or a
    jr z, .matched
    ld a, [wWordCount]
    cp b
    jr z, .no            ; ran out of words
    push hl
    ld a, b
    call WordPtr
    ld d, h
    ld e, l
    pop hl
    ld c, SLOT_LEN
.ch:
    ld a, [de]
    cp [hl]
    jr nz, .no
    or a
    jr z, .wordEnd
    inc de
    inc hl
    dec c
    jr nz, .ch
    ld a, [hl]           ; a lead word never fills 8 characters, this is only for safety
    or a
    jr nz, .no
.wordEnd:
    inc hl
    inc b
    jr .word
.matched:
    ld a, b
    ret
.no:
    xor a
    ret

; CopyWord: a = word index, de = destination. Copies with a NUL. Clobbers a, bc, de, hl.
CopyWord:
    push de
    call WordPtr
    pop de
    ld b, SLOT_LEN
.c:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .c
    xor a
    ld [de], a
    ret

; Parse: wInput/wInputLen -> wParsedIntent, wParsedTopic, wParsedWord, wParsedName, wParsedLike. Clobbers everything.
Parse::
    xor a
    ld [wParsedTopic], a
    ld [wParsedWord], a
    ld [wParsedName], a
    ld [wParsedLike], a
    call SplitWords
    ld a, [wWordCount]
    or a
    jp z, .noise
    call LookupWords
    ; "MY NAME IS X" and friends: the tail must not be a stop word or a cue
    ld hl, LeadsName
.nameLead:
    ld a, [hl]
    or a
    jr z, .likeLeads
    push hl
    call PrefixIs
    pop hl
    or a
    jr z, .nextName
    ld b, a
    ld a, [wWordCount]
    cp b
    jr z, .nextName
    jr c, .nextName
    ld e, b
    ld d, 0
    push hl
    ld hl, wWordFlags
    add hl, de
    ld a, [hl]
    and FLAG_STOP
    ld c, a
    ld hl, wWordCue
    add hl, de
    ld a, [hl]
    or c
    pop hl
    jr nz, .nextName
    ld a, b
    ld de, wParsedName
    call CopyWord
    ld a, INTENT_NAME
    ld [wParsedIntent], a
    ret
.nextName:
    call SkipLead
    jr .nameLead
.likeLeads:
    ld hl, LeadsLike
.likeLead:
    ld a, [hl]
    or a
    jr z, .scan
    push hl
    call PrefixIs
    pop hl
    or a
    jr z, .nextLike
    ld b, a
    ld a, [wWordCount]
    cp b
    jr z, .nextLike
    jr c, .nextLike
    ld e, b
    ld d, 0
    push hl
    ld hl, wWordFlags
    add hl, de
    ld a, [hl]
    pop hl
    and FLAG_STOP
    jr nz, .nextLike
    ld a, b
    ld de, wParsedLike
    call CopyWord
    ld a, INTENT_LIKE
    ld [wParsedIntent], a
    ret
.nextLike:
    call SkipLead
    jr .likeLead
.scan:
    ; first topic word, any negation, best cue (lowest class number wins)
    ld a, [wWordCount]
    ld b, a
    ld hl, wWordTopic
    ld c, 0
.t:
    ld a, [hl+]
    or a
    jr nz, .haveTopic
    dec b
    jr nz, .t
    xor a
.haveTopic:
    ld [wParsedTopic], a
    ld a, [wWordCount]
    ld b, a
    ld c, 0              ; c = best cue
    ld d, 0              ; d = negated
    ld hl, wWordCue
    ld e, 0
.w:
    push hl
    ld a, [hl]
    or a
    jr z, .noCue
    ld l, a
    ld a, c
    or a
    jr z, .takeCue
    ld a, l
    cp c
    jr nc, .noCue
.takeCue:
    ld c, l
.noCue:
    pop hl
    push hl
    ld a, l
    add MAX_WORDS * 2    ; wWordFlags is two arrays past wWordCue
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld a, [hl]
    and FLAG_NEG
    or d
    ld d, a
    pop hl
    inc hl
    dec b
    jr nz, .w
    ; negation swaps insult and praise
    ld a, d
    or a
    jr z, .noSwap
    ld a, c
    cp CUE_INSULT
    jr nz, .notInsult
    ld c, CUE_PRAISE
    jr .noSwap
.notInsult:
    cp CUE_PRAISE
    jr nz, .noSwap
    ld c, CUE_INSULT
.noSwap:
    ld a, c
    or a
    jr z, .noCueWord
    ld e, a
    ld d, 0
    ld hl, CueIntent
    add hl, de
    ld a, [hl]
    ld [wParsedIntent], a
    ret
.noCueWord:
    ld a, [wParsedTopic]
    or a
    jr z, .noTopic
    cp LAST_TECH_TOPIC + 1
    jr nc, .general
    ld a, INTENT_TECH
    ld [wParsedIntent], a
    ret
.general:
    ld a, [wWordFlags]
    and FLAG_QUESTION
    ld a, INTENT_QUESTION
    jr nz, .set
    ld a, INTENT_TALK
.set:
    ld [wParsedIntent], a
    ret
.noTopic:
    ; longest word that is not a stop word
    ld a, [wWordCount]
    ld b, a
    ld c, 0              ; index
    ld d, 0              ; best length
    ld e, 255            ; best index
.long:
    push bc
    push de
    ld b, 0
    ld hl, wWordFlags
    add hl, bc
    ld a, [hl]
    and FLAG_STOP
    pop de
    jr nz, .skipLong
    ld hl, wWordLen
    add hl, bc
    ld a, [hl]
    cp d
    jr c, .skipLong
    jr z, .skipLong
    ld d, a
    ld e, c
.skipLong:
    pop bc
    inc c
    dec b
    jr nz, .long
    ld a, e
    cp 255
    jr nz, .haveBest
    ld a, [wWordFlags]
    and FLAG_QUESTION
    jr z, .noise
    ld a, INTENT_QUESTION
    ld [wParsedIntent], a
    ret
.haveBest:
    ; the word must be all letters and contain a vowel
    ld a, e
    ld [wBestWord], a
    call WordPtr
    ld b, SLOT_LEN
    ld c, 0              ; vowel seen
.chk:
    ld a, [hl+]
    or a
    jr z, .chkEnd
    cp 'A'
    jr c, .noise         ; a digit
    cp 'A'
    jr z, .vowel
    cp 'E'
    jr z, .vowel
    cp 'I'
    jr z, .vowel
    cp 'O'
    jr z, .vowel
    cp 'U'
    jr z, .vowel
    cp 'Y'
    jr nz, .notVowel
.vowel:
    ld c, 1
.notVowel:
    dec b
    jr nz, .chk
.chkEnd:
    ld a, c
    or a
    jr z, .noise
    ld a, [wBestWord]
    ld de, wParsedWord
    call CopyWord
    ld a, INTENT_UNKNOWN
    ld [wParsedIntent], a
    ret
.noise:
    ld a, INTENT_NOISE
    ld [wParsedIntent], a
    xor a
    ld [wParsedTopic], a
    ret

; SkipLead: hl -> a lead entry -> hl = next entry.
SkipLead:
.w:
    ld a, [hl+]
    or a
    jr nz, .w
    ld a, [hl]
    or a
    jr nz, .w
    inc hl
    ret

; Each entry: words separated by NUL, closed by an empty word. An empty entry ends the list.
LeadsName:
    db "MY", 0, "NAME", 0, "IS", 0, 0
    db "CALL", 0, "ME", 0, 0
    db "IM", 0, 0
    db "I", 0, "AM", 0, 0
    db 0
LeadsLike:
    db "I", 0, "LIKE", 0, 0
    db "I", 0, "LOVE", 0, 0
    db 0

SECTION "parser_vars2", WRAM0
wBestWord: ds 1
