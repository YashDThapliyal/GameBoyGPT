// Shared Playwright setup for the browser tests and the demo capture.
import { chromium } from "../../web/node_modules/playwright/index.mjs";
import { spawn } from "node:child_process";

export async function startServer(port = 8124) {
  const proc = spawn(".venv/bin/python", ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", "web"], { stdio: "ignore" });
  await new Promise((r) => setTimeout(r, 800));
  return { url: `http://127.0.0.1:${port}/`, stop: () => proc.kill() };
}

export async function launch(contextOptions = {}) {
  const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required", "--use-gl=swiftshader", "--mute-audio"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 }, ...contextOptions });
  const page = await context.newPage();
  return { browser, context, page };
}

export const readU8 = (page, name, off = 0) => page.evaluate(([n, o]) => { const w = window.__override; return w.gb.peek(w.build.addresses[n] + o); }, [name, off]);
