"""app/live/voice_tools.py — voice tool REGISTRY for the Gemini Live proxy (SDD §11.3, F-07).

Integrity rule (BDD-F07-S05): every number spoken comes from a tool call in the same turn, so
this module only *wraps* existing backend functions; it never re-implements analytics.

Later stages extend the registry without touching ``session.py``::

    from app.live.voice_tools import register_voice_tool

    @register_voice_tool(name="compare_fields", action_kind="field_comparison",
                         description="TC-024: compare Geleki, Lakwa and Lakhmani ...")
    def _compare_fields(period: str = "L12M") -> dict:
        from app.analytics.field_compare import compare_fields   # resolved lazily at call time
        return compare_fields(period=period)

Backend functions are resolved **lazily at call time** through small seams (``_wells()``,
``_resolve()``), so Stage N's repository refactor cannot break import of this module.
Declarations are reflected from the Python signature (str/int/float/bool; defaults => optional).
Results are JSON-safe and **currency-stripped** (D-1: no ₹ / USD in voice).
"""

from __future__ import annotations

import importlib
import inspect
import logging
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("wellpulse.live.voice_tools")

ALL_PERSONAS = frozenset({"ED", "ASSET_MANAGER", "FIELD_ENGINEER"})

# Keys dropped from tool results before they reach the voice model (D-1: band + rig-days only).
_MONEY_KEY_MARKERS = ("usd", "inr", "lakh", "crore", "rupee", "realisation", "payback", "npv", "_cost", "cost_")
# Money amounts inside string values, e.g. "$45,000", "₹ 12 lakh", "USD 3.2M", "Rs. 500".
_MONEY_TEXT_RE = re.compile(
    r"(?:[₹$]|\bUSD\b|\bINR\b|\bRs\.?)\s?\d[\d,]*(?:\.\d+)?\s?(?:k|K|M|mn|million|lakh|crore|cr)?"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:USD|INR|dollars?|rupees?|lakh|crore)\b",
    re.IGNORECASE,
)
_KEEP_KEYS = frozenset({"cost_band", "cost_band_mix"})  # explicitly allowed (bands, not amounts)

_PY_TO_SCHEMA = {str: "STRING", int: "INTEGER", float: "NUMBER", bool: "BOOLEAN"}
TOOL_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class VoiceTool:
    name: str
    fn: Callable[..., Any]
    description: str
    action_kind: str | None = None  # emitted as {type:"action", kind, payload} after a call
    personas: frozenset[str] = field(default_factory=lambda: ALL_PERSONAS)


# Registry populated at import time by decorators only (never mutated per request).
VOICE_TOOLS: dict[str, VoiceTool] = {}


def register_voice_tool(
    name: str,
    description: str,
    action_kind: str | None = None,
    personas: frozenset[str] | set[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: add a function to the voice registry (last registration wins)."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        VOICE_TOOLS[name] = VoiceTool(
            name=name,
            fn=fn,
            description=description,
            action_kind=action_kind,
            personas=frozenset(personas) if personas else ALL_PERSONAS,
        )
        return fn

    return deco


def tools_for(persona: str | None) -> list[VoiceTool]:
    p = (persona or "").upper()
    return [t for t in VOICE_TOOLS.values() if not p or p not in ALL_PERSONAS or p in t.personas]


# ---------------------------------------------------------------------------
# JSON / integrity helpers
# ---------------------------------------------------------------------------
def to_json_safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_json_safe(asdict(obj))
    if hasattr(obj, "model_dump"):
        return to_json_safe(obj.model_dump())
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(x) for x in obj]
    return str(obj)


def _is_money_key(key: str) -> bool:
    k = key.lower()
    return k not in _KEEP_KEYS and any(m in k for m in _MONEY_KEY_MARKERS)


def strip_money(obj: Any) -> Any:
    """Recursively drop currency keys and scrub currency amounts from strings (D-1)."""
    if isinstance(obj, dict):
        return {k: strip_money(v) for k, v in obj.items() if not _is_money_key(str(k))}
    if isinstance(obj, list):
        return [strip_money(x) for x in obj]
    if isinstance(obj, str):
        return _MONEY_TEXT_RE.sub("[cost band only]", obj)
    return obj


