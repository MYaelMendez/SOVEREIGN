"""PC://EVIDENCE — Acceptance Tests.

16 acceptance criteria:
  1. publish event with hash chain
  2. verify bus integrity
  3. query by schema prefix
  4. JSONL round-trip
  5. tampered event detected
  6. malformed JSONL rejected
  7. bus root produced
  8. decision gate flow
  9. evidence → decision → grant
  10. evidence ≠ authority (constitutional)
  11. multi-source (vision + benchmark + test + git)
  12. producer hash consistency
  13. payload hash verification
  14. empty bus
  15. cross-source query
  16. bus receipt
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_bus import (
    BUS_VERSION,
    BenchmarkEvidenceSource,
    DecisionGate,
    EvidenceBus,
    EvidenceEvent,
    EvidenceSource,
    GitEvidenceSource,
    TestEvidenceSource,
    VisionEvidenceSource,
    validate_evidence_event,
    compute_producer_hash,
)


def test_01_publish_event():
    """Test: publish event with hash chain."""
    bus = EvidenceBus()
    source = VisionEvidenceSource("producer_hash_123")

    event = source.emit_detection("test_video", [{"track_id": 1, "class": "person"}], 0)
    published = bus.publish(event)

    assert published.event_hash != "", "event_hash should be set"
    assert published.payload_hash != "", "payload_hash should be set"
    assert published.previous_hash == bus._genesis_hash, "first event should link to genesis"
    assert len(bus.events) == 1
    return True


def test_02_verify_bus():
    """Test: verify bus integrity."""
    bus = EvidenceBus()
    source = VisionEvidenceSource("producer_hash_123")

    for i in range(5):
        event = source.emit_detection("test_video", [{"track_id": i}], i)
        bus.publish(event)

    is_valid, errors = bus.verify()
    assert is_valid, f"Bus should be valid: {errors}"
    return True


def test_03_query_by_schema():
    """Test: query by schema prefix."""
    bus = EvidenceBus()
    vision_src = VisionEvidenceSource("vp")
    bench_src = BenchmarkEvidenceSource("bp")

    bus.publish(vision_src.emit_detection("v1", [], 0))
    bus.publish(bench_src.emit_latency("b1", 10.0, 20.0, 60.0))
    bus.publish(vision_src.emit_detection("v2", [], 1))

    vision_events = bus.query("vision://")
    bench_events = bus.query("benchmark://")

    assert len(vision_events) == 2, f"Expected 2 vision events, got {len(vision_events)}"
    assert len(bench_events) == 1, f"Expected 1 benchmark event, got {len(bench_events)}"
    return True


def test_04_jsonl_roundtrip():
    """Test: JSONL round-trip preserves all data."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        bus = EvidenceBus()
        source = VisionEvidenceSource("producer_hash_123")

        for i in range(5):
            event = source.emit_detection("test_video", [{"track_id": i, "class": "person"}], i)
            bus.publish(event)

        bus.to_jsonl(jsonl_path)

        loaded = EvidenceBus.from_jsonl(jsonl_path)
        assert len(loaded.events) == 5, f"Expected 5 events, got {len(loaded.events)}"

        is_valid, errors = loaded.verify()
        assert is_valid, f"Loaded bus should be valid: {errors}"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_05_tampered_event():
    """Test: tampered event is detected."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        bus = EvidenceBus()
        source = VisionEvidenceSource("producer_hash_123")

        for i in range(5):
            event = source.emit_detection("test_video", [{"track_id": i}], i)
            bus.publish(event)

        bus.to_jsonl(jsonl_path)

        # Tamper: modify a payload
        with open(jsonl_path, "r") as f:
            lines = f.readlines()
        data = json.loads(lines[2])
        data["payload"]["detections"][0]["track_id"] = 999
        lines[2] = json.dumps(data) + "\n"
        with open(jsonl_path, "w") as f:
            f.writelines(lines)

        loaded = EvidenceBus.from_jsonl(jsonl_path)
        is_valid, errors = loaded.verify()
        assert not is_valid, "Tampered event should be detected"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_06_malformed_jsonl():
    """Test: malformed JSONL is rejected."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        f.write('{"schema": "vision://detection", "id": "123"}\n')
        f.write('INVALID JSON\n')
        jsonl_path = Path(f.name)

    try:
        try:
            EvidenceBus.from_jsonl(jsonl_path)
            assert False, "Malformed JSONL should raise ValueError"
        except ValueError:
            pass
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_07_bus_root():
    """Test: bus root is produced."""
    bus = EvidenceBus()
    source = VisionEvidenceSource("producer_hash_123")

    for i in range(5):
        event = source.emit_detection("test_video", [{"track_id": i}], i)
        bus.publish(event)

    root = bus.compute_bus_root()
    assert len(root) == 64, f"Bus root should be 64 hex chars, got {len(root)}"
    assert root != "0" * 64, "Bus root should not be zero"
    return True


