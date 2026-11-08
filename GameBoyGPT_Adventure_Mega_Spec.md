# GAMEBOYGPT: 8-BIT ADVENTURE
## Complete one-shot engineering specification for an autonomous coding agent
**Version:** 1.0 | **Target:** 1989 Nintendo Game Boy (DMG-01), emulated on Apple M3 Pro / 18 GB RAM | **Status:** implementation plan, not a claim that anything has been built

> **Primary hook:** “I built a choose-your-own-adventure game where a tiny transformer running on the original 1989 Game Boy writes each new story event. Then I optimized the inference engine around 8 KB of RAM and benchmarked every change.”
>
> **Engineering thesis:** *What actually reduces end-to-end neural text generation latency on a 4.194304 MHz, 8-bit CPU, and at what cost to accuracy, ROM, and RAM?*

---

# 0. AUTONOMOUS AGENT CONTRACT — READ FIRST

You are the lead engineer, ML researcher, retro-console programmer, QA engineer, benchmark engineer, and release engineer. Work through this specification in dependency order. **Implement, run, test, capture evidence, and commit. Do not stop at planning, a fake UI, or a ROM displaying canned responses.** The project is complete only when an actual `.gb` ROM performs **the transformer forward pass on the emulated DMG CPU** using embedded learned weights, accepts controller input, and displays model-generated events.

**Priority order:** (1) correct bootable ROM and interactive adventure; (2) genuine inference on hardware; (3) reference-matched correctness; (4) truthful reproducible metrics; (5) baseline vs optimized variants; (6) polished visuals and publication. If optimizing blocks a playable baseline, **freeze and ship the validated baseline** before experimental work.

**Autonomy:** Investigate toolchain availability, install ordinary tools in user-local or Homebrew environment if permitted, document exact versions, make technical decisions yourself within constraints, and create periodic Git commits. No mid-run permission questions for normal local work. Do not overwrite unrelated data. Do not claim real hardware execution without testing a real unit. Do not fake screenshots, speedups, trained weights, event diversity, tests, or model outputs. If a required capability is unavailable, write the blocker in `PROGRESS.md` and ship the highest verified checkpoint.

**Honest limitations:** An offline M3 Pro is sufficient for toolchain, tiny-model training, and emulation. A compelling story-writing model on an 8-bit DMG is **not guaranteed**; response latency could be long. Reduce generation length/model complexity based on measurements. Never replace neural generation with a deterministic lookup without explicit indication and separate accounting. Do not claim “first LLM on a Game Boy,” “FlashAttention,” “PagedAttention,” or breakthrough speedups without evidence. All benchmark numbers must come from actual instrumented runs.

**Separate environments:** Python, PyTorch, C/C++, NumPy, and browser dashboards may be used **offline** for data generation, model training, export, reference correctness, benchmarking, analysis, and UI visualization. **No host-side inference whatsoever during a Game Boy gameplay run.** The shipping ROM must have SM83 assembly code for the actual neural inference, bank switching, tokenizer/input mapping, rendering, sampling/decoding, state machine, and game rules. Build-time macros and asset conversion are allowed. A small amount of support assembly for display and input is fine; the entire shipped runtime should ideally be RGBDS SM83 assembly.

**Mandatory deliverables:** `build/gameboygpt.gb`, an automated runnable test suite, `make demo`, `make verify`, `make benchmark`, `make compare`, a fixed-point reference implementation, weight-exporter and trained model documentation, baseline ROM and optimized ROM of the **same model**, machine-readable benchmark reports, emulator screenshots and screen recording/GIF (only if captured from an actual run), README, TECHNICAL_REPORT, RESULTS, PRIOR_ART, and one-command reproducibility instructions.

---

# 1. WHAT WE ARE BUILDING

## 1.1 Player-facing product

A real original-Game-Boy-compatible adventure ROM. It boots to a crisp monochrome splash screen, starts an atmospheric text adventure, lets the player choose `LEFT`, `RIGHT`, `FORWARD`, `SEARCH` (or up/down alternatives depending on scene), and **a learned causal transformer generates a short event** in response to the choice and compact game state. The deterministic game engine maintains truth: location, obstacles, inventory, lives, and goals. The model writes *narrative flavor and short events* but must not arbitrarily change inventory or invent unwinnable transitions. Provide an explicit `AI WRITING...` progress display during inference, a controllable text reveal, a `NEW RUN` reset, and a metrics/debug overlay.

Player loop: title -> opening scene -> choose action -> form structured model context -> tokenize -> run on-device transformer -> decode 3-8 short tokens (adjust from measured throughput) -> validate/restrict format -> display narrative -> update authoritative game state -> repeat. Use **no online API** and no prerecorded per-action narrative masquerading as generated text. Built-in opening line and UI labels are allowed and must be identified as static assets.

The strongest demo is a split comparison: `VANILLA` and `OPTIMIZED` builds accepting the same prompt, seed, action, checkpoint, and quantized weights, with elapsed DMG-equivalent seconds/token measured honestly. A second demo shows different action choices yield measurably different neural continuations. A third shows increasing generalization to withheld action/state combinations, not just memorized training pairs.

## 1.2 Two inseparable products

- **Playable cartridge:** `gameboygpt.gb`, authentic DMG-specific palette, controller-driven story and game state, deterministic replay and a clear “AI-generated” boundary.
- **ML systems lab:** A reference model, assembly kernels, export format, correctness checker, baselines, per-op profiler, and an ablation study of cycles/token vs numerical accuracy vs ROM/RAM footprint. An optional local static dashboard visualizes real CSV/JSON benchmarks, not invented values.

## 1.3 Primary success criteria (hard gates)

1. DMG-only emulation successfully boots and accepts input. No Color-only features, double-speed mode, host GPU help, network traffic, or MBC behaviors unavailable to ordinary compatible cartridges.
2. Learned weights are embedded in the ROM, with reproducible model checksum and training provenance. A genuinely causal neural network produces next-token scores on the SM83, with at least one attention head and a real attention operation over preceding tokens.
3. Each exported fixed-point kernel matches a **bit-exact, independently implemented integer reference** for dozens to hundreds of randomized and edge-case fixtures, including saturation and overflow conditions.
4. Multiple end-to-end, multi-token greedy generations exactly match the integer reference. If numerical semantics are intentionally changed by an experimental quantization variant, provide its own matching reference and independent quality evaluation.
5. Show at least two action-conditioned continuations from the same state that differ **because the model receives different input**, not because two prewritten response strings were selected. Confirm with a replay trace and input token IDs.
6. Generate a playable sequence of >= 5 turns in DMG emulator with valid game-state transitions; log the true elapsed time per neural token and per complete event.
7. Benchmark a **simple correct vanilla SM83 implementation** against at least one same-model output-equivalent optimization, keeping clock mode, model, tokens, prompt lengths, and runtime display behavior controlled.
8. Produce readable screenshots, source documentation, ablation results, all raw fixtures, hashes, build commands, and caveats.

## 1.4 Stretch criteria (never block the minimum)

- More coherent story endings, inventory-conditioned events, longer context, more locations, save/load with cartridge RAM, 2-3 optimization wins, automatically chosen mixed precision, physical DMG flashcart demonstration, playable browser-hosted emulator demo, and compatibility with a second independent emulator.

