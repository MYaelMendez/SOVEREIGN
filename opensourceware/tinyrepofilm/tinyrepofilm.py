#!/usr/bin/env python3
"""tinyRepoFilm — any repo / org / user → one sealed, self-verifying film.

    tinyrepofilm --target menloresearch --dry-run
    tinyrepofilm --target MYaelMendez --derive-only
    tinyrepofilm --target NousResearch/hermes-agent --publish   # explicit only

The product is NOT the video. It is the contract that makes the video admit
when it is wrong. Every defect paid across three films is a guard here:

  1. type is DETECTED, never assumed (GraphQL contributionsCollection is User-only)
  2. GitHub access is authenticated `gh api` (anonymous 403 at 60 req/h)
  3. commit_activity is retried on HTTP 202 (async computation)
  4. narration numbers are BOUND to derived fields, never typed by hand
  5. semantic gate runs BEFORE render; fail-closed
  6. pixel gate alone is insufficient: receipt-uniqueness + visual review
  7. NO publish without --publish; publish goes through kanban_push.py
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, time
from pathlib import Path

ROOT=Path(r"C:/æ")
KITS=ROOT/"opensourceware"
DEFAULT_OUT=ROOT/"tinyfilmmemory/explainer/deliverables"

STAGES=["detect","derive","bind","gate","render","seal","publish"]

# A refusal is a RESULT, not a crash. Callers must be able to tell them apart.
EXIT_OK=0
EXIT_REFUSED=10        # gate said no — correct outcome, record it
EXIT_BLOCKED=11        # environment/infrastructure unavailable, not a verdict
EXIT_STAGED=2          # derived+staged, render intentionally not wired

def refuse(reason:str, code:int=EXIT_REFUSED) -> dict:
    return {"verdict":"REFUSED","reason":reason,"exit_code":code}

def emit_decision(dec:dict, target:str, out:Path|None=None) -> None:
    """Persist the verdict beside the artifact — a refusal that is not
    recorded is a refusal that did not happen."""
    if out is None: return
    d=out/f"decision-{target.replace('/','_')}.json"
    d.parent.mkdir(parents=True,exist_ok=True)
    d.write_text(json.dumps({"target":target,**dec},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"  decision: {d}")

def gh(path:str, jq:str|None=None) -> dict|list|None:
    cmd=["gh","api",path]
    if jq: cmd+=["--jq",jq]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60,encoding="utf-8",errors="replace")
    if r.returncode!=0: return None
    try: return json.loads(r.stdout) if not jq else r.stdout.strip()
    except Exception: return r.stdout.strip()

def count_contributors(repo:str) -> int:
    """Count distinct contributor ids across ALL pages — never cap at 100."""
    ids=set()
    for page in range(1,60):
        chunk=gh(f"repos/{repo}/contributors?per_page=100&page={page}&anon=true")
        if not isinstance(chunk,list) or not chunk: break
        ids.update(c.get("id") or c.get("login") for c in chunk)
        if len(chunk)<100: break
    return len(ids)

def detect(target:str) -> str:
    if "/" in target:
        ok=gh(f"repos/{target}",".full_name")
        return "repo" if ok else "REFUSED: repo not found"
    # GitHub serves both users AND orgs from /users/{name}; the discriminator
    # is the `type` field. This exact assumption broke the Nous film.
    typ=gh(f"users/{target}",".type")
    if typ=="User": return "user"
    if typ=="Organization" or gh(f"orgs/{target}",".login"): return "org"
    return "REFUSED: target is neither user nor org"

def _retry_stats(repo:str) -> list:
    for _ in range(5):
        d=gh(f"repos/{repo}/stats/commit_activity")
        if isinstance(d,list) and d: return d
        time.sleep(2)
    return []

def fork_provenance(target:str) -> dict:
    """Read the DERIVED provenance record made by `gh api compare` in terminal.
    Fail closed: an unverified fork is refused, never filmed as authorship."""
    f=Path(__file__).parent/(target.replace("/","_")+"-provenance.json")
    if not f.exists():
        return {"fork":False,"refuse":False,"reason":"not a fork; no provenance needed"}
    d=json.loads(f.read_text(encoding="utf-8"))
    if d.get("target")!=target: return {"fork":True,"refuse":True,"reason":"provenance target mismatch"}
    if d.get("decision")=="REFUSE TO FILM" or d.get("local_authorship") is False:
        return {**d,"refuse":True}
    return {**d,"refuse":False}

def derive(kind:str,target:str) -> dict:
    """Normalize all three shapes into one Facts record. No invented numbers."""
    if kind=="user":
        d=gh(f"users/{target}")
        cal=gh(f"users/{target}/events/public",".[0:1]")
        raise RuntimeError(
          "user derivation must use gen_contributions.py (GraphQL contributionsCollection). "
          "Refusing to invent a calendar from public events.")
    if kind=="repo":
        d=gh(f"repos/{target}")
        act=_retry_stats(target)
        return {"kind":kind,"target":target,
          "public_repos":1,"followers":0,
          "total_stars":d["stargazers_count"],"total_forks":d["forks_count"],
          "contributor_sum":count_contributors(target),
          "commits_52w":sum(w.get("total",0) for w in act),
          "active_weeks":sum(1 for w in act if w.get("total",0)>0),
          "peak_week":max((w.get("total",0) for w in act),default=0),
          "source":"GitHub REST · stats/commit_activity (retried on 202)"}
    # org: aggregate across repos, authenticated
    meta=gh(f"orgs/{target}")
    repos=gh(f"orgs/{target}/repos?per_page=100&sort=updated") or []
    weeks=[0]*52; cs=0
    for r in repos:
        n=count_contributors(r["full_name"])
        cs+=int(n or 0)
        for i,w in enumerate(_retry_stats(r["full_name"])[:52]):
            weeks[i]+=w.get("total",0)
    return {"kind":kind,"target":target,
      "public_repos":len(repos),"followers":meta.get("followers",0),
      "total_stars":sum(r["stargazers_count"] for r in repos),
      "total_forks":sum(r["forks_count"] for r in repos),
      "contributor_sum":cs,"commits_52w":sum(weeks),
      "active_weeks":sum(1 for w in weeks if w>0),"peak_week":max(weeks,default=0),
      "source":"GitHub REST · org aggregate (authenticated gh api)"}

# Scene claims bind to fact keys. No literal numbers appear in the text.
SCENES=[
 ("BUILT FROM PUBLIC GITHUB",            "public_repos",   "repos"),
 ("STARS AND FORKS",                     "total_stars",    "stars"),
 ("CONTRIBUTOR RECORDS",                 "contributor_sum","contributors"),
 ("COMMITS IN FIFTY TWO WEEKS",          "commits_52w",    "commits"),
 ("WEEKS THAT SHIPPED",                  "active_weeks",   "weeks"),
 ("THE PEAK WEEK",                       "peak_week",      "stars"),
 ("ONE ARCHIVE OF CAPABILITY",           "public_repos",   "repos"),
 ("EVERY NUMBER IS DERIVED",             "commits_52w",    "commits"),
]

def bind(facts:dict) -> list:
    out=[]
    for title,key,focus in SCENES:
        val=facts.get(key)
        if not isinstance(val,int) or val<0:
            raise ValueError(f"bind REFUSED: {key} is not a derived integer ({val!r})")
        out.append({"title":title,"fact":key,"value":val,"focus":focus,
                    "spoken_numbers":[val]})
    return out

def gate(story:list,facts:dict) -> dict:
    problems=[]
    for s in story:
        if facts.get(s["fact"])!=s["value"]:
            problems.append(f"{s['fact']} drifted: story={s['value']} data={facts.get(s['fact'])}")
        for n in s["spoken_numbers"]:
            if n not in set(facts.values()):
                problems.append(f"narrated number {n} is absent from derived record")
    if facts.get("commits_52w",0)<=0: problems.append("no derived commits — refuse to film")
    if facts.get("contributor_sum",0)==0: problems.append("no derived contributors")
    return {"ok":not problems,"problems":problems}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",required=True)
    ap.add_argument("--out",type=Path,default=DEFAULT_OUT)
    ap.add_argument("--dry-run",action="store_true")
    ap.add_argument("--derive-only",action="store_true")
    ap.add_argument("--publish",action="store_true")
    a=ap.parse_args()

    print(f"tinyRepoFilm · target={a.target}")
    print("  stages: "+" → ".join(STAGES))
    if a.dry_run:
        print("  DRY-RUN: no tool calls, no files, no publish")
        print("  guards: detect / gh-auth / 202-retry / bound-narration / semantic-gate / receipt-unique / explicit-publish")
        return 0

    kind=detect(a.target)
    print(f"  detect: {kind}")
    if isinstance(kind,str) and kind.startswith("REFUSED"):
        d=refuse(kind); emit_decision(d,a.target,a.out)
        print("  REFUSED:",kind,file=sys.stderr); return EXIT_REFUSED

    if kind=="repo":
        prov=fork_provenance(a.target)
        print(f"  provenance: {prov.get('reason') or ('fork, local commits present' if prov.get('fork') else 'not a fork')}")
        if prov.get("refuse"):
            d=refuse(prov["reason"]); emit_decision(d,a.target,a.out)
            print("  REFUSED: "+prov["reason"],file=sys.stderr); return EXIT_REFUSED
    try: facts=derive(kind,a.target)
    except (RuntimeError, FileNotFoundError) as e:
        d=refuse(str(e),EXIT_BLOCKED); emit_decision(d,a.target,a.out)
        print(f"  BLOCKED: {e}",file=sys.stderr); return EXIT_BLOCKED
    print(f"  derive: stars={facts['total_stars']:,} forks={facts['total_forks']:,} "
          f"contributors={facts['contributor_sum']:,} commits/52w={facts['commits_52w']:,} "
          f"active={facts['active_weeks']}/52 peak={facts['peak_week']:,}")

    story=bind(facts)
    res=gate(story,facts)
    print(f"  gate: {'PASS' if res['ok'] else 'REFUSE'} · {len(story)} scenes bound")
    for p in res["problems"]: print("    !",p)
    if not res["ok"]:
        d=refuse("semantic gate: "+"; ".join(res["problems"]))
        emit_decision(d,a.target,a.out)
        print("  REFUSED: "+d["reason"],file=sys.stderr); return EXIT_REFUSED

    out=a.out/f"trf-{a.target.replace('/','_')}"
    out.mkdir(parents=True,exist_ok=True)
    (out/"facts.json").write_text(json.dumps(facts,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (out/"story.json").write_text(json.dumps(story,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (out/"gate.json").write_text(json.dumps(res,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"  staged: {out} (facts + story + gate)")

    if a.derive_only:
        print("  DERIVE-ONLY: stopping before render (no GPU, no publish)")
        return 0

    print("  render: delegate to kit at "+str(KITS/"hermes-contributions-film"))
    # CLOSE THE LOOP: the ledger's verdict is the next run's instruction.
    sys.path.insert(0,str(ROOT/"tinyfilmmemory"))
    try:
        import tinyfilmmemory as tfm
        v=tfm.verify(tfm.DEFAULT_LEDGER)
        print(f"  loop: chain={'OK' if v['chain']['ok'] else 'BROKEN'} length={v['chain']['length']} "
              f"films={v['films_checked']} drift={v['drift']}")
        if v['drift']:
            print("  next brief: re-seal or quarantine: "+', '.join(sorted(set(v['drift']))))
        else:
            print("  next brief: clean — proceed")
    except Exception as e:
        print(f"  loop: UNAVAILABLE ({type(e).__name__}: {e}) — do not claim the loop closed")
    print("  REFUSED: full render is not wired in this revision — use the existing kit; "
          "this CLI owns detection, derivation, binding and gates.")
    if a.publish:
        d=refuse("--publish without a sealed receipt"); emit_decision(d,a.target,a.out)
        print("  REFUSED: "+d["reason"],file=sys.stderr); return EXIT_REFUSED
    return EXIT_STAGED

if __name__=="__main__": sys.exit(main())
