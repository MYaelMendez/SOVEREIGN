"""PC://ACTUATOR — Acceptance Tests.

16 acceptance criteria:
  1. 9 invariantes en código
  2. Proposal ≠ Grant
  3. Grant ≠ Execution
  4. Execution ≠ Success
  5. Success ≠ Verified Consequence
  6. Proposal se publica a Evidence Bus
  7. Grant se publica a Evidence Bus
  8. Execution se publica a Evidence Bus
  9. Verification se publica a Evidence Bus
 10. Flujo completo: propose → grant → execute → verify
 11. Capability no existe → DENY
 12. Consequential sin grant → DENY
 13. Grant usado no se puede reusar
 14. Intent hash único
 15. Bound intent hash incluye proposal_id
 16. Actuator receipt
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_bus import EvidenceBus, EvidenceSource, compute_producer_hash
from actuator import (
    ACTUATOR_VERSION,
    Actuator,
    ConsequenceLevel,
    Execution,
    Grant,
    Invariantes,
    Proposal,
    ProposalStatus,
    Verification,
    Witness,
)


def test_01_9_invariantes():
    """Test: 9 invariantes en código."""
    invariants = Invariantes.all()
    assert len(invariants) == 9
    assert "Observation ≠ Decision" in invariants
    assert "Evidence ≠ Authority" in invariants
    assert "Presentation ≠ Truth" in invariants
    assert "Capability ≠ Permission" in invariants
    assert "Proposal ≠ Grant" in invariants
    assert "Grant ≠ Execution" in invariants
    assert "Execution ≠ Success" in invariants
    assert "Success ≠ Verified Consequence" in invariants
    assert "Verified ≠ Consequence" in invariants
    return True


def test_02_proposal_not_grant():
    """Test: Proposal ≠ Grant."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={"key": "value"},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    assert proposal.status == ProposalStatus.PENDING
    assert proposal.grant_id is None
    assert proposal.proposal_id != ""
    return True


def test_03_grant_not_execution():
    """Test: Grant ≠ Execution."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={"key": "value"},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)
    assert grant is not None
    assert grant.grant_id != ""
    assert grant.proposal_id == proposal.proposal_id
    assert grant.used is False
    return True


def test_04_execution_not_success():
    """Test: Execution ≠ Success."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    # Register a capability that fails
    def failing_handler(params):
        raise RuntimeError("Intentional failure")

    actuator.register_capability("failing_cap", failing_handler, {})

    proposal = actuator.propose(
        intent="test_fail",
        capability="failing_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)
    execution = actuator.execute(grant.grant_id)

    assert execution.success is False
    assert execution.exit_code == 1
    assert "Intentional failure" in execution.stderr
    return True


def test_05_success_not_verified():
    """Test: Success ≠ Verified Consequence."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    # Register a capability that succeeds
    def success_handler(params):
        return "done"

    actuator.register_capability("success_cap", success_handler, {})

    proposal = actuator.propose(
        intent="test_success",
        capability="success_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)
    execution = actuator.execute(grant.grant_id)

    assert execution.success is True
    assert execution.exit_code == 0

    # Verify with wrong expected state
    verification = actuator.verify(
        execution.execution_id,
        expected_state={"status": "wrong"},
    )

    assert verification.verified is False
    return True


def test_06_proposal_published():
    """Test: Proposal se publica a Evidence Bus."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    proposals = bus.query("actuator://proposal")
    assert len(proposals) == 1
    assert proposals[0].payload["proposal_id"] == proposal.proposal_id
    return True


def test_07_grant_published():
    """Test: Grant se publica a Evidence Bus."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)

    grants = bus.query("actuator://grant")
    assert len(grants) == 1
    assert grants[0].payload["grant_id"] == grant.grant_id
    return True


def test_08_execution_published():
    """Test: Execution se publica a Evidence Bus."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    def handler(params):
        return "ok"

    actuator.register_capability("test_cap", handler, {})

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)
    execution = actuator.execute(grant.grant_id)

    executions = bus.query("actuator://execution")
    assert len(executions) == 1
    assert executions[0].payload["execution_id"] == execution.execution_id
    return True


def test_09_verification_published():
    """Test: Verification se publica a Evidence Bus."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    def handler(params):
        return "ok"

    actuator.register_capability("test_cap", handler, {})

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)
    execution = actuator.execute(grant.grant_id)
    verification = actuator.verify(execution.execution_id, {"status": "observed"})

    verifications = bus.query("actuator://verification")
    assert len(verifications) == 1
    assert verifications[0].payload["verification_id"] == verification.verification_id
    return True


def test_10_full_flow():
    """Test: Flujo completo: propose → grant → execute → verify."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    def handler(params):
        return "done"

    actuator.register_capability("full_cap", handler, {})

    # Propose
    proposal = actuator.propose(
        intent="full_test",
        capability="full_cap",
        parameters={"key": "value"},
        consequence_level=ConsequenceLevel.LOCAL,
    )
    assert proposal.status == ProposalStatus.PENDING

    # Grant
    grant = actuator.grant(proposal.proposal_id)
    assert grant is not None
    assert proposal.status == ProposalStatus.GRANTED

    # Execute
    execution = actuator.execute(grant.grant_id)
    assert execution.success is True
    assert proposal.status == ProposalStatus.EXECUTED

    # Verify
    verification = actuator.verify(execution.execution_id, {"status": "observed"})
    assert verification.verified is True
    assert proposal.status == ProposalStatus.VERIFIED

    # Check all published to bus
    assert len(bus.query("actuator://proposal")) == 1
    assert len(bus.query("actuator://grant")) == 1
    assert len(bus.query("actuator://execution")) == 1
    assert len(bus.query("actuator://verification")) == 1
    return True