---

# 2. PRIOR ART — READ, CREDIT, LEARN; DO NOT SIMPLY REPACKAGE

Inspect and summarize these projects **before** final architecture is locked, then create `docs/PRIOR_ART.md` with feature comparison, exact source URLs, version/commit, reused insights, license obligations, and distinctions. Reference sources only where helpful; never copy code without required attribution.

### Closest Game Boy implementations

1. **maddiedreese/gbc-transformer** — https://github.com/maddiedreese/gbc-transformer . A 260K-parameter TinyStories transformer on stock **Game Boy Color**; fixed-point RMSNorm, RoPE, SwiGLU, MBC5, cartridge SRAM KV cache, 16-token context, 512-token tokenizer. Learn from its fixed-point reference and memory limitations. Distinguish *original DMG compatibility* and player-driven interactive narrative plus reproducible ablations. It reports very slow output; do not claim real-time performance without new benchmarks.
2. **crashtheuniverse/chatgbc** — https://github.com/crashtheuniverse/chatgbc . Pure SM83 assembly **Game Boy Color**, ternary recurrent `minGRU` / sparse-expert language model, codebook/precomputed arithmetic, reported 0.46 sec/token. Important: **not a transformer**. Learn from it how to make prompt input, screen output, ternary arithmetic, and proper bit-exact validation practical. Report its speed as the author's and avoid invalid apples-to-apples comparisons.
3. **Elyan Labs optimized GBC transformer** — https://www.elyanlabs.ai/gbc-llm.html . Reports 10.09x improvement on GBC transformer without changing output, but also describes a retracted/incorrect speed claim for a different technique; highlights risks of SP-hijacking under active interrupts. Use as motivation for independent reproductions, correct cycle accounting, and separating simulator-only hacks from hardware-safe kernels.
4. **ArneshBanerjee/gpt2.s** — https://github.com/ArneshBanerjee/gpt2.s . Entire 124M GPT-2 inference in AArch64 assembly on Apple Silicon: useful inspiration for exact tests and careful numerical kernels, but **different architecture and CPU**.
5. **GBDev Pan Docs** — https://gbdev.io/pandocs/ ; **RGBDS** — https://rgbds.gbdev.io/ and https://github.com/gbdev/rgbds ; **PyBoy** — https://docs.pyboy.dk/ ; **SameBoy** — https://sameboy.github.io/ and https://sameboy.github.io/debugger/ . These are primary hardware/tooling references. Verify mapper, RAM, bank handling, registers, LCD timing, emulator APIs against current documentation.

### Papers and technical ideas (read abstracts/methods, cite accurately)

| Publication | Link | Relevant concept | What *not* to claim |
|---|---|---|---|
| Vaswani et al., *Attention Is All You Need* (2017) | https://arxiv.org/abs/1706.03762 | Scaled dot-product self-attention and transformer design | Don't call a lookup/Markov model a transformer |
| Eldan & Li, *TinyStories* (2023) | https://arxiv.org/abs/2305.07759 | Small models and narrow narrative distributions | Coherent free-form language is not guaranteed for extremely tiny models |
| Dao et al., *FlashAttention* (NeurIPS 2022) | https://arxiv.org/abs/2205.14135 | Data movement, tiling, online softmax | Do not call DMG implementation GPU FlashAttention; describe as streaming/IO-aware inspiration |
| Kwon et al., *PagedAttention / vLLM* (SOSP 2023) | https://arxiv.org/abs/2309.06180 | KV cache management, fragmentation, serving | Paging/batching advantages don't apply directly to one tiny single-request Game Boy |
| Xiao et al., *SmoothQuant* (ICML 2023) | https://arxiv.org/abs/2211.10438 | Quantization sensitivity, calibration | Do not claim SmoothQuant is implemented unless its method is actually used |
| Ma et al., *BitNet b1.58* (2024) | https://arxiv.org/abs/2402.17764 | Ternary weights and specialized hardware arithmetic | Ternary conversion needs actual trained/validated weights; no free parity guarantee |
| Dao et al., *FlashAttention-2* (2023) | https://arxiv.org/abs/2307.08691 | Work partitioning and data movement | Most GPU parallelism tricks are irrelevant to SM83 |
| Frantar et al., *GPTQ* (2022/23) | https://arxiv.org/abs/2210.17323 | Post-training quantization tradeoffs | A tiny custom model may benefit more from quantization-aware training |
| Williams et al., *Roofline Model* (2009) | https://doi.org/10.1145/1498765.1498785 | Balance arithmetic work and data motion | Report Game Boy-aware analytic cost model rather than copying GPU roofline units |
| Williams et al., *FlashAttention* online softmax predecessor: Milakov & Gimelshein (2018) | https://arxiv.org/abs/1805.02867 | Numerically stable online softmax | Integer fixed-point approximations are not mathematically identical to FP softmax |

The scientific contribution here should be **hardware-aware measurement and optimization**, not novelty of attention, quantization, the Game Boy, or the adventure genre by themselves.

---

# 3. HARDWARE / TOOLCHAIN CONTRACT

### 3.1 Exact hardware target

- Target **DMG-01**, monochrome original Game Boy, Sharp SM83-like 8-bit CPU, nominal 4,194,304 CPU clock cycles/sec; do not confuse T-cycles with M-cycles (1 M-cycle = 4 T-cycles for many CPU instructions; verify definitions with tools).
- Built-in **8 KiB WRAM** (`$C000-$DFFF`), **8 KiB VRAM** used chiefly for graphics, a small HRAM and hardware registers. Avoid presenting external cartridge RAM as onboard RAM.
- Display 160 × 144 pixels, 4 shades, tile-based background (20 × 18 8×8 tiles). Layout all UI and text within this grid.
- Cartridge ROM: fixed 16 KiB bank at `$0000-$3FFF`, switchable 16 KiB bank at `$4000-$7FFF`. Use **MBC5** for >= 64 KiB cartridge; start with **512 KiB or 1 MiB ROM target**, expand only when supported. Bank 0 must contain safe always-resident code and interrupts.
- Optional cartridge SRAM may be used, with a separately disclosed 8 KiB / 32 KiB allocation, for KV cache or saves. If used, headline must read “8 KB onboard WRAM + X KB cartridge SRAM.” Track its access cost and flashcart requirements. Preferred baseline starts without SRAM if model/context fits; switch transparently if needed.
- No multiplication/division instructions or native FP. Implement fixed-point math with explicit signedness, width, rounding, saturation, and shift conventions. Avoid reliance on C integer behavior at runtime.

### 3.2 Toolchain

- **RGBDS** (`rgbasm`, `rgblink`, `rgbfix`, `rgbgfx`) for assembly and ROM headers. Pin tested version and exact flags in `toolchain.lock`/README.
- **PyBoy** for automated DMG-only emulator tests, button input, in-memory debug/mailbox inspection, screenshot and captured frames. Pin version. Set emulator hardware model explicitly, not auto-detect Color features. Verify its API against installed version.
- **SameBoy** for independent manual visual inspection and, if feasible, a secondary replay/correctness check.
- `uv` or virtualenv for host scripts; PyTorch / NumPy for tiny model training and reference checks; `pytest` for tests; `Pillow` for sprites/screenshots; `matplotlib` or a simple static HTML dashboard for benchmark images. Keep host-only dependencies clearly separated from runtime.
- macOS Apple Silicon is a supported dev machine; all Game Boy code is **SM83**, not AArch64. The local M3 Pro executes the training/export/dev tools and emulator, not the neural inference under test.

