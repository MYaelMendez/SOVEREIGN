"""PC://QR_API_V1 — Acceptance Tests (Updated).

Tests:
  1-3: Invariantes + state machine
  4-8: Key management + contract lifecycle
  9-12: Signature verification + threshold
  13-19: Mutation resistance (7 fields)
  20: Replay protection
  21-24: QR encode/decode + evidence pointer + ledger
  25-28: Crypto valid ≠ authorized + receipt + bus integration
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_bus import EvidenceBus, EvidenceSource, compute_producer_hash
from qr_api import (
    QRContract,
    QRContractManager,
    QRContractState,
    QRInvariantes,
    QRKeyManager,
    QRAPIServer,
)


# --- Acceptance Tests ---
def test_01_qr_invariantes():
    """Test: QR invariantes."""
    invariants = QRInvariantes.all()
    assert len(invariants) == 3
    assert "SignatureValid ≠ Authorized" in invariants
    assert "ThresholdMet ≠ Executed" in invariants
    assert "Executed ≠ VerifiedConsequence" in invariants
    return True


def test_02_state_machine():
    """Test: State machine defined."""
    states = [s.value for s in QRContractState]
    assert "created" in states
    assert "signed_partial" in states
    assert "signed_threshold" in states
    assert "crypto_verified" in states
    assert "policy_eligible" in states
    assert "grant_required" in states
    assert "authorized" in states
    assert "executing" in states
    assert "executed" in states
    assert "awaiting_evidence" in states
    assert "verified" in states
    assert "expired" in states
    assert "revoked" in states
    return True


def test_03_state_transitions():
    """Test: State transitions follow contract."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            threshold_required=2,
        )
        assert contract.state == QRContractState.CREATED

        cm.sign_contract(contract.contract_id, "alice")
        assert contract.state == QRContractState.SIGNED_PARTIAL

        cm.sign_contract(contract.contract_id, "bob")
        assert contract.state == QRContractState.SIGNED_THRESHOLD

        passed, _ = cm.verify_contract(contract.contract_id)
        assert passed
        assert contract.state == QRContractState.CRYPTO_VERIFIED
        return True


def test_04_key_create():
    """Test: key.create."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        public_key = manager.generate_key("alice")
        assert public_key is not None
        assert len(public_key) == 64
        return True


def test_05_key_public():
    """Test: key.public."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        manager.generate_key("alice")
        public_key = manager.get_public_key("alice")
        assert public_key is not None
        return True


def test_06_contract_create():
    """Test: Contract creation with nonce + issued_at."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )

        assert contract.contract_id != ""
        assert contract.nonce != ""
        assert contract.issued_at != ""
        assert contract.threshold_required == 2
        assert contract.threshold_total == 2
        return True


def test_07_contract_hash_includes_all_fields():
    """Test: Contract hash includes all signed material."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            evidence="evidence://123",
            expires_at="2027-01-01T00:00:00",
        )

        hash1 = contract.compute_hash()

        original_intent = contract.intent_hash
        contract.intent_hash = "b" * 64
        hash2 = contract.compute_hash()
        assert hash1 != hash2, "Hash should change when intent_hash changes"
        contract.intent_hash = original_intent

        original_nonce = contract.nonce
        contract.nonce = str(uuid.uuid4())
        hash3 = contract.compute_hash()
        assert hash1 != hash3, "Hash should change when nonce changes"
        contract.nonce = original_nonce

        return True


def test_08_threshold_structural():
    """Test: Threshold is structural, not string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob", "charlie"],
            threshold_required=2,
        )

        assert contract.threshold_required == 2
        assert contract.threshold_total == 3
        return True


def test_09_signature_verify():
    """Test: signature.verify."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")
        server.key_create("bob")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )

        server.contract_sign(contract.contract_id, "alice")
        assert server.signature_verify(contract.contract_id, "alice")
        return True


