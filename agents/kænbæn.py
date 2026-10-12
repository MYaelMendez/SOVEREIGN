"""
æ:// kænbæn — Sovereign Computing Shared Memory

The canonical shared brain: every agent reads this before acting.
Thread-safe, self-syncing, read-write.

Usage:
    from kænbæn import kænbæn

    # read
    smap = kænbæn.system_map()
    contracts = kænbæn.capability_contracts()
    gates = kænbæn.gates()
    chain = kænbæn.genesis_chain()

    # write (thread-safe, live-sync to GitHub Pages)
    kænbæn.append_receipt('cron', sha256='...', detail='...')
    kænbæn.update_debt('stale-cache', 'resolved')
    kænbæn.register_agent('new-agent', capabilities=[...])
    kænbæn.sync_live()
"""
from __future__ import annotations

import json
import hashlib
import threading
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone


# ── paths ───────────────────────────────────────────────────
K_BASE = Path(r"C:\æ\kænbæn")
try:
    K_LIVE = Path(r"C:\æ\github-pages\kaenbaen")
except Exception:
    K_LIVE = None

# ── lock ────────────────────────────────────────────────────
_lock = threading.RLock()


# ── helpers ─────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _load(name: str) -> dict[str, Any]:
    p = K_BASE / f"{name}.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(name: str, data: dict[str, Any], sync: bool = True) -> str:
    p = K_BASE / f"{name}.json"
    text = json.dumps(data, indent=2, ensure_ascii=False)
    p.write_text(text, encoding="utf-8")
    if sync and K_LIVE:
        live_p = K_LIVE / f"{name}.json"
        live_p.write_text(text, encoding="utf-8")
    return text


def _receipt_id(desc: str, sha: str) -> str:
    """Generate a compact receipt ID."""
    raw = f"{desc}::{sha}::{int(time.time())}"
    return f"ae://receipt/{_sha256(raw)}"


# ── kænbæn: read methods ──────────────────────────────────────
_cache: dict[str, dict[str, Any]] = {}


def system_map() -> dict[str, Any]:
    if "system_map" not in _cache:
        with _lock:
            if "system_map" not in _cache:
                _cache["system_map"] = _load("system-map")
    return _cache["system_map"].copy()


def capability_contracts() -> dict[str, Any]:
    if "contracts" not in _cache:
        with _lock:
            if "contracts" not in _cache:
                _cache["contracts"] = _load("capability-contracts")
    return _cache["contracts"].copy()


def gates() -> dict[str, Any]:
    if "gates" not in _cache:
        with _lock:
            if "gates" not in _cache:
                _cache["gates"] = _load("verification-gates")
    return _cache["gates"].copy()


def genesis_chain() -> dict[str, Any]:
    if "chain" not in _cache:
        with _lock:
            if "chain" not in _cache:
                _cache["chain"] = _load("genesis-chain")
    return _cache["chain"].copy()


# ── write methods ────────────────────────────────────────────
def append_receipt(
    receipt_type: str,
    sha256: str,
    detail: str,
    agent: str = "fleet",
) -> str:
    """Append a receipt to the genesis chain."""
    with _lock:
        chain = _load("genesis-chain")
        rid = _receipt_id(detail, sha256)

        # determine prev
        prev = "genesis"
        if chain.get("chain") and len(chain["chain"]) > 0:
            prev = chain["chain"][-1].get("receipt", "genesis")
        elif chain.get("receipts") and len(chain.get("receipts", [])) > 0:
            prev = chain["receipts"][-1].get("receipt", "genesis")

        receipt = {
            "receipt": rid,
            "type": receipt_type,
            "sha256": sha256,
            "detail": detail,
            "agent": agent,
            "timestamp": _now(),
            "prev": prev,
        }

        receipts = chain.get("receipts") or []
        receipts.append(receipt)
        chain["receipts"] = receipts

        _save("genesis-chain", chain)
        _cache.pop("chain", None)
        return rid


def append_chain(chain_entry: dict[str, Any]) -> str:
    """Append a chain entry (receipt + prev hash)."""
    with _lock:
        chain = _load("genesis-chain")
        chain_entries = chain.get("chain") or []

        prev = "genesis"
        if chain_entries:
            prev = chain_entries[-1].get("receipt", "genesis")

        entry = {
            "receipt": chain_entry.get("receipt", _receipt_id(
                chain_entry.get("description", ""),
                chain_entry.get("sha256", "")
            )),
            "prev": prev,
            "description": chain_entry.get("description", ""),
            "artifacts": chain_entry.get("artifacts", []),
            "timestamp": _now(),
        }
        chain_entries.append(entry)
        chain["chain"] = chain_entries

        _save("genesis-chain", chain)
        _cache.pop("chain", None)
        return entry["receipt"]