### 3.3 Environment discovery commands (do not assume installed)

Check OS and architecture, Homebrew, `rgbasm --version`, `python3 --version`, available free disk, PyBoy package version, SameBoy availability, and GPU acceleration training support (`torch.backends.mps.is_available()`). Choose reliable CPU training for tiny models if MPS adds overhead. Create `scripts/bootstrap.sh` with safe installation guidance and never request credentials.

---

# 4. MACHINE-READABLE MODEL CONTRACT

## 4.1 Select an architecture small enough to actually finish

Use a **decoder-only causal transformer** (not a recurrent model dressed as one), configurable with these default targets:

| Parameter | Prototype | Release candidate |
|---|---:|---:|
| layers | 1 | 1 or 2 (select by measured latency) |
| hidden dimension `d` | 16 | 32 |
| heads | 1 | 2 |
| per-head dimension | 16 | 16 |
| FFN hidden size | 32 | 64 |
| vocab size | 48 | 96 (or 64 if more usable) |
| context | 8 | 16 |
| precision | int8 activations & weights where practical | fixed-point int8/Q7, 16/24/32-bit accumulators |
| rough model size | a few thousand params | ~10–30K params, compute true count |

Do **not** assert these configurations are capable of coherent English without training evidence. Treat them as feasibility targets. If needed, simplify to a narrower controlled grammar, fewer tokens and shorter events, but preserve genuine transformer attention. The game may use word/subword tokens backed by a 48–96-entry bespoke vocabulary with one or more special control tokens. Only claim 'language model' if it predicts token distributions; do not imply general conversational intelligence.

### 4.2 Mathematical specification

Input: a token sequence of length `L<=CTX`, tokens from learned vocabulary. Embeddings plus positional embeddings -> pre-LN (or RMSNorm if measurably simpler) -> causal multi-head Q,K,V dot-product attention -> output projection + residual -> pre-LN -> two-layer feed-forward with ReLU/ReLU-squared -> residual -> tied or untied output projection -> logits -> greedy/top-k. Every operation must have an independent Python **fixed-point equivalent** matching the assembly's exact rounding and saturation. Off-device FP32 model and exported quantized model should also be compared for quality, but FP32 parity is **not** the same as integer bit-exactness.

Prefer exact integer-friendly ReLU and simple stable scaling over GELU, RoPE, SwiGLU and layer normalization if those hurt performance; document deviations. The original transformer paper is a conceptual reference, not an obligation to replicate every contemporary architectural component. Implement at least one actual scaled QK attention and value aggregation across prior tokens. Write exact equations and tensor shapes in `docs/MODEL.md`.

### 4.3 Loss and training

Train offline on the M3 Pro from scratch, with fixed seeds, pinned libraries, optimizer and data split. Use next-token cross-entropy loss, AdamW, gradient clipping, short sequence batching. For tiny models, training runs should be bounded and resumable; avoid indefinite expensive training. Save training curves, train/validation loss and **bits per character or token NLL**. Use early stopping or select checkpoint by held-out validation metric. Save a `checkpoint.pt` host artifact separate from ROM export. Include baseline quality before training or shuffled/untrained baseline.

### 4.4 Dataset and story language

Do **not** assume a 20K-parameter model will produce vivid coherent paragraphs. Create a **small, intentionally learnable narrative event language** first, e.g. 64–96 tokens for locations, verbs, items, monsters, weather, causal markers, and punctuation. Every instance contains a structured prefix: `<BOS> <ROOM_FOREST> <HAS_KEY> <ACT_LEFT> <EVENT> ... <EOS>`. Model predicts 3–8 continuation tokens; deterministic display grammar expands tokens into readable, atmospheric but honest short English sentences. If expansion adds fixed words, document exactly which words are deterministic and which tokens were neural-generated. Avoid passing it off as unrestricted natural-language generation.

Training samples must cover diverse room/action/inventory combinations and varied valid continuations. Write data generation scripts with held-out **combinations** (not just random examples from the same templates). Avoid leakage of exact target continuations. Require at least 3 held-out state-action families and 5 distinguishable continuation patterns. Optionally train an additional character/byte-level model as exploratory stretch if latency permits.

Story world: a ruined tower, misty forest, cave, river, gate, ancient key, lantern, sleeping guardian. Keep deterministic, finite state transitions and possible win/lose conditions. Build 8–12 simple rooms and 4 actions, with coherent rules. Show clear choices and consequences. Use seedable procedural layout that preserves solvability (test with BFS or reachable-state search).

### 4.5 Conditioning and context

Use compact symbolic tokens rather than expensive English prompt BPE. Each turn starts from a canonical short feature sequence. Include `room`, `action`, key/inventory flags, progress indicator, and perhaps previous event category. Maintain a bounded rolling context of <=16 tokens. If full history won't fit, keep **structured state**, not a misleading claim of open-ended memory. Evaluate held-out action consistency: does LEFT prompt produce a plausible LEFT-conditioned event?

### 4.6 Validity constraints

No arbitrary model text may alter engine truth: item pickup, room transition, damage, or win state come from deterministic rules. Allow generation from a constrained token subset; optionally mask invalid next tokens using a tiny finite-state grammar in assembly. Report that decoding is constrained; distinguish model's token choices from deterministic rendering. Fallback is allowed only with an explicit recorded `FALLBACK` flag, a counter in metrics, and a trace; never conceal fallback inside published generated examples. If >10% of gameplay events require fallback on test seeds, mark quality gate failing and fix the model/data/constraints.

---

# 5. ROM RUNTIME DESIGN (ALL SM83 ASSEMBLY)

## 5.1 Mandatory source modules

`src/boot.asm` startup vectors, header, interrupts; `src/video.asm` tile/font renderer, VBlank-safe updates; `src/input.asm` debounced joypad; `src/ui.asm` screen modes, story scrolling, menu; `src/game.asm` deterministic world, inventory, RNG, seed/replay; `src/tokenizer.asm` symbolic tokens & prompt formatter; `src/model.asm` forward pass and tensor buffer management; `src/matvec.asm`, `src/attention.asm`, `src/norm.asm`, `src/activation.asm`, `src/quant.asm`, `src/sampler.asm`; `src/bank.asm` ROM/SRAM banking; `src/profile.asm` hardware/emulated cycle accounting instrumentation; `src/debug.asm` mailbox + trace, optional build only. Banked model weights generated by `tools/export_weights.py` into `generated/*.asm` or `.bin` linked as ROMX data.

Do **not** write monolithic 6K-line assembly with no test seams. Define calling conventions, clobbered registers, scratch space, and return conventions per function. All code must assemble under pinned RGBDS.

## 5.2 Memory and banking specification

