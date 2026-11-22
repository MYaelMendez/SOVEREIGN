#!/usr/bin/env python3
"""secræt — sovereign secret CLI.  >_æ:secræt

Verbs:
  sources            which candidate paths exist (env -> HERMES_SECRETS -> secrets.json -> keys/)
  status             counts + fingerprints, never values
  list               key | kind | masked preview | sha256 fingerprint
  get <KEY>          masked + fingerprint, and the value written to a 0600 temp file
                     (stdout NEVER carries the value)
  seal <KEY>         read the value from stdin, write into the vault
  audit [N]          the last N audit lines

Rule: stdout is for humans and logs and stays clean. The value moves through a
file descriptor the caller already owns, never through argv, never through
stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys
import tempfile
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SECRETS_DIR = ROOT / "secrets"
STORE = SECRETS_DIR / "secrets.json"
KEYS = SECRETS_DIR / "keys"
AUDIT = SECRETS_DIR / "bridge.audit.log"


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fp(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


def mask(value: str, kind: str = "") -> str:
    if not value:
        return ""
    if kind in ("password", "bluesky"):
        return "•" * max(6, min(18, len(value)))
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * max(6, len(value) - 4)


def _load_store() -> dict:
    try:
        doc = json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        doc = {"schema": "secraet.v1", "exportedAt": "", "secrets": []}
    if not isinstance(doc.get("secrets"), list):
        doc["secrets"] = []
    return doc


def _save_store(doc: dict) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    doc["exportedAt"] = stamp()
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STORE)


def _audit(line: str) -> None:
    try:
        with AUDIT.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp()} {line}\n")
    except Exception:
        pass


def _key_file(key: str) -> pathlib.Path:
    safe = "".join(c if (c.isalnum() or c in "._-@") else "_" for c in key)[:80] or "key"
    return KEYS / f"{safe}.key"


def resolve(key: str) -> dict | None:
    """Resolution order: env -> HERMES_SECRETS -> secrets.json -> keys/<KEY>.key"""
    env = os.environ.get(key)
    if env:
        return {"key": key, "kind": "env", "value": env, "source": f"env:{key}"}
    hs = os.environ.get("HERMES_SECRETS")
    if hs and pathlib.Path(hs).is_file():
        try:
            doc = json.loads(pathlib.Path(hs).read_text(encoding="utf-8"))
            for s in doc.get("secrets", []):
                if s.get("key") == key and s.get("value"):
                    return {"key": key, "kind": s.get("kind", "generic"),
                            "value": s["value"], "source": hs}
        except Exception:
            pass
    for s in _load_store()["secrets"]:
        if s.get("key") == key and s.get("value"):
            return {"key": key, "kind": s.get("kind", "generic"),
                    "value": s["value"], "source": str(STORE)}
    kf = _key_file(key)
    if kf.is_file():
        return {"key": key, "kind": "file", "value": kf.read_text(encoding="utf-8"),
                "source": str(kf)}
    return None


def all_keys() -> list[dict]:
    out: dict[str, dict] = {}
    for s in _load_store()["secrets"]:
        if s.get("key"):
            out[s["key"]] = {"key": s["key"], "kind": s.get("kind", "generic"),
                             "value": s.get("value", ""), "source": str(STORE)}
    if KEYS.is_dir():
        for p in sorted(KEYS.glob("*.key")):
            k = p.stem
            if k not in out:
                out[k] = {"key": k, "kind": "file", "value": p.read_text(encoding="utf-8"),
                          "source": str(p)}
    return list(out.values())


def cmd_sources(_a) -> int:
    cands = {
        "env": sorted(k for k in os.environ if "KEY" in k.upper() or "TOKEN" in k.upper())[:10],
        "HERMES_SECRETS": os.environ.get("HERMES_SECRETS", ""),
        "secrets.json": str(STORE) if STORE.is_file() else "",
        "keys/": str(KEYS) + f" ({len(list(KEYS.glob('*.key')))} files)" if KEYS.is_dir() else "",
    }
    print(json.dumps({"schema": "secraet.sources.v1", **cands}, indent=1, ensure_ascii=False))
    return 0


def cmd_status(_a) -> int:
    ks = all_keys()
    print(json.dumps({
        "schema": "secraet.status.v1",
        "count": len(ks),
        "store": str(STORE),
        "store_present": STORE.is_file(),
        "keys_dir_present": KEYS.is_dir(),
        "keys_files": len(list(KEYS.glob("*.key"))) if KEYS.is_dir() else 0,
        "audit_present": AUDIT.is_file(),
        "fingerprints": {k["key"]: fp(k["value"]) for k in ks},
    }, indent=1, ensure_ascii=False))
    return 0


def cmd_list(_a) -> int:
    ks = all_keys()
    if not ks:
        print("no entries.")
        return 0
    print(f"{'KEY':28} {'KIND':10} {'PREVIEW':22} {'SHA256'}")
    for k in sorted(ks, key=lambda x: x["key"]):
        print(f"{k['key'][:27]:28} {k['kind'][:9]:10} {mask(k['value'], k['kind'])[:21]:22} {fp(k['value'])}")
    _audit(f"op=list n={len(ks)}")
    return 0


def cmd_get(a) -> int:
    r = resolve(a.key)
    if not r:
        print(f"unknown key: {a.key}", file=sys.stderr)
        return 2
    if a.json:
        # the value is carried in the result; stdout stays clean of it
        print(json.dumps({"key": r["key"], "kind": r["kind"], "source": r["source"],
                          "preview": mask(r["value"], r["kind"]), "sha256": fp(r["value"]),
                          "value": r["value"]}, ensure_ascii=False))
    else:
        fd, path = tempfile.mkstemp(prefix="secræt-", suffix=".key",
                                    dir=tempfile.gettempdir())
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(r["value"])
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        print(f"key      {r['key']}")
        print(f"kind     {r['kind']}")
        print(f"source   {r['source']}")
        print(f"preview  {mask(r['value'], r['kind'])}")
        print(f"sha256   {fp(r['value'])}")
        print(f"value    {path}  (0600 — read it, never paste it)")
    _audit(f"op=get key={a.key} fp={fp(r['value'])}")
    return 0


def cmd_seal(a) -> int:
    value = sys.stdin.read().strip()
    if not value:
        print("no value on stdin", file=sys.stderr)
        return 2
    doc = _load_store()
    for s in doc["secrets"]:
        if s.get("key") == a.key:
            s.update({"kind": a.kind, "value": value, "updated": stamp()})
            break
    else:
        doc["secrets"].append({"key": a.key, "kind": a.kind, "value": value,
                               "note": a.note or "", "updated": stamp()})
    _save_store(doc)
    kf = _key_file(a.key)
    KEYS.mkdir(parents=True, exist_ok=True)
    kf.write_text(value, encoding="utf-8")
    try:
        os.chmod(kf, stat.S_IREAD | stat.S_IWRITE)
    except Exception:
        pass
    _audit(f"op=seal key={a.key} fp={fp(value)}")
    print(f"sealed {a.key} ({a.kind}) sha256:{fp(value)} -> {STORE} + {kf}")
    return 0


def cmd_audit(a) -> int:
    if not AUDIT.is_file():
        print("no audit log.")
        return 0
    lines = AUDIT.read_text(encoding="utf-8").splitlines()
    for line in lines[-a.n:]:
        print(line)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="secræt", description="sovereign secret CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources").set_defaults(fn=cmd_sources)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    g = sub.add_parser("get")
    g.add_argument("key")
    g.add_argument("--json", action="store_true")
    g.set_defaults(fn=cmd_get)
    s = sub.add_parser("seal")
    s.add_argument("key")
    s.add_argument("--kind", default="api_key")
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_seal)
    au = sub.add_parser("audit")
    au.add_argument("n", nargs="?", type=int, default=10)
    au.set_defaults(fn=cmd_audit)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
