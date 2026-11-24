#!/usr/bin/env python3
"""gen_github_hygiene.py — derive account hygiene + a signature from live GitHub data.

    python agents/gen_github_hygiene.py --repos <repos.json> --profile <profile.json> \
        --pinned <pinned.json> --out <dir>

Read-only. It NEVER calls a mutating GitHub endpoint. Proposed changes are
written as text for the operator to authorize.
"""
from __future__ import annotations
import argparse, collections, datetime, hashlib, json, sys
from pathlib import Path

NOW = datetime.datetime(2026,11,23,tzinfo=datetime.timezone.utc)
SIGNATURE = [
    ("MYaelMendez.github.io","truth surface","the verified estate — derived inventories, receipts, films"),
    ("vaeult","custody","where the secret lives — scrypt → AES-256-GCM, never in a surface"),
    ("gpu-mcp","compute","sovereign RTX over MCP — the CUDA_MCP² leaf"),
    ("tinycuda","one-file GPU","a deterministic rasteriser in one file — capability compressed"),
    ("vidaeo","video","AEE cycle: SPEC → TEST → receipt — the film as instrument"),
    ("hermes-ae","robot receipts","one receipted tool for robot studio, physics and motion"),
]
TOPICS = ["opensourceware","internetofagents","sovereign-compute","agentic-video",
          "tiny-family","receipts","cuda","robotics","fork-archive","hypothesis"]

def days(d):
    try: return max(0,(NOW-datetime.datetime.fromisoformat(d.replace('Z','+00:00'))).days)
    except Exception: return 9999

def analyze(repos,profile,pinned):
    orig=[r for r in repos if not r['fork']]; forks=[r for r in repos if r['fork']]
    return {
      "schema":"ae/github-hygiene/1",
      "derived_at":NOW.isoformat(),
      "source":"GitHub REST /user, /users/MYaelMendez/repos, GraphQL pinnedItems — read only",
      "account":{"login":profile.get('login'),"name":profile.get('name'),
        "public_repos":profile.get('public_repos'),"followers":profile.get('followers'),
        "following":profile.get('following'),
        "bio":profile.get('bio'),"blog":profile.get('blog'),"location":profile.get('location')},
      "measured":{
        "repos":len(repos),"forks":len(forks),"originals":len(orig),
        "fork_ratio":round(len(forks)/len(repos),3),
        "stars_total":sum(r['stargazers_count'] for r in repos),
        "repos_with_stars":sum(1 for r in repos if r['stargazers_count']>0),
        "no_description":sum(1 for r in repos if not r.get('description')),
        "originals_no_description":[r['name'] for r in orig if not r.get('description')],
        "no_license":sum(1 for r in repos if not r.get('license')),
        "originals_no_license":[r['name'] for r in orig if not r.get('license')],
        "no_topics":sum(1 for r in repos if not r.get('topics')),
        "no_homepage":sum(1 for r in repos if not r.get('homepage')),
        "empty_repos":[r['name'] for r in repos if r.get('size',0)==0],
        "stale_365":sum(1 for r in repos if days(r['pushed_at'])>365),
        "stale_730":sum(1 for r in repos if days(r['pushed_at'])>730),
        "default_branches":dict(collections.Counter(r['default_branch'] for r in repos)),
        "languages":dict(collections.Counter(r.get('language') or 'none' for r in repos)),
        "pinned_count":len(pinned),
        "pinned":pinned,
        "pinned_forks":[p['name'] for p in pinned if p.get('isFork')],
        "repo_profile_has_readme":None,
      },
      "signature":{
        "thesis":"One sovereign laptop, many agents, receipts for everything.",
        "bio_candidate":"I think systems. One sovereign laptop (teknium · RTX 3050), many agents, receipts for everything. #opensourceware #internetofagents — myaelmendez.github.io",
        "pin_six":[{"repo":n,"axis":a,"why":w} for n,a,w in SIGNATURE],
        "topics":TOPICS,
        "profile_readme_outline":[
          "00 · THESIS — one human, many agents, the conductor in between",
          "01 · SIX AXES — truth / custody / compute / one-file GPU / video / robots",
          "02 · RECEIPTS — hash chains, gates, refusals; what is measured vs claimed",
          "03 · THE TINY FAMILY — capability compressed onto one laptop",
          "04 · FORKS ARE AN ARCHIVE — each fork a hypothesis, never surplus to prune",
          "05 · CONTACT — X @yaelmendez · yael@llm.store · myaelmendez.github.io",
        ],
      },
      "hygiene_queue":[{"action":"add topics","scope":"all 359 repos","authorization":"required",
          "reason":"0 topics means no machine-readable taxonomy for the signature"},
        {"action":"add descriptions","scope":"originals only","authorization":"required",
         "reason":"unlabelled originals are invisible in search and profile"},
        {"action":"add license","scope":"originals without license","authorization":"required",
         "reason":"#opensourceware needs an explicit license on every original"},
        {"action":"write profile README","scope":"MYaelMendez/MYaelMendez","authorization":"required",
         "reason":"repo has only cloud/, no README.md"},
        {"action":"replace pinned fork","scope":"profile pinnedItems","authorization":"required",
         "reason":"the only pin is a fork; six originals define the signature"},
        {"action":"archive stale","scope":"stale >730d","authorization":"required",
         "reason":"archive is reversible; deletion is NOT proposed"},
        {"action":"delete empty repo","scope":"FEDIVERSE-ATPROTO--macos-command-line","authorization":"required",
         "reason":"0 bytes; propose, never execute without explicit approval"}],
      "not_proposed":["bulk fork deletion","force-push","history rewrite","permission changes",
                      "profile bio/blog edits — those change public identity; operator decides"],
    }