Produce `docs/MEMORY_MAP.md` with exact byte counts for input tokens, activations, scratch matrix-vector buffers, attention context, KV, decoder, RNG, game state, UI, stack, and debug mailbox. Explicitly reserve stack headroom and interrupts. Target <=7 KiB static WRAM usage unless analysis justifies more; ensure not exceeding 8 KiB total WRAM. Keep model weights in ROM, **not WRAM**. Each banked tensor has `{bank, address, shape, stride, precision, scale}`. All code that runs during switches should be in fixed bank 0, or use safe trampolines. Guard against interrupt routines inadvertently accessing switched model pages. If using cartridge SRAM, specify MBC5 RAM enable/bank protocol, actual allocation, and battery-backed save implications. Keep hardware compatibility in tests.

Provide a ROM layout map: bank 0 startup/main hot kernels/interrupts; subsequent ROM banks weights arranged in row-major or tile-major blocks, dictionary/codebooks, assets and fonts. Select ROM size and mapper based on actual payload and header checksum. Header must explicitly support DMG rather than GBC-only.

## 5.3 Zero-fake inference protocol

The model forward pass on the Game Boy must execute dot products from **the actual learned weights**; Q,K,V attention must read token-dependent activations and compute dynamic scores; output logits must depend on changed state-action tokens. There must be no runtime precomputed story-response lookup or host injection. Verification mode writes token IDs, logits subset/checksum, kernel checksum, current phase, iteration, and bank switches to reserved debug mailbox for PyBoy. This mailbox is instrumentation only; retail ROM does not rely on it. Audit shipped `.gb` with bank content and disassembly/text checks to show model weights and math code are present.

## 5.4 Integer arithmetic correctness

Document Q format for every tensor, e.g. signed int8 values with per-tensor/per-row power-of-two scales, int16/24/32 accumulator where needed. For each MAC: signed input interpretation, product width, sum width, overflow behavior, fixed-point requantization, ties-to-even or away-from-zero rounding, saturation bounds. Implement `mul_signed8`, optional lookup multiply, `dot_i8`, `matvec_i8`, residual add, quantize, normalization approximations, QK attention, streaming softmax or monotone alternative, and output argmax. If non-softmax attention is chosen for extreme efficiency, identify the modified architecture honestly and verify the conditioning/weights were trained for that exact rule.

### Practical trap: attention implementation

With single-token autoregressive decode and context <=16, a full LxL attention matrix is not needed. The vanilla baseline may hold a length-L score vector. Streaming attention reduces this temporary vector, but can add integer arithmetic and be slower. Do not assume a speedup. Distinguish prefill vs decode, measuring both. For quantized softmax: max subtract, bounded exponential lookup, fixed-point normalization, guard sum=0. For online softmax: prove fixed-point reference matching separately; an optimized integer algorithm need not equal FP32 softmax.

## 5.5 Baseline behavior

The **V0 vanilla implementation** must prioritize readable, correct kernels and reference matching. Do not deliberately cripple it to manufacture speedups; it may use straightforward practical coding and safe integer arithmetic. The optimized build must retain V0 model and decoding semantics when measuring speed-only optimizations, and must run identical deterministic token traces.

## 5.6 Story runtime UX state machine

`BOOT`, `TITLE`, `INTRO`, `ACTION_MENU`, `PREFILL`, `GENERATING`, `REVEAL`, `STATE_UPDATE`, `ENDING`, `STATS`, `ERROR`. Each state has explicit entry/exit, button handling, draw operations, and debugging markers. Press A to confirm, B to back/skip reveal, START for pause/stats, SELECT for metrics overlay; no need to type arbitrary English text. Each generated event should display in <=2-3 lines with pagination. Use text-wrap and avoid typing text during unbounded critical sections. Screen should remain responsive enough to show progress even if generation is slow: display a step/counter as an honest progress marker rather than spinning a fake neural animation.

---

# 6. HARDWARE-AWARE OPTIMIZATION RESEARCH PLAN

Every optimization must have a written hypothesis, correct implementation, reference-based correctness tests, cycle-level measurement, ablation report and a **keep/revert decision**. Avoid bundling changes together before measuring them. Do not assume any target speedup.

## V0: Vanilla baseline [MANDATORY]

Simple tested int8 matrix-vector kernels, correct (possibly vector-buffered) attention, row-major weights, straightforward bank switches, separate operations, basic fixed-point arithmetic, real generation. Save immutable `baseline` tag and model hash. Benchmark before optimization.

## V1: Bank-aware tensor tiling + access scheduling [MANDATORY]

Hypothesis: grouping weights by consumed output rows/layers and aligning tensors within 16 KiB cartridge banks reduces bank switches / branch overhead and encourages linear sequential ROM reads. Build `tools/rom_layout.py` that takes tensor metadata and emits bank assignments. Compare naive deterministic layout vs optimized same-weight layout; compute actual bank-switch counts, bytes loaded, cycle impact. Prevent bank crossing within hot loops where practical. Validate exact same logits/tokens.

## V2: Optimized integer multiply/accumulate [MANDATORY]

Benchmark alternatives: shift/add multiplication, partial 4-bit nibble tables, small codebook lookups, additive ternary path (only with appropriate weights). Choose based on measured SM83 instruction cycles, *including* table construction, unpacking and memory accesses. Implement signedness/overflow checks. This is likely to matter more than sophisticated attention tiling. Compare matvec microbenchmark and whole-model tokens/s. If V2 worsens speed, retain V0 path and record negative result.

## V3: Fused operations + buffer reuse [HIGH]

Fuse bias, scaling, activation or residual where it reduces reloads and scratch storage. Explicitly test for saturation changes, rounding order and numerical drift. A fusion that changes integer rounding must be treated as a new numeric variant with its own reference and quality gates. Report peak WRAM and cycles/token.

## V4: Streaming attention / online normalization [HIGH IF MEMORY-BOUND]

Implement score-by-score attention with bounded accumulators and no full score array. Compare to vanilla with same inputs, Q format and arithmetic semantics if possible; if not bit-identical, report token divergences, quality and accuracy. Optimize **peak RAM first**; investigate speed only with measurements. Do not label as actual FlashAttention. In a tiny decode-only context the gain may be negligible.

## V5: KV caching and context scheduling [HIGH IF RECOMPUTE-BOUND]

Benchmark cached K/V vs recomputation for generation; memory cost is `layers*context*heads*head_dim*2*bytes_per_value`. Use WRAM or cartridge SRAM only within documented limits. If reading/writing SRAM is costlier than recompute for tiny models, document and choose the faster correct path. For every generated token, enforce causal positions and state reset. Profile prefill separately from decode. A fixed-capacity ring buffer is not PagedAttention; do not label it that.

## V6: INT4 / INT8 / per-layer precision [RESEARCH]

Support weight-only INT4 packed nibbles, per-row / power-of-two scales, and calibration-driven mixed precision. Same fixed-point inference engine; fewer bytes do not imply fewer instructions. Compare checkpoint held-out NLL, action-conditioned validity, token disagreement, ROM size, decode cycles. Try post-training calibration first; if quality drops, optional quantization-aware fine-tuning of tiny model on M3 Pro. Include an achievable accuracy constraint relative to V0 baseline (e.g. <=5% relative NLL degradation, configurable and reported rather than hidden).

