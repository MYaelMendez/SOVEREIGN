"""kænbæn — shared system memory for the æ:// sovereign computing stack.

Every agent reads from these files before acting. The system remembers itself.
This module is the importable interface used by agents, cron jobs, and kænbæn surfaces.

Usage:
    from kænbæn import kænbæn

    # Read shared state
    smap = kænbæn.system_map()
    contracts = kænbæn.contracts()
    gates = kænbæn.gates()
    chain = kænbæn.genesis_chain()

    # Write receipts
    kænbæn.append_receipt(type='cron', sha256='...', detail='...')
    kænbæn.update_debt(name, status='resolved')
    kænbæn.register_agent(agent_id, capabilities=[...])
    kænbæn.update_surface(surface_id, key, value)
    kænbæn.sync_live()
"""
import json
import os
import time
import shutil
import hashlib
import threading
from pathlib import Path

try:
    K_BASE = Path(r"C:\æ\kænbæn")
except Exception:
    K_BASE = Path(__file__).parent

# Live deploy target (GitHub Pages /kaenbaen/)
K_LIVE = Path(r"C:\æ\github-pages\kaenbaen")

# Lock for concurrent access
_lock = threading.Lock()

# ── load + save helpers ────────────────────────────────────

def _load(name):
    p = K_BASE / f"{name}.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(name, data, indent=2, sync=True):
    p = K_BASE / f"{name}.json"
    text = json.dumps(data, indent=indent, ensure_ascii=False)
    p.write_text(text, encoding="utf-8")
    # Sync to live GitHub Pages directory
    if sync and K_LIVE.exists():
        live_p = K_LIVE / f"{name}.json"
        live_p.write_text(text, encoding="utf-8")
    return text

def _timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def _sha256(data):
    return hashlib.sha256(data.encode()).hexdigest()[:16]

# ── public interface ───────────────────────────────────────

class _KaenbaenFacade:
    """Facade over the 5 kænbæn JSON files."""

    def __init__(self):
        self._smap = None
        self._contracts = None
        self._gates = None
        self._chain = None

    def system_map(self):
        if self._smap is None:
            self._smap = _load("system-map")
        return self._smap

    def capability_contracts(self):
        if self._contracts is None:
            self._contracts = _load("capability-contracts")
        return self._contracts

    def gates(self):
        if self._gates is None:
            self._gates = _load("verification-gates")
        return self._gates

    def genesis_chain(self):
        if self._chain is None:
            self._chain = _load("genesis-chain")
        return self._chain

    def _invalidate(self):
        self._smap = None
        self._contracts = None
        self._gates = None
        self._chain = None


kænbæn = _KaenbaenFacade()

# ── write API ──────────────────────────────────────────────

def append_receipt(type="cron", sha256="", detail="", agent=""):
    """Append a receipt to the genesis chain."""
    with _lock:
        chain = kænbæn.genesis_chain()
        if not agent:
            agent = os.environ.get("AGENT_ID", "hermes")
        receipt = {
            "type": type,
            "sha256": sha256 or "pending",
            "detail": detail,
            "timestamp": _timestamp(),
            "agent": agent
        }
        chain.setdefault("receipts", []).append(receipt)
        _save("genesis-chain", chain)
        kænbæn._chain = None
        return receipt

def update_debt(name, status="resolved"):
    """Update a debt in the system map."""
    with _lock:
        smap = kænbæn.system_map()
        debts = smap.get("known_debts", [])
        for d in debts:
            if isinstance(d, str) and d == name:
                idx = debts.index(d)
                debts[idx] = {"name": name, "status": status, "updated": _timestamp()}
                break
            elif isinstance(d, dict) and d.get("name") == name:
                d["status"] = status
                d["updated"] = _timestamp()
                break
        else:
            debts.append({"name": name, "status": status, "updated": _timestamp()})
        smap["known_debts"] = debts
        _save("system-map", smap)
        kænbæn._smap = None