def test_11_capability_not_exists():
    """Test: Capability no existe → DENY."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal = actuator.propose(
        intent="test_action",
        capability="nonexistent_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    assessment = actuator.assess(proposal.proposal_id)
    assert assessment["capability_exists"] is False
    return True


def test_12_consequential_requires_grant():
    """Test: Consequential sin grant → DENY."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    def handler(params):
        return "ok"

    actuator.register_capability("ext_cap", handler, {})

    proposal = actuator.propose(
        intent="external_action",
        capability="ext_cap",
        parameters={},
        consequence_level=ConsequenceLevel.EXTERNAL,
    )

    assessment = actuator.assess(proposal.proposal_id)
    assert assessment["requires_grant"] is True
    assert assessment["policy_verdict"] == "require_grant"
    return True


def test_13_grant_not_reusable():
    """Test: Grant usado no se puede reusar."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    def handler(params):
        return "ok"

    actuator.register_capability("test_cap", handler, {})

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)

    # First execution should succeed
    execution1 = actuator.execute(grant.grant_id)
    assert execution1.success is True

    # Second execution should fail
    try:
        actuator.execute(grant.grant_id)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already used" in str(e)
    return True


def test_14_intent_hash_unique():
    """Test: Intent hash único."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal1 = actuator.propose(
        intent="action_1",
        capability="test_cap",
        parameters={"key": "value1"},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    proposal2 = actuator.propose(
        intent="action_2",
        capability="test_cap",
        parameters={"key": "value2"},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    hash1 = actuator._compute_intent_hash(proposal1)
    hash2 = actuator._compute_intent_hash(proposal2)

    assert hash1 != hash2
    assert len(hash1) == 64
    return True


def test_15_bound_intent_hash():
    """Test: Bound intent hash incluye proposal_id."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    intent_hash = actuator._compute_intent_hash(proposal)
    bound_hash = actuator._compute_bound_intent_hash(proposal, intent_hash)

    assert bound_hash != intent_hash
    assert len(bound_hash) == 64
    return True


def test_16_actuator_receipt():
    """Test: Actuator receipt."""
    bus = EvidenceBus()
    actuator = Actuator(bus)

    def handler(params):
        return "ok"

    actuator.register_capability("test_cap", handler, {})

    proposal = actuator.propose(
        intent="test_action",
        capability="test_cap",
        parameters={},
        consequence_level=ConsequenceLevel.LOCAL,
    )

    grant = actuator.grant(proposal.proposal_id)
    execution = actuator.execute(grant.grant_id)
    verification = actuator.verify(execution.execution_id, {"status": "observed"})

    receipt = {
        "schema": "actuator://receipt",
        "actuator_version": ACTUATOR_VERSION,
        "proposal_id": proposal.proposal_id,
        "grant_id": grant.grant_id,
        "execution_id": execution.execution_id,
        "verification_id": verification.verification_id,
        "verified": verification.verified,
        "bus_root": bus.compute_bus_root(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    assert receipt["verified"] is True
    assert len(receipt["bus_root"]) == 64
    return True


# --- Test Runner ---
def run_all_tests():
    """Run all 16 acceptance tests."""
    tests = [
        ("9 invariantes", test_01_9_invariantes),
        ("Proposal ≠ Grant", test_02_proposal_not_grant),
        ("Grant ≠ Execution", test_03_grant_not_execution),
        ("Execution ≠ Success", test_04_execution_not_success),
        ("Success ≠ Verified", test_05_success_not_verified),
        ("proposal published", test_06_proposal_published),
        ("grant published", test_07_grant_published),
        ("execution published", test_08_execution_published),
        ("verification published", test_09_verification_published),
        ("full flow", test_10_full_flow),
        ("capability not exists", test_11_capability_not_exists),
        ("consequential requires grant", test_12_consequential_requires_grant),
        ("grant not reusable", test_13_grant_not_reusable),
        ("intent hash unique", test_14_intent_hash_unique),
        ("bound intent hash", test_15_bound_intent_hash),
        ("actuator receipt", test_16_actuator_receipt),
    ]

    passed = 0
    failed = 0
    results = []

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
            results.append(f"  ✓ {name}")
        except Exception as e:
            failed += 1
            results.append(f"  ✗ {name}: {e}")

    print(f"\nPC://ACTUATOR — Acceptance Tests")
    print(f"{'=' * 50}")
    for r in results:
        print(r)
    print(f"{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED — PC://ACTUATOR_V1 FROZEN")
    else:
        print(f"\n✗ {failed} TESTS FAILED — DO NOT FREEZE ACTUATOR")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