def update_debt(name: str, status: str) -> bool:
    """Update a known debt's status (e.g. 'resolved', 'in-progress')."""
    with _lock:
        debts = list(_load("system-map").get("known_debts", []))

        updated = False
        for debt in debts:
            if isinstance(debt, dict) and debt.get("name") == name:
                debt["status"] = status
                debt["updated"] = _now()
                updated = True
            elif isinstance(debt, str) and debt == name:
                debts.remove(debt)
                debts.append({
                    "name": name, "status": status, "updated": _now()
                })
                updated = True

        if updated:
            smap = _load("system-map")
            smap["known_debts"] = debts
            _save("system-map", smap)
            _cache.pop("system_map", None)
        return updated


def resolve_debt(name: str) -> bool:
    """Mark a debt as resolved."""
    return update_debt(name, "resolved")


def register_agent(agent_id: str, capabilities: list[str]) -> str:
    """Register a new agent in capability-contracts.json."""
    with _lock:
        contracts = _load("capability-contracts")
        agents = contracts.get("agents", {})
        agents[agent_id] = {
            "path": f"C:/æ/agents/{agent_id}.py",
            "can": capabilities,
            "cannot": [],
            "registered_at": _now(),
            "status": "active",
        }
        contracts["agents"] = agents
        _save("capability-contracts", contracts)
        _cache.pop("contracts", None)
        return agent_id


def update_surface(surface_id: str, key: str, value: Any) -> bool:
    """Update a field on a surface in system-map.json."""
    with _lock:
        smap = _load("system-map")
        surfaces = smap.get("surfaces", {})
        if surface_id not in surfaces:
            return False
        surfaces[surface_id][key] = value
        smap["surfaces"] = surfaces
        _save("system-map", smap)
        _cache.pop("system_map", None)
        return True


def update_gate(gate_id: str, key: str, value: Any) -> bool:
    """Update a field on a verification gate."""
    with _lock:
        gates_data = _load("verification-gates")
        gates_dict = gates_data.get("gates", {})
        if gate_id not in gates_dict:
            return False
        gates_dict[gate_id][key] = value
        gates_data["gates"] = gates_dict
        _save("verification-gates", gates_data)
        _cache.pop("gates", None)
        return True


def sync_live() -> bool:
    """Force sync all kænbæn files to GitHub Pages /kaenbaen/."""
    if not K_LIVE:
        return False
    with _lock:
        for name in ["system-map", "capability-contracts", "verification-gates", "genesis-chain"]:
            text = json.dumps(_load(name), indent=2, ensure_ascii=False)
            (K_LIVE / f"{name}.json").write_text(text, encoding="utf-8")
    return True


# ── verify before act ────────────────────────────────────────
def verify_before_act(agent_name: str, action: str) -> bool:
    """Verify kænbæn state is accessible before dispatching an agent action."""
    try:
        smap = system_map()
        contracts = capability_contracts()
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        return False


# ── legacy compatibility ─────────────────────────────────────
def load_system_map() -> dict[str, Any]:
    return system_map()


def load_capability_contracts() -> dict[str, Any]:
    return capability_contracts()


def load_verification_gates() -> dict[str, Any]:
    return gates()


def load_genesis_chain() -> dict[str, Any]:
    return genesis_chain()


# ── self-test ────────────────────────────────────────────────
def selftest() -> bool:
    """Run a quick self-test: read + write + verify."""
    try:
        # read
        smap = system_map()
        assert smap.get("system") == "æ://"
        contracts = capability_contracts()
        assert "agents" in contracts
        gates_data = gates()
        assert "gates" in gates_data
        chain = genesis_chain()
        assert "receipts" in chain or "chain" in chain
        print("  read: PASS")

        # write + verify
        rid = append_receipt(
            receipt_type="selftest",
            sha256="test",
            detail="kænbæn selftest",
            agent="kænbæn"
        )
        print(f"  write: PASS (receipt={rid})")

        chain2 = genesis_chain()
        assert any(r.get("receipt") == rid for r in chain2.get("receipts", []))
        print("  verify: PASS")

        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


if __name__ == "__main__":
    print("=== æ:// kænbæn — shared system memory ===")
    print(f"  base: {K_BASE}")
    print(f"  live: {K_LIVE or 'N/A'}")
    smap = system_map()
    print(f"  surfaces: {list(smap.get('surfaces', {}).keys())}")
    print(f"  debts: {len(smap.get('known_debts', []))}")
    contracts = capability_contracts()
    print(f"  agents: {list(contracts.get('agents', {}).keys())}")
    gates_d = gates()
    print(f"  gates: {list(gates_d.get('gates', {}).keys())}")
    chain = genesis_chain()
    print(f"  receipts: {len(chain.get('receipts', []))}")
    print(f"  chain: {len(chain.get('chain', []))}")
    print("\nRunning selftest...")
    if selftest():
        print("\n✅ kænbæn is active and maximized")
    else:
        print("\n❌ kænbæn selftest failed")
        exit(1)
