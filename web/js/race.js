// The race. Two emulators run two real ROMs with the same seed and the same button press, and the page compares what comes out.
// Timers show emulated seconds, so fast-forwarding changes how long you wait and leaves every number the same.
import { Handheld } from "./emulator.js";
import { showSteps } from "./steps.js";

const $ = (id) => document.getElementById(id);
const ST = { BOOT: 0, INTRO: 1, MENU: 2, THINKING: 4, STREAMING: 5, READ: 6 };
const HOLD_SEC = 0.07;
const GAP_SEC = 0.07;
const PROMPT_LEN_FALLBACK = 9;
const FAST_FORWARD = 8;
const SEED_RANGE = 0xffff;
const FACE = { w: 72, h: 64 };
const OPENING_TRACK_TOKENS = 16;
const TRACK_LEAD_ROOM = 2;
const FRAMES_PER_DRAW = 6;

class Racer {
  constructor(side, rom, addresses, build) {
    this.side = side;
    this.rom = rom;
    this.a = addresses;
    this.build = build;
    this.tap = null;
    this.startedAt = null;
    this.finishedAt = null;
    this.tokens = [];
  }

  async boot(audioCtx, onFrame) {
    const module = await Binjgb();
    this.gb = new Handheld(module, $(`screen${this.side}`), onFrame);
    this.gb.volume = 0;
    this.gb.boot(this.rom, null, audioCtx);
    this.gb.setPalette("green");
  }

  stop() { this.gb?.shutdown(); }

  get state() { return this.gb.peek(this.a.wMB_State); }

  runTap(now) {
    const t = this.tap;
    if (!t) return false;
    if (t.down && now - t.at >= HOLD_SEC) {
      this.gb.press(t.name, false);
      t.down = false;
      t.at = now;
    }
    if (!t.down && now - t.at >= GAP_SEC) this.tap = null;
    return this.tap !== null;
  }

  press(name, now) {
    this.gb.press(name, true);
    this.tap = { name, down: true, at: now };
  }

  /** Clicks through the intro. Returns true once this console is waiting on its menu. */
  toMenu() {
    const now = this.gb.seconds();
    if (this.runTap(now)) return false;
    const state = this.state;
    if (state === ST.MENU) return true;
    if (state === ST.BOOT || state === ST.INTRO) this.press("a", now);
    return false;
  }

  /** Moves the menu cursor. Returns true once it sits on the chosen action. */
  toItem(item) {
    const now = this.gb.seconds();
    if (this.runTap(now)) return false;
    const sel = this.gb.peek(this.a.wMenuSel);
    if (sel === item) return true;
    this.press((sel >> 1) !== (item >> 1) ? "down" : "right", now);
    return false;
  }

  go(seed) {
    this.gb.poke(this.a.wMB_ForceSeed, 1);
    this.gb.poke(this.a.wNarrRng, seed & 255);
    this.gb.poke(this.a.wNarrRng + 1, seed >> 8);
    const now = this.gb.seconds();
    this.press("a", now);
    this.startedAt = now;
  }

  /** Follows the reply. Returns true once it has finished. */
  follow() {
    const now = this.gb.seconds();
    this.runTap(now);
    this.readTokens();
    if (this.finishedAt === null && this.state === ST.READ) this.finishedAt = now;
    return this.finishedAt !== null;
  }

  readTokens() {
    const start = this.build.promptLen ?? PROMPT_LEN_FALLBACK;
    const len = this.gb.peek(this.a.wSeqLen);
    if (len <= start + this.tokens.length || len > this.build.ctx) return;
    this.tokens = [];
    for (let i = start; i < len; i++) this.tokens.push(this.gb.peek(this.a.wSeq + i * 2) | (this.gb.peek(this.a.wSeq + i * 2 + 1) << 8));
    $(`words${this.side}`).textContent = this.tokens.join(" ");
  }

  get elapsed() {
    if (this.startedAt === null) return 0;
    return (this.finishedAt ?? this.gb.seconds()) - this.startedAt;
  }
}

const clock = (s) => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, "0")}`;
const friendly = (s) => (s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${s.toFixed(1)} s`);

let racers = [];
let raceItem = 0;
let phase = "idle";
let audioCtx = null;
let frameCount = 0;

function setSpeed() {
  const speed = $("fast").checked ? FAST_FORWARD : 1;
  for (const r of racers) if (r.gb) r.gb.speed = speed;
}

function showClocks() {
  for (const r of racers) $(`clock${r.side}`).textContent = clock(r.elapsed);
}

/** The reply's length isn't known until someone finishes, so the track grows until then and fits it afterwards. */
function trackLength() {
  const finisher = racers.find((r) => r.finishedAt !== null);
  if (finisher) return Math.max(finisher.tokens.length, 1);
  const lead = Math.max(...racers.map((r) => r.tokens.length));
  return Math.max(OPENING_TRACK_TOKENS, lead + TRACK_LEAD_ROOM);
}

function showTrack() {
  const length = trackLength();
  for (const r of racers) {
    const share = Math.min(r.tokens.length / length, 1) * 100;
    $(`fill${r.side}`).style.width = `${share}%`;
    $(`runner${r.side}`).style.left = `${share}%`;
    $(`count${r.side}`).textContent = String(r.tokens.length);
  }
  if (frameCount % FRAMES_PER_DRAW) return;
  // The runners are the real sprites, live from each console's own screen.
  for (const r of racers) $(`runner${r.side}`).getContext("2d").drawImage($(`screen${r.side}`), 0, 0, FACE.w, FACE.h, 0, 0, FACE.w, FACE.h);
}

