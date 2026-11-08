; model.asm - transformer forward pass and tensor buffers.
INCLUDE "constants.inc"
INCLUDE "model_constants.inc"

SECTION "kv_cache", WRAM0, ALIGN[10]
wKCache:: ds MODEL_CTX * MODEL_D
wVCache:: ds MODEL_CTX * MODEL_D

SECTION "tensors", WRAM0, ALIGN[8]
wE::   ds MODEL_D             ; embedding of the last position
wN::   ds MODEL_D             ; normalized embedding
wQ::   ds MODEL_D
wA::   ds MODEL_D             ; attention output
wO::   ds MODEL_D
wX::   ds MODEL_D             ; after attention residual
wN2::  ds MODEL_D
wF::   ds MODEL_FFN
wO2::  ds MODEL_D
wX2::  ds MODEL_D
wN3::  ds MODEL_D
wZ::   ds MODEL_K             ; output bottleneck

SECTION "seq_vars", WRAM0
wSeq::    ds MODEL_CTX * 2    ; 16-bit token ids, little-endian
wSeqLen:: ds 1
wStepJ:   ds 1
wRowMode:: ds 1               ; 0: score the emotion rows, 1: score EOS, slots and words
wRowsLeft: ds 2
wLogits:: ds MODEL_VOCAB * 2  ; int16 little-endian
wCacheLen:: ds 1              ; positions already holding valid K,V (V5 only)

SECTION "model_code", ROM0
; EmbedPos: a = position. wE = sat8(tok[wSeq[a]] + pos[a]). Clobbers everything.
; The token table starts each bank on a row boundary: 512 rows of 32 bytes fill a bank exactly, so id >> 9 picks the bank.
EmbedPos::
    ld c, a
    push bc
    ld l, a
    ld h, 0
    add hl, hl
    ld de, wSeq
    add hl, de
    ld a, [hl+]
    ld e, a
    ld d, [hl]           ; de = id
    ld a, d
    srl a
    add BANK(DataTok)
    call BankSwitch
    ld a, d
    and 1
    ld h, a
    ld l, e
    REPT 5
    add hl, hl
    ENDR
    ld de, DataTok
    add hl, de
    ld de, wE
    ld b, MODEL_D
.c1:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .c1
    pop bc
    ld l, c
    ld h, 0
    REPT 5
    add hl, hl
    ENDR
    ld de, DataPos
    add hl, de
    ld a, BANK(DataPos)
    call BankSwitch
    ld d, h
    ld e, l
    ld hl, wE
    ld b, h
    ld c, l
    jp SatAdd

; ComputeKV: a = position j. Embeds, normalizes and writes K[j], V[j]; leaves wE, wN for j. Clobbers everything.
ComputeKV::
    ld [wStepJ], a
    call EmbedPos
    ld de, wE
    ld bc, wN
    call Norm
    ld a, [wStepJ]
    ld hl, wKCache
    call KVRowPtr
    ld b, h
    ld c, l
    ld hl, TK
    ld de, wN
    call MatVec
    ld a, [wStepJ]
    ld hl, wVCache
    call KVRowPtr
    ld b, h
    ld c, l
    ld hl, TV
    ld de, wN
    call MatVec
    ret

; ForwardStep: wSeq[0..wSeqLen) -> wLogits for the next token. Clobbers everything.
ForwardStep::
    ld a, 1
    ld [wMB_Phase], a
    ; V0: recompute every key/value. The last iteration leaves wE/wN for the current position.
    ; KV_CACHE: start from the first position not cached; K,V of a position never change once computed.
IF DEF(KV_CACHE)
    ld a, [wCacheLen]
ELSE
    xor a
ENDC
.kv:
    push af
    call ComputeKV
    pop af
    inc a
    ld hl, wSeqLen
    cp [hl]
    jr nz, .kv
    ld [wAttnL], a
IF DEF(KV_CACHE)
    ld [wCacheLen], a
ENDC
    ld a, 2
    ld [wMB_Phase], a
BlockAfterKV::
    ld hl, TQ
    ld de, wN
    ld bc, wQ
    call MatVec
    ld a, 3
    ld [wMB_Phase], a
PhAttn::
    ld de, wQ
    ld bc, wA
    xor a
    call AttendHead
    ld de, wQ + MODEL_HEAD_DIM
    ld bc, wA + MODEL_HEAD_DIM
    ld a, MODEL_HEAD_DIM
    call AttendHead
    ld a, 4
    ld [wMB_Phase], a
