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
    # Stage Y: the persona filter comes from the RBAC matrix (app/agent/rbac.py); unmapped tools fall back
    # to their registered ``personas`` set.
    from app.agent import rbac

    return [t for t in VOICE_TOOLS.values() if rbac.voice_tool_visible(t.name, persona, t.personas)]


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
    from app.agent import rbac  # Stage Y: tool-layer gating (SDD §16), not the prompt

    sig = inspect.signature(tool.fn)
    args, denial, cap = rbac.voice_gate(name, args, persona, tool.personas, set(sig.parameters))
    if denial is not None:
        return {**denial, "duration_ms": 0}
    try:
        clean = {k: v for k, v in (args or {}).items() if k in sig.parameters}
        result = strip_money(to_json_safe(tool.fn(**clean)))
        if persona:
            result = rbac.redact(persona, cap, result)
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


# ---------------------------------------------------------------------------
# Stage P: TC-019 / TC-020 (SDD §6.2, §11.3). Thin wrappers — the numbers come from the tools.
# ---------------------------------------------------------------------------
def _envelope_for_voice(r: Any, max_wells: int = 5) -> dict[str, Any]:
    env = r.envelope()
    data = env.get("data")
    if isinstance(data, dict) and isinstance(data.get("wells"), list) and len(data["wells"]) > max_wells:
        data["wells_total"] = len(data["wells"])
        data["wells"] = data["wells"][:max_wells]  # voice payload: worst wells only (full list on screen)
    return env


@register_voice_tool(
    name="attribute_decline",
    description=(
        "TC-019: why did production decline? Splits lost oil over a window (default 180 days) into "
        "SUBSURFACE, EQUIPMENT, OPERATIONAL, HUMAN_PROCESS (a delay owned by a function, never a person), "
        "EXTERNAL and UNEXPLAINED, with barrels, % and controllable share. Give well_id (e.g. 'LKW-047') "
        "for one well, or field (optionally cluster_id) for a field rollup. Use for 'why did it decline', "
        "'human factor or controllable', 'production kyun gira'."
    ),
    action_kind="attribution_waterfall",
)
def _v_attribute_decline(well_id: str = "", field: str = "", cluster_id: str = "", window_days: int = 180) -> dict[str, Any]:
    from app.analytics.tools.attribution import attribute_decline

    return _envelope_for_voice(attribute_decline(well_id=well_id or None, field=field or None,
                                                 cluster_id=cluster_id or None, window_days=int(window_days or 180)))


@register_voice_tool(
    name="classify_well_health",
    description=(
        "TC-020: which wells are OK, at risk, underperforming or not producing in a field (Geleki, Lakwa, "
        "Lakhmani), optionally one cluster. 'Sick or lost production' = AT_RISK + UNDERPERFORMING. Use for "
        "'how many wells are sick', 'kitne wells band hain', 'which wells are not producing'."
    ),
    action_kind="health_buckets",
)
def _v_classify_well_health(field: str, cluster_id: str = "") -> dict[str, Any]:
    from app.analytics.tools.health import classify_well_health

    env = classify_well_health(field, cluster_id=cluster_id or None).envelope()
    data = env.get("data")
    if isinstance(data, dict) and isinstance(data.get("wells"), list):
        flagged = [w for w in data["wells"] if w.get("bucket") != "PRODUCING_OK"]
        data["wells_total"] = len(data["wells"])
        data["wells"] = flagged[:10]  # voice payload: non-OK wells only, first 10
    return env


# ---------------------------------------------------------------------------
# Stage T: TC-024 / TC-028 / TC-029 (+ TC-017 v2 markers). Thin wrappers — the numbers come from the tools.
# ``compare_fields`` re-registers the Stage U placeholder name (last registration wins) so the registry
# count is unchanged; it now resolves to TC-024 directly instead of the lazy lookup path.
# ---------------------------------------------------------------------------
@register_voice_tool(
    name="compare_fields",
    description=(
        "TC-024: which field is not performing? Ranks Geleki, Lakwa, Lakhmani by gap to target (period QTD, "
        "MTD, YTD or L12M; default QTD) with actual vs target BOPD, uptime, water cut, health counts, active "
        "interventions, rig / rigless candidates and the worst field's top loss driver (factor class, "
        "controllable or not). Use for 'which field is underperforming', 'kaunsa field peeche hai'."
    ),
    action_kind="field_comparison",
    personas={"ED", "ASSET_MANAGER"},
)
def _v_compare_fields_tc024(period: str = "QTD") -> dict[str, Any]:
    from app.analytics.tools.field_performance import compare_fields

    return compare_fields(period=(period or "QTD").upper()).envelope()


@register_voice_tool(
    name="field_production_history",
    description=(
        "TC-028: field-wise production history (default all three fields, 60 months to as-of): per field start "
        "vs end oil BOPD and % change, gas start vs end, water-cut change (pp) and producing wells. Tell these "
        "numbers first; the plot opens only if the user asks for it. Use for '5 year production field-wise', "
        "'pichle paanch saal ka production'."
    ),
    action_kind="field_history_chart",
    personas={"ED", "ASSET_MANAGER"},
)
def _v_field_production_history(fields: str = "", freq: str = "M") -> dict[str, Any]:
    from app.analytics.tools.field_history import field_production_history

    env = field_production_history(fields=fields or None, freq=(freq or "M").upper()).envelope()
    data = env.get("data")
    if isinstance(data, dict) and isinstance(data.get("series"), list):
        data["series_rows"] = len(data["series"])
        data.pop("series")  # voice payload: summary only (full monthly series is on screen / in the chart)
    return env


