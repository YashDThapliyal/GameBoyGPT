#!/usr/bin/env python3
"""Static dashboard: embeds the measured CSV. With no data it says so and never shows invented numbers."""
from __future__ import annotations
import csv, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = """<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>GameBoyGPT Benchmarks</title>
<style>:root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e6e5e0;--bar:#2a78d6}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#3a3a37;--bar:#3987e5}}
body{background:var(--bg);color:var(--ink);font:15px/1.45 ui-monospace,Menlo,monospace;margin:0;padding:16px;max-width:860px}
select{font:inherit;background:var(--bg);color:var(--ink);border:1px solid var(--line);padding:4px}
.row{display:grid;grid-template-columns:minmax(0,62px) 1fr 86px;gap:8px;align-items:center;margin:6px 0}
.bar{height:16px;background:var(--bar);border-radius:0 4px 4px 0}.track{background:var(--line);border-radius:0 4px 4px 0}
.note{color:var(--ink2)}table{border-collapse:collapse;width:100%;margin-top:16px}td,th{border-bottom:1px solid var(--line);padding:4px;text-align:right}td:first-child,th:first-child{text-align:left}</style>
<h1>GameBoyGPT benchmarks</h1><p class=note>Measured on an emulated DMG with PyBoy, greedy decoding, same model. Rows come from reports/benchmark.csv.</p>
<label>Workload <select id=w></select></label> <label>Metric <select id=m><option value=nominal_seconds_per_token>Seconds per token<option value=seconds_per_event>Seconds per event<option value=first_token_tcycles>First token T-cycles<option value=decode_tcycles_median>Median token T-cycles</select></label>
<div id=out></div><table id=t></table>
<script>const D=__DATA__;const out=document.getElementById('out'),w=document.getElementById('w'),m=document.getElementById('m');
if(!D.length){out.textContent='NO BENCHMARK DATA YET';w.disabled=m.disabled=true}else{
[...new Set(D.map(r=>r.workload))].forEach(x=>w.add(new Option(x,x)));
function draw(){const rows=D.filter(r=>r.workload==w.value&&r.round=='0');const max=Math.max(...rows.map(r=>+r[m.value]));
out.innerHTML=rows.map(r=>`<div class=row title="tokens match V0: ${r.token_match_baseline}"><span>${r.version}</span><div class=track><div class=bar style="width:${+r[m.value]/max*100}%"></div></div><span>${(+r[m.value]).toLocaleString()}</span></div>`).join('');
document.getElementById('t').innerHTML='<tr><th>Variant<th>Tokens<th>Same as V0<th>WRAM<th>ROM</tr>'+rows.map(r=>`<tr><td>${r.version}<td>${r.output_tokens}<td>${r.token_match_baseline}<td>${r.peak_wram_bytes}<td>${r.rom_bytes}</tr>`).join('')}
w.onchange=m.onchange=draw;draw()}</script></html>"""


def main():
    path = ROOT / "reports" / "benchmark.csv"
    rows = list(csv.DictReader(open(path))) if path.exists() else []
    (ROOT / "reports" / "dashboard.html").write_text(TEMPLATE.replace("__DATA__", json.dumps(rows)))
    print("wrote reports/dashboard.html with", len(rows), "rows")


if __name__ == "__main__":
    main()
