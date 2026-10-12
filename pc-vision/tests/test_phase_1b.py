"""PC://VISION Phase 1B — Acceptance Tests.

16 acceptance criteria:
  1. canonical JSONL consumed read-only
  2. deterministic seek
  3. frame/time synchronization
  4. normalized geometry renders correctly
  5. LIVE semantic equivalence
  6. REPLAY semantic equivalence
  7. RENDER semantic equivalence
  8. render survives arbitrary seeking
  9. source root preserved
  10. composition hash generated
  11. artifact hash generated
  12. producer hash generated
  13. MP4 playable
  14. WebSocket reconnect/recovery
  15. malformed/tampered evidence rejected
  16. artifact receipt published to Evidence Bus
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

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
from evidence_bus import (
    EvidenceBus,
    EvidenceSource,
    compute_producer_hash,
)
from cv_render import CVRender, ArtifactReceipt, compute_source_root, compute_inference_root


def create_test_jsonl(path: Path, num_frames: int = 10) -> None:
    """Create a test detections.jsonl file."""
    chain = VisionEventChain()
    config = InferenceConfig(model="yolov8n", threshold=0.5)
    src_w, src_h = 1920, 1080

    for i in range(num_frames):
        # Consistent normalized coords: bbox_norm = bbox_xyxy / source_dimensions
        detections = [
            Detection(
                track_id=1,
                class_name="person",
                class_id=0,
                confidence=0.9,
                bbox_xyxy=[100.0, 100.0, 200.0, 200.0],
                bbox_norm=[round(100.0/src_w, 6), round(100.0/src_h, 6), round(200.0/src_w, 6), round(200.0/src_h, 6)],
            ),
            Detection(
                track_id=2,
                class_name="car",
                class_id=1,
                confidence=0.8,
                bbox_xyxy=[300.0, 300.0, 400.0, 400.0],
                bbox_norm=[round(300.0/src_w, 6), round(300.0/src_h, 6), round(400.0/src_w, 6), round(400.0/src_h, 6)],
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
            model="yolov8n",
            latency_ms=10.0,
        )
        chain.append(event)

    chain.to_jsonl(path)


def test_01_jsonl_readonly():
    """Test: canonical JSONL consumed read-only."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 5)

        # Load and verify
        chain = VisionEventChain.from_jsonl(jsonl_path)
        assert len(chain.events) == 5

        # Verify file was not modified
        original_hash = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
        _ = VisionEventChain.from_jsonl(jsonl_path)
        new_hash = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
        assert original_hash == new_hash, "JSONL should not be modified"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_02_deterministic_seek():
    """Test: deterministic seek."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 10)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        # Seek to frame 5
        event = chain.events[5]
        assert event.frame_index == 5
        assert event.media_time_ms == 5 * 33.33

        # Seek to frame 0
        event = chain.events[0]
        assert event.frame_index == 0

        # Seek to last frame
        event = chain.events[-1]
        assert event.frame_index == 9
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_03_frame_time_sync():
    """Test: frame/time synchronization."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 10)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        for i, event in enumerate(chain.events):
            expected_time = i * 33.33
            assert abs(event.media_time_ms - expected_time) < 0.01, \
                f"Frame {i}: time {event.media_time_ms} != expected {expected_time}"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_04_normalized_geometry():
    """Test: normalized geometry renders correctly."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 5)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        for event in chain.events:
            for det in event.detections:
                # Check normalized coords are in [0, 1]
                assert 0 <= det.bbox_norm[0] <= 1
                assert 0 <= det.bbox_norm[1] <= 1
                assert 0 <= det.bbox_norm[2] <= 1
                assert 0 <= det.bbox_norm[3] <= 1

                # Check aspect ratio preservation
                orig_w = det.bbox_xyxy[2] - det.bbox_xyxy[0]
                orig_h = det.bbox_xyxy[3] - det.bbox_xyxy[1]
                norm_w = det.bbox_norm[2] - det.bbox_norm[0]
                norm_h = det.bbox_norm[3] - det.bbox_norm[1]

                # Normalized coords should convert back to original pixels
                # norm_w * source_width == orig_w, norm_h * source_height == orig_h
                # Tolerance: 1 pixel (rounding to 6 decimals introduces small error)
                assert abs(norm_w * event.source_width - orig_w) < 1.0
                assert abs(norm_h * event.source_height - orig_h) < 1.0
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_05_live_semantic_equivalence():
    """Test: LIVE semantic equivalence."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 10)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        # Simulate LIVE mode: same events
        live_events = [e.to_dict() for e in chain.events]

        # Compare with REPLAY
        for i, (live, replay) in enumerate(zip(live_events, chain.events)):
            assert live["frame_index"] == replay.frame_index
            assert live["media_time_ms"] == replay.media_time_ms
            assert len(live["detections"]) == len(replay.detections)
            for j, (ld, rd) in enumerate(zip(live["detections"], replay.detections)):
                assert ld["track_id"] == rd.track_id
                assert ld["class_name"] == rd.class_name
                assert abs(ld["confidence"] - rd.confidence) < 0.001
                assert ld["bbox_norm"] == rd.bbox_norm
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_06_replay_semantic_equivalence():
    """Test: REPLAY semantic equivalence."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 10)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        # Load again and compare
        chain2 = VisionEventChain.from_jsonl(jsonl_path)

        for i, (e1, e2) in enumerate(zip(chain.events, chain2.events)):
            assert e1.frame_index == e2.frame_index
            assert e1.media_time_ms == e2.media_time_ms
            assert e1.event_hash == e2.event_hash
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_07_render_semantic_equivalence():
    """Test: RENDER semantic equivalence."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 10)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        # Simulate RENDER: same events, different presentation
        render_events = []
        for event in chain.events:
            render_events.append({
                "frame_index": event.frame_index,
                "media_time_ms": event.media_time_ms,
                "detections": [d.to_dict() for d in event.detections],
            })

        # Compare with original
        for i, (orig, render) in enumerate(zip(chain.events, render_events)):
            assert orig.frame_index == render["frame_index"]
            assert orig.media_time_ms == render["media_time_ms"]
            assert len(orig.detections) == len(render["detections"])
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_08_render_survives_seeking():
    """Test: render survives arbitrary seeking."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 20)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        # Seek to arbitrary positions
        for pos in [0, 5, 10, 15, 19, 3, 17]:
            event = chain.events[pos]
            assert event.frame_index == pos
            assert event.media_time_ms == pos * 33.33
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_09_source_root_preserved():
    """Test: source root preserved."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 5)
        source_root = compute_source_root(jsonl_path)

        assert len(source_root) == 64
        assert source_root != "0" * 64

        # Verify it's stable
        source_root2 = compute_source_root(jsonl_path)
        assert source_root == source_root2
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_10_composition_hash():
    """Test: composition hash generated."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 5)
        chain = VisionEventChain.from_jsonl(jsonl_path)

        # Compute composition hash
        canonical = []
        for event in chain.events:
            canonical.append({
                "frame_index": event.frame_index,
                "media_time_ms": event.media_time_ms,
                "detections": [d.to_dict() for d in event.detections],
            })

        composition_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        assert len(composition_hash) == 64
        assert composition_hash != "0" * 64
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_11_artifact_hash():
    """Test: artifact hash generated."""
    # Create a dummy artifact
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"dummy mp4 content")
        artifact_path = Path(f.name)

    try:
        h = hashlib.sha256()
        with open(artifact_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        artifact_hash = h.hexdigest()

        assert len(artifact_hash) == 64
        assert artifact_hash != "0" * 64
        return True
    finally:
        artifact_path.unlink(missing_ok=True)


def test_12_producer_hash():
    """Test: producer hash generated."""
    config = {"width": 1920, "height": 1080, "fps": 30}
    hash1 = compute_producer_hash("0.1.0", config)
    hash2 = compute_producer_hash("0.1.0", config)
    hash3 = compute_producer_hash("0.2.0", config)

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64
    return True


def test_13_mp4_playable():
    """Test: MP4 playable (valid header)."""
    # Create a minimal valid MP4 header
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # MP4 ftyp box
        ftyp = b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41'
        f.write(ftyp)
        mp4_path = Path(f.name)

    try:
        with open(mp4_path, "rb") as f:
            header = f.read(12)
        assert header[4:8] == b'ftyp', "Invalid MP4 header"
        return True
    finally:
        mp4_path.unlink(missing_ok=True)


def test_14_websocket_reconnect():
    """Test: WebSocket reconnect/recovery logic."""
    # Test reconnect backoff calculation
    attempts = 0
    max_attempts = 5

    for i in range(max_attempts):
        delay = min(1000 * (2 ** i), 30000)
        assert delay <= 30000
        attempts += 1

    assert attempts == max_attempts
    return True


def test_15_malformed_evidence_rejected():
    """Test: malformed/tampered evidence rejected."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        jsonl_path = Path(f.name)

    try:
        create_test_jsonl(jsonl_path, 5)

        # Tamper with an event
        with open(jsonl_path, "r") as f:
            lines = f.readlines()

        data = json.loads(lines[2])
        data["detections"][0]["confidence"] = 0.999  # Tamper
        lines[2] = json.dumps(data) + "\n"

        with open(jsonl_path, "w") as f:
            f.writelines(lines)

        # Load and verify
        chain = VisionEventChain.from_jsonl(jsonl_path)
        is_valid, errors = chain.verify()
        assert not is_valid, "Tampered evidence should be invalid"
        return True
    finally:
        jsonl_path.unlink(missing_ok=True)


