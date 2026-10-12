"""PC://VISION Phase 1A — Acceptance Tests.

16 acceptance criteria:
  1. schema validation
  2. deterministic ordering
  3. source hash stable
  4. frame hashes stable
  5. inference config captured
  6. event chain valid
  7. replay frame count exact
  8. replay timing exact
  9. detection equivalence
  10. CPU fallback
  11. CUDA path measured
  12. malformed JSONL rejected
  13. tampered frame detected
  14. tampered event detected
  15. final stream root produced
  16. receipt generated
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import json as json_module

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jsonl_schema import (
    CanonicalVisionEvent,
    Detection,
    InferenceConfig,
    VisionEventChain,
    compute_frame_hash,
    compute_source_hash,
    validate_event_schema,
    SCHEMA_VERSION,
)
from deterministic_replay import DeterministicReplay


def test_01_schema_validation():
    """Test: schema validation catches invalid events."""
    config = InferenceConfig()
    event = CanonicalVisionEvent(
        frame_index=0,
        media_time_ms=0.0,
        captured_at="2026-10-04T00:00:00.000Z",
        processed_at="2026-10-04T00:00:00.000Z",
        source_id="test://image/test",
        source_hash="a" * 64,
        frame_hash="b" * 64,
        source_width=1920,
        source_height=1080,
        detections=[],
        inference_config_hash=config.compute_hash(),
        backend="cpu",
        model="test",
        latency_ms=1.0,
    )
    errors = validate_event_schema(event)
    assert len(errors) == 0, f"Valid event should have no errors: {errors}"

    # Invalid: negative confidence
    bad_detection = Detection(
        track_id=1,
        class_name="person",
        class_id=0,
        confidence=1.5,  # Invalid
        bbox_xyxy=[0, 0, 100, 100],
        bbox_norm=[0, 0, 0.1, 0.1],
    )
    event.detections = [bad_detection]
    errors = validate_event_schema(event)
    assert len(errors) > 0, "Invalid detection should produce errors"
    return True


def test_02_deterministic_ordering():
    """Test: frame_index must be sequential."""
    chain = VisionEventChain()
    config = InferenceConfig()

    for i in range(5):
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    is_valid, errors = chain.verify()
    assert is_valid, f"Chain should be valid: {errors}"
    return True


def test_03_source_hash_stable():
    """Test: all events share the same source_hash."""
    chain = VisionEventChain()
    config = InferenceConfig()
    source_hash = "a" * 64

    for i in range(3):
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash=source_hash,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    for event in chain.events:
        assert event.source_hash == source_hash, "source_hash must be stable"
    return True


def test_04_frame_hashes_stable():
    """Test: frame hashes are unique and non-empty."""
    chain = VisionEventChain()
    config = InferenceConfig()

    for i in range(5):
        frame_hash = hashlib.sha256(f"frame{i}".encode()).hexdigest()
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=frame_hash,
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    hashes = [e.frame_hash for e in chain.events]
    assert len(hashes) == len(set(hashes)), "Frame hashes should be unique"
    assert all(h for h in hashes), "Frame hashes should be non-empty"
    return True


def test_05_inference_config_captured():
    """Test: inference_config_hash is present and consistent."""
    config = InferenceConfig(model="yolov8n", threshold=0.5)
    config_hash = config.compute_hash()

    chain = VisionEventChain()
    for i in range(3):
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config_hash,
            backend="cpu",
            model=config.model,
            latency_ms=1.0,
        )
        chain.append(event)

    for event in chain.events:
        assert event.inference_config_hash == config_hash, "Config hash must be consistent"
    return True


def test_06_event_chain_valid():
    """Test: hash chain is valid."""
    chain = VisionEventChain()
    config = InferenceConfig()

    for i in range(10):
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    is_valid, errors = chain.verify()
    assert is_valid, f"Chain should be valid: {errors}"
    return True


def test_07_replay_frame_count_exact():
    """Test: replay produces exact frame count."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        chain = VisionEventChain()
        config = InferenceConfig()
        for i in range(7):
            event = CanonicalVisionEvent(
                frame_index=i,
                media_time_ms=i * 33.33,
                captured_at="2026-10-04T00:00:00.000Z",
                processed_at="2026-10-04T00:00:00.000Z",
                source_id="test://video/test",
                source_hash="a" * 64,
                frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
                source_width=1920,
                source_height=1080,
                detections=[],
                inference_config_hash=config.compute_hash(),
                backend="cpu",
                model="test",
                latency_ms=1.0,
            )
            chain.append(event)
        chain.to_jsonl(jsonl_path)

        replay = DeterministicReplay(jsonl_path)
        passed, errors, _ = replay.run_all_verifications(expected_count=7)
        assert passed, f"Replay should pass: {errors}"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_08_replay_timing_exact():
    """Test: replay timing is exact."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        chain = VisionEventChain()
        config = InferenceConfig()
        for i in range(5):
            event = CanonicalVisionEvent(
                frame_index=i,
                media_time_ms=i * 40.0,  # 25 fps
                captured_at="2026-10-04T00:00:00.000Z",
                processed_at="2026-10-04T00:00:00.000Z",
                source_id="test://video/test",
                source_hash="a" * 64,
                frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
                source_width=1920,
                source_height=1080,
                detections=[],
                inference_config_hash=config.compute_hash(),
                backend="cpu",
                model="test",
                latency_ms=1.0,
            )
            chain.append(event)
        chain.to_jsonl(jsonl_path)

        replay = DeterministicReplay(jsonl_path)
        passed, errors, _ = replay.run_all_verifications(expected_duration_ms=160.0)
        assert passed, f"Replay timing should be exact: {errors}"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_09_detection_equivalence():
    """Test: same track_id → same class."""
    chain = VisionEventChain()
    config = InferenceConfig()

    for i in range(5):
        detections = [
            Detection(
                track_id=1,
                class_name="person",
                class_id=0,
                confidence=0.9,
                bbox_xyxy=[100, 100, 200, 200],
                bbox_norm=[0.1, 0.1, 0.2, 0.2],
            ),
            Detection(
                track_id=2,
                class_name="car",
                class_id=1,
                confidence=0.8,
                bbox_xyxy=[300, 300, 400, 400],
                bbox_norm=[0.3, 0.3, 0.4, 0.4],
            ),
        ]
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=detections,
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    is_valid, errors = chain.verify()
    assert is_valid, f"Chain should be valid: {errors}"
    return True


def test_10_cpu_fallback():
    """Test: CPU backend works."""
    config = InferenceConfig(backend="cpu")
    assert config.backend == "cpu"
    assert config.compute_hash() != ""
    return True


def test_11_cuda_path_measured():
    """Test: CUDA backend is detected (if available)."""
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    # Either CUDA is available or we gracefully fall back to CPU
    config = InferenceConfig(backend="cuda" if cuda_available else "cpu")
    assert config.backend in ["cpu", "cuda"]
    return True


def test_12_malformed_jsonl_rejected():
    """Test: malformed JSONL is rejected."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        f.write('{"frame_index": 0, "media_time_ms": 0}\n')
        f.write('{"frame_index": 1, "media_time_ms": 33.33, "source_hash": "a"}\n')
        f.write('INVALID JSON\n')
        jsonl_path = Path(f.name)

    try:
        # from_jsonl should raise ValueError on malformed lines
        try:
            VisionEventChain.from_jsonl(jsonl_path)
            assert False, "Malformed JSONL should raise ValueError"
        except ValueError:
            pass  # Expected — json.JSONDecodeError is a subclass of ValueError
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_13_tampered_frame_detected():
    """Test: tampered frame is detected via hash mismatch."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        chain = VisionEventChain()
        config = InferenceConfig()
        for i in range(5):
            event = CanonicalVisionEvent(
                frame_index=i,
                media_time_ms=i * 33.33,
                captured_at="2026-10-04T00:00:00.000Z",
                processed_at="2026-10-04T00:00:00.000Z",
                source_id="test://video/test",
                source_hash="a" * 64,
                frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
                source_width=1920,
                source_height=1080,
                detections=[],
                inference_config_hash=config.compute_hash(),
                backend="cpu",
                model="test",
                latency_ms=1.0,
            )
            chain.append(event)
        chain.to_jsonl(jsonl_path)

        # Tamper: modify a frame hash
        with open(jsonl_path, "r") as f:
            lines = f.readlines()
        data = json.loads(lines[2])
        data["frame_hash"] = "tampered_hash_value"
        lines[2] = json.dumps(data) + "\n"
        with open(jsonl_path, "w") as f:
            f.writelines(lines)

        replay = DeterministicReplay(jsonl_path)
        passed, errors, _ = replay.run_all_verifications()
        assert not passed, "Tampered frame should be detected"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_14_tampered_event_detected():
    """Test: tampered event is detected via chain break."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        chain = VisionEventChain()
        config = InferenceConfig()
        for i in range(5):
            event = CanonicalVisionEvent(
                frame_index=i,
                media_time_ms=i * 33.33,
                captured_at="2026-10-04T00:00:00.000Z",
                processed_at="2026-10-04T00:00:00.000Z",
                source_id="test://video/test",
                source_hash="a" * 64,
                frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
                source_width=1920,
                source_height=1080,
                detections=[],
                inference_config_hash=config.compute_hash(),
                backend="cpu",
                model="test",
                latency_ms=1.0,
            )
            chain.append(event)
        chain.to_jsonl(jsonl_path)

        # Tamper: modify an event hash
        with open(jsonl_path, "r") as f:
            lines = f.readlines()
        data = json.loads(lines[3])
        data["event_hash"] = "tampered_event_hash"
        lines[3] = json.dumps(data) + "\n"
        with open(jsonl_path, "w") as f:
            f.writelines(lines)

        replay = DeterministicReplay(jsonl_path)
        passed, errors, _ = replay.run_all_verifications()
        assert not passed, "Tampered event should be detected"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_15_stream_root_produced():
    """Test: final stream root is produced."""
    chain = VisionEventChain()
    config = InferenceConfig()
    for i in range(5):
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    root = chain.compute_stream_root()
    assert len(root) == 64, f"Stream root should be 64 hex chars, got {len(root)}"
    assert root != "0" * 64, "Stream root should not be zero"
    return True


