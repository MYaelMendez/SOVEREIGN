"""PC://ACTUATOR — Bounded action plane.

La otra mitad del loop cibernético:
  Sensorium: Reality → Evidence
  Actuator: Authority → Reality

Flujo:
  proposal → capability? → policy? → consequential? → 🧿 GRANT → ACT → WITNESS → 🧾

5 invariantes adicionales:
  Proposal ≠ Grant
  Grant ≠ Execution
  Execution ≠ Success
  Success ≠ Verified Consequence

PC://ACTUATOR_V1
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from evidence_bus import EvidenceBus, EvidenceEvent, EvidenceSource, compute_producer_hash


# --- Constants ---
ACTUATOR_VERSION = "PC://ACTUATOR_V1"


# --- 9 Invariantes (4 sensorium + 5 actuator) ---
class Invariantes:
    """Los 9 invariantes constitucionales de PC://."""

    # Sensorium (4)
    OBSERVATION_DECISION = "Observation ≠ Decision"
    EVIDENCE_AUTHORITY = "Evidence ≠ Authority"
    PRESENTATION_TRUTH = "Presentation ≠ Truth"
    CAPABILITY_PERMISSION = "Capability ≠ Permission"

    # Actuator (5)
    PROPOSAL_GRANT = "Proposal ≠ Grant"
    GRANT_EXECUTION = "Grant ≠ Execution"
    EXECUTION_SUCCESS = "Execution ≠ Success"
    SUCCESS_VERIFIED = "Success ≠ Verified Consequence"
    VERIFIED_CONSEQUENCE = "Verified ≠ Consequence"

    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.OBSERVATION_DECISION,
            cls.EVIDENCE_AUTHORITY,
            cls.PRESENTATION_TRUTH,
            cls.CAPABILITY_PERMISSION,
            cls.PROPOSAL_GRANT,
            cls.GRANT_EXECUTION,
            cls.EXECUTION_SUCCESS,
            cls.SUCCESS_VERIFIED,
            cls.VERIFIED_CONSEQUENCE,
        ]

    @classmethod
    def actuator_invariantes(cls) -> List[str]:
        return [
            cls.PROPOSAL_GRANT,
            cls.GRANT_EXECUTION,
            cls.EXECUTION_SUCCESS,
            cls.SUCCESS_VERIFIED,
        ]


# --- Enums ---
class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    GRANTED = "granted"
    EXECUTED = "executed"
    VERIFIED = "verified"
    FAILED = "failed"


class PolicyVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_GRANT = "require_grant"


class ConsequenceLevel(str, Enum):
    LOCAL = "local"           # No external consequence
    DURABLE = "durable"       # Persistent but reversible
    EXTERNAL = "external"     # External side effect
    IRREVERSIBLE = "irreversible"  # Cannot be undone


# --- Data Classes ---
@dataclass
class Proposal:
    """Propuesta de acción — NO es un grant."""
    proposal_id: str
    intent: str
    capability: str
    parameters: Dict[str, Any]
    consequence_level: ConsequenceLevel
    proposed_by: str
    proposed_at: str
    status: ProposalStatus = ProposalStatus.PENDING
    grant_id: Optional[str] = None
    execution_id: Optional[str] = None
    verification_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "intent": self.intent,
            "capability": self.capability,
            "parameters": self.parameters,
            "consequence_level": self.consequence_level.value,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "status": self.status.value,
            "grant_id": self.grant_id,
            "execution_id": self.execution_id,
            "verification_id": self.verification_id,
        }


@dataclass
class Grant:
    """Grant de autoridad — NO es execution."""
    grant_id: str
    proposal_id: str
    intent_hash: str
    bound_intent_hash: str
    granted_by: str
    grant_at: str
    expires_at: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "proposal_id": self.proposal_id,
            "intent_hash": self.intent_hash,
            "bound_intent_hash": self.bound_intent_hash,
            "granted_by": self.granted_by,
            "grant_at": self.grant_at,
            "expires_at": self.expires_at,
            "constraints": self.constraints,
            "used": self.used,
        }


@dataclass
class Execution:
    """Execution de un grant — NO es success."""
    execution_id: str
    grant_id: str
    proposal_id: str
    capability: str
    parameters: Dict[str, Any]
    started_at: str
    completed_at: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "grant_id": self.grant_id,
            "proposal_id": self.proposal_id,
            "capability": self.capability,
            "parameters": self.parameters,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "success": self.success,
        }


@dataclass
class Verification:
    """Verificación de consecuencia — NO es execution."""
    verification_id: str
    execution_id: str
    proposal_id: str
    expected_state: Dict[str, Any]
    observed_state: Dict[str, Any]
    verified: bool
    verified_at: str
    evidence_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "execution_id": self.execution_id,
            "proposal_id": self.proposal_id,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "verified": self.verified,
            "verified_at": self.verified_at,
            "evidence_hash": self.evidence_hash,
        }


