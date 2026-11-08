SECTION "luts", ROM0, ALIGN[8]
ExpLut::
    db $7F,$77,$70,$69,$63,$5D,$57,$52,$4D,$48,$44,$40,$3C,$38,$35,$32,$2F,$2C,$29,$27,$24,$22,$20,$1E,$1C,$1B,$19,$17,$16,$15,$13,$12
    db $11,$10,$0F,$0E,$0D,$0D,$0C,$0B,$0A,$0A,$09,$09,$08,$08,$07,$07,$06,$06,$06,$05,$05,$05,$04,$04,$04,$04,$03,$03,$03,$03,$03,$02
    db $02,$02,$02,$02,$02,$02,$02,$02,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$00,$00,$00,$00,$00,$00,$00
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
NormLut::
    db $7F,$7F,$7F,$7F,$7F,$66,$55,$49,$40,$39,$33,$2F,$2B,$27,$25,$22,$20,$1E,$1C,$1B,$1A,$18,$17,$16,$15,$14,$14,$13,$12,$12,$11,$11
    db $10,$10,$0F,$0F,$0E,$0E,$0D,$0D,$0D,$0C,$0C,$0C,$0C,$0B,$0B,$0B,$0B,$0A,$0A,$0A,$0A,$0A,$09,$09,$09,$09,$09,$09,$09,$08,$08,$08
    db $08,$08,$08,$08,$08,$07,$07,$07,$07,$07,$07,$07,$07,$07,$07,$06,$06,$06,$06,$06,$06,$06,$06,$06,$06,$06,$06,$06,$06,$06,$05,$05
    db $05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$05,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04
SECTION "recip_lut", ROM0, ALIGN[8]
RecipLut::
    db $7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7F,$7C,$75,$6F,$69,$64,$5F,$5B,$57,$54,$50,$4D,$4A,$48,$45,$43,$41
    db $3F,$3D,$3B,$3A,$38,$37,$35,$34,$33,$31,$30,$2F,$2E,$2D,$2C,$2B,$2A,$29,$29,$28,$27,$26,$26,$25,$24,$24,$23,$22,$22,$21,$21,$20
    db $20,$1F,$1F,$1E,$1E,$1D,$1D,$1D,$1C,$1C,$1B,$1B,$1B,$1A,$1A,$1A,$19,$19,$19,$19,$18,$18,$18,$17,$17,$17,$17,$16,$16,$16,$16,$15
    db $15,$15,$15,$15,$14,$14,$14,$14,$14,$13,$13,$13,$13,$13,$13,$12,$12,$12,$12,$12,$12,$11,$11,$11,$11,$11,$11,$11,$10,$10,$10,$10
    db $10,$10,$10,$10,$0F,$0F,$0F,$0F,$0F,$0F,$0F,$0F,$0F,$0E,$0E,$0E,$0E,$0E,$0E,$0E,$0E,$0E,$0E,$0E,$0D,$0D,$0D,$0D,$0D,$0D,$0D,$0D
    db $0D,$0D,$0D,$0D,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0C,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B,$0B
    db $0B,$0B,$0B,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$0A,$09,$09,$09,$09,$09,$09,$09,$09
    db $09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$09,$08,$08,$08,$08,$08,$08,$08,$08,$08,$08,$08,$08,$08,$08,$08
SECTION "words", ROM0
WordPtrs::
    dw Word0
    dw Word1
    dw Word2
    dw Word3
    dw Word4
    dw Word5
    dw Word6
    dw Word7
    dw Word8
    dw Word9
    dw Word10
    dw Word11
    dw Word12
    dw Word13
    dw Word14
    dw Word15
    dw Word16
    dw Word17
    dw Word18
    dw Word19
    dw Word20
    dw Word21
    dw Word22
    dw Word23
    dw Word24
    dw Word25
    dw Word26
    dw Word27
    dw Word28
    dw Word29
    dw Word30
    dw Word31
    dw Word32
    dw Word33
    dw Word34
    dw Word35
    dw Word36
    dw Word37
    dw Word38
    dw Word39
    dw Word40
    dw Word41
    dw Word42
    dw Word43
    dw Word44
    dw Word45
    dw Word46
    dw Word47
    dw Word48
    dw Word49
    dw Word50
    dw Word51
    dw Word52
    dw Word53
    dw Word54
    dw Word55
    dw Word56
    dw Word57
    dw Word58
    dw Word59
    dw Word60
    dw Word61
    dw Word62
    dw Word63
    dw Word64
    dw Word65
    dw Word66
    dw Word67
Word0: db "", 0
Word1: db "A", 0
Word2: db "AND", 0
Word3: db "ARCHES", 0
Word4: db "BARS", 0
Word5: db "BATS", 0
Word6: db "BITE", 0
Word7: db "BONES", 0
Word8: db "BUT", 0
Word9: db "BY", 0
Word10: db "CANDLES", 0
Word11: db "CHAINS", 0
Word12: db "CLIMB", 0
Word13: db "COLD", 0
Word14: db "COLUMNS", 0
Word15: db "DARK", 0
Word16: db "FALL", 0
Word17: db "FERNS", 0
Word18: db "FIND", 0
Word19: db "GATE", 0
Word20: db "GO", 0
Word21: db "GUARDIAN", 0
Word22: db "HUMS", 0
Word23: db "HURT", 0
Word24: db "IDOLS", 0
Word25: db "IS", 0
Word26: db "KEY", 0
Word27: db "LAMP", 0
Word28: db "LEECHES", 0
Word29: db "LEFT", 0
Word30: db "LOCKED", 0
Word31: db "LOOK", 0
Word32: db "LOOM", 0
Word33: db "NEED", 0
Word34: db "NO", 0
Word35: db "NOTHING", 0
Word36: db "ON", 0
Word37: db "ONLY", 0
Word38: db "OPENS", 0
Word39: db "PALE", 0
Word40: db "PATH", 0
Word41: db "PRESS", 0
Word42: db "RAPIDS", 0
Word43: db "REEDS", 0
Word44: db "RIGHT", 0
Word45: db "ROCKS", 0
Word46: db "ROOTS", 0
Word47: db "SEARCH", 0
Word48: db "SHADOWS", 0
Word49: db "SHOWS", 0
Word50: db "SIGH", 0
Word51: db "SILENT", 0
Word52: db "SLEEPS", 0
Word53: db "STAIRS", 0
Word54: db "STIR", 0
Word55: db "STONES", 0
Word56: db "STOP", 0
Word57: db "TAKE", 0
Word58: db "THE", 0
Word59: db "TURN", 0
Word60: db "TURNS", 0
Word61: db "UNDER", 0
Word62: db "WAIT", 0
Word63: db "WAKES", 0
Word64: db "WALK", 0
Word65: db "WET", 0
Word66: db "YOU", 0
Word67: db "YOUR", 0
