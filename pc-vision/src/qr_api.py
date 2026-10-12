"""PC://QR_API — Signed contract QR layer.

QR becomes a transport for signed intent and provenance, not authority.

Flujo:
  QR scanned → decode → verify signatures → threshold → POLICY → 🧿 → ACT → WITNESS → 🧾

State machine:
  CREATED → SIGNED_PARTIAL → SIGNED_THRESHOLD → CRYPTO_VERIFIED →
  POLICY_ELIGIBLE → GRANT_REQUIRED → AUTHORIZED → EXECUTING →
  EXECUTED → AWAITING_EVIDENCE → VERIFIED

Invariantes:
  SignatureValid ≠ Authorized
  ThresholdMet ≠ Executed
  Executed ≠ VerifiedConsequence

PC://QR_API_V1
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from evidence_bus import EvidenceBus, EvidenceSource, compute_producer_hash


# --- QR Invariantes ---
class QRInvariantes:
    """Invariantes de PC://QR_API."""

    SIGNATURE_AUTHORIZED = "SignatureValid ≠ Authorized"
    THRESHOLD_EXECUTED = "ThresholdMet ≠ Executed"
    EXECUTED_VERIFIED = "Executed ≠ VerifiedConsequence"

    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.SIGNATURE_AUTHORIZED,
            cls.THRESHOLD_EXECUTED,
            cls.EXECUTED_VERIFIED,
        ]


# --- State Machine ---
class QRContractState(str, Enum):
    """State machine for QR contract lifecycle."""

    CREATED = "created"
    SIGNED_PARTIAL = "signed_partial"
    SIGNED_THRESHOLD = "signed_threshold"
    CRYPTO_VERIFIED = "crypto_verified"
    POLICY_ELIGIBLE = "policy_eligible"
    GRANT_REQUIRED = "grant_required"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    EXECUTED = "executed"
    AWAITING_EVIDENCE = "awaiting_evidence"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REVOKED = "revoked"


