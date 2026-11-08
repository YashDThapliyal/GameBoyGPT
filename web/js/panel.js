// The notes beside the handheld. Live values come from emulated memory; build values come from rom/build.json.
const STATES = ["Booting", "Playing its intro", "Waiting for your move", "Watching you type", "Thinking: reading the prompt", "Generating words", "Waiting for you to read", "Showing its internals", "Powering down"];
const MOODS = ["Smug", "Amused", "Angry", "Wary", "Bored", "Dying"];
const FRAME_SEC = 70224 / 4194304;

export class Panel {
  constructor(build) {
    this.build = build;
    this.el = (id) => document.getElementById(id);
    this.lastKey = "";
    this.renderBuild();
  }

  renderBuild() {
    const b = this.build;
    const rows = [["Model", `${b.params.toLocaleString("en-US")} parameters, one attention block`], ["Vocabulary", `${b.vocabSize} tokens, phrases included`], ["Numbers", "8-bit weights, 8-bit activations"],
      ["Clock", "4.19 MHz, no multiply instruction"], ["ROM", `${Math.round(b.romBytes / 1024)} KB`], ["Work RAM in use", `${b.wramBytes.toLocaleString("en-US")} of 8,192 bytes`]];
    if (b.measured) rows.push(["Benchmarked speed", `${b.measured.secondsPerToken.toFixed(2)} s per token, ${b.measured.secondsPerResponse.toFixed(1)} s per response`]);
    this.el("build").replaceChildren(...rows.map(([k, v]) => {
      const d = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = k;
      dd.textContent = v;
      d.append(dt, dd);
      return d;
    }));
  }

  off() {
    this.el("lvState").textContent = "Powered off";
  }

  /** Called about ten times a second while the emulator runs. */
  update(gb) {
    const a = this.build.addresses;
    const u8 = (name, off = 0) => gb.peek(a[name] + off);
    const u16 = (name, off = 0) => u8(name, off) | (u8(name, off + 1) << 8);
    const state = u8("wMB_State");
    this.el("lvState").textContent = STATES[state] ?? "Running";
    const responses = u16("wMB_Responses");
    this.el("lvTotal").textContent = u16("wMB_TotalTokens").toLocaleString("en-US");
    if (!responses && state !== 4 && state !== 5) return;
    this.el("lvMood").textContent = MOODS[u8("wMB_Mood")] ?? "None yet";
    if (responses) {
      const frames = u16("wLastEventFrames");
      const tokens = u8("wLastEventTokens");
      if (tokens) this.el("lvLast").textContent = `${tokens} tokens in ${(frames * FRAME_SEC).toFixed(1)} s`;
    }
    const len = u8("wSeqLen");
    if (len > this.build.ctx || (state !== 4 && state !== 5 && state !== 6 && state !== 2)) return;
    const key = `${len}:${u16("wSeq", (len - 1) * 2)}`;
    if (key === this.lastKey) return;
    this.lastKey = key;
    const box = this.el("tokens");
    const frag = document.createDocumentFragment();
    for (let i = this.build.promptLen; i < len; i++) {
      const id = u16("wSeq", i * 2);
      const word = this.build.vocab[id] ?? "?";
      const control = word.startsWith("<");
      const t = document.createElement("span");
      t.className = control ? "tok ctl" : "tok";
      const b = document.createElement("b");
      const n = document.createElement("i");
      b.textContent = control ? word.replace(/[<>]/g, "").replace("E_", "face: ").toLowerCase() : word;
      n.textContent = id;
      t.append(b, n);
      frag.append(t);
    }
    if (frag.childNodes.length) box.replaceChildren(frag);
  }
}
