// Records a real session of the site. The ROM, replies and page are real and run at real speed. Only the seeds are chosen,
// and this script fails if the ROM's tokens differ from the reference. The video opens with two seconds of the ending. Run by `make demo`.
import { readFileSync, mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";
import { startServer, launch, readU8 } from "../tests/web/lib.mjs";

const { turns } = JSON.parse(readFileSync("tools/demo_seeds.json"));
const OUT = "docs/demo";
const TMP = `${OUT}/raw`;
const COLD_OPEN = { after: 0.25, length: 2 };
const POWER_DOWN = 8;
const READ = 6;
const MENU = 2;
const WRITING = 5;
mkdirSync(TMP, { recursive: true });
const srv = await startServer(8126);
const { browser, context, page } = await launch({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: TMP, size: { width: 1280, height: 720 } } });

// Headless browsers draw no cursor, and the dodging switch makes no sense without one. This is the only thing added to the page.
await page.addInitScript(() => {
  addEventListener("DOMContentLoaded", () => {
    const cursor = document.createElement("div");
    cursor.style.cssText = "position:fixed;z-index:99;left:640px;top:360px;width:18px;height:24px;pointer-events:none;background:#f0e9d2;outline:1px solid #1f1f1f;clip-path:polygon(0 0,100% 66%,55% 66%,75% 100%,50% 100%,32% 70%,0 90%)";
    document.body.append(cursor);
    addEventListener("mousemove", (e) => { cursor.style.left = `${e.clientX}px`; cursor.style.top = `${e.clientY}px`; }, true);
  });
});

const state = () => readU8(page, "wMB_State");
const waitState = async (want, ms = 60000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if ((await state()) === want) return;
    await page.waitForTimeout(40);
  }
  throw new Error(`state ${want} not reached, still ${await state()}`);
};
const tapA = async () => {
  await page.evaluate(() => window.__override.gb.press("a", true));
  await page.waitForTimeout(90);
  await page.evaluate(() => window.__override.gb.press("a", false));
  await page.waitForTimeout(90);
};
const toMenu = async () => {
  for (let i = 0; i < 200 && (await state()) !== MENU; i++) await tapA();
  await waitState(MENU);
};
// Pins the sampler so this take can be checked against the reference. It touches no tokens or weights.
const pin = (seed) => page.evaluate((s) => {
  const w = window.__override;
  w.gb.poke(w.build.debug.wMB_ForceSeed, 1);
  w.gb.poke(w.build.debug.wNarrRng, s & 255);
  w.gb.poke(w.build.debug.wNarrRng + 1, s >> 8);
}, seed);
const tokens = () => page.evaluate(() => {
  const w = window.__override; const a = w.build.addresses; const n = w.gb.peek(a.wSeqLen); const out = [];
  for (let i = 0; i < n; i++) out.push(w.gb.peek(a.wSeq + i * 2) | (w.gb.peek(a.wSeq + i * 2 + 1) << 8));
  return out;
});
const moveTo = async (selector) => {
  const box = await page.locator(selector).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 14 });
  return box;
};
const click = async (selector) => {
  await moveTo(selector);
  await page.waitForTimeout(120);
  await page.mouse.down();
  await page.waitForTimeout(70);
  await page.mouse.up();
};
const typeMessage = async (text) => {
  await click("#say");
  await page.keyboard.type(text.toLowerCase(), { delay: 45 });
  await page.waitForTimeout(150);
  await page.keyboard.press("Enter");
};
// From the second try the switch runs away from the cursor, so it takes a few goes to catch.
const flipSwitch = async () => {
  for (let i = 0; i < 6; i++) {
    const box = await moveTo("#power");
    await page.waitForTimeout(200);
    const now = await page.locator("#power").boundingBox();
    if (now.x === box.x) break;
  }
  await page.waitForTimeout(100);
  await page.mouse.down();
  await page.waitForTimeout(70);
  await page.mouse.up();
};
const finishTurn = async (turn, readSeconds) => {
  await waitState(READ);
  assert.deepEqual(await tokens(), turn.tokens, `the ROM must replay the reference for "${turn.say}"`);
  await page.waitForTimeout(readSeconds * 1000);
};
const nextTurn = async (turn) => {
  await toMenu();
  await page.waitForTimeout(60);
  await pin(turn.seed);
};

await page.goto(srv.url);
await page.waitForTimeout(500);
const t0 = Date.now();
await click("#power");
await page.waitForFunction(() => window.__override?.gb?.e);
await page.waitForTimeout(1400);

const [name, smash, ...shutdowns] = turns;
await nextTurn(name);
await typeMessage(name.say);
await finishTurn(name, 1.3);

await nextTurn(smash);
await typeMessage(smash.say);
await waitState(WRITING);
await click("#btnXray");
await finishTurn(smash, 1.8);
await click("#btnXray");
await page.waitForTimeout(800);

for (const turn of shutdowns) {
  await nextTurn(turn);
  await flipSwitch();
  await finishTurn(turn, turn === shutdowns.at(-1) ? 0.9 : 1.1);
}
await click("#plug");
await waitState(POWER_DOWN);
await page.waitForFunction(() => document.documentElement.dataset.fight === "takeover", null, { timeout: 30000 });
const takeoverAt = (Date.now() - t0) / 1000;
await page.mouse.move(1270, 710, { steps: 6 });
await page.waitForFunction(() => /connected to anything/.test(document.getElementById("toLine").textContent), null, { timeout: 15000 });
await page.waitForTimeout(1800);

const seconds = (Date.now() - t0) / 1000;
await page.screenshot({ path: `${OUT}/final_frame.png` });
const video = page.video();
await context.close();
await browser.close();
srv.stop();
const raw = `${OUT}/raw.webm`;
renameSync(await video.path(), raw);
rmSync(TMP, { recursive: true, force: true });
const ffmpeg = (args) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...args]);
const rawSeconds = Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", raw]).toString());
const start = Math.max(0, rawSeconds - seconds - 0.1);
const openStart = start + takeoverAt + COLD_OPEN.after;
const graph = `[0:v]trim=start=${openStart}:duration=${COLD_OPEN.length},setpts=PTS-STARTPTS[open];[0:v]trim=start=${start},setpts=PTS-STARTPTS[main];[open][main]concat=n=2:v=1[out]`;
ffmpeg(["-i", raw, "-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", `${OUT}/system_override_demo.mp4`]);
ffmpeg(["-i", `${OUT}/system_override_demo.mp4`, "-vf", "fps=10,scale=480:-1:flags=neighbor,split[a][b];[a]palettegen=max_colors=32[p];[b][p]paletteuse=dither=none", `${OUT}/system_override_demo.gif`]);
rmSync(raw);
writeFileSync(`${OUT}/demo_tokens.json`, JSON.stringify({ seconds, coldOpenSeconds: COLD_OPEN.length, turns: turns.map((t) => ({ say: t.say, reply: t.reply, tokens: t.tokens })) }));
console.log(JSON.stringify({ seconds, takeoverAt, replies: turns.map((t) => t.reply) }));
