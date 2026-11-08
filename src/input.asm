; input.asm - joypad sampling, called once per frame from the VBlank ISR so it stays live during inference.
INCLUDE "constants.inc"

SECTION "input_vars", HRAM
hJoyHeld::    ds 1
hJoyPressed:: ds 1   ; rising edges, latched until consumed by ConsumePressed

SECTION "input_code", ROM0
; ReadJoypad: updates hJoyHeld/hJoyPressed. Clobbers a, b.
ReadJoypad::
    ld a, $20            ; select d-pad
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    swap a
    ld b, a
    ld a, $10            ; select buttons
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    or b                 ; high nibble d-pad, low nibble buttons
    ld b, a
    ld a, $30
    ldh [rP1], a
    ldh a, [hJoyHeld]
    cpl
    and b                ; newly pressed this frame
    ld c, a
    ldh a, [hJoyPressed]
    or c
    ldh [hJoyPressed], a
    ld a, b
    ldh [hJoyHeld], a
    ret

; ConsumePressed: returns latched presses in a and clears the latch. Interrupt-safe.
ConsumePressed::
    di
    ldh a, [hJoyPressed]
    push af
    xor a
    ldh [hJoyPressed], a
    pop af
    ei
    ret
