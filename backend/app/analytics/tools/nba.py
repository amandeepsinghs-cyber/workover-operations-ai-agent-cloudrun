"""TC-022 ``recommend_next_best_action`` — ranked next best actions per well (SDD §9.1, F-04, F-14, Stage R).

Every number comes from an existing tool or a landing table; there is no LLM and no currency (D-1).

Pipeline (``recommend_next_best_action(well_id, as_of, top_k)``):

1. **Evidence** (:func:`well_evidence`, cached per ``(well_id, as_of)``): open status episode, TC-005 signature,
   TC-002 Chan class, TC-003 fillage, TC-004 offsets, the two latest ``pressure_surveys`` rows, TC-021 ML top-k,
   construction (production-casing age) and job history *before* ``as_of``.
2. **Physics mechanism** (first that applies): offsets ``RESERVOIR_DECLINE`` → open non-producing episode reason
   → TC-005 signature → TC-002 water mechanism with a real water-cut rise (Trigger-C gating) → Trigger B's last
   failure mode. TC-008 routes it to a catalogue job.
3. **Candidates:** ML classes with p ≥ 0.10, the TC-008 physics route and its TC-008 alternatives; one job per
   intervention class (:func:`select_job`, lift-type and history aware).
4. **Diagnostic fit** (:func:`diagnostic_fit`, shared with TC-027): ``FIT`` ✔ / ``UNCLEAR`` ? / ``CONTRADICTED`` ✘
   with the deciding evidence. Contradicted candidates are rejected with that reason.
5. **Guardrails:** G-1 coning (Chan WOR′ slope < 0 with a water problem in play) forces ``CHOKE_BACK`` to rank 1
   and rejects squeeze / gel; G-2 ``RESERVOIR_DECLINE`` forces ``NO_JOB_JUSTIFIED`` and rejects everything else;
   G-3 ML top-1 class ≠ physics class → flag ``MODEL_PHYSICS_DISAGREEMENT`` with both shown.
6. **Evidence per candidate:** TC-009 uplift and deferred barrels; Beta-smoothed ``p_success`` (field × class ×
   lift, prior = asset class rate, α = 5, then shrunk again toward that by this well's own outcomes); catalogue
   rig-days / cost band / unit type; TC-011 MRO; first free rig window in ``rig_calendar``; D11 SOP steps.
7. **Score** = ``deferred_bbl_12mo × p_success ÷ max(rig_days, 0.5) × (1 − min(0.45, 0.15 · n_risk_flags))``.
   Order: guardrail-forced → ``FIT`` → ``UNCLEAR``; inside a tier by score, then ML probability.

Decisions R-D1..R-D10 are recorded in ``docs/pinned_values.md`` §11.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from app import settings

from .candidate_ranking import (
    ALTERNATIVES,
    ROUTING,
    _CFG as _TRIG_CFG,
    _catalogue,
    _duration_range,
    _trigger_b,
    check_mro,
    check_offsets,
    detect_mechanical_signature,
    estimate_uplift,
    fillage_proxy,
    route_intervention,
)
from .chan_diagnostic import chan_diagnostic
from .common import (
    ToolResult,
    ToolStatus,
    WellId,
    build_provenance,
    load_table,
    load_yaml,
    register_cache,
    unavailable,
    well_master_row,
    well_rows,
)

TOOL_ID = "TC-022"

# --- pinned constants (SDD §9.1; not tuned) ------------------------------------------------------
ALPHA = 5.0                       # Beta prior strength (pseudo-jobs)
ML_MIN_PROB = 0.10                # ML class enters the candidate set at p >= 0.10
RISK_STEP, RISK_CAP = 0.15, 0.45  # score discount per risk flag, capped
CASING_AGE_YEARS = 35.0           # WELL_INTEGRITY: production casing older than this
REPEAT_FAILURES, REPEAT_WINDOW_DAYS = 3, 730
LOGISTICS_DAYS = 14               # LOGISTICS_DELAY: earliest start more than this many days after as_of
LOW_EVIDENCE_N = 5                # LOW_EVIDENCE: fewer field jobs of this class + lift
RIG_SLOT_HORIZON_DAYS = 90
PI_DROP_PCT = -30.0               # pressure surveys: PI fall that signals near-wellbore damage
SBHP_DEPLETION_PCT = -10.0        # ... unless static pressure itself fell this much (depletion)
SCORE_FORMULA = ("deferred_bbl_12mo * p_success / max(rig_days, 0.5) * (1 - min(0.45, 0.15 * n_risk_flags))")

FIT, UNCLEAR, CONTRADICTED = "FIT", "UNCLEAR", "CONTRADICTED"
FIT_SYMBOL = {FIT: "✔", UNCLEAR: "?", CONTRADICTED: "✘"}
FIT_ORDER = {FIT: 2, UNCLEAR: 1, CONTRADICTED: 0}

WATER_CLASSES = frozenset({"IC-11", "IC-12", "IC-13"})
ROD_LIFTS = frozenset({"SRP", "PCP"})
MECHANICAL_DAMAGE = frozenset({"PUMP_WEAR", "ROD_PART", "SUDDEN_MECH", "TUBING_LEAK"})
FINISHED = ("SUCCESS", "PARTIAL", "FAILED")

# Mechanisms (TC-005 signatures, TC-002 classes, failure codes) that each class addresses.
ADDRESSES: dict[str, frozenset[str]] = {
    "IC-01": frozenset({"PUMP_WEAR"}),
    "IC-02": frozenset({"ROD_PART", "SUDDEN_MECH"}),
    "IC-03": frozenset({"TUBING_LEAK"}),
    "IC-04": frozenset({"WAX"}),
    "IC-05": frozenset({"SCALE"}),
    "IC-06": frozenset({"SAND"}),
    "IC-07": frozenset({"GL_VALVE", "GL_INJ_ANOMALY"}),
    "IC-08": frozenset({"GAS_INTERFERENCE", "LIFT_INEFFICIENCY"}),
    "IC-09": frozenset({"PI_DECLINE"}),
    "IC-10": frozenset({"PI_DECLINE", "BYPASSED_PAY"}),
    "IC-11": frozenset({"CHANNELLING", "CHANNELLING_OR_INJECTOR_BREAKTHROUGH", "INJECTOR_BREAKTHROUGH",
                        "WATER_CHANNELLING"}),
    "IC-12": frozenset({"MULTILAYER", "WATER_ZONE"}),
    "IC-13": frozenset({"CONING"}),
    "IC-14": frozenset({"SURFACE", "CASING_LEAK"}),
    "IC-15": frozenset({"RESERVOIR_DECLINE"}),
}
# Default catalogue job per class (refined by select_job).
CLASS_DEFAULT_JOB: dict[str, str] = {
    "IC-01": "PUMP_OVERHAUL", "IC-02": "ROD_REPLACE", "IC-03": "TUBING_REPLACE", "IC-04": "WAX_HOTOIL",
    "IC-05": "SCALE_ACID_BULLHEAD", "IC-06": "SAND_CLEANOUT", "IC-07": "GLV_REPLACE", "IC-08": "LIFT_OPTIM",
    "IC-09": "MATRIX_ACID", "IC-10": "RE_PERFORATION", "IC-11": "CEMENT_SQUEEZE", "IC-12": "STRADDLE_PACKER",
    "IC-13": "CHOKE_BACK", "IC-14": "SURFACE_REPAIR", "IC-15": "NO_JOB_JUSTIFIED",
}
_RIG_CLASSES = {"WORKOVER_RIG": ("CLASS_I", "CLASS_II"), "PULLING_UNIT": ("PULLING_UNIT", "CLASS_I", "CLASS_II")}


# =================================================================================================
# evidence
# =================================================================================================
@dataclass(frozen=True)
class WellEvidence:
    well_id: WellId
    field: str
    lift_type: str
    as_of: date
    casing_vented: bool
    open_episode: dict | None
    mech: dict | None              # TC-005
    chan: dict | None              # TC-002
    chan_message: str
    water_active: bool             # Trigger-C water gating (mechanism + confidence + water-cut rise)
    fillage: dict | None           # TC-003
    offsets: dict | None           # TC-004
    pressure: dict | None          # pressure_surveys (latest + previous + changes)
    wht: dict | None               # WHT trend over the TC-005 window
    physics: dict | None           # {mechanism, source, evidence}
    route: Any | None              # TC-008 InterventionRoute
    ml: dict                       # {status, top_k[{ic, label, prob}], flags, message}
    history: list[dict]            # finished jobs before as_of (newest first)
    casing_age_years: float | None
    casing_install_date: date | None
    failures_24mo: int
    failed_water_jobs: list[dict]
    health: dict | None


def _d(x: Any) -> date | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if isinstance(x, pd.Timestamp):
        return x.date()
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _open_episode(well_id: WellId, as_of: date) -> dict | None:
    s = well_rows("well_status_history", well_id)
    if s.empty:
        return None
    cur = s[(s["start_date"] <= as_of) & (s["end_date"].isna() | (s["end_date"] >= as_of))]
    if cur.empty:
        return None
    r = cur.sort_values("start_date").iloc[-1]
    return {"episode_id": str(r["episode_id"]), "status": str(r["status"]),
            "reason_code": r["reason_code"] if isinstance(r["reason_code"], str) else None,
            "start_date": _d(r["start_date"])}


def _pressure(well_id: WellId, as_of: date) -> dict | None:
    ps = well_rows("pressure_surveys", well_id)
    if ps.empty:
        return None
    ps = ps[ps["survey_date"] <= as_of].sort_values("survey_date")
    if ps.empty:
        return None
    cols = ("survey_id", "survey_date", "sbhp_kgcm2", "fbhp_kgcm2", "pi_bpd_per_kgcm2", "fluid_level_m")

    def row(r) -> dict:
        return {c: (_d(r[c]) if c == "survey_date" else (None if pd.isna(r[c]) else
                                                          (str(r[c]) if c == "survey_id" else float(r[c]))))
                for c in cols}

    latest = row(ps.iloc[-1])
    prev = row(ps.iloc[-2]) if len(ps) >= 2 else None
    out = {"latest": latest, "previous": prev, "n_surveys": int(len(ps)), "sbhp_change_pct": None,
           "pi_change_pct": None, "doc_id": None}
    if prev:
        if prev["sbhp_kgcm2"]:
            out["sbhp_change_pct"] = round((latest["sbhp_kgcm2"] / prev["sbhp_kgcm2"] - 1.0) * 100.0, 1)
        if prev["pi_bpd_per_kgcm2"]:
            out["pi_change_pct"] = round((latest["pi_bpd_per_kgcm2"] / prev["pi_bpd_per_kgcm2"] - 1.0) * 100.0, 1)
    out["doc_id"] = _doc_for_survey(well_id, latest["survey_date"])
    return out


def _doc_store():
    try:
        from app.analytics.docs_pdf.store import get_store

        return get_store()
    except Exception:  # corpus not built: citations are simply omitted
        return None


def _well_docs(well_id: WellId) -> pd.DataFrame:
    st = _doc_store()
    if st is None:
        return pd.DataFrame(columns=["doc_id", "doc_type", "workover_id", "doc_date", "title"])
    d = st.docs
    return d[d["well_id"] == well_id]


def _doc_for_survey(well_id: WellId, survey_date: date | None) -> str | None:
    d = _well_docs(well_id)
    if survey_date is None or d.empty:
        return None
    m = d[(d["doc_type"] == "D07") & (d["doc_date"].astype(str) == str(survey_date))]
    return str(m.iloc[0]["doc_id"]) if len(m) else None


def _wht(well_id: WellId, as_of: date) -> dict | None:
    win = int(_TRIG_CFG["signatures"]["window_days"])
    n = int(_TRIG_CFG["signatures"]["edge_days"])
    d = well_rows("daily_production", well_id)
    if "wht_degc" not in d.columns:
        return None
    p = d[(d["production_date"] > as_of - timedelta(days=win)) & (d["production_date"] <= as_of)
          & (d["is_producing"] == True)].sort_values("production_date")  # noqa: E712
    p = p[p["wht_degc"].notna()]
    if len(p) < 3 * n:
        return None
    a, b = float(p["wht_degc"].iloc[:n].mean()), float(p["wht_degc"].iloc[-n:].mean())
    return {"first_degc": round(a, 1), "last_degc": round(b, 1), "change_degc": round(b - a, 1), "window_days": win}


def _ml(well_id: WellId, as_of: date) -> dict:
    from .intervention_classifier import classify_intervention

    r = classify_intervention(well_id, as_of=as_of, top_k=3)
    if r.value is None:
        return {"status": r.status.value, "top_k": [], "flags": ["ML_UNAVAILABLE"], "message": r.message,
                "model_version": None}
    v = r.value
    return {"status": r.status.value, "top_k": [{"ic": str(c.ic), "label": c.label, "prob": float(c.prob)}
                                                for c in v.top_k],
            "flags": list(v.flags), "message": r.message, "model_version": v.model_version,
            "holdout_macro_f1": v.holdout_macro_f1}


def _history(well_id: WellId, as_of: date) -> list[dict]:
    wo = well_rows("workover_history", well_id)
    if wo.empty:
        return []
    h = wo[(~wo["is_censored"].astype(bool)) & (wo["start_date"] < as_of)].sort_values("start_date", ascending=False)
    docs = _well_docs(well_id)
    out = []
    for r in h.itertuples(index=False):
        dd = docs[docs["workover_id"] == r.workover_id] if len(docs) else docs
        report = dd[dd["doc_type"] == "D02"]
        rca = dd[dd["doc_type"] == "D08"]
        out.append({
            "workover_id": str(r.workover_id), "start_date": _d(r.start_date),
            "job_code": r.catalogue_job_code if isinstance(r.catalogue_job_code, str) else None,
            "intervention_class": r.intervention_class if isinstance(r.intervention_class, str) else None,
            "outcome": str(r.outcome), "failure_code": r.failure_code if isinstance(r.failure_code, str) else None,
            "run_life_days": None if pd.isna(r.run_life_days) else float(r.run_life_days),
            "rig_days": None if pd.isna(r.rig_days) else float(r.rig_days),
            "report_doc_id": str(report.iloc[0]["doc_id"]) if len(report) else None,
            "rca_doc_id": str(rca.iloc[0]["doc_id"]) if len(rca) else None,
        })
    return out


def _physics(ev_parts: dict) -> dict | None:
    off, ep, mech, chan = ev_parts["offsets"], ev_parts["open_episode"], ev_parts["mech"], ev_parts["chan"]
    if off and off["verdict"] == "RESERVOIR_DECLINE":
        return {"mechanism": "RESERVOIR_DECLINE", "source": "TC-004 check_offsets",
                "evidence": off["summary"]}
    if ep and ep["status"] != "PRODUCING" and ep["reason_code"] in ROUTING:
        return {"mechanism": ep["reason_code"], "source": "well_status_history (open episode)",
                "evidence": f"well {ep['status']} since {ep['start_date']} for {ep['reason_code']} ({ep['episode_id']})"}
    if mech and mech["signature"] not in (None, "NONE") and mech["confidence"] in ("HIGH", "MEDIUM"):
        return {"mechanism": mech["signature"], "source": "TC-005 detect_mechanical_signature",
                "evidence": mech["evidence"]}
    if chan and ev_parts["water_active"]:
        return {"mechanism": chan["mechanism"], "source": "TC-002 chan_diagnostic",
                "evidence": f"{chan['evidence']}; water cut {chan['water_cut_start_pct']}% -> {chan['water_cut_end_pct']}%"}
    tb = ev_parts["trigger_b"]
    if tb.get("fired") and ev_parts["history"]:
        last = next((h for h in ev_parts["history"] if h["failure_code"] in ROUTING), None)
        if last:
            return {"mechanism": last["failure_code"], "source": "TC-007 trigger B (last failure mode)",
                    "evidence": (f"{tb['days_since']:.0f} d since last job > p50 run life {tb['p50_days']:.0f} d; "
                                 f"last failure mode {last['failure_code']} ({last['workover_id']}, {last['start_date']})")}
    return None


def well_evidence(well_id: WellId, as_of: date | None = None) -> WellEvidence | None:
    return _evidence_cached(str(well_id).strip().upper(), as_of or settings.AS_OF)


@lru_cache(maxsize=1024)
def _evidence_cached(well_id: WellId, as_of: date) -> WellEvidence | None:
    wm = well_master_row(well_id)
    if wm is None:
        return None
    lift = str(wm.get("lift_type"))
    m = detect_mechanical_signature(well_id, as_of=as_of)
    mech = ({"signature": m.value.signature.value, "confidence": m.value.confidence.value,
             "evidence": m.value.evidence, "metrics": dict(m.value.metrics), "status": m.status.value}
            if m.value is not None else None)
    c = chan_diagnostic(well_id, as_of=as_of)
    chan = None
    if c.value is not None:
        v = c.value
        chan = {"mechanism": v.mechanism.value, "wor_slope": v.wor_slope, "wor_prime_slope": v.wor_prime_slope,
                "r_squared": v.r_squared, "confidence": v.confidence.value,
                "water_cut_start_pct": v.water_cut_start_pct, "water_cut_end_pct": v.water_cut_end_pct,
                "evidence": v.discriminating_evidence, "status": c.status.value}
    tc = _TRIG_CFG["trigger_c"]
    water_active = bool(chan and chan["mechanism"] in tc["water_mechanisms"] and chan["confidence"] in ("HIGH", "MEDIUM")
                        and chan["water_cut_end_pct"] - chan["water_cut_start_pct"] >= float(tc["min_water_cut_rise_pp"]))
    f = fillage_proxy(well_id, as_of=as_of)
    fill = ({"gap_pct": f.value.gap_pct, "volumetric_efficiency_pct": f.value.volumetric_efficiency_pct,
             "is_diverging": f.value.is_diverging, "status": f.status.value} if f.value is not None else None)
    o = check_offsets(well_id, as_of=as_of)
    off = None
    if o.value is not None:
        ov = o.value
        names = ", ".join(f"{w} {r:+.1f}%" for w, r, _ in ov.offset_residuals)
        off = {"verdict": ov.verdict.value, "subject_residual_pct": ov.subject_residual_pct,
               "offset_median_residual_pct": ov.offset_median_residual_pct,
               "excess_residual_pct": ov.excess_residual_pct, "n_offsets_used": ov.n_offsets_used,
               "offset_wells": [{"well_id": w, "residual_pct": r, "distance_m": dm} for w, r, dm in ov.offset_residuals],
               "summary": (f"subject residual {ov.subject_residual_pct:+.1f}% vs median {ov.offset_median_residual_pct:+.1f}% "
                           f"of {ov.n_offsets_used} same-zone offsets ({names}); verdict {ov.verdict.value}")}
    hist = _history(well_id, as_of)
    tb = _trigger_b(well_id, as_of)
    ep = _open_episode(well_id, as_of)
    parts = {"offsets": off, "open_episode": ep, "mech": mech, "chan": chan, "water_active": water_active,
             "trigger_b": tb, "history": hist}
    phys = _physics(parts)
    route = None
    if phys is not None:
        verdict = "RESERVOIR_DECLINE" if phys["mechanism"] == "RESERVOIR_DECLINE" else (off["verdict"] if off else "INSUFFICIENT")
        rr = route_intervention(well_id, "CHANNELLING" if phys["mechanism"] == "RESERVOIR_DECLINE" else phys["mechanism"],
                                verdict, evidence={"source": phys["source"]})
        route = rr.value
    cas = well_rows("casing_tally", well_id)
    pc = cas[cas["string_type"] == "PRODUCTION"] if len(cas) else cas
    inst = _d(pc.iloc[0]["install_date"]) if len(pc) else None
    age = round((as_of - inst).days / 365.25, 1) if inst else None
    lo = as_of - timedelta(days=REPEAT_WINDOW_DAYS)
    fails = sum(1 for h in hist if h["start_date"] >= lo and h["failure_code"] not in (None, "NONE"))
    failed_water = [h for h in hist if h["outcome"] == "FAILED" and h["intervention_class"] in ("IC-11", "IC-12", "IC-14")]
    try:
        from .health import _classify

        wh = _classify(well_id, as_of, {})
        health = {"bucket": wh.bucket, "reason": wh.reason, "reason_code": wh.reason_code}
    except Exception:  # health is used only for urgency wording
        health = None
    return WellEvidence(
        well_id=well_id, field=str(wm.get("field")), lift_type=lift, as_of=as_of,
        casing_vented=bool(wm.get("casing_vented")), open_episode=ep, mech=mech, chan=chan,
        chan_message=c.message, water_active=water_active, fillage=fill, offsets=off,
        pressure=_pressure(well_id, as_of), wht=_wht(well_id, as_of), physics=phys, route=route,
        ml=_ml(well_id, as_of), history=hist, casing_age_years=age, casing_install_date=inst,
        failures_24mo=fails, failed_water_jobs=failed_water, health=health)


# =================================================================================================
# job selection + diagnostic fit (shared with TC-027)
# =================================================================================================
def ic_labels() -> dict[str, str]:
    return {k: str(v["label"]) for k, v in load_yaml("ic_map.yaml")["classes"].items()}


def job_ic(job_code: str) -> str | None:
    cat = _catalogue()
    return str(cat.loc[job_code, "intervention_class"]) if job_code in cat.index else None


def select_job(ic: str, ev: WellEvidence) -> tuple[str, str]:
    """Best catalogue job of class ``ic`` for this well (lift type, history, physics route) + why."""
    if ev.route is not None and job_ic(ev.route.job_code) == ic:
        return ev.route.job_code, f"TC-008 physics route for {ev.physics['mechanism']}"
    job = CLASS_DEFAULT_JOB[ic]
    hist = ev.history
    if ic == "IC-11" and any(h["job_code"] == "CEMENT_SQUEEZE" and h["outcome"] == "FAILED" for h in hist):
        return "POLYMER_GEL", "prior cement squeeze failed on this well (catalogue: gel after failed squeeze)"
    if ic == "IC-04" and any(h["job_code"] == "WAX_HOTOIL" and h["outcome"] == "FAILED" for h in hist):
        return "WAX_SOLVENT", "hot oil failed before on this well (catalogue: solvent on recurrence)"
    if ic == "IC-06":
        lo = ev.as_of - timedelta(days=REPEAT_WINDOW_DAYS)
        if sum(1 for h in hist if h["job_code"] == "SAND_CLEANOUT" and h["start_date"] >= lo) >= 2:
            return "SAND_CONTROL", ">= 2 sand cleanouts in 24 months (catalogue: repeated cleanouts)"
    if ic == "IC-08" and ev.physics and ev.physics["mechanism"] == "GAS_INTERFERENCE":
        return "GAS_SEP_INSTALL", "gas interference signature"
    if ic == "IC-14" and ev.physics and ev.physics["mechanism"] == "CASING_LEAK":
        return "CASING_REPAIR", "casing leak mechanism"
    return job, f"default {ic} job for a {ev.lift_type} well"


def _fit_from_mechanism(ic: str, ev: WellEvidence) -> tuple[str, str] | None:
    p = ev.physics
    if p and p["mechanism"] in ADDRESSES.get(ic, ()):
        return FIT, f"addresses the diagnosed {p['mechanism']} ({p['source']}: {p['evidence']})"
    return None


def diagnostic_fit(job_code: str, ev: WellEvidence) -> tuple[str, str]:
    """(FIT | UNCLEAR | CONTRADICTED, deciding evidence) for one job on this well (SDD §9.2 row 1)."""
    ic = job_ic(job_code) or ""
    off, ep, chan, mech, ps = ev.offsets, ev.open_episode, ev.chan, ev.mech, ev.pressure
    rd = bool(off and off["verdict"] == "RESERVOIR_DECLINE")
    sbhp = (f"; SBHP {ps['previous']['sbhp_kgcm2']} -> {ps['latest']['sbhp_kgcm2']} kg/cm2 "
            f"({ps['sbhp_change_pct']:+.1f}%, surveys {ps['previous']['survey_date']} / {ps['latest']['survey_date']})"
            if ps and ps.get("previous") and ps.get("sbhp_change_pct") is not None else "")
    if ic == "IC-15":
        if job_code == "PLUG_ABANDON":
            return UNCLEAR, "plug and abandon is an asset decision (rate vs opex); not evaluated by TC-022"
        if rd:
            return FIT, f"decline is shared with the offsets: {off['summary']}{sbhp}"
        if ev.physics:
            return CONTRADICTED, f"a well-specific mechanism is diagnosed ({ev.physics['mechanism']}: {ev.physics['evidence']})"
        return UNCLEAR, "no well-specific mechanism diagnosed and offsets do not show a shared decline"
    if rd:
        return CONTRADICTED, (f"G-2: {off['summary']}{sbhp}; a wellbore job cannot restore reservoir pressure")
    if ic in ("IC-01", "IC-02") and ev.lift_type not in ROD_LIFTS:
        return CONTRADICTED, f"not applicable: {ev.lift_type} well has no rod pump"
    if ic == "IC-07" and ev.lift_type != "GAS_LIFT":
        return CONTRADICTED, f"not applicable: {ev.lift_type} well has no gas-lift valves"
    if ep and ep["status"] != "PRODUCING" and ep["reason_code"]:
        if ep["reason_code"] in ADDRESSES.get(ic, ()):
            return FIT, f"well {ep['status']} since {ep['start_date']} for {ep['reason_code']} ({ep['episode_id']}); this job restores it"
        return CONTRADICTED, (f"well {ep['status']} since {ep['start_date']} for {ep['reason_code']} "
                              f"({ep['episode_id']}); this job does not restore it")
    hit = _fit_from_mechanism(ic, ev)
    if ic == "IC-08" and ev.physics and ev.physics["mechanism"] in MECHANICAL_DAMAGE:
        return CONTRADICTED, (f"catalogue: lift optimisation applies without mechanical damage; "
                              f"{ev.physics['source']} shows {ev.physics['mechanism']} ({ev.physics['evidence']})")
    if ic in WATER_CLASSES:
        if chan is None:
            if "below" in ev.chan_message.lower():
                return CONTRADICTED, f"no water problem to treat: {ev.chan_message}"
            return UNCLEAR, f"Chan diagnostic unavailable: {ev.chan_message}"
        m, s = chan["mechanism"], chan["wor_prime_slope"]
        wc = f"water cut {chan['water_cut_start_pct']}% -> {chan['water_cut_end_pct']}%"
        if ic == "IC-11":
            if m == "CONING":
                return CONTRADICTED, (f"G-1: WOR′ slope {s:+.2f} < 0 is a coning signature ({wc}); a squeeze or gel "
                                      f"does not stop coning — reduce drawdown (choke back)")
            if m in ADDRESSES["IC-11"]:
                return FIT, f"WOR′ slope {s:+.2f} > +0.30 = channelling ({wc}, r²={chan['r_squared']}): water shut-off squeeze"
            return hit or (UNCLEAR, f"WOR′ slope {s:+.2f} ({m}, {wc}) does not single out a channel")
        if ic == "IC-13":
            if m == "CONING":
                return FIT, f"WOR′ slope {s:+.2f} < 0 = coning ({wc}, r²={chan['r_squared']}): reduce drawdown"
            if m in ADDRESSES["IC-11"]:
                return CONTRADICTED, (f"WOR′ slope {s:+.2f} = channelling ({wc}); choking back does not stop water "
                                      f"flowing through a channel")
            return hit or (UNCLEAR, f"WOR′ slope {s:+.2f} ({m}, {wc}) is not a coning signature")
        if ic == "IC-12":
            if m == "CONING":
                return CONTRADICTED, f"WOR′ slope {s:+.2f} = coning ({wc}); isolating a layer does not stop coning"
            return hit or (UNCLEAR, f"WOR′ slope {s:+.2f} ({m}, {wc}); zonal isolation needs a log-identified water layer")
    if hit:
        return hit
    if ic == "IC-04":
        if mech is None:
            return UNCLEAR, "TC-005 unavailable (too few producing days in the window)"
        thr = float(_TRIG_CFG["signatures"]["wax"]["min_thp_rise_frac"])
        thp = mech["metrics"].get("thp_change_frac")
        wht = (f"; WHT {ev.wht['first_degc']} -> {ev.wht['last_degc']} °C ({ev.wht['change_degc']:+.1f} °C)"
               if ev.wht else "")
        if thp is not None and thp < thr:
            return CONTRADICTED, (f"no wax signature: THP {thp:+.1%} over {_TRIG_CFG['signatures']['window_days']} d "
                                  f"(wax needs >= {thr:+.0%} with falling liquid){wht}; TC-005 = {mech['signature']}")
        return UNCLEAR, f"THP change {'n/a' if thp is None else f'{thp:+.1%}'}{wht}; TC-005 = {mech['signature']}"
    if ic in ("IC-09", "IC-10"):
        if ps is None or ps.get("pi_change_pct") is None:
            return UNCLEAR, "fewer than two pressure surveys before as_of: PI trend unknown"
        pi = (f"PI {ps['previous']['pi_bpd_per_kgcm2']} -> {ps['latest']['pi_bpd_per_kgcm2']} bpd/kg/cm2 "
              f"({ps['pi_change_pct']:+.1f}%){sbhp}")
        if ps["pi_change_pct"] <= PI_DROP_PCT and (ps["sbhp_change_pct"] or 0.0) > SBHP_DEPLETION_PCT:
            if ev.water_active or (chan and chan["mechanism"] in ADDRESSES["IC-11"]):
                return UNCLEAR, (f"{pi} suggests near-wellbore damage, but water {chan['mechanism'].lower()} "
                                 f"(WOR′ {chan['wor_prime_slope']:+.2f}) is the active mechanism; "
                                 f"{'re-perforating' if ic == 'IC-10' else 'stimulating'} does not shut off water")
            return FIT, f"{pi}: productivity fell while reservoir pressure held (near-wellbore damage)"
        if (ps["sbhp_change_pct"] or 0.0) <= SBHP_DEPLETION_PCT:
            return UNCLEAR, f"{pi}: static pressure is depleting; inflow work cannot restore pressure"
        return UNCLEAR, f"{pi}: no productivity loss beyond {PI_DROP_PCT:.0f}%"
    if ic == "IC-01" and ev.fillage and ev.fillage["is_diverging"] and ev.fillage["status"] == "OK":
        return FIT, f"fillage diverging (gap {ev.fillage['gap_pct']}%, volumetric efficiency {ev.fillage['volumetric_efficiency_pct']}%)"
    sig = mech["signature"] if mech else "unavailable"
    return UNCLEAR, f"no discriminating evidence for or against (TC-005 = {sig})"


# =================================================================================================
# per-candidate evidence
# =================================================================================================
def p_success_beta(job_code: str, ev: WellEvidence) -> dict:
    """Beta-smoothed success odds for (field, class, lift), then shrunk by this well's own record (α = 5)."""
    ic = job_ic(job_code)
    wo = load_table("workover_history")
    h = wo[(wo["intervention_class"] == ic) & wo["outcome"].isin(FINISHED) & (wo["start_date"] < ev.as_of)
           & (~wo["is_censored"].astype(bool))]
    n_asset, s_asset = int(len(h)), int((h["outcome"] == "SUCCESS").sum())
    out = {"intervention_class": ic, "alpha": ALPHA, "n_asset": n_asset, "s_asset": s_asset, "p_asset": None,
           "n_field": 0, "s_field": 0, "p_field": None, "n_well": 0, "s_well": 0, "p_success": None,
           "scope": f"{ev.field} × {ic} × {ev.lift_type} (prior: asset {ic}, all lifts)"}
    if n_asset == 0:
        return out
    p_asset = s_asset / n_asset
    wm = load_table("well_master")[["well_id", "lift_type"]]
    hf = h[h["field"] == ev.field].merge(wm, on="well_id", how="left")
    hf = hf[hf["lift_type"] == ev.lift_type]
    n_f, s_f = int(len(hf)), int((hf["outcome"] == "SUCCESS").sum())
    p_field = (s_f + ALPHA * p_asset) / (n_f + ALPHA)
    hw = h[h["well_id"] == ev.well_id]
    n_w, s_w = int(len(hw)), int((hw["outcome"] == "SUCCESS").sum())
    p = (s_w + ALPHA * p_field) / (n_w + ALPHA)
    out.update(p_asset=round(p_asset, 3), n_field=n_f, s_field=s_f, p_field=round(p_field, 3), n_well=n_w,
               s_well=s_w, p_success=round(p, 3))
    return out