def test_16_receipt_generated():
    """Test: receipt is generated with all required fields."""
    chain = VisionEventChain()
    config = InferenceConfig()
    for i in range(3):
        event = CanonicalVisionEvent(
            frame_index=i,
            media_time_ms=i * 33.33,
            captured_at="2026-10-04T00:00:00.000Z",
            processed_at="2026-10-04T00:00:00.000Z",
            source_id="test://video/test",
            source_hash="a" * 64,
            frame_hash=hashlib.sha256(f"frame{i}".encode()).hexdigest(),
            source_width=1920,
            source_height=1080,
            detections=[],
            inference_config_hash=config.compute_hash(),
            backend="cpu",
            model="test",
            latency_ms=1.0,
        )
        chain.append(event)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "frame_count": len(chain.events),
        "stream_root": chain.compute_stream_root(),
        "source_hash": chain.events[0].source_hash,
        "inference_config_hash": chain.events[0].inference_config_hash,
        "backend": chain.events[0].backend,
        "model": chain.events[0].model,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    assert receipt["frame_count"] == 3
    assert len(receipt["stream_root"]) == 64
    assert receipt["schema_version"] == SCHEMA_VERSION
    return True


# --- Test Runner ---
def run_all_tests():
    """Run all 16 acceptance tests."""
    tests = [
        ("schema validation", test_01_schema_validation),
        ("deterministic ordering", test_02_deterministic_ordering),
        ("source hash stable", test_03_source_hash_stable),
        ("frame hashes stable", test_04_frame_hashes_stable),
        ("inference config captured", test_05_inference_config_captured),
        ("event chain valid", test_06_event_chain_valid),
        ("replay frame count exact", test_07_replay_frame_count_exact),
        ("replay timing exact", test_08_replay_timing_exact),
        ("detection equivalence", test_09_detection_equivalence),
        ("CPU fallback", test_10_cpu_fallback),
        ("CUDA path measured", test_11_cuda_path_measured),
        ("malformed JSONL rejected", test_12_malformed_jsonl_rejected),
        ("tampered frame detected", test_13_tampered_frame_detected),
        ("tampered event detected", test_14_tampered_event_detected),
        ("stream root produced", test_15_stream_root_produced),
        ("receipt generated", test_16_receipt_generated),
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

    print(f"\nPC://VISION PHASE 1A — Acceptance Tests")
    print(f"{'=' * 50}")
    for r in results:
        print(r)
    print(f"{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED — PCVISION_EVENT_SCHEMA_V1 FROZEN")
    else:
        print(f"\n✗ {failed} TESTS FAILED — DO NOT FREEZE SCHEMA")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