## V7: LUT nonlinearities and ternary/codebook weights [OPTIONAL]

Measure lookup tables for exp/normalization or min/max approximations; evaluate actual ROM bank costs and accuracy. Ternary requires retraining or quantization-aware training and cannot be compared as same-model exact-output. Include small ablation or leave as future work if unproductive. Attribute ChatGBC and BitNet inspirations.

## V8: Automatic bank/precision configuration search [STRETCH]

A bounded host-side search over layer precision, ROM layouts, context and LUT strategies, with <=20 trial configs and deterministic seeds. Objective is weighted measured DMG seconds per event under ROM/WRAM and quality constraints. Do not use network model calls to fabricate optimizer fitness; actual ROM tests produce fitness. Cache results by config/weights hash and avoid training a new model per trial except deliberate quantization-aware trials.

### Explicitly deferred

PagedAttention (no concurrent request batching), speculative decoding (verification overhead likely dominates), GPU kernel FlashAttention implementation, large MoE (storage/switch complexity), arbitrary multi-turn chat (model too small), running model training inside Game Boy (not main project), non-DMG-only speed tricks.

---

# 7. METRICS AND EXPERIMENTAL METHODOLOGY

## 7.1 Critical metric definitions

`T_cycle_per_token`: total **DMG T-cycles** from one decode iteration start to decoded output token end (include relevant bank switching/decoder work; state exactly what's excluded). `seconds_per_token = T_cycle_per_token / 4,194,304` at nominal DMG speed. Do not conflate emulator wall-clock seconds and simulated hardware seconds. `tokens_per_second = 1 / seconds_per_token`. Also measure `first_token_latency`, `prompt_prefill_cycles`, `median and p95 decode cycles/token`, `complete_event_latency`, `input->narrative latency`, `bank_switches/token`, `peak_WRAM`, `peak_cartridge_SRAM`, `ROM_bytes`, `model_parameter_count`, `heldout_loss`, `bits_per_character`, `action_consistency`, `valid_event_rate`, `fallback_rate`, `checksum/token_parity`.

One player action can involve 3-8 tokens, so **seconds per event** may be a more meaningful UX metric than tokens/sec. Show both.

## 7.2 Clock and profiler integrity

SM83 exposes no portable free-running high-resolution CPU cycle counter. Preferred: instrument the chosen emulator's CPU instruction/cycle accounting or implement a reliable trace-based cycle total with validated timing semantics. **Do not fake precision** using arbitrary frame counts or CPU-time on macOS. For player-visible approximate elapsed time, count frames at nominal refresh as secondary measure, not primary per-op timer. Test timing against known instruction-sequence ROMs and confirm one independent emulator or traced instruction logs when possible. Calibrate whether counters include HALT, LCD waits, timers, interrupts, and rendering. Store calibration notes.

When emulator instrumentation cannot produce trustworthy exact cycles, report `DMG-equivalent frames` with uncertainty and call cycle results `estimated` rather than exact. Do not claim physical hardware timings unless hardware measured.

## 7.3 Standard fixed benchmark workloads

- `PROMPT_A`: forest + no key + LEFT; 16 generated tokens or configured cap.
- `PROMPT_B`: cave + lantern + SEARCH; same cap.
- `PROMPT_C`: tower + key + FORWARD.
- `PROMPT_D`: river + no inventory + RIGHT.
- Mixed shorter/longer context (4, 8, 16 tokens) when supported.
- Use a fixed checkpoint, vocabulary, quantization, integer implementation, greedy decode and fixed seed. Run at least 3 emulator repetitions per case if deterministic instrumentation; use identical cold/hot cache conditions across variants. For every variant collect `raw/trace_{variant}_{case}.json`, full generated token IDs and SHA256 of ROM and model.

## 7.4 Ablation policy

Record V0, V1, V2, V3, etc. as **cumulative versions**, plus isolated A/B toggles for changes whose interaction can be measured safely. Keep `git` tags or per-variant build configs; never overwrite baseline. Only compare speed as exact-output when output tokens + kernel tests agree. Precision/layout change comparisons may change output; report accuracy and token divergence separately.

Include a *fair comparison* to C/host simulation only as a **reference functional correctness/operation-count comparison**, not a CPU seconds/token showdown; the hardware is fundamentally different. The main fair performance comparison is **vanilla SM83 vs optimized SM83**, with both running under the same emulated DMG CPU.

## 7.5 Quality testing

- Held-out next-token loss, action/state consistency across 100+ disjoint scenarios; report train/test partition method.
- Novelty audit: exact continuation overlap with train templates, unique token sequences over 100 varied action seeds, fallback/invalid count.
- Small human study optional: blind rating of 20 events on coherence, action relevance, atmospheric interest. No generated marketing results.
- Story solvability: engine state-transition BFS, automated 100-seed simulation, no softlock.
- Explicitly disclose model vocabulary restrictions and template-based rendering if used.

## 7.6 Required output CSV schema

`version,git_commit,rom_sha256,model_sha256,emulator,emulator_version,hardware_mode,workload,context_len,output_tokens,round,first_token_tcycles,decode_tcycles_total,decode_tcycles_median,decode_tcycles_p95,nominal_seconds_per_token,seconds_per_event,bank_switches,peak_wram_bytes,peak_sram_bytes,rom_bytes,token_match_baseline,heldout_nll,action_valid_rate,notes`

Missing entries are `null`/`NA`, never made-up zeros. Require scripts to validate fields and fail on nonsensical negative cycles, missing ROM checksums, or impossible memory values.

---

# 8. USER INTERFACE AND VISUAL IDENTITY

## 8.1 Game Boy ROM UI

Design for real **160×144 four-shade monochrome** screen, not a fake high-resolution phone/web UI. Respect 20×18 tiles, contrast, 8×8 font, button legibility, text clipping, and VBlank safe graphics transfers.

Visual direction: atmospheric 1989 fantasy game, pixel-art forest/castle silhouettes, limited ink-like shading, chunky bitmap typography, simple animated cursor, minimal flicker. Reference aesthetic: early Zelda / text adventure without copying proprietary assets or logos. Produce original 1-bit/2-bit tile art and typography license audit.

Required screens:
1. **Title:** `8-BIT ADVENTURE`, subline `A TINY TRANSFORMER STORY`, START prompt; small CPU/brain glyph.
2. **Adventure:** upper ~6 tile rows show forest/cave/river/tower scene and room name; middle ~5 tile rows text event; lower ~5 rows 2-4 controller choices; bottom row status `KEY 0/1 | TURN 03`. Adapt layout based on readability.
3. **AI Writing:** prominent `THE CARTRIDGE IS THINKING` / `GENERATING 3/6`, optional rotating tile glyph and progress indicator backed by real model progress; no fake instantaneous result.
4. **Narrative:** story reveal, page/skip with A, action-conditioned changes highlighted only if accurate.
5. **Stats:** `V0/VOPT`, DMG-equivalent sec/token, model size, tokens/event, SRAM use, ROM bank switches, real values; show N/A until measured.
6. **Ending:** WIN/LOSE with short AI-generated epilogue if feasible.

### Example UI copy (concept only, not benchmark/data)

`DARK FOREST` / `A SHADOW MOVES BY THE OLD GATE.` / `> GO LEFT    SEARCH    GO RIGHT` / `A CHOOSE    START STATS`.

## 8.2 Developer benchmark visualizations

Create `docs/figures/` with generated charts directly from benchmark CSV:
- **Main hero:** screenshot/image of real `.gb` ROM inside an original-style Game Boy frame *clearly labeled emulator screenshot*, not photorealistic fake hardware.
- **Optimization waterfall:** V0->Vn bars showing cumulative **sec/token** and relative speedup; error bars or per-workload ranges when available.
- **Latency breakdown:** stacked bar of prefill, matvec, attention, normalization, sampling, UI, ROM bank overhead; only if instrumentation genuinely supports it.
- **Pareto frontier:** x=seconds/token, y=held-out NLL or action-valid rate, bubble area=ROM bytes, color=precision/layout.
- **Memory diagram:** bank 0, bank-switch windows, SRAM, WRAM, activations, KV cache with actual byte values.
- **Correctness evidence:** grid of bit-exact tests pass, baseline vs optimized token traces, reference hashes.
- **Training evidence:** train and validation curves plus held-out example outputs.

Build **optional** local interactive static HTML (`reports/dashboard.html`) with filter selectors for model variant/workload/metric and side-by-side terminal-style benchmark cards. It must read actual embedded JSON/CSV generated by the report script and never initialize with invented numbers. If no data, render an explicit `NO BENCHMARK DATA YET` message.

## 8.3 Video/release deliverables

Capture one real emulator video/GIF <=45 sec (if generation permits) showing boot, player choice, actual generation progress, fresh story event, and optimization comparison; use sped-up footage only with a conspicuous speed label and also show real-time segment. Keep terminal overlay with commit/model hash and real measured seconds/token. Make at least 3 genuine emulator screenshots: title, game choice, generation/metrics. Avoid using generative images as evidence of gameplay.

Candidate post headline **only if verified**: “I turned a 1989 Game Boy into an AI dungeon master. Every choice runs a tiny transformer on the 8-bit CPU. Here’s what bank-aware inference actually saved.” Include real numbers, prior-art acknowledgments, and model limitations; do not claim generalized reasoning.

---

# 9. REPOSITORY STRUCTURE

```
gameboygpt/
  SPEC.md                     # this file
  README.md
  PROGRESS.md
  RESULTS.md
  LICENSE
  NOTICE.md
  Makefile
  pyproject.toml / uv.lock
  toolchain.lock
  .gitignore
  src/
    boot.asm video.asm input.asm ui.asm game.asm tokenizer.asm
    model.asm matvec.asm attention.asm norm.asm activation.asm
    quant.asm sampler.asm bank.asm profile.asm debug.asm
    include/ constants.inc macros.inc memory.inc
  assets/
    tiles/ font.png scenes.png title.png
    data/ vocab.json train.jsonl val.jsonl test.jsonl
  training/
    dataset.py model.py train.py evaluate.py quantize.py
    config.yaml
  reference/
    fixed_point.py model_fp32.py format.py
  tools/
    bootstrap.sh export_weights.py rom_layout.py pack_rom.py
    run_emulator.py verify_kernel.py verify_tokens.py
    benchmark.py profile_cycles.py compare.py
    render_dashboard.py capture_demo.py analyze_quality.py
  generated/                 # generated ROM banks, metadata; reproducible
  tests/
    test_dataset.py test_export.py test_fixed_point.py
    test_kernel_vectors.py test_model_parity.py test_rom_boot.py
    test_buttons.py test_game_state.py test_generated_output.py
    test_benchmark_integrity.py
  configs/
    prototype.yaml release.yaml V0.yaml V1.yaml V2.yaml
    V3.yaml V4.yaml V5.yaml V6.yaml
  docs/
    PRIOR_ART.md MODEL.md MEMORY_MAP.md NUMERICS.md
    PERFORMANCE.md ARCHITECTURE.md GAMEPLAY.md
    BENCHMARK_METHOD.md DEMO_SCRIPT.md RELEASE_CHECKLIST.md
    figures/
  reports/
    raw/ figures/ benchmark.csv benchmark.json dashboard.html
  build/                     # .gb, sym, map, binaries, captured frames
  checkpoints/               # training outputs, ignored unless small
```

Ensure `generated` artifacts needed to rebuild are reproducible; record source and binary SHA256 hashes. Do not commit giant third-party data or unauthorized weights. Provide a tiny seed fixture in repo for offline smoke testing.

---

# 10. IMPLEMENTATION PHASES WITH PASS/FAIL GATES

**Work sequentially. Commit each passing phase. Update `PROGRESS.md` every phase**: completed files, tests, hashes, blockers, next exact command. If context resets, reread `SPEC.md` + `PROGRESS.md`, resume immediately. Don't spend the entire run on architecture or optional visual polish.

## PHASE 0 — audit, bootstrap, research [mandatory]

- Read prior art and primary hardware docs. Check machine/tools. Lock tool versions. Decide ROM mapper/SRAM budget and model size by quick cost estimate (parameter count, multiply-add count/token, worst-case CPU cycles and ROM bytes).
- Write source citations, prior-art matrix, architecture diagram and prototype risk register. Most severe risks: inference too slow, RAM overflow, broken bank switching, quantization-induced nonsense, misleading benchmark timing, static-text fallback.
- Initialize repository, `Makefile`, dependency manager, verify RGBDS assembles a minimal ROM, create `PROGRESS.md`.
- **Gate:** `make smoke` boots a minimal valid DMG ROM and produces a screenshot; source docs and pinned versions exist. Commit `cp0-bootstrap`.

## PHASE 1 — playable game shell [mandatory]

- Build tile engine, input debounce, game state, rooms, choices, deterministic transitions and endings, static intro. Sprite/image tools create licensed original assets. Use placeholders only for generated story events, marked `STATIC PLACEHOLDER` and tracked; do not claim final neural generation.
- Add seedable determinism, UI screenshot checks and 100-seed solvability tests. Provide instrumentation state mailbox.
- **Gate:** run 5-turn adventure via automation, no lockups, readable UI, correct item and room transitions, .gb DMG mode verified. Commit `cp1-game-shell`.

## PHASE 2 — dataset, training and model quality [mandatory]

- Build structured event corpus with train/val/test splits by withheld combinations; tokenizer/vocabulary; offline PyTorch transformer, all model hyperparameters defined, automated train/eval, plots, reproducible checkpoint and logs. Include 1-layer d16 prototype then test 1–2 layer d32 model. Choose feasible checkpoint on *heldout* quality and inference budget, not simply best-looking sample.
- Baseline untrained vs trained quality; report action-conditioning ablation with shuffled action inputs and invalid-event frequency. Export one chosen model, keep original FP32 and quantized checkpoints.
- **Gate:** validation loss improves from untrained baseline; action changes matter in controlled trials; 20 held-out prompts generate nontrivial outputs; model count and export size within budgets. Commit `cp2-training`.

## PHASE 3 — reference fixed-point implementation [mandatory]

- Freeze integer numerical contract and model export binary header: magic, format_version, architecture, number of banks, tensor table with bank/address/shape/scale, checksum. Independent bit-exact Python reference. Test every rounding/overflow case; fixed golden input and output fixtures including attention and final logits. Train quantization-aware if PTQ collapses.
- **Gate:** exporter round-trips; integer reference runs full model for 20 prompts without overflow/NaN analogs; held-out quality/validity meets documented floor. Commit `cp3-fixedpoint`.

## PHASE 4 — SM83 assembly inference [mandatory, hardest]

- Implement scalar signed arithmetic, matvec, scaling, embeddings, attention, norm, FFN, output projection and decoder, banked weight reading, bounded scratch buffers. Unit-test each kernel by emulator mailbox against golden vectors. Automate ROM launch and debug extraction with PyBoy.
- Implement real tokenized prompt from current state/action; generated token loop, no host inference, explicit progress. Support deterministic greedy to simplify proof.
- **Gate:** kernel randomized/edge-case parity; end-to-end greedy token IDs exactly match integer reference on >=20 scenarios; shipping ROM generates >=3 different coherent/valid **neural** events from action contexts; no hidden canned continuations. Commit `cp4-real-inference`.

## PHASE 5 — playable AI adventure [mandatory]

- Wire model outputs to narrative display, continuation validation, deterministic world transitions, ending, metrics overlay, graceful text overflow, reset, and consistent input. Avoid fallback unless flagged. Make generation length adaptive only through clearly specified deterministic budget (not hidden change in token semantics).
- **Gate:** 5-turn automated full journey with at least 3 neural-generated events, zero crashes, no graphical corruption, no game-state softlock, acceptable validity/fallback metrics recorded. Capture genuine screenshots. Commit `cp5-playable`.

## PHASE 6 — trustworthy vanilla benchmark [mandatory]

- Freeze V0 configuration, set a baseline tag, record hashes. Establish emulator timing calibration. Implement ROM kernel microbench and end-to-end deterministic timing. At minimum measure V0 decode cycles/token, per-event latency, bank switches, ROM bytes, WRAM bytes. Measure 4 fixed prompts x 3 repetitions. Compare token traces to reference.
- **Gate:** report reproducible metrics, raw logs, methodology and timestamp/version. `make benchmark BASELINE=1` works. Commit `cp6-baseline`.

## PHASE 7 — hardware-aware optimization [mandatory minimum V1/V2]

- Implement V1 ROM layout / bank scheduling, isolate speed gain and exact parity. Implement V2 arithmetic optimization, isolate speed gain and exact parity. Preserve both winners and losers in experiment report; choose fastest passing verified kernel by measured cycles. Don't tune on quality holdout. Attempt V3-V6 in order of measured bottlenecks and budget; stop if regressions prevent shipping.
- **Gate:** at least two genuinely implemented optimization experiments with numerical parity and real cycle measurements; cumulative performance breakdown, negative results documented. Commit `cp7-optimization`.

## PHASE 8 — ablation/report/dashboard [mandatory]

- Collect end-to-end and per-kernel numbers for all validated variants. Generate waterfall, Pareto, latency breakdown where supported, memory map, correct baseline checks, sample quality table. Create optional dashboard only after CSV exists. Create `RESULTS.md` with hardware, build, methods, hashes, raw log links and limitations. Label quantitative improvements relative to actual baseline, never prior projects with different models/hardware.
- **Gate:** `make compare` regenerates analysis from raw data; no invented numbers; output screenshots and figures correctly sourced. Commit `cp8-report`.

## PHASE 9 — release and viral demo packaging [mandatory if resources]

- Make `make demo` build/load ROM and optionally run scripted player sequence, capture exact real emulator video/screenshots, show a prompt/action pair, generation progress and original/optimized throughput. Polish README intro with click-friendly 45-second concept, architecture, demo screenshots, commands, numerical chart, prior-art table, meaningful limitations.
- QA with PyBoy and independently SameBoy if supported; rerun from clean clone; audit redistributable assets/licenses; include `NOTICE.md` and original work attribution. Check copyright/trademarks and avoid using official Nintendo artwork/logos.
- **Gate:** clean `make all && make verify && make benchmark && make demo` on documented setup, artifact hashes, playable ROM, truthful visuals, no test regressions. Tag `v0.1.0`. Commit `cp9-release`.

## OPTIONAL PHASE 10 — physical cartridge

- If user later provides an original DMG and compatible MBC5 flash cartridge, validate on actual hardware with filmed evidence and battery/runtime measurements. Do not assume emulator behavior proves physical speed/safety. This is optional, not a requirement for this build.

---

# 11. TEST MATRIX AND FAILURE HANDLING

### Functional

- Boot on DMG mode (not GBC), valid headers/checksums, readable font and responsive joypad. Buttons with hold/repeat. Full map reachable and winnable. Inventory state truth, non-blocking UI, text clipping. ROM bank address sanity and bank 0 residency. SRAM enabled/disabled tests if used. Recovery after reset.

### Model correctness

- Endianness, signed int8 extremes, negative multiply, saturating adds, rounding boundaries, accumulator overflow, bank boundary reads, odd-sized tensor strides, zero-length or max-length sequences, causal masking, EOS behavior, deterministic argmax tie-breaking, model checksum mismatch handling. Random kernel tensors with fixed seeds. Differential tests to Python fixed-point implementation. End-to-end token trace parity.

### Numerical/ML

- Report FP32 to INT8 quality difference, quantization scale sweeps, context length sensitivity, action-conditioning score on heldout combinations, simple repeated-prompt diversity with fixed seeded sampling if sampling enabled, exact token duplicates vs training templates, fallback frequency. No arbitrary cherry-picking only success outputs.

### Performance

- Cold bank vs warm bank, context 4/8/16, first token vs steady decode, different event lengths, UI enabled vs debug kernel mode. All cycle timings calibrated. Don't report clock-normalized sec/token from host emulator FPS. Benchmark optimizer must not opportunistically skip layer work or reduce model tokens without reporting. Measure rendering overhead separately but retain end-to-end UX numbers.

### Failure flow

- At a failing phase: reproduce with small fixture -> isolate one kernel/input -> compare Python fixed-point -> inspect bank/stack/register assumptions -> patch -> add regression test -> rerun full prior suite -> commit. After bounded retries prioritize smallest correct model and a full playable flow. A slower honest success is better than a fast fake.

---

# 12. PUBLICATION AND CLAIMS CHECKLIST

- Show real emulator footage, distinguish accelerated video vs real-time.
- State: “original Game Boy (DMG) emulator,” not “physical Game Boy” unless physically tested.
- State: “tiny causal transformer,” not “GPT-2/ChatGPT/LLM with full language understanding.”
- Clarify offline training uses M3 Pro/PyTorch; inference computation is cartridge-side SM83.
- Specify constraints correctly: 8 KiB **internal** WRAM plus any external SRAM, ROM size, actual number of parameters, context length, precision, tokens/sec, event latency, vocabulary and constrained decoding, static game engine and generated narrative boundary.
- Do not claim first-ever; cite GBC Transformer, ChatGBC and Elyan Labs.
- Avoid cherry-picked baseline. Exact optimization claims only with identical model/weights/numerical semantics and reproducible instrumentation. Precision variants compare Pareto fronts/quality, not exact outputs.
- Explain architectural features accurately: streaming attention != GPU FlashAttention; ring KV cache != PagedAttention; optimization search != on-device AI self-improvement.
- If latency is prohibitively slow, be explicit and make the demo about hardware constraints and measured tradeoffs, not polished magical gameplay.
- Include technical debt and future work: larger models, optional cartridge SRAM, non-greedy sampling, physical hardware, physical power measurements.

---

# 13. HUMAN-READABLE PUBLIC DEMO SCRIPT (ADJUST TO REAL RESULTS)

**0–5 sec:** show real DMG-style emulator booting the cartridge, title `8-BIT ADVENTURE`.

**5–12 sec:** “This Game Boy has an 8-bit CPU and 8 KB of built-in RAM. I trained a tiny transformer offline and packed its weights inside a cartridge.” Show relevant assembly kernel and ROM bank illustration.

**12–25 sec:** choose `GO LEFT`; overlay `action tokens -> integer attention -> generated story event`. Show real loading/cycle progress and actual generated text. If time-lapsed, label `N× playback speed`; show one real-time stretch.

**25–35 sec:** same prompt with `GO RIGHT`; get a different actually generated continuation. Show state transitions/choices. If outputs are bad, don't conceal that: choose valid representative test seeds and show quality metric.

**35–43 sec:** display measured `Vanilla: X sec/token` vs `Optimized: Y sec/token` with speedup `X/Y`, exact hardware, model, and output parity label. Blank fields until real results exist.

**43–45 sec:** `No GPU. No API. Just SM83 assembly.` + repo link + “What made it faster?”

The accompanying technical article should contain 1) why naive inference was slow, 2) memory bank design, 3) bit-exact reference, 4) ablation charts, 5) game design, 6) honest failures and prior art.

