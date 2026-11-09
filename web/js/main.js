// Wires the shell together. It loads the ROM, runs it, and offers the display options. It never generates text.
import { Handheld } from "./emulator.js";
import { bindControls } from "./controls.js";
import { Panel } from "./panel.js";
import { Composer, cleanText } from "./composer.js";
import { Fight } from "./fight.js";
import { XRay } from "./xray.js";

const $ = (id) => document.getElementById(id);
const SAVE_KEY = "system-override-save-v1";
const PREF_KEY = "system-override-display-v1";
const POWER_FLASH_MS = 350;
const PLUG_PRESS_MS = 120;
const CONTENT_MAX = 1240;
const CONSOLE_SHARE = 0.46;
const HEADER_AND_HINTS = 150;
const SHELL_UNITS = { w: 192, h: 318 };
const params = new URLSearchParams(location.search);

let gb = null;
let panel = null;
let composer = null;
let fight = null;
let xray = null;
let romBytes = null;
let tickCount = 0;
let audioCtx = null;
let on = false;

function showMessage(text) { $("lcdMsg").textContent = text; }

function loadSave() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    return raw ? Uint8Array.from(atob(raw), (c) => c.charCodeAt(0)) : null;
  } catch { return null; }
}

// The ROM's scratch tables share the cartridge's RAM chip, so "RAM changed" fires constantly: save on a slow timer instead.
const SAVE_INTERVAL_MS = 4000;
let lastSaveMs = 0;

function storeSave(force = false) {
  if (!gb?.saveDirty) return;
  const now = performance.now();
  if (!force && now - lastSaveMs < SAVE_INTERVAL_MS) return;
  lastSaveMs = now;
  gb.saveDirty = false;
  try {
    localStorage.setItem(SAVE_KEY, btoa(Array.from(gb.readExtRam(), (b) => String.fromCharCode(b)).join("")));
  } catch { /* Private windows can refuse storage. The cartridge simply forgets on reload. */ }
}

async function fetchBytes(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} returned ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

async function prepare() {
  const build = await (await fetch("rom/build.json")).json();
  panel = new Panel(build);
  composer = new Composer(() => gb, build.addresses, (text) => {
    $("say").value = text;
    panel.say("That message didn't reach the chip. Press Reset under the options below, then send it again.");
  });
  fight = new Fight(build, $("screen"), () => {
    gb?.press("a", true);
    setTimeout(() => gb?.press("a", false), PLUG_PRESS_MS);
  });
  xray = new XRay(build);
  window.__override = { build, get gb() { return gb; } };
  romBytes = await fetchBytes(`rom/${build.rom}`);
}

async function powerOn() {
  if (on) return;
  on = true;
  syncPower();
  showMessage("");
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    audioCtx.resume().catch(() => {});
    // A fresh instance per power-on, like a console losing its RAM. The cartridge save comes back from storage.
    const module = await Binjgb();
    if (!on) return;
    gb = new Handheld(module, $("screen"), onFrame);
    gb.volume = $("btnSound").getAttribute("aria-pressed") === "true" ? 0.5 : 0;
    gb.ghost = $("optGhost").checked && !$("optClean").checked;
    gb.boot(romBytes, loadSave(), audioCtx);
    applyPalette();
    setTimeout(() => $("lcd").classList.add("on"), POWER_FLASH_MS);
  } catch (err) {
    on = false;
    gb = null;
    syncPower();
    showMessage(`Could not start the emulator: ${err.message}. Reload the page to try again.`);
  }
}

function powerOff() {
  if (!on) return;
  storeSave(true);
  composer?.cancel();
  fight?.reset();
  on = false;
  gb?.shutdown();
  gb = null;
  $("lcd").classList.remove("on");
  panel?.off();
  syncPower();
  syncSend();
}

function syncPower() {
  $("power").setAttribute("aria-pressed", String(on));
  $("led").classList.toggle("on", on);
  $("btnPower").textContent = on ? "Turn off" : "Turn on";
  $("btnReset").disabled = !on;
}

function onFrame() {
  composer.step();
  fight.drawFace();
  if (++tickCount % 6) return;
  fight.update(gb);
  panel.update(gb, composer, fight.coachLine);
  document.body.dataset.phase = panel.generating ? "busy" : "idle";
  xray.update(gb);
  syncSend();
  storeSave();
}

function syncSend() {
  const blocked = Boolean(panel?.generating || composer?.busy);
  $("send").disabled = blocked;
  for (const move of document.querySelectorAll("#moves button")) {
    move.disabled = blocked;
    if (!blocked) move.setAttribute("aria-pressed", "false");
  }
  $("send").textContent = blocked ? "Wait" : (fight?.sendLabel ?? "Send");
}

