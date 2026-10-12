"""PC://SENSORIUM — Multi-sensor observation plane.

Generaliza PC://VISION a un sensorium completo:
  VISION://  camera, tracking, objects
  SYSTEM://  CPU, GPU, RAM, processes, network
  AUDIO://   microphone, events, transcription

Todos alimentan PC://EVIDENCE_BUS_V1.

Invariantes:
  Observation ≠ Decision
  Evidence ≠ Authority
  Presentation ≠ Truth
  Capability ≠ Permission

PC://SENSORIUM_V1
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from evidence_bus import EvidenceBus, EvidenceEvent, EvidenceSource, compute_producer_hash


# --- Constants ---
SENSORIUM_VERSION = "PC://SENSORIUM_V1"


# --- 4 Invariantes como código ---
class Invariantes:
    """Los 4 invariantes constitucionales de PC://SENSORIUM."""

    OBSERVATION_DECISION = "Observation ≠ Decision"
    EVIDENCE_AUTHORITY = "Evidence ≠ Authority"
    PRESENTATION_TRUTH = "Presentation ≠ Truth"
    CAPABILITY_PERMISSION = "Capability ≠ Permission"

    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.OBSERVATION_DECISION,
            cls.EVIDENCE_AUTHORITY,
            cls.PRESENTATION_TRUTH,
            cls.CAPABILITY_PERMISSION,
        ]

    @classmethod
    def verify(cls, event: EvidenceEvent) -> bool:
        """Verify an event doesn't violate any invariant."""
        # Evidence events never contain authority decisions
        if event.schema.startswith("authority://"):
            return False
        # Evidence events never contain grants
        if "grant" in event.payload and event.schema.startswith("evidence://"):
            return False
        return True


# --- System Sensor ---
@dataclass
class SystemReading:
    """Lectura del sistema — CPU, GPU, RAM, procesos."""
    timestamp: str
    cpu_percent: float
    cpu_freq_mhz: float
    ram_total_gb: float
    ram_used_gb: float
    ram_percent: float
    gpu_name: str = ""
    gpu_temp_c: float = 0.0
    gpu_util_percent: float = 0.0
    gpu_vram_used_mb: float = 0.0
    gpu_vram_total_mb: float = 0.0
    process_count: int = 0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 2),
            "cpu_freq_mhz": round(self.cpu_freq_mhz, 2),
            "ram_total_gb": round(self.ram_total_gb, 2),
            "ram_used_gb": round(self.ram_used_gb, 2),
            "ram_percent": round(self.ram_percent, 2),
            "gpu_name": self.gpu_name,
            "gpu_temp_c": round(self.gpu_temp_c, 2),
            "gpu_util_percent": round(self.gpu_util_percent, 2),
            "gpu_vram_used_mb": round(self.gpu_vram_used_mb, 2),
            "gpu_vram_total_mb": round(self.gpu_vram_total_mb, 2),
            "process_count": self.process_count,
            "network_sent_mb": round(self.network_sent_mb, 2),
            "network_recv_mb": round(self.network_recv_mb, 2),
        }


class SystemSensor:
    """Sensor de sistema — CPU, GPU, RAM, procesos, red."""

    def __init__(self):
        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config={"platform": platform.system()},
        )

    def read(self) -> SystemReading:
        """Read current system state."""
        # CPU
        cpu_percent = self._get_cpu_percent()
        cpu_freq = self._get_cpu_freq()

        # RAM
        ram_total, ram_used, ram_percent = self._get_ram()

        # GPU
        gpu_name, gpu_temp, gpu_util, gpu_vram_used, gpu_vram_total = self._get_gpu()

        # Processes
        process_count = self._get_process_count()

        # Network
        net_sent, net_recv = self._get_network()

        return SystemReading(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z",
            cpu_percent=cpu_percent,
            cpu_freq_mhz=cpu_freq,
            ram_total_gb=ram_total,
            ram_used_gb=ram_used,
            ram_percent=ram_percent,
            gpu_name=gpu_name,
            gpu_temp_c=gpu_temp,
            gpu_util_percent=gpu_util,
            gpu_vram_used_mb=gpu_vram_used,
            gpu_vram_total_mb=gpu_vram_total,
            process_count=process_count,
            network_sent_mb=net_sent,
            network_recv_mb=net_recv,
        )

    def _get_cpu_percent(self) -> float:
        """Get CPU usage percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0

    def _get_cpu_freq(self) -> float:
        """Get CPU frequency in MHz."""
        try:
            import psutil
            freq = psutil.cpu_freq()
            return freq.current if freq else 0.0
        except ImportError:
            return 0.0

    def _get_ram(self) -> tuple:
        """Get RAM info: (total_gb, used_gb, percent)."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return (
                mem.total / (1024 ** 3),
                mem.used / (1024 ** 3),
                mem.percent,
            )
        except ImportError:
            return (0.0, 0.0, 0.0)

    def _get_gpu(self) -> tuple:
        """Get GPU info: (name, temp, util, vram_used, vram_total)."""
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                # Try to get more info via nvidia-smi
                try:
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                         "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        parts = result.stdout.strip().split(", ")
                        return (name, float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
                except Exception:
                    pass
                return (name, 0.0, 0.0, 0.0, 0.0)
        except ImportError:
            pass
        return ("", 0.0, 0.0, 0.0, 0.0)

    def _get_process_count(self) -> int:
        """Get process count."""
        try:
            import psutil
            return len(psutil.pids())
        except ImportError:
            return 0

    def _get_network(self) -> tuple:
        """Get network I/O: (sent_mb, recv_mb)."""
        try:
            import psutil
            net = psutil.net_io_counters()
            return (net.bytes_sent / (1024 ** 2), net.bytes_recv / (1024 ** 2))
        except ImportError:
            return (0.0, 0.0)

    def emit(self, subject: str = "system://localhost") -> EvidenceEvent:
        """Create a system evidence event."""
        reading = self.read()
        source = EvidenceSource("pc-sensorium-system", self.producer_hash)
        return source.emit(
            schema="system://reading",
            subject=subject,
            payload=reading.to_dict(),
        )


# --- Audio Sensor (placeholder) ---
@dataclass
class AudioReading:
    """Lectura de audio — placeholder para futura implementación."""
    timestamp: str
    sample_rate: int = 16000
    channels: int = 1
    duration_ms: float = 0.0
    rms_db: float = 0.0
    transcription: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration_ms": round(self.duration_ms, 2),
            "rms_db": round(self.rms_db, 2),
            "transcription": self.transcription,
        }


