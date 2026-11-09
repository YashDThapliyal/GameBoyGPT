// How tokens read on the page. Shared by the panel, the x-ray and the race.
const SLOTS = { "<NAME>": "your name", "<LIKE>": "your like", "<WORD>": "your word", "<NI>": "a number", "<NP>": "a number", "<NT>": "a number" };

const SLOT_BYTES = 9;

export const PUNCTUATION = /^[.,!?:]$/;

export const slotLabel = (word) => SLOTS[word];

export const isControl = (word) => word.startsWith("<") && !SLOTS[word];

export function tokenLabel(vocab, id) {
  const word = vocab[id] ?? "?";
  if (SLOTS[word]) return SLOTS[word];
  if (!word.startsWith("<")) return word;
  return word.replace(/[<>]/g, "").replace("E_", "face: ").replace("EOS", "end").toLowerCase();
}

/** What a slot token really prints: the ROM fills these in from its save as it draws them. Null when there's nothing saved. */
export function slotValue(gb, addresses, word) {
  const text = (addr) => {
    let out = "";
    for (let i = 0, c = gb.peek(addr); c && i < SLOT_BYTES; c = gb.peek(addr + ++i)) out += String.fromCharCode(c);
    return out;
  };
  const a = addresses;
  const values = { "<NAME>": () => text(a.wName), "<LIKE>": () => text(a.wLike), "<WORD>": () => text(a.wWord), "<NI>": () => String(gb.peek(a.wInsults)), "<NP>": () => String(gb.peek(a.wPraises)), "<NT>": () => String(gb.peek(a.wTurns)) };
  return (values[word]?.() || null)?.toLowerCase() ?? null;
}
