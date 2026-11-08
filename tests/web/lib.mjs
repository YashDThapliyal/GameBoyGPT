// Shared Playwright setup for the browser tests and the demo capture.
import { chromium } from "../../web/node_modules/playwright/index.mjs";
import { spawn } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export function chromePath() {
  const base = join(homedir(), "Library/Caches/ms-playwright");
  if (!existsSync(base)) return undefined;
  const dir = readdirSync(base).filter((d) => d.startsWith("chromium-")).sort().pop();
  if (!dir) return undefined;
  for (const sub of ["chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing", "chrome-mac/Chromium.app/Contents/MacOS/Chromium", "chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"]) {
    const p = join(base, dir, sub);
    if (existsSync(p)) return p;
  }
  return undefined;
}

export async function startServer(port = 8124) {
  const proc = spawn(".venv/bin/python", ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", "web"], { stdio: "ignore" });
  await new Promise((r) => setTimeout(r, 800));
  return { url: `http://127.0.0.1:${port}/`, stop: () => proc.kill() };
}

export async function launch(contextOptions = {}) {
  const browser = await chromium.launch({ executablePath: chromePath(), args: ["--autoplay-policy=no-user-gesture-required", "--use-gl=swiftshader"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 }, ...contextOptions });
  const page = await context.newPage();
  return { browser, context, page };
}

export const readU8 = (page, name, off = 0) => page.evaluate(([n, o]) => { const w = window.__override; return w.gb.peek(w.build.addresses[n] + o); }, [name, off]);
