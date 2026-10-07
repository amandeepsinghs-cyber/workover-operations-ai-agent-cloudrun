"""app/live/fallback.py — text answer used after 3 consecutive Gemini Live failures (BDD-F07-S04).

v0.4 Stage V: answers come from the ADK agent (``app.agent.runner.run_turn``, tool-grounded, same
tools and RBAC as ``POST /api/chat``). The legacy per-well Gemini-API-key chat path is removed.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("wellpulse.live.fallback")


def answer_text(text: str, ui: dict[str, Any] | None = None, history: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Return ``{"text", "recommendation", "artifacts", "actions", "engine"}``; never raises."""
    ui = ui or {}
    try:
        from app.agent.runner import run_turn

        data = run_turn(
            session_id=ui.get("session_id") or "live-fallback",
            user_id="live",
            persona=ui.get("persona") or "ASSET_MANAGER",
            field=ui.get("field"),
            well_id=ui.get("well_id"),
            language=ui.get("language") or "hinglish",
            text=text,
            screen=ui.get("screen"),
        )
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        return {"text": data.get("response", ""), "recommendation": data.get("recommendation"),
                "artifacts": data.get("artifacts", []), "actions": data.get("actions", []),
                "engine": f"text-fallback:{data.get('engine', 'adk-runner')}"}
    except Exception as e:  # noqa: BLE001 - never raise into the Live session
        logger.warning("fallback answer failed: %s: %s", type(e).__name__, e)
        return {"text": "Model unavailable; please retry.", "engine": "text-fallback:error"}