def test_08_decision_gate_flow():
    """Test: decision gate flow."""
    bus = EvidenceBus()
    vision_src = VisionEvidenceSource("vp")
    gate = DecisionGate(bus)

    event = vision_src.emit_detection("test_video", [{"track_id": 1}], 0)
    published = bus.publish(event)

    decision = gate.evaluate(
        intent="detect_objects",
        evidence_ids=[published.id],
        policy_verdict="allow",
        principal="human://root",
        reason="Vision evidence supports object detection",
    )

    assert decision.policy_verdict == "allow"
    assert decision.grant_id is not None, "Allow decision should produce grant"
    assert decision.principal == "human://root"
    return True


def test_09_evidence_to_grant():
    """Test: evidence → decision → grant."""
    bus = EvidenceBus()
    bench_src = BenchmarkEvidenceSource("bp")
    gate = DecisionGate(bus)

    event = bench_src.emit_latency("test_op", 10.0, 20.0, 60.0)
    published = bus.publish(event)

    decision = gate.evaluate(
        intent="run_benchmark",
        evidence_ids=[published.id],
        policy_verdict="allow",
        principal="agent://vscoder",
        reason="Benchmark evidence supports execution",
    )

    assert decision.grant_id is not None
    assert len(decision.evidence_refs) == 1
    assert decision.evidence_refs[0] == published.id
    return True


def test_10_evidence_not_authority():
    """Test: evidence ≠ authority (constitutional principle)."""
    bus = EvidenceBus()
    vision_src = VisionEvidenceSource("vp")
    gate = DecisionGate(bus)

    event = vision_src.emit_detection("test_video", [{"track_id": 1}], 0)
    published = bus.publish(event)

    # Evidence alone cannot produce a grant
    # Decision requires: Evidence + Intent + Policy + Principal
    decision = gate.evaluate(
        intent="detect_objects",
        evidence_ids=[published.id],
        policy_verdict="deny",  # Policy denies
        principal="human://root",
        reason="Evidence exists but policy denies",
    )

    assert decision.grant_id is None, "Denied decision should not produce grant"
    assert decision.policy_verdict == "deny"
    return True


def test_11_multi_source():
    """Test: multi-source (vision + benchmark + test + git)."""
    bus = EvidenceBus()
    vision_src = VisionEvidenceSource("vp")
    bench_src = BenchmarkEvidenceSource("bp")
    test_src = TestEvidenceSource("tp")
    git_src = GitEvidenceSource("gp")

    bus.publish(vision_src.emit_detection("v1", [], 0))
    bus.publish(bench_src.emit_latency("b1", 10.0, 20.0, 60.0))
    bus.publish(test_src.emit_result("t1", True, 10, 0))
    bus.publish(git_src.emit_change("g1", "modify", ["file.ts"]))

    assert len(bus.query("vision://")) == 1
    assert len(bus.query("benchmark://")) == 1
    assert len(bus.query("test://")) == 1
    assert len(bus.query("git://")) == 1

    is_valid, errors = bus.verify()
    assert is_valid, f"Multi-source bus should be valid: {errors}"
    return True


