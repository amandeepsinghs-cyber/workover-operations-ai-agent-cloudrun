"""Extended ADK tool wrappers (SDD §12.3, Stage V).

Provides 19 thin, RBAC-gated wrappers covering TC-001..TC-009, TC-011, TC-013..TC-016, TC-018, TC-021,
TC-025, and document/SOP helpers (TC-026). All wrappers follow the contract established in
``app.agent.adk_tools``: str/int/bool arguments, lazy imports, RBAC gating via :func:`invoke`,
currency stripping, and concise docstrings for model routing.
"""

from __future__ import annotations

import datetime
import re
import sys
from collections.abc import Callable

from app.agent import rbac
from app.agent.adk_tools import (
    ToolContext,
    _missing,
    ctx_field,
    ctx_persona,
    ctx_well,
    invoke,
    norm_well_id,
)

# --------------------------------------------------------------------------------------------------
# Post-processing helpers for payload trimming
# --------------------------------------------------------------------------------------------------


def _fit_decline_post(env: dict) -> dict:
    data = env.get("data")
    if isinstance(data, dict):
        rs = data.get("residual_series")
        if isinstance(rs, list) and len(rs) > 60:
            data["residual_series_len"] = len(rs)
            data.pop("residual_series", None)
    return env


def _trigger_scan_post(env: dict) -> dict:
    data = env.get("data")
    if isinstance(data, list):
        fired = [r for r in data if isinstance(r, dict) and r.get("any_fired")]
        env["data"] = {
            "n_scanned": len(data),
            "n_fired": len(fired),
            "triggers": fired[:25],
        }
    elif isinstance(data, dict):
        rows = data.get("triggers") or data.get("rows")
        if isinstance(rows, list):
            fired = [r for r in rows if isinstance(r, dict) and r.get("any_fired")]
            data["n_scanned"] = len(rows)
            data["n_fired"] = len(fired)
            data["triggers"] = fired[:25]
    return env


def _map_post(env: dict) -> dict:
    data = env.get("data")
    if isinstance(data, dict):
        points = data.get("points")
        if isinstance(points, list):
            data["n_points"] = len(points)
            if len(points) > 50:
                data.pop("boundaries", None)
                data.pop("geojson", None)
                data.pop("cluster_polygons", None)
    return env


# --------------------------------------------------------------------------------------------------
# 19 Extended tool wrappers
# --------------------------------------------------------------------------------------------------


def fit_decline_curve(
    well_id: str = "",
    lookback_months: int = 36,
    tool_context: ToolContext = None,
) -> dict:
    """TC-001: fit hyperbolic/exponential Arps decline curve for one well (qi, b, Di, r², expected vs actual BOPD).
    Use for 'decline curve', 'decline rate', 'Arps fit', or 'production forecast' for a well."""
    from app.analytics.tools.arps_decline import fit_decline_curve as tc001

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-001", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-001",
        capability="well.diagnostics",
        fn=tc001,
        kwargs={"well_id": wid, "lookback_months": int(lookback_months or 36)},
        post=_fit_decline_post,
    )


def chan_diagnostic(
    well_id: str = "",
    window_days: int = 90,
    tool_context: ToolContext = None,
) -> dict:
    """TC-002: water-cut diagnostic (Chan log WOR and WOR' derivative plot slope) to identify water mechanisms.
    Distinguishes CHANNELLING (rapid channeling / breakthrough) from BOTTOM_WATER_CONING or NORMAL_CONING."""
    from app.analytics.tools.chan_diagnostic import chan_diagnostic as tc002

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-002", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-002",
        capability="well.diagnostics",
        fn=tc002,
        kwargs={"well_id": wid, "window_days": int(window_days or 90)},
    )


def fillage_proxy(
    well_id: str = "",
    window_days: int = 30,
    tool_context: ToolContext = None,
) -> dict:
    """TC-003: sucker rod pump (SRP) pump fillage and volumetric efficiency proxy from gross production and SPM.
    Identifies fluid pound, incomplete pump fillage, or gas interference for rod-pumped wells."""
    from app.analytics.tools.candidate_ranking import fillage_proxy as tc003

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-003", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-003",
        capability="well.diagnostics",
        fn=tc003,
        kwargs={"well_id": wid, "window_days": int(window_days or 30)},
    )


