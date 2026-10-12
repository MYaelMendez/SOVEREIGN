"""PC://EVIDENCE — Evidence Bus compartido.

Envelope común para todas las fuentes de evidencia:
  vision://, benchmark://, test://, git://, runtime://, external://

Principio constitucional:
  Evidence puede informar una decisión.
  Evidence nunca se convierte por sí sola en autoridad.

  Evidence + Intent + Policy + Principal → Decision → Grant

PC://EVIDENCE_BUS_V1
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, TypeVar


# --- Constants ---
BUS_VERSION = "PC://EVIDENCE_BUS_V1"
GENESIS_HASH = hashlib.sha256(b"PC_EVIDENCE_GENESIS").hexdigest()


# --- Type Variable ---
T = TypeVar("T")


# --- Evidence Event Envelope ---
@dataclass
class EvidenceEvent(Generic[T]):
    """Envelope común de evidencia — desacoplado de la fuente.

    Cada evento es un eslabón en una hash chain verificable.
    El payload es tipado por la fuente (vision, benchmark, test, etc).
    """
    schema: str                    # "vision://detection", "benchmark://latency", etc.
    id: str                        # UUID único
    source: str                    # "pc-vision", "vscoder-benchmark", etc.
    subject: str                   # Sujeto de la evidencia (archivo, test, etc.)
    observed_at: str               # ISO 8601 timestamp
    payload: T                     # Datos específicos de la fuente
    payload_hash: str = ""         # SHA-256 del payload canónico
    producer_hash: str = ""        # SHA-256 del productor (código + config)
    previous_hash: str = ""        # Hash del evento anterior en la cadena
    event_hash: str = ""           # SHA-256 de este evento

    def compute_payload_hash(self) -> str:
        """Compute SHA-256 of the canonical payload."""
        if isinstance(self.payload, dict):
            canonical = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        else:
            canonical = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def compute_event_hash(self) -> str:
        """Compute this event's hash from its content + previous event hash."""
        canonical = {
            "schema": self.schema,
            "id": self.id,
            "source": self.source,
            "subject": self.subject,
            "observed_at": self.observed_at,
            "payload_hash": self.payload_hash,
            "producer_hash": self.producer_hash,
            "previous_hash": self.previous_hash,
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def finalize(self) -> EvidenceEvent[T]:
        """Compute and set payload_hash and event_hash."""
        self.payload_hash = self.compute_payload_hash()
        self.event_hash = self.compute_event_hash()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bus_version": BUS_VERSION,
            "schema": self.schema,
            "id": self.id,
            "source": self.source,
            "subject": self.subject,
            "observed_at": self.observed_at,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
            "producer_hash": self.producer_hash,
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> EvidenceEvent:
        return cls(
            schema=d["schema"],
            id=d["id"],
            source=d["source"],
            subject=d["subject"],
            observed_at=d["observed_at"],
            payload=d["payload"],
            payload_hash=d.get("payload_hash", ""),
            producer_hash=d.get("producer_hash", ""),
            previous_hash=d.get("previous_hash", ""),
            event_hash=d.get("event_hash", ""),
        )


# --- Evidence Bus ---
class EvidenceBus:
    """Bus de evidencia compartido — secuencia verificable de eventos.

    Todas las fuentes (vision, benchmark, test, git, runtime) publican aquí.
    POLICY, RECEIPTS y MOLT consumen de aquí.
    """

    def __init__(self):
        self.events: List[EvidenceEvent] = []
        self._genesis_hash = GENESIS_HASH

    def publish(self, event: EvidenceEvent) -> EvidenceEvent:
        """Publish an event to the bus, computing its hash."""
        if not self.events:
            event.previous_hash = self._genesis_hash
        else:
            event.previous_hash = self.events[-1].event_hash
        event.finalize()
        self.events.append(event)
        return event

    def verify(self) -> tuple[bool, List[str]]:
        """Verify the entire bus. Returns (is_valid, list_of_errors)."""
        errors = []
        prev_hash = self._genesis_hash

        for i, event in enumerate(self.events):
            # Check ordering
            if event.previous_hash != prev_hash:
                errors.append(f"Event {i}: previous_hash mismatch")

            # Recompute event hash
            recomputed = event.compute_event_hash()
            if recomputed != event.event_hash:
                errors.append(f"Event {i}: event_hash mismatch (tampered?)")

            # Recompute payload hash
            recomputed_payload = event.compute_payload_hash()
            if recomputed_payload != event.payload_hash:
                errors.append(f"Event {i}: payload_hash mismatch")

            prev_hash = event.event_hash

        return len(errors) == 0, errors

    def compute_bus_root(self) -> str:
        """Compute the Merkle-like root of the entire bus."""
        if not self.events:
            return hashlib.sha256(b"PC_EVIDENCE_EMPTY_BUS").hexdigest()

        hashes = [e.event_hash for e in self.events]
        while len(hashes) > 1:
            next_level = []
            for i in range(0, len(hashes), 2):
                left = hashes[i]
                right = hashes[i + 1] if i + 1 < len(hashes) else left
                combined = hashlib.sha256((left + right).encode()).hexdigest()
                next_level.append(combined)
            hashes = next_level

        root_payload = f"{BUS_VERSION}:{len(self.events)}:{hashes[0]}"
        return hashlib.sha256(root_payload.encode()).hexdigest()

    def query(self, schema_prefix: str) -> List[EvidenceEvent]:
        """Query events by schema prefix (e.g., 'vision://', 'benchmark://')."""
        return [e for e in self.events if e.schema.startswith(schema_prefix)]

    def to_jsonl(self, path: Path) -> None:
        """Write the bus to a JSONL file."""
        with open(path, "w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(event.to_dict(), separators=(",", ":")) + "\n")

    @classmethod
    def from_jsonl(cls, path: Path) -> EvidenceBus:
        """Load a bus from a JSONL file. Raises ValueError on malformed lines."""
        bus = cls()
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Line {line_num}: invalid JSON: {e}")
                try:
                    event = EvidenceEvent.from_dict(data)
                except (KeyError, TypeError) as e:
                    raise ValueError(f"Line {line_num}: missing or invalid field: {e}")
                bus.events.append(event)
        return bus


# --- Evidence Sources ---
class EvidenceSource:
    """Base class for evidence sources."""

    def __init__(self, source_name: str, producer_hash: str):
        self.source_name = source_name
        self.producer_hash = producer_hash

    def emit(self, schema: str, subject: str, payload: Any) -> EvidenceEvent:
        """Create an evidence event."""
        return EvidenceEvent(
            schema=schema,
            id=str(uuid.uuid4()),
            source=self.source_name,
            subject=subject,
            observed_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z",
            payload=payload,
            producer_hash=self.producer_hash,
        )


class VisionEvidenceSource(EvidenceSource):
    """PC://VISION → EvidenceEvent<PCVisionEvent>."""

    def __init__(self, producer_hash: str):
        super().__init__("pc-vision", producer_hash)

    def emit_detection(self, subject: str, detections: List[Dict], frame_index: int) -> EvidenceEvent:
        return self.emit(
            schema="vision://detection",
            subject=subject,
            payload={
                "frame_index": frame_index,
                "detections": detections,
            },
        )


class BenchmarkEvidenceSource(EvidenceSource):
    """benchmark.ts → EvidenceEvent<BenchmarkResult>."""

    def __init__(self, producer_hash: str):
        super().__init__("vscoder-benchmark", producer_hash)

    def emit_latency(self, subject: str, p50: float, p95: float, fps: float) -> EvidenceEvent:
        return self.emit(
            schema="benchmark://latency",
            subject=subject,
            payload={
                "p50_ms": p50,
                "p95_ms": p95,
                "fps": fps,
            },
        )


class TestEvidenceSource(EvidenceSource):
    """test runner → EvidenceEvent<TestResult>."""

    def __init__(self, producer_hash: str):
        super().__init__("vscoder-test", producer_hash)

    def emit_result(self, subject: str, passed: bool, total: int, failed: int) -> EvidenceEvent:
        return self.emit(
            schema="test://result",
            subject=subject,
            payload={
                "passed": passed,
                "total": total,
                "failed": failed,
            },
        )


class GitEvidenceSource(EvidenceSource):
    """git.ts → EvidenceEvent<GitEvent>."""

    def __init__(self, producer_hash: str):
        super().__init__("vscoder-git", producer_hash)

    def emit_change(self, subject: str, change_type: str, files: List[str]) -> EvidenceEvent:
        return self.emit(
            schema="git://change",
            subject=subject,
            payload={
                "change_type": change_type,
                "files": files,
            },
        )


# --- Decision Gate ---
@dataclass
class Decision:
    """Resultado del Decision Gate.

    Evidence + Intent + Policy + Principal → Decision → Grant
    """
    decision_id: str
    intent: str
    evidence_refs: List[str]  # IDs de EvidenceEvents
    policy_verdict: str       # "allow", "deny", "require_grant"
    principal: str            # "human://root", "agent://vscoder", etc.
    grant_id: Optional[str]   # None si no se concede grant
    reason: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "intent": self.intent,
            "evidence_refs": self.evidence_refs,
            "policy_verdict": self.policy_verdict,
            "principal": self.principal,
            "grant_id": self.grant_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class DecisionGate:
    """Decision Gate — Evidence + Intent + Policy + Principal → Decision.

    Principio constitucional:
      Evidence puede informar una decisión.
      Evidence nunca se convierte por sí sola en autoridad.
    """

    def __init__(self, bus: EvidenceBus):
        self.bus = bus
        self.decisions: List[Decision] = []

    def evaluate(
        self,
        intent: str,
        evidence_ids: List[str],
        policy_verdict: str,
        principal: str,
        reason: str,
    ) -> Decision:
        """Evaluate a decision based on evidence + policy + principal."""
        decision = Decision(
            decision_id=str(uuid.uuid4()),
            intent=intent,
            evidence_refs=evidence_ids,
            policy_verdict=policy_verdict,
            principal=principal,
            grant_id=str(uuid.uuid4()) if policy_verdict == "allow" else None,
            reason=reason,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        )
        self.decisions.append(decision)
        return decision

    def verify_evidence(self, evidence_ids: List[str]) -> bool:
        """Verify that all referenced evidence exists in the bus."""
        bus_ids = {e.id for e in self.bus.events}
        return all(eid in bus_ids for eid in evidence_ids)


# --- Validation ---
def validate_evidence_event(event: EvidenceEvent) -> List[str]:
    """Validate an evidence event against the schema. Returns list of errors."""
    errors = []

    if not event.schema:
        errors.append("schema is required")
    if not event.id:
        errors.append("id is required")
    if not event.source:
        errors.append("source is required")
    if not event.subject:
        errors.append("subject is required")
    if not event.observed_at:
        errors.append("observed_at is required")
    if not event.payload_hash:
        errors.append("payload_hash is required")
    if not event.producer_hash:
        errors.append("producer_hash is required")
    if not event.event_hash:
        errors.append("event_hash is required")

    return errors


def compute_producer_hash(code_version: str, config: Dict[str, Any]) -> str:
    """Compute producer hash from code version + config."""
    canonical = json.dumps({
        "code_version": code_version,
        "config": config,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
