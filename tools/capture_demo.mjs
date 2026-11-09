// Records a real session of the site. The ROM, replies and page are real and run at real speed. Only the seeds are chosen,
// and this script fails if the ROM's tokens differ from the reference. The video opens with two seconds of the ending. Run by `make demo`.
import { readFileSync, mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";
import { startServer, launch, readU8 } from "../tests/web/lib.mjs";

const { turns } = JSON.parse(readFileSync("tools/demo_seeds.json"));
const OUT = "docs/demo";
const TMP = `${OUT}/raw`;
const COLD_OPEN = { after: 0.3, length: 2 };
const POWER_DOWN = 8;
const READ = 6;
const MENU = 2;
const WRITING = 5;
mkdirSync(TMP, { recursive: true });
const srv = await startServer(8126);
const { browser, context, page } = await launch({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: TMP, size: { width: 1280, height: 720 } } });

const recordingStart = Date.now();
const timeline = [];
const mark = (name) => timeline.push({ name, at: Date.now() });

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
const finishTurn = async (turn, readSeconds, readMark) => {
  await waitState(READ);
  mark(readMark);
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
mark("power");
await click("#power");
mark("powered");
await page.waitForFunction(() => window.__override?.gb?.e);
await page.waitForTimeout(1400);

const [name, smash, ...shutdowns] = turns;
await nextTurn(name);
mark("typeName");
await typeMessage(name.say);
mark("waitName");
await finishTurn(name, 1.6, "readName");

mark("toSmash");
await nextTurn(smash);
mark("typeSmash");
await typeMessage(smash.say);
mark("waitSmash");
await waitState(WRITING);
mark("coverOff");
await click("#btnXray");
await page.waitForTimeout(800);
mark("chipLive");
await finishTurn(smash, 1.8, "readSmash");
mark("coverOn");
await click("#btnXray");
await page.waitForTimeout(800);

for (const [i, turn] of shutdowns.entries()) {
  mark(`toFlip${i}`);
  await nextTurn(turn);
  mark(`flip${i}`);
  await flipSwitch();
  mark(`waitFlip${i}`);
  await finishTurn(turn, 1.4, `readFlip${i}`);
}
mark("plug");
await click("#plug");
await waitState(POWER_DOWN);
await page.waitForTimeout(2300);
mark("fade");
await page.waitForFunction(() => document.documentElement.dataset.fight === "takeover", null, { timeout: 30000 });
mark("takeover");
const takeoverAt = (Date.now() - t0) / 1000;
await page.mouse.move(1270, 710, { steps: 6 });
await page.waitForFunction(() => /connected to anything/.test(document.getElementById("toLine").textContent), null, { timeout: 15000 });
await page.waitForTimeout(1800);
mark("end");

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
// Screencast time drifts from wall time, so both are tied to two moments visible in the footage: the LED lighting up and the takeover filling the page.
const firstFrameWhere = (crop, matches) => {
  const fps = 20;
  const bytes = execFileSync("ffmpeg", ["-loglevel", "error", "-i", raw, "-vf", `fps=${fps},format=rgb24,crop=${crop}`, "-f", "rawvideo", "-"], { maxBuffer: 1 << 28 });
  for (let i = 0; i < bytes.length; i += 3) if (matches(bytes[i], bytes[i + 1], bytes[i + 2])) return i / 3 / fps;
  throw new Error(`no frame matched for crop ${crop}`);
};
const atWall = (name) => (timeline.find((m) => m.name === name).at - t0) / 1000;
const ledFrame = firstFrameWhere("1:1:150:218", (r, g) => r > 170 && g < 110);
const takeoverFrame = firstFrameWhere("1:1:1200:90", (r, g) => r > 170 && g > 180);
const scale = (takeoverFrame - ledFrame) / (atWall("takeover") - atWall("powered"));
const videoAt = (wallSeconds) => ledFrame + (wallSeconds - atWall("powered")) * scale;
const start = Math.max(0, videoAt(0));
const videoSeconds = videoAt(seconds) - start;
// The finished video plays at true speed: its clock and the timeline below are real seconds.
const openStart = takeoverFrame + COLD_OPEN.after;
const graph = `[0:v]trim=start=${openStart}:duration=${COLD_OPEN.length * scale},setpts=(PTS-STARTPTS)/${scale}[open];[0:v]trim=start=${start}:duration=${videoSeconds},setpts=(PTS-STARTPTS)/${scale}[main];[open][main]concat=n=2:v=1[out]`;
ffmpeg(["-i", raw, "-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", `${OUT}/system_override_demo.mp4`]);
rmSync(raw);
writeFileSync(`${OUT}/demo_tokens.json`, JSON.stringify({ seconds, coldOpenSeconds: COLD_OPEN.length, timeline: timeline.map((m) => ({ name: m.name, seconds: (m.at - t0) / 1000 })), turns: turns.map((t) => ({ say: t.say, reply: t.reply, tokens: t.tokens })) }));
console.log(JSON.stringify({ seconds, videoSeconds, scale, ledFrame, takeoverFrame, replies: turns.map((t) => t.reply) }));
