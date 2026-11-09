// Records the tweet GIF: a real message, the cover coming off, and the real chip generating a reply.
// The seed is chosen, and this script fails unless the ROM's tokens equal the reference's. Run by `make gif`.
import { readFileSync, mkdirSync, renameSync, rmSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";
import { startServer, launch, readU8 } from "../tests/web/lib.mjs";

const { setup, take } = JSON.parse(readFileSync("tools/gif_take.json"));
const OUT = "docs/demo";
const TMP = `${OUT}/rawgif`;
const GIF = `${OUT}/gameboygpt.gif`;
const SPEED = 1.5;
const LEAD_IN_SEC = 1.4;
const HOLD_SEC = 2.2;
const CONSOLE_UNIT = "1.5px"; // three screen pixels per LCD pixel
const STRIP = 54;
const MENU = 2;
const READ = 6;
const WRITING = 5;
mkdirSync(TMP, { recursive: true });
const srv = await startServer(8139);
process.on("exit", () => srv.stop());
const { browser, context, page } = await launch({ viewport: { width: 1400, height: 1120 }, recordVideo: { dir: TMP, size: { width: 1400, height: 1120 } } });

const state = () => readU8(page, "wMB_State");
const waitState = async (want, ms = 90000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if ((await state()) === want) return;
    await page.waitForTimeout(30);
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
const send = async (text) => {
  await page.locator("#say").fill(text);
  await page.locator("#say").press("Enter");
};

await page.goto(srv.url);
await page.evaluate((u) => { document.documentElement.style.setProperty("--u", u); window.addEventListener("resize", (e) => e.stopImmediatePropagation(), true); }, CONSOLE_UNIT);
await page.waitForTimeout(300);
const box = await page.locator("#device").boundingBox();
await page.locator("#power").click();
const ledAt = Date.now();
await page.waitForFunction(() => window.__override?.gb?.e);
await page.waitForTimeout(1200);
await toMenu();
await pin(setup.seed);
await send(setup.say);
await waitState(READ);
assert.deepEqual(await tokens(), setup.tokens, "setup turn must replay the reference");
await page.waitForTimeout(300);
await toMenu();
await page.waitForTimeout(LEAD_IN_SEC * 1000);
await pin(take.seed);
const sentAt = Date.now();
await send(take.say);
await waitState(WRITING);
await page.locator("#btnXray").click();
await page.waitForFunction(() => getComputedStyle(document.getElementById("cover")).visibility === "hidden" && document.getElementById("cover").getAnimations().every((x) => x.playState === "finished"));
const coverGoneAt = Date.now();
await waitState(READ);
assert.deepEqual(await tokens(), take.tokens, "the take must replay the reference");
await page.waitForTimeout(HOLD_SEC * 1000);
const endAt = Date.now();

// Text for the strip above the console, in the site's own font.
await page.evaluate((text) => {
  const cap = document.createElement("div");
  cap.id = "gifcap";
  cap.textContent = text;
  cap.style.cssText = `position:fixed;left:0;top:0;z-index:99;width:${576}px;height:${54}px;display:flex;align-items:center;justify-content:center;background:#1c3527;color:#f0e9d2;font:400 18px/1 "Press Start 2P",monospace`;
  document.body.append(cap);
}, `You: ${take.say}`);
mkdirSync("build", { recursive: true });
await page.locator("#gifcap").screenshot({ path: "build/gif_strip.png" });
const video = page.video();
await context.close();
await browser.close();
const raw = `${OUT}/rawgif.webm`;
renameSync(await video.path(), raw);
rmSync(TMP, { recursive: true, force: true });

const firstFrameWhere = (crop, matches, afterSeconds = 0) => {
  const fps = 20;
  const bytes = execFileSync("ffmpeg", ["-loglevel", "error", "-i", raw, "-vf", `fps=${fps},format=rgb24,crop=${crop}`, "-f", "rawvideo", "-"], { maxBuffer: 1 << 28 });
  for (let i = Math.round(afterSeconds * fps) * 3; i < bytes.length; i += 3) if (matches(bytes[i], bytes[i + 1], bytes[i + 2])) return i / 3 / fps;
  throw new Error(`no frame matched for crop ${crop}`);
};
const ledFrame = firstFrameWhere(`1:1:${Math.round(box.x + 36)}:${Math.round(box.y + 222)}`, (r, g) => r > 170 && g < 110);
// A spot where the cream cover gives way to the green board.
const boardFrame = firstFrameWhere(`1:1:${Math.round(box.x + 300)}:${Math.round(box.y + 930)}`, (r, g, b) => r < 60 && g > 56 && g < 90 && b < 70, ledFrame + 3);
const scale = (boardFrame - ledFrame) / ((coverGoneAt - ledAt) / 1000);
const videoAt = (at) => ledFrame + ((at - ledAt) / 1000) * scale;
const start = videoAt(sentAt) - LEAD_IN_SEC * scale;
const length = videoAt(endAt) - start;
const crop = `${576}:${954}:${Math.round(box.x)}:${Math.round(box.y)}`;
const graph = `[0:v]trim=start=${start}:duration=${length},setpts=(PTS-STARTPTS)/${scale * SPEED},crop=${crop},pad=576:${954 + STRIP}:0:${STRIP}:0x1c3527[c];[c][1:v]overlay=0:0,fps=12,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle`;
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", raw, "-i", "build/gif_strip.png", "-filter_complex", graph, GIF]);
rmSync(raw);
srv.stop();
console.log(JSON.stringify({ seconds: length / (scale * SPEED), scale, megabytes: +(statSync(GIF).size / 1048576).toFixed(1), reply: take.reply }));
