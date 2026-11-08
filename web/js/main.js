// Wires the shell together. It loads the ROM, runs it, and offers the display options. It never generates text.
import { Handheld } from "./emulator.js";
import { bindControls } from "./controls.js";
import { Panel } from "./panel.js";

const $ = (id) => document.getElementById(id);
const SAVE_KEY = "system-override-save-v1";
const PREF_KEY = "system-override-display-v1";
const POWER_FLASH_MS = 350;
const params = new URLSearchParams(location.search);

let moduleP = null;
let gb = null;
let panel = null;
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
    moduleP = moduleP || Binjgb();
    const module = await moduleP;
    if (!on) return;
    gb = new Handheld(module, $("screen"), onFrame);
    gb.volume = $("btnSound").getAttribute("aria-pressed") === "true" ? 0.5 : 0;
    gb.ghost = $("optGhost").checked && !$("optClean").checked;
    gb.boot(romBytes, loadSave(), audioCtx);
    applyPalette();
    setTimeout(() => $("lcd").classList.add("on"), POWER_FLASH_MS);
  } catch (err) {
    on = false;
    syncPower();
    showMessage(`Could not start the emulator: ${err.message}. Reload the page to try again.`);
  }
}

function powerOff() {
  if (!on) return;
  storeSave(true);
  on = false;
  gb?.shutdown();
  gb = null;
  $("lcd").classList.remove("on");
  panel?.off();
  syncPower();
}

function syncPower() {
  $("power").setAttribute("aria-pressed", String(on));
  $("led").classList.toggle("on", on);
  $("btnPower").textContent = on ? "Turn off" : "Turn on";
  $("btnReset").disabled = !on;
}

function onFrame() {
  if (++tickCount % 6) return;
  panel.update(gb);
  storeSave();
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
  const availW = narrow || full ? window.innerWidth - 8 : window.innerWidth - 400 - 48 - 48;
  const availH = (narrow ? Infinity : window.innerHeight - (full ? 8 : 70));
  const maxK = Math.min((availW - 12) / 192, (availH - 8) / 318, full ? 8 : 4);
  const k = Math.max(1, Math.floor(maxK * dpr) / dpr);
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
    if (ev.detail > 0 && ev.target.closest?.("button, input")) document.activeElement?.blur();
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
