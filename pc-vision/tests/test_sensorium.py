"""PC://SENSORIUM — Acceptance Tests.

16 acceptance criteria:
  1. 4 invariantes en código
  2. System sensor produce lectura
  3. System reading tiene todos los campos
  4. Audio sensor produce lectura
  5. Sensorium publica a Evidence Bus
  6. Multi-sensor (system + audio)
  7. Instrument panel produce datos
  8. Vision data en panel
  9. System data en panel
  10. Evidence data en panel
  11. Authority data en panel (observation only)
  12. Invariante: Evidence ≠ Authority
  13. Invariante: Observation ≠ Decision
  14. Invariante: Presentation ≠ Truth
  15. Invariante: Capability ≠ Permission
  16. Sensorium receipt
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_bus import EvidenceBus, EvidenceEvent, EvidenceSource, compute_producer_hash
from sensorium import (
    SENSORIUM_VERSION,
    AudioSensor,
    AudioReading,
    InstrumentPanel,
    Invariantes,
    Sensorium,
    SystemSensor,
    SystemReading,
)


def test_01_invariantes():
    """Test: 4 invariantes en código."""
    invariants = Invariantes.all()
    assert len(invariants) == 4
    assert "Observation ≠ Decision" in invariants
    assert "Evidence ≠ Authority" in invariants
    assert "Presentation ≠ Truth" in invariants
    assert "Capability ≠ Permission" in invariants
    return True


def test_02_system_sensor():
    """Test: System sensor produce lectura."""
    sensor = SystemSensor()
    reading = sensor.read()

    assert reading.timestamp != ""
    assert reading.cpu_percent >= 0
    assert reading.ram_total_gb > 0
    assert reading.ram_percent >= 0
    return True


def test_03_system_reading_fields():
    """Test: System reading tiene todos los campos."""
    sensor = SystemSensor()
    reading = sensor.read()
    d = reading.to_dict()

    required = [
        "timestamp", "cpu_percent", "cpu_freq_mhz",
        "ram_total_gb", "ram_used_gb", "ram_percent",
        "gpu_name", "gpu_temp_c", "gpu_util_percent",
        "gpu_vram_used_mb", "gpu_vram_total_mb",
        "process_count", "network_sent_mb", "network_recv_mb",
    ]

    for field in required:
        assert field in d, f"Missing field: {field}"
    return True


def test_04_audio_sensor():
    """Test: Audio sensor produce lectura."""
    sensor = AudioSensor()
    event = sensor.emit()

    assert event.schema == "audio://reading"
    assert event.source == "pc-sensorium-audio"
    assert event.payload["timestamp"] != ""
    return True


def test_05_sensorium_publishes():
    """Test: Sensorium publica a Evidence Bus."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)

    event = sensorium.observe_system()

    assert event.schema == "system://reading"
    assert event.source == "pc-sensorium-system"
    assert len(bus.events) == 1
    return True


def test_06_multi_sensor():
    """Test: Multi-sensor (system + audio)."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)

    events = sensorium.observe_all()

    assert len(events) == 2
    assert len(bus.events) == 2

    schemas = [e.schema for e in bus.events]
    assert "system://reading" in schemas
    assert "audio://reading" in schemas
    return True


def test_07_instrument_panel():
    """Test: Instrument panel produce datos."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_all()

    panel = InstrumentPanel(bus)
    data = panel.get_panel_data()

    assert "sensorium" in data
    assert "vision" in data
    assert "system" in data
    assert "evidence" in data
    assert "authority" in data
    return True


def test_08_vision_data():
    """Test: Vision data en panel."""
    bus = EvidenceBus()
    panel = InstrumentPanel(bus)

    data = panel.get_panel_data()
    vision = data["vision"]

    # No vision data yet
    assert vision["status"] == "no_data"
    return True


def test_09_system_data():
    """Test: System data en panel."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_system()

    panel = InstrumentPanel(bus)
    data = panel.get_panel_data()
    system = data["system"]

    assert system["status"] == "active"
    assert "cpu_percent" in system
    assert "ram_percent" in system
    return True


def test_10_evidence_data():
    """Test: Evidence data en panel."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_all()

    panel = InstrumentPanel(bus)
    data = panel.get_panel_data()
    evidence = data["evidence"]

    assert evidence["event_count"] == 2
    assert len(evidence["bus_root"]) == 64
    assert "system://reading" in evidence["schemas"]
    return True


