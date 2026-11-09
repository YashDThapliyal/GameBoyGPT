// The optimization chart on the Benchmarks page. Bars and savings come from the recorded benchmark in build.json. The words are here.
const PHASES = [["keys", "Keys and values"], ["attention", "Attention"], ["feedForward", "Feed-forward"], ["output", "Output scores"], ["picking", "Picking a word"]];
const STEP_TEXT = {
  V0: { name: "Plain forward pass", why: "Multiplies the slow way, and redoes attention for every earlier token, every time.", from: "Where we started." },
  V1: { name: "Bank layout", why: "Keeps data in one memory bank. Almost nothing crossed banks, so it barely helped.", from: 'Framing from <a href="https://arxiv.org/abs/2205.14135">FlashAttention</a>: data movement is a cost.' },
  V2: { name: "Quarter-square multiply", why: "Multiplies with a table of squares instead of shift-and-add.", from: "A classic maths trick. A nibble table lost to it." },
  V3: { name: "Tight loops, row pruning", why: "Runs one tight loop per row, and skips words that can't be chosen.", from: "Our own profiling." },
  V4: { name: "Sparse attention", why: "Skips attention weights that rounded to zero. Attention was already cheap.", from: 'Same idea as the zero skips in <a href="https://github.com/crashtheuniverse/chatgbc">chatgbc</a>.' },
  V5: { name: "Cached attention", why: "Remembers earlier tokens' keys and values instead of recomputing them.", from: 'Standard transformer practice. <a href="https://github.com/maddiedreese/gbc-transformer">gbc-transformer</a> does it too.' },
  V5S: { name: "Stack-pointer reads", why: "Reads weights with the stack pointer, the quickest way on this CPU. Untested on hardware.", from: 'Also used in the <a href="https://www.elyanlabs.ai/gbc-llm.html">Elyan Labs</a> fork, which warns about the same risk.' },
  V5Z: { name: "Zero-column skip", why: "A zero input makes a whole column zero, so it skips the column.", from: 'Same idea as the zero skips in <a href="https://github.com/crashtheuniverse/chatgbc">chatgbc</a>.' },
  V6T: { name: "Per-token head tables", why: "Builds a times table for each of the 16 inputs to the output layer, so each multiply there is one lookup.", from: "Our own profile. Closest earlier idea: chatgbc's 27-sum lookup." },
};
const DEFAULT_STEP = "V5";

const make = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};

function drawLegend(host) {
  host.replaceChildren(...PHASES.map(([key, label]) => {
    const item = make("li");
    item.append(make("i", `ph-${key}`), label);
    return item;
  }));
}

function stepRow(step, slowest, select) {
  const row = make("button", "opt");
  row.type = "button";
  row.dataset.step = step.id;
  row.setAttribute("aria-pressed", "false");
  const bar = make("span", "opt-bar");
  bar.style.width = `${(step.seconds / slowest) * 100}%`;
  for (const [key, label] of PHASES) {
    const seg = make("i", `ph-${key}`);
    seg.style.flexGrow = String(step.phases[key]);
    seg.title = `${label}: ${step.phases[key].toFixed(1)} s`;
    bar.append(seg);
  }
  const track = make("span", "opt-track");
  track.append(bar, make("b", "", `${step.seconds.toFixed(1)} s`));
  row.append(make("span", "gain", step.id === "V0" ? "start" : `${step.gain.toFixed(2)}×`), make("span", "opt-name", STEP_TEXT[step.id].name), track);
  row.addEventListener("click", () => select(step.id));
  return row;
}

/** The part of the bar that shrank most, measured against the build before. */
function biggestDrop(step, before) {
  let best = null;
  for (const [key, label] of PHASES) {
    const saved = before.phases[key] - step.phases[key];
    if (!best || saved > best.saved) best = { label, saved };
  }
  return best;
}

function describe(host, step, before) {
  const text = STEP_TEXT[step.id];
  host.replaceChildren();
  host.append(make("h3", "", text.name));
  const why = make("p", "", text.why);
  host.append(why);
  if (before) {
    const saved = before.seconds - step.seconds;
    const drop = biggestDrop(step, before);
    const effect = saved < 0.5 ? "Saved under a second per reply." : `Saved ${saved.toFixed(1)} s per reply, mostly from ${drop.label.toLowerCase()}.`;
    host.append(make("p", "effect", effect));
  }
  const from = make("p", "origin");
  from.innerHTML = text.from; // Trusted text from this file.
  host.append(from);
}

export function showSteps(steps) {
  if (!steps) return;
  const slowest = steps[0].seconds;
  const detail = document.getElementById("optDetail");
  const select = (id) => {
    const at = steps.findIndex((s) => s.id === id);
    describe(detail, steps[at], steps[at - 1]);
    for (const row of document.querySelectorAll(".opt")) row.setAttribute("aria-pressed", String(row.dataset.step === id));
  };
  document.getElementById("optList").replaceChildren(...steps.map((step) => stepRow(step, slowest, select)));
  drawLegend(document.getElementById("optLegend"));
  select(DEFAULT_STEP);
}