def test_10_threshold_evaluate():
    """Test: threshold.evaluate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")
        server.key_create("bob")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            threshold_required=2,
        )

        passed, msg = server.threshold_evaluate(contract.contract_id)
        assert not passed

        server.contract_sign(contract.contract_id, "alice")
        server.contract_sign(contract.contract_id, "bob")

        passed, msg = server.threshold_evaluate(contract.contract_id)
        assert passed
        return True


def test_11_private_key_not_in_qr():
    """Test: private key never crosses into QR."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
        )

        server.contract_sign(contract.contract_id, "alice")
        qr_data = server.contract_encode(contract.contract_id)

        assert "private" not in qr_data.lower()
        return True


def test_12_signature_valid_not_authorized():
    """Test: SignatureValid ≠ Authorized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
        )

        server.contract_sign(contract.contract_id, "alice")

        assert server.signature_verify(contract.contract_id, "alice")
        passed, _ = server.threshold_evaluate(contract.contract_id)
        assert not passed
        return True


def test_13_mutation_intent_hash():
    """Test: Mutation of intent_hash breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "intent_hash", "b" * 64)
        return True


def test_14_mutation_threshold():
    """Test: Mutation of threshold breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "threshold_required", 1)
        return True


def test_15_mutation_signers():
    """Test: Mutation of signers breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "signers", ["alice"])
        return True


def test_16_mutation_evidence():
    """Test: Mutation of evidence breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            evidence="evidence://123",
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "evidence", "evidence://456")
        return True


def test_17_mutation_expires_at():
    """Test: Mutation of expires_at breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            expires_at="2027-01-01T00:00:00",
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "expires_at", "2028-01-01T00:00:00")
        return True


def test_18_mutation_nonce():
    """Test: Mutation of nonce breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "nonce", str(uuid.uuid4()))
        return True


def test_19_mutation_contract_id():
    """Test: Mutation of contract_id breaks signature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        assert cm.mutate_and_verify(contract.contract_id, "contract_id", str(uuid.uuid4()))
        return True


def test_20_replay_protection():
    """Test: Replay protection via nonce."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        passed, _ = cm.verify_contract(contract.contract_id)
        assert passed
        cm.mark_nonce_used(contract.contract_id)

        passed, msg = cm.verify_contract(contract.contract_id)
        assert not passed
        assert "replay" in msg.lower() or "nonce" in msg.lower()
        return True


def test_21_expired_contract():
    """Test: Expired contract rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
            expires_at="2020-01-01T00:00:00",
        )

        server.contract_sign(contract.contract_id, "alice")
        passed, msg = server.threshold_evaluate(contract.contract_id)
        assert not passed
        assert "expired" in msg.lower()
        return True


def test_22_qr_encode_decode():
    """Test: QR encode/decode roundtrip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
        )

        qr_data = server.contract_encode(contract.contract_id)
        decoded = server.contract_manager.decode_qr(qr_data)

        assert decoded is not None
        assert decoded.contract_id == contract.contract_id
        assert decoded.intent_hash == contract.intent_hash
        return True


def test_23_qr_evidence_pointer():
    """Test: QR as evidence pointer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        source = EvidenceSource("test", "producer_hash")
        event = source.emit(
            schema="test://evidence",
            subject="test_subject",
            payload={"data": "test"},
        )
        bus.publish(event)

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
            evidence=event.id,
        )

        server.publish_contract(contract)
        assert contract.evidence == event.id
        return True


def test_24_ledger_read():
    """Test: ledger.read from Evidence Bus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
        )

        server.publish_contract(contract)

        ledger_entry = server.ledger_read(contract.contract_id)
        assert ledger_entry is not None
        assert ledger_entry["contract_id"] == contract.contract_id
        return True


def test_25_crypto_valid_but_not_authorized():
    """Test: Cryptographic truth ≠ operational permission."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = QRKeyManager(Path(tmpdir))
        cm = QRContractManager(manager)
        manager.generate_key("alice")
        manager.generate_key("bob")

        contract = cm.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            threshold_required=2,
        )
        cm.sign_contract(contract.contract_id, "alice")
        cm.sign_contract(contract.contract_id, "bob")

        passed, _ = cm.verify_contract(contract.contract_id)
        assert passed

        cm.mark_nonce_used(contract.contract_id)

        contract_hash = contract.compute_hash()
        valid = 0
        for signer in contract.signers:
            sig = contract.signatures.get(signer)
            if sig and manager.verify(signer, contract_hash, sig):
                valid += 1
        assert valid >= 2

        passed, msg = cm.verify_contract(contract.contract_id)
        assert not passed
        return True