PhProj::
    ld hl, TO
    ld de, wA
    ld bc, wO
    call MatVec
    ld hl, wE
    ld de, wO
    ld bc, wX
    call SatAdd
    ld de, wX
    ld bc, wN2
    call Norm
    ld a, 5
    ld [wMB_Phase], a
PhFfn::
    ld hl, TF1
    ld de, wN2
    ld bc, wF
    call MatVec
    ld hl, wF
    ld b, MODEL_FFN
    call Relu
    ld hl, TF2
    ld de, wF
    ld bc, wO2
    call MatVec
    ld hl, wX
    ld de, wO2
    ld bc, wX2
    call SatAdd
    ld de, wX2
    ld bc, wN3
    call Norm
    ld a, 6
    ld [wMB_Phase], a
PhOut::
    jp OutputLogits

; OutputLogits: wN3 -> wZ -> wLogits. The factored head costs k x (d + rows) MACs rather than d x rows.
OutputLogits::
    ld hl, TB
    ld de, wN3
    ld bc, wZ
    call MatVec
IF DEF(HEAD_TABLES)
    ld a, [wRowMode]
    or a
    jp nz, OutputWithTables
ENDC
IF DEF(FAST_DOT)
    ; Only rows the decoder can choose at this position are computed.
    ld de, wZ
    ld a, MODEL_K
    call LoadXBiased
    ld a, BANK(DataOut)
    call BankSwitch
    ld a, [wRowMode]
    or a
    jr nz, .later
    ld bc, DataOut + TOK_FIRST_EMOTION * MODEL_K
    ld hl, wRowsLeft
    ld a, LOW(TOK_EOS - TOK_FIRST_EMOTION)
    ld [hl+], a
    ld [hl], HIGH(TOK_EOS - TOK_FIRST_EMOTION)
    ld hl, wLogits + TOK_FIRST_EMOTION * 2
    jr .row
.later:
    ld bc, DataOut + TOK_EOS * MODEL_K
    ld hl, wRowsLeft
    ld a, LOW(MODEL_VOCAB - TOK_EOS)
    ld [hl+], a
    ld [hl], HIGH(MODEL_VOCAB - TOK_EOS)
    ld hl, wLogits + TOK_EOS * 2
.row:
    push hl
    xor a
    ldh [hAcc + 2], a
    ld d, a
    ld e, a
    ld hl, DotW{d:MODEL_K}
    call DotEnter
    push bc
    ld c, LOGIT_SHIFT
    call RsAcc
    pop bc
    pop hl
    ld a, e
    ld [hl+], a
    ld a, d
    ld [hl+], a
    push hl
    ld hl, wRowsLeft
    ld a, [hl]
    sub 1
    ld [hl+], a
    ld a, [hl]
    sbc 0
    ld [hl-], a
    or [hl]
    pop hl
    jr nz, .row
    ret
ELSE
    ; Vanilla computes every row, then the sampler applies the mask.
    ld hl, TOut
    call LoadTensor
    ld a, LOW(wZ)
    ld [wMvX], a
    ld a, HIGH(wZ)
    ld [wMvX + 1], a
    ld a, [wMvBank]
    call BankSwitch
    ld hl, wRowsLeft
    ld a, LOW(MODEL_VOCAB)
    ld [hl+], a
    ld [hl], HIGH(MODEL_VOCAB)
    ld hl, wLogits
.row:
    push hl
    call DotRow
    ld c, LOGIT_SHIFT
    call RsAcc
    pop hl
    ld a, e
    ld [hl+], a
    ld a, d
    ld [hl+], a
    push hl
    ld hl, wRowsLeft
    ld a, [hl]
    sub 1
    ld [hl+], a
    ld a, [hl]
    sbc 0
    ld [hl-], a
    or [hl]
    pop hl
    jr nz, .row
    ret
ENDC

IF DEF(HEAD_TABLES)
; ---- Head tables: the output head has hundreds of rows but only MODEL_K inputs, and those inputs stay fixed for the whole
; pass. So each input gets a 256-entry table of its products with every biased weight, and a MAC becomes one lookup.
; Tables live in cartridge RAM bank 1. Saves live in bank 0, and RAM is enabled only during this pass.
SECTION "head_tables", SRAM[$A000], BANK[1]
sHeadTab: ds MODEL_K * 512

SECTION "head_vars", WRAM0
wTabWeights: ds 2
wTabLogit:   ds 2

SECTION "head_code", ROM0
; BuildHeadTables: entry[b] = (b - 128) * z + 32768 for each z in wZ. Unsigned, so a running sum needs no sign logic.
BuildHeadTables:
    ld hl, sHeadTab
    ld a, MODEL_K
    ldh [hLoop], a
    push hl
    ld hl, wZ
    ld a, l
    ld [wTabLogit], a
    ld a, h
    ld [wTabLogit + 1], a
    pop hl