@register_voice_tool(
    name="well_profile",
    description=(
        "TC-029 + TC-017: tell me about one well (e.g. 'GK-129'): zone / formation, lift type, casing and tubing "
        "sizes, lithology, health bucket, current rate, decline residual, last test and pressure survey, the "
        "interventions in the last `months` (24 / 36 / 60; job, date, outcome) and nearby wells in the same "
        "cluster with bucket, rate and decline residual. Use for 'tell me more about this well', 'history', "
        "'nearby wells', 'is well ke aas paas'."
    ),
    action_kind="well_profile",
)
def _v_well_profile(well_id: str, months: int = 36) -> dict[str, Any]:
    from app.analytics.tools.well_profile import well_production_series, well_profile

    env = well_profile(well_id).envelope()
    data = env.get("data")
    if isinstance(data, dict):
        c = data.get("construction") or {}
        data["construction"] = {
            "casing": [{k: s.get(k) for k in ("string_type", "od_in", "grade", "shoe_m")} for s in c.get("casing", [])],
            "tubing_size_in": c.get("tubing_size_in"), "casing_size_in": c.get("casing_size_in"),
            "perfs": c.get("perfs", []),
        }
        prod = well_production_series(well_id, months=int(months or 36), metrics=["oil"],
                                      overlay_decline_fit=False).envelope()
        pd_ = prod.get("data") or {}
        data["interventions_in_window"] = [
            {k: m.get(k) for k in ("date", "job_code", "job_name", "outcome", "rig_days", "doc_id")}
            for m in pd_.get("interventions", [])]
        data["historical_interventions"] = pd_.get("historical_interventions", [])
        data["history_window"] = {"months": pd_.get("months"), "start": pd_.get("window_start"),
                                  "end": pd_.get("window_end")}
    return env


# ---------------------------------------------------------------------------
# Stage Q: TC-021 ML intervention classifier (SDD §8, BDD-F03-S03/S06). Quality numbers come from
# analytics/model/intervention_classifier_metrics.json via the tool, never from the prompt.
# ---------------------------------------------------------------------------
@register_voice_tool(
    name="classify_intervention",
    description=(
        "TC-021: which of 15 intervention types (IC-01..IC-15) the ML model predicts for a well, with the top-3 "
        "calibrated probabilities, the main driving signals (direction up/down) and the model's holdout quality. "
        "Give well_id (e.g. 'LKM-023'). Leave well_id empty to get only the model-quality card (holdout macro-F1, "
        "top-3 accuracy, rule-baseline macro-F1, synthetic-data disclosure). Use for 'what job does this well need', "
        "'how good is this model / can I trust it', 'ESP replacement' (maps to IC-08; no ESP wells in the data), "
        "'kaunsa intervention chahiye'."
    ),
    action_kind="intervention_classification",
)
def _v_classify_intervention(well_id: str = "", top_k: int = 3) -> dict[str, Any]:
    from app.analytics.tools.intervention_classifier import classify_intervention, model_quality

    if not well_id:
        return model_quality().envelope()
    env = classify_intervention(well_id=well_id.strip().upper(), top_k=int(top_k or 3)).envelope()
    env["model_quality"] = model_quality().envelope().get("data")
    return env


# ---------------------------------------------------------------------------
# Stage R: TC-022 next best action + TC-027 counterfactual (SDD §9.1/9.2). Cost as band + rig-days only.
# Registry is now 13 tools (> SDD §11.3's 12): Stage V trims the legacy well_summary / well_workovers /
# well_recommendation tools (well_recommendation is now TC-022 rank-1 anyway).
# ---------------------------------------------------------------------------
@register_voice_tool(
    name="next_best_action",
    description=(
        "TC-022: ranked next best actions for one well (job, intervention class, diagnostic fit, uplift BOPD, "
        "deferred bbl over 12 months, p_success, rig-days, cost band, earliest rig slot, risk flags, SOP id), the "
        "physics route vs the ML suggestion, guardrail flags (coning -> choke back; reservoir decline -> no job) "
        "and rejected candidates with reasons. Use for 'what should we do on GK-129', 'next best action', "
        "'kya karein', 'kaunsa job'."
    ),
    action_kind="nba",
)
def _v_next_best_action(well_id: str, top_k: int = 3) -> dict[str, Any]:
    from app.analytics.tools.nba import recommend_next_best_action

    env = recommend_next_best_action(well_id.strip().upper(), top_k=int(top_k or 3)).envelope()
    data = env.get("data")
    if isinstance(data, dict):
        data.pop("job_menu", None)  # UI picker only; keep the voice payload small
        for a in data.get("actions") or []:
            a["sop_phases"] = [p.get("phase") for p in a.pop("sop_steps", None) or [] if p.get("phase")]
    return env


@register_voice_tool(
    name="compare_interventions",
    description=(
        "TC-027: why the recommended job and not an alternative, for one well. Side-by-side on diagnostic fit "
        "(incl. latest pressure survey), this well's history, field efficacy, execution (rig-days, cost band, "
        "rig slot) and value, with a verdict, the deciding dimension and cited prior-job documents. Give "
        "well_id and alternative (e.g. 'WAX_REMOVAL', 'REPERFORATION', 'IC-04'); recommended defaults to the "
        "TC-022 rank-1 job. Use for 'why not wax removal', 'squeeze ki jagah reperf kyun nahi'."
    ),
    action_kind="counterfactual",
)
def _v_compare_interventions(well_id: str, alternative: str, recommended: str = "") -> dict[str, Any]:
    from app.analytics.tools.counterfactual import compare_interventions

    return compare_interventions(well_id.strip().upper(), recommended_job=recommended or None,
                                 alternative_job=alternative).envelope()
