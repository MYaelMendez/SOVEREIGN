"""PC://VISION — Canonical Vision Event Schema V1.

Define el contrato inmutable de evidencia para el motor de visión.
Cada evento es un eslabón en una hash chain verificable.

PCVISION_EVENT_SCHEMA_V1
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --- Constants ---
SCHEMA_VERSION = "PCVISION_EVENT_SCHEMA_V1"
STREAM_ROOT_VERSION = "PCVISION_STREAM_ROOT_V1"


# --- Data Classes ---
@dataclass
class InferenceConfig:
    """Configuración de inferencia — mismo frame + config diferente ≠ mismo experimento."""
    model: str = "yolov8n"
    model_hash: str = ""
    model_version: str = ""
    threshold: float = 0.5
    iou_threshold: float = 0.5
    tracker: str = "bytetrack"
    tracker_config: Dict[str, Any] = field(default_factory=dict)
    input_size: Tuple[int, int] = (640, 640)
    backend: str = "cpu"
    precision: str = "fp32"
    code_version: str = "0.1.0"

    def compute_hash(self) -> str:
        """Hash canónico de la configuración de inferencia."""
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class Detection:
    """Detección individual con coordenadas normalizadas y originales."""
    track_id: int
    class_name: str
    class_id: int
    confidence: float
    bbox_xyxy: List[float]  # [x1, y1, x2, y2] en píxeles originales
    bbox_norm: List[float]  # [x1_norm, y1_norm, x2_norm, y2_norm] normalizado 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "class_id": self.class_id,
            "confidence": round(self.confidence, 6),
            "bbox_xyxy": [round(v, 2) for v in self.bbox_xyxy],
            "bbox_norm": [round(v, 6) for v in self.bbox_norm],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Detection:
        return cls(
            track_id=d["track_id"],
            class_name=d["class_name"],
            class_id=d["class_id"],
            confidence=d["confidence"],
            bbox_xyxy=d["bbox_xyxy"],
            bbox_norm=d["bbox_norm"],
        )


@dataclass
class CanonicalVisionEvent:
    """Evento canónico de visión — eslabón en la hash chain.

    Tres tiempos:
      - frame_index: orden determinista
      - media_time_ms: tiempo en el medio (determina replay)
      - captured_at: cuándo se capturó el frame
      - processed_at: cuándo se procesó

    Hash chain:
      E_n = SHA256(E_{n-1} || FrameHash_n || CanonicalDetections_n || InferenceConfigHash)
    """
    frame_index: int
    media_time_ms: float
    captured_at: str
    processed_at: str
    source_id: str
    source_hash: str
    frame_hash: str
    source_width: int
    source_height: int
    detections: List[Detection]
    inference_config_hash: str
    backend: str
    model: str
    latency_ms: float
    prev_event_hash: str = ""
    event_hash: str = ""

    def compute_event_hash(self) -> str:
        """Compute this event's hash from its content + previous event hash."""
        canonical = {
            "frame_index": self.frame_index,
            "media_time_ms": self.media_time_ms,
            "captured_at": self.captured_at,
            "processed_at": self.processed_at,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "frame_hash": self.frame_hash,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "detections": [d.to_dict() for d in self.detections],
            "inference_config_hash": self.inference_config_hash,
            "backend": self.backend,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 3),
            "prev_event_hash": self.prev_event_hash,
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def finalize(self) -> CanonicalVisionEvent:
        """Compute and set this event's hash."""
        self.event_hash = self.compute_event_hash()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "frame_index": self.frame_index,
            "media_time_ms": self.media_time_ms,
            "captured_at": self.captured_at,
            "processed_at": self.processed_at,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "frame_hash": self.frame_hash,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "detections": [d.to_dict() for d in self.detections],
            "inference_config_hash": self.inference_config_hash,
            "backend": self.backend,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 3),
            "prev_event_hash": self.prev_event_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CanonicalVisionEvent:
        return cls(
            frame_index=d["frame_index"],
            media_time_ms=d["media_time_ms"],
            captured_at=d["captured_at"],
            processed_at=d["processed_at"],
            source_id=d["source_id"],
            source_hash=d["source_hash"],
            frame_hash=d["frame_hash"],
            source_width=d["source_width"],
            source_height=d["source_height"],
            detections=[Detection.from_dict(dd) for dd in d["detections"]],
            inference_config_hash=d["inference_config_hash"],
            backend=d["backend"],
            model=d["model"],
            latency_ms=d["latency_ms"],
            prev_event_hash=d.get("prev_event_hash", ""),
            event_hash=d.get("event_hash", ""),
        )