def _rig_slot(equipment: str, need_days: int, start_min: date, as_of: date) -> dict:
    cal = load_table("rig_calendar")
    if cal.empty:
        return {"status": "UNAVAILABLE", "message": "rig_calendar empty"}
    lo, hi = cal["date"].min(), cal["date"].max()
    if start_min < lo or start_min > hi:
        return {"status": "UNAVAILABLE", "message": f"rig_calendar covers {lo}..{hi}; required start {start_min} is outside it"}
    classes = _RIG_CLASSES.get(equipment)
    c = cal[(cal["date"] >= start_min) & (cal["date"] <= as_of + timedelta(days=RIG_SLOT_HORIZON_DAYS))]
    if classes:
        c = c[c["rig_class"].isin(classes)]
    best = None
    for rid, g in c.groupby("rig_id"):
        free = set(g[g["status"] == "AVAILABLE"]["date"])
        for d0 in sorted(free):
            if all(d0 + timedelta(days=i) in free for i in range(need_days)):
                if best is None or d0 < best[1]:
                    best = (str(rid), d0, str(g["rig_class"].iloc[0]))
                break
    if best is None:
        return {"status": "NO_SLOT", "message": f"no {need_days}-day free window for {equipment} within "
                                                f"{RIG_SLOT_HORIZON_DAYS} d (rig_calendar {lo}..{hi})"}
    return {"status": "OK", "rig_id": best[0], "rig_class": best[2], "start_date": best[1],
            "basis": "first free window in rig_calendar for this well alone (TC-015 allocates the field queue)"}


