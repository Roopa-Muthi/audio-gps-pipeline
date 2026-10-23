"""
Sprint 7 — Real-time dashboard server

Serves static/index.html and exposes a WebSocket at /ws that the orchestrator
pushes resolved events into. Runs in the same asyncio event loop as the
orchestrator (via asyncio.gather in main.py) so there's no extra process or
IPC layer between "event resolved" and "shown on screen."
"""
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

_active_connections: list[WebSocket] = []
_STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/")
async def index() -> HTMLResponse:
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_connections.append(websocket)
    try:
        while True:
            # We don't expect messages from the browser; this just keeps the
            # connection open and lets us detect a disconnect promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        _active_connections.remove(websocket)


async def broadcast_event(payload: dict) -> None:
    """Push a JSON-serializable event to every connected dashboard tab."""
    message = json.dumps(payload)
    dead: list[WebSocket] = []
    for ws in _active_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _active_connections.remove(ws)
