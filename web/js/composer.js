// Gets text from the page's box into the ROM. It works the handheld the way a player would: buttons to reach the ROM's own
// keyboard screen, then the text goes into that screen's input buffer and Start sends it. The ROM parses it and the model replies.
const ST = { BOOT: 0, INTRO: 1, MENU: 2, KEYBOARD: 3, READING: 4, WRITING: 5, REPLY: 6, INSPECT: 7, OFF_ANIM: 8 };
const TYPE_ITEM = 7;
const HOLD_SEC = 0.07;
const GAP_SEC = 0.07;
const KEYBOARD_SETTLE_SEC = 0.25;
const RESEND_AFTER_SEC = 1;
const GIVE_UP_SEC = 45;

export const MAX_INPUT = 36;

/** What the ROM's keyboard can type: capitals, digits and a little punctuation. Everything else becomes a space. */
export function cleanText(raw) {
  return raw.toUpperCase().replace(/[‘’]/g, "'").replace(/[^A-Z0-9',.?!-]+/g, " ").trim().slice(0, MAX_INPUT).trim();
}

export class Composer {
  constructor(getEmulator, addresses, onGiveUp) {
    this.getEmulator = getEmulator;
    this.a = addresses;
    this.onGiveUp = onGiveUp;
    this.pending = null;
    this.tap = null;
    this.sent = null;
  }

  get busy() { return this.pending !== null; }

  send(text) {
    this.pending = { text, wroteAt: null, keyboardAt: null, startedAt: null };
  }

  cancel() {
    this.pending = null;
    this.tap = null;
  }

  /** The text behind the reply now starting, or null when it came from the on-screen menu. */
  takeSent() {
    const text = this.sent;
    this.sent = null;
    return text;
  }

  /** Runs once per browser frame. Timing uses emulated seconds, so a slow or fast display changes nothing. */
  step() {
    const gb = this.getEmulator();
    if (!this.pending || !gb?.e) return;
    const now = gb.seconds();
    const p = this.pending;
    p.startedAt ??= now;
    if (now - p.startedAt > GIVE_UP_SEC) {
      this.cancel();
      this.onGiveUp(p.text);
      return;
    }
    if (this.tap && this.runTap(gb, now)) return;
    this.advance(gb, now, p);
  }

  /** Returns true while a button press is still in progress. */
  runTap(gb, now) {
    const t = this.tap;
    if (t.down && now - t.at >= HOLD_SEC) {
      gb.press(t.name, false);
      t.down = false;
      t.at = now;
    }
    if (!t.down && now - t.at >= GAP_SEC) this.tap = null;
    return this.tap !== null;
  }

  press(gb, now, name) {
    gb.press(name, true);
    this.tap = { name, down: true, at: now };
  }

  advance(gb, now, p) {
    const state = gb.peek(this.a.wMB_State);
    if (state === ST.BOOT || state === ST.INTRO || state === ST.REPLY) this.press(gb, now, "a");
    else if (state === ST.INSPECT) this.press(gb, now, "b");
    else if (state === ST.MENU) this.chooseTypeItem(gb, now);
    else if (state === ST.KEYBOARD) this.fillKeyboard(gb, now, p);
    else if ((state === ST.READING || state === ST.WRITING) && p.wroteAt !== null) this.pending = null;
  }

  chooseTypeItem(gb, now) {
    const sel = gb.peek(this.a.wMenuSel);
    if (sel === TYPE_ITEM) this.press(gb, now, "a");
    else this.press(gb, now, (sel >> 1) !== (TYPE_ITEM >> 1) ? "down" : "right");
  }

  fillKeyboard(gb, now, p) {
    p.keyboardAt ??= now;
    if (now - p.keyboardAt < KEYBOARD_SETTLE_SEC) return;
    if (p.wroteAt !== null && now - p.wroteAt < RESEND_AFTER_SEC) return;
    const bytes = Array.from(p.text, (c) => c.charCodeAt(0));
    bytes.forEach((b, i) => gb.poke(this.a.wInput + i, b));
    gb.poke(this.a.wInput + bytes.length, 0);
    gb.poke(this.a.wInputLen, bytes.length);
    p.wroteAt = now;
    this.sent = p.text;
    this.press(gb, now, "start");
  }
}
