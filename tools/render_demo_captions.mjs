// Draws the short demo's captions and end card in the site's own fonts, as images for tools/make_short_demo.py.
import { mkdirSync } from "node:fs";
import { startServer, launch } from "../tests/web/lib.mjs";

const OUT = "build/demo_captions";
const CAPTIONS = { name: "Tell it your name", inside: "The real chip, live", off: "Now try to turn it off", speed: "Sped up" };
mkdirSync(OUT, { recursive: true });
const srv = await startServer(8137);
const { browser, page } = await launch({ viewport: { width: 1280, height: 720 } });
await page.goto(`${srv.url}about.html`);
await page.evaluate(() => document.fonts.load('16px "Press Start 2P"'));
const blank = () => page.evaluate(() => { document.body.replaceChildren(); document.body.style.cssText = "margin:0;background:transparent;min-height:0;display:block"; const s = document.createElement("style"); s.textContent = "body::before,body::after{display:none!important}"; document.head.append(s); });
await blank();
for (const [name, text] of Object.entries(CAPTIONS)) {
  await page.evaluate(([t, small]) => {
    const el = document.createElement("div");
    el.id = "cap";
    el.textContent = t;
    el.style.cssText = small
      ? 'display:inline-block;padding:8px 10px;background:#1f1f1f;color:#c4cfa1;font:400 12px/1 "Press Start 2P",monospace;white-space:nowrap'
      : 'display:inline-block;padding:18px 22px;background:#ffd23f;color:#1f1f1f;border:5px solid #1f1f1f;font:400 28px/1 "Press Start 2P",monospace;white-space:nowrap';
    document.body.replaceChildren(el);
  }, [text, name === "speed"]);
  await page.locator("#cap").screenshot({ path: `${OUT}/${name}.png`, omitBackground: true });
}
await page.evaluate(() => {
  const card = document.createElement("div");
  card.id = "card";
  card.style.cssText = "width:1280px;height:720px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px;background:#1c3527;color:#f0e9d2;text-align:center";
  card.innerHTML = '<div style="font:400 42px/1.5 \'Press Start 2P\',monospace">A TRANSFORMER ON<br>A 1989 GAME BOY</div><div style="font:400 36px/1.2 VT323,monospace;color:#c4cfa1">Written in assembly. Running in an emulator.</div>';
  document.body.replaceChildren(card);
});
await page.evaluate(() => document.fonts.load('36px VT323'));
await page.waitForTimeout(150);
await page.locator("#card").screenshot({ path: `${OUT}/card.png` });
await browser.close();
srv.stop();
