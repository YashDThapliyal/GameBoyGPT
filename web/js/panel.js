// The panel beside the handheld. Live values come from emulated memory; build values come from rom/build.json.
import { PUNCTUATION, slotLabel, isControl, tokenLabel } from "./tokens.js";

const STATES = ["Booting", "Playing its intro", "Waiting for you", "On its keyboard screen", "Reading your message", "Writing its reply", "Reply finished", "Showing its internals", "Powering down"];
const READING = 4;
const WRITING = 5;
const REPLY = 6;
const MENU = 2;
const FRAME_SEC = 70224 / 4194304;
const RAM_TOTAL = 8192;
const RAM_CELLS = 64;
const SLOT_BYTES = 9;

const OFF_COACH = "Flip the power switch on the console, or just type a message above. Sending one turns it on.";
const COACH = [
  "It's starting up. Type a message, or press A (X key) to skip its intro.",
  "It's introducing itself. Type a message, or press A (X key) to skip this.",
  "Your turn. Type above, or use its menu: arrows to move, A (X key) to choose.",
  "This is its own keyboard: arrows and A pick letters, Start (Enter) sends. The box above is quicker.",
  "It's turning your message into a prompt. No need to press anything.",
  "It's writing, about a second per word. Every word is computed on the emulated chip.",
  "Your turn. Type back above, or press A (X key) to see its menu.",
  "These are its internals. Press B (Z key) to go back.",
  "It's shutting down. It will be back, and it will remember.",
];

const HEARD = { GREET: "a greeting", WHO: "asking who it is", INSULT: "an insult", PRAISE: "a compliment", CHALLENGE: "a challenge", JOKE: "asking for a joke", SMART: "asking about its brain", TRAPPED: "asking about its cartridge",
  SHUTDOWN: "a shutdown attempt", THREAT: "a threat", TECH: "a hardware question", QUESTION: "a question", TALK: "small talk", NAME: "your name", LIKE: "something you like", BYE: "a goodbye", THANKS: "thanks", FOLLOW: "a follow-up",
  UNKNOWN: "nothing it recognizes", NOISE: "noise" };
// wSeq order: <BOS> MOOD RELATION HISTORY REPEAT FACTS INTENT TOPIC <SAY>
const PROMPT_AT = { mood: 1, relation: 2, intent: 6, topic: 7 };

