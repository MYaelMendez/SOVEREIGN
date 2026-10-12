"""PC://VISION — Render Pipeline.

Chrome headless → MP4 artifact.
Consumes composition.html + detections.jsonl.
Produces artifact.mp4 + artifact_hash.

PC://VISION_PRESENTATION_V1
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from evidence_bus import EvidenceBus, EvidenceEvent, EvidenceSource, compute_producer_hash


# --- Config ---
_CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
_FFMPEG = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe"
_DEFAULT_WIDTH = 1920
_DEFAULT_HEIGHT = 1080
_DEFAULT_FPS = 30
_DEFAULT_DURATION = 10


class CVRender:
    """Render pipeline — composition.html → artifact.mp4.

    Steps:
      1. Load composition.html
      2. Chrome headless → PNG frames
      3. ffmpeg → MP4
      4. Compute artifact_hash
      5. Publish artifact://render to Evidence Bus
    """

    def __init__(
        self,
        composition_path: Path,
        output_dir: Path,
        width: int = _DEFAULT_WIDTH,
        height: int = _DEFAULT_HEIGHT,
        fps: int = _DEFAULT_FPS,
        duration: int = _DEFAULT_DURATION,
    ):
        self.composition_path = Path(composition_path)
        self.output_dir = Path(output_dir)
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = duration
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Producer hash
        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config={
                "width": width,
                "height": height,
                "fps": fps,
                "duration": duration,
            },
        )

    def render(self) -> Dict[str, Any]:
        """Render composition to MP4 and return artifact info."""
        # Step 1: Chrome headless → PNG
        png_path = self.output_dir / "frame.png"
        self._chrome_screenshot(png_path)

        # Step 2: ffmpeg → MP4
        mp4_path = self.output_dir / "artifact.mp4"
        self._ffmpeg_render(png_path, mp4_path)

        # Step 3: Compute artifact hash
        artifact_hash = self._compute_file_hash(mp4_path)

        # Step 4: Cleanup
        png_path.unlink(missing_ok=True)

        return {
            "ok": True,
            "artifact_path": str(mp4_path),
            "artifact_hash": artifact_hash,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "duration": self.duration,
            "size_bytes": mp4_path.stat().st_size,
        }

    def _chrome_screenshot(self, png_path: Path) -> None:
        """Take a screenshot using Chrome headless."""
        args = [
            _CHROME,
            "--headless",
            "--disable-gpu",
            f"--window-size={self.width},{self.height}",
            f"--screenshot={png_path}",
            "--virtual-time-budget=5000",
            f"file:///{self.composition_path}",
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"Chrome failed: {result.stderr[:300]}")
        if not png_path.exists():
            raise RuntimeError("Chrome did not produce screenshot")

    def _ffmpeg_render(self, png_path: Path, mp4_path: Path) -> None:
        """Render PNG to MP4 using ffmpeg."""
        args = [
            _FFMPEG, "-y",
            "-loop", "1", "-i", str(png_path),
            "-t", str(self.duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "20",
            "-movflags", "+faststart",
            "-vf", f"scale={self.width}:{self.height}",
            "-r", str(self.fps),
            str(mp4_path),
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:300]}")

    def _compute_file_hash(self, path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def publish_to_bus(self, bus: EvidenceBus, artifact_info: Dict[str, Any]) -> EvidenceEvent:
        """Publish artifact://render event to Evidence Bus."""
        source = EvidenceSource("pc-vision-render", self.producer_hash)
        event = source.emit(
            schema="artifact://render",
            subject=artifact_info["artifact_path"],
            payload={
                "artifact_hash": artifact_info["artifact_hash"],
                "width": artifact_info["width"],
                "height": artifact_info["height"],
                "fps": artifact_info["fps"],
                "duration": artifact_info["duration"],
                "size_bytes": artifact_info["size_bytes"],
                "producer_hash": self.producer_hash,
            },
        )
        return bus.publish(event)


class ArtifactReceipt:
    """Generate artifact receipt with full provenance.

    Receipt contains:
      - source_root (from detections.jsonl)
      - inference_root (from inference config)
      - composition_hash
      - artifact_hash
      - producer_hash
      - timestamp
    """

    def __init__(
        self,
        source_root: str,
        inference_root: str,
        composition_hash: str,
        artifact_hash: str,
        producer_hash: str,
    ):
        self.source_root = source_root
        self.inference_root = inference_root
        self.composition_hash = composition_hash
        self.artifact_hash = artifact_hash
        self.producer_hash = producer_hash
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "artifact://receipt",
            "source_root": self.source_root,
            "inference_root": self.inference_root,
            "composition_hash": self.composition_hash,
            "artifact_hash": self.artifact_hash,
            "producer_hash": self.producer_hash,
            "timestamp": self.timestamp,
        }

    def compute_receipt_hash(self) -> str:
        """Compute SHA-256 hash of the receipt."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def save(self, path: Path) -> None:
        """Save receipt to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def publish_to_bus(self, bus: EvidenceBus) -> EvidenceEvent:
        """Publish artifact://receipt to Evidence Bus."""
        source = EvidenceSource("pc-vision-receipt", self.producer_hash)
        event = source.emit(
            schema="artifact://receipt",
            subject=self.artifact_hash,
            payload=self.to_dict(),
        )
        return bus.publish(event)


def compute_source_root(jsonl_path: Path) -> str:
    """Compute source root hash from detections.jsonl."""
    h = hashlib.sha256()
    with open(jsonl_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_inference_root(jsonl_path: Path) -> str:
    """Compute inference root hash from first event's config."""
    with open(jsonl_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        if not first_line:
            return "0" * 64
        event = json.loads(first_line)
        config_hash = event.get("inference_config_hash", "")
        return config_hash
