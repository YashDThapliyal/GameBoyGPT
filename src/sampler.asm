; sampler.asm - masked argmax and seeded near-top sampling over wLogits. Matches reference/fixed_point.py.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "sampler_vars", WRAM0
wNarrRng::  ds 2
wCands:     ds SAMPLE_CANDS

SECTION "sampler_code", ROM0
; LogitPtr: a = token -> hl = &wLogits[a]. Clobbers a, de.
LogitPtr:
    ld l, a
    ld h, 0
    add hl, hl
    ld de, wLogits
    add hl, de
    ret

; ArgmaxMasked: -> a = best id in [TOK_FIRST_GEN, VOCAB), ties to lowest. de = its logit. Clobbers everything.
ArgmaxMasked::
    ld a, TOK_FIRST_GEN
    call LogitPtr
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    xor $80
    ld d, a              ; de = best logit, high byte biased for unsigned comparison
    ld b, TOK_FIRST_GEN
    ld c, TOK_FIRST_GEN + 1
.loop:
    ld a, [hl+]
    push af              ; candidate low
    ld a, [hl+]
    xor $80              ; candidate high, biased
    cp d
    jr c, .lower         ; high < best high
    jr nz, .take         ; high > best high
    pop af
    push af
    cp e
    jr c, .lower
    jr z, .lower         ; tie keeps the lowest id
    ld a, d              ; equal high byte
.take:
    ld d, a
    pop af
    ld e, a
    ld b, c
    jr .next
.lower:
    pop af
.next:
    inc c
    ld a, c
    cp MODEL_VOCAB
    jr nz, .loop
    ld a, d
    xor $80
    ld d, a
    ld a, b
    ret

; SampleMasked: picks uniformly among the first SAMPLE_CANDS ids within SAMPLE_MARGIN of the best,
; advancing wNarrRng once. Returns a = id. Clobbers everything.
SampleMasked::
    call ArgmaxMasked
    ; threshold = best - margin, biased
    ld a, e
    sub LOW(SAMPLE_MARGIN)
    ld e, a
    ld a, d
    sbc HIGH(SAMPLE_MARGIN)
    xor $80
    ld d, a
    push de
    ld a, TOK_FIRST_GEN
    call LogitPtr
    pop de
    ld b, 0              ; candidate count
    ld c, TOK_FIRST_GEN
.scan:
    ld a, [hl+]
    push af
    ld a, [hl+]
    xor $80
    cp d
    jr c, .below
    jr nz, .cand
    pop af
    push af
    cp e
    jr c, .below
.cand:
    pop af
    push hl
    ld hl, wCands
    ld a, b
    add l
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld [hl], c
    pop hl
    inc b
    ld a, b
    cp SAMPLE_CANDS
    jr z, .pick
    jr .next
.below:
    pop af
.next:
    inc c
    ld a, c
    cp MODEL_VOCAB
    jr nz, .scan
.pick:
    ; rng_byte on the narration LFSR
    push bc
    ld a, [wNarrRng]
    ld c, a
    ld a, [wNarrRng + 1]
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
    ld [wNarrRng], a
    ld a, b
    ld [wNarrRng + 1], a
    ld a, c              ; rng byte
    pop bc
    ld c, b
.mod:
    cp c
    jr c, .idx
    sub c
    jr .mod
.idx:
    ld hl, wCands
    add l
    ld l, a
    jr nc, .nc2
    inc h
.nc2:
    ld a, [hl]
    ret

; GenerateTokens: wSeq/wSeqLen hold the prompt. Appends tokens up to the context cap or EOS, calling
; the UI hook after each. Returns carry set if the event was capped without EOS. Clobbers everything.
GenerateTokens::
    xor a
    ld [wMB_NumTokens], a
.next:
    ld a, [wSeqLen]
    cp MODEL_CTX
    jr z, .capped
    call ProfileTokenStart
    call ForwardStep
    call PickToken
    ld b, a
    ld hl, wSeq
    ld a, [wSeqLen]
    add l
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld [hl], b
    ld a, [wSeqLen]
    inc a
    ld [wSeqLen], a
    ld hl, wMB_NumTokens
    inc [hl]
    ld a, b
    push af
    call ProfileTokenEnd
    pop af
    push af
    call TokenHook
    pop af
    cp TOK_EOS
    jr nz, .next
    and a                ; clear carry: finished with EOS
    ret
.capped:
    scf
    ret

; PickToken: greedy or sampled per wMB_Greedy; records masked logit checksum. -> a = id.
PickToken::
    call LogitChecksum
    ld a, [wMB_Greedy]
    or a
    jp z, SampleMasked
    jp ArgmaxMasked

; LogitChecksum: 16-bit wrapping sum of masked logits into wMB_LogitSum.
LogitChecksum:
    ld a, TOK_FIRST_GEN
    call LogitPtr
    ld de, 0
    ld b, MODEL_VOCAB - TOK_FIRST_GEN
.l:
    ld a, [hl+]
    add e
    ld e, a
    ld a, [hl+]
    adc d
    ld d, a
    dec b
    jr nz, .l
    ld a, e
    ld [wMB_LogitSum], a
    ld a, d
    ld [wMB_LogitSum + 1], a
    ret