/** Chooses one of the ROM's menu actions from the page. */
async function sendMove(button) {
  if (!composer || panel.generating || composer.busy) return;
  if (!on) await powerOn();
  if (!on) return;
  button.setAttribute("aria-pressed", "true");
  composer.sendAction(Number(button.dataset.item), button.dataset.label);
  syncSend();
}

/** Sends a message from the page, switching the handheld on first when needed. */
async function sendMessage(raw) {
  const text = cleanText(raw);
  if (!text || !composer || panel.generating || composer.busy) return false;
  if (!on) await powerOn();
  if (!on) return false;
  composer.send(text);
  syncSend();
  return true;
}

function applyPalette() {
  const clean = $("optClean").checked;
  gb?.setPalette($("optTint").checked && !clean ? "green" : "gray");
}

function applyDisplay() {
  const device = $("device");
  const clean = $("optClean").checked;
  device.classList.toggle("clean", clean);
  device.classList.toggle("opt-grid", $("optGrid").checked);
  device.classList.toggle("opt-glow", $("optGlow").checked);
  if (gb) gb.ghost = $("optGhost").checked && !clean;
  applyPalette();
  try {
    localStorage.setItem(PREF_KEY, JSON.stringify(Object.fromEntries(["optTint", "optGrid", "optGlow", "optGhost", "optClean"].map((k) => [k, $(k).checked]))));
  } catch { /* Preferences just reset next time. */ }
}

function restorePrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");
    for (const [k, v] of Object.entries(saved)) if ($(k)) $(k).checked = v;
  } catch { /* Defaults stay. */ }
  if (params.get("display") === "clean") $("optClean").checked = true;
}

/** Sizes the object so one LCD pixel is a whole number of device pixels. */
function fit() {
  const dpr = window.devicePixelRatio || 1;
  const full = document.fullscreenElement != null;
  document.documentElement.classList.toggle("fullscreen", full);
  const narrow = window.innerWidth <= 900;
  const availW = narrow || full ? window.innerWidth - 16 : Math.min(window.innerWidth, CONTENT_MAX) * CONSOLE_SHARE;
  const availH = narrow ? Infinity : window.innerHeight - (full ? 8 : HEADER_AND_HINTS);
  const maxK = Math.min(availW / SHELL_UNITS.w, availH / SHELL_UNITS.h, full ? 8 : 4);
  const smallest = narrow || full ? 1 : 2;
  const k = Math.max(smallest, Math.floor(maxK * dpr) / dpr);
  document.documentElement.style.setProperty("--u", `${k / 2}px`);
}

async function main() {
  document.documentElement.classList.toggle("demo", params.get("demo") === "1");
  restorePrefs();
  applyDisplay();
  fit();
  window.addEventListener("resize", fit);
  document.addEventListener("fullscreenchange", fit);
  window.addEventListener("pagehide", () => storeSave(true));
  bindControls(document, () => gb, () => { audioCtx?.resume().catch(() => {}); });

  $("power").addEventListener("click", () => (on ? powerOff() : powerOn()));
  $("btnPower").addEventListener("click", () => (on ? powerOff() : powerOn()));
  $("btnReset").addEventListener("click", () => { powerOff(); powerOn(); });
  $("btnFull").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen?.().catch((e) => showMessage(`Full screen was refused: ${e.message}`));
  });
  $("btnSound").addEventListener("click", (ev) => {
    const enabled = ev.currentTarget.getAttribute("aria-pressed") !== "true";
    ev.currentTarget.setAttribute("aria-pressed", String(enabled));
    ev.currentTarget.textContent = enabled ? "Sound on" : "Sound off";
    if (gb) gb.volume = enabled ? 0.5 : 0;
  });
  for (const id of ["optTint", "optGrid", "optGlow", "optGhost", "optClean"]) $(id).addEventListener("change", applyDisplay);
  // A mouse click must not leave focus on a page button, or the next Enter (Start) would press it again.
  document.addEventListener("click", (ev) => {
    if (ev.detail > 0 && ev.target.closest?.("button, input[type=checkbox]")) document.activeElement?.blur();
  });
  $("composer").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (await sendMessage($("say").value)) $("say").value = "";
    $("say").focus();
  });
  $("moves").addEventListener("click", (ev) => {
    const move = ev.target.closest("button");
    if (move) sendMove(move);
  });

  try {
    await prepare();
  } catch (err) {
    showMessage(`Could not load the ROM: ${err.message}. Run scripts/serve_web.sh and open the address it prints.`);
    return;
  }
  showMessage("");
  if (params.get("autostart") === "1") powerOn();
}

main();