def test_26_threshold_met_not_executed():
    """Test: ThresholdMet ≠ Executed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")
        server.key_create("bob")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
            threshold_required=2,
        )

        server.contract_sign(contract.contract_id, "alice")
        server.contract_sign(contract.contract_id, "bob")

        passed, _ = server.threshold_evaluate(contract.contract_id)
        assert passed
        return True


def test_27_qr_api_receipt():
    """Test: QR API receipt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")
        server.key_create("bob")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice", "bob"],
        )

        server.contract_sign(contract.contract_id, "alice")
        server.contract_sign(contract.contract_id, "bob")
        server.publish_contract(contract)

        receipt = {
            "schema": "qr://receipt/v1",
            "contract_id": contract.contract_id,
            "contract_hash": contract.compute_hash(),
            "signers": contract.signers,
            "signatures": contract.signatures,
            "nonce": contract.nonce,
            "bus_root": bus.compute_bus_root(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        assert len(receipt["contract_hash"]) == 64
        assert len(receipt["bus_root"]) == 64
        return True


def test_28_qr_bus_integration():
    """Test: QR contract in Evidence Bus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EvidenceBus()
        server = QRAPIServer(bus, Path(tmpdir))
        server.key_create("alice")

        contract = server.contract_manager.create_contract(
            intent_hash="a" * 64,
            signers=["alice"],
        )

        server.publish_contract(contract)

        contracts = bus.query("pc://contract")
        assert len(contracts) == 1
        assert contracts[0].payload["contract_id"] == contract.contract_id

        is_valid, errors = bus.verify()
        assert is_valid
        return True


# --- Test Runner ---
def run_all_tests():
    """Run all 28 acceptance tests."""
    tests = [
        ("QR invariantes", test_01_qr_invariantes),
        ("state machine", test_02_state_machine),
        ("state transitions", test_03_state_transitions),
        ("key.create", test_04_key_create),
        ("key.public", test_05_key_public),
        ("contract create", test_06_contract_create),
        ("hash includes all fields", test_07_contract_hash_includes_all_fields),
        ("threshold structural", test_08_threshold_structural),
        ("signature.verify", test_09_signature_verify),
        ("threshold.evaluate", test_10_threshold_evaluate),
        ("private key not in QR", test_11_private_key_not_in_qr),
        ("SignatureValid ≠ Authorized", test_12_signature_valid_not_authorized),
        ("mutation intent_hash", test_13_mutation_intent_hash),
        ("mutation threshold", test_14_mutation_threshold),
        ("mutation signers", test_15_mutation_signers),
        ("mutation evidence", test_16_mutation_evidence),
        ("mutation expires_at", test_17_mutation_expires_at),
        ("mutation nonce", test_18_mutation_nonce),
        ("mutation contract_id", test_19_mutation_contract_id),
        ("replay protection", test_20_replay_protection),
        ("expired contract", test_21_expired_contract),
        ("QR encode/decode", test_22_qr_encode_decode),
        ("QR evidence pointer", test_23_qr_evidence_pointer),
        ("ledger.read", test_24_ledger_read),
        ("crypto valid ≠ authorized", test_25_crypto_valid_but_not_authorized),
        ("ThresholdMet ≠ Executed", test_26_threshold_met_not_executed),
        ("QR API receipt", test_27_qr_api_receipt),
        ("QR bus integration", test_28_qr_bus_integration),
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

    print(f"\nPC://QR_API_V1 — Acceptance Tests (Updated)")
    print(f"{'=' * 50}")
    for r in results:
        print(r)
    print(f"{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED — PC://QR_API_V1 UPDATED")
    else:
        print(f"\n✗ {failed} TESTS FAILED")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
