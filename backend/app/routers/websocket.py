"""WebSocket endpoint and ConnectionManager for real-time live telemetry and alerts.
Specified in /docs/HANDOFF.md §8.8.
"""
import json
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])


class WebSocketManager:
    def __init__(self):
        # Map websocket -> set of subscribed station_ids (empty set means all stations)
        self.active_connections: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    def subscribe(self, websocket: WebSocket, station_ids: Optional[List[str]] = None):
        if websocket in self.active_connections:
            if station_ids:
                self.active_connections[websocket] = set(station_ids)
            else:
                self.active_connections[websocket] = set()  # All stations

    async def broadcast(self, message_type: str, data: Dict[str, Any], station_id: Optional[str] = None):
        """Broadcast event to relevant connected clients."""
        payload = json.dumps({"type": message_type, "data": data})
        dead_connections = []

        for ws, sub_stations in list(self.active_connections.items()):
            try:
                # If subscriber specified station_ids, filter accordingly
                if station_id and sub_stations and station_id not in sub_stations:
                    continue
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)


ws_manager = WebSocketManager()


@router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                if msg.get("action") == "subscribe":
                    stn_ids = msg.get("station_ids")
                    ws_manager.subscribe(websocket, stn_ids)
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