def _mro(job_code: str, as_of: date) -> dict:
    from .candidate_ranking import JOB_ITEMS

    if not JOB_ITEMS.get(job_code):
        return {"mro_status": "NOT_REQUIRED", "mro_blocker": None, "earliest_feasible_start": as_of + timedelta(days=2),
                "transit_days": 0, "note": "no tracked MRO items for this job"}
    r = check_mro(job_code, required_date=as_of + timedelta(days=2))
    v = r.value
    if r.status != ToolStatus.OK:
        return {"mro_status": "NO_STOCK", "mro_blocker": v["governing_blocker"], "earliest_feasible_start": None,
                "transit_days": None, "note": r.message}
    st = "IN_STOCK" if not v["transit_days"] else "TRANSFER_REQUIRED"
    return {"mro_status": st, "mro_blocker": v["governing_blocker"], "earliest_feasible_start": v["earliest_feasible_start"],
            "transit_days": v["transit_days"], "alternate_base": v["alternate_base"],
            "note": "mro_inventory is a current snapshot (not time-varying)"}


_FOOTER_RE = re.compile(r"WellPulse synthetic document corpus \| \S+ Page \d+ of \d+ SYNTHETIC DATA - generated from "
                        r"WellPulse landing tables - not for operational use")


@lru_cache(maxsize=64)
def sop_steps(doc_id: str) -> dict | None:
    """Phases and steps of a D11 SOP parsed from its text layer (title, page, phases[{phase, steps[]}])."""
    st = _doc_store()
    if st is None or not doc_id:
        return None
    meta = st.doc(doc_id)
    if meta is None:
        return None
    ch = st.chunks[st.chunks["doc_id"] == doc_id].sort_values("page")
    text, page_of_proc = "", None
    for r in ch.itertuples(index=False):
        t = _FOOTER_RE.sub(" ", str(r.text))
        if page_of_proc is None and "Procedure " in t:
            page_of_proc = int(r.page)
        text += " " + t
    out = {"doc_id": doc_id, "title": meta.get("title"), "uri": meta.get("uri") or f"/api/docs/{doc_id}.pdf",
           "procedure_page": page_of_proc, "phases": []}
    if "Procedure " not in text:
        return out
    proc = text.split("Procedure ", 1)[1].split("Job-code variants")[0]
    parts = re.split(r"\bStep (\d+)\.\s", proc)
    title, steps = parts[0].strip(), []
    for i in range(1, len(parts), 2):
        body = re.sub(r"\s+", " ", parts[i + 1]).strip()
        last = i + 2 >= len(parts)
        nxt_new_phase = (not last) and parts[i + 2] == "1"
        new_title = None
        if nxt_new_phase and ". " in body:
            k = body.rfind(". ")
            body, new_title = body[:k + 1], body[k + 2:].strip()
        steps.append(body)
        if nxt_new_phase or last:
            out["phases"].append({"phase": title, "steps": steps})
            title, steps = new_title or "", []
    return out


