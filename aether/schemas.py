"""
æ:// schemas — standalone, language-agnostic data patterns for agent fleets.

Extracted from kænbæn (C:/æ/kænbæn/) — the shared memory of the æ://
sovereign computing stack. These schemas are the SPEC, not the implementation.
Any fleet can adopt these data shapes.

Usage:
    from aether.schemas import SystemMap, ReceiptChain, Surface

    smap = SystemMap(system="my-fleet")
    smap.add_surface(Surface(path="/api", status="active"))
    smap.resolve_debt("stale-cache")

    chain = ReceiptChain()
    chain.append_chain("build", artifacts=["build.py"])
    assert chain.verify_chain()
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BaseSchema:
    """Base class with serialization and validation."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseSchema":
        """Deserialize from dict."""
        raise NotImplementedError

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "BaseSchema":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))


class SystemMap(BaseSchema):
    """Fleet topology — what exists, where, how to verify.

    Maps every surface (endpoint) in the fleet, known debts, and
    the foundation layer (language → implementation → runtime).
    """

    def __init__(
        self,
        system: str = "æ://",
        version: str = "",
        description: str = "",
        surfaces: dict[str, Surface] | None = None,
        known_debts: list[Any] | None = None,
        foundation: dict[str, Any] | None = None,
    ):
        self.system = system
        self.version = version
        self.description = description
        self.surfaces: dict[str, Surface] = surfaces or {}
        self.known_debts: list[Any] = known_debts or []
        self.foundation: dict[str, Any] = foundation or {}

    def add_surface(self, surface: Surface) -> None:
        """Register a surface."""
        self.surfaces[surface.id] = surface

    def resolve_debt(self, name: str) -> bool:
        """Mark a debt as resolved. Returns True if found."""
        for d in self.known_debts:
            if isinstance(d, str) and d == name:
                idx = self.known_debts.index(d)
                self.known_debts[idx] = {
                    "name": name,
                    "status": "resolved",
                    "updated": _now(),
                }
                return True
            elif isinstance(d, dict) and d.get("name") == name:
                d["status"] = "resolved"
                d["updated"] = _now()
                return True
        return False

    def add_debt(self, name: str) -> None:
        """Add a new debt."""
        self.known_debts.append(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "version": self.version,
            "description": self.description,
            "surfaces": {k: v.to_dict() for k, v in self.surfaces.items()},
            "known_debts": self.known_debts,
            "foundation": self.foundation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemMap":
        surfaces = {
            k: Surface.from_dict(v) for k, v in data.get("surfaces", {}).items()
        }
        return cls(
            system=data.get("system", "æ://"),
            version=data.get("version", ""),
            description=data.get("description", ""),
            surfaces=surfaces,
            known_debts=data.get("known_debts", []),
            foundation=data.get("foundation", {}),
        )


class Surface(BaseSchema):
    """An addressable endpoint in the fleet.

    Every surface has a path, status, and optional metadata.
    Surfaces are the nodes in the constellation.
    """

    def __init__(
        self,
        id: str = "",
        path: str = "",
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ):
        self.id = id
        self.path = path
        self.status = status
        self.metadata: dict[str, Any] = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Surface":
        return cls(
            id=data.get("id", ""),
            path=data.get("path", ""),
            status=data.get("status", "active"),
            metadata=data.get("metadata", {}),
        )


class CapabilityContract(BaseSchema):
    """What each agent can and cannot do.

    Every agent declares its capabilities and constraints.
    This is the contract the agent agrees to.
    """

    def __init__(
        self,
        agent_id: str = "",
        path: str = "",
        capabilities: list[str] | None = None,
        cannot: list[str] | None = None,
        modes: dict[str, str] | None = None,
    ):
        self.agent_id = agent_id
        self.path = path
        self.capabilities: list[str] = capabilities or []
        self.cannot: list[str] = cannot or []
        self.modes: dict[str, str] = modes or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "path": self.path,
            "capabilities": self.capabilities,
            "cannot": self.cannot,
            "modes": self.modes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityContract":
        return cls(
            agent_id=data.get("agent_id", ""),
            path=data.get("path", ""),
            capabilities=data.get("capabilities", []),
            cannot=data.get("cannot", []),
            modes=data.get("modes", {}),
        )


class VerificationGate(BaseSchema):
    """What verifies an artifact before it can be published.

    Every gate has a command, a pass condition, and a fail condition.
    An artifact that has not been verified is not an artifact.
    """

    def __init__(
        self,
        gate_id: str = "",
        command: str = "",
        pass_condition: str = "",
        fail_condition: str = "",
        thresholds: dict[str, Any] | None = None,
    ):
        self.gate_id = gate_id
        self.command = command
        self.pass_condition = pass_condition
        self.fail_condition = fail_condition
        self.thresholds: dict[str, Any] = thresholds or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "command": self.command,
            "pass": self.pass_condition,
            "fail": self.fail_condition,
            "thresholds": self.thresholds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationGate":
        return cls(
            gate_id=data.get("gate_id", ""),
            command=data.get("command", ""),
            pass_condition=data.get("pass", ""),
            fail_condition=data.get("fail", ""),
            thresholds=data.get("thresholds", {}),
        )


class Receipt(BaseSchema):
    """An execution receipt — proof of work.

    Every action produces a receipt. The receipt carries the
    action's type, its SHA-256 hash, and a timestamp.
    """

    def __init__(
        self,
        receipt_type: str = "unknown",
        sha256: str = "",
        detail: str = "",
        timestamp: str = "",
        agent: str = "",
    ):
        self.type = receipt_type
        self.sha256 = sha256
        self.detail = detail
        self.timestamp = timestamp or _now()
        self.agent = agent

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "sha256": self.sha256,
            "detail": self.detail,
            "timestamp": self.timestamp,
            "agent": self.agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Receipt":
        return cls(
            receipt_type=data.get("type", "unknown"),
            sha256=data.get("sha256", ""),
            detail=data.get("detail", ""),
            timestamp=data.get("timestamp", ""),
            agent=data.get("agent", ""),
        )


class ChainEntry(BaseSchema):
    """A single entry in the receipt chain.

    Each entry chains to the previous entry's receipt ID.
    The chain is the memory.
    """

    def __init__(
        self,
        receipt_id: str = "",
        prev: str = "genesis",
        description: str = "",
        timestamp: str = "",
        artifacts: list[str] | None = None,
    ):
        self.receipt_id = receipt_id
        self.prev = prev
        self.description = description
        self.timestamp = timestamp or _now()
        self.artifacts: list[str] = artifacts or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt": self.receipt_id,
            "prev": self.prev,
            "description": self.description,
            "timestamp": self.timestamp,
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChainEntry":
        return cls(
            receipt_id=data.get("receipt", ""),
            prev=data.get("prev", "genesis"),
            description=data.get("description", ""),
            timestamp=data.get("timestamp", ""),
            artifacts=data.get("artifacts", []),
        )


class ReceiptChain(BaseSchema):
    """Immutable receipt chain — the system's memory.

    Each entry chains to the previous. The chain is verifiable:
    every entry's receipt_id must hash to the prev field of the next.
    """

    def __init__(
        self,
        genesis: dict[str, Any] | None = None,
        chain: list[ChainEntry] | None = None,
        receipts: list[Receipt] | None = None,
    ):
        self.genesis = genesis or {}
        self.chain: list[ChainEntry] = chain or []
        self.receipts: list[Receipt] = receipts or []

    def append_receipt(self, receipt: Receipt) -> Receipt:
        """Append a standalone receipt (not chained)."""
        self.receipts.append(receipt)
        return receipt

    def append_chain(
        self,
        description: str,
        artifacts: list[str] | None = None,
    ) -> ChainEntry:
        """Append a chained entry. Returns the new entry."""
        prev = self.chain[-1].receipt_id if self.chain else "genesis"
        receipt_id = _hash_entry(prev, description, artifacts or [])
        entry = ChainEntry(
            receipt_id=receipt_id,
            prev=prev,
            description=description,
            artifacts=artifacts or [],
        )
        self.chain.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """Verify the chain integrity.

        Every entry's receipt_id must match the hash of
        (prev + description + artifacts).
        """
        for i, entry in enumerate(self.chain):
            expected = _hash_entry(entry.prev, entry.description, entry.artifacts)
            if entry.receipt_id != expected:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "genesis": self.genesis,
            "chain": [e.to_dict() for e in self.chain],
            "receipts": [r.to_dict() for r in self.receipts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReceiptChain":
        chain = [ChainEntry.from_dict(e) for e in data.get("chain", [])]
        receipts = [Receipt.from_dict(r) for r in data.get("receipts", [])]
        return cls(
            genesis=data.get("genesis", {}),
            chain=chain,
            receipts=receipts,
        )


# ── Validators ──────────────────────────────────────────────


def validate_system_map(data: dict[str, Any]) -> list[str]:
    """Validate a system-map dict. Returns list of errors."""
    errors = []
    if not data.get("system"):
        errors.append("system is required")
    if not isinstance(data.get("surfaces", {}), dict):
        errors.append("surfaces must be a dict")
    if not isinstance(data.get("known_debts", []), list):
        errors.append("known_debts must be a list")
    return errors


def validate_chain(data: dict[str, Any]) -> list[str]:
    """Validate a receipt-chain dict. Returns list of errors."""
    errors = []
    chain = data.get("chain", [])
    if not isinstance(chain, list):
        errors.append("chain must be a list")
        return errors

    for i, entry in enumerate(chain):
        if "receipt" not in entry:
            errors.append(f"chain[{i}] missing receipt")
        if "prev" not in entry:
            errors.append(f"chain[{i}] missing prev")

    return errors


# ── Helpers ─────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _hash_entry(prev: str, description: str, artifacts: list[str]) -> str:
    text = f"{prev}::{description}::{','.join(artifacts)}"
    return f"ae://receipt/{hashlib.sha256(text.encode()).hexdigest()[:16]}"
