"""Render the film corpus index as a reachable HTML page.

152 films, 115 already live at their own URLs. They were never unreachable —
they were unindexed. This page is the front door: every film with its measured
duration, its voice status, its defect state and its SHA-256 citation.

Gold on void. No CDN. The data is fetched from film-corpus.json beside it.
"""
import json
import os
import pathlib

GP = pathlib.Path(r'C:\æ\github-pages')
data = json.loads((GP / 'film-corpus.json').read_text(encoding='utf-8'))
s = data['summary']

HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>THE CORPUS — æ://film</title>
<meta name="description" content="__FILMS__ receipted robotics films. Every claim carries a hash.">
<style>
:root{--gold:#D4AF37;--void:#050505;--ink:#e8e6df;--dim:#8a7a3f;--teal:#2dd4bf;--mag:#ff40dc}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--void);color:var(--ink);font:14px/1.6 "JetBrains Mono",ui-monospace,Consolas,monospace;
background-image:linear-gradient(rgba(212,175,55,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(212,175,55,.03) 1px,transparent 1px);
background-size:32px 32px}
header{background:var(--gold);color:#050505;padding:22px 20px}
header h1{font-size:26px;letter-spacing:.14em;font-weight:700}
header p{font-size:12px;color:#3a3010;margin-top:6px;letter-spacing:.06em}
.wrap{max-width:1100px;margin:0 auto;padding:20px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:18px 0}
.stat{border:1px solid #2a2415;padding:12px}
.stat b{display:block;color:var(--gold);font-size:24px}
.stat span{font-size:11px;color:var(--dim);letter-spacing:.08em}
.finding{border-left:3px solid var(--teal);padding:12px 14px;margin:18px 0;background:#0a0d0f;font-size:13px}
.finding b{color:var(--teal)}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
button{background:#0d0e12;color:var(--dim);border:1px solid #2a2415;padding:7px 12px;
font:inherit;font-size:12px;cursor:pointer;letter-spacing:.06em}
button.on{background:var(--gold);color:#050505;border-color:var(--gold)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--dim);border-bottom:1px solid #2a2415;padding:8px 6px;
font-weight:400;letter-spacing:.08em;font-size:11px;position:sticky;top:0;background:var(--void)}
td{padding:7px 6px;border-bottom:1px solid #14151a;vertical-align:top}
tr:hover td{background:#0b0c10}
a{color:var(--gold);text-decoration:none}
a:hover{text-decoration:underline}
.bad{color:var(--mag)}
.good{color:var(--teal)}
.dim{color:var(--dim)}
.hash{font-size:10px;color:#5a5230}
.pill{font-size:10px;border:1px solid #2a2415;padding:1px 5px;color:var(--dim)}
.pill.v{border-color:var(--teal);color:var(--teal)}
footer{border-top:1px solid #2a2415;margin-top:26px;padding:18px 0;font-size:11px;color:var(--dim)}
.none{color:var(--dim);font-style:italic}
</style></head><body>
<header><h1>THE CORPUS</h1>
<p>&gt;_æ://film &nbsp;·&nbsp; __FILMS__ FILMS &nbsp;·&nbsp; __MINUTES__ MINUTES &nbsp;·&nbsp; EVERY CLAIM CARRIES A HASH</p></header>
<div class="wrap">
<div class="stats">
<div class="stat"><b>__FILMS__</b><span>FILMS</span></div>
<div class="stat"><b>__LIVE__</b><span>LIVE NOW</span></div>
<div class="stat"><b>__UNPUB__</b><span>UNPUBLISHED</span></div>
<div class="stat"><b>__MINUTES__</b><span>MINUTES</span></div>
<div class="stat"><b>__VOICE__</b><span>WITH VOICE</span></div>
<div class="stat"><b>__VERT__</b><span>9:16 VERTICAL</span></div>
<div class="stat"><b class="bad">__DEF__</b><span>DEFECTIVE</span></div>
<div class="stat"><b class="bad">__DEFLIVE__</b><span>DEFECTIVE &amp; LIVE</span></div>
</div>
<div class="finding">
<b>WHAT THE CORPUS MEASURED.</b> Defect rate with voice: <b>__RATEV__%</b>.
Without voice: <b>__RATES__%</b>. Every failure in the corpus is co-extensive with
having audio — __FROZEN__ seconds of frozen picture, all of it at the seam between
picture and voice. The rendering never failed. The physics never failed. The GPU
never failed. <b>Defects live at interfaces, not in components</b>, and every gate
we had was a component gate. <code>tinyCUDAVIDEO</code> now checks the seam.
</div>
<div class="controls">
<button data-f="all" class="on">ALL</button>
<button data-f="live">LIVE</button>
<button data-f="voice">WITH VOICE</button>
<button data-f="vertical">9:16</button>
<button data-f="defective">DEFECTIVE</button>
<button data-f="unpublished">UNPUBLISHED</button>
</div>
<table><thead><tr>
<th>FILM</th><th>LENGTH</th><th>VOICE</th><th>STATE</th><th>DATE</th><th>CITATION</th>
</tr></thead><tbody id="rows"></tbody></table>
<footer>
Generated from measurement, not recollection: durations and frozen tails from
ffprobe, hashes from the delivered bytes, live status from HTTP HEAD.<br>
Data: <a href="film-corpus.json">film-corpus.json</a> &nbsp;·&nbsp;
<a href="index.html">&gt;_æ:// home</a> &nbsp;·&nbsp;
<a href="https://github.com/MYaelMendez">github.com/MYaelMendez</a><br>
<span class="dim">Not verified: no second-machine reproduction. Every number here is from one laptop.</span>
</footer>
</div>
<script>
const DATA = __DATA__;
const rows = document.getElementById('rows');
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function render(f){
  const list = DATA.filter(e =>
    f==='all' ? true :
    f==='live' ? e.live :
    f==='voice' ? e.has_voice :
    f==='vertical' ? e.vertical :
    f==='defective' ? e.defective :
    !e.live);
  rows.innerHTML = list.map(e => {
    const name = e.live
      ? `<a href="${esc(e.url)}">${esc(e.film)}</a>`
      : `<span class="dim">${esc(e.film)}</span>`;
    const voice = e.has_voice ? '<span class="pill v">VOICE</span>' : '<span class="pill">silent</span>';
    let state;
    if (e.defective) state = `<span class="bad">FROZEN ${e.frozen_tail_s}s</span>` +
      (e.repair_available ? ' <span class="pill v">repair ready</span>' : '');
    else if (e.live) state = '<span class="good">LIVE</span>';
    else state = '<span class="dim">local</span>';
    const vert = e.vertical ? ' <span class="pill">9:16</span>' : '';
    return `<tr><td>${name}${vert}</td><td>${e.seconds.toFixed(2)}s</td><td>${voice}</td>`+
           `<td>${state}</td><td class="dim">${esc(e.mtime)}</td>`+
           `<td class="hash">${esc(e.citation)}<br>${e.sha256.slice(0,16)}</td></tr>`;
  }).join('') || '<tr><td colspan="6" class="none">nothing matches</td></tr>';
}
document.querySelectorAll('button[data-f]').forEach(b => b.onclick = () => {
  document.querySelectorAll('button[data-f]').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); render(b.dataset.f);
});
render('all');
</script>
</body></html>
"""

repl = {
    '__FILMS__': str(s['films']), '__LIVE__': str(s['live']),
    '__UNPUB__': str(s['unpublished']), '__MINUTES__': str(s['total_minutes']),
    '__VOICE__': str(s['with_voice']), '__VERT__': str(s['vertical']),
    '__DEF__': str(s['defective']), '__DEFLIVE__': str(s['defective_live']),
    '__RATEV__': str(s['defect_rate_with_voice_pct']),
    '__RATES__': str(s['defect_rate_silent_pct']),
    '__FROZEN__': str(s['frozen_seconds_total']),
    '__DATA__': json.dumps(data['films'], separators=(',', ':')),
}
for k, v in repl.items():
    HTML = HTML.replace(k, v)
(GP / 'corpus.html').write_text(HTML, encoding='utf-8')
print(f"  corpus.html · {len(HTML):,} bytes · {s['films']} films embedded")
for tag in ('<html', '</html>', '<table', '</table>', '<script', '</script>'):
    print(f"    {tag}: {HTML.count(tag)}")