.table:
    push hl
    ld hl, wTabLogit
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, [hl+]          ; z
    ld c, a
    rlca
    sbc a
    ld b, a              ; bc = z, sign extended
    ld a, l
    ld [wTabLogit], a
    ld a, h
    ld [wTabLogit + 1], a
    pop hl
    ; start = 32768 - 128 * z. z is bc: 128 * z is z << 7, which only touches two bytes for |z| <= 127.

    push hl
    ld h, b
    ld l, c
    REPT 7
    add hl, hl
    ENDR
    ld a, l
    cpl
    add 1
    ld e, a
    ld a, h
    cpl
    adc $80
    ld d, a
    pop hl
.entry:
    ld a, e
    ld [hl], a
    inc h
    ld a, d
    ld [hl], a
    dec h
    ld a, e
    add c
    ld e, a
    ld a, d
    adc b
    ld d, a
    inc l
    jr nz, .entry
    inc h
    inc h
    ldh a, [hLoop]
    dec a
    ldh [hLoop], a
    jr nz, .table
    ret

MACRO HMAC                  ; \1 = input index; \2 = register holding the biased weight
    ld h, HIGH(sHeadTab) + 2 * (\1)
    ld l, \2
    ld a, [hl]
    add e
    ld e, a
    inc h
    ld a, [hl]
    adc d
    ld d, a
    jr nc, :+
    ldh a, [hAcc + 2]
    inc a
    ldh [hAcc + 2], a
:
ENDM

; OutputWithTables: wZ -> wLogits for EOS, slots and words. Same logits as the other paths, bit for bit.
OutputWithTables:
    ld a, $0A
    ld [MBC5_RAMG], a
    ld a, 1
    ld [MBC5_RAMB], a
    call BuildHeadTables
    ld a, BANK(DataOut)
    call BankSwitch
    ld hl, wTabWeights
    ld a, LOW(DataOut + TOK_EOS * MODEL_K)
    ld [hl+], a
    ld [hl], HIGH(DataOut + TOK_EOS * MODEL_K)
    ld hl, wTabLogit
    ld a, LOW(wLogits + TOK_EOS * 2)
    ld [hl+], a
    ld [hl], HIGH(wLogits + TOK_EOS * 2)
    ld hl, wRowsLeft
    ld a, LOW(MODEL_VOCAB - TOK_EOS)
    ld [hl+], a
    ld [hl], HIGH(MODEL_VOCAB - TOK_EOS)
.row:
    xor a
    ldh [hAcc + 2], a
    ld hl, wTabWeights
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    di
    ld [wSaveSP], sp
    ld sp, hl
    ld de, 0
    FOR I, 0, MODEL_K, 2
    pop bc
    HMAC I, c
    HMAC I + 1, b
    ENDR
    ld hl, sp + 0
    ld a, l
    ld [wTabWeights], a
    ld a, h
    ld [wTabWeights + 1], a
    ld a, [wSaveSP]
    ld l, a
    ld a, [wSaveSP + 1]
    ld h, a
    ld sp, hl
    ei
    ; acc = sum + k * 32768, so remove the bias from the top byte; then (acc + 8) >> 4
    ld a, e
    add 8
    ld e, a
    ld a, d
    adc 0
    ld d, a
    ldh a, [hAcc + 2]
    adc LOW(-(MODEL_K / 2))
    ld b, a
    ld a, e
    swap a
    and $0F
    ld e, a
    ld a, d
    swap a
    ld c, a
    and $F0
    or e
    ld e, a              ; low byte of the logit
    ld a, c
    and $0F
    ld c, a
    ld a, b
    swap a
    and $F0
    or c
    ld d, a              ; high byte
    ld hl, wTabLogit
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, e
    ld [hl+], a
    ld a, d
    ld [hl+], a
    ld a, l
    ld [wTabLogit], a
    ld a, h
    ld [wTabLogit + 1], a
    ld hl, wRowsLeft
    ld a, [hl]
    sub 1
    ld [hl+], a
    ld a, [hl]
    sbc 0
    ld [hl-], a
    or [hl]
    jp nz, .row
    xor a
    ld [MBC5_RAMG], a
    ret
ENDC

SECTION "model_code_tail", ROM0
; ModelReset: invalidates per-event state before a new prompt.
ModelReset::
    xor a
    ld [wCacheLen], a
    ret
