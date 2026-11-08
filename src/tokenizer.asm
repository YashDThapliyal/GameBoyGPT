; tokenizer.asm - Phase 1 placeholder narration. Replaced by the neural model in Phase 5.
INCLUDE "constants.inc"
SECTION "tok_code", ROM0
StrPlaceholder1: db "STATIC PLACEHOLDER", 0
NarrateEvent::
    ld a, 1
    ld [wMB_Placeholder], a
    ld hl, StrPlaceholder1
    ld b, TEXT_ROW
    ld c, TEXT_COL
    jp PrintAt
DrawStats::
    ret