# --- Actuator ---
class Actuator:
    """Actuator — Authority → Reality.

    Flujo:
      1. Recibe proposal
      2. Verifica capability existe
      3. Verifica policy permite
      4. Si es consequential → requiere 🧿 HUMAN GRANT
      5. Ejecuta con grant
      6. Witness verifica consecuencia
      7. Publica a Evidence Bus
    """

    def __init__(self, bus: EvidenceBus):
        self.bus = bus
        self.proposals: Dict[str, Proposal] = {}
        self.grants: Dict[str, Grant] = {}
        self.executions: Dict[str, Execution] = {}
        self.verifications: Dict[str, Verification] = {}
        self.capabilities: Dict[str, Any] = {}
        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config={"version": ACTUATOR_VERSION},
        )

    def register_capability(self, name: str, handler: Any, metadata: Dict[str, Any]) -> None:
        """Register a capability."""
        self.capabilities[name] = {
            "handler": handler,
            "metadata": metadata,
        }

    def propose(
        self,
        intent: str,
        capability: str,
        parameters: Dict[str, Any],
        consequence_level: ConsequenceLevel,
        proposed_by: str = "agent://vscoder",
    ) -> Proposal:
        """Create a proposal — NO es un grant."""
        proposal = Proposal(
            proposal_id=str(uuid.uuid4()),
            intent=intent,
            capability=capability,
            parameters=parameters,
            consequence_level=consequence_level,
            proposed_by=proposed_by,
            proposed_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        )
        self.proposals[proposal.proposal_id] = proposal

        # Publish proposal to evidence bus
        self._publish_proposal(proposal)

        return proposal

    def assess(self, proposal_id: str) -> Dict[str, Any]:
        """Assess a proposal against capability + policy."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {"error": "Proposal not found"}

        # Check capability exists
        capability_exists = proposal.capability in self.capabilities

        # Check policy
        policy_verdict = self._check_policy(proposal)

        # Determine if grant required
        requires_grant = proposal.consequence_level in [
            ConsequenceLevel.EXTERNAL,
            ConsequenceLevel.IRREVERSIBLE,
        ]

        return {
            "proposal_id": proposal_id,
            "capability_exists": capability_exists,
            "policy_verdict": policy_verdict.value,
            "requires_grant": requires_grant,
            "consequence_level": proposal.consequence_level.value,
        }

    def grant(
        self,
        proposal_id: str,
        granted_by: str = "human://root",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Optional[Grant]:
        """Grant authority for a proposal — NO es execution."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return None

        # Compute intent hash
        intent_hash = self._compute_intent_hash(proposal)
        bound_intent_hash = self._compute_bound_intent_hash(proposal, intent_hash)

        grant = Grant(
            grant_id=str(uuid.uuid4()),
            proposal_id=proposal_id,
            intent_hash=intent_hash,
            bound_intent_hash=bound_intent_hash,
            granted_by=granted_by,
            grant_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            constraints=constraints or {},
        )

        self.grants[grant.grant_id] = grant
        proposal.grant_id = grant.grant_id
        proposal.status = ProposalStatus.GRANTED

        # Publish grant to evidence bus
        self._publish_grant(grant)

        return grant

    def execute(self, grant_id: str) -> Execution:
        """Execute a grant — NO es success."""
        grant = self.grants.get(grant_id)
        if not grant:
            raise ValueError("Grant not found")

        if grant.used:
            raise ValueError("Grant already used")

        # Check expiry
        if grant.expires_at and grant.expires_at < time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()):
            raise ValueError("Grant expired")

        proposal = self.proposals.get(grant.proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        # Mark grant as used
        grant.used = True

        # Execute
        execution = Execution(
            execution_id=str(uuid.uuid4()),
            grant_id=grant_id,
            proposal_id=proposal.proposal_id,
            capability=proposal.capability,
            parameters=proposal.parameters,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        )

        try:
            capability = self.capabilities.get(proposal.capability)
            if not capability:
                raise RuntimeError(f"Capability not found: {proposal.capability}")

            handler = capability["handler"]
            result = handler(proposal.parameters)

            execution.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            execution.exit_code = 0
            execution.stdout = str(result)
            execution.success = True

        except Exception as e:
            execution.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            execution.exit_code = 1
            execution.stderr = str(e)
            execution.success = False

        self.executions[execution.execution_id] = execution
        proposal.execution_id = execution.execution_id
        proposal.status = ProposalStatus.EXECUTED

        # Publish execution to evidence bus
        self._publish_execution(execution)

        return execution

    def verify(self, execution_id: str, expected_state: Dict[str, Any]) -> Verification:
        """Verify consequence — NO es execution."""
        execution = self.executions.get(execution_id)
        if not execution:
            raise ValueError("Execution not found")

        # Observe current state
        observed_state = self._observe_state(execution.proposal_id)

        # Compare
        verified = self._compare_states(expected_state, observed_state)

        verification = Verification(
            verification_id=str(uuid.uuid4()),
            execution_id=execution_id,
            proposal_id=execution.proposal_id,
            expected_state=expected_state,
            observed_state=observed_state,
            verified=verified,
            verified_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            evidence_hash=self._compute_evidence_hash(execution, observed_state),
        )

        self.verifications[verification.verification_id] = verification

        proposal = self.proposals.get(execution.proposal_id)
        if proposal:
            proposal.verification_id = verification.verification_id
            proposal.status = ProposalStatus.VERIFIED if verified else ProposalStatus.FAILED

        # Publish verification to evidence bus
        self._publish_verification(verification)

        return verification

    def _check_policy(self, proposal: Proposal) -> PolicyVerdict:
        """Check policy for a proposal."""
        # Simple policy: LOCAL always allowed, others require grant
        if proposal.consequence_level == ConsequenceLevel.LOCAL:
            return PolicyVerdict.ALLOW
        return PolicyVerdict.REQUIRE_GRANT

    def _compute_intent_hash(self, proposal: Proposal) -> str:
        """Compute intent hash."""
        canonical = json.dumps({
            "intent": proposal.intent,
            "capability": proposal.capability,
            "parameters": proposal.parameters,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _compute_bound_intent_hash(self, proposal: Proposal, intent_hash: str) -> str:
        """Compute bound intent hash (includes proposal ID + timestamp)."""
        canonical = json.dumps({
            "proposal_id": proposal.proposal_id,
            "intent_hash": intent_hash,
            "proposed_at": proposal.proposed_at,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _observe_state(self, proposal_id: str) -> Dict[str, Any]:
        """Observe current state after execution."""
        # Placeholder: in production, this would query actual state
        return {"status": "observed"}

    def _compare_states(self, expected: Dict[str, Any], observed: Dict[str, Any]) -> bool:
        """Compare expected vs observed state."""
        return expected == observed

    def _compute_evidence_hash(self, execution: Execution, observed_state: Dict[str, Any]) -> str:
        """Compute evidence hash."""
        canonical = json.dumps({
            "execution_id": execution.execution_id,
            "observed_state": observed_state,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _publish_proposal(self, proposal: Proposal) -> EvidenceEvent:
        """Publish proposal to evidence bus."""
        source = EvidenceSource("pc-actuator", self.producer_hash)
        event = source.emit(
            schema="actuator://proposal",
            subject=proposal.proposal_id,
            payload=proposal.to_dict(),
        )
        return self.bus.publish(event)

    def _publish_grant(self, grant: Grant) -> EvidenceEvent:
        """Publish grant to evidence bus."""
        source = EvidenceSource("pc-actuator", self.producer_hash)
        event = source.emit(
            schema="actuator://grant",
            subject=grant.grant_id,
            payload=grant.to_dict(),
        )
        return self.bus.publish(event)

    def _publish_execution(self, execution: Execution) -> EvidenceEvent:
        """Publish execution to evidence bus."""
        source = EvidenceSource("pc-actuator", self.producer_hash)
        event = source.emit(
            schema="actuator://execution",
            subject=execution.execution_id,
            payload=execution.to_dict(),
        )
        return self.bus.publish(event)

    def _publish_verification(self, verification: Verification) -> EvidenceEvent:
        """Publish verification to evidence bus."""
        source = EvidenceSource("pc-actuator", self.producer_hash)
        event = source.emit(
            schema="actuator://verification",
            subject=verification.verification_id,
            payload=verification.to_dict(),
        )
        return self.bus.publish(event)


# --- Witness ---
class Witness:
    """Witness — verifica consecuencias y publica a Evidence Bus."""

    def __init__(self, bus: EvidenceBus):
        self.bus = bus
        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config={"version": ACTUATOR_VERSION},
        )

    def witness(self, execution: Execution, expected_state: Dict[str, Any]) -> Verification:
        """Witness an execution and verify consequence."""
        # Observe current state
        observed_state = self._observe_state(execution.proposal_id)

        # Compare
        verified = expected_state == observed_state

        verification = Verification(
            verification_id=str(uuid.uuid4()),
            execution_id=execution.execution_id,
            proposal_id=execution.proposal_id,
            expected_state=expected_state,
            observed_state=observed_state,
            verified=verified,
            verified_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            evidence_hash=self._compute_evidence_hash(execution, observed_state),
        )

        # Publish to evidence bus
        source = EvidenceSource("pc-actuator-witness", self.producer_hash)
        event = source.emit(
            schema="actuator://verification",
            subject=verification.verification_id,
            payload=verification.to_dict(),
        )
        self.bus.publish(event)

        return verification

    def _observe_state(self, proposal_id: str) -> Dict[str, Any]:
        """Observe current state."""
        return {"status": "observed", "proposal_id": proposal_id}

    def _compute_evidence_hash(self, execution: Execution, observed_state: Dict[str, Any]) -> str:
        """Compute evidence hash."""
        canonical = json.dumps({
            "execution_id": execution.execution_id,
            "observed_state": observed_state,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