def check_offsets(
    well_id: str = "",
    k: int = 6,
    tool_context: ToolContext = None,
) -> dict:
    """TC-004: compare well decline against k nearest same-zone offset wells to test reservoir vs well-specific decline.
    Verdicts: WELL_SPECIFIC (well problem), RESERVOIR_DECLINE (shared field decline), MIXED, or INSUFFICIENT."""
    from app.analytics.tools.candidate_ranking import check_offsets as tc004

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-004", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-004",
        capability="well.diagnostics",
        fn=tc004,
        kwargs={"well_id": wid, "k": int(k or 6)},
    )


def detect_mechanical_signature(
    well_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-005: detect downhole mechanical failure signatures (tubing leak, parting, pump wear, valve leakage).
    Evaluates high-frequency sensor and test trends to pinpoint mechanical versus reservoir decline."""
    from app.analytics.tools.candidate_ranking import (
        detect_mechanical_signature as tc005,
    )

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-005", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-005",
        capability="well.diagnostics",
        fn=tc005,
        kwargs={"well_id": wid},
    )


def predict_failure(
    well_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-006: Cox proportional hazards run-life survival model predicting estimated time to failure (ETTF days).
    Evaluates current run duration, historical run lives, and partial hazard for sucker rod pump wells."""
    from app.analytics.tools.candidate_ranking import predict_failure as tc006

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-006", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-006",
        capability="well.diagnostics",
        fn=tc006,
        kwargs={"well_id": wid},
    )