# --- Hash Chain ---
class VisionEventChain:
    """Hash chain de eventos de visión — secuencia verificable."""

    def __init__(self):
        self.events: List[CanonicalVisionEvent] = []
        self.genesis_hash: str = hashlib.sha256(b"PCVISION_GENESIS").hexdigest()

    def append(self, event: CanonicalVisionEvent) -> CanonicalVisionEvent:
        """Append an event to the chain, computing its hash."""
        if not self.events:
            event.prev_event_hash = self.genesis_hash
        else:
            event.prev_event_hash = self.events[-1].event_hash
        event.finalize()
        self.events.append(event)
        return event

    def verify(self) -> Tuple[bool, List[str]]:
        """Verify the entire chain. Returns (is_valid, list_of_errors)."""
        errors = []
        prev_hash = self.genesis_hash

        for i, event in enumerate(self.events):
            # Check ordering
            if event.frame_index != i:
                errors.append(f"Frame {i}: frame_index={event.frame_index} (expected {i})")

            # Check prev_event_hash
            if event.prev_event_hash != prev_hash:
                errors.append(f"Frame {i}: prev_event_hash mismatch")

            # Recompute event hash
            recomputed = event.compute_event_hash()
            if recomputed != event.event_hash:
                errors.append(f"Frame {i}: event_hash mismatch (tampered?)")

            prev_hash = event.event_hash

        return len(errors) == 0, errors

    def compute_stream_root(self) -> str:
        """Compute the Merkle-like root of the entire stream."""
        if not self.events:
            return hashlib.sha256(b"PCVISION_EMPTY_STREAM").hexdigest()

        # Build Merkle tree from event hashes
        hashes = [e.event_hash for e in self.events]
        while len(hashes) > 1:
            next_level = []
            for i in range(0, len(hashes), 2):
                left = hashes[i]
                right = hashes[i + 1] if i + 1 < len(hashes) else left
                combined = hashlib.sha256((left + right).encode()).hexdigest()
                next_level.append(combined)
            hashes = next_level

        # Final root includes stream metadata
        root_payload = f"{STREAM_ROOT_VERSION}:{len(self.events)}:{hashes[0]}"
        return hashlib.sha256(root_payload.encode()).hexdigest()

    def to_jsonl(self, path: Path) -> None:
        """Write the chain to a JSONL file."""
        with open(path, "w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(event.to_dict(), separators=(",", ":")) + "\n")

    @classmethod
    def from_jsonl(cls, path: Path) -> VisionEventChain:
        """Load a chain from a JSONL file. Raises ValueError on malformed lines."""
        chain = cls()
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
                    event = CanonicalVisionEvent.from_dict(data)
                except (KeyError, TypeError) as e:
                    raise ValueError(f"Line {line_num}: missing or invalid field: {e}")
                chain.events.append(event)
        return chain


# --- Validation ---
def validate_event_schema(event: CanonicalVisionEvent) -> List[str]:
    """Validate an event against the schema. Returns list of errors."""
    errors = []

    if event.frame_index < 0:
        errors.append(f"frame_index must be >= 0, got {event.frame_index}")

    if event.media_time_ms < 0:
        errors.append(f"media_time_ms must be >= 0, got {event.media_time_ms}")

    if event.source_width <= 0 or event.source_height <= 0:
        errors.append(f"Invalid source dimensions: {event.source_width}x{event.source_height}")

    if not event.source_hash:
        errors.append("source_hash is required")

    if not event.frame_hash:
        errors.append("frame_hash is required")

    if not event.inference_config_hash:
        errors.append("inference_config_hash is required")

    for i, det in enumerate(event.detections):
        if det.confidence < 0 or det.confidence > 1:
            errors.append(f"Detection {i}: confidence {det.confidence} out of [0,1]")
        if len(det.bbox_xyxy) != 4:
            errors.append(f"Detection {i}: bbox_xyxy must have 4 values")
        if len(det.bbox_norm) != 4:
            errors.append(f"Detection {i}: bbox_norm must have 4 values")
        if det.bbox_norm[0] < 0 or det.bbox_norm[2] > 1:
            errors.append(f"Detection {i}: bbox_norm x out of [0,1]")
        if det.bbox_norm[1] < 0 or det.bbox_norm[3] > 1:
            errors.append(f"Detection {i}: bbox_norm y out of [0,1]")

    return errors


def compute_frame_hash(frame_bytes: bytes) -> str:
    """Compute SHA-256 hash of a frame's raw bytes."""
    return hashlib.sha256(frame_bytes).hexdigest()


def compute_source_hash(source_path: Path) -> str:
    """Compute SHA-256 hash of a source file."""
    h = hashlib.sha256()
    with open(source_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
