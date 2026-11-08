// Records a real session of the browser handheld. Nothing is composited except the page itself. Run by `make demo`.
import { readFileSync, mkdirSync, renameSync, readdirSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { startServer, launch, readU8 } from "../tests/web/lib.mjs";

const seeds = JSON.parse(readFileSync("tools/demo_seeds.json"));
const OUT = "docs/demo";
const TMP = `${OUT}/raw`;
mkdirSync(TMP, { recursive: true });
const srv = await startServer(8126);
const { browser, context, page } = await launch({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: TMP, size: { width: 1280, height: 720 } } });

const state = (p) => readU8(p, "wMB_State");
const waitState = async (want, ms = 60000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if ((await state(page)) === want) return;
    await page.waitForTimeout(40);
  }
  throw new Error(`state ${want} not reached`);
};
const press = async (name, ms = 110) => {
  const box = await page.locator(`[data-pad=${name}]`).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 6 });
  await page.mouse.down();
  await page.waitForTimeout(ms);
  await page.mouse.up();
  await page.waitForTimeout(90);
};
// Pins the sampler so this recording can be replayed and checked. It does not touch the tokens or the weights.
const pin = (seed) => page.evaluate((s) => {
  const w = window.__override;
  w.gb.m._emulator_write_mem(w.gb.e, w.build.debug.wMB_ForceSeed, 1);
  w.gb.m._emulator_write_mem(w.gb.e, w.build.debug.wNarrRng, s & 255);
  w.gb.m._emulator_write_mem(w.gb.e, w.build.debug.wNarrRng + 1, s >> 8);
}, seed);
const tokens = () => page.evaluate(() => {
  const w = window.__override; const a = w.build.addresses; const n = w.gb.peek(a.wSeqLen); const out = [];
  for (let i = 0; i < n; i++) out.push(w.gb.peek(a.wSeq + i * 2) | (w.gb.peek(a.wSeq + i * 2 + 1) << 8));
  return out;
});

await page.goto(`${srv.url}?demo=1`);
await page.waitForTimeout(700);
const t0 = Date.now();
await page.locator("#power").click();
await page.waitForFunction(() => window.__override?.gb?.e);
// Boot, corruption and logo play at full length. The fixed lines are skipped one by one once read.
for (let i = 0; i < 120 && (await state(page)) !== 2; i++) {
  const onIntroText = await page.evaluate(() => { const w = window.__override; return w.gb.peek(w.build.debug.wRobotOn) === 1 && w.gb.peek(w.build.addresses.wMB_State) === 1; });
  if (onIntroText) {
    await page.waitForTimeout(800);
    await press("a");
  } else {
    await page.waitForTimeout(100);
  }
}
await waitState(2);
await page.waitForTimeout(450);
await press("right");
await page.waitForTimeout(200);
await pin(seeds.first);
await press("a");
await waitState(6);
const first = await tokens();
await page.waitForTimeout(1300);
await press("a");
await waitState(2, 5000);
await page.waitForTimeout(300);
await pin(seeds.second);
await press("a");
await waitState(6);
const second = await tokens();
await page.waitForTimeout(2200);
const seconds = (Date.now() - t0) / 1000;
await page.screenshot({ path: `${OUT}/final_frame.png` });
const video = page.video();
await context.close();
await browser.close();
srv.stop();
const raw = await video.path();
renameSync(raw, `${OUT}/raw.webm`);
rmSync(TMP, { recursive: true, force: true });
const f = (args) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...args]);
f(["-ss", "0.6", "-i", `${OUT}/raw.webm`, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", `${OUT}/system_override_demo.mp4`]);
f(["-i", `${OUT}/system_override_demo.mp4`, "-vf", "crop=500:720:200:0,fps=12,scale=320:-1:flags=neighbor,split[a][b];[a]palettegen=max_colors=48[p];[b][p]paletteuse=dither=none", `${OUT}/system_override_demo.gif`]);
rmSync(`${OUT}/raw.webm`);
const expectFile = { seconds, first, second };
console.log(JSON.stringify(expectFile));
import("node:fs").then((fs) => fs.writeFileSync(`${OUT}/demo_tokens.json`, JSON.stringify(expectFile)));
