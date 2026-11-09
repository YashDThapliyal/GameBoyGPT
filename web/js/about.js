// Fills the About page's numbers from the build's own metadata, so they can't drift from the ROM. The page reads fine without it.
const set = (name, text) => {
  for (const el of document.querySelectorAll(`[data-fact="${name}"]`)) el.textContent = text;
};

async function main() {
  const build = await (await fetch("rom/build.json")).json();
  set("params", build.params.toLocaleString("en-US"));
  set("rom", `${Math.round(build.romBytes / 1024)} KB`);
  set("vocab", String(build.vocabSize));
  set("wram", build.wramBytes.toLocaleString("en-US"));
  if (!build.measured) return;
  set("perToken", build.measured.secondsPerToken.toFixed(2));
  set("perReply", build.measured.secondsPerResponse.toFixed(1));
}

main().catch(() => { /* The written numbers stay in place. */ });
