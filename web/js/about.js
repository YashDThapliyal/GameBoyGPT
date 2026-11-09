// Draws the About page's bars from the build's own numbers, so the diagrams can't drift from the ROM.
const make = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};
const set = (name, text) => {
  for (const el of document.querySelectorAll(`[data-fact="${name}"]`)) el.textContent = text;
};
const size = (bytes) => (bytes >= 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes.toLocaleString("en-US")} bytes`);
const shadeOf = (segment, index) => (/^(Free|Unused)$/.test(segment.label) ? "free" : index === 0 ? "" : `s${Math.min(index, 3)}`);

function drawMemory(group, segments) {
  const total = segments.reduce((sum, s) => sum + s.bytes, 0);
  const bar = make("div", "bar");
  const legend = make("ul", "legend");
  segments.forEach((segment, i) => {
    const shade = shadeOf(segment, i);
    const seg = make("i", `seg ${shade}`);
    seg.style.flexGrow = String(segment.bytes);
    seg.style.flexBasis = "0";
    seg.title = `${segment.label}: ${size(segment.bytes)}`;
    seg.setAttribute("aria-hidden", "true");
    bar.append(seg);
    const item = make("li");
    item.append(make("i", shade), `${segment.label} ${size(segment.bytes)}`);
    legend.append(item);
  });
  bar.setAttribute("aria-label", `${size(total)} in total`);
  group.append(bar, legend);
}

function drawLadder(steps) {
  const slowest = Math.max(...steps.map((s) => s.seconds));
  document.getElementById("ladder").replaceChildren(...steps.map((step) => {
    const row = make("div", "step");
    const track = make("div", "step-track");
    const bar = make("i");
    bar.style.width = `${(step.seconds / slowest) * 80}%`;
    track.append(bar, make("b", "", `${step.seconds.toFixed(2)} s`));
    row.append(make("span", "", step.label), track);
    return row;
  }));
}

async function main() {
  const build = await (await fetch("rom/build.json")).json();
  set("params", build.params.toLocaleString("en-US"));
  set("rom", `${Math.round(build.romBytes / 1024)} KB`);
  set("wram", build.wramBytes.toLocaleString("en-US"));
  for (const group of document.querySelectorAll("[data-memory]")) drawMemory(group, build.memory[group.dataset.memory]);
  const save = build.memory.cart.find((s) => s.label === "Your save");
  set("save", size(save.bytes));
  if (build.ladder) drawLadder(build.ladder);
  if (build.measured) set("perToken", build.measured.secondsPerToken.toFixed(2));
}

main().catch(() => { document.getElementById("ladder").textContent = "Couldn't load the build's numbers. Reload the page to try again."; });