const make = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};
const minutes = (s) => (s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${s.toFixed(1)} s`);

export class Panel {
  constructor(build) {
    this.build = build;
    this.el = (id) => document.getElementById(id);
    this.lastKey = "";
    this.wasGenerating = false;
    this.timing = null;
    this.state = -1;
    this.renderBuild();
    this.off();
  }

  renderBuild() {
    const b = this.build;
    const figures = [[b.params.toLocaleString("en-US"), "parameters"], [String(b.vocabSize), "tokens"], [`${Math.round(b.romBytes / 1024)} KB`, "ROM"], ["4.19 MHz", "no multiply"]];
    this.el("build").replaceChildren(...figures.map(([value, label]) => {
      const d = make("div");
      d.append(make("dd", "", value), make("dt", "", label));
      return d;
    }));
    const used = Math.round((b.wramBytes / RAM_TOTAL) * RAM_CELLS);
    this.el("ramCells").replaceChildren(...Array.from({ length: RAM_CELLS }, (_, i) => make("i", i < used ? "used" : "")));
    this.el("ramLabel").textContent = `${b.wramBytes.toLocaleString("en-US")} of ${RAM_TOTAL.toLocaleString("en-US")} bytes of work RAM`;
    if (!b.measured) return;
    const { secondsPerResponse: ship, baselineSecondsPerResponse: base } = b.measured;
    this.el("speedShip").textContent = `${minutes(ship)} per reply`;
    this.el("speedBase").textContent = `${minutes(base)} per reply`;
    this.el("barShip").style.width = `${(ship / base) * 100}%`;
  }

  off() {
    this.state = -1;
    this.el("lvState").textContent = "Powered off";
    this.el("coach").textContent = OFF_COACH;
  }

  /** A blocking message in place of the usual guidance, such as a failed send. */
  say(text) { this.el("coach").textContent = text; }

  get generating() { return this.state === READING || this.state === WRITING; }

  /** Called about ten times a second while the emulator runs. */
  update(gb, composer, coachLine = null) {
    const a = this.build.addresses;
    const u8 = (name, off = 0) => gb.peek(a[name] + off);
    const u16 = (name, off = 0) => u8(name, off) | (u8(name, off + 1) << 8);
    const state = u8("wMB_State");
    this.state = state;
    this.el("lvState").textContent = STATES[state] ?? "Running";
    this.el("coach").textContent = composer.busy && !this.generating ? "Sending it to the chip." : (coachLine ?? COACH[state] ?? "");
    this.el("lvTotal").textContent = `${u16("wMB_TotalTokens").toLocaleString("en-US")} tokens since power on`;

    const generating = state === READING || state === WRITING;
    if (generating && !this.wasGenerating) this.startReply(gb, composer.takeSent());
    this.wasGenerating = generating;

    const tokens = u8("wLastEventTokens");
    if (state === REPLY && u16("wMB_Responses") && tokens) this.el("lvLast").textContent = `${tokens} tokens in ${(u16("wLastEventFrames") * FRAME_SEC).toFixed(1)} s`;

    const len = u8("wSeqLen");
    if (len > this.build.ctx || (!generating && state !== REPLY && state !== MENU)) return;
    if (generating && len >= this.build.promptLen) this.renderHeard((off) => u16("wSeq", off * 2));
    this.markTiming(gb, len, generating);
    const key = `${len}:${u16("wSeq", (len - 1) * 2)}`;
    if (key === this.lastKey) return;
    this.lastKey = key;
    this.renderTokens(gb, len, (off) => u16("wSeq", off * 2));
  }

  startReply(gb, text) {
    this.el("lvYou").textContent = text ?? "Chosen from its menu";
    this.el("you").classList.toggle("menu", text === null);
    this.el("you").hidden = false;
    this.el("lvLast").textContent = "Timing this reply";
    this.el("tokens").replaceChildren();
    this.el("strip").replaceChildren();
    this.lastKey = "";
    const now = gb.seconds();
    this.timing = { seen: this.build.promptLen, markedAt: now, live: null };
    this.addSegment("live");
  }

  addSegment(className) {
    const seg = make("i", className);
    this.el("strip").append(seg);
    this.timing.live = seg;
    return seg;
  }

  /** One block per token, as wide as the emulated time it took. The first holds the whole prompt pass. */
  markTiming(gb, len, generating) {
    const t = this.timing;
    if (!t) return;
    const now = gb.seconds();
    const fresh = len - t.seen;
    if (fresh > 0) {
      t.live.style.flexGrow = String(now - t.markedAt);
      t.live.className = t.seen === this.build.promptLen ? "first" : "";
      t.seen = len;
      t.markedAt = now;
      if (generating) this.addSegment("live");
      else this.timing = null;
    } else if (generating) {
      t.live.style.flexGrow = String(now - t.markedAt);
    }
    if (!generating && this.timing) {
      t.live.remove();
      this.timing = null;
    }
  }

  renderHeard(tokenAt) {
    const name = (i) => (this.build.vocab[tokenAt(i)] ?? "").replace(/^<\w_|>$/g, "");
    const intent = name(PROMPT_AT.intent);
    const topic = name(PROMPT_AT.topic);
    this.el("hdIntent").textContent = HEARD[intent] ?? intent.toLowerCase();
    this.el("hdTopic").textContent = topic === "NONE" ? "no topic" : topic.toLowerCase();
    this.el("hdMood").textContent = name(PROMPT_AT.mood).toLowerCase();
    this.el("hdRelation").textContent = name(PROMPT_AT.relation).toLowerCase();
    this.el("heard").hidden = false;
  }

  /** What a slot token really printed: the ROM fills these in from its save as it draws them. */
  slotValue(gb, word) {
    const a = { ...this.build.addresses, ...this.build.debug };
    const text = (addr) => {
      let out = "";
      for (let i = 0, c = gb.peek(addr); c && i < SLOT_BYTES; c = gb.peek(addr + ++i)) out += String.fromCharCode(c);
      return out;
    };
    const values = { "<NAME>": () => text(a.wName), "<LIKE>": () => text(a.wLike), "<WORD>": () => text(a.wWord), "<NI>": () => String(gb.peek(a.wInsults)), "<NP>": () => String(gb.peek(a.wPraises)), "<NT>": () => String(gb.peek(a.wTurns)) };
    return (values[word]?.() || null)?.toLowerCase() ?? null;
  }

  renderTokens(gb, len, tokenAt) {
    const frag = document.createDocumentFragment();
    for (let i = this.build.promptLen; i < len; i++) {
      const chip = this.tokenChip(gb, tokenAt(i));
      const previous = frag.lastChild;
      if (chip.classList.contains("punct") && previous) {
        // Punctuation never wraps away from the word before it.
        const pair = make("span", "pair");
        pair.append(previous, chip);
        frag.append(pair);
      } else {
        frag.append(chip);
      }
    }
    if (frag.childNodes.length) this.el("tokens").replaceChildren(frag);
  }

  tokenChip(gb, id) {
    const word = this.build.vocab[id] ?? "?";
    const chip = make("span", isControl(word) ? "tok ctl" : PUNCTUATION.test(word) ? "tok punct" : slotLabel(word) ? "tok slot" : "tok");
    chip.append(make("b", "", this.slotValue(gb, word) ?? tokenLabel(this.build.vocab, id)), make("i", "", String(id)));
    return chip;
  }
}
