// The words around the console. Live values come from emulated memory, so nothing here can disagree with the ROM.
import { PUNCTUATION, slotLabel, isControl, tokenLabel } from "./tokens.js";

const STATES = ["Booting", "Introducing itself", "Your turn", "On its keyboard", "Reading", "Writing", "Your turn", "Showing its internals", "Powering down"];
const READING = 4;
const WRITING = 5;
const REPLY = 6;
const MENU = 2;
const FRAME_SEC = 70224 / 4194304;
const SLOT_BYTES = 9;

const OFF_COACH = "Type something and send it. That switches the console on.";
const COACH = [
  "It's starting up. Your message can go in now.",
  "It's introducing itself. Send a message to skip this, or press A (X key).",
  "Say something, or pick a move.",
  "This is its own keyboard: arrows and A pick letters, Start sends. The box here is quicker.",
  "It's reading what you said.",
  "It's writing, about a second per word. Watch the screen.",
  "Answer it, or press A (X key) to see its own menu.",
  "These are its internals. Press B (Z key) to go back.",
  "It's shutting down. It will be back.",
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

export class Panel {
  constructor(build) {
    this.build = build;
    this.el = (id) => document.getElementById(id);
    this.lastKey = "";
    this.wasGenerating = false;
    this.timing = null;
    this.state = -1;
    this.off();
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
    const finishedNow = state === REPLY && this.state !== REPLY;
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
    if (key !== this.lastKey) {
      this.lastKey = key;
      this.renderTokens(gb, len, (off) => u16("wSeq", off * 2));
    }
    if (finishedNow) this.announceReply();
  }

  /** Screen readers get the same words the ROM wrote. Nothing else on the page repeats them. */
  announceReply() {
    const words = [...this.el("tokens").querySelectorAll(".tok:not(.ctl) b")].map((b) => b.textContent);
    this.el("spoken").textContent = words.join(" ").replace(/ ([.,!?:])/g, "$1");
  }

  startReply(gb, text) {
    this.el("lvYou").textContent = text ?? "Chosen on the console's menu";
    this.el("you").hidden = false;
    this.el("lvLast").textContent = "Timing this reply";
    this.el("tokens").replaceChildren();
    this.el("strip").replaceChildren();
    this.lastKey = "";
    this.timing = { seen: this.build.promptLen, markedAt: gb.seconds(), live: null };
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
    const heard = HEARD[intent] ?? intent.toLowerCase();
    this.el("hdIntent").textContent = heard;
    this.el("hdTopic").textContent = topic === "NONE" ? "no topic" : topic.toLowerCase();
    this.el("hdMood").textContent = name(PROMPT_AT.mood).toLowerCase();
    this.el("hdRelation").textContent = name(PROMPT_AT.relation).toLowerCase();
    this.el("heard").hidden = false;
    this.el("heardShort").textContent = topic === "NONE" ? heard : `${heard}, about ${topic.toLowerCase()}`;
    this.el("heardLine").hidden = false;
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