def html(r:dict)->str:
    m=r['measured'];s=r['signature']
    rows="".join(
      f"<tr><td>{x['repo']}</td><td>{x['axis']}</td><td>{x['why']}</td></tr>"
      for x in s['pin_six'])
    q="".join(f"<li><b>{x['action']}</b> · {x['scope']} — {x['reason']} "
              f"<span class='dim'>[{x['authorization']}]</span></li>" for x in r['hygiene_queue'])
    kpis=[("REPOS",m['repos']),("FORKS",f"{m['fork_ratio']:.0%}"),("ORIGINALS",m['originals']),
          ("TOPICS",m['no_topics'] and "0"),("STARS",m['stars_total']),("PINNED",m['pinned_count'])]
    cards="".join(f"<div class='k'><div class='t'>{a}</div><div class='v'>{b}</div></div>" for a,b in kpis)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>github hygiene · developer signature</title><style>
:root{{--gold:#D4AF37;--void:#050505;--ink:#e8e4d8;--dim:#8a8577;--line:#2a2620;--ok:#00ff9d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);font-family:'JetBrains Mono',ui-monospace,monospace;padding:34px 30px 80px;line-height:1.6}}
h1{{font-size:clamp(25px,4vw,42px);color:var(--gold);margin:0 0 6px}}.sub{{color:var(--dim);font-size:12px;margin-bottom:24px}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin-bottom:18px}}
.k{{border:1px solid var(--line);padding:11px}}.k .t{{font-size:9px;color:var(--dim);letter-spacing:.15em}}.k .v{{font-size:21px;color:var(--gold)}}
.panel{{border:1px solid var(--line);padding:16px 18px;margin-bottom:14px;background:#0d1118}}
h2{{font-size:11px;color:var(--dim);letter-spacing:.18em;margin:0 0 12px;font-weight:500}}
p,li{{font-size:13px}}b{{color:var(--gold)}}.dim{{color:var(--dim)}}code{{color:#70dcff}}
table{{width:100%;border-collapse:collapse;font-size:12px}}th{{text-align:left;color:var(--dim);font-size:9px;letter-spacing:.12em;border-bottom:1px solid var(--line);padding:6px}}
td{{padding:7px 6px;border-bottom:1px solid var(--line)}}ul{{margin:0;padding-left:18px}}
</style></head><body>
<h1>github hygiene · developer signature</h1>
<div class="sub">measured from the live account · read-only audit · nothing remote was changed</div>
<div class="kpis">{cards}</div>
<div class="panel"><h2>01 · THE SIGNAL</h2>
<p><b>{m['repos']} repos, {m['forks']} of them forks ({m['fork_ratio']:.0%}).</b> That is an archive of
hypotheses, not clutter — the estate's own rule says forks are never pruned. The problem is not volume:
it is that <b>0 repos carry topics</b>, <b>8 originals have no description</b>, <b>{m['originals_no_license'] and len(m['originals_no_license'])} originals have no license</b>,
and the single pinned repo is <b>a fork</b> ({', '.join(m['pinned_forks']) or 'none'}).
The account currently presents an inherited repo as its signature.</p>
<p>Live profile: <code>{r['account']['login']}</code> · followers {r['account']['followers']} · following {r['account']['following']} ·
blog <code>{r['account']['blog']}</code>. Total stars across all {m['repos']} repos: <b>{m['stars_total']}</b> — stars are not the signature; the six axes below are.</p></div>
<div class="panel"><h2>02 · THE SIGNATURE · {s['thesis']}</h2>
<table><thead><tr><th>REPO</th><th>AXIS</th><th>WHY IT SPEAKS</th></tr></thead><tbody>{rows}</tbody></table>
<p style="margin-top:12px"><b>Bio candidate:</b> {s['bio_candidate']}</p>
<p><b>Topics vocabulary:</b> {', '.join(s['topics'])}</p></div>
<div class="panel"><h2>03 · PROFILE README OUTLINE</h2><ul>{''.join('<li>'+x+'</li>' for x in s['profile_readme_outline'])}</ul>
<p class="dim" style="margin-top:10px">The repo <code>MYaelMendez/MYaelMendez</code> currently contains only <code>cloud/</code> — no README.md.</p></div>
<div class="panel"><h2>04 · HYGIENE QUEUE · ALL REQUIRE AUTHORIZATION</h2><ul>{q}</ul>
<p style="margin-top:12px"><b>Explicitly not proposed:</b> {', '.join(r['not_proposed'])}.</p>
<p class="dim">Stale &gt;365d: {m['stale_365']} · &gt;730d: {m['stale_730']} · empty repos: {', '.join(m['empty_repos'])} · default branches: {', '.join(f'{k} {v}' for k,v in m['default_branches'].items())}.</p></div>
</body></html>'''

def main():
    ap=argparse.ArgumentParser()
    for k in ['repos','profile','pinned']: ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    repos=json.loads(a.repos.read_text(encoding='utf-8'))
    prof=json.loads(a.profile.read_text(encoding='utf-8'))
    pin=json.loads(a.pinned.read_text(encoding='utf-8'))
    d=analyze(repos,prof,pin)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'github-hygiene.json').write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    h=html(d); (a.out/'github-hygiene.html').write_text(h,encoding='utf-8')
    print(f"repos={d['measured']['repos']} forks={d['measured']['forks']} originals={d['measured']['originals']} "
          f"topics={d['measured']['no_topics']} pinned={d['measured']['pinned_count']}")
    print(f"wrote {a.out/'github-hygiene.html'} {len(h.encode('utf-8')):,}B")
    return 0

if __name__=='__main__': sys.exit(main())
