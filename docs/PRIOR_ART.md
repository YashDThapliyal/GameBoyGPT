# Prior Art

Sources checked 2026-11-07 through the GitHub API, the listed pages, the arXiv API and Crossref. Every speed figure below is the named author's claim; none was reproduced here. This project copies no code, weights, tables or assets from any project listed.

"Derived" marks arithmetic done for this document from the cited source. "Not stated" means the source was reachable and did not say. All sources were reachable.

## 1. Feature comparison

| | gbc-transformer | Elyan Labs fork | chatgbc | gpt2.s |
|---|---|---|---|---|
| **Source** | [maddiedreese/gbc-transformer](https://github.com/maddiedreese/gbc-transformer) | [page](https://www.elyanlabs.ai/gbc-llm.html), [Scottcjn/gbc-transformer](https://github.com/Scottcjn/gbc-transformer) | [crashtheuniverse/chatgbc](https://github.com/crashtheuniverse/chatgbc) | [ArneshBanerjee/gpt2.s](https://github.com/ArneshBanerjee/gpt2.s) |
| **Hardware target** | Stock GBC with EZ-FLASH Junior; author tested only GBC | GBC, emulators only (PyBoy, SameBoy); "not run on real silicon" | GBC; header is CGB-only (`rgbfix -C`); uses KEY1 and SVBK | Apple Silicon (AArch64) |
| **Language** | C (GBDK-2020 4.5.0) | C plus SM83 inner MAC | SM83 assembly (RGBDS), Python tooling | AArch64 assembly, no libc calls |
| **Model type** | Transformer: 5 layers, dim 64, 8 heads, 4 KV heads, RoPE, RMSNorm, SwiGLU | Same model and weights as upstream | v1.0: **not a transformer**. minGRU core plus 4 ReLU² experts per layer, 3 layers. v0.1-v0.3 were transformers | GPT-2 small transformer, 12 blocks |
| **Parameters** | 260K (`stories260K.bin`) | 260K | 373,952 (v1.0); 260K (v0.3) | 124M |
| **Context** | 16 tokens | 16 tokens per upstream shape; page does not state | Recurrent state, no window (v1.0); 24-position ring (v0.3) | 1024 tokens |
| **Tokenizer** | BPE, 512 tokens, on device | Repo: as upstream. Page says "byte-level", which conflicts with the repo | BPE, 1024 tokens, 3.46 chars/token on held-out text (v1.0); 512 tokens, 2.10 (v0.3) | GPT-2 byte-level BPE; non-ASCII approximate |
| **Weight format** | Row-wise int8 with Q16 scale per row; Q12 activations held in int32 | Same, int8-to-int8 | Trained ternary with power-of-two row scale; int8 activations and state (v1.0); 4-bit Lloyd-Max, 8-bit KV projections (v0.3) | fp32 |
| **RAM / SRAM / ROM** | Base WRAM under 8 KB; SRAM KV cache 20,480 B of 4 banks (derived: 5×16×32×4×2, `-Wm-ya4`); MBC5+RAM+BATTERY | Not stated on page; repo keeps SRAM KV cache | 192 B recurrent state; story build has no SRAM; uses WRAM banks 1 and 7; 512 KB ROM (MBC5). Rei build adds 8 KB battery SRAM | 75 MB KV cache, 340 MB transposed copy, about 550 MB mapped file |
| **Reported speed (author)** | About 0.0059 tokens/s, one token per 2 min 49 s (estimated elapsed time, real GBC) | 476,200 to 47,200 frames for 16 tokens, 10.09x (emulator). About 17 s/token is the author's stated projection, not a measurement | 0.46 s/token, 962,790 M-cycles/token, DIV/TIMA, double speed (v1.0). 6.16 s/token, 12,918,757 cycles (v0.3) | 90-100 tokens/s on M1, one thread |
| **Quality evidence** | Sample output on hardware | 16 tokens byte-identical to upstream | 1.126 bits/char vs fp32 1.123 (v1.0); 1.149 vs 0.876 (v0.3) | Greedy tokens match PyTorch on 4 prompts |
| **License** | MIT | MIT (page states none; repo is MIT) | MIT | MIT |
| **Commit checked** | `28c443c1b0cb3d4536f4575bcdfd647a3ec8ad73` (2026-07-29) | `320a7ff0e32006b247a261f87ee1f2fece1b7e71` (2026-08-05); page undated | `319d8d06930298abf2c7a247c1febf1f6d4601de` (2026-09-29); v0.3 tag `29b5702c62391196cf2a7dae6de8ecd73da100b9` | `6750cdc493fd9c7d0065678a8d46471f3fc116d2` (2026-11-07) |

## 2. Per-project notes

**gbc-transformer.** Insight: the source is a complete integer transformer reference. RMSNorm sums `(v*v)>>4`, divides by the length, adds 1, takes a bitwise `isqrt32`, inverts as `2^22/root`, then applies Q12 gains. Softmax subtracts the row maximum and evaluates `exp(-x)` as the reciprocal of a 4th-order Taylor series, with integer divides. PR #1 fixed a matmul overflow from 16-bit int promotion on SM83. Distinction: it is C, while we write SM83 assembly and build a game. Its Makefile sets no CGB flag and the runtime makes no CGB calls, so "DMG compatible" alone does not separate us from it; the author simply has not reported running it on a DMG. License: MIT, so copied code would need the notice kept. We copy none. Its weights come from `karpathy/tinyllamas` (MIT per the Hugging Face card) and we do not use them.

**Elyan Labs fork.** Insight: the ratio ladder is measured per change, and output is the gate. Stages: pointer walk 1.18x, loop hoists 1.28x, strength reduction 1.35x, KEY1 double speed 2.73x, KV hoists 2.76x, 8×8 byte-split MAC 10.09x (cumulative). Effective: the MAC splits `xv = 256(c-128)+a`, keeps all partial products in int16, and walks activations with `pop bc`. Little gain: KV bank and base hoists, 174,600 to 172,800 frames. Rejected: deleting clamp checks (2.7% faster, diverges at position 5) and int16 KV entries (44 overflows, fails at position 12); both passed a 3-token check, so its gate is 16 tokens. Withdrawn: "ternary 53.6% faster" was a misattributed N64 figure, and no Game Boy ternary kernel exists. Caveats: KEY1 is CGB-only, contributing 2.01x, so 10.09x does not transfer to a DMG. The SP kernel runs with interrupts disabled and is untested on a console with a live LCD. Its own emulator baseline (498 s/token) and upstream's hardware figure (169 s/token) disagree by 2.9x, unreconciled, so only the ratio is claimed. PRs #2-#7 were still open upstream when checked. Distinction: it optimises an existing C ROM; we write assembly from the start and need a hardware-safe kernel. License: MIT. We copy no code.

**chatgbc.** Insight: the method is the main lesson. A Python integer twin defines the bit-exact spec, tests compare ROM tokens against it, and a disagreement is bisected by layer. Cycle counts come from an on-cartridge DIV/TIMA census. Kernel: three ternary weights times three activations give one of 27 sums, built once per input vector (381 cycles a block, 22 blocks), and each weight triple is stored as a byte that addresses its sum (12 cycles per lookup, `302+8s` a row). `mul.asm` is plain shift-add (about 130 cycles for 8×16) used only outside hot paths. Stages with few outputs become tables and mostly-zero outputs become skips: ReLU² is a 256-byte page and `w2` touches only nonzero pairs. Greedy argmax needs no softmax or stored logits. Its no-repeat rule skips a token that would complete a seen 4-gram. Also: real hardware does not zero RAM at power-up, and HRAM code buys no faster memory. Its v0.3 is the closer comparison for us: a transformer at 12.9M cycles/token, losing 31% bits/char to quantization and window, where the author then chose to leave attention. Distinction: v1.0 is not a transformer, its seconds assume double speed, and bits/char and s/token must not be compared directly with a transformer's. License: MIT. We copy no code. Its data is TinyStories (CDLA-Sharing-1.0).

**gpt2.s.** Insight: exact-match verification against a reference implementation (12 tokenizer cases, 4 prompts of 40 tokens), and transposing weights so each output is one sequential row read. Distinction: 64-bit CPU, NEON, fp32, a different architecture and a different scale; no number transfers. License: MIT. We copy no code.

**Comparability.** Seconds per token are not comparable across these projects: clock mode, model size, tokenizer and decoding differ. Frames are not seconds. M-cycle counts on the same model are the only figures that travel, and only when the kernel's assumptions (double speed, banked WRAM) are stated.

## Additions for SYSTEM OVERRIDE

- **binjgb** provides the browser emulator core; see NOTICE.md.
- **chatgbc's** 27-sum lookup, built once per input and read by weight, is the closest prior idea to this project's head tables. Theirs tabulates ternary weight triples and ours tabulates a full 256-entry byte multiply per input. We arrived at ours from our profile, and it uses none of their code.
- **BPE** (Sennrich et al., [Neural Machine Translation of Rare Words with Subword Units](https://arxiv.org/abs/1508.07909), 2015) is the method behind the phrase tokens, applied to whole words rather than characters.
- **Low-rank output layers** are a standard factorization. The head here is not novel; running it on a DMG with lookup tables is what this project measured.

## 3. Papers

| Publication (verified) | Concept | How it applies to a DMG | What we do NOT claim |
|---|---|---|---|
| Vaswani et al., [Attention Is All You Need](https://arxiv.org/abs/1706.03762), 2017 | Scaled dot-product attention | Defines what must run for the ROM to be called a transformer | That a lookup or Markov model is a transformer |
| Eldan & Li, [TinyStories](https://arxiv.org/abs/2305.07759), 2023 | Small models on a narrow distribution | Justifies a tiny model and restricted narrative language | Coherent free-form language from an extremely tiny model |
| Dao et al., [FlashAttention](https://arxiv.org/abs/2205.14135), 2022 | IO-aware attention, tiling | Bank switches and copies as the data-movement cost; tile to bank boundaries | That the DMG runs FlashAttention; at most IO-aware inspiration |
| Dao, [FlashAttention-2](https://arxiv.org/abs/2307.08691), 2023 | Work partitioning, parallelism | Only the data-movement framing; the SM83 has no parallelism | That GPU parallelism tricks apply |
| Milakov & Gimelshein, [Online normalizer calculation for softmax](https://arxiv.org/abs/1805.02867), 2018 | Softmax without storing all scores | Possible streaming attention to lower WRAM use | That a fixed-point approximation equals FP softmax |
| Kwon et al., [PagedAttention / vLLM](https://arxiv.org/abs/2309.06180), SOSP 2023 | KV cache memory management | Vocabulary for a KV cache in SRAM banks | Paging or batching gains; this is one request on one device |
| Xiao et al., [SmoothQuant](https://arxiv.org/abs/2211.10438), ICML 2023 | Quantization sensitivity, calibration | Motivates per-layer calibration | That SmoothQuant is implemented, unless its method is used |
| Frantar et al., [GPTQ](https://arxiv.org/abs/2210.17323), ICLR 2023 | Post-training quantization trade-offs | Baseline against quantization-aware training | That GPTQ results extend to a tiny custom model |
| Ma et al., [The Era of 1-bit LLMs (BitNet b1.58)](https://arxiv.org/abs/2402.17764), 2024 | Ternary weights | Ternary turns multiplies into adds or table lookups | Ternary parity without trained and validated weights |
| Williams, Waterman & Patterson, [Roofline](https://doi.org/10.1145/1498765.1498785), CACM 52(4):65-76, 2009 | Balance of compute and data motion | Form for a Game Boy-specific analytic cost model | GPU roofline units or a roofline result for the DMG |

### Citation check against spec section 2

- **Roofline DOI: correct.** It resolves to ACM. Crossref lists Williams, Waterman, Patterson, CACM 52(4), April 2009.
- **Milakov & Gimelshein 2018: correct, but the spec row is mislabelled.** The arXiv ID, authors and year match. The row's leading "Williams et al., FlashAttention" is wrong: Williams is unrelated and that is not this paper's title. The FlashAttention bibliography does list it.
- **FlashAttention-2 is single-author** (Tri Dao), so "Dao et al." is wrong.
- **BitNet b1.58** is the model name, not the paper title. arXiv marks it "Work in progress".
- **FlashAttention "NeurIPS 2022"** is absent from arXiv metadata and was not checked here. PagedAttention, SmoothQuant and GPTQ venues are confirmed by arXiv comments.
- **Spec item 1 distinction is weak:** see the gbc-transformer note. We can claim only what we test on a DMG.
- **Spec item 3 wording:** the sources disable interrupts around the SP kernel. The stated risk is untested hardware behaviour with a live LCD, and interrupts firing would overwrite activations.
- **Spec item 2:** the model, speed and "not a transformer" statements check out, but 0.46 s/token depends on CGB double speed.

## 4. Primary tooling references

| Tool | Reference | Use | License (GitHub API) |
|---|---|---|---|
| Pan Docs | [gbdev.io/pandocs](https://gbdev.io/pandocs/): [Memory Map](https://gbdev.io/pandocs/Memory_Map.html), [MBC5](https://gbdev.io/pandocs/MBC5.html), [CGB Registers](https://gbdev.io/pandocs/CGB_Registers.html), [Instruction Set](https://gbdev.io/pandocs/CPU_Instruction_Set.html), [Interrupts](https://gbdev.io/pandocs/Interrupts.html), [STAT](https://gbdev.io/pandocs/STAT.html), [OAM DMA](https://gbdev.io/pandocs/OAM_DMA_Transfer.html), [Power-Up](https://gbdev.io/pandocs/Power_Up_Sequence.html) | Hardware authority; KEY1 and SVBK are CGB-only | CC0-1.0 |
| RGBDS | [rgbds.gbdev.io](https://rgbds.gbdev.io/), [gbdev/rgbds](https://github.com/gbdev/rgbds); latest release v1.0.4 | Assembler, linker, header fix | MIT |
| PyBoy | [docs.pyboy.dk](https://docs.pyboy.dk/), [Baekalfen/PyBoy](https://github.com/Baekalfen/PyBoy); latest release v2.9.0 | Headless tests and token comparison | Not asserted; read its LICENSE before redistributing |
| SameBoy | [sameboy.github.io](https://sameboy.github.io/), [debugger](https://sameboy.github.io/debugger/), [LIJI32/SameBoy](https://github.com/LIJI32/SameBoy); latest release v1.0.5 | Second emulator, cycle debugging | Not asserted; read its LICENSE before redistributing |

Emulators are not silicon: chatgbc's author hit a zeroed-RAM bug that passed in emulation, and Elyan flags the SP kernel as hardware-unverified. Emulator results here must be labelled as such.
