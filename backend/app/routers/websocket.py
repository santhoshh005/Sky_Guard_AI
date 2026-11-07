"""WebSocket endpoint and ConnectionManager for real-time live telemetry and alerts.
Specified in /docs/HANDOFF.md §8.8.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

logger = logging.getLogger("skyguard.ws")
MAX_CONNECTIONS = 200
SEND_TIMEOUT_S = 2.0

router = APIRouter(tags=["WebSocket"])


class WebSocketManager:
    def __init__(self):
        # Map websocket -> set of subscribed station_ids (empty set means all stations)
        self.active_connections: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket) -> bool:
        if len(self.active_connections) >= MAX_CONNECTIONS:
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
            return False
        await websocket.accept()
        self.active_connections[websocket] = set()
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    def subscribe(self, websocket: WebSocket, station_ids: Optional[List[str]] = None):
        if websocket in self.active_connections:
            if isinstance(station_ids, list) and station_ids:
                self.active_connections[websocket] = {str(s)[:64] for s in station_ids[:500]}
            else:
                self.active_connections[websocket] = set()  # All stations

    async def broadcast(self, message_type: str, data: Dict[str, Any], station_id: Optional[str] = None):
        """Broadcast event to relevant connected clients."""
        payload = json.dumps({"type": message_type, "data": data}, default=str)
        targets = [
            ws for ws, subs in list(self.active_connections.items())
            if not (station_id and subs and station_id not in subs)
        ]

        async def _send(ws: WebSocket) -> Optional[WebSocket]:
            try:
                await asyncio.wait_for(ws.send_text(payload), timeout=SEND_TIMEOUT_S)
                return None
            except Exception:
                return ws

        # Concurrent sends: one slow client can no longer stall ingestion for everyone
        for dead in await asyncio.gather(*(_send(ws) for ws in targets)):
            if dead is not None:
                self.disconnect(dead)


ws_manager = WebSocketManager()


@router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    if not await ws_manager.connect(websocket):
        return
    try:
        while True:
            raw_text = await websocket.receive_text()
            if len(raw_text) > 16_384:
                continue
            try:
                msg = json.loads(raw_text)
                if msg.get("action") == "subscribe":
                    stn_ids = msg.get("station_ids")
                    ws_manager.subscribe(websocket, stn_ids)
            except (ValueError, AttributeError):
                logger.debug("Ignoring malformed WebSocket message")
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)
