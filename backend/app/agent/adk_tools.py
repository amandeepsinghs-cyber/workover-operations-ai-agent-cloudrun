"""ADK tool wrappers (SDD §12.3): thin, RBAC-gated, currency-stripped adapters over the deterministic tools.

Every wrapper follows one contract (implemented once in :func:`invoke`):

1. resolve persona + UI context from ``tool_context.state`` (set by ``runner.run_turn`` every turn);
2. ``rbac.check_call`` (capability per SDD §16.2; own-cluster scoping for FIELD_ENGINEER);
3. call the tool, wrap the ``ToolResult`` as the REST envelope ``{status, data, message, missing_fields,
   provenance}`` (SDD §13.1) plus ``tool_id``;
4. ``rbac.redact`` (FE loses ``cost_band``; ED gets a construction summary) and strip currency keys (D-1).

Wrappers never raise and never compute numbers themselves (the tools do). Docstrings are ≤ 3 lines with
routing hints because the model reads them (SDD §12.7). Signatures use only str / int / bool so ADK can
reflect them; ``well_id`` alone is enough (the prefix resolves the field, K-6).

UI artifacts are **not** recorded here: ``runner`` builds them from this invocation's
``function_response`` events only (K-4 fix — no module-level mutable state in ``agent/``).
"""

from __future__ import annotations

import inspect
import re
import time
from collections.abc import Callable
from typing import Any

from app.agent import rbac

try:  # ADK is a runtime dependency (uv add google-adk); keep import-light for unit tests of invoke()
    from google.adk.tools.tool_context import ToolContext
except ImportError:  # pragma: no cover - ADK missing
    ToolContext = Any  # type: ignore[misc,assignment]

# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
_WELL_RE = re.compile(r"^\s*(GK|LKW|LKM|GLK)[\s_\-]*0*(\d{1,4})\s*$", re.IGNORECASE)
FIELDS = ("Geleki", "Lakwa", "Lakhmani")


def norm_well_id(raw: str | None) -> str:
    """'gk 129' / 'GK129' / 'gk-129' → 'GK-129'; LKW/LKM zero-padded to three digits. '' stays ''."""
    s = (raw or "").strip()
    if not s:
        return ""
    m = _WELL_RE.match(s)
    if not m:
        return s.upper()
    return f"{m.group(1).upper()}-{int(m.group(2)):03d}"


def norm_field(raw: str | None) -> str:
    s = (raw or "").strip()
    if not s or s.upper() == "ALL":
        return ""
    for f in FIELDS:
        if f.lower() == s.lower():
            return f
    return s


def _state(tool_context: Any) -> dict[str, Any]:
    st = getattr(tool_context, "state", None)
    if st is None:
        return {}
    try:
        return {k: st.get(k) for k in ("persona", "ui_field", "ui_well_id", "ui_cluster_id", "language")}
    except Exception:  # noqa: BLE001
        return {}


def ctx_persona(tool_context: Any) -> str:
    return rbac.resolve_persona(_state(tool_context).get("persona") or rbac.current_persona())


def ctx_well(tool_context: Any, well_id: str | None) -> str:
    """Explicit id wins; else the well selected in the UI (``this well``)."""
    return norm_well_id(well_id) or norm_well_id(_state(tool_context).get("ui_well_id"))


def ctx_field(tool_context: Any, field: str | None) -> str:
    """Explicit field wins; else the field selected in the UI ('' when ALL)."""
    return norm_field(field) or norm_field(_state(tool_context).get("ui_field"))


def _strip_money(obj: Any) -> Any:
    from app.live.voice_tools import strip_money

    return strip_money(obj)


def _envelope(result: Any, tool_id: str) -> dict[str, Any]:
    from app.analytics.tools.common import ToolResult, to_jsonable

    if isinstance(result, ToolResult):
        env = result.envelope()
    elif isinstance(result, dict) and "status" in result and ("data" in result or "message" in result):
        env = dict(to_jsonable(result))
    else:
        env = {"status": "OK", "data": to_jsonable(result), "message": "", "missing_fields": [], "provenance": {}}
    env.setdefault("missing_fields", [])
    env.setdefault("provenance", {})
    env.setdefault("message", "")
    env["tool_id"] = tool_id
    return env