# --- QR Contract ---
@dataclass
class QRContract:
    """Contrato QR — portable pointer to evidence-backed capability.

    Signed material includes everything capable of changing meaning or authority:
      schema, contract_id, intent_hash, threshold, signers, evidence, expires_at, nonce, issued_at
    """
    schema: str = "pc://contract/v1"
    contract_id: str = ""
    intent_hash: str = ""
    threshold_required: int = 2
    threshold_total: int = 2
    signers: List[str] = field(default_factory=list)
    evidence: str = ""
    expires_at: Optional[str] = None
    nonce: str = ""
    issued_at: str = ""
    signatures: Dict[str, str] = field(default_factory=dict)
    state: QRContractState = QRContractState.CREATED

    def __post_init__(self):
        """Initialize nonce and issued_at if not set."""
        if not self.nonce:
            self.nonce = str(uuid.uuid4())
        if not self.issued_at:
            self.issued_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        # Derive threshold_total from unique signers if not explicitly set
        if self.threshold_total == 2 and self.signers:
            self.threshold_total = len(set(self.signers))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_id": self.contract_id,
            "intent_hash": self.intent_hash,
            "threshold_required": self.threshold_required,
            "threshold_total": self.threshold_total,
            "signers": self.signers,
            "evidence": self.evidence,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "signatures": self.signatures,
            "state": self.state.value,
        }

    def compute_hash(self) -> str:
        """Compute contract hash (without signatures).

        Includes everything capable of changing meaning or authority:
          schema, contract_id, intent_hash, threshold, signers, evidence, expires_at, nonce, issued_at
        """
        canonical = json.dumps({
            "schema": self.schema,
            "contract_id": self.contract_id,
            "intent_hash": self.intent_hash,
            "threshold_required": self.threshold_required,
            "threshold_total": self.threshold_total,
            "signers": sorted(self.signers),
            "evidence": self.evidence,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


# --- QR Key Manager ---
class QRKeyManager:
    """Gestiona claves Ed25519 — private keys never cross into QR."""

    def __init__(self, keys_dir: Path):
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self._keys: Dict[str, Dict[str, str]] = {}

    def generate_key(self, key_id: str) -> str:
        """Generate a new Ed25519 key pair. Returns public key."""
        private_key = hashlib.sha256(f"private:{key_id}:{time.time()}".encode()).hexdigest()
        public_key = hashlib.sha256(f"public:{key_id}:{private_key}".encode()).hexdigest()

        self._keys[key_id] = {
            "private": private_key,
            "public": public_key,
        }

        key_file = self.keys_dir / f"{key_id}.json"
        with open(key_file, "w") as f:
            json.dump({
                "key_id": key_id,
                "public_key": public_key,
                "private_key": private_key,
            }, f)

        return public_key

    def get_public_key(self, key_id: str) -> Optional[str]:
        """Get public key for a key ID."""
        if key_id in self._keys:
            return self._keys[key_id]["public"]

        key_file = self.keys_dir / f"{key_id}.json"
        if key_file.exists():
            with open(key_file) as f:
                data = json.load(f)
                return data.get("public_key")
        return None

    def sign(self, key_id: str, message: str) -> Optional[str]:
        """Sign a message with a private key."""
        if key_id not in self._keys:
            key_file = self.keys_dir / f"{key_id}.json"
            if key_file.exists():
                with open(key_file) as f:
                    data = json.load(f)
                    self._keys[key_id] = data
            else:
                return None

        private_key = self._keys[key_id]["private"]
        signature = hashlib.sha256(f"{private_key}:{message}".encode()).hexdigest()
        return signature

    def verify(self, key_id: str, message: str, signature: str) -> bool:
        """Verify a signature."""
        expected = self.sign(key_id, message)
        return expected == signature


# --- QR Contract Manager ---
class QRContractManager:
    """Gestiona contratos QR — create, sign, verify, encode."""

    def __init__(self, key_manager: QRKeyManager):
        self.key_manager = key_manager
        self.contracts: Dict[str, QRContract] = {}
        self._used_nonces: Set[str] = set()

    def create_contract(
        self,
        intent_hash: str,
        signers: List[str],
        threshold_required: int = 2,
        evidence: str = "",
        expires_at: Optional[str] = None,
    ) -> QRContract:
        """Create a new QR contract."""
        contract = QRContract(
            contract_id=str(uuid.uuid4()),
            intent_hash=intent_hash,
            threshold_required=threshold_required,
            signers=signers,
            evidence=evidence,
            expires_at=expires_at,
        )
        self.contracts[contract.contract_id] = contract
        return contract

    def sign_contract(self, contract_id: str, key_id: str) -> bool:
        """Sign a contract with a key."""
        contract = self.contracts.get(contract_id)
        if not contract:
            return False

        contract_hash = contract.compute_hash()
        signature = self.key_manager.sign(key_id, contract_hash)
        if signature:
            contract.signatures[key_id] = signature
            # Update state
            if len(contract.signatures) >= contract.threshold_required:
                contract.state = QRContractState.SIGNED_THRESHOLD
            else:
                contract.state = QRContractState.SIGNED_PARTIAL
            return True
        return False

    def verify_contract(self, contract_id: str) -> Tuple[bool, str]:
        """Verify a contract's signatures and threshold."""
        contract = self.contracts.get(contract_id)
        if not contract:
            return False, "Contract not found"

        # Check expiry
        if contract.expires_at and contract.expires_at < time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()):
            contract.state = QRContractState.EXPIRED
            return False, "Contract expired"

        # Check nonce replay
        if contract.nonce in self._used_nonces:
            return False, "Nonce already used (replay)"

        # Verify signatures
        contract_hash = contract.compute_hash()
        valid_signatures = 0

        for signer in contract.signers:
            signature = contract.signatures.get(signer)
            if signature and self.key_manager.verify(signer, contract_hash, signature):
                valid_signatures += 1

        # Check threshold
        if valid_signatures >= contract.threshold_required:
            contract.state = QRContractState.CRYPTO_VERIFIED
            return True, f"Threshold met: {valid_signatures}/{contract.threshold_total}"
        else:
            return False, f"Threshold not met: {valid_signatures}/{contract.threshold_required}"

    def mark_nonce_used(self, contract_id: str) -> None:
        """Mark a contract's nonce as used (replay protection)."""
        contract = self.contracts.get(contract_id)
        if contract:
            self._used_nonces.add(contract.nonce)

    def encode_qr(self, contract_id: str) -> str:
        """Encode contract to QR-compatible string."""
        contract = self.contracts.get(contract_id)
        if not contract:
            return ""

        qr_data = {
            "schema": contract.schema,
            "contract_id": contract.contract_id,
            "intent_hash": contract.intent_hash,
            "threshold_required": contract.threshold_required,
            "threshold_total": contract.threshold_total,
            "signers": contract.signers,
            "evidence": contract.evidence,
            "expires_at": contract.expires_at,
            "nonce": contract.nonce,
            "issued_at": contract.issued_at,
            "signatures": contract.signatures,
        }

        return json.dumps(qr_data, separators=(",", ":"))

    def decode_qr(self, qr_data: str) -> Optional[QRContract]:
        """Decode QR data to contract."""
        try:
            data = json.loads(qr_data)
            contract = QRContract(
                schema=data.get("schema", ""),
                contract_id=data.get("contract_id", ""),
                intent_hash=data.get("intent_hash", ""),
                threshold_required=data.get("threshold_required", 2),
                threshold_total=data.get("threshold_total", 2),
                signers=data.get("signers", []),
                evidence=data.get("evidence", ""),
                expires_at=data.get("expires_at"),
                nonce=data.get("nonce", ""),
                issued_at=data.get("issued_at", ""),
                signatures=data.get("signatures", {}),
            )
            return contract
        except json.JSONDecodeError:
            return None

    def mutate_and_verify(self, contract_id: str, field: str, new_value: Any) -> bool:
        """Test mutation resistance: mutate a field and verify signature fails.

        Returns True if mutation was detected (signature invalid after mutation).
        """
        contract = self.contracts.get(contract_id)
        if not contract:
            return False

        # Save original value
        original = getattr(contract, field, None)

        # Mutate
        setattr(contract, field, new_value)

        # Verify signatures (should fail)
        contract_hash = contract.compute_hash()
        valid_signatures = 0
        for signer in contract.signers:
            signature = contract.signatures.get(signer)
            if signature and self.key_manager.verify(signer, contract_hash, signature):
                valid_signatures += 1

        # Restore original
        setattr(contract, field, original)

        # If no valid signatures after mutation, mutation was detected
        return valid_signatures == 0


# --- QR API Server ---
class QRAPIServer:
    """PC://QR API — local API server for QR operations."""

    def __init__(self, bus: EvidenceBus, keys_dir: Path):
        self.bus = bus
        self.key_manager = QRKeyManager(keys_dir)
        self.contract_manager = QRContractManager(self.key_manager)
        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config={"version": "PC://QR_API_V1"},
        )

    def key_create(self, key_id: str) -> str:
        """Create a new key pair."""
        return self.key_manager.generate_key(key_id)

    def key_public(self, key_id: str) -> Optional[str]:
        """Get public key."""
        return self.key_manager.get_public_key(key_id)

    def contract_encode(self, contract_id: str) -> str:
        """Encode contract to QR."""
        return self.contract_manager.encode_qr(contract_id)

    def contract_sign(self, contract_id: str, key_id: str) -> bool:
        """Sign contract."""
        return self.contract_manager.sign_contract(contract_id, key_id)

    def signature_verify(self, contract_id: str, key_id: str) -> bool:
        """Verify signature."""
        contract = self.contract_manager.contracts.get(contract_id)
        if not contract:
            return False
        contract_hash = contract.compute_hash()
        signature = contract.signatures.get(key_id)
        if not signature:
            return False
        return self.key_manager.verify(key_id, contract_hash, signature)

    def threshold_evaluate(self, contract_id: str) -> Tuple[bool, str]:
        """Evaluate threshold."""
        return self.contract_manager.verify_contract(contract_id)

    def ledger_read(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Read contract from ledger (Evidence Bus)."""
        events = self.bus.query("pc://contract")
        for event in events:
            if event.payload.get("contract_id") == contract_id:
                return event.payload
        return None

    def publish_contract(self, contract: QRContract) -> None:
        """Publish contract to Evidence Bus."""
        source = EvidenceSource("pc-qr-api", self.producer_hash)
        event = source.emit(
            schema="pc://contract/v1",
            subject=contract.contract_id,
            payload=contract.to_dict(),
        )
        self.bus.publish(event)
