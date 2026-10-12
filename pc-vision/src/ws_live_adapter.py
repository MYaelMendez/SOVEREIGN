"""PC://VISION — WebSocket Live Adapter.

Servidor WebSocket que envía eventos canónicos al Canvas.
Permite modo LIVE en Executive Bridge.

PC://VISION_PRESENTATION_V1
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import websockets

from jsonl_schema import VisionEventChain


logger = logging.getLogger(__name__)


class WSLiveAdapter:
    """WebSocket adapter — sirve eventos canónicos al Canvas.

    Clients connect to ws://127.0.0.1:8765
    Messages: { type: "frame", frame_index, events: [...] }
    """

    def __init__(self, jsonl_path: Path, host: str = "127.0.0.1", port: int = 8765):
        self.jsonl_path = Path(jsonl_path)
        self.host = host
        self.port = port
        self.chain = VisionEventChain.from_jsonl(self.jsonl_path)
        self.clients: set = set()
        self._running = False

    async def register(self, websocket) -> None:
        """Register a new client."""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total: {len(self.clients)}")

    async def unregister(self, websocket) -> None:
        """Unregister a client."""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.clients)}")

    async def send_frame(self, websocket, frame_index: int) -> None:
        """Send a frame to a client."""
        if frame_index >= len(self.chain.events):
            return

        event = self.chain.events[frame_index]
        message = {
            "type": "frame",
            "frame_index": event.frame_index,
            "media_time_ms": event.media_time_ms,
            "detections": [d.to_dict() for d in event.detections],
            "source_width": event.source_width,
            "source_height": event.source_height,
            "events": [e.to_dict() for e in self.chain.events],
        }

        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Send error: {e}")

    async def broadcast_frame(self, frame_index: int) -> None:
        """Broadcast a frame to all connected clients."""
        if not self.clients:
            return

        message = {
            "type": "frame",
            "frame_index": frame_index,
            "events": [e.to_dict() for e in self.chain.events],
        }

        disconnected = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(message))
            except Exception:
                disconnected.add(client)

        for client in disconnected:
            self.clients.discard(client)

    async def handler(self, websocket, path) -> None:
        """Handle a WebSocket connection."""
        await self.register(websocket)
        try:
            # Send initial frame
            await self.send_frame(websocket, 0)

            # Keep connection alive
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("type") == "seek":
                        frame_index = data.get("frame_index", 0)
                        await self.send_frame(websocket, frame_index)
                    elif data.get("type") == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            await self.unregister(websocket)

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._running = True
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()  # Run forever

    def start_sync(self) -> None:
        """Start the server synchronously."""
        asyncio.run(self.start())

    async def stop(self) -> None:
        """Stop the server."""
        self._running = False
        for client in self.clients:
            await client.close()
        self.clients.clear()


class WSClient:
    """Cliente WebSocket — para testing."""

    def __init__(self, uri: str = "ws://127.0.0.1:8765"):
        self.uri = uri
        self.websocket = None

    async def connect(self) -> None:
        """Connect to the server."""
        self.websocket = await websockets.connect(self.uri)

    async def send(self, message: Dict[str, Any]) -> None:
        """Send a message."""
        await self.websocket.send(json.dumps(message))

    async def receive(self) -> Dict[str, Any]:
        """Receive a message."""
        message = await self.websocket.recv()
        return json.loads(message)

    async def close(self) -> None:
        """Close the connection."""
        if self.websocket:
            await self.websocket.close()