def invoke(
    tool_context: Any,
    *,
    tool_id: str,
    capability: str | Callable[[dict[str, Any]], str],
    fn: Callable[..., Any],
    kwargs: dict[str, Any],
    post: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate → call → envelope → redact → strip currency. Never raises."""
    t0 = time.perf_counter()
    persona = ctx_persona(tool_context)
    cap = capability(kwargs) if callable(capability) else capability
    try:
        params = set(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        params = None
    scoped, detail = rbac.check_call(persona, cap, dict(kwargs), params)
    if detail is not None:
        env = rbac.denied_envelope(persona, cap, detail)
        env["tool_id"] = tool_id
        return env
    call_kwargs = {k: v for k, v in scoped.items() if params is None or k in params}
    try:
        env = _envelope(fn(**call_kwargs), tool_id)
    except Exception as e:  # noqa: BLE001 - a tool failure must reach the model as a status, not a crash
        env = {"status": "UNAVAILABLE", "data": None, "message": f"tool error: {type(e).__name__}: {e}",
               "missing_fields": [], "provenance": {"tool_id": tool_id}, "tool_id": tool_id}
    env = rbac.redact(persona, cap, env)
    env = _strip_money(env)
    if post is not None and env.get("status") != "UNAVAILABLE":
        try:
            env = post(env)
        except Exception:  # noqa: BLE001, S110 - post-processing is cosmetic (payload trimming)
            pass
    env.setdefault("provenance", {})
    if isinstance(env["provenance"], dict):
        env["provenance"].setdefault("wrapper_ms", round((time.perf_counter() - t0) * 1000, 1))
    return env


def _missing(tool_id: str, field_name: str, message: str) -> dict[str, Any]:
    return {"status": "UNAVAILABLE", "data": None, "message": message, "missing_fields": [field_name],
            "provenance": {"tool_id": tool_id}, "tool_id": tool_id}


# --------------------------------------------------------------------------------------------------
# L1–L5 core wrappers (orchestrator-written). Names match BDD-F18-S01 "required tool calls".
# --------------------------------------------------------------------------------------------------
def field_production_history(fields: str = "", freq: str = "M", plot: bool = False,
                             tool_context: ToolContext = None) -> dict:
    """TC-028 L1: field-wise production history (default all 3 fields, 60 months): start vs end oil, gas, water cut,
    producing wells. Use for '5 year production field-wise'. Tell the numbers first; set plot=true ONLY when the
    user asks for a plot / chart / graph."""
    from app.analytics.tools.field_history import field_production_history as tc028

    return invoke(tool_context, tool_id="TC-028", capability="field.aggregate", fn=tc028,
                  kwargs={"fields": fields or None, "freq": (freq or "M").upper()})


def compare_fields(period: str = "QTD", tool_context: ToolContext = None) -> dict:
    """TC-024: which field is not performing? Ranks Geleki, Lakwa, Lakhmani by gap to target (QTD|MTD|YTD|L12M)
    with uptime, water cut, health counts and the worst field's top loss driver."""
    from app.analytics.tools.field_performance import compare_fields as tc024

    return invoke(tool_context, tool_id="TC-024", capability="field.aggregate", fn=tc024,
                  kwargs={"period": (period or "QTD").upper()})


def classify_well_health(field: str = "", cluster_id: str = "", tool_context: ToolContext = None) -> dict:
    """TC-020 L2: how many wells in a field are OK / AT_RISK / UNDERPERFORMING / NOT_PRODUCING.
    'Sick or lost production' = AT_RISK + UNDERPERFORMING (sick_or_lost_count); NOT_PRODUCING is separate."""
    from app.analytics.tools.health import classify_well_health as tc020

    f = ctx_field(tool_context, field)
    if not f:
        return _missing("TC-020", "field", "Which field? Geleki, Lakwa or Lakhmani.")
    cl = (cluster_id or "").strip() or (_state(tool_context).get("ui_cluster_id") or "")
    return invoke(tool_context, tool_id="TC-020", capability="field.health", fn=tc020,
                  kwargs={"field": f, "cluster_id": cl or None, "well_id": ctx_well(tool_context, "")},
                  post=_health_post)


def _health_post(env: dict) -> dict:
    data = env.get("data")
    if isinstance(data, dict) and isinstance(data.get("wells"), list):
        flagged = [w for w in data["wells"] if w.get("bucket") != "PRODUCING_OK"]
        data["flagged_wells"] = flagged
        data.pop("wells")  # OK wells are not needed by the model / the card (counts carry them)
    return env


def attribute_decline(well_id: str = "", field: str = "", cluster_id: str = "", window_days: int = 180,
                      tool_context: ToolContext = None) -> dict:
    """TC-019: why did production decline? Lost oil split into SUBSURFACE / EQUIPMENT / OPERATIONAL / HUMAN_PROCESS
    (a function's delay, never a person) / EXTERNAL / UNEXPLAINED with controllable share. well_id for one well,
    or field (optional cluster_id) for the field factor breakdown."""
    from app.analytics.tools.attribution import attribute_decline as tc019

    wid = norm_well_id(well_id)
    f = norm_field(field)
    if not wid and not f:  # neither given → UI context: selected well, else selected field
        wid = ctx_well(tool_context, "")
        f = "" if wid else ctx_field(tool_context, "")
    if not wid and not f:
        return _missing("TC-019", "well_id", "Give a well (e.g. GK-129) or a field.")
    return invoke(tool_context, tool_id="TC-019", capability=rbac.attribution_capability, fn=tc019,
                  kwargs={"well_id": wid or None, "field": f or None, "cluster_id": (cluster_id or "").strip() or None,
                          "window_days": int(window_days or 180)})


def rank_candidates(field: str = "", queue: str = "all", limit: int = 15, tool_context: ToolContext = None) -> dict:
    """TC-010 L3: priority list of wells that need intervention (rig and rigless queues) ranked by deferred barrels
    recovered x p_success / rig-days, with cost band and rig-days (never money). queue = rig | rigless | all."""
    from app.analytics.tools.candidate_ranking import rank_candidates as tc010

    f = ctx_field(tool_context, field)
    if not f:
        return _missing("TC-010", "field", "Which field? Geleki, Lakwa or Lakhmani.")
    q = (queue or "all").lower()
    n = max(1, min(int(limit or 15), 50))

    def post(env: dict) -> dict:
        d = env.get("data")
        if isinstance(d, dict):
            for key in ("rig_queue", "rigless_queue"):
                rows = d.get(key)
                if isinstance(rows, list):
                    d[f"{key}_total"] = len(rows)
                    keep = (q == "all") or key.startswith(q)
                    d[key] = rows[:n] if keep else []
        return env

    return invoke(tool_context, tool_id="TC-010", capability="queue.read", fn=tc010,
                  kwargs={"field": f, "well_id": ctx_well(tool_context, "")}, post=post)


def well_profile(well_id: str = "", k_neighbours: int = 4, tool_context: ToolContext = None) -> dict:
    """TC-029 L4: tell me about one well: zone, lift, construction (casing / tubing / perfs), status, health bucket,
    last test, last pressure survey and nearby wells (distance, bucket, oil rate, decline residual)."""
    from app.analytics.tools.well_profile import well_profile as tc029

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-029", "well_id", "Which well? e.g. GK-129.")
    return invoke(tool_context, tool_id="TC-029", capability="well.construction", fn=tc029,
                  kwargs={"well_id": wid, "k_neighbours": int(k_neighbours or 4)})


def plot_production(well_id: str = "", months: int = 36, metrics: str = "oil,water_cut",
                    tool_context: ToolContext = None) -> dict:
    """TC-017 L4: one well's production history (months 24 | 36 | 60) with a marker for every intervention
    (job, outcome, document) plus older 'historical' interventions. metrics e.g. 'oil,water_cut,gas,gor,wht'."""
    from app.analytics.tools.well_profile import well_production_series as tc017

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-017", "well_id", "Which well? e.g. GK-129.")
    mets = [m.strip() for m in (metrics or "oil,water_cut").split(",") if m.strip()]
    return invoke(tool_context, tool_id="TC-017", capability="asset.overview", fn=tc017,
                  kwargs={"well_id": wid, "months": int(months or 36), "metrics": mets})


def recommend_next_best_action(well_id: str = "", top_k: int = 3, tool_context: ToolContext = None) -> dict:
    """TC-022 L5: ranked next best interventions for one well (job, uplift BOPD, deferred bbl 12 mo, p_success with n,
    rig-days, cost band, rig slot, risk flags, SOP) and rejected jobs with reasons. May say NO_JOB_JUSTIFIED."""
    from app.analytics.tools.nba import recommend_next_best_action as tc022

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-022", "well_id", "Which well? e.g. GK-129.")

    def post(env: dict) -> dict:
        d = env.get("data")
        if isinstance(d, dict):
            d.pop("job_menu", None)
            try:  # v0.5 (D-32): multimodal success engine ranking, analogs and drivers for the spoken answer
                from app.analytics.tools.success_engine import compact_summary
                d["multimodal"] = compact_summary(wid)
            except Exception:  # noqa: BLE001 - never break TC-022 on the decoration
                pass
        return env

    return invoke(tool_context, tool_id="TC-022", capability="well.nba", fn=tc022,
                  kwargs={"well_id": wid, "top_k": int(top_k or 3)}, post=post)


def compare_interventions(alternative: str, well_id: str = "", recommended: str = "",
                          tool_context: ToolContext = None) -> dict:
    """TC-027 L5: why the recommended job and not an alternative ('why not wax removal?'). Six-dimension table,
    verdict, deciding dimension, cited prior jobs. alternative e.g. WAX_REMOVAL, REPERFORATION; recommended
    defaults to the TC-022 rank-1 job."""
    from app.analytics.tools.counterfactual import compare_interventions as tc027

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-027", "well_id", "Which well? e.g. GK-129.")
    if not (alternative or "").strip():
        return _missing("TC-027", "alternative", "Which alternative job? e.g. WAX_REMOVAL.")
    return invoke(tool_context, tool_id="TC-027", capability="well.nba", fn=tc027,
                  kwargs={"well_id": wid, "recommended_job": (recommended or "").strip() or None,
                          "alternative_job": alternative.strip()})


def build_well_dossier(well_id: str = "", tool_context: ToolContext = None) -> dict:
    """TC-023: field-dispatch history pack / dossier PDF for one well ('I'm going to the field', 'history pack',
    'dossier'): sections, three highlights, sources and the PDF link."""
    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-023", "well_id", "Which well? e.g. GK-129.")
    try:
        from app.analytics.tools.dossier import build_well_dossier as tc023
    except ImportError:  # Stage S module not present in this build
        return _missing("TC-023", "dossier", "Dossier builder (TC-023) is not available in this build.")
    return invoke(tool_context, tool_id="TC-023", capability="docs.sop_dossier", fn=tc023,
                  kwargs={"well_id": wid, "persona": ctx_persona(tool_context), "refresh": False})


def search_documents(query: str, well_id: str = "", field: str = "", doc_types: str = "", top_k: int = 5,
                     tool_context: ToolContext = None) -> dict:
    """TC-026: search the PDF corpus (completion, workover, pressure, lab, chemical, SOP …) and return cited hits
    (doc_id, title, page, snippet, link). doc_types e.g. 'D02,D11' (D11 = SOPs)."""
    from app.analytics.docs_pdf.store import get_store, norm_doc_types

    persona = ctx_persona(tool_context)
    wid = norm_well_id(well_id)
    f = norm_field(field)

    def tc026(query: str, well_id: str | None, field: str | None, doc_types: list[str] | None, top_k: int):
        store = get_store()
        if store is None:
            return {"status": "UNAVAILABLE", "data": [], "message": "document index not built",
                    "missing_fields": ["document_index"], "provenance": {"tool_id": "TC-026"}}
        types = rbac.allowed_doc_types(persona, doc_types)
        hits = store.search(query, well_id=well_id, field=field, doc_types=types, top_k=top_k)
        return {"status": "OK" if hits else "LOW_CONFIDENCE", "data": hits,
                "message": f"{len(hits)} document(s) matched" if hits else "no document matched",
                "missing_fields": [], "provenance": store.provenance() | {"query": query}}

    return invoke(tool_context, tool_id="TC-026", capability="docs.sop_dossier", fn=tc026,
                  kwargs={"query": query, "well_id": wid or None, "field": f or None,
                          "doc_types": norm_doc_types(doc_types or None), "top_k": max(1, min(int(top_k or 5), 10))})


CORE_TOOLS: list[Callable[..., dict]] = [
    field_production_history,    # TC-028  L1
    compare_fields,              # TC-024
    classify_well_health,        # TC-020  L2
    attribute_decline,           # TC-019  L2
    rank_candidates,             # TC-010  L3
    well_profile,                # TC-029  L4
    plot_production,             # TC-017  L4
    recommend_next_best_action,  # TC-022  L5
    compare_interventions,       # TC-027  L5
    build_well_dossier,          # TC-023
    search_documents,            # TC-026
]


def _ext_tools() -> list[Callable[..., dict]]:
    try:
        from app.agent.adk_tools_ext import EXT_TOOLS
    except ImportError:
        return []
    return list(EXT_TOOLS)


ALL: list[Callable[..., dict]] = CORE_TOOLS + _ext_tools()
TOOLS_BY_NAME: dict[str, Callable[..., dict]] = {t.__name__: t for t in ALL}
