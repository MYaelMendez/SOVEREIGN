"""PC://VISION — Motor de visión determinista.

Produce CanonicalVisionEvents desde un source (video o imagen).
Cada frame genera un evento con hash chain verificable.

Build order: 1→3 (Truth Layer)
  1. jsonl_schema.py ✓
  2. cv_engine.py (este archivo)
  3. deterministic_replay.py
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from jsonl_schema import (
    CanonicalVisionEvent,
    Detection,
    InferenceConfig,
    VisionEventChain,
    compute_frame_hash,
    compute_source_hash,
    validate_event_schema,
)


class CVEengine:
    """Motor de visión — produce eventos canónicos desde un source.

    Uso:
        engine = CVEengine(InferenceConfig(model="yolov8n"))
        chain = engine.process_video("input.mp4")
        chain.to_jsonl(Path("detections.jsonl"))
    """

    def __init__(self, config: InferenceConfig):
        self.config = config
        self.config_hash = config.compute_hash()
        self._model = None
        self._tracker = None

    def _load_model(self):
        """Lazy-load the detection model."""
        if self._model is not None:
            return

        try:
            from ultralytics import YOLO
            self._model = YOLO(f"{self.config.model}.pt")
        except ImportError:
            raise RuntimeError(
                "ultralytics not installed. Install with: pip install ultralytics"
            )

    def _get_tracker(self):
        """Lazy-load the tracker."""
        if self._tracker is not None:
            return self._tracker

        try:
            from supervision.tracker.byte_tracker import ByteTrackTracker
            self._tracker = ByteTrackTracker()
        except ImportError:
            raise RuntimeError(
                "supervision not installed. Install with: pip install supervision"
            )

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        media_time_ms: float,
        source_id: str,
        source_hash: str,
        captured_at: str,
    ) -> CanonicalVisionEvent:
        """Process a single frame and return a CanonicalVisionEvent."""
        self._load_model()
        self._get_tracker()

        h, w = frame.shape[:2]
        processed_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"

        # Compute frame hash
        _, buf = cv2.imencode(".png", frame)
        frame_hash = compute_frame_hash(buf.tobytes())

        # Run inference
        t0 = time.perf_counter()
        results = self._model(frame, verbose=False)
        latency_ms = (time.perf_counter() - t0) * 1000

        # Extract detections
        detections: List[Detection] = []
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes
            if boxes is not None:
                xyxy = boxes.xyxy.cpu().numpy()
                conf = boxes.conf.cpu().numpy()
                cls = boxes.cls.cpu().numpy().astype(int)

                # Update tracker
                try:
                    import supervision as sv
                    sv_detections = sv.Detections(
                        xyxy=xyxy,
                        confidence=conf,
                        class_id=cls,
                    )
                    tracked = self._tracker.update(sv_detections)
                    track_ids = tracked.tracker_id if hasattr(tracked, "tracker_id") else [-1] * len(xyxy)
                except Exception:
                    track_ids = [-1] * len(xyxy)

                for i in range(len(xyxy)):
                    x1, y1, x2, y2 = xyxy[i]
                    bbox_norm = [
                        round(x1 / w, 6),
                        round(y1 / h, 6),
                        round(x2 / w, 6),
                        round(y2 / h, 6),
                    ]
                    detections.append(Detection(
                        track_id=int(track_ids[i]) if i < len(track_ids) else -1,
                        class_name=result.names.get(int(cls[i]), f"class_{cls[i]}"),
                        class_id=int(cls[i]),
                        confidence=float(conf[i]),
                        bbox_xyxy=[float(x1), float(y1), float(x2), float(y2)],
                        bbox_norm=bbox_norm,
                    ))

        event = CanonicalVisionEvent(
            frame_index=frame_index,
            media_time_ms=media_time_ms,
            captured_at=captured_at,
            processed_at=processed_at,
            source_id=source_id,
            source_hash=source_hash,
            frame_hash=frame_hash,
            source_width=w,
            source_height=h,
            detections=detections,
            inference_config_hash=self.config_hash,
            backend=self.config.backend,
            model=self.config.model,
            latency_ms=latency_ms,
        )

        # Validate
        errors = validate_event_schema(event)
        if errors:
            raise ValueError(f"Event validation failed: {errors}")

        return event

    def process_video(
        self,
        video_path: str,
        output_jsonl: Optional[str] = None,
        max_frames: Optional[int] = None,
    ) -> VisionEventChain:
        """Process an entire video file and return the event chain."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        source_hash = compute_source_hash(video_path)
        source_id = f"vision://video/{video_path.stem}"

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval_ms = 1000.0 / fps

        chain = VisionEventChain()
        frame_index = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if max_frames is not None and frame_index >= max_frames:
                break

            media_time_ms = frame_index * frame_interval_ms
            captured_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"

            event = self.process_frame(
                frame=frame,
                frame_index=frame_index,
                media_time_ms=media_time_ms,
                source_id=source_id,
                source_hash=source_hash,
                captured_at=captured_at,
            )
            chain.append(event)
            frame_index += 1

        cap.release()

        if output_jsonl:
            chain.to_jsonl(Path(output_jsonl))

        return chain

    def process_image(
        self,
        image_path: str,
        source_id: Optional[str] = None,
    ) -> CanonicalVisionEvent:
        """Process a single image and return a CanonicalVisionEvent."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        frame = cv2.imread(str(image_path))
        if frame is None:
            raise RuntimeError(f"Cannot read image: {image_path}")

        source_hash = compute_source_hash(image_path)
        source_id = source_id or f"vision://image/{image_path.stem}"
        captured_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"

        return self.process_frame(
            frame=frame,
            frame_index=0,
            media_time_ms=0.0,
            source_id=source_id,
            source_hash=source_hash,
            captured_at=captured_at,
        )