---

# 14. BUDGET, COMPUTE AND AUTONOMY LIMITS

Your M3 Pro/18 GB is for *development and offline training*. Avoid running extremely large model training; target a tiny trained model that reaches usable held-out performance within a bounded local run. Use CPU where appropriate; MPS may help, but isn't required. No paid cloud services. Autonomy can run many local tests, but limit parallel emulators/processes to avoid exhausting the laptop and corrupting benchmark consistency. For reliable performance metrics, execute one emulator and one benchmark workload at a time; record system load if relevant.

**Time allocation by priority, not estimates:** get full end-to-end model correctness before any research variant; get baseline measurements before optimizations; get at least one optimization and report before speculative extra features. Maintain failure logs and preserve all partial artifacts. An overnight run may not complete all phases. Report exactly what is verified; do not imply it did.

---

# 15. REQUIRED TOP-LEVEL COMMANDS

Implement these commands and document environment assumptions:

```
make bootstrap     # verify/install guidance; non-destructive
make smoke         # minimal DMG ROM boot smoke
make train         # deterministic tiny model training
make export        # pack quantized checkpoint into ROM tensors
make rom           # compile the real assembly ROM
make verify        # arithmetic + model + emulator correctness tests
make play          # open ROM in GUI emulator when available
make demo          # scripted choice/input/outputs + screenshots
make benchmark     # cycle-accurate or explicitly calibrated timing
make compare       # generate tables/figures from authentic raw data
make report        # produce RESULTS + charts + dashboard
make all           # build and verify required release path
make clean         # remove only generated artifacts
```

