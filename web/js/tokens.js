// How tokens read on the page. Shared by the panel, the x-ray and the race.
const SLOTS = { "<NAME>": "your name", "<LIKE>": "your like", "<WORD>": "your word", "<NI>": "a number", "<NP>": "a number", "<NT>": "a number" };

export const PUNCTUATION = /^[.,!?:]$/;

export const slotLabel = (word) => SLOTS[word];

export const isControl = (word) => word.startsWith("<") && !SLOTS[word];

export function tokenLabel(vocab, id) {
  const word = vocab[id] ?? "?";
  if (SLOTS[word]) return SLOTS[word];
  if (!word.startsWith("<")) return word;
  return word.replace(/[<>]/g, "").replace("E_", "face: ").replace("EOS", "end").toLowerCase();
}