def register_agent(agent_id, capabilities=None, cannot=None):
    """Register an agent in capability contracts."""
    with _lock:
        contracts = kænbæn.capability_contracts()
        agents = contracts.setdefault("agents", {})
        agents[agent_id] = {
            "path": f"C:/æ/agents/{agent_id}.py",
            "capabilities": capabilities or [],
            "cannot": cannot or [],
            "registered_at": _timestamp(),
            "status": "active"
        }
        _save("capability-contracts", contracts)
        kænbæn._contracts = None

def update_surface(surface_id, key, value):
    """Update a surface property in system-map."""
    with _lock:
        smap = kænbæn.system_map()
        surfaces = smap.setdefault("surfaces", {})
        if surface_id not in surfaces:
            surfaces[surface_id] = {}
        surfaces[surface_id][key] = value
        _save("system-map", smap)
        kænbæn._smap = None

def update_gate(gate_id, key, value):
    """Update a verification gate property."""
    with _lock:
        gates = kænbæn.gates()
        g = gates.setdefault("gates", {})
        if gate_id not in g:
            g[gate_id] = {}
        g[gate_id][key] = value
        _save("verification-gates", gates)
        kænbæn._gates = None

def sync_live():
    """Force-sync all kænbæn files to live GitHub Pages /kaenbaen/."""
    results = {}
    for name in ["system-map", "capability-contracts", "verification-gates", "genesis-chain"]:
        try:
            data = _load(name)
            text = _save(name, data, sync=True)
            results[name] = f"synced ({len(text)} bytes)"
        except Exception as e:
            results[name] = f"error: {e}"
    return results

def append_chain_receipt(receipt_type, description, artifacts=None):
    """Append a structured receipt to the chain."""
    with _lock:
        chain = kænbæn.genesis_chain()
        entry = {
            "receipt": f"ae://receipt/{receipt_type}-{_sha256(description)}",
            "prev": chain.get("chain", [{}])[-1].get("receipt", "genesis") if chain.get("chain") else "genesis",
            "description": description,
            "timestamp": _timestamp(),
            "artifacts": artifacts or []
        }
        chain.setdefault("chain", []).append(entry)
        _save("genesis-chain", chain)
        kænbæn._chain = None
        return entry

# ── module interface ───────────────────────────────────────
kænbæn.append_receipt = append_receipt
kænbæn.update_debt = update_debt
kænbæn.register_agent = register_agent
kænbæn.update_surface = update_surface
kænbæn.update_gate = update_gate
kænbæn.sync_live = sync_live
kænbæn.append_chain_receipt = append_chain_receipt

# ── legacy compatibility ───────────────────────────────────
# Keep old function names working
def load_system_map():
    return kænbæn.system_map()

def load_capability_contracts():
    return kænbæn.capability_contracts()

def load_verification_gates():
    return kænbæn.gates()

def load_genesis_chain():
    return kænbæn.genesis_chain()

def verify_before_act(agent_name, action):
    try:
        load_system_map()
        load_capability_contracts()
        return True
    except FileNotFoundError:
        return False

if __name__ == "__main__":
    print("=== kænbæn — shared system memory ===")
    print(f"  base: {K_BASE}")
    print(f"  live: {K_LIVE}")
    smap = kænbæn.system_map()
    print(f"  surfaces: {list(smap.get('surfaces', {}).keys())}")
    print(f"  debts: {len(smap.get('known_debts', []))}")
    contracts = kænbæn.capability_contracts()
    print(f"  agents: {list(contracts.get('agents', {}).keys())}")
    gates = kænbæn.gates()
    print(f"  gates: {list(gates.get('gates', {}).keys())}")
    chain = kænbæn.genesis_chain()
    print(f"  receipts: {len(chain.get('receipts', []))}")
    print(f"  chain: {len(chain.get('chain', []))}")
    print("\n✅ kænbæn is active and maximized")
