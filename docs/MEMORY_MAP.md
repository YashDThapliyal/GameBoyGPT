# Memory map

Generated from the linker map of the shipped build (V6T).

```
ROM0: 12042 bytes used / 4342 free
	ROMX: 67023 bytes used / 14897 free in 5 banks
	SRAM: 8234 bytes used / 8150 free in 2 banks
	WRAM0: 5303 bytes used / 2889 free
	HRAM: 87 bytes used / 40 free
```

| Region | Use |
|---|---|
| ROM bank 0 | Kernels, quarter-square table, LUTs, sprite tables, ISR, sampler. Must stay mapped during inference. |
| ROM bank 1 | Conversation code: UI, parser, memory, word table, parser tables. |
| ROM bank 2 and up | Token embeddings pinned at $4000, then position and block tensors in the order they are used. |
| WRAM | K/V cache (32 x 32 x 2), logits (763 x 2), token ids (32 x 2), tensors, shadow BG map, shadow OAM, memory. |
| $DE00-$DEFF | Stack, 256 bytes. |
| $DF00-$DFFF | Debug mailbox read by the test harness. |
| HRAM | Input vector for the dot kernels (64 bytes), OAM DMA routine, accumulators. |
| Cartridge RAM bank 0 | Save data with magic and checksum. |
| Cartridge RAM bank 1 | Head tables: 16 inputs x 512 bytes, rebuilt for every token. |