@dataclass(frozen=True)
class CandidateEval:
    job_code: str
    job_name: str
    ic: str
    ic_label: str
    selection_note: str
    diagnostic_fit: str
    fit_symbol: str
    fit_evidence: str
    uplift_bopd: float | None
    deferred_bbl_12mo: float | None
    uplift_method: str | None
    uplift_status: str
    p_success: float | None
    p_success_n: int
    p_success_detail: dict
    requires_rig: bool
    rig_days: float
    duration_days_min: float
    duration_days_max: float
    unit_type: str
    cost_band: str
    risk_flags: list[str]
    mro_status: str
    mro_blocker: str | None
    earliest_start_date: date | None
    rig_slot: dict | None
    score: float
    sop_doc_id: str | None
    sop: dict | None


def evaluate_job(job_code: str, ev: WellEvidence, selection_note: str = "") -> CandidateEval:
    cat = _catalogue()
    row = cat.loc[job_code]
    ic = str(row["intervention_class"])
    fit, fit_ev = diagnostic_fit(job_code, ev)
    requires_rig = bool(row["requires_rig"])
    d_min, d_max = _duration_range(job_code, float(row["est_days"]))
    rig_days = round((d_min + d_max) / 2.0, 1) if requires_rig else 0.0
    if job_code == "NO_JOB_JUSTIFIED":
        d_min = d_max = 0.0
    up = estimate_uplift(ev.well_id, job_code, as_of=ev.as_of)
    uv = up.value
    ps = p_success_beta(job_code, ev)
    p = 0.0 if job_code == "NO_JOB_JUSTIFIED" else ps["p_success"]
    mro = _mro(job_code, ev.as_of) if job_code != "NO_JOB_JUSTIFIED" else {
        "mro_status": "NOT_REQUIRED", "mro_blocker": None, "earliest_feasible_start": None}
    slot = None
    earliest = mro.get("earliest_feasible_start")
    if requires_rig and earliest is not None:
        slot = _rig_slot(str(row["equipment"]), max(1, int(math.ceil(rig_days))), earliest, ev.as_of)
        if slot["status"] == "OK":
            earliest = max(earliest, slot["start_date"])
        elif slot["status"] == "NO_SLOT":
            earliest = None
    flags: list[str] = []
    if job_code != "NO_JOB_JUSTIFIED":
        integrity = (ev.casing_age_years is not None and ev.casing_age_years > CASING_AGE_YEARS) or any(
            h["job_code"] in ("CEMENT_SQUEEZE", "POLYMER_GEL") and h["outcome"] == "FAILED" for h in ev.history)
        if integrity and requires_rig:
            flags.append("WELL_INTEGRITY")
        if ev.failures_24mo >= REPEAT_FAILURES:
            flags.append("REPEAT_FAILURE")
        if (earliest is not None and (earliest - ev.as_of).days > LOGISTICS_DAYS) or (slot and slot["status"] == "NO_SLOT") \
                or mro["mro_status"] == "NO_STOCK":
            flags.append("LOGISTICS_DELAY")
        if ps["n_field"] < LOW_EVIDENCE_N:
            flags.append("LOW_EVIDENCE")
    deferred = float(uv.deferred_bbl_avoided_12mo) if uv is not None else None
    score = 0.0
    if deferred is not None and p:
        score = round(deferred * p / max(rig_days, 0.5) * (1.0 - min(RISK_CAP, RISK_STEP * len(flags))), 1)
    sop_id = row["sop_doc_id"] if isinstance(row["sop_doc_id"], str) else None
    return CandidateEval(
        job_code=job_code, job_name=str(row["job_name"]), ic=ic, ic_label=ic_labels().get(ic, ic),
        selection_note=selection_note, diagnostic_fit=fit, fit_symbol=FIT_SYMBOL[fit], fit_evidence=fit_ev,
        uplift_bopd=uv.uplift_bopd if uv is not None else None, deferred_bbl_12mo=deferred,
        uplift_method=uv.method if uv is not None else None, uplift_status=up.status.value,
        p_success=p if job_code != "NO_JOB_JUSTIFIED" else None, p_success_n=ps["n_field"], p_success_detail=ps,
        requires_rig=requires_rig, rig_days=rig_days, duration_days_min=d_min, duration_days_max=d_max,
        unit_type=str(row["equipment"]), cost_band=str(row["cost_band"]), risk_flags=flags,
        mro_status=mro["mro_status"], mro_blocker=mro.get("mro_blocker"), earliest_start_date=earliest,
        rig_slot=slot, score=score, sop_doc_id=sop_id, sop=sop_steps(sop_id) if sop_id else None)


