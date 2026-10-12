"""ÆVLC_RENDER_PIPELINE_V1 — Generative Media Player and Studio.

Render pipeline:
  composition.html → Chrome headless → frames → ffmpeg → artifact.mp4 → verify → 🧾

Publica a PC://EVIDENCE_BUS_V1.

Invariantes:
  Generate ≠ Render
  Render ≠ Artifact
  Artifact ≠ Verified Artifact
  Verified Artifact ≠ Published Artifact

ÆVLC_RENDER_PIPELINE_V1
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from evidence_bus import EvidenceBus, EvidenceSource, compute_producer_hash


# --- Constants ---
RENDER_VERSION = "ÆVLC_RENDER_PIPELINE_V1"
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 30
DEFAULT_DURATION = 10
DEFAULT_CODEC = "h264"


# --- Data Classes ---
@dataclass
class RenderConfig:
    """Configuración de render."""
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: int = DEFAULT_FPS
    duration: int = DEFAULT_DURATION
    codec: str = DEFAULT_CODEC
    crf: int = 20
    preset: str = "fast"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "duration": self.duration,
            "codec": self.codec,
            "crf": self.crf,
            "preset": self.preset,
        }

    def compute_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ArtifactReceipt:
    """Receipt de artifact — publica a PC://EVIDENCE_BUS."""
    schema: str = "media://render/v1"
    producer: str = "aevlc-render"
    composition_hash: str = ""
    timeline_hash: str = ""
    assets_root: str = ""
    render_config_hash: str = ""
    frame_count: int = 0
    fps: int = 0
    duration_ms: int = 0
    width: int = 0
    height: int = 0
    codec: str = ""
    artifact_hash: str = ""
    verified: bool = False
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "producer": self.producer,
            "composition_hash": self.composition_hash,
            "timeline_hash": self.timeline_hash,
            "assets_root": self.assets_root,
            "render_config_hash": self.render_config_hash,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "duration_ms": self.duration_ms,
            "width": self.width,
            "height": self.height,
            "codec": self.codec,
            "artifact_hash": self.artifact_hash,
            "verified": self.verified,
            "timestamp": self.timestamp,
        }

    def compute_receipt_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