Do not make `make all` silently train for hours; allow separate `make train` and use a recorded reproducible checkpoint when present. `make demo` must never succeed if it is merely opening a UI with a placeholder narrative. `make verify` should fail on ROM/reference token mismatch or on unverified model inference.

---

# 16. FINAL AUTONOMOUS PROMPT TO PASTE INTO CLAUDE CODE

```
You are the autonomous lead engineer for GameBoyGPT: 8-Bit Adventure.
Read SPEC.md entirely, then implement this project end-to-end, beginning now.
This is an execution assignment, not a request for another plan.

Target: original monochrome Nintendo Game Boy (DMG) compatible .gb ROM,
with actual tiny causal transformer inference written in SM83 assembly and
trained weights inside the cartridge. Offline training/reference/benchmark
tools can use Python/PyTorch on my Apple M3 Pro 18 GB Mac. During gameplay,
no neural computation may be delegated to the host or an API.

Implement the playable choose-your-own-adventure game, quantized transformer,
full bit-exact fixed-point reference and tests, baseline SM83 inference,
and a vanilla-vs-optimized ablation suite with trustworthy DMG cycles/token,
seconds/event, ROM, RAM, accuracy and output parity. Include the bank-aware
and arithmetic optimization experiments. Then implement other optimizations
only when motivated by measurements and when they do not prevent release.

Study and cite the prior repositories and papers specified in SPEC.md; do
not copy without license compliance and do not claim first-ever novelty.

Work sequentially through phases 0-9. At each checkpoint: implement actual
code, run real tests, fix failures, update PROGRESS.md, save logs, and commit.
Do not ask me routine questions. Choose the smallest correct real transformer
that fits and performs acceptably if the ambitious model is too slow.
Do not fake outputs, metrics, emulator screenshots, improvement claims,
or neural generation. Never hide deterministic fallback as generated text.

Final outputs: a working .gb, a 5-turn fully playable demonstrated scenario,
independently verified reference-matching token outputs, a baseline and at
least two measured optimization experiments, real emulator screenshots,
accurate benchmark CSV/charts, a polished README and technical report,
and commands make demo / make verify / make benchmark / make compare.

As an engineering release manager, stop optional work before it threatens a
complete verified baseline. Preserve progress and resume by rereading
SPEC.md and PROGRESS.md if context is compacted. At the end, clearly report
which gates passed, any failing gates, exact measured results, and the paths
to the final ROM, screenshots, code, and report. Begin building immediately.
```

