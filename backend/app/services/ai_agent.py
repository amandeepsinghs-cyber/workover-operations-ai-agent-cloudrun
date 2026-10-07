"""Structured per-well recommendation (TC-022 rank-1) used by ``/api/wells/{id}/recommendations``.

v0.4 Stage V: the legacy Gemini-API-key chat path (``call_gemini_api``, ``chat_with_well_agent``,
local keyword "petroleum expert") is removed. All conversation now goes through the ADK agent in
``app.agent.runner`` (Vertex AI, ADC). This module keeps only the deterministic, tool-backed
recommendation object.
"""

from __future__ import annotations

import json
from typing import Any


def generate_structured_recommendation(well: dict[str, Any]) -> dict[str, Any]:
    """Structured recommendation = TC-022 rank-1 action (SDD §13.3; Stage R). No USD, no payback.

    The former hard-coded titles / uplift numbers were fabricated and are gone; when TC-022 has no
    action the object says so (status UNAVAILABLE) instead of inventing one.
    """
    from app.analytics.tools.nba import (
        recommend_next_best_action,
        recommendation_from_nba,
    )

    result = recommend_next_best_action(str(well["id"]))
    rec = recommendation_from_nba(result)
    if rec is not None:
        return rec
    return {
        "status": "UNAVAILABLE",
        "title": "No recommendation available",
        "urgency": "Review",
        "urgency_badge": "warning",
        "cost_band": None,
        "rig_days": None,
        "catalogue_job_codes": [],
        "projected_flow_uplift_bopd": None,
        "action_items": [],
        "risk_mitigation": result.message or "TC-022 returned no action.",
        "flags": list(getattr(result.value, "flags", []) or []),
        "provenance": json.loads(json.dumps(result.provenance, default=str)),
    }