# =================================================================================================
# TC-022
# =================================================================================================
@dataclass(frozen=True)
class NbaAction:
    rank: int
    job_code: str
    job_name: str
    ic: str
    ic_label: str
    sources: list[str]
    ml_prob: float | None
    diagnostic_fit: str
    fit_symbol: str
    fit_evidence: str
    uplift_bopd: float | None
    deferred_bbl_12mo: float | None
    uplift_method: str | None
    p_success: float | None
    p_success_n: int
    p_success_detail: dict
    rig_days: float
    requires_rig: bool
    unit_type: str
    duration_days_min: float
    duration_days_max: float
    cost_band: str
    risk_flags: list[str]
    mro_status: str
    mro_blocker: str | None
    earliest_start_date: date | None
    rig_slot: dict | None
    score: float
    why: str
    sop_doc_id: str | None
    sop_title: str | None
    sop_url: str | None
    sop_steps: list[dict]
    guardrail: str | None = None


@dataclass(frozen=True)
class NextBestActions:
    well_id: WellId
    field: str
    lift_type: str
    as_of: date
    actions: list[NbaAction]
    rejected: list[dict]
    flags: list[str]
    physics_route: dict | None
    ml_suggestion: dict | None
    evidence: dict
    score_formula: str = SCORE_FORMULA
    notes: list[str] = field(default_factory=list)
    job_menu: list[dict] = field(default_factory=list)   # catalogue jobs for the "why not X?" picker