# ---------------------------------------------------------------------------
# Declarations + execution
# ---------------------------------------------------------------------------
def _param_schema(fn: Callable[..., Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    props: dict[str, dict[str, str]] = {}
    required: list[str] = []
    for pname, p in inspect.signature(fn).parameters.items():
        if pname in ("tool_context", "self") or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        ann = p.annotation
        if isinstance(ann, str):  # from __future__ annotations
            ann = {"str": str, "int": int, "float": float, "bool": bool}.get(ann.split("|")[0].strip(), str)
        stype = _PY_TO_SCHEMA.get(ann, "STRING")
        desc = pname.replace("_", " ")
        if p.default is not inspect.Parameter.empty:
            if p.default is not None:
                desc += f" (default {p.default!r})"
        else:
            required.append(pname)
        props[pname] = {"type": stype, "description": desc}
    return props, required


def declarations_data(persona: str | None = None) -> list[dict[str, Any]]:
    """Plain-dict function declarations (testable without google-genai)."""
    out = []
    for t in tools_for(persona):
        props, required = _param_schema(t.fn)
        out.append(
            {
                "name": t.name,
                "description": t.description,
                "parameters": {"type": "OBJECT", "properties": props, "required": required},
            }
        )
    return out


def build_genai_tools(persona: str | None = None) -> list[Any]:
    """google.genai ``types.Tool`` list for LiveConnectConfig."""
    from google.genai import types

    decls = []
    for d in declarations_data(persona):
        props = {
            k: types.Schema(type=v["type"], description=v["description"])
            for k, v in d["parameters"]["properties"].items()
        }
        decls.append(
            types.FunctionDeclaration(
                name=d["name"],
                description=d["description"],
                parameters=types.Schema(type="OBJECT", properties=props, required=d["parameters"]["required"])
                if props
                else None,
            )
        )
    return [types.Tool(function_declarations=decls)] if decls else []


def execute_voice_tool(name: str, args: dict[str, Any] | None, persona: str | None = None) -> dict[str, Any]:
    """Run a registered tool synchronously; never raises (errors become a result dict)."""
    t0 = time.perf_counter()
    tool = VOICE_TOOLS.get(name)
    if tool is None:
        return {"status": "ERROR", "message": f"unknown tool {name}", "duration_ms": 0}
    if persona and persona.upper() in ALL_PERSONAS and persona.upper() not in tool.personas:
        return {"status": "UNAVAILABLE", "message": f"not permitted for persona {persona}", "duration_ms": 0}
    try:
        sig = inspect.signature(tool.fn)
        clean = {k: v for k, v in (args or {}).items() if k in sig.parameters}
        result = strip_money(to_json_safe(tool.fn(**clean)))
    except Exception as e:  # tool errors must not kill the voice session
        logger.warning("voice tool %s failed: %s: %s", name, type(e).__name__, e)
        result = {"status": "ERROR", "message": f"{type(e).__name__}: {e}"}
    if not isinstance(result, dict):
        result = {"status": "OK", "data": result}
    result.setdefault("status", "OK")
    result.setdefault("duration_ms", round((time.perf_counter() - t0) * 1000, 1))
    return result


# ---------------------------------------------------------------------------
# Import seams (resolved at call time; Stage N may replace the data layer)
# ---------------------------------------------------------------------------
def _resolve(candidates: list[tuple[str, str]]) -> Callable[..., Any] | None:
    """First importable ``module:attr`` from the list, or None."""
    for mod, attr in candidates:
        try:
            fn = getattr(importlib.import_module(mod), attr, None)
        except Exception:
            fn = None
        if callable(fn):
            return fn
    return None


def _wells() -> list[dict[str, Any]]:
    # app.api.wells re-exports whatever data source the REST API uses, so voice == screen.
    fn = _resolve([("app.api.wells", "get_all_wells")])
    if fn is None:
        raise RuntimeError("well data source unavailable")
    return list(fn())


def _find_well(well_id: str) -> dict[str, Any] | None:
    wid = (well_id or "").strip().upper().replace(" ", "")
    for w in _wells():
        if str(w.get("id", "")).upper() == wid:
            return w
    return None


def _not_found(well_id: str) -> dict[str, Any]:
    return {"status": "NOT_FOUND", "message": f"well {well_id} not found"}


# ---------------------------------------------------------------------------
# Initial registrations (Stage U). Stage T/V add TC-0xx tools via register_voice_tool.
# ---------------------------------------------------------------------------
@register_voice_tool(
    name="fleet_kpis",
    description=(
        "Fleet-level KPIs: total wells, healthy / warning / failed counts, total oil BOPD, gas MCFD, "
        "average water cut. Use for 'how is the field doing', 'kitne wells down hain'."
    ),
    action_kind="health_buckets",
)
def _v_fleet_kpis() -> Any:
    fn = _resolve([("app.api.wells", "get_fleet_kpis")])
    if fn is None:
        return {"status": "UNAVAILABLE", "message": "fleet KPIs not available"}
    return fn()


@register_voice_tool(
    name="list_problem_wells",
    description=(
        "List wells in a given status ('failed' or 'warning'), lowest oil rate first, with status reason. "
        "Use for 'which wells are down / at risk', 'sabse kharab well'."
    ),
    action_kind="priority_queue",
)
def _v_list_problem_wells(status: str = "failed", limit: int = 5) -> dict[str, Any]:
    st = (status or "failed").strip().lower()
    rows = [w for w in _wells() if str(w.get("status", "")).lower() == st]
    rows.sort(key=lambda w: (w.get("current_metrics") or {}).get("oil_bopd", 0) or 0)
    n = max(1, min(int(limit or 5), 10))
    return {
        "status": "OK",
        "filter_status": st,
        "total_matching": len(rows),
        "wells": [
            {
                "well_id": w.get("id"),
                "name": w.get("name"),
                "field": w.get("field"),
                "status": w.get("status"),
                "status_reason": w.get("status_reason") or w.get("health_reason"),
                "oil_bopd": (w.get("current_metrics") or {}).get("oil_bopd"),
                "water_cut_pct": (w.get("current_metrics") or {}).get("water_cut_pct"),
            }
            for w in rows[:n]
        ],
    }


@register_voice_tool(
    name="well_summary",
    description=(
        "Summary of one well (e.g. 'GK-129'): status, lift type, formation, current oil / gas / water cut "
        "and pressures. Use whenever the user asks about a specific well or 'this well'."
    ),
    action_kind="well_profile",
)
def _v_well_summary(well_id: str) -> dict[str, Any]:
    w = _find_well(well_id)
    if w is None:
        return _not_found(well_id)
    keep = ("id", "name", "field", "status", "status_reason", "health_bucket", "lift_type", "formation",
            "cluster_id", "spud_date", "current_metrics")
    out = {k: w[k] for k in keep if k in w}
    out["workover_count"] = len(w.get("workovers") or [])
    # ``status`` is the tool envelope status (OK/ERROR); the well's condition is ``well_health``.
    out["well_health"] = w.get("status")
    out["status"] = "OK"
    return out


@register_voice_tool(
    name="well_workovers",
    description=(
        "Workover / intervention history of one well (date, job type, findings, outcome, rig-days). "
        "Use for 'pichla workover', 'what was done on this well before'."
    ),
)
def _v_well_workovers(well_id: str, limit: int = 3) -> dict[str, Any]:
    w = _find_well(well_id)
    if w is None:
        return _not_found(well_id)
    wos = list(w.get("workovers") or [])
    wos.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return {"status": "OK", "well_id": w.get("id"), "total": len(wos), "workovers": wos[: max(1, min(int(limit or 3), 10))]}


@register_voice_tool(
    name="well_recommendation",
    description=(
        "Recommended next intervention for one well (title, urgency, action items, risk mitigation; "
        "cost as band only). Use for 'what should we do', 'kya karein', 'recommend'."
    ),
    action_kind="nba",
)
def _v_well_recommendation(well_id: str) -> dict[str, Any]:
    w = _find_well(well_id)
    if w is None:
        return _not_found(well_id)
    fn = _resolve([("app.services.ai_agent", "generate_structured_recommendation")])
    if fn is None:
        return {"status": "UNAVAILABLE", "message": "recommendation engine not available"}
    return {"status": "OK", "well_id": w.get("id"), "recommendation": fn(w)}


@register_voice_tool(
    name="compare_fields",
    description=(
        "TC-024: compare fields (Geleki, Lakwa, Lakhmani) on production vs plan / decline to find the "
        "underperforming field. Use for 'which field is underperforming', 'kaunsa field peeche hai'."
    ),
    action_kind="field_comparison",
)
def _v_compare_fields(period: str = "L12M") -> dict[str, Any]:
    fn = _resolve(
        [
            ("app.analytics.field_compare", "compare_fields"),
            ("app.analytics.fields", "compare_fields"),
            ("app.analytics", "compare_fields"),
        ]
    )
    if fn is None:
        return {"status": "UNAVAILABLE", "message": "field comparison (TC-024) is not available in this build yet"}
    try:
        return fn(period=period)
    except TypeError:
        return fn()