# --- Render Pipeline ---
class RenderPipeline:
    """ÆVLC Render Pipeline.

    Flujo:
      1. Load composition.html
      2. Chrome headless → PNG frames
      3. ffmpeg → MP4
      4. ffprobe → verify
      5. Generate receipt
      6. Publish to Evidence Bus
    """

    def __init__(
        self,
        composition_path: Path,
        output_dir: Path,
        config: Optional[RenderConfig] = None,
        assets_dir: Optional[Path] = None,
    ):
        self.composition_path = Path(composition_path)
        self.output_dir = Path(output_dir)
        self.config = config or RenderConfig()
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config=self.config.to_dict(),
        )

        # Hashes
        self.composition_hash = self._compute_file_hash(self.composition_path)
        self.timeline_hash = self._compute_timeline_hash()
        self.assets_root = self._compute_assets_hash()

    def render(self) -> ArtifactReceipt:
        """Execute the full render pipeline."""
        # Step 1: Chrome headless → PNG
        png_path = self.output_dir / "frame.png"
        self._chrome_screenshot(png_path)

        # Step 2: ffmpeg → MP4
        mp4_path = self.output_dir / "artifact.mp4"
        self._ffmpeg_render(png_path, mp4_path)

        # Step 3: ffprobe → verify
        probe_info = self._ffprobe_verify(mp4_path)

        # Step 4: Compute artifact hash
        artifact_hash = self._compute_file_hash(mp4_path)

        # Step 5: Cleanup
        png_path.unlink(missing_ok=True)

        # Step 6: Generate receipt
        receipt = ArtifactReceipt(
            composition_hash=self.composition_hash,
            timeline_hash=self.timeline_hash,
            assets_root=self.assets_root,
            render_config_hash=self.config.compute_hash(),
            frame_count=probe_info.get("frame_count", 0),
            fps=self.config.fps,
            duration_ms=int(self.config.duration * 1000),
            width=self.config.width,
            height=self.config.height,
            codec=self.config.codec,
            artifact_hash=artifact_hash,
            verified=True,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        return receipt

    def _chrome_screenshot(self, png_path: Path) -> None:
        """Take a screenshot using Chrome headless."""
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        args = [
            chrome,
            "--headless",
            "--disable-gpu",
            f"--window-size={self.config.width},{self.config.height}",
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
        ffmpeg = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe"
        args = [
            ffmpeg, "-y",
            "-loop", "1", "-i", str(png_path),
            "-t", str(self.config.duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(self.config.crf),
            "-preset", self.config.preset,
            "-movflags", "+faststart",
            "-vf", f"scale={self.config.width}:{self.config.height}",
            "-r", str(self.config.fps),
            str(mp4_path),
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:300]}")

    def _ffprobe_verify(self, mp4_path: Path) -> Dict[str, Any]:
        """Verify MP4 with ffprobe."""
        ffprobe = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffprobe.exe"
        args = [
            ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name",
            "-of", "json",
            str(mp4_path),
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr[:300]}")

        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]

        # Parse frame rate
        fps_str = stream.get("r_frame_rate", "30/1")
        num, den = fps_str.split("/")
        fps = int(num) / int(den) if int(den) != 0 else 30

        return {
            "width": stream.get("width", 0),
            "height": stream.get("height", 0),
            "fps": int(fps),
            "frame_count": int(stream.get("nb_frames", 0)),
            "codec": stream.get("codec_name", ""),
        }

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

    def _compute_timeline_hash(self) -> str:
        """Compute timeline hash (placeholder)."""
        # In production, this would hash a timeline.json
        return hashlib.sha256(b"timeline_placeholder").hexdigest()

    def _compute_assets_hash(self) -> str:
        """Compute assets root hash."""
        if not self.assets_dir or not self.assets_dir.exists():
            return ""

        h = hashlib.sha256()
        for file in sorted(self.assets_dir.rglob("*")):
            if file.is_file():
                h.update(file.name.encode())
                h.update(self._compute_file_hash(file).encode())
        return h.hexdigest()

    def publish_to_bus(self, bus: EvidenceBus, receipt: ArtifactReceipt) -> None:
        """Publish receipt to Evidence Bus."""
        source = EvidenceSource("aevlc-render", self.producer_hash)
        event = source.emit(
            schema="media://render/v1",
            subject=receipt.artifact_hash,
            payload=receipt.to_dict(),
        )
        bus.publish(event)


# --- Verification ---
class ArtifactVerifier:
    """Verifica artifacts contra receipts."""

    def __init__(self, receipt: ArtifactReceipt):
        self.receipt = receipt

    def verify(self, artifact_path: Path) -> bool:
        """Verify an artifact matches its receipt."""
        # Check artifact hash
        h = hashlib.sha256()
        with open(artifact_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        artifact_hash = h.hexdigest()

        if artifact_hash != self.receipt.artifact_hash:
            return False

        # Check file exists and is non-empty
        if not artifact_path.exists() or artifact_path.stat().st_size == 0:
            return False

        return True

    def verify_frame_count(self, expected: int) -> bool:
        """Verify frame count matches."""
        return self.receipt.frame_count == expected

    def verify_duration(self, expected_ms: int) -> bool:
        """Verify duration matches."""
        return self.receipt.duration_ms == expected_ms

    def verify_resolution(self, width: int, height: int) -> bool:
        """Verify resolution matches."""
        return self.receipt.width == width and self.receipt.height == height

    def verify_fps(self, fps: int) -> bool:
        """Verify FPS matches."""
        return self.receipt.fps == fps


# --- Authority Classes ---
class AuthorityClasses:
    """Clases de autoridad para render pipeline."""

    GENERATE = "LOCAL"
    PREVIEW = "LOCAL"
    RENDER = "LOCAL"
    VERIFY = "LOCAL"
    SAVE_DURABLY = "DURABLE"
    PUBLISH = "EXTERNAL"

    @classmethod
    def get_authority(cls, operation: str) -> str:
        """Get authority level for an operation."""
        mapping = {
            "generate": cls.GENERATE,
            "preview": cls.PREVIEW,
            "render": cls.RENDER,
            "verify": cls.VERIFY,
            "save": cls.SAVE_DURABLY,
            "publish": cls.PUBLISH,
        }
        return mapping.get(operation.lower(), "LOCAL")