def _why(c: CandidateEval, ev: WellEvidence) -> str:
    d = c.p_success_detail
    if c.job_code == "NO_JOB_JUSTIFIED":
        return f"{c.job_name}: {c.fit_evidence}."
    up = (f"+{c.uplift_bopd} BOPD, {c.deferred_bbl_12mo:.0f} bbl over 12 months ({c.uplift_method})"
          if c.uplift_bopd is not None else "uplift unavailable (TC-009)")
    ps = (f"p_success {c.p_success:.2f} (n={d['n_field']} {ev.field} {ev.lift_type} {c.ic} jobs, {d['s_field']} successful; "
          f"this well {d['s_well']}/{d['n_well']}; asset prior {d['p_asset']})" if c.p_success is not None
          else "p_success unavailable")
    ex = (f"{'rig' if c.requires_rig else 'rigless'} ({c.unit_type}), {c.rig_days} rig-days, duration "
          f"{c.duration_days_min}-{c.duration_days_max} d, cost band {c.cost_band}; MRO {c.mro_status}")
    rf = f"; risk: {', '.join(c.risk_flags)}" if c.risk_flags else ""
    return f"{c.job_name} ({c.ic} {c.ic_label}). Fit {c.fit_symbol}: {c.fit_evidence}. {up}; {ps}. {ex}{rf}. Score {c.score}."


