"""Deterministic intent router (keyword rules over the SDD §12.5 routing hints).

Used in exactly two places, never silently:
* :mod:`app.agent.fake_llm` — the scripted LLM for CI / offline tests (``WELLPULSE_AGENT_LLM=fake``);
* the runner's **degraded** path when Vertex is unreachable (SDD §12.6): ``ChatReply.status = "degraded"`` and the
  text says "Model unavailable; showing tool output." (W-12: no silent keyword fallback).

It only chooses tools + arguments; every number still comes from the tools.
"""

from __future__ import annotations

import re
from typing import Any

from app.agent.adk_tools import norm_field, norm_well_id

_WELL_RE = re.compile(r"\b(GK|LKW|LKM)[\s\-_]?(\d{1,3})\b", re.IGNORECASE)
_FIELD_RE = re.compile(r"\b(geleki|lakwa|lakhmani)\b", re.IGNORECASE)

# job keywords (text order decides the alternative in "why not X")
_JOBS = [
    (r"wax|paraffin", "wax removal"), (r"re-?perf|perforat", "reperforation"), (r"acid|stimul", "acid stimulation"),
    (r"scale", "scale removal"), (r"sand", "sand cleanout"), (r"gas[- ]?lift valve|glv", "gas-lift valve replacement"),
    (r"pump", "pump overhaul"), (r"squeeze|wso|water shut", "cement squeeze"), (r"choke", "choke back"),
    (r"frac", "hydraulic fracturing"),
]


def _has(t: str, pat: str) -> bool:
    return re.search(pat, t, re.IGNORECASE) is not None


def well_in(text: str) -> str:
    m = _WELL_RE.search(text or "")
    return norm_well_id(f"{m.group(1)}-{m.group(2)}") if m else ""


def field_in(text: str) -> str:
    m = _FIELD_RE.search(text or "")
    return norm_field(m.group(1)) if m else ""


def _months(t: str) -> int:
    if _has(t, r"\b(5|five|paanch)[- ]?(year|yr|saal)"):
        return 60
    if _has(t, r"\b(2|two|do)[- ]?(year|yr|saal)"):
        return 24
    return 36


def _alternative(t: str) -> str:
    m = re.search(r"(instead of|rather than|why not( just)?|ki jagah|ke bajaye)\s+([a-z\- ]+)", t, re.IGNORECASE)
    scope = m.group(3) if m else t
    best = None
    for pat, name in _JOBS:
        mm = re.search(pat, scope, re.IGNORECASE)
        if mm and (best is None or mm.start() < best[0]):
            best = (mm.start(), name)
    if best is None and m is None:
        return ""
    return best[1] if best else ""


def route(text: str, ctx: dict[str, Any] | None = None, history: list[str] | None = None) -> list[tuple[str, dict]]:
    """Return ``[(tool_name, args), ...]`` for one user message. ``ctx`` = UI context (field, well_id)."""
    ctx = ctx or {}
    t = (text or "").strip()
    tl = t.lower()
    well = well_in(t)
    field = field_in(t)
    cw = well or norm_well_id(ctx.get("well_id"))
    cf = field or norm_field(ctx.get("field"))
    calls: list[tuple[str, dict]] = []

    if _has(tl, r"real (lakwa |geleki |lakhmani )?data|is this (data )?real|synthetic|asli data"):
        return []

    plot = _has(tl, r"\b(plot|chart|graph|grafh|dikhao)\b")
    field_wise = _has(tl, r"field[- ]?wise|5[- ]?year|five[- ]?year|paanch saal|past .* years.*field|fields?'? production")
    if field_wise or (plot and not well and not _has(tl, r"this well|well ki")):
        prev_field_level = any(_has(h, r"field[- ]?wise|5[- ]?year|five[- ]?year|paanch saal") for h in (history or []))
        if field_wise or prev_field_level or not cw:
            return [("field_production_history", {"plot": bool(plot)})]

    if _has(tl, r"why not|instead of|rather than|kyun nahi|ki jagah|ke bajaye|against an alternative"):
        alt = _alternative(t)
        if alt:
            return [("compare_interventions", {"well_id": cw, "alternative": alt})]

    if _has(tl, r"which field|kaunsa field|not performing|underperforming field|field .*peeche|compare (all )?(the )?fields"):
        return [("compare_fields", {})]

    if _has(tl, r"sick|lost production|losing production|lose kar|at risk|not producing|band hain|kitne wells|how many wells"):
        calls.append(("classify_well_health", {"field": cf}))
        if _has(tl, r"sick|lost|lose|losing") and cf:
            calls.append(("attribute_decline", {"field": cf}))
        return calls

    if _has(tl, r"why .*declin|decline.*why|kyun gir|kyon gir|human factor|controllable|root cause"):
        return [("attribute_decline", {"well_id": well} if well else ({"field": field} if field else {}))]

    if _has(tl, r"priority list|priority|need intervention|needs intervention|candidate|rig queue|intervention list"):
        return [("rank_candidates", {"field": cf})]

    if _has(tl, r"worst well|worst wells|sabse kharab|lowest produc|सबसे खराब"):
        return [("query_wells", {"field": cf, "order_by": "decline_residual_pct", "direction": "ASC", "limit": 5})]

    if _has(tl, r"dossier|history pack|going to the field|field (pe|par) ja|before i go|ja raha|poori history"):
        return [("build_well_dossier", {"well_id": cw})]

    if _has(tl, r"\bsop\b|procedure|standard operating|how is this job done|job kaise"):
        return [("list_sops", {})]

    if _has(tl, r"document|pdf|report for|workover report|pressure survey report"):
        return [("search_documents", {"query": t, "well_id": cw})]

    if _has(tl, r"trust (the|this|it)|model quality|how good is (this|the) model|classifier|machine learning|\bml\b|intervention type"):
        return [("classify_intervention", {"well_id": well})]

    if _has(tl, r"tell me (more )?about|profile|nearby|aas paas|history of|production history|about this well|is well ke"):
        if _has(tl, r"tell me|about|profile|nearby|aas paas|is well ke"):
            calls.append(("well_profile", {"well_id": cw}))
        if _has(tl, r"production history|history|plot|chart"):
            calls.append(("plot_production", {"well_id": cw, "months": _months(tl)}))
        return calls

    if _has(tl, r"next best|recommend|what should we do|kya karein|kya karna|kaunsa job|interventions?\b"):
        return [("recommend_next_best_action", {"well_id": cw})]

    if _has(tl, r"\bmap\b|naksha"):
        return [("render_well_map", {"field": cf})]
    if _has(tl, r"weekly report|daily report|monthly report"):
        return [("generate_report", {"field": cf, "period": "MONTHLY" if "month" in tl else "DAILY" if "daily" in tl else "WEEKLY"})]
    if _has(tl, r"rig schedule|schedule rigs"):
        return [("schedule_rigs", {"field": cf})]
    if _has(tl, r"hierarchy|how many fields|clusters"):
        return [("query_hierarchy", {"field": field})]
    return []
