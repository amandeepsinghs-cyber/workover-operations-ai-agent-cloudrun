"""app/live/fallback.py — text answer used after 3 consecutive Gemini Live failures (BDD-F07-S04).

Seam: Stage V provides ``app.agent.runner.run_turn`` (ADK Runner, tool-grounded). Until then the
existing per-well chat function (``app.services.ai_agent.chat_with_well_agent``) answers. Both are
resolved lazily at call time so neither stage's refactor breaks the Live route.
"""

from __future__ import annotations

import logging
from typing import Any

from app.live.voice_tools import _find_well, _resolve

logger = logging.getLogger("wellpulse.live.fallback")


def answer_text(text: str, ui: dict[str, Any] | None = None, history: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Return ``{"text", "recommendation"?, "engine"}``; never raises."""
    ui = ui or {}
    language = ui.get("language") or "english"
    try:
        run_turn = _resolve([("app.agent.runner", "run_turn")])
        if run_turn is not None:  # Stage V
            reply = run_turn(
                session_id=ui.get("session_id") or "live-fallback",
                user_id="live",
                persona=ui.get("persona") or "ASSET_MANAGER",
                field=ui.get("field"),
                well_id=ui.get("well_id"),
                language=language,
                text=text,
            )
            data = reply.model_dump() if hasattr(reply, "model_dump") else dict(reply)
            return {"text": data.get("response", ""), "recommendation": data.get("recommendation"),
                    "engine": data.get("engine", "adk-runner")}

        chat = _resolve([("app.services.ai_agent", "chat_with_well_agent")])
        well = _find_well(ui["well_id"]) if ui.get("well_id") else None
        if chat is None or well is None:
            return {"text": "Text mode needs a selected well; open a well and ask again.", "engine": "text-fallback"}
        out = chat(well, text, language=language)
        return {"text": out.get("response", ""), "recommendation": out.get("recommendation"),
                "engine": f"text-fallback:{out.get('engine', 'chat')}"}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("fallback answer failed: %s: %s", type(e).__name__, e)
        return {"text": "Model unavailable; please retry.", "engine": "text-fallback:error"}
