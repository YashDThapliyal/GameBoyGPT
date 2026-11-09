// The visit count in the header. Only the live site counts, and a tab session counts once however many pages it opens.
// The service receives a plain "plus one" and never anything a visitor types. If it's down, the count just stays hidden.
const LIVE_HOST = "gameboygpt.vercel.app";
const COUNTER = "https://abacus.jasoncameron.dev";
const KEY = "gameboygpt-yash-site/visits";
const SESSION_FLAG = "gameboygpt-visit-counted";
const TIMEOUT_MS = 4000;

function alreadyCounted() {
  try {
    if (sessionStorage.getItem(SESSION_FLAG)) return true;
    sessionStorage.setItem(SESSION_FLAG, "1");
  } catch { /* Without storage, each page counts. The site still works. */ }
  return false;
}

async function showVisits() {
  const el = document.getElementById("visits");
  if (!el || location.hostname !== LIVE_HOST) return;
  const action = alreadyCounted() ? "get" : "hit";
  const response = await fetch(`${COUNTER}/${action}/${KEY}`, { signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!response.ok) return;
  const { value } = await response.json();
  if (!Number.isFinite(value)) return;
  el.textContent = `${value.toLocaleString("en-US")} ${value === 1 ? "visit" : "visits"}`;
  el.hidden = false;
}

showVisits().catch(() => { /* A broken counter must never affect the page. */ });
