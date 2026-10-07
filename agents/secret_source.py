#!/usr/bin/env python3
"""secret_source.py — the GLOCAL secret-source contract (with væult tier).

Shared loader so every local agent consumes secrets identically. Resolution
order, highest first:

  1. explicit env var            (VPS_SIGN_KEY, BSKY_AGENT_*, ...)
  2. bridge export file          (secrets.json — the browser "Push to local")
  3. **væult**                   (C:\\æ\\secrets\\privateclient\\privateclient.væult)
  4. None                        (caller decides: refuse, or degrade)

The væult tier is the encrypted-at-rest store. It is OPTIONAL and unlocked
per-call: the passphrase comes from VAEULT_PASSPHRASE (scripted) or is skipped
entirely when absent, so an agent never blocks on a prompt and never sees a
secret it wasn't granted.

Stdlib only. Never prints raw values.

Why a tier and not a replacement: the bridge export is the human-facing
"Push to local" door and stays first-class; væult is the durable, encrypted
custody that survives a browser-cache wipe. Both feed the same callers.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Optional

# ── tier 2: bridge export ─────────────────────────────────────────────────────

DEFAULT_PATHS = [
    os.environ.get("HERMES_SECRETS"),
    str(pathlib.Path(os.environ.get("USERPROFILE", "C:/æ")) / "æ" / "secrets" / "secrets.json"),
    "C:/æ/secrets/secrets.json",
]

# ── tier 3: væult ─────────────────────────────────────────────────────────────

VAEULT_PATH = pathlib.Path(os.environ.get(
    "VAEULT_PATH", r"C:\æ\secrets\privateclient\privateclient.væult"))
VAEULT_MODULE = pathlib.Path(os.environ.get("VAEULT_MODULE", r"C:\æ\væult\væult.py"))


def _load_export(path: Optional[str]) -> list[dict]:
    if not path:
        return []
    p = pathlib.Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get("secrets"), list):
        return data["secrets"]
    if isinstance(data, list):
        return data
    return []


def _vaeult_unlocked():
    """Return (module, key) if væult can be opened right now, else (None, None).

    Unlock is opt-in via VAEULT_PASSPHRASE — no passphrase means the tier is
    skipped, never prompted. A wrong passphrase is a silent skip (the caller
    may have other tiers); the vault itself refuses to decrypt.
    """
    passphrase = os.environ.get("VAEULT_PASSPHRASE")
    if not passphrase or not VAEULT_PATH.exists() or not VAEULT_MODULE.exists():
        return None, None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_vaeult_consumer", str(VAEULT_MODULE))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        doc = mod.load_raw(VAEULT_PATH)
        salt = mod._b64d(doc["salt"])
        key = mod.derive_key(passphrase, salt, doc.get("n", mod.KDF_N),
                             doc.get("r", mod.KDF_R), doc.get("p", mod.KDF_P))
        chk = doc.get("check")
        if chk:
            try:
                mod.open_entry(key, "__check__", chk)
            except Exception:
                return None, None          # wrong passphrase — skip the tier
        return mod, key
    except Exception:
        return None, None


def _vaeult_entries() -> dict[str, str]:
    """All entries as {name: value}, or {} when locked/unavailable."""
    mod, key = _vaeult_unlocked()
    if mod is None:
        return {}
    try:
        doc = mod.load_raw(VAEULT_PATH)
        out: dict[str, str] = {}
        for name, blob in doc.get("entries", {}).items():
            try:
                out[name] = mod.open_entry(key, name, blob)
            except Exception:
                continue
        return out
    except Exception:
        return {}


# ── public contract ───────────────────────────────────────────────────────────

def get_secret(key: str, export_path: Optional[str] = None) -> Optional[str]:
    """Exact key lookup: env → bridge export → væult."""
    env = os.environ.get(key)
    if env:
        return env
    for cand in (export_path, *DEFAULT_PATHS):
        for s in _load_export(cand):
            if str(s.get("key", "")).upper() == key.upper():
                return s.get("value")
    v = _vaeult_entries()
    for k, val in v.items():
        if k.upper() == key.upper():
            return val
    return None


def get_by_prefix(prefix: str, export_path: Optional[str] = None) -> dict[str, str]:
    """Return {key: value} for every secret whose key starts with prefix.
    env → bridge export → væult; earlier tiers win on collision."""
    out: dict[str, str] = {}
    for k, v in os.environ.items():
        if k.upper().startswith(prefix.upper()):
            out[k] = v
    for cand in (export_path, *DEFAULT_PATHS):
        for s in _load_export(cand):
            skey = str(s.get("key", ""))
            if skey.upper().startswith(prefix.upper()) and skey not in out:
                out[skey] = s.get("value")
    for k, val in _vaeult_entries().items():
        if k.upper().startswith(prefix.upper()) and k not in out:
            out[k] = val
    return out


def sources() -> dict:
    """Which tiers are live right now (never values). For diagnostics."""
    env_keys = [k for k in os.environ
                if any(k.upper().startswith(p) for p in ("VPS_", "BSKY_AGENT_", "NOUS_"))]
    bridge = []
    for cand in DEFAULT_PATHS:
        if cand and pathlib.Path(cand).exists():
            bridge = [s.get("key") for s in _load_export(cand)]
            break
    mod, key = _vaeult_unlocked()
    vault = sorted(mod.load_raw(VAEULT_PATH).get("entries", {})) if mod else []
    return {
        "env": sorted(env_keys),
        "bridge": sorted(k for k in bridge if k),
        "væult": {"path": str(VAEULT_PATH), "exists": VAEULT_PATH.exists(),
                  "unlocked": mod is not None, "entries": vault},
    }


if __name__ == "__main__":
    # diagnostic only — names and tiers, never values
    print(json.dumps(sources(), indent=2, ensure_ascii=False))
