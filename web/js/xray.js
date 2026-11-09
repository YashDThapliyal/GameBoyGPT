// X-ray mode. Everything drawn here is read from emulated memory: the chip's work RAM, the network's activations, and the
// candidate list the sampler is about to draw the next token from.
import { tokenLabel } from "./tokens.js";

const WRAM_START = 0xc000;
const GRID_W = 128;
const GRID_H = 64;
const CANDIDATES_SHOWN = 6;
const BYTE_SHADES = [[0x4d, 0x53, 0x3c], [0x8b, 0x95, 0x6d], [0xc4, 0xcf, 0xa1], [0xe6, 0xdf, 0xca]];
const ACTIVATION_SHADES = ["#1f1f1f", "#4d533c", "#8b956d", "#c4cfa1"];
// Compute order through one forward pass.
const LAYERS = [["Input", "wE", 32], ["Query", "wQ", 32], ["Attention", "wA", 32], ["Feed-forward", "wF", 64], ["Output", "wX2", 32], ["Bottleneck", "wZ", 16]];

const make = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};

export class XRay {
  constructor(build) {
    this.build = build;
    this.a = { ...build.addresses, ...build.debug };
    this.el = (id) => document.getElementById(id);
    this.active = false;
    this.lastCandidates = "";
    this.ctx = this.el("wram").getContext("2d");
    this.image = this.ctx.createImageData(GRID_W, GRID_H);
    this.layerCanvases = this.buildLayers();
    this.el("btnXray").addEventListener("click", () => this.toggle());
  }

  buildLayers() {
    const rows = LAYERS.map(([label, , size]) => {
      const row = make("div", "layer");
      const canvas = make("canvas");
      canvas.width = size;
      canvas.height = 1;
      row.append(make("span", "", label), canvas);
      return { row, canvas };
    });
    this.el("layers").replaceChildren(...rows.map((r) => r.row));
    return rows.map((r) => r.canvas);
  }

  toggle() {
    this.active = !this.active;
    this.el("device").classList.toggle("xray", this.active);
    document.documentElement.classList.toggle("xray-on", this.active);
    this.el("xrayPanel").hidden = !this.active;
    this.el("btnXray").setAttribute("aria-pressed", String(this.active));
    this.el("btnXray").textContent = this.active ? "Close the case" : "See inside the chip";
  }

  /** Called about ten times a second while the emulator runs. */
  update(gb) {
    if (!this.active) return;
    this.drawWram(gb);
    this.drawLayers(gb);
    this.renderCandidates(gb);
  }

  drawWram(gb) {
    const px = this.image.data;
    for (let i = 0; i < GRID_W * GRID_H; i++) {
      const value = gb.peek(WRAM_START + i);
      const shade = BYTE_SHADES[value >> 6];
      const at = i * 4;
      px[at] = shade[0];
      px[at + 1] = shade[1];
      px[at + 2] = shade[2];
      px[at + 3] = value === 0 ? 40 : 255;
    }
    this.ctx.putImageData(this.image, 0, 0);
  }

  /** Activations are signed bytes. Darker means closer to zero, whichever the sign. */
  drawLayers(gb) {
    LAYERS.forEach(([, symbol, size], row) => {
      const ctx = this.layerCanvases[row].getContext("2d");
      for (let x = 0; x < size; x++) {
        const raw = gb.peek(this.a[symbol] + x);
        const magnitude = Math.abs(raw > 127 ? raw - 256 : raw);
        ctx.fillStyle = ACTIVATION_SHADES[Math.min(magnitude >> 4, ACTIVATION_SHADES.length - 1)];
        ctx.fillRect(x, 0, 1, 1);
      }
    });
  }

  readCandidates(gb) {
    const count = gb.peek(this.a.wCandN);
    const list = [];
    for (let i = 0; i < count; i++) {
      const id = gb.peek(this.a.wCandId + i * 2) | (gb.peek(this.a.wCandId + i * 2 + 1) << 8);
      if (id < this.build.vocabSize) list.push({ id, weight: gb.peek(this.a.wCandW + i) });
    }
    return list;
  }

  renderCandidates(gb) {
    const list = this.readCandidates(gb);
    const picked = gb.peek(this.a.wPickId) | (gb.peek(this.a.wPickId + 1) << 8);
    const key = `${picked}:${list.map((c) => `${c.id}.${c.weight}`).join()}`;
    if (key === this.lastCandidates || !list.length) return;
    this.lastCandidates = key;
    const total = list.reduce((sum, c) => sum + c.weight, 0) || 1;
    const top = [...list].sort((a, b) => b.weight - a.weight).slice(0, CANDIDATES_SHOWN);
    this.el("candidates").replaceChildren(...top.map((c) => {
      const share = (c.weight / total) * 100;
      const row = make("div", c.id === picked ? "cand picked" : "cand");
      const bar = make("i");
      bar.style.width = `${share}%`;
      row.append(make("b", "", tokenLabel(this.build.vocab, c.id)), make("span", "", `${Math.round(share)}%`), bar);
      return row;
    }));
    this.el("candMore").textContent = list.length > CANDIDATES_SHOWN ? `Plus ${list.length - CANDIDATES_SHOWN} less likely options.` : "";
  }
}