def _to_action(rank: int, c: CandidateEval, sources: list[str], ml_prob: float | None, ev: WellEvidence,
               guardrail: str | None) -> NbaAction:
    sop = c.sop or {}
    return NbaAction(
        rank=rank, job_code=c.job_code, job_name=c.job_name, ic=c.ic, ic_label=c.ic_label, sources=sources,
        ml_prob=ml_prob, diagnostic_fit=c.diagnostic_fit, fit_symbol=c.fit_symbol, fit_evidence=c.fit_evidence,
        uplift_bopd=c.uplift_bopd, deferred_bbl_12mo=c.deferred_bbl_12mo, uplift_method=c.uplift_method,
        p_success=c.p_success, p_success_n=c.p_success_n, p_success_detail=c.p_success_detail,
        rig_days=c.rig_days, requires_rig=c.requires_rig, unit_type=c.unit_type,
        duration_days_min=c.duration_days_min, duration_days_max=c.duration_days_max, cost_band=c.cost_band,
        risk_flags=c.risk_flags, mro_status=c.mro_status, mro_blocker=c.mro_blocker,
        earliest_start_date=c.earliest_start_date, rig_slot=c.rig_slot, score=c.score,
        why=(f"[{guardrail}] " if guardrail else "") + _why(c, ev), sop_doc_id=c.sop_doc_id,
        sop_title=sop.get("title"), sop_url=sop.get("uri") if c.sop_doc_id else None,
        sop_steps=list(sop.get("phases") or []), guardrail=guardrail)


def _evidence_summary(ev: WellEvidence) -> dict:
    return {"open_episode": ev.open_episode, "tc005_signature": ev.mech, "tc002_chan": ev.chan,
            "water_problem_active": ev.water_active, "tc003_fillage": ev.fillage, "tc004_offsets": ev.offsets,
            "pressure_surveys": ev.pressure, "wht_trend": ev.wht, "health": ev.health,
            "production_casing_age_years": ev.casing_age_years, "failures_24mo": ev.failures_24mo}


def recommend_next_best_action(well_id: WellId, as_of: date | None = None, top_k: int = 3) -> ToolResult:
    return _nba_cached(str(well_id).strip().upper(), as_of or settings.AS_OF, max(1, min(int(top_k), 10)))


@lru_cache(maxsize=512)
def _nba_cached(well_id: WellId, as_of: date, top_k: int) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "top_k": top_k}
    ev = well_evidence(well_id, as_of)
    if ev is None:
        return unavailable(TOOL_ID, params, t0, ["well_id"], f"Well {well_id} not found.")
    cat = _catalogue()
    flags: list[str] = []
    if as_of != settings.AS_OF:
        flags.append("AS_OF_OVERRIDE")
    flags += [f for f in ev.ml["flags"] if f not in flags]
    if ev.ml["status"] == "LOW_CONFIDENCE" and "ML_LOW_CONFIDENCE" not in flags:
        flags.append("ML_LOW_CONFIDENCE")

    # ---- candidates: class -> (job, sources, ml_prob)
    cands: dict[str, dict] = {}

    def add(ic: str, source: str, prob: float | None = None, job: str | None = None, note: str = "") -> None:
        if ic not in CLASS_DEFAULT_JOB:
            return
        if ic not in cands:
            j, why = (job, note) if job else select_job(ic, ev)
            cands[ic] = {"job": j, "sources": [], "ml_prob": None, "note": why}
        cands[ic]["sources"].append(source)
        if prob is not None:
            cands[ic]["ml_prob"] = prob

    rejected: list[dict] = []
    low_ml: list[dict] = []
    for c in ev.ml["top_k"]:
        if c["prob"] >= ML_MIN_PROB:
            add(c["ic"], f"ML {c['ic']} p={c['prob']:.2f}", c["prob"])
        else:
            low_ml.append(c)
    route = ev.route
    physics_route = None
    if route is not None:
        ric = job_ic(route.job_code)
        add(ric, f"TC-008 physics route ({ev.physics['mechanism']})", job=route.job_code,
            note=f"TC-008 physics route for {ev.physics['mechanism']}")
        physics_route = {"mechanism": ev.physics["mechanism"], "source": ev.physics["source"],
                         "evidence": ev.physics["evidence"], "job_code": route.job_code, "ic": ric,
                         "selection_evidence": route.selection_evidence}
        for alt in ALTERNATIVES.get(route.job_code, []):
            aic = job_ic(alt)
            if aic is None:
                continue
            if aic in cands and cands[aic]["job"] != alt:
                rejected.append({"job_code": alt, "ic": aic, "source": "TC-008 alternative",
                                 "reason": f"same class as {cands[aic]['job']}; catalogue criterion: "
                                           f"{cat.loc[alt, 'selection_evidence']}"})
                continue
            add(aic, f"TC-008 alternative to {route.job_code}", job=alt, note=f"TC-008 alternative to {route.job_code}")
    else:
        flags.append("NO_PHYSICS_MECHANISM")

    # ---- guardrails
    forced: dict[str, str] = {}
    g2 = bool(ev.offsets and ev.offsets["verdict"] == "RESERVOIR_DECLINE")
    water_in_play = ev.water_active or any(ic in WATER_CLASSES for ic in cands)
    g1 = bool(not g2 and ev.chan and ev.chan["mechanism"] == "CONING" and ev.chan["wor_prime_slope"] < 0 and water_in_play)
    if g2:
        add("IC-15", "G-2 guardrail (RESERVOIR_DECLINE)", job="NO_JOB_JUSTIFIED", note="G-2")
        forced["IC-15"] = "G-2 RESERVOIR_DECLINE"
        flags.append("G2_RESERVOIR_DECLINE")
    elif g1:
        add("IC-13", "G-1 guardrail (Chan coning)", job="CHOKE_BACK", note="G-1")
        forced["IC-13"] = "G-1 CONING"
        flags.append("G1_CONING_GUARDRAIL")
    ml_top = ev.ml["top_k"][0] if ev.ml["top_k"] else None
    ml_suggestion = None
    if ml_top:
        ml_suggestion = {"ic": ml_top["ic"], "label": ml_top["label"], "prob": ml_top["prob"],
                         "job_code": cands.get(ml_top["ic"], {}).get("job") or CLASS_DEFAULT_JOB.get(ml_top["ic"]),
                         "status": ev.ml["status"]}
    phys_ic = job_ic(route.job_code) if route is not None else None
    if ml_top and phys_ic and ml_top["ic"] != phys_ic:  # G-3
        flags.append("MODEL_PHYSICS_DISAGREEMENT")
    if g1 and ml_top and ml_top["ic"] != "IC-13" and "MODEL_PHYSICS_DISAGREEMENT" not in flags:
        flags.append("MODEL_PHYSICS_DISAGREEMENT")
    for c in low_ml:
        if c["ic"] in cands:
            cands[c["ic"]]["ml_prob"] = c["prob"]
        else:
            rejected.append({"job_code": CLASS_DEFAULT_JOB.get(c["ic"]), "ic": c["ic"], "source": "ML",
                             "reason": f"ML probability {c['prob']:.3f} < {ML_MIN_PROB:.2f}"})

    # ---- evaluate, filter, rank
    ranked: list[tuple[tuple, CandidateEval, dict]] = []
    for ic, c in cands.items():
        ce = evaluate_job(c["job"], ev, c["note"])
        if ic in forced:
            ranked.append(((0, -ce.score, -(c["ml_prob"] or 0.0), ce.job_code), ce, c | {"guardrail": forced[ic]}))
            continue
        if g2:
            rejected.append({"job_code": ce.job_code, "ic": ic, "source": ", ".join(c["sources"]),
                             "reason": f"G-2 RESERVOIR_DECLINE: {ev.offsets['summary']}"})
            continue
        if ce.diagnostic_fit == CONTRADICTED:
            rejected.append({"job_code": ce.job_code, "ic": ic, "source": ", ".join(c["sources"]),
                             "reason": f"diagnostic fit ✘: {ce.fit_evidence}",
                             "demoted_by": "G-1" if (g1 and ic == "IC-11") else None})
            continue
        if ce.job_code == "NO_JOB_JUSTIFIED":
            rejected.append({"job_code": ce.job_code, "ic": ic, "source": ", ".join(c["sources"]),
                             "reason": f"not a refusal case: {ce.fit_evidence}"})
            continue
        tier = 1 if ce.diagnostic_fit == FIT else 2
        ranked.append(((tier, -ce.score, -(c["ml_prob"] or 0.0), ce.job_code), ce, c | {"guardrail": None}))
    ranked.sort(key=lambda t: t[0])
    actions = [_to_action(i + 1, ce, c["sources"], c["ml_prob"], ev, c["guardrail"])
               for i, (_, ce, c) in enumerate(ranked[:top_k])]
    for i, (_, ce, c) in enumerate(ranked[top_k:], start=top_k + 1):
        rejected.append({"job_code": ce.job_code, "ic": ce.ic, "source": ", ".join(c["sources"]),
                         "reason": f"ranked #{i} (fit {ce.fit_symbol}, score {ce.score}) below top-{top_k}"})
    if len(actions) < top_k:
        flags.append("FEWER_THAN_TOP_K")
    notes = ["uplift and deferred barrels are TC-009's decline-restore estimate for the well (the same for every "
             "job); jobs differ by diagnostic fit, p_success, rig-days and risk",
             "no currency: cost is cost_band + rig_days (D-1)",
             "synthetic WellPulse data; ML probabilities are from TC-021 (see its disclosure)"]
    labels = ic_labels()
    menu = [{"job_code": str(j), "job_name": str(r["job_name"]), "ic": str(r["intervention_class"]),
             "ic_label": labels.get(str(r["intervention_class"]), "")}
            for j, r in cat.sort_values(["intervention_class", "job_code"]).iterrows() if j != "PLUG_ABANDON"]
    val = NextBestActions(well_id=well_id, field=ev.field, lift_type=ev.lift_type, as_of=as_of, actions=actions,
                          rejected=rejected, flags=flags, physics_route=physics_route, ml_suggestion=ml_suggestion,
                          evidence=_evidence_summary(ev), notes=notes, job_menu=menu)
    if not actions:
        return ToolResult(ToolStatus.UNAVAILABLE, val, ["candidates"],
                          f"{well_id}: no candidate job survived the diagnostic-fit screen; engineer review.",
                          build_provenance(TOOL_ID, params, t0))
    a1 = actions[0]
    healthy = bool(ev.physics is None and (ev.health or {}).get("bucket") == "PRODUCING_OK")
    if healthy:
        flags.append("WELL_HEALTHY_NO_TRIGGER")
    status = ToolStatus.LOW_CONFIDENCE if (healthy or ("ML_LOW_CONFIDENCE" in flags and not a1.guardrail
                                                       and a1.diagnostic_fit != FIT)) else ToolStatus.OK
    msg = ((f"{well_id} is producing OK with no diagnosed mechanism; actions below are a watch-list, not a "
            f"call to mobilise. " if healthy else "")
           + f"{well_id} as of {as_of}: action 1 {a1.job_code} ({a1.ic}, fit {a1.fit_symbol}, score {a1.score}, "
           f"{a1.rig_days} rig-days, cost band {a1.cost_band}); {len(actions)} action(s), {len(rejected)} rejected"
           + (f"; flags {', '.join(flags)}" if flags else "") + ".")
    return ToolResult(status, val, [], msg, build_provenance(TOOL_ID, params, t0, ml_model=ev.ml.get("model_version")))