def test_12_producer_hash():
    """Test: producer hash consistency."""
    config = {"model": "yolov8n", "threshold": 0.5}
    hash1 = compute_producer_hash("0.1.0", config)
    hash2 = compute_producer_hash("0.1.0", config)
    hash3 = compute_producer_hash("0.2.0", config)

    assert hash1 == hash2, "Same code + config should produce same hash"
    assert hash1 != hash3, "Different code should produce different hash"
    return True


def test_13_payload_hash():
    """Test: payload hash verification."""
    bus = EvidenceBus()
    source = VisionEvidenceSource("producer_hash_123")

    event = source.emit_detection("test_video", [{"track_id": 1, "class": "person"}], 0)
    published = bus.publish(event)

    # Verify payload hash
    recomputed = published.compute_payload_hash()
    assert recomputed == published.payload_hash, "Payload hash should match"
    return True


def test_14_empty_bus():
    """Test: empty bus."""
    bus = EvidenceBus()
    root = bus.compute_bus_root()
    assert len(root) == 64, "Empty bus should still produce a root"
    is_valid, errors = bus.verify()
    assert is_valid, "Empty bus should be valid"
    return True


def test_15_cross_source_query():
    """Test: cross-source query."""
    bus = EvidenceBus()
    vision_src = VisionEvidenceSource("vp")
    bench_src = BenchmarkEvidenceSource("bp")

    for i in range(3):
        bus.publish(vision_src.emit_detection(f"v{i}", [], i))
        bus.publish(bench_src.emit_latency(f"b{i}", 10.0 + i, 20.0 + i, 60.0))

    all_events = bus.query("")
    assert len(all_events) == 6, f"Expected 6 events, got {len(all_events)}"
    return True


def test_16_bus_receipt():
    """Test: bus receipt."""
    bus = EvidenceBus()
    vision_src = VisionEvidenceSource("vp")
    bench_src = BenchmarkEvidenceSource("bp")

    bus.publish(vision_src.emit_detection("v1", [], 0))
    bus.publish(bench_src.emit_latency("b1", 10.0, 20.0, 60.0))

    receipt = {
        "bus_version": BUS_VERSION,
        "event_count": len(bus.events),
        "bus_root": bus.compute_bus_root(),
        "sources": list(set(e.source for e in bus.events)),
        "schemas": list(set(e.schema for e in bus.events)),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    assert receipt["event_count"] == 2
    assert len(receipt["bus_root"]) == 64
    assert "pc-vision" in receipt["sources"]
    assert "vscoder-benchmark" in receipt["sources"]
    return True


# --- Test Runner ---
def run_all_tests():
    """Run all 16 acceptance tests."""
    tests = [
        ("publish event", test_01_publish_event),
        ("verify bus", test_02_verify_bus),
        ("query by schema", test_03_query_by_schema),
        ("JSONL round-trip", test_04_jsonl_roundtrip),
        ("tampered event", test_05_tampered_event),
        ("malformed JSONL", test_06_malformed_jsonl),
        ("bus root", test_07_bus_root),
        ("decision gate flow", test_08_decision_gate_flow),
        ("evidence → grant", test_09_evidence_to_grant),
        ("evidence ≠ authority", test_10_evidence_not_authority),
        ("multi-source", test_11_multi_source),
        ("producer hash", test_12_producer_hash),
        ("payload hash", test_13_payload_hash),
        ("empty bus", test_14_empty_bus),
        ("cross-source query", test_15_cross_source_query),
        ("bus receipt", test_16_bus_receipt),
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

    print(f"\nPC://EVIDENCE — Acceptance Tests")
    print(f"{'=' * 50}")
    for r in results:
        print(r)
    print(f"{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED — PC://EVIDENCE_BUS_V1 FROZEN")
    else:
        print(f"\n✗ {failed} TESTS FAILED — DO NOT FREEZE BUS")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