function commentary() {
  const [fast, slow] = racers;
  const gap = fast.tokens.length - slow.tokens.length;
  if (fast.finishedAt !== null) return `Tuned finished in ${friendly(fast.elapsed)}. Untuned is on ${slow.tokens.length} of ${fast.tokens.length} tokens.`;
  if (slow.finishedAt !== null) return `Untuned finished in ${friendly(slow.elapsed)}. Tuned is on ${fast.tokens.length} of ${slow.tokens.length} tokens.`;
  if (!fast.tokens.length && !slow.tokens.length) return "Neck and neck. Both are reading the prompt.";
  if (gap === 0) return `Neck and neck on ${fast.tokens.length} ${fast.tokens.length === 1 ? "token" : "tokens"}.`;
  const leader = gap > 0 ? "Tuned" : "Untuned";
  const lead = Math.abs(gap);
  return `${leader} is ahead by ${lead} ${lead === 1 ? "token" : "tokens"}.`;
}

function tick() {
  if (phase === "booting") {
    const ready = racers.map((r) => r.toMenu());
    if (ready.every(Boolean)) phase = "aiming";
    return;
  }
  if (phase === "aiming") {
    const ready = racers.map((r) => r.toItem(raceItem));
    if (!ready.every(Boolean)) return;
    const seed = Math.floor(Math.random() * SEED_RANGE) + 1;
    for (const r of racers) r.go(seed);
    phase = "racing";
    return;
  }
  if (phase !== "racing") return;
  const done = racers.map((r) => r.follow());
  frameCount += 1;
  showClocks();
  showTrack();
  $("status").textContent = commentary();
  for (const r of racers) $(`lane${r.side}`).classList.toggle("finished", r.finishedAt !== null);
  if (done.every(Boolean)) finish();
}

function finish() {
  phase = "done";
  const [fast, slow] = racers;
  const same = fast.tokens.length === slow.tokens.length && fast.tokens.every((t, i) => t === slow.tokens[i]);
  window.__race = { same, fast: fast.elapsed, slow: slow.elapsed, tokens: fast.tokens, slowTokens: slow.tokens };
  showTrack();
  if (same) showResult(fast, slow);
  else $("status").textContent = "The two consoles wrote different tokens, which should never happen. Reload the page and try again.";
  setPicking(true);
}

function showResult(fast, slow) {
  $("status").textContent = "";
  $("resultMultiple").textContent = `${(slow.elapsed / fast.elapsed).toFixed(1)}× faster`;
  $("resultLine").textContent = `Both wrote the same ${fast.tokens.length} tokens. The speed work saved ${friendly(slow.elapsed - fast.elapsed)} on this reply.`;
  $("timeFast").textContent = friendly(fast.elapsed);
  $("timeSlow").textContent = friendly(slow.elapsed);
  $("timeBarSlow").style.setProperty("--share", "100%");
  $("timeBarFast").style.setProperty("--share", `${(fast.elapsed / slow.elapsed) * 100}%`);
  $("result").hidden = false;
}

function setPicking(enabled) {
  for (const b of document.querySelectorAll("#picks button")) b.disabled = !enabled;
}

async function start(item, build, roms) {
  for (const r of racers) r.stop();
  raceItem = item;
  phase = "off";
  setPicking(false);
  $("status").textContent = "Starting both consoles.";
  $("result").hidden = true;
  for (const side of ["Fast", "Slow"]) {
    $(`words${side}`).textContent = "";
    $(`clock${side}`).textContent = clock(0);
    $(`lane${side}`).classList.remove("finished");
    $(`fill${side}`).style.width = "0%";
    $(`runner${side}`).style.left = "0%";
    $(`count${side}`).textContent = "0";
  }
  audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
  const shipAddresses = { ...build.addresses, ...build.debug };
  racers = [new Racer("Fast", roms.fast, shipAddresses, build), new Racer("Slow", roms.slow, build.race.addresses, build)];
  let first = true;
  const onFrame = () => {
    // Both emulators call this. One tick per browser frame is plenty.
    first = !first;
    if (first) tick();
  };
  await Promise.all(racers.map((r) => r.boot(audioCtx, onFrame)));
  setSpeed();
  phase = "booting";
}

/** Recorded benchmark numbers, kept apart from the live race and labelled as such. */
function showRecorded(build) {
  $("headParams").textContent = build.params.toLocaleString("en-US");
  const m = build.measured;
  if (!m) return;
  $("headSpeedup").textContent = `${m.speedup.toFixed(2)}×`;
  if (build.steps) $("headCount").textContent = String(build.steps.length - 1);
  $("recTuned").textContent = friendly(m.secondsPerResponse);
  $("recUntuned").textContent = friendly(m.baselineSecondsPerResponse);
  $("recSpeedup").textContent = `${m.speedup.toFixed(2)}×`;
  $("recCached").textContent = `${m.speedupVsCached.toFixed(2)}×`;
  showSteps(build.steps);
}

async function main() {
  const build = await (await fetch("rom/build.json")).json();
  showRecorded(build);
  const fetchRom = async (name) => new Uint8Array(await (await fetch(`rom/${name}`)).arrayBuffer());
  const roms = { fast: await fetchRom(build.rom), slow: await fetchRom(build.race.rom) };
  $("fast").addEventListener("change", setSpeed);
  $("picks").addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (button) start(Number(button.dataset.item), build, roms);
  });
  setPicking(true);
  $("status").textContent = "Pick something to say and both consoles start together.";
}

main().catch((err) => { $("status").textContent = `The race couldn't load: ${err.message}. Reload the page to try again.`; });