class AudioSensor:
    """Sensor de audio — placeholder."""

    def __init__(self):
        self.producer_hash = compute_producer_hash(
            code_version="0.1.0",
            config={"sample_rate": 16000},
        )

    def emit(self, subject: str = "audio://microphone") -> EvidenceEvent:
        """Create an audio evidence event."""
        reading = AudioReading(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z",
        )
        source = EvidenceSource("pc-sensorium-audio", self.producer_hash)
        return source.emit(
            schema="audio://reading",
            subject=subject,
            payload=reading.to_dict(),
        )


# --- Sensorium ---
class Sensorium:
    """Sensorium — multi-sensor observation plane.

    Coordina todos los sensores y publica a PC://EVIDENCE.
    """

    def __init__(self, bus: EvidenceBus):
        self.bus = bus
        self.system_sensor = SystemSensor()
        self.audio_sensor = AudioSensor()
        self.sensors: Dict[str, EvidenceSource] = {
            "system": EvidenceSource("pc-sensorium-system", self.system_sensor.producer_hash),
            "audio": EvidenceSource("pc-sensorium-audio", self.audio_sensor.producer_hash),
        }

    def observe_system(self) -> EvidenceEvent:
        """Observe system state and publish to bus."""
        event = self.system_sensor.emit()
        return self.bus.publish(event)

    def observe_audio(self) -> EvidenceEvent:
        """Observe audio state and publish to bus."""
        event = self.audio_sensor.emit()
        return self.bus.publish(event)

    def observe_all(self) -> List[EvidenceEvent]:
        """Observe all sensors and publish to bus."""
        events = []
        events.append(self.observe_system())
        events.append(self.observe_audio())
        return events

    def get_sensor_readings(self) -> Dict[str, Any]:
        """Get current readings from all sensors."""
        return {
            "system": self.system_sensor.read().to_dict(),
            "audio": AudioReading(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            ).to_dict(),
        }


# --- Executive Bridge Instrument Panel ---
class InstrumentPanel:
    """Executive Bridge — instrument panel del sensorium.

    Muestra:
      - VISION: tracks, FPS, latency
      - SYSTEM: CPU, GPU, RAM
      - EVIDENCE: stream root, event chain, receipts
      - AUTHORITY: grants, policy
    """

    def __init__(self, bus: EvidenceBus):
        self.bus = bus

    def get_panel_data(self) -> Dict[str, Any]:
        """Get all instrument panel data."""
        return {
            "sensorium": {
                "version": SENSORIUM_VERSION,
                "invariants": Invariantes.all(),
            },
            "vision": self._get_vision_data(),
            "system": self._get_system_data(),
            "evidence": self._get_evidence_data(),
            "authority": self._get_authority_data(),
        }

    def _get_vision_data(self) -> Dict[str, Any]:
        """Get vision sensor data."""
        vision_events = self.bus.query("vision://")
        if not vision_events:
            return {"status": "no_data"}

        latest = vision_events[-1]
        return {
            "status": "active",
            "frame_count": len(vision_events),
            "latest_frame": latest.payload.get("frame_index", 0),
            "detections": len(latest.payload.get("detections", [])),
            "source": latest.source,
        }

    def _get_system_data(self) -> Dict[str, Any]:
        """Get system sensor data."""
        system_events = self.bus.query("system://")
        if not system_events:
            return {"status": "no_data"}

        latest = system_events[-1]
        payload = latest.payload
        return {
            "status": "active",
            "cpu_percent": payload.get("cpu_percent", 0),
            "ram_percent": payload.get("ram_percent", 0),
            "gpu_name": payload.get("gpu_name", ""),
            "gpu_temp_c": payload.get("gpu_temp_c", 0),
            "gpu_util_percent": payload.get("gpu_util_percent", 0),
            "process_count": payload.get("process_count", 0),
        }

    def _get_evidence_data(self) -> Dict[str, Any]:
        """Get evidence bus data."""
        return {
            "event_count": len(self.bus.events),
            "bus_root": self.bus.compute_bus_root(),
            "schemas": list(set(e.schema for e in self.bus.events)),
            "sources": list(set(e.source for e in self.bus.events)),
        }

    def _get_authority_data(self) -> Dict[str, Any]:
        """Get authority data (observation only, no decisions)."""
        # Authority is never stored in evidence bus
        # This is a read-only view of current policy state
        return {
            "policy": "PC://LOCAL",
            "consequential_grants": "NONE",
            "human_root": "🧿",
            "note": "Authority is never derived from evidence",
        }