# =================================================================================================
# §13.3 recommendation object (replaces the fabricated generate_structured_recommendation fields)
# =================================================================================================
_URGENCY = {"NOT_PRODUCING": ("Immediate", "critical"), "UNDERPERFORMING": ("High", "warning"),
            "AT_RISK": ("Medium", "warning"), "PRODUCING_OK": ("Routine", "healthy")}
_RISK_TEXT = {
    "WELL_INTEGRITY": "Old production casing or a failed squeeze on record: pressure-test casing and review the "
                      "latest cement bond log before pumping.",
    "REPEAT_FAILURE": "Three or more failures in 24 months: include a root-cause review and failed-part analysis.",
    "LOGISTICS_DELAY": "Earliest start is more than 14 days out: confirm rig slot and material transfer now.",
    "LOW_EVIDENCE": "Fewer than five comparable jobs in this field: treat p_success as low-evidence.",
}


def recommendation_from_nba(result: ToolResult) -> dict | None:
    """§13.3 recommendation object built from TC-022 rank 1 (no USD, no payback)."""
    v = result.value
    if v is None or not v.actions:
        return None
    a = v.actions[0]
    bucket = (v.evidence.get("health") or {}).get("bucket")
    urgency, badge = _URGENCY.get(bucket, ("Review", "warning"))
    if a.job_code == "NO_JOB_JUSTIFIED":
        urgency, badge = "No job", "healthy"
    items = [p["phase"] for p in a.sop_steps if p.get("phase")]
    return json.loads(json.dumps({
        "title": a.job_name, "job_code": a.job_code, "intervention_class": a.ic, "urgency": urgency,
        "urgency_badge": badge, "cost_band": a.cost_band, "rig_days": a.rig_days, "requires_rig": a.requires_rig,
        "catalogue_job_codes": [a.job_code],
        "unit_type": a.unit_type, "duration_days_min": a.duration_days_min, "duration_days_max": a.duration_days_max,
        "projected_flow_uplift_bopd": a.uplift_bopd, "deferred_bbl_12mo": a.deferred_bbl_12mo,
        "p_success": a.p_success, "p_success_n": a.p_success_n,
        "action_items": items or ([a.fit_evidence] if a.job_code == "NO_JOB_JUSTIFIED" else []),
        "sop_doc_id": a.sop_doc_id, "sop_url": a.sop_url,
        "risk_mitigation": " ".join(_RISK_TEXT[f] for f in a.risk_flags if f in _RISK_TEXT) or "No risk flag raised.",
        "risk_flags": a.risk_flags, "why": a.why, "flags": list(v.flags), "as_of": v.as_of,
        "provenance": result.provenance,
    }, default=str))  # JSON-safe (dates → ISO) for websocket send_json callers


def _clear() -> None:
    _evidence_cached.cache_clear()
    _nba_cached.cache_clear()
    sop_steps.cache_clear()


register_cache(_clear)
