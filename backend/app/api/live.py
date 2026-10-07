"""app/api/live.py — ``WS /ws/live`` (SDD §11.4, §13.4).

Thin route: all logic lives in ``app.live.session``. Tests inject a fake Gemini session by setting
``app.state.live_connect_factory`` (a ``(model, config) -> async context manager`` callable).
The legacy ``WS /api/wells/{id}/live`` shim stays in ``app.api.wells`` until Stage V (D-20).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.live.session import handle_live_websocket

router = APIRouter()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    factory = getattr(websocket.app.state, "live_connect_factory", None)
    await handle_live_websocket(websocket, connect_factory=factory)