---

# 17. EXECUTION LOG TEMPLATE (`PROGRESS.md`)

```
# Progress
Status: IN_PROGRESS | VERIFIED_PARTIAL | VERIFIED_RELEASE | BLOCKED
Hardware: macOS / Apple Silicon M3 Pro / 18 GB
Toolchain: [versions]
Model: [shape], [count], [sha256]
ROM: [mapper], [ROM bytes], [SRAM bytes], [sha256]
Last passing checkpoint: [number + commit]
Current failing test: [command / fixture / expected vs actual]
Measured baseline: [cycles/token, secs/event or NOT MEASURED]
Measured optimized: [cycles/token, secs/event or NOT MEASURED]
Last 5 actions: ...
Next action: [single precise command or code task]
Known risks: ...
```

# 18. DEFINITION OF DONE

A credible result is **not** merely a beautiful Game Boy screen or a plausible sentence. It is a bootable original-DMG ROM that executes a learned transformer in SM83 assembly, accepts choices, uses neural token outputs to write story events, passes independent fixed-point tests, and supplies a fair measured vanilla-vs-optimized experiment. If any of those are missing, mark release as `VERIFIED_PARTIAL`, explain the gap, and do not pitch the corresponding claim.

**Build the correct game first. Measure it. Only then make it fast.**