def trigger_scan(
    field: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-007: scan all active wells in a field against diagnostic triggers (A: decline, B: run life, C: alarms, D: hazard).
    Identifies candidate wells with fired triggers needing intervention screening."""
    from app.analytics.tools.candidate_ranking import trigger_scan as tc007

    f = ctx_field(tool_context, field)
    if not f:
        return _missing("TC-007", "field", "Which field? Geleki, Lakwa or Lakhmani.")
    return invoke(
        tool_context,
        tool_id="TC-007",
        capability="well.diagnostics",
        fn=tc007,
        kwargs={"field": f},
        post=_trigger_scan_post,
    )


def route_intervention(
    mechanism: str,
    offset_verdict: str = "ISOLATED",
    well_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-008: route diagnosed decline mechanism to candidate intervention jobs and primary route.
    Valid offset_verdict values: WELL_SPECIFIC (or ISOLATED), RESERVOIR_DECLINE, MIXED, INSUFFICIENT."""
    from app.analytics.tools.candidate_ranking import route_intervention as tc008

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-008", "well_id", "Which well? e.g. GK-129.")
    mech = (mechanism or "").strip()
    if not mech:
        return _missing("TC-008", "mechanism", "Which decline mechanism? e.g. WAX, CHANNELLING, SCALE, SAND.")
    ov = (offset_verdict or "WELL_SPECIFIC").strip().upper()
    if ov == "ISOLATED":
        ov = "WELL_SPECIFIC"
    return invoke(
        tool_context,
        tool_id="TC-008",
        capability="well.diagnostics",
        fn=tc008,
        kwargs={"well_id": wid, "mechanism": mech, "offset_verdict": ov},
    )


def estimate_uplift(
    job_code: str,
    well_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-009: estimate production uplift (BOPD increase, 12-month cumulative barrels, P(success)) for a job code.
    Use for 'uplift', 'incremental oil', or 'production gain' for jobs like WAX_HOTOIL, MATRIX_ACID, etc."""
    from app.analytics.tools.candidate_ranking import estimate_uplift as tc009

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-009", "well_id", "Which well? e.g. GK-129.")
    jc = (job_code or "").strip().upper()
    if not jc:
        return _missing("TC-009", "job_code", "Which job code? e.g. WAX_HOTOIL, MATRIX_ACID.")
    if jc == "WAX_REMOVAL":
        jc = "WAX_HOTOIL"
    return invoke(
        tool_context,
        tool_id="TC-009",
        capability="well.diagnostics",
        fn=tc009,
        kwargs={"well_id": wid, "job_code": jc},
    )


def check_mro(
    job_code: str,
    required_date: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-011: check maintenance, repair, and operations (MRO) spare parts and long-lead material availability.
    Evaluates inventory, procurement lead time, and blockers for jobs like WAX_HOTOIL, PUMP_OVERHAUL, etc."""
    from app.analytics.tools.candidate_ranking import check_mro as tc011

    jc = (job_code or "").strip().upper()
    if not jc:
        return _missing("TC-011", "job_code", "Which job code? e.g. WAX_HOTOIL, PUMP_OVERHAUL.")
    if jc == "WAX_REMOVAL":
        jc = "WAX_HOTOIL"
    req_d = None
    if required_date:
        try:
            req_d = datetime.date.fromisoformat(required_date.strip())
        except (ValueError, TypeError):
            req_d = None
    return invoke(
        tool_context,
        tool_id="TC-011",
        capability="well.nba",
        fn=tc011,
        kwargs={"job_code": jc, "required_date": req_d},
    )


def generate_draft_plan(
    well_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-013: generate comprehensive draft intervention plan (summary, diagnostic evidence, MRO, SOP, risks).
    Compiles complete workover / intervention justification package in AWAITING REVIEW status."""
    from app.analytics.tools.candidate_ranking import generate_draft_plan as tc013

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-013", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-013",
        capability="well.nba",
        fn=tc013,
        kwargs={"well_id": wid},
    )


def generate_report(
    field: str = "",
    period: str = "WEEKLY",
    tool_context: ToolContext = None,
) -> dict:
    """TC-014: generate field production allocation and operations report (DAILY, WEEKLY, or MONTHLY).
    Summarizes producing wells, field production, target variance, and active candidate counts."""
    from app.analytics.tools.candidate_ranking import generate_report as tc014

    f = ctx_field(tool_context, field)
    if not f:
        return _missing("TC-014", "field", "Which field? Geleki, Lakwa or Lakhmani.")
    p = (period or "WEEKLY").strip().upper()
    if p not in ("DAILY", "WEEKLY", "MONTHLY"):
        p = "WEEKLY"
    return invoke(
        tool_context,
        tool_id="TC-014",
        capability="queue.read",
        fn=tc014,
        kwargs={"field": f, "period": p, "well_id": ctx_well(tool_context, "")},
    )


def schedule_rigs(
    field: str = "",
    horizon_days: int = 30,
    tool_context: ToolContext = None,
) -> dict:
    """TC-015: schedule workover rigs and surface crews for queued candidate wells over a planning horizon.
    Optimizes rig allocation, mobilization, and sequence to maximize barrels recovered."""
    from app.analytics.tools.candidate_ranking import schedule_rigs as tc015

    f = ctx_field(tool_context, field)
    if not f:
        return _missing("TC-015", "field", "Which field? Geleki, Lakwa or Lakhmani.")
    return invoke(
        tool_context,
        tool_id="TC-015",
        capability="queue.read",
        fn=tc015,
        kwargs={
            "field": f,
            "horizon_days": int(horizon_days or 30),
            "well_id": ctx_well(tool_context, ""),
        },
    )


def query_wells(
    field: str = "",
    order_by: str = "decline_residual_pct",
    direction: str = "ASC",
    limit: int = 10,
    tool_context: ToolContext = None,
) -> dict:
    """TC-018: query and rank wells in a field. Valid order_by: oil_rate_bopd, decline_residual_pct, deferred_bopd,
    days_to_failure, water_cut_pct. Use oil_rate_bopd ASC for 'lowest producers', deferred_bopd DESC for highest loss."""
    from app.analytics.tools.candidate_ranking import query_wells as tc018

    f = ctx_field(tool_context, field)
    if not f:
        return _missing("TC-018", "field", "Which field? Geleki, Lakwa or Lakhmani.")
    valid_orders = {"oil_rate_bopd", "decline_residual_pct", "deferred_bopd", "days_to_failure", "water_cut_pct"}
    ob = (order_by or "decline_residual_pct").strip().lower()
    if ob not in valid_orders:
        ob = "decline_residual_pct"
    dir_norm = "DESC" if (direction or "").strip().upper() == "DESC" else "ASC"
    n = max(1, min(int(limit or 10), 100))
    return invoke(
        tool_context,
        tool_id="TC-018",
        capability="queue.read",
        fn=tc018,
        kwargs={
            "field": f,
            "order_by": ob,
            "direction": dir_norm,
            "limit": n,
            "well_id": ctx_well(tool_context, ""),
        },
    )


def render_well_map(
    field: str = "",
    cluster_id: str = "",
    highlight_well_ids: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-016: geospatial well map with coordinates, health status colors, surface facilities, and cluster boundaries.
    field or cluster_id to filter; highlight_well_ids as comma-separated IDs to highlight."""
    from app.analytics.tools.render_well_map import render_well_map as tc016

    f = ctx_field(tool_context, field)
    cl = (cluster_id or "").strip()
    hl_list = None
    if highlight_well_ids:
        hl_list = [norm_well_id(x) for x in highlight_well_ids.split(",") if norm_well_id(x)]
        if not hl_list:
            hl_list = None
    return invoke(
        tool_context,
        tool_id="TC-016",
        capability="asset.overview",
        fn=tc016,
        kwargs={"field": f or None, "cluster_id": cl or None, "highlight_well_ids": hl_list},
        post=_map_post,
    )


def query_hierarchy(
    field: str = "",
    cluster_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-025: asset hierarchy showing fields, production installations, drill sites, clusters, and well counts.
    Use for organizational overview, field boundaries, or cluster facility rollups."""
    from app.analytics.tools.hierarchy import query_hierarchy as tc025

    f = ctx_field(tool_context, field)
    cl = (cluster_id or "").strip()
    return invoke(
        tool_context,
        tool_id="TC-025",
        capability="asset.overview",
        fn=tc025,
        kwargs={"field": f or None, "cluster_id": cl or None},
    )


def classify_intervention(
    well_id: str = "",
    top_k: int = 3,
    tool_context: ToolContext = None,
) -> dict:
    """TC-021: which of 15 intervention classes the ML model predicts; leave well_id empty for model quality
    / can I trust the model (model card: holdout macro-F1, synthetic disclosure)."""
    from app.analytics.tools import intervention_classifier as ic

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return invoke(
            tool_context,
            tool_id="TC-021",
            capability="well.diagnostics",
            fn=ic.model_quality,
            kwargs={},
        )
    return invoke(
        tool_context,
        tool_id="TC-021",
        capability="well.diagnostics",
        fn=ic.classify_intervention,
        kwargs={"well_id": wid, "top_k": int(top_k or 3)},
    )


def get_document(
    doc_id: str,
    tool_context: ToolContext = None,
) -> dict:
    """TC-026: retrieve metadata and PDF URL for a specific document by its document ID (e.g. SOP-IC-01).
    Subject to persona-based document type permissions (D01-D11)."""
    persona = ctx_persona(tool_context)
    did = (doc_id or "").strip()
    if not did:
        return _missing("TC-026", "doc_id", "Which document ID? e.g. SOP-IC-01.")

    def tc026_get_doc(doc_id: str) -> dict:
        from app.analytics.docs_pdf.store import get_store

        store = get_store()
        if store is None:
            return {
                "status": "UNAVAILABLE",
                "data": None,
                "message": "document index not built",
                "missing_fields": ["document_index"],
                "provenance": {"tool_id": "TC-026"},
            }
        row = store.doc(doc_id)
        if row is None:
            return {
                "status": "UNAVAILABLE",
                "data": None,
                "message": f"document {doc_id} not found",
                "missing_fields": [],
                "provenance": {"tool_id": "TC-026"},
            }
        doc_type = row.get("doc_type")
        if not rbac.doc_type_allowed(persona, doc_type):
            return rbac.denied_envelope(
                persona,
                rbac.doc_type_capability(doc_type),
                f"doc_type {doc_type} not permitted for persona {persona}",
            )
        data = dict(row)
        data["pdf_url"] = f"/api/docs/{doc_id}.pdf"
        return {
            "status": "OK",
            "data": data,
            "message": f"document {doc_id} retrieved",
            "missing_fields": [],
            "provenance": {"tool_id": "TC-026", "doc_id": doc_id},
        }

    return invoke(
        tool_context,
        tool_id="TC-026",
        capability="docs.sop_dossier",
        fn=tc026_get_doc,
        kwargs={"doc_id": did},
    )


def list_sops(
    intervention_class: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-026: list all available D11 standard operating procedures (IC-01..IC-15), or get detailed procedure
    and acceptance criteria for a specific intervention class (e.g. 'IC-04')."""
    from app.analytics.docs_pdf.sop import load_sop

    raw_ic = (intervention_class or "").strip()
    norm_ic = ""
    if raw_ic:
        m = re.match(r"^(?:IC[-_]?)?0*(\d+)$", raw_ic, re.IGNORECASE)
        norm_ic = f"IC-{int(m.group(1)):02d}" if m else raw_ic.upper()

    def tc026_list_sops(ic: str) -> dict:
        if not ic:
            items = []
            for i in range(1, 16):
                key = f"IC-{i:02d}"
                doc = load_sop(key)
                if doc:
                    items.append({
                        "sop_id": doc.get("sop_id"),
                        "intervention_class": key,
                        "title": doc.get("title"),
                    })
            return {
                "status": "OK",
                "data": items,
                "message": f"{len(items)} SOP(s) available",
                "missing_fields": [],
                "provenance": {"tool_id": "TC-026", "source": "D11 SOP library"},
            }
        doc = load_sop(ic)
        if doc is None:
            return {
                "status": "UNAVAILABLE",
                "data": None,
                "message": f"SOP for {ic} not found",
                "missing_fields": ["intervention_class"],
                "provenance": {"tool_id": "TC-026", "source": "D11 SOP library"},
            }
        phases = []
        for ph in doc.get("procedure", []):
            if isinstance(ph, dict):
                name = ph.get("phase") or ph.get("phase_name") or ph.get("title") or "Unknown"
                steps = ph.get("steps") or []
                phases.append({"phase": name, "step_count": len(steps) if isinstance(steps, list) else 0})
        data = {
            "sop_id": doc.get("sop_id"),
            "title": doc.get("title"),
            "purpose": doc.get("purpose"),
            "pre_job_checks": doc.get("pre_job_checks"),
            "procedure_phases": phases,
            "acceptance_criteria": doc.get("acceptance_criteria"),
        }
        return {
            "status": "OK",
            "data": data,
            "message": f"SOP {doc.get('sop_id')} retrieved",
            "missing_fields": [],
            "provenance": {"tool_id": "TC-026", "source": "D11 SOP library"},
        }

    return invoke(
        tool_context,
        tool_id="TC-026",
        capability="docs.sop_dossier",
        fn=tc026_list_sops,
        kwargs={"ic": norm_ic},
    )


# --------------------------------------------------------------------------------------------------
# v0.6 Stage ED-7: ED meeting diagnostics (TC-033 / TC-034 / TC-035)
# --------------------------------------------------------------------------------------------------


def compare_offset_decline(
    well_id: str = "",
    months: int = 24,
    tool_context: ToolContext = None,
) -> dict:
    """TC-033: what is wrong with this well? Compares its decline, water cut and THP with its nearest offset wells
    over `months` (default 24). Verdict WELL_SPECIFIC (problem in this well), RESERVOIR_WIDE (offsets decline
    alike), WATER (scope WELL or AREA), RESTORED (a recent job restored rate), MIXED or INSUFFICIENT, with a
    one-line headline, each offset's last job and the mechanical signature. Use for 'what's wrong with GK-129',
    'compare decline with nearby wells', 'is it the well or the reservoir'."""
    from app.analytics.tools.offset_decline import offset_decline_compare as tc033

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-033", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-033",
        capability="well.diagnostics",
        fn=tc033,
        kwargs={"well_id": wid, "months": max(12, min(int(months or 24), 60))},
        post=_series_post,
    )


def well_anomalies(
    well_id: str = "",
    months: int = 24,
    tool_context: ToolContext = None,
) -> dict:
    """TC-034: any anomalies in this well's history? Rule-based scan of the last `months` (default 24): rate drops
    (>=30%), water-cut jumps / 12-month rise (>=10 pts), THP shifts (>=25%), downtime episodes (>=7 days, with
    reason and deferred bbl, ongoing flag), each linked to a nearby job. Use for 'well history', 'anything
    unusual', 'anomalies', 'what happened to this well'."""
    from app.analytics.tools.anomalies import well_anomalies as tc034

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-034", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-034",
        capability="well.diagnostics",
        fn=tc034,
        kwargs={"well_id": wid, "months": max(6, min(int(months or 24), 60))},
    )


def wax_sand_behaviour(
    well_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """TC-035: is this normal wax / sand, and can we predict it? For WAX and SAND: fluid flag, job count and last
    job, the well's own repeat cycle vs the field norm, next-due date / overdue days (only when the well has a
    repeat pattern), downtime days and deferred bbl, and an ongoing episode if any. There is no sand-rate data:
    say behaviour is inferred from jobs and downtime. Use for 'wax problem', 'sand production history', 'when is
    the next wax job due', 'is this normal wax'."""
    from app.analytics.tools.wax_sand import wax_sand_behaviour as tc035

    wid = ctx_well(tool_context, well_id)
    if not wid:
        return _missing("TC-035", "well_id", "Which well? e.g. GK-129.")
    return invoke(
        tool_context,
        tool_id="TC-035",
        capability="well.diagnostics",
        fn=tc035,
        kwargs={"well_id": wid},
    )


def _series_post(env: dict) -> dict:
    """Drop monthly series from the model payload (the chart is on screen)."""
    data = env.get("data")
    if isinstance(data, dict):
        for blk in [data.get("subject")] + list(data.get("offsets") or []):
            if isinstance(blk, dict) and isinstance(blk.get("series"), list):
                blk["series_months"] = len(blk.pop("series"))
    return env


# --------------------------------------------------------------------------------------------------
# EXT_TOOLS registry (19 wrappers in exact spec order + 3 v0.6 ED tools)
# --------------------------------------------------------------------------------------------------

EXT_TOOLS: list[Callable[..., dict]] = [
    fit_decline_curve,           # TC-001
    chan_diagnostic,             # TC-002
    fillage_proxy,               # TC-003
    check_offsets,               # TC-004
    detect_mechanical_signature, # TC-005
    predict_failure,             # TC-006
    trigger_scan,                # TC-007
    route_intervention,          # TC-008
    estimate_uplift,             # TC-009
    check_mro,                   # TC-011
    generate_draft_plan,         # TC-013
    generate_report,             # TC-014
    schedule_rigs,               # TC-015
    query_wells,                 # TC-018
    render_well_map,             # TC-016
    query_hierarchy,             # TC-025
    classify_intervention,       # TC-021
    get_document,                # TC-026
    list_sops,                   # TC-026
    compare_offset_decline,      # TC-033 (v0.6 ED-7)
    well_anomalies,              # TC-034 (v0.6 ED-7)
    wax_sand_behaviour,          # TC-035 (v0.6 ED-7)
]

# If adk_tools was imported during our module initialization before EXT_TOOLS was bound,
# refresh ALL and TOOLS_BY_NAME so callers importing adk_tools_ext first always see 30 tools.
if "app.agent.adk_tools" in sys.modules:
    _adk = sys.modules["app.agent.adk_tools"]
    if hasattr(_adk, "CORE_TOOLS"):
        _adk.ALL = _adk.CORE_TOOLS + list(EXT_TOOLS)
        _adk.TOOLS_BY_NAME = {t.__name__: t for t in _adk.ALL}

