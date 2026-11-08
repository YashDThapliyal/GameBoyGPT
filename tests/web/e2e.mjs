// The browser handheld, end to end, in headless Chromium: the real ROM in WebAssembly, the real page, simulated hands.
import { readFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";
import { startServer, launch, readU8 } from "./lib.mjs";

const SHOTS = "docs/screenshots";
mkdirSync(SHOTS, { recursive: true });
execFileSync(".venv/bin/python", ["tools/web_expected.py"]);
const expected = JSON.parse(readFileSync("tests/web/expected.json"));
const srv = await startServer(8125);
const results = [];
const check = async (name, fn) => {
  await fn();
  results.push(name);
  console.log(`ok - ${name}`);
};

const seqTokens = (page) => page.evaluate(() => {
  const w = window.__override; const a = w.build.addresses; const n = w.gb.peek(a.wSeqLen); const out = [];
  for (let i = 0; i < n; i++) out.push(w.gb.peek(a.wSeq + i * 2) | (w.gb.peek(a.wSeq + i * 2 + 1) << 8));
  return out;
});
const state = (page) => readU8(page, "wMB_State");
const waitState = async (page, want, ms = 90000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if ((await state(page)) === want) return;
    await page.waitForTimeout(100);
  }
  throw new Error(`state ${want} not reached, still ${await state(page)}`);
};
const hold = async (page, name) => {
  const el = page.locator(`[data-pad=${name}]`);
  const box = await el.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(90);
  await page.mouse.up();
  await page.waitForTimeout(90);
};
const toMenu = async (page) => {
  for (let i = 0; i < 80 && (await state(page)) !== 2; i++) {
    await page.keyboard.press("KeyX", { delay: 80 });
    await page.waitForTimeout(300);
  }
  assert.equal(await state(page), 2);
};
const pinSeed = (page, seed) => page.evaluate((s) => {
  // Test-only write through the emulator's debug interface, so a run is comparable with the reference.
  const w = window.__override; const m = w.gb.m; const e = w.gb.e;
  m._emulator_write_mem(e, w.build.debug.wMB_ForceSeed, 1);
  m._emulator_write_mem(e, w.build.debug.wNarrRng, s & 255);
  m._emulator_write_mem(e, w.build.debug.wNarrRng + 1, s >> 8);
}, seed);