def test_11_authority_data():
    """Test: Authority data en panel (observation only)."""
    bus = EvidenceBus()
    panel = InstrumentPanel(bus)

    data = panel.get_panel_data()
    authority = data["authority"]

    assert authority["policy"] == "PC://LOCAL"
    assert authority["consequential_grants"] == "NONE"
    assert authority["human_root"] == "🧿"
    return True


def test_12_evidence_not_authority():
    """Test: Invariante Evidence ≠ Authority."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_system()

    # Evidence events never contain authority
    for event in bus.events:
        assert not event.schema.startswith("authority://"), \
            "Evidence bus should not contain authority events"
        assert "grant" not in event.payload or not event.schema.startswith("evidence://"), \
            "Evidence events should not contain grants"
    return True


def test_13_observation_not_decision():
    """Test: Invariante Observation ≠ Decision."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_system()

    # Observation events never contain decisions
    for event in bus.events:
        assert "decision" not in event.payload, \
            "Observation events should not contain decisions"
        assert "grant_id" not in event.payload, \
            "Observation events should not contain grant IDs"
    return True


def test_14_presentation_not_truth():
    """Test: Invariante Presentation ≠ Truth."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_system()

    # Presentation events (if any) don't modify truth
    truth_schemas = ["vision://detection", "system://reading", "audio://reading"]
    for event in bus.events:
        if event.schema.startswith("presentation://"):
            # Presentation events should reference truth, not replace it
            assert "source_hash" in event.payload or "reference" in event.payload
    return True


def test_15_capability_not_permission():
    """Test: Invariante Capability ≠ Permission."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_system()

    # Having a sensor (capability) doesn't grant permission
    # Permission comes from HUMAN://ROOT via DecisionGate
    for event in bus.events:
        assert "permission" not in event.payload, \
            "Capability events should not contain permissions"
    return True


def test_16_sensorium_receipt():
    """Test: Sensorium receipt."""
    bus = EvidenceBus()
    sensorium = Sensorium(bus)
    sensorium.observe_all()

    receipt = {
        "schema": "sensorium://receipt",
        "sensorium_version": SENSORIUM_VERSION,
        "event_count": len(bus.events),
        "bus_root": bus.compute_bus_root(),
        "invariants": Invariantes.all(),
        "sensors": ["system", "audio"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    assert receipt["event_count"] == 2
    assert len(receipt["bus_root"]) == 64
    assert len(receipt["invariants"]) == 4
    return True


# --- Test Runner ---
def run_all_tests():
    """Run all 16 acceptance tests."""
    tests = [
        ("4 invariantes", test_01_invariantes),
        ("system sensor", test_02_system_sensor),
        ("system reading fields", test_03_system_reading_fields),
        ("audio sensor", test_04_audio_sensor),
        ("sensorium publishes", test_05_sensorium_publishes),
        ("multi-sensor", test_06_multi_sensor),
        ("instrument panel", test_07_instrument_panel),
        ("vision data", test_08_vision_data),
        ("system data", test_09_system_data),
        ("evidence data", test_10_evidence_data),
        ("authority data", test_11_authority_data),
        ("Evidence ≠ Authority", test_12_evidence_not_authority),
        ("Observation ≠ Decision", test_13_observation_not_decision),
        ("Presentation ≠ Truth", test_14_presentation_not_truth),
        ("Capability ≠ Permission", test_15_capability_not_permission),
        ("sensorium receipt", test_16_sensorium_receipt),
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

    print(f"\nPC://SENSORIUM — Acceptance Tests")
    print(f"{'=' * 50}")
    for r in results:
        print(r)
    print(f"{'=' * 50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED — PC://SENSORIUM_V1 FROZEN")
    else:
        print(f"\n✗ {failed} TESTS FAILED — DO NOT FREEZE SENSORIUM")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
