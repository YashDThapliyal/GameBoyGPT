// A thin wrapper around binjgb, an emulator compiled to WebAssembly. This file only moves data in and out of it:
// bytes of the ROM, button states, finished frames, audio. Everything the ROM computes, it computes inside the core.
const TICKS_PER_SECOND = 4194304;
const AUDIO_FRAMES = 4096;
const AUDIO_LATENCY_SEC = 0.1;
const MAX_STEP_SEC = 5 / 60;
const EVENT_NEW_FRAME = 1;
const EVENT_AUDIO_FULL = 2;
const EVENT_UNTIL_TICKS = 4;
const CGB_COLOR_CURVE = 0;
const ABGR = (r, g, b) => (0xff000000 | (b << 16) | (g << 8) | r) >>> 0;
const PALETTES = {
  green: [ABGR(0xc4, 0xcf, 0xa1), ABGR(0x8b, 0x95, 0x6d), ABGR(0x4d, 0x53, 0x3c), ABGR(0x1f, 0x1f, 0x1f)],
  gray: [ABGR(0xff, 0xff, 0xff), ABGR(0xaa, 0xaa, 0xaa), ABGR(0x55, 0x55, 0x55), ABGR(0, 0, 0)],
};

export class Handheld {
  constructor(module, canvas, onFrame) {
    this.m = module;
    this.ctx2d = canvas.getContext("2d");
    this.onFrame = onFrame;
    this.image = this.ctx2d.createImageData(160, 144);
    this.back = document.createElement("canvas");
    this.back.width = 160;
    this.back.height = 144;
    this.backCtx = this.back.getContext("2d");
    this.ghost = false;
    this.volume = 0.5;
    this.raf = 0;
    this.lastSec = 0;
    this.leftover = 0;
    this.saveDirty = false;
  }

  /** Boots the ROM. extRam restores the battery-backed cartridge RAM. */
  boot(romBytes, extRam, audioCtx) {
    const m = this.m;
    this.audioCtx = audioCtx;
    const size = (romBytes.byteLength + 0x7fff) & ~0x7fff;
    this.romPtr = m._malloc(size);
    const rom = new Uint8Array(m.HEAP8.buffer, this.romPtr, size);
    rom.fill(0);
    rom.set(romBytes);
    this.e = m._emulator_new_simple(this.romPtr, size, audioCtx.sampleRate, AUDIO_FRAMES, CGB_COLOR_CURVE);
    if (!this.e) throw new Error("The emulator rejected the ROM.");
    this.joypad = m._joypad_new();
    m._emulator_set_default_joypad_callback(this.e, this.joypad);
    this.frameBuffer = new Uint8ClampedArray(m.HEAP8.buffer, m._get_frame_buffer_ptr(this.e), m._get_frame_buffer_size(this.e));
    this.audioBuffer = new Uint8Array(m.HEAP8.buffer, m._get_audio_buffer_ptr(this.e), m._get_audio_buffer_capacity(this.e));
    this.audioStart = 0;
    if (extRam) this.writeExtRam(extRam);
    this.ticksStart = this.ticks();
    this.lastSec = 0;
    this.leftover = 0;
    this.raf = requestAnimationFrame((t) => this.step(t));
  }

  shutdown() {
    cancelAnimationFrame(this.raf);
    if (!this.e) return;
    this.m._emulator_delete(this.e);
    this.m._joypad_delete(this.joypad);
    this.m._free(this.romPtr);
    this.e = 0;
  }

  ticks() { return this.m._emulator_get_ticks_f64(this.e); }

  /** Real-time pacing: never faster than the handheld's clock. */
  step(ms) {
    this.raf = requestAnimationFrame((t) => this.step(t));
    const sec = ms / 1000;
    const delta = Math.min(Math.max(sec - (this.lastSec || sec), 0), MAX_STEP_SEC);
    this.lastSec = sec;
    const until = this.ticks() + delta * TICKS_PER_SECOND - this.leftover;
    for (;;) {
      const ev = this.m._emulator_run_until_f64(this.e, until);
      if (ev & EVENT_NEW_FRAME) this.drawFrame();
      if (ev & EVENT_AUDIO_FULL) this.pushAudio();
      if (ev & EVENT_UNTIL_TICKS) break;
    }
    this.leftover = this.ticks() - until;
    if (this.m._emulator_was_ext_ram_updated(this.e)) this.saveDirty = true;
    this.onFrame();
  }

  drawFrame() {
    this.image.data.set(this.frameBuffer);
    this.backCtx.putImageData(this.image, 0, 0);
    this.ctx2d.globalAlpha = this.ghost ? 0.62 : 1;
    this.ctx2d.drawImage(this.back, 0, 0);
  }

  pushAudio() {
    const ctx = this.audioCtx;
    if (ctx.state !== "running") return;
    const now = ctx.currentTime;
    const later = now + AUDIO_LATENCY_SEC;
    this.audioStart = this.audioStart || later;
    if (this.audioStart < now) {
      this.audioStart = later;
      return;
    }
    const buf = ctx.createBuffer(2, AUDIO_FRAMES, ctx.sampleRate);
    const l = buf.getChannelData(0);
    const r = buf.getChannelData(1);
    for (let i = 0; i < AUDIO_FRAMES; i++) {
      l[i] = (this.audioBuffer[2 * i] * this.volume) / 255;
      r[i] = (this.audioBuffer[2 * i + 1] * this.volume) / 255;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    src.start(this.audioStart);
    this.audioStart += AUDIO_FRAMES / ctx.sampleRate;
  }

  press(button, down) {
    if (!this.e) return;
    const fn = { up: "_set_joyp_up", down: "_set_joyp_down", left: "_set_joyp_left", right: "_set_joyp_right", a: "_set_joyp_A", b: "_set_joyp_B", start: "_set_joyp_start", select: "_set_joyp_select" }[button];
    this.m[fn](this.e, down ? 1 : 0);
  }

  setPalette(name) {
    if (!this.e) return;
    const [w, l, d, k] = PALETTES[name];
    for (const type of [0, 1, 2]) this.m._emulator_set_bw_palette_simple(this.e, type, w, l, d, k);
  }

  /** Reads memory through the emulator's debug interface. Has no effect on the running ROM. */
  peek(addr) { return this.m._emulator_read_mem(this.e, addr); }

  withExtRam(cb) {
    const m = this.m;
    const file = m._ext_ram_file_data_new(this.e);
    const view = new Uint8Array(m.HEAP8.buffer, m._get_file_data_ptr(file), m._get_file_data_size(file));
    const out = cb(file, view);
    m._file_data_delete(file);
    return out;
  }

  readExtRam() {
    return this.withExtRam((file, view) => {
      this.m._emulator_write_ext_ram(this.e, file);
      return new Uint8Array(view);
    });
  }

  writeExtRam(bytes) {
    this.withExtRam((file, view) => {
      if (view.byteLength !== bytes.byteLength) return;
      view.set(bytes);
      this.m._emulator_read_ext_ram(this.e, file);
    });
  }
}