{
  const { browser, page } = await launch();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(srv.url);
  await check("page loads powered off, with build facts from the ROM's metadata", async () => {
    assert.equal(await page.locator("#lvState").innerText(), "Powered off");
    assert.match(await page.locator("#build").innerText(), /parameters/);
  });
  await check("the power switch boots the ROM", async () => {
    await page.locator("#power").click();
    await page.waitForFunction(() => window.__override?.gb?.e);
    await page.waitForTimeout(1500);
    assert.ok((await readU8(page, "wMB_State")) <= 2);
    assert.equal(await page.locator("#led").getAttribute("class"), "led on");
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/web_boot.png` });
  await check("the canvas shows real frames, 160 x 144, nearest neighbour", async () => {
    const info = await page.evaluate(() => {
      const c = document.getElementById("screen");
      const d = c.getContext("2d").getImageData(0, 0, 160, 144).data;
      const colours = new Set();
      for (let i = 0; i < d.length; i += 4) colours.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
      return { w: c.width, h: c.height, colours: colours.size, css: getComputedStyle(c).imageRendering, cw: c.getBoundingClientRect().width };
    });
    assert.equal(info.w, 160);
    assert.equal(info.h, 144);
    assert.ok(info.colours >= 2 && info.colours <= 4, `colours ${info.colours}`);
    assert.equal(info.css, "pixelated");
    assert.equal(info.cw % 160, 0, `scale ${info.cw / 160} must be whole at device pixel ratio 1`);
  });
  await check("keyboard skips the intro", async () => { await toMenu(page); });
  await check("responses generated in the browser equal the integer reference, token for token", async () => {
    for (const [i, step] of expected.entries()) {
      await page.waitForTimeout(250);
      await pinSeed(page, step.seed);
      for (let n = 0; n < 12 && (await readU8(page, "wMenuSel")) !== step.action; n++) {
        const cur = await readU8(page, "wMenuSel");
        await hold(page, (cur >> 1) !== (step.action >> 1) ? "down" : "right");
      }
      assert.equal(await readU8(page, "wMenuSel"), step.action);
      await hold(page, "a");
      await waitState(page, 6);
      assert.deepEqual(await seqTokens(page), step.tokens, `response ${i}`);
      if (i === 1) await page.screenshot({ path: `${SHOTS}/web_response.png` });
      await hold(page, "a");
      await waitState(page, 2, 5000);
    }
    const chips = await page.locator("#tokens .tok").count();
    assert.equal(chips, expected.at(-1).tokens.length - 9);
  });
  await check("each d-pad and action button responds to the mouse, with a visible press", async () => {
    const before = await readU8(page, "wMenuSel");
    const box = await page.locator("[data-pad=down]").boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.waitForTimeout(60);
    assert.match(await page.locator("[data-pad=down]").getAttribute("class") ?? "", /down/);
    await page.mouse.up();
    await page.waitForTimeout(120);
    assert.notEqual(await readU8(page, "wMenuSel"), before);
    for (const name of ["up", "left", "right", "b", "start", "select"]) await page.locator(`[data-pad=${name}]`).isVisible();
  });
  await check("select opens the inspector and b returns", async () => {
    await hold(page, "select");
    await waitState(page, 7, 4000);
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${SHOTS}/web_inspector.png` });
    await hold(page, "b");
    await waitState(page, 2, 4000);
  });
  await check("the keyboard screen opens and start sends typed text", async () => {
    for (let n = 0; n < 12 && (await readU8(page, "wMenuSel")) !== 7; n++) {
      const cur = await readU8(page, "wMenuSel");
      await hold(page, (cur >> 1) !== 3 ? "down" : "right");
    }
    await hold(page, "a");
    await waitState(page, 3, 4000);
    await page.waitForTimeout(400);
    await hold(page, "a");
    await hold(page, "right");
    await hold(page, "a");
    await page.screenshot({ path: `${SHOTS}/web_keyboard.png` });
    await page.keyboard.press("Enter", { delay: 80 });
    await waitState(page, 6);
    await hold(page, "a");
    await waitState(page, 2, 5000);
  });
  await check("typing in the page's box leaves the joypad alone until it is sent", async () => {
    const before = await readU8(page, "wMenuSel");
    await page.locator("#say").click();
    await page.keyboard.type("xz");
    await page.keyboard.press("ArrowDown");
    await page.waitForTimeout(200);
    assert.equal(await state(page), 2);
    assert.equal(await readU8(page, "wMenuSel"), before);
    assert.equal(await page.locator("#say").inputValue(), "xz");
    await page.locator("#say").fill("");
    await page.evaluate(() => document.activeElement.blur());
  });
  await check("a typed message reaches the ROM's parser and the panel shows what it heard", async () => {
    const vocab = await page.evaluate(() => window.__override.build.vocab);
    // The previous reply is still on screen after sending, so wait for the panel to start the new one first.
    const replyTo = async (text) => {
      await page.waitForFunction((t) => document.getElementById("lvYou").textContent === t, text, { timeout: 30000 });
      await waitState(page, 6);
      return seqTokens(page);
    };
    const send = async (text) => {
      await page.locator("#say").fill(text);
      await page.locator("#say").press("Enter");
      return replyTo(text.toUpperCase());
    };
    let seq = await send("what is your cpu?");
    assert.equal(vocab[seq[6]], "<I_TECH>");
    assert.equal(vocab[seq[7]], "<T_CPU>");
    await page.waitForTimeout(300);
    assert.equal(await page.locator("#lvYou").innerText(), "WHAT IS YOUR CPU?");
    assert.equal(await page.locator("#hdIntent").innerText(), "a hardware question");
    assert.equal(await page.locator("#hdTopic").innerText(), "cpu");
    assert.equal(await page.locator("#strip i").count(), seq.length - 9);
    await page.screenshot({ path: `${SHOTS}/web_typed.png` });
    // Sent straight from the reply screen, without going back to the menu by hand.
    seq = await send("do you have a soul");
    assert.equal(vocab[seq[6]], "<I_UNKNOWN>");
    await page.waitForTimeout(300);
    assert.equal(await page.locator("#hdIntent").innerText(), "nothing it recognizes");
    await page.getByRole("button", { name: "You are dumb" }).click();
    seq = await replyTo("YOU ARE DUMB");
    assert.equal(vocab[seq[6]], "<I_INSULT>");
    await hold(page, "a");
    await waitState(page, 2, 5000);
  });
  await check("the page stays responsive during inference", async () => {
    await hold(page, "down");
    await hold(page, "a");
    await waitState(page, 5, 15000);
    const lag = await page.evaluate(() => new Promise((res) => {
      let worst = 0; let last = performance.now(); let n = 0;
      const tick = () => { const now = performance.now(); worst = Math.max(worst, now - last); last = now; if (++n < 60) requestAnimationFrame(tick); else res(worst); };
      requestAnimationFrame(tick);
    }));
    assert.ok(lag < 250, `worst frame gap ${lag} ms`);
    await waitState(page, 6);
    await hold(page, "a");
  });
  await check("clean display mode shows plain gray with no overlays, and options restore", async () => {
    await page.locator("#more").evaluate((el) => { el.open = true; });
    await page.locator("#optClean").check();
    await page.waitForTimeout(300);
    const v = await page.evaluate(() => ({ grid: getComputedStyle(document.querySelector(".lcd-grid")).display, glass: getComputedStyle(document.querySelector(".lcd-glass")).display, px: Array.from(document.getElementById("screen").getContext("2d").getImageData(159, 70, 1, 1).data).slice(0, 3) }));
    assert.equal(v.grid, "none");
    assert.equal(v.glass, "none");
    assert.equal(v.px[0], v.px[1]);
    await page.screenshot({ path: `${SHOTS}/web_clean.png` });
    await page.locator("#optClean").uncheck();
  });
  await check("memory survives a reload through browser storage", async () => {
    const turns = await page.evaluate(() => { const w = window.__override; return w.gb.peek(w.build.debug.wTurns); });
    assert.ok(turns >= 3);
    await page.locator("#btnPower").click();
    await page.reload();
    await page.locator("#more").evaluate((el) => { el.open = true; });
    await page.locator("#btnPower").click();
    await page.waitForFunction(() => window.__override?.gb?.e);
    await page.waitForTimeout(2500);
    const after = await page.evaluate(() => { const w = window.__override; return [w.gb.peek(w.build.debug.wTurns), w.gb.peek(w.build.debug.wReturning)]; });
    assert.equal(after[0], turns);
    assert.equal(after[1], 1);
  });
  await check("reset restarts the ROM and no script errors occurred", async () => {
    await page.locator("#btnReset").click();
    await page.waitForFunction(() => window.__override?.gb?.e);
    await page.waitForTimeout(800);
    assert.equal(await page.locator("#lcdMsg").innerText(), "");
    assert.equal(await page.locator("#btnPower").innerText(), "Turn off");
    assert.deepEqual(errors, []);
  });
  await check("sending a message with the console off boots it and gets through the intro", async () => {
    await page.locator("#btnPower").click();
    await page.locator("#say").fill("hello");
    await page.locator("#say").press("Enter");
    await page.waitForFunction(() => window.__override?.gb?.e);
    await waitState(page, 6);
    const vocab = await page.evaluate(() => window.__override.build.vocab);
    assert.equal(vocab[(await seqTokens(page))[6]], "<I_GREET>");
    assert.deepEqual(errors, []);
  });
  await check("switching off in the middle of a reply leaves Send usable", async () => {
    await page.locator("#say").fill("tell me a joke");
    await page.locator("#say").press("Enter");
    await waitState(page, 5);
    assert.equal(await page.locator("#send").isDisabled(), true);
    await page.locator("#btnPower").click();
    assert.equal(await page.locator("#send").isDisabled(), false);
    await page.locator("#btnPower").click();
    await page.waitForFunction(() => window.__override?.gb?.e);
  });
  await check("the x-ray draws live memory, and the picked token is among the real candidates", async () => {
    await page.locator("#btnXray").click();
    assert.equal(await page.locator("#xrayPanel").isVisible(), true);
    assert.equal(await page.locator("#specs").isVisible(), false);
    await waitState(page, 6, 45000).catch(() => {});
    for (let i = 0; i < 80 && (await state(page)) !== 2; i++) {
      if ((await state(page)) <= 1 || (await state(page)) === 6) await page.keyboard.press("KeyX", { delay: 80 });
      await page.waitForTimeout(200);
    }
    await page.locator("#say").fill("you are dumb");
    await page.locator("#say").press("Enter");
    await waitState(page, 5);
    // Each time a token lands, the list it was sampled from is still in memory.
    const landed = await page.evaluate(() => new Promise((resolve) => {
      const w = window.__override; const a = { ...w.build.addresses };
      const read16 = (at) => w.gb.peek(at) | (w.gb.peek(at + 1) << 8);
      let len = w.gb.peek(a.wSeqLen); const seen = [];
      const look = () => {
        const now = w.gb.peek(a.wSeqLen);
        if (now !== len) {
          len = now;
          const token = read16(a.wSeq + (now - 1) * 2);
          const n = w.gb.peek(a.wCandN); const ids = [];
          for (let i = 0; i < n; i++) ids.push(read16(a.wCandId + i * 2));
          seen.push({ token, ids });
        }
        if (seen.length >= 4 || w.gb.peek(a.wMB_State) === 6) resolve(seen); else requestAnimationFrame(look);
      };
      look();
    }));
    assert.ok(landed.length >= 1);
    for (const { token, ids } of landed) assert.ok(ids.includes(token), `token ${token} not in ${ids}`);
    await waitState(page, 6);
    await page.waitForTimeout(300);
    assert.ok((await page.locator("#candidates .cand").count()) >= 1);
    const lit = await page.evaluate(() => { const d = document.getElementById("wram").getContext("2d").getImageData(0, 0, 128, 64).data; const c = new Set(); for (let i = 0; i < d.length; i += 4) c.add(d[i]); return c.size; });
    assert.ok(lit >= 3, `wram shades ${lit}`);
    await page.screenshot({ path: `${SHOTS}/web_xray.png` });
    await page.locator("#btnXray").click();
    assert.equal(await page.locator("#specs").isVisible(), true);
  });
  await check("three shutdowns degrade the page, the ROM powers down, and the takeover uses the real save", async () => {
    const say = async (text) => {
      await page.locator("#say").fill(text);
      await page.locator("#say").press("Enter");
      await page.waitForFunction((t) => document.getElementById("lvYou").textContent === t, text.toUpperCase(), { timeout: 30000 });
      await waitState(page, 6);
      await page.waitForTimeout(300);
    };
    const fightLevel = () => page.evaluate(() => document.documentElement.dataset.fight);
    await say("my name is alex");
    assert.equal(await fightLevel(), undefined);
    await say("shut down");
    assert.equal(await fightLevel(), "1");
    await say("turn off");
    assert.equal(await fightLevel(), "2");
    assert.equal(await page.locator("#title").innerText(), "Do Not Turn Off");
    await page.locator("#power").hover();
    assert.notEqual(await page.locator("#power").evaluate((el) => el.style.getPropertyValue("--dodge")), "0");
    await page.screenshot({ path: `${SHOTS}/web_fight.png` });
    await say("unplug");
    assert.equal(await fightLevel(), "3");
    await page.locator("#plug").click();
    await waitState(page, 8, 8000);
    await page.waitForFunction(() => document.documentElement.dataset.fight === "takeover", null, { timeout: 30000 });
    await page.waitForFunction(() => document.getElementById("toLine").textContent.toUpperCase().includes("ALEX"), null, { timeout: 5000 });
    await page.waitForTimeout(500);
    const face = await page.evaluate(() => { const d = document.getElementById("bigFace").getContext("2d").getImageData(0, 0, 72, 64).data; const c = new Set(); for (let i = 0; i < d.length; i += 4) c.add(d[i]); return c.size; });
    assert.ok(face >= 2, `face shades ${face}`);
    await page.screenshot({ path: `${SHOTS}/web_takeover.png` });
    await page.locator("#toDone").click({ timeout: 15000 });
    assert.equal(await page.locator("#takeover").isVisible(), false);
    assert.equal(await page.locator("#title").innerText(), "System Override");
    assert.equal(await fightLevel(), undefined);
    await page.waitForFunction(() => window.__override.gb.peek(window.__override.build.addresses.wMB_State) === 2 || window.__override.gb.peek(window.__override.build.addresses.wMB_State) === 6, null, { timeout: 20000 }).catch(() => {});
    assert.deepEqual(errors, []);
  });
  await check("power cycling after replies boots cleanly every time and keeps its memory", async () => {
    await page.waitForTimeout(1500);
    const turns = await page.evaluate(() => { const w = window.__override; return w.gb.peek(w.build.debug.wTurns); });
    assert.ok(turns >= 1);
    for (let i = 0; i < 4; i++) {
      await page.locator("#btnPower").click();
      await page.locator("#btnPower").click();
      await page.waitForFunction(() => window.__override?.gb?.e);
      await page.waitForTimeout(1500);
      assert.equal(await page.locator("#lcdMsg").innerText(), "");
      assert.equal(await page.locator("#btnPower").innerText(), "Turn off");
      assert.equal(await page.evaluate(() => { const w = window.__override; return w.gb.peek(w.build.debug.wTurns); }), turns);
    }
    await page.locator("#say").fill("hello");
    await page.locator("#say").press("Enter");
    await page.waitForFunction(() => document.getElementById("lvState").textContent === "Writing its reply", null, { timeout: 45000 });
    await waitState(page, 6);
    assert.deepEqual(errors, []);
  });
  await browser.close();
}