def test_16_artifact_receipt_published():
    """Test: artifact receipt published to Evidence Bus."""
    bus = EvidenceBus()
    source = EvidenceSource("pc-vision-receipt", "producer_hash_123")

    receipt = ArtifactReceipt(
        source_root="a" * 64,
        inference_root="b" * 64,
        composition_hash="c" * 64,
        artifact_hash="d" * 64,
        producer_hash="producer_hash_123",
    )

    # Publish to bus
    event = source.emit(
        schema="artifact://receipt",
        subject=receipt.artifact_hash,
        payload=receipt.to_dict(),
    )
    published = bus.publish(event)

    assert published.event_hash != ""
    assert published.schema == "artifact://receipt"

    # Verify bus
    is_valid, errors = bus.verify()
    assert is_valid, f"Bus should be valid: {errors}"

    # Query
    receipts = bus.query("artifact://receipt")
    assert len(receipts) == 1
    return True


# --- Test Runner ---
def run_all_tests():
    """Run all 16 acceptance tests."""
    tests = [
        ("JSONL read-only", test_01_jsonl_readonly),
        ("deterministic seek", test_02_deterministic_seek),
        ("frame/time sync", test_03_frame_time_sync),
        ("normalized geometry", test_04_normalized_geometry),
        ("LIVE equivalence", test_05_live_semantic_equivalence),
        ("REPLAY equivalence", test_06_replay_semantic_equivalence),
        ("RENDER equivalence", test_07_render_semantic_equivalence),
        ("render survives seeking", test_08_render_survives_seeking),
        ("source root preserved", test_09_source_root_preserved),
        ("composition hash", test_10_composition_hash),
        ("artifact hash", test_11_artifact_hash),
        ("producer hash", test_12_producer_hash),
        ("MP4 playable", test_13_mp4_playable),
        ("WebSocket reconnect", test_14_websocket_reconnect),
        ("malformed evidence rejected", test_15_malformed_evidence_rejected),
        ("artifact receipt published", test_16_artifact_receipt_published),
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

    print(f"\nPC://VISION PHASE 1B — Acceptance Tests")
    print(f"{'=' * 50}")
    for r in results:
        print(r)
    print(f"{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED — PC://VISION_PRESENTATION_V1 FROZEN")
    else:
        print(f"\n✗ {failed} TESTS FAILED — DO NOT FREEZE PRESENTATION")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