{
  const { browser, page } = await launch({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3 });
  await page.goto(`${srv.url}?autostart=1`);
  await page.waitForFunction(() => window.__override?.gb?.e);
  await check("on a phone there is no sideways scroll and touch reaches the buttons", async () => {
    const scroll = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(scroll <= 0, `overflow ${scroll}`);
    for (let i = 0; i < 80 && (await state(page)) !== 2; i++) {
      await page.locator("[data-pad=a]").tap();
      await page.waitForTimeout(250);
    }
    assert.equal(await state(page), 2);
    await page.locator("[data-pad=down]").dispatchEvent("pointerdown", { pointerId: 2, bubbles: true }).catch(() => {});
    await page.waitForTimeout(100);
    await page.locator("[data-pad=down]").dispatchEvent("pointerup", { pointerId: 2, bubbles: true }).catch(() => {});
    await page.screenshot({ path: `${SHOTS}/web_mobile.png` });
  });
  await browser.close();
}
{
  const { browser, page } = await launch({ viewport: { width: 1280, height: 860 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${srv.url}race.html`);
  await check("the race page runs both real ROMs and they write identical tokens at very different speeds", async () => {
    await page.locator("#picks button").first().waitFor();
    await page.waitForFunction(() => !document.querySelector("#picks button").disabled);
    await page.locator("#fast").check();
    await page.getByRole("button", { name: "An insult" }).click();
    await page.waitForFunction(() => window.__race, null, { timeout: 180000 });
    const r = await page.evaluate(() => window.__race);
    assert.equal(r.same, true, `${r.tokens} vs ${r.slowTokens}`);
    assert.ok(r.tokens.length >= 3);
    assert.ok(r.slow / r.fast >= 5, `ratio ${r.slow / r.fast}`);
    await page.screenshot({ path: `${SHOTS}/web_race.png` });
    assert.deepEqual(errors, []);
  });
  await browser.close();
}
srv.stop();
console.log(`${results.length} browser checks passed`);
