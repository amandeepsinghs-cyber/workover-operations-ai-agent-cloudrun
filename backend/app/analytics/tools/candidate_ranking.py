"""TC-003…TC-015, TC-017, TC-018 — port of ADK ``tools/candidate_ranking.py`` (v0.3.0).

What changed in the port (SDD §3.2, §6.1):

* **No per-well constants.** v0.3.0 returned hard-coded values for the seven demo wells
  (GK-129/141/055/087/103/112/147) and a constant for every other well (e.g. ETTF 142 d, uplift
  9 BOPD, residual −2.5 %). Every number now comes from the landing tables, TC-001/TC-002 or the
  pinned CoxPH model. Where the data cannot support a value the tool says ``UNAVAILABLE``.
* **Field-aware** (K-6): ``field`` is required for field-level tools; per-well tools resolve the
  well across all fields. ``as_of`` defaults to ``settings.AS_OF``.
* **No currency** (K-7, D-1): TC-010 ranks on ``deferred_bbl_avoided_12mo × p_success ÷ max(rig_days, 0.5)``
  and returns ``cost_band`` + ``rig_days``; ``realisation_per_bbl`` and ₹ fields are gone.
* Job codes are the v0.4 ``job_catalogue`` codes (e.g. ``CEMENT_SQUEEZE``, ``PUMP_OVERHAUL``).
"""

from __future__ import annotations

import math
import pickle
import time
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from functools import lru_cache
from typing import Literal

import numpy as np
import pandas as pd

from app import settings
from app.analytics.generator.fields import FIELD_CONFIGS

from .arps_decline import arps_hyperbolic, fit_decline_curve
from .chan_diagnostic import chan_diagnostic
from .common import (
    Confidence,
    JobCode,
    MechSignature,
    OffsetVerdict,
    ToolResult,
    ToolStatus,
    WaterMechanism,
    WellId,
    build_provenance,
    field_well_ids,
    load_table,
    load_yaml,
    register_cache,
    unavailable,
    well_master_row,
    well_rows,
)
from .hierarchy import field_of, resolve_field

_CFG = load_yaml("triggers.yaml")
_SEV_ORDER = {None: 0, "WATCH": 1, "FLAG": 2, "URGENT": 3}


def _as_of(as_of: date | None) -> date:
    return as_of or settings.AS_OF


def _producing(daily: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    d = daily[(daily["production_date"] >= start) & (daily["production_date"] <= end)]
    return d[d["is_producing"] == True].sort_values("production_date")  # noqa: E712


def _catalogue() -> pd.DataFrame:
    return load_table("job_catalogue").set_index("job_code")


# ---------------------------------------------------------------------------
# TC-003 · fillage_proxy()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FillageResult:
    well_id: WellId
    theoretical_displacement_blpd: float
    actual_liquid_blpd: float
    gap_blpd: float
    gap_pct: float
    volumetric_efficiency_pct: float
    trend_slope_blpd_per_day: float
    is_diverging: bool
    confidence: Confidence


def fillage_proxy(well_id: WellId, as_of: date | None = None, window_days: int = 30) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"well_id": well_id, "as_of": str(as_of), "window_days": window_days}
    w_row = well_master_row(well_id)
    if w_row is None:
        return unavailable("TC-003", params, t0, ["well_id"], f"Well {well_id} not found.")
    if str(w_row["lift_type"]) != "SRP":
        return unavailable("TC-003", params, t0, ["lift_type:SRP"],
                           f"Well {well_id} is {w_row['lift_type']}; not a rod-pumped well.")
    missing = [f for f in ("plunger_diameter_in", "stroke_length_in") if pd.isna(w_row.get(f))]
    if missing:
        return unavailable("TC-003", params, t0, missing,
                           f"Missing SRP geometry fields for {well_id}: {', '.join(missing)}.")

    df_w = _producing(well_rows("daily_production", well_id), as_of - timedelta(days=window_days), as_of)
    if df_w.empty or df_w["spm"].isna().all():
        return unavailable("TC-003", params, t0, ["spm"], f"Missing SPM or producing records for {well_id}.")

    d_in = float(w_row["plunger_diameter_in"])
    s_in = float(w_row["stroke_length_in"])
    ap = (math.pi / 4.0) * (d_in ** 2)
    spm = float(df_w["spm"].iloc[-1])
    rt_frac = float(df_w["runtime_fraction"].iloc[-1])
    theo = round(0.1166 * ap * s_in * spm * rt_frac, 1)
    actual = round(float(df_w["liquid_rate_blpd"].iloc[-7:].mean()), 1)
    gaps = theo - df_w["liquid_rate_blpd"].astype(float).to_numpy()
    slope = round(float(np.polyfit(np.arange(len(gaps)), gaps, 1)[0]), 2) if len(gaps) >= 5 else 0.0

    gap = round(theo - actual, 1)
    gap_pct = round((gap / max(theo, 0.1)) * 100.0, 1)
    vol_eff = round((actual / max(theo, 0.1)) * 100.0, 1)
    is_div = bool(gap_pct > 25.0 and slope > 0.15)
    status = ToolStatus.LOW_CONFIDENCE if vol_eff > 100.0 else ToolStatus.OK
    conf = Confidence.LOW if vol_eff > 100.0 else Confidence.HIGH
    res = FillageResult(well_id, theo, actual, gap, gap_pct, vol_eff, slope, is_div, conf)
    return ToolResult(status, res, [],
                      f"Fillage for {well_id}: theoretical {theo} blpd, actual {actual} blpd (eff {vol_eff}%).",
                      build_provenance("TC-003", params, t0))


# ---------------------------------------------------------------------------
# TC-004 · check_offsets()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OffsetResult:
    well_id: WellId
    verdict: OffsetVerdict
    subject_residual_pct: float
    offset_residuals: list[tuple[WellId, float, float]]
    offset_median_residual_pct: float
    excess_residual_pct: float
    n_offsets_used: int
    confidence: Confidence


def check_offsets(well_id: WellId, as_of: date | None = None, k: int = 6, same_zone_only: bool = True) -> ToolResult:
    return _offsets_cached(well_id, _as_of(as_of), int(k), bool(same_zone_only))


@lru_cache(maxsize=4096)
def _offsets_cached(well_id: WellId, as_of: date, k: int, same_zone_only: bool) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "k": k, "same_zone_only": same_zone_only}
    subj_fit = fit_decline_curve(well_id, as_of=as_of)
    if subj_fit.value is None:
        return ToolResult(ToolStatus.INSUFFICIENT_HISTORY, None, [],
                          f"Cannot compute offset check: subject well {well_id} lacks decline fit.",
                          build_provenance("TC-004", params, t0))
    subj_res = float(subj_fit.value.residual_pct)

    sub_off = well_rows("well_offsets", well_id).copy()
    if same_zone_only and (sub_off["same_zone"] == True).sum() >= 3:  # noqa: E712
        sub_off = sub_off[sub_off["same_zone"] == True]  # noqa: E712
    sub_off = sub_off.sort_values("distance_m").head(k)

    offset_list: list[tuple[WellId, float, float]] = []
    for _, o_row in sub_off.iterrows():
        oid = str(o_row["offset_well_id"])
        o_fit = fit_decline_curve(oid, as_of=as_of)
        if o_fit.value is not None:
            offset_list.append((oid, float(o_fit.value.residual_pct), float(o_row["distance_m"])))

    if len(offset_list) < 3:
        val = OffsetResult(well_id, OffsetVerdict.INSUFFICIENT, subj_res, offset_list, 0.0, 0.0,
                           len(offset_list), Confidence.LOW)
        return ToolResult(ToolStatus.INSUFFICIENT_HISTORY, val, [],
                          f"Fewer than 3 active same-zone offsets for {well_id}.",
                          build_provenance("TC-004", params, t0))

    med_off = round(float(np.median([r for _, r, _ in offset_list])), 1)
    excess = round(subj_res - med_off, 1)
    if abs(excess) <= 5.0 and med_off < -10.0:
        verdict = OffsetVerdict.RESERVOIR_DECLINE
    elif excess < -15.0:
        verdict = OffsetVerdict.WELL_SPECIFIC
    else:
        verdict = OffsetVerdict.MIXED
    res = OffsetResult(well_id, verdict, subj_res, offset_list, med_off, excess, len(offset_list), Confidence.HIGH)
    return ToolResult(ToolStatus.OK, res, [],
                      f"Offset verdict for {well_id}: {verdict.value} (subject {subj_res:+.1f}%, offsets median "
                      f"{med_off:+.1f}%, excess {excess:+.1f}pp).",
                      build_provenance("TC-004", params, t0))


# ---------------------------------------------------------------------------
# TC-005 · detect_mechanical_signature()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MechDiagnosis:
    well_id: WellId
    signature: MechSignature
    confidence: Confidence
    evidence: str
    metrics: dict
    unavailable_discriminators: list[str] = field(default_factory=list)


def _mean(s: pd.Series) -> float | None:
    s = s.dropna().astype(float)
    return float(s.mean()) if len(s) else None


def detect_mechanical_signature(well_id: WellId, as_of: date | None = None, window_days: int | None = None) -> ToolResult:
    return _mech_cached(well_id, _as_of(as_of), int(window_days or _CFG["signatures"]["window_days"]))


@lru_cache(maxsize=4096)
def _mech_cached(well_id: WellId, as_of: date, window_days: int) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "window_days": window_days}
    cfg = _CFG["signatures"]
    w_row = well_master_row(well_id)
    if w_row is None:
        return unavailable("TC-005", params, t0, ["well_id"], f"Well {well_id} not found.")
    p = _producing(well_rows("daily_production", well_id), as_of - timedelta(days=window_days - 1), as_of)
    n_edge = int(cfg["edge_days"])
    if len(p) < 3 * n_edge:
        return ToolResult(ToolStatus.INSUFFICIENT_HISTORY, None, [],
                          f"{well_id}: {len(p)} producing days in the {window_days}-day window (< {3 * n_edge}).",
                          build_provenance("TC-005", params, t0))
    a, b = p.iloc[:n_edge], p.iloc[-n_edge:]
    step_n = int(cfg["scale"]["step_days"])
    pre, post = p.iloc[:-step_n], p.iloc[-step_n:]
    liq_a, liq_b = _mean(a["liquid_rate_blpd"]), _mean(b["liquid_rate_blpd"])
    m = {
        "liquid_change_frac": round(liq_b / liq_a - 1.0, 3) if liq_a else None,
        "chp_change_kgcm2": None,
        "thp_change_frac": None,
        "thp_change_kgcm2": None,
        "liquid_step_frac": None,
        "liquid_cv_ratio": None,
        "gor_change_frac": None,
        "gl_inj_rate_change_frac": None,
        "gl_inj_pressure_change_kgcm2": None,
    }
    chp_a, chp_b = _mean(a["chp_kgcm2"]), _mean(b["chp_kgcm2"])
    if chp_a is not None and chp_b is not None:
        m["chp_change_kgcm2"] = round(chp_b - chp_a, 2)
    thp_a, thp_b = _mean(a["thp_kgcm2"]), _mean(b["thp_kgcm2"])
    if thp_a and thp_b is not None:
        m["thp_change_frac"] = round(thp_b / thp_a - 1.0, 3)
        m["thp_change_kgcm2"] = round(thp_b - thp_a, 2)
    pre_med = float(pre["liquid_rate_blpd"].median()) if len(pre) else None
    if pre_med:
        m["liquid_step_frac"] = round(float(post["liquid_rate_blpd"].mean()) / pre_med - 1.0, 3)
    cv_a = float(a["liquid_rate_blpd"].std() / a["liquid_rate_blpd"].mean()) if liq_a else None
    cv_b = float(b["liquid_rate_blpd"].std() / b["liquid_rate_blpd"].mean()) if liq_b else None
    if cv_a and cv_b is not None:
        m["liquid_cv_ratio"] = round(cv_b / cv_a, 2)
    gor_a, gor_b = _mean(a["gor_scf_bbl"]), _mean(b["gor_scf_bbl"])
    if gor_a and gor_b is not None:
        m["gor_change_frac"] = round(gor_b / gor_a - 1.0, 3)
    lift = str(w_row["lift_type"])
    if lift == "GAS_LIFT":
        gr_a, gr_b = _mean(a["gl_inj_rate_mscfd"]), _mean(b["gl_inj_rate_mscfd"])
        gp_a, gp_b = _mean(a["gl_inj_pressure_kgcm2"]), _mean(b["gl_inj_pressure_kgcm2"])
        if gr_a and gr_b is not None:
            m["gl_inj_rate_change_frac"] = round(gr_b / gr_a - 1.0, 3)
        if gp_a is not None and gp_b is not None:
            m["gl_inj_pressure_change_kgcm2"] = round(gp_b - gp_a, 2)

    vented = bool(w_row.get("casing_vented"))
    unavail = ["closed_casing_annulus"] if vented else []

    def le(x, thr):
        return x is not None and x <= thr

    def ge(x, thr):
        return x is not None and x >= thr

    liq = m["liquid_change_frac"]
    sig, ev = MechSignature.NONE, "no mechanical signature above the noise thresholds"
    c = cfg
    if lift == "GAS_LIFT" and ge(m["gl_inj_rate_change_frac"], c["gl_valve"]["min_inj_rate_rise_frac"]) and le(
            m["gl_inj_pressure_change_kgcm2"], c["gl_valve"]["max_inj_pressure_change_kgcm2"]):
        sig = MechSignature.GL_VALVE
        ev = (f"gas-lift injection rate {m['gl_inj_rate_change_frac']:+.0%} with injection pressure "
              f"{m['gl_inj_pressure_change_kgcm2']:+.1f} kg/cm2 (valve passing / failed)")
    elif ge(m["liquid_cv_ratio"], c["sand"]["min_cv_ratio"]) and le(liq, c["sand"]["max_liquid_change_frac"]):
        sig = MechSignature.SAND
        ev = f"liquid-rate scatter x{m['liquid_cv_ratio']:.1f} with liquid {liq:+.0%} (solids loading)"
    elif lift == "SRP" and not vented and ge(m["chp_change_kgcm2"], c["pump_wear"]["min_chp_rise_kgcm2"]) and le(
            liq, c["pump_wear"]["max_liquid_change_frac"]):
        sig = MechSignature.PUMP_WEAR
        ev = f"CHP {m['chp_change_kgcm2']:+.1f} kg/cm2 with liquid {liq:+.0%} (fluid pound / worn pump)"
    elif ge(m["thp_change_frac"], c["wax"]["min_thp_rise_frac"]) and le(liq, c["wax"]["max_liquid_change_frac"]):
        sig = MechSignature.WAX
        ev = f"THP {m['thp_change_frac']:+.0%} with liquid {liq:+.0%} (flowline / tubing deposition)"
    elif le(m["liquid_step_frac"], c["scale"]["max_step_frac"]) and not ge(
            m["chp_change_kgcm2"], c["scale"]["max_chp_rise_kgcm2"]):
        sig = MechSignature.SCALE
        ev = f"liquid step {m['liquid_step_frac']:+.0%} in the last {step_n} producing days without a CHP rise"
    elif not vented and le(liq, c["tubing_leak"]["max_liquid_change_frac"]) and le(
            m["thp_change_kgcm2"], c["tubing_leak"]["max_thp_change_kgcm2"]) and not ge(
            m["chp_change_kgcm2"], c["tubing_leak"]["max_chp_rise_kgcm2"]):
        sig = MechSignature.TUBING_LEAK
        ev = f"liquid {liq:+.0%} with THP {m['thp_change_kgcm2']:+.1f} kg/cm2 and flat CHP"
    elif lift == "SRP" and ge(m["gor_change_frac"], c["gas_interference"]["min_gor_rise_frac"]) and le(
            liq, c["gas_interference"]["max_liquid_change_frac"]):
        sig = MechSignature.GAS_INTERFERENCE
        ev = f"GOR {m['gor_change_frac']:+.0%} with liquid {liq:+.0%}"

    conf = Confidence.HIGH if sig != MechSignature.NONE else Confidence.MEDIUM
    status = ToolStatus.OK
    if sig == MechSignature.NONE and vented:
        status = ToolStatus.DISCRIMINATOR_UNAVAILABLE
        ev = "casing vented: CHP-based discriminators (pump wear, tubing leak) unavailable; " + ev
    val = MechDiagnosis(well_id, sig, conf, ev, m, unavail)
    return ToolResult(status, val, unavail, f"Mechanical signature for {well_id}: {sig.value} — {ev}.",
                      build_provenance("TC-005", params, t0))


# ---------------------------------------------------------------------------
# TC-006 · predict_failure()  (CoxPH, SRP only — model trained on Geleki v0.3.0, Gate E/N)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FailurePrediction:
    well_id: WellId
    ettf_days: float | None
    ci_low_days: float | None
    ci_high_days: float | None
    predicted_date: date | None
    hazard: float
    confidence: Confidence
    top_features: list[tuple[str, float]]
    model_version: str
    baseline_ettf_days: float | None
    days_in_current_run: int | None = None
    horizon_capped: bool = False


MODEL_VERSION = "coxph-v1.0-geleki"
_FEATURES = ["liquid_rate_obs", "wc_sq_obs", "fillage_gap_obs", "chp_obs", "well_age_days"]


@lru_cache(maxsize=1)
def _coxph():
    with open(settings.MODEL_DIR / "coxph_srp_v1.pkl", "rb") as f:
        return pickle.load(f)


def _current_run_start(well_id: WellId, as_of: date) -> date | None:
    wo = well_rows("workover_history", well_id)
    if wo.empty:
        return None
    ok = wo[(~wo["is_censored"].astype(bool)) & (~wo["outcome"].isin(_CFG["trigger_b"]["exclude_outcomes"]))]
    ok = ok[ok["end_date"].notna() & (ok["end_date"] <= as_of)]
    return (max(ok["end_date"]) + timedelta(days=1)) if len(ok) else None


def _srp_features(well_id: WellId, as_of: date) -> tuple[dict | None, list[str]]:
    w = well_master_row(well_id)
    p = _producing(well_rows("daily_production", well_id), as_of - timedelta(days=29), as_of)
    if p.empty:
        return None, ["daily_production:producing_days_30d"]
    missing = [f for f in ("plunger_diameter_in", "stroke_length_in", "completion_date") if pd.isna(w.get(f))]
    if missing:
        return None, missing
    liq = float(p["liquid_rate_blpd"].mean())
    wc = float(p["water_cut_pct"].mean())
    chp = float(p["chp_kgcm2"].mean())
    spm = float(p["spm"].mean())
    rt = float(p["runtime_fraction"].mean())
    ap = (math.pi / 4.0) * float(w["plunger_diameter_in"]) ** 2
    theo = 0.1166 * ap * float(w["stroke_length_in"]) * spm * rt
    comp = w["completion_date"]
    comp = comp.date() if hasattr(comp, "date") and not isinstance(comp, date) else comp
    return {
        "liquid_rate_obs": liq,
        "wc_sq_obs": (wc / 75.0) ** 2,
        "fillage_gap_obs": max(0.0, theo - liq),
        "chp_obs": chp,
        "well_age_days": float((as_of - comp).days),
    }, []


def predict_failure(well_id: WellId, as_of: date | None = None, model_version: str | None = None) -> ToolResult:
    return _predict_cached(well_id, _as_of(as_of), model_version or MODEL_VERSION)


@lru_cache(maxsize=4096)
def _predict_cached(well_id: WellId, as_of: date, model_version: str) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "model_version": model_version}
    w = well_master_row(well_id)
    if w is None:
        return unavailable("TC-006", params, t0, ["well_id"], f"Well {well_id} not found.")
    if model_version != MODEL_VERSION:
        return unavailable("TC-006", params, t0, ["model_version"], f"Model {model_version} is not deployed.")
    if str(w["lift_type"]) != "SRP":
        return unavailable("TC-006", params, t0, ["lift_type:SRP"],
                           f"{MODEL_VERSION} covers rod-pumped wells only; {well_id} is {w['lift_type']}.")
    feats, missing = _srp_features(well_id, as_of)
    if feats is None:
        return unavailable("TC-006", params, t0, missing, f"Cannot build CoxPH features for {well_id}.")
    cph = _coxph()
    x = pd.DataFrame([feats])[_FEATURES]
    hazard = float(cph.predict_partial_hazard(x).to_numpy().ravel()[0])
    sf = cph.predict_survival_function(x)
    times = sf.index.to_numpy(dtype=float)
    surv = sf.iloc[:, 0].to_numpy(dtype=float)
    run_start = _current_run_start(well_id, as_of)
    t_run = float((as_of - run_start).days) if run_start else 0.0
    s0 = float(np.interp(t_run, times, surv, left=1.0, right=float(surv[-1])))
    capped = False

    def q(level: float) -> float | None:
        nonlocal capped
        if s0 <= 0:
            return None
        cond = surv / s0
        idx = np.where((times > t_run) & (cond <= level))[0]
        if not len(idx):
            capped = True
            return None
        return round(float(times[idx[0]] - t_run), 1)

    ettf, lo, hi = q(0.5), q(0.95), q(0.05)
    coefs = cph.params_
    means = getattr(cph, "_norm_mean", pd.Series(0.0, index=coefs.index))
    contrib = {f: float(coefs[f] * (feats[f] - float(means.get(f, 0.0)))) for f in _FEATURES}
    top = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:3]
    tb = _trigger_b(well_id, as_of)
    base = round(max(0.0, tb["p50_days"] - tb["days_since"]), 1) if tb["available"] else None
    conf = Confidence.MEDIUM if field_of(well_id) == "Geleki" else Confidence.LOW
    pred = FailurePrediction(
        well_id=well_id, ettf_days=ettf, ci_low_days=lo, ci_high_days=hi,
        predicted_date=(as_of + timedelta(days=int(round(ettf)))) if ettf is not None else None,
        hazard=round(hazard, 4), confidence=conf, top_features=[(k, round(v, 3)) for k, v in top],
        model_version=MODEL_VERSION, baseline_ettf_days=base, days_in_current_run=int(t_run),
        horizon_capped=capped,
    )
    status = ToolStatus.OK if conf != Confidence.LOW else ToolStatus.LOW_CONFIDENCE
    note = "" if conf != Confidence.LOW else " (model trained on Geleki SRP wells; out-of-field)"
    ettf_txt = f"{ettf:.0f}d" if ettf is not None else f"beyond model horizon ({times[-1]:.0f}d)"
    return ToolResult(status, pred, [], f"Predicted ETTF for {well_id}: {ettf_txt}, partial hazard {hazard:.3f}{note}.",
                      build_provenance("TC-006", params, t0))


# ---------------------------------------------------------------------------
# TC-007 · trigger_scan()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TriggerResult:
    well_id: WellId
    trigger_a: Literal[None, "WATCH", "FLAG", "URGENT"]
    trigger_a_days: int
    trigger_a_residual_pct: float | None
    trigger_b: bool
    trigger_b_days_since: float | None
    trigger_b_p50_days: float | None
    trigger_c: str | None
    trigger_d: bool
    trigger_d_ettf_days: float | None
    any_fired: bool
    highest_severity: Literal[None, "WATCH", "FLAG", "URGENT"]
    evidence: dict = field(default_factory=dict)


def _tier(x: float) -> str | None:
    a = _CFG["trigger_a"]
    if x < a["urgent_pct"]:
        return "URGENT"
    if x < a["flag_pct"]:
        return "FLAG"
    if x < a["watch_pct"]:
        return "WATCH"
    return None


def trigger_a_state(well_id: WellId, as_of: date) -> dict:
    """Trigger A (spec/04 §8.1) from the TC-001 residual series. Returns tier, days and reasons."""
    a = _CFG["trigger_a"]
    fit = fit_decline_curve(well_id, as_of=as_of)
    out = {"tier": None, "days": 0, "residual_pct": None, "max_last7_pct": None, "reason": None, "fit_status": fit.status.value}
    if fit.value is None:
        out["reason"] = f"no decline fit ({fit.status.value})"
        return out
    v = fit.value
    out["residual_pct"] = v.residual_pct
    if fit.status == ToolStatus.LOW_CONFIDENCE:
        out["reason"] = "decline fit LOW_CONFIDENCE (Trigger A must not fire on a LOW fit)"
        return out
    series = v.residual_series
    n = int(a["persistence_days"])
    if len(series) < n:
        out["reason"] = "fewer residual points than the persistence window"
        return out
    if (as_of - series[-1][0]).days > int(a["max_staleness_days"]):
        out["reason"] = f"last producing residual {series[-1][0]} is stale (post-workover transient or shut-in)"
        return out
    last = series[-n:]
    worst_of_best = max(r for _, r in last)
    out["max_last7_pct"] = worst_of_best
    days = 0
    for _, r in reversed(series):
        if r < a["watch_pct"]:
            days += 1
        else:
            break
    out["days"] = days
    tier = _tier(worst_of_best)
    if tier is None:
        return out
    # no choke change inside the persistence window
    d = well_rows("daily_production", well_id)
    win = d[(d["production_date"] >= last[0][0]) & (d["production_date"] <= last[-1][0]) & (d["is_producing"] == True)]  # noqa: E712
    if win["choke_size_64th"].nunique() > 1:
        out["reason"] = "choke change inside the persistence window suppresses Trigger A"
        return out
    if tier == "URGENT" and v.n_tested_points_90d == 0:
        tier = "FLAG"  # DC-070 / DP-002 allocation cap
        out["reason"] = "capped at FLAG: no TESTED points in the trailing 90 days (DC-070)"
    out["tier"] = tier
    return out


def _weighted_median(values: list[float], weights: list[float]) -> float:
    order = np.argsort(values)
    v = np.asarray(values, dtype=float)[order]
    w = np.maximum(np.asarray(weights, dtype=float)[order], 1e-9)
    c = np.cumsum(w) / w.sum()
    return float(v[int(np.searchsorted(c, 0.5))])


@lru_cache(maxsize=4096)
def _trigger_b(well_id: WellId, as_of: date) -> dict:
    """Trigger B (spec/04 §8.2): days since last intervention vs throughput-weighted p50 of own run-lives."""
    cfg = _CFG["trigger_b"]
    wo = well_rows("workover_history", well_id)
    out = {"available": False, "fired": False, "days_since": None, "p50_days": None, "n_run_lives": 0,
           "reason": None}
    if wo.empty:
        out["reason"] = "no intervention history"
        return out
    ok = wo[(~wo["is_censored"].astype(bool)) & (~wo["outcome"].isin(cfg["exclude_outcomes"]))
            & (wo["start_date"] <= as_of)].sort_values("start_date")
    d = well_rows("daily_production", well_id)
    rl, wt = [], []
    for r in ok.itertuples(index=False):
        if r.run_life_days is None or pd.isna(r.run_life_days) or r.run_life_days <= 0:
            continue
        s = r.start_date - timedelta(days=int(r.run_life_days))
        seg = d[(d["production_date"] >= s) & (d["production_date"] < r.start_date)]
        rl.append(float(r.run_life_days))
        wt.append(float(seg["liquid_rate_blpd"].fillna(0.0).sum()))
    out["n_run_lives"] = len(rl)
    run_start = _current_run_start(well_id, as_of)
    if run_start is not None:
        out["days_since"] = float((as_of - run_start).days + 1)
    if len(rl) < int(cfg["min_prior_run_lives"]):
        out["reason"] = f"{len(rl)} prior run-life(s) (< {cfg['min_prior_run_lives']}): INSUFFICIENT_HISTORY"
        return out
    if run_start is None:
        out["reason"] = "no completed intervention before as_of"
        return out
    out["available"] = True
    out["p50_days"] = round(_weighted_median(rl, wt), 1)
    out["fired"] = bool(out["days_since"] > out["p50_days"])
    return out


@lru_cache(maxsize=64)
def _field_hazards(field: str, as_of: date) -> dict[str, float]:
    hz = {}
    for wid in field_well_ids(field, active_only=True):
        r = predict_failure(wid, as_of=as_of)
        if r.value is not None:
            hz[wid] = r.value.hazard
    return hz


def trigger_c_state(well_id: WellId, as_of: date) -> dict:
    c = _CFG["trigger_c"]
    out = {"signature": None, "source": None, "evidence": None}
    mech = detect_mechanical_signature(well_id, as_of=as_of)
    if mech.value is not None and mech.value.signature != MechSignature.NONE and mech.value.confidence in (
            Confidence.HIGH, Confidence.MEDIUM):
        return {"signature": mech.value.signature.value, "source": "TC-005", "evidence": mech.value.evidence}
    chan = chan_diagnostic(well_id, as_of=as_of)
    if chan.value is not None:
        v = chan.value
        rise = v.water_cut_end_pct - v.water_cut_start_pct
        if (v.mechanism.value in c["water_mechanisms"] and v.confidence in (Confidence.HIGH, Confidence.MEDIUM)
                and rise >= float(c["min_water_cut_rise_pp"])):
            return {"signature": v.mechanism.value, "source": "TC-002",
                    "evidence": f"{v.discriminating_evidence}; water cut {v.water_cut_start_pct:.1f}% -> {v.water_cut_end_pct:.1f}%"}
    return out


def _scan_one(wid: WellId, as_of: date, hazards: dict[str, float], hz_thr: float | None) -> TriggerResult:
    ta = trigger_a_state(wid, as_of)
    tb = _trigger_b(wid, as_of)
    tc = trigger_c_state(wid, as_of)
    td_fired, ettf = False, None
    if wid in hazards and hz_thr is not None:
        td_fired = hazards[wid] >= hz_thr
        pf = predict_failure(wid, as_of=as_of)
        ettf = pf.value.ettf_days if pf.value else None
    sev = ta["tier"]
    for fired, level in ((tc["signature"] is not None, "FLAG"), (tb["fired"], "WATCH"), (td_fired, "WATCH")):
        if fired and _SEV_ORDER[level] > _SEV_ORDER[sev]:
            sev = level
    any_fired = bool(ta["tier"] or tb["fired"] or tc["signature"] or td_fired)
    return TriggerResult(
        well_id=wid, trigger_a=ta["tier"], trigger_a_days=int(ta["days"]), trigger_a_residual_pct=ta["residual_pct"],
        trigger_b=bool(tb["fired"]), trigger_b_days_since=tb["days_since"], trigger_b_p50_days=tb["p50_days"],
        trigger_c=tc["signature"], trigger_d=bool(td_fired), trigger_d_ettf_days=ettf,
        any_fired=any_fired, highest_severity=sev if any_fired else None,
        evidence={"a": ta.get("reason"), "a_max_last7_pct": ta.get("max_last7_pct"), "b": tb.get("reason"),
                  "b_n_run_lives": tb["n_run_lives"], "c_source": tc["source"], "c": tc["evidence"],
                  "d_hazard": hazards.get(wid), "d_threshold": hz_thr},
    )


@lru_cache(maxsize=64)
def _scan_field(field: str, as_of: date) -> tuple[TriggerResult, ...]:
    hazards = _field_hazards(field, as_of)
    pct = float(_CFG["trigger_d"]["hazard_percentile"])
    hz_thr = float(np.percentile(list(hazards.values()), pct)) if len(hazards) >= 5 else None
    return tuple(_scan_one(w, as_of, hazards, hz_thr) for w in field_well_ids(field, active_only=True))


def trigger_scan(field: str, as_of: date | None = None, well_ids: list[WellId] | None = None) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"field": field, "as_of": str(as_of), "well_ids": well_ids}
    f = resolve_field(field or "")
    if f is None:
        return unavailable("TC-007", params, t0, [f"field:{field}"], f"Unknown field '{field}'.")
    results = list(_scan_field(f, as_of))
    if well_ids:
        wanted = {w.upper() for w in well_ids}
        results = [r for r in results if r.well_id in wanted]
    fired = sum(1 for r in results if r.any_fired)
    return ToolResult(ToolStatus.OK, results, [], f"Scanned {len(results)} active wells in {f}; {fired} triggered.",
                      build_provenance("TC-007", params, t0, n_wells=len(results)))


# ---------------------------------------------------------------------------
# TC-008 · route_intervention()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InterventionRoute:
    well_id: WellId
    job_code: JobCode
    job_name: str
    requires_rig: bool
    equipment: str
    duration_days_min: float
    duration_days_max: float
    cost_band: Literal["LOW", "MED", "HIGH"]
    selection_evidence: str
    alternatives: list[tuple[JobCode, str, str]]
    queue: Literal["RIG", "RIGLESS", "NONE"]
    intervention_class: str | None = None
    sop_doc_id: str | None = None


# Mechanism -> v0.4 catalogue job (selection evidence lives in job_catalogue.selection_evidence).
ROUTING: dict[str, JobCode] = {
    "CHANNELLING": "CEMENT_SQUEEZE",
    "CHANNELLING_OR_INJECTOR_BREAKTHROUGH": "CEMENT_SQUEEZE",
    "INJECTOR_BREAKTHROUGH": "CEMENT_SQUEEZE",
    "MULTILAYER": "STRADDLE_PACKER",
    "CONING": "CHOKE_BACK",
    "PUMP_WEAR": "PUMP_OVERHAUL",
    "ROD_PART": "ROD_REPLACE",
    "SUDDEN_MECH": "ROD_REPLACE",
    "TUBING_LEAK": "TUBING_REPLACE",
    "WAX": "WAX_HOTOIL",          # TC-008.6: annulus hot oil is rigless on an SRP well; scraping is not
    "SCALE": "SCALE_ACID_BULLHEAD",
    "SAND": "SAND_CLEANOUT",
    "GL_VALVE": "GLV_REPLACE",
    "GL_INJ_ANOMALY": "GLV_REPLACE",
    "GAS_INTERFERENCE": "GAS_SEP_INSTALL",
    "WATER_CHANNELLING": "CEMENT_SQUEEZE",
    "PI_DECLINE": "MATRIX_ACID",
    "SURFACE": "SURFACE_REPAIR",
    "LIFT_INEFFICIENCY": "LIFT_OPTIM",
    "CASING_LEAK": "CASING_REPAIR",
    "BYPASSED_PAY": "ADD_PERFORATION",
    "WATER_ZONE": "STRADDLE_PACKER",
}
# Same-problem alternatives considered (and why they lose) — catalogue codes only.
ALTERNATIVES: dict[JobCode, list[JobCode]] = {
    "CEMENT_SQUEEZE": ["STRADDLE_PACKER", "POLYMER_GEL"],
    "STRADDLE_PACKER": ["CEMENT_SQUEEZE"],
    "CHOKE_BACK": ["CEMENT_SQUEEZE"],
    "PUMP_OVERHAUL": ["LIFT_OPTIM"],
    "ROD_REPLACE": ["PUMP_OVERHAUL"],
    "TUBING_REPLACE": ["PUMP_OVERHAUL"],
    "WAX_HOTOIL": ["WAX_SCRAPE", "WAX_SOLVENT"],
    "SCALE_ACID_BULLHEAD": ["SCALE_INHIBITOR"],
    "SAND_CLEANOUT": ["SAND_CONTROL"],
    "GLV_REPLACE": ["LIFT_OPTIM"],
    "GAS_SEP_INSTALL": ["LIFT_OPTIM"],
    "MATRIX_ACID": ["RE_PERFORATION", "HYDRAULIC_FRAC"],
    "SURFACE_REPAIR": [],
    "LIFT_OPTIM": ["LIFT_CONVERSION"],
    "CASING_REPAIR": ["CEMENT_SQUEEZE"],
    "ADD_PERFORATION": ["ZONE_TRANSFER"],
}


def _duration_range(job_code: JobCode, est_days: float) -> tuple[float, float]:
    """p25–p75 of historical rig-days for the job (all fields); catalogue estimate if < 5 records."""
    wo = load_table("workover_history")
    h = wo[(wo["catalogue_job_code"] == job_code) & (~wo["is_censored"].astype(bool))]["rig_days"].dropna()
    h = h[h > 0]
    if len(h) >= 5:
        return round(float(h.quantile(0.25)), 1), round(float(h.quantile(0.75)), 1)
    return float(est_days), float(est_days)


def route_intervention(well_id: WellId, mechanism: str, offset_verdict: OffsetVerdict | str,
                       evidence: dict | None = None) -> ToolResult:
    t0 = time.perf_counter()
    verdict = OffsetVerdict(offset_verdict) if not isinstance(offset_verdict, OffsetVerdict) else offset_verdict
    params = {"well_id": well_id, "mechanism": mechanism, "offset_verdict": verdict.value}
    if well_master_row(well_id) is None:
        return unavailable("TC-008", params, t0, ["well_id"], f"Well {well_id} not found.")
    cat = _catalogue()
    ev_txt = "; ".join(f"{k}: {v}" for k, v in (evidence or {}).items() if v is not None)

    if verdict == OffsetVerdict.RESERVOIR_DECLINE:  # TC-008.2: unconditional refusal
        row = cat.loc["NO_JOB_JUSTIFIED"]
        off = check_offsets(well_id).value
        detail = (f"subject {off.subject_residual_pct:+.1f}% vs {off.n_offsets_used} offsets median "
                  f"{off.offset_median_residual_pct:+.1f}% (excess {off.excess_residual_pct:+.1f} pp)") if off else ""
        route = InterventionRoute(
            well_id, "NO_JOB_JUSTIFIED", str(row["job_name"]), False, "NONE", 0.0, 0.0, "LOW",
            f"{row['selection_evidence']}. {detail}".strip(),
            [(ROUTING.get(mechanism, "CEMENT_SQUEEZE"), str(cat.loc[ROUTING.get(mechanism, 'CEMENT_SQUEEZE'), 'job_name']),
              "Rejected: decline is shared with same-zone offsets; a wellbore job cannot restore reservoir pressure.")],
            "NONE", str(row["intervention_class"]), None)
        return ToolResult(ToolStatus.OK, route, [], f"{well_id} routed to NO_JOB_JUSTIFIED (RESERVOIR_DECLINE).",
                          build_provenance("TC-008", params, t0))

    job = ROUTING.get(str(mechanism))
    if job is None or job not in cat.index:
        return unavailable("TC-008", params, t0, [f"mechanism:{mechanism}"],
                           f"No catalogue route for mechanism '{mechanism}'; engineer review required.")
    row = cat.loc[job]
    d_min, d_max = _duration_range(job, float(row["est_days"]))
    wo = well_rows("workover_history", well_id)
    alts = []
    for alt in ALTERNATIVES.get(job, []):
        if alt not in cat.index:
            continue
        a = cat.loc[alt]
        failed = wo[(wo["catalogue_job_code"] == alt) & (wo["outcome"] == "FAILED")] if len(wo) else wo
        if len(failed):
            fr = failed.sort_values("start_date").iloc[-1]
            why = f"Rejected: {alt} failed on this well ({fr['workover_id']}, {fr['start_date']})."
        elif bool(a["requires_rig"]) and not bool(row["requires_rig"]):
            why = f"Rejected: needs a rig ({a['equipment']}); the recommended job is rigless."
        else:
            why = f"Alternative when: {a['selection_evidence']}."
        alts.append((alt, str(a["job_name"]), why))
    requires_rig = bool(row["requires_rig"])
    route = InterventionRoute(
        well_id=well_id, job_code=job, job_name=str(row["job_name"]), requires_rig=requires_rig,
        equipment=str(row["equipment"]), duration_days_min=d_min, duration_days_max=d_max,
        cost_band=str(row["cost_band"]),
        selection_evidence=f"{row['selection_evidence']}" + (f" | {ev_txt}" if ev_txt else ""),
        alternatives=alts, queue="RIG" if requires_rig else "RIGLESS",
        intervention_class=str(row["intervention_class"]), sop_doc_id=row["sop_doc_id"] if isinstance(row["sop_doc_id"], str) else None,
    )
    return ToolResult(ToolStatus.OK, route, [], f"Routed {well_id} ({mechanism}) -> {job} ({route.queue}).",
                      build_provenance("TC-008", params, t0))


# ---------------------------------------------------------------------------
# TC-009 · estimate_uplift()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UpliftEstimate:
    well_id: WellId
    current_bopd: float
    expected_post_job_bopd: float
    uplift_bopd: float
    deferred_bbl_avoided_12mo: float
    method: str
    p_success: float | None
    p_success_n: int
    confidence: Confidence
    p_success_scope: str | None = None


def job_success_rate(job_code: JobCode, field: str | None) -> tuple[float | None, int, str | None]:
    """Share of SUCCESS among finished jobs with this catalogue code (same field if n >= 10, else all fields)."""
    wo = load_table("workover_history")
    h = wo[(wo["catalogue_job_code"] == job_code) & (wo["outcome"].isin(["SUCCESS", "PARTIAL", "FAILED"]))]
    if field is not None:
        hf = h[h["field"] == field]
        if len(hf) >= 10:
            return round(float((hf["outcome"] == "SUCCESS").mean()), 2), int(len(hf)), field
    if len(h) == 0:
        return None, 0, None
    return round(float((h["outcome"] == "SUCCESS").mean()), 2), int(len(h)), "ALL_FIELDS"


def estimate_uplift(well_id: WellId, job_code: JobCode, as_of: date | None = None) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"well_id": well_id, "job_code": job_code, "as_of": str(as_of)}
    if well_master_row(well_id) is None:
        return unavailable("TC-009", params, t0, ["well_id"], f"Well {well_id} not found.")
    if job_code not in _catalogue().index:
        return unavailable("TC-009", params, t0, ["job_code"], f"Unknown job_code {job_code}.")
    fld = field_of(well_id)
    p_succ, p_n, scope = job_success_rate(job_code, fld)
    fit = fit_decline_curve(well_id, as_of=as_of)
    recent = _producing(well_rows("daily_production", well_id), as_of - timedelta(days=13), as_of)
    if fit.value is not None:
        current = float(fit.value.actual_bopd)
    elif len(recent):
        current = round(float(recent["oil_rate_bopd"].tail(7).mean()), 1)
    else:
        return unavailable("TC-009", params, t0, ["daily_production:recent_producing_days"],
                           f"{well_id} has no recent producing days to estimate a current rate.",
                           status=ToolStatus.INSUFFICIENT_HISTORY)
    if job_code == "NO_JOB_JUSTIFIED":
        est = UpliftEstimate(well_id, current, current, 0.0, 0.0, "NONE", None, 0, Confidence.HIGH, None)
        return ToolResult(ToolStatus.OK, est, [], f"{well_id}: no job, no uplift.", build_provenance("TC-009", params, t0))

    if fit.value is not None and fit.status == ToolStatus.OK:
        v = fit.value
        method = "DECLINE_RESTORE"
        expected = float(v.expected_bopd)
        t_now = float((as_of - v.fit_origin_date).days)
        k = np.arange(1, 366, dtype=float)
        ratio = arps_hyperbolic(t_now + k, v.qi_bopd, v.b, v.di_per_day) / max(
            float(arps_hyperbolic(np.array([t_now]), v.qi_bopd, v.b, v.di_per_day)[0]), 1e-6)
        conf = Confidence.HIGH if p_n >= 20 else Confidence.MEDIUM
    else:
        # analogue: median post/pre oil ratio of SUCCESS jobs with this catalogue code
        wo = load_table("workover_history")
        h = wo[(wo["catalogue_job_code"] == job_code) & (wo["outcome"] == "SUCCESS")
               & (wo["pre_job_oil_bopd"] > 0) & wo["post_job_oil_bopd"].notna()]
        if len(h) < 5:
            return unavailable("TC-009", params, t0, ["decline_fit", "job_analogues"],
                               f"No reliable decline fit for {well_id} and < 5 analogue jobs for {job_code}.",
                               status=ToolStatus.INSUFFICIENT_HISTORY)
        method = "ANALOGUE"
        expected = current * float((h["post_job_oil_bopd"] / h["pre_job_oil_bopd"]).median())
        ratio = np.ones(365)
        conf = Confidence.LOW
    uplift = round(max(0.0, expected - current), 1)
    deferred = round(float(uplift * ratio.sum()), 0)
    est = UpliftEstimate(well_id, round(current, 1), round(expected, 1), uplift, deferred, method, p_succ, p_n, conf, scope)
    status = ToolStatus.OK if conf != Confidence.LOW else ToolStatus.LOW_CONFIDENCE
    ps = f"{p_succ:.0%}" if p_succ is not None else "n/a"
    return ToolResult(status, est, [],
                      f"Uplift for {well_id} ({job_code}): +{uplift} BOPD, {deferred:.0f} bbl over 12 mo "
                      f"(P(success)={ps}, n={p_n}, {method}).",
                      build_provenance("TC-009", params, t0))


# ---------------------------------------------------------------------------
# TC-010 · rank_candidates()  (K-7: no currency)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CandidateRow:
    rank: int
    well_id: WellId
    queue: Literal["RIG", "RIGLESS"]
    mechanism: str
    job_code: JobCode
    job_name: str
    rig_days: float
    deferred_bbl_avoided_12mo: float
    p_success: float | None
    p_success_n: int
    priority_score: float
    cost_band: str
    uplift_bopd: float
    cluster_id: str | None
    highest_severity: str | None
    mechanism_source: str


@dataclass(frozen=True)
class CandidateQueues:
    rig_queue: list[CandidateRow]
    rigless_queue: list[CandidateRow]
    excluded_refusals: list[tuple[WellId, str, str]]
    excluded_unrouted: list[tuple[WellId, str]] = field(default_factory=list)
    score_formula: str = "deferred_bbl_avoided_12mo * p_success / max(rig_days, 0.5)"


def _mechanism_for(tr: TriggerResult, as_of: date) -> tuple[str | None, str]:
    if tr.trigger_c:
        return tr.trigger_c, f"trigger C ({tr.evidence.get('c_source')})"
    if tr.trigger_b or tr.trigger_d:
        wo = well_rows("workover_history", tr.well_id)
        wo = wo[(~wo["is_censored"].astype(bool)) & (wo["start_date"] <= as_of) & wo["failure_code"].isin(ROUTING)]
        if len(wo):
            last = wo.sort_values("start_date").iloc[-1]
            return str(last["failure_code"]), f"run-life/hazard trigger; last failure mode on {last['start_date']}"
    return None, "no diagnosed mechanism"


@lru_cache(maxsize=64)
def _rank_field(field: str, as_of: date) -> CandidateQueues:
    scan = _scan_field(field, as_of)
    wm = load_table("well_master").set_index("well_id")
    rig, rigless, refusals, unrouted = [], [], [], []
    for tr in scan:
        if not tr.any_fired:
            continue
        off = check_offsets(tr.well_id, as_of=as_of)
        verdict = off.value.verdict if off.value is not None else OffsetVerdict.INSUFFICIENT
        mech, src = _mechanism_for(tr, as_of)
        if verdict == OffsetVerdict.RESERVOIR_DECLINE:
            rt = route_intervention(tr.well_id, mech or "CHANNELLING", verdict).value
            refusals.append((tr.well_id, "NO_JOB_JUSTIFIED", rt.selection_evidence))
            continue
        if mech is None:
            unrouted.append((tr.well_id, "NO_MECHANISM_DIAGNOSED: trigger fired without a signature; engineer review"))
            continue
        rr = route_intervention(tr.well_id, mech, verdict)
        if rr.value is None:
            unrouted.append((tr.well_id, rr.message))
            continue
        rt = rr.value
        up = estimate_uplift(tr.well_id, rt.job_code, as_of=as_of).value
        if up is None:
            unrouted.append((tr.well_id, f"uplift unavailable for {rt.job_code}"))
            continue
        rig_days = round((rt.duration_days_min + rt.duration_days_max) / 2.0, 1) if rt.requires_rig else 0.0
        p = up.p_success if up.p_success is not None else 0.0
        score = round(up.deferred_bbl_avoided_12mo * p / max(rig_days, 0.5), 1)
        row = CandidateRow(0, tr.well_id, rt.queue, mech, rt.job_code, rt.job_name, rig_days,
                           up.deferred_bbl_avoided_12mo, up.p_success, up.p_success_n, score, rt.cost_band,
                           up.uplift_bopd, wm.loc[tr.well_id, "cluster_id"], tr.highest_severity, src)
        (rig if rt.queue == "RIG" else rigless).append(row)
    rig.sort(key=lambda r: (-r.priority_score, r.well_id))
    rigless.sort(key=lambda r: (-r.priority_score, r.well_id))
    return CandidateQueues([replace(r, rank=i + 1) for i, r in enumerate(rig)],
                           [replace(r, rank=i + 1) for i, r in enumerate(rigless)], refusals, unrouted)


def rank_candidates(field: str, as_of: date | None = None) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"field": field, "as_of": str(as_of)}
    f = resolve_field(field or "")
    if f is None:
        return unavailable("TC-010", params, t0, [f"field:{field}"], f"Unknown field '{field}'.")
    q = _rank_field(f, as_of)
    return ToolResult(ToolStatus.OK, q, [],
                      f"{f}: {len(q.rig_queue)} RIG, {len(q.rigless_queue)} RIGLESS candidates, "
                      f"{len(q.excluded_refusals)} refusal(s), {len(q.excluded_unrouted)} need engineer review.",
                      build_provenance("TC-010", params, t0))


# ---------------------------------------------------------------------------
# TC-011 · check_mro()
# ---------------------------------------------------------------------------
JOB_ITEMS: dict[JobCode, list[str]] = {
    "CEMENT_SQUEEZE": ["CEMENT_RETAINER_55"],
    "PUMP_OVERHAUL": ["SRP_PLUNGER_150", "SRP_VALVE_ROD"],
    "ROD_REPLACE": ["ROD_GRADE_D_78", "POLISHED_ROD_125"],
    "TUBING_REPLACE": ["TUBING_J55_278"],
    "WAX_HOTOIL": ["PARAFFIN_SOLVENT_BBL"],
    "WAX_SOLVENT": ["PARAFFIN_SOLVENT_BBL"],
    "SCALE_ACID_BULLHEAD": ["SCALE_INHIBITOR_DRUM"],
    "SCALE_INHIBITOR": ["SCALE_INHIBITOR_DRUM"],
    "GLV_REPLACE": ["GAS_LIFT_VALVE_1IN"],
    "STRADDLE_PACKER": ["BRIDGE_PLUG_55"],
}


def check_mro(job_code: JobCode, required_date: date | None = None, primary_base: str = "NAZIRA") -> ToolResult:
    t0 = time.perf_counter()
    required_date = required_date or (settings.AS_OF + timedelta(days=2))
    params = {"job_code": job_code, "required_date": str(required_date), "primary_base": primary_base}
    mro = load_table("mro_inventory")
    items = JOB_ITEMS.get(job_code, [])
    blocker, alt_base, transit = None, None, 0
    checked = []
    for item in items:
        rows = mro[mro["item_code"] == item]
        prim = rows[rows["base"] == primary_base]
        on_hand = int(prim["qty_on_hand"].sum()) if len(prim) else 0
        checked.append({"item_code": item, "primary_qty_on_hand": on_hand})
        if on_hand > 0:
            continue
        alts = rows[(rows["base"] != primary_base) & (rows["qty_on_hand"] > 0)].sort_values("transit_days")
        if len(alts):
            a = alts.iloc[0]
            if int(a["transit_days"]) >= transit:
                blocker, alt_base, transit = str(a["item_name"]), str(a["base"]), int(a["transit_days"])
        else:
            blocker, alt_base, transit = str(rows.iloc[0]["item_name"]) if len(rows) else item, None, None
            break
    res = {
        "job_code": job_code, "primary_base": primary_base, "alternate_base": alt_base,
        "governing_blocker": blocker, "transit_days": transit,
        "earliest_feasible_start": (required_date + timedelta(days=transit)) if transit is not None else None,
        "items_checked": checked,
    }
    status = ToolStatus.OK if transit is not None else ToolStatus.UNAVAILABLE
    return ToolResult(status, res, [] if transit is not None else ["mro_inventory:stock"],
                      f"MRO check for {job_code}: earliest start {res['earliest_feasible_start']} (blocker={blocker}).",
                      build_provenance("TC-011", params, t0))


# ---------------------------------------------------------------------------
# TC-012 · search_well_history()  (keyword match over document_index; TC-026 TF-IDF replaces it in Stage O)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DocumentHit:
    doc_id: str
    doc_type: str
    doc_date: date | None
    title: str
    gcs_uri: str | None
    excerpt: str
    relevance: float


def search_well_history(well_id: WellId, query: str = "workover history", top_k: int = 5) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "query": query, "top_k": top_k}
    if well_master_row(well_id) is None:
        return unavailable("TC-012", params, t0, ["well_id"], f"Well {well_id} not found.")
    docs = well_rows("document_index", well_id)
    terms = {t for t in query.lower().replace("-", " ").split() if len(t) > 2}
    hits = []
    for r in docs.itertuples(index=False):
        text = f"{r.title} {r.doc_type}".lower()
        score = sum(1 for t in terms if t in text) / max(len(terms), 1)
        hits.append(DocumentHit(r.doc_id, r.doc_type, r.doc_date, r.title, getattr(r, "gcs_uri", None), r.title,
                                round(score, 2)))
    hits.sort(key=lambda h: (-h.relevance, str(h.doc_date)), reverse=False)
    hits = [h for h in hits if h.relevance > 0][:top_k] or sorted(hits, key=lambda h: str(h.doc_date), reverse=True)[:top_k]
    return ToolResult(ToolStatus.OK, hits, [], f"Found {len(hits)} document(s) for {well_id}.",
                      build_provenance("TC-012", params, t0))


# ---------------------------------------------------------------------------
# TC-013 · generate_draft_plan()
# ---------------------------------------------------------------------------
def generate_draft_plan(well_id: WellId, run_date: date | None = None) -> ToolResult:
    t0 = time.perf_counter()
    run_date = _as_of(run_date)
    params = {"well_id": well_id, "run_date": str(run_date)}
    if well_master_row(well_id) is None:
        return unavailable("TC-013", params, t0, ["well_id"], f"Well {well_id} not found.")
    U = "[UNAVAILABLE]"
    arps = fit_decline_curve(well_id, as_of=run_date).value
    tr = trigger_scan(field_of(well_id), as_of=run_date, well_ids=[well_id]).value
    tr = tr[0] if tr else None
    offsets = check_offsets(well_id, as_of=run_date).value
    verdict = offsets.verdict if offsets else OffsetVerdict.INSUFFICIENT
    mech, src = _mechanism_for(tr, run_date) if tr else (None, "well not active")
    chan = chan_diagnostic(well_id, as_of=run_date).value
    route = route_intervention(well_id, mech, verdict).value if (mech or verdict == OffsetVerdict.RESERVOIR_DECLINE) else None
    uplift = estimate_uplift(well_id, route.job_code, as_of=run_date).value if route else None
    mro = check_mro(route.job_code, required_date=run_date + timedelta(days=2)).value if route else None
    docs = search_well_history(well_id, query=f"{route.job_name if route else ''} workover completion").value
    plan = {
        "well_id": well_id,
        "run_date": str(run_date),
        "approval_status": "AWAITING REVIEW",  # TC-013.3: never APPROVED inside this tool
        "why_this_well_now": (f"Producing {arps.actual_bopd} BOPD vs {arps.expected_bopd} BOPD expected "
                              f"({arps.residual_pct:+.1f}% residual)." if arps else f"Decline fit {U}."),
        "triggers": tr,
        "diagnosis": {
            "mechanism": mech or U,
            "mechanism_source": src,
            "wor_prime_slope": chan.wor_prime_slope if chan else U,
            "offset_verdict": verdict.value,
        },
        "recommended_job": ({"job_code": route.job_code, "job_name": route.job_name, "queue": route.queue,
                             "requires_rig": route.requires_rig, "cost_band": route.cost_band,
                             "duration_days_min": route.duration_days_min, "duration_days_max": route.duration_days_max,
                             "selection_evidence": route.selection_evidence} if route else U),
        "rejected_alternatives": route.alternatives if route else [],
        "value_estimate": ({"uplift_bopd": uplift.uplift_bopd, "deferred_bbl_avoided_12mo": uplift.deferred_bbl_avoided_12mo,
                            "p_success": uplift.p_success, "p_success_n": uplift.p_success_n} if uplift else U),
        "logistics": mro or U,
        "citations": docs,
        "numeric_provenance": {
            "actual_bopd": "TC-001:fit_decline_curve", "wor_prime_slope": "TC-002:chan_diagnostic",
            "offset_verdict": "TC-004:check_offsets", "uplift_bopd": "TC-009:estimate_uplift",
            "p_success": "TC-009:workover_history outcomes", "logistics": "TC-011:mro_inventory",
        },
    }
    return ToolResult(ToolStatus.OK, plan, [], f"Draft intervention plan for {well_id} (status=AWAITING REVIEW).",
                      build_provenance("TC-013", params, t0))


# ---------------------------------------------------------------------------
# TC-014 · generate_report()
# ---------------------------------------------------------------------------
def generate_report(field: str, period: Literal["DAILY", "WEEKLY", "MONTHLY"] = "WEEKLY",
                    as_of: date | None = None) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"field": field, "period": period, "as_of": str(as_of)}
    f = resolve_field(field or "")
    if f is None:
        return unavailable("TC-014", params, t0, [f"field:{field}"], f"Unknown field '{field}'.")
    ranked = _rank_field(f, as_of)
    wm = load_table("well_master")
    w = wm[wm["field"] == f]
    dl = load_table("decision_log")
    dl = dl[dl["well_id"].map(field_of) == f] if len(dl) else dl
    report = {
        "field": f, "period": period, "as_of": str(as_of), "is_stale": False,
        "summary": {
            "total_wells": int(len(w)), "active_wells": int((w["status"] == "ACTIVE").sum()),
            "permanently_idle_wells": int((w["status"] != "ACTIVE").sum()),
            "rig_queue_count": len(ranked.rig_queue), "rigless_queue_count": len(ranked.rigless_queue),
            "refusal_count": len(ranked.excluded_refusals), "engineer_review_count": len(ranked.excluded_unrouted),
        },
        "rig_queue": ranked.rig_queue, "rigless_queue": ranked.rigless_queue,
        "refusals": ranked.excluded_refusals,
        "where_the_system_was_wrong": (
            [{"well_id": r.well_id, "decision": r.decision, "reason": r.reason_text} for r in dl.itertuples()
             if r.decision in ("REJECT", "MODIFY")] if len(dl) else None),
        "where_the_system_was_wrong_note": None if len(dl) else
            "UNAVAILABLE: no reviewer decisions recorded for this field (decision_log).",
    }
    return ToolResult(ToolStatus.OK, report, [], f"{period} allocation report for {f} as of {as_of}.",
                      build_provenance("TC-014", params, t0))


# ---------------------------------------------------------------------------
# TC-015 · schedule_rigs()
# ---------------------------------------------------------------------------
def schedule_rigs(field: str, as_of: date | None = None, horizon_days: int = 30) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"field": field, "as_of": str(as_of), "horizon_days": horizon_days}
    f = resolve_field(field or "")
    if f is None:
        return unavailable("TC-015", params, t0, [f"field:{field}"], f"Unknown field '{field}'.")
    ranked = _rank_field(f, as_of)
    cal = load_table("rig_calendar")
    end = as_of + timedelta(days=horizon_days)
    cal = cal[(cal["date"] > as_of) & (cal["date"] <= end)]
    free: dict[str, set] = {rid: set(g[g["status"] == "AVAILABLE"]["date"]) for rid, g in cal.groupby("rig_id")}
    rig_class = {rid: str(g["rig_class"].iloc[0]) for rid, g in cal.groupby("rig_id")}
    cat = _catalogue()
    assignments, unscheduled = [], []
    for cand in ranked.rig_queue:
        need = max(1, int(math.ceil(cand.rig_days)))
        equip = str(cat.loc[cand.job_code, "equipment"])
        mro = check_mro(cand.job_code, required_date=as_of + timedelta(days=1)).value
        start_min = mro["earliest_feasible_start"] or end
        best = None
        for rid in sorted(free):
            if equip == "WORKOVER_RIG" and rig_class[rid] != "WORKOVER_RIG":
                continue
            days = sorted(d for d in free[rid] if d >= start_min)
            for d0 in days:
                span = [d0 + timedelta(days=i) for i in range(need)]
                if all(s in free[rid] for s in span) and (best is None or d0 < best[1]):
                    best = (rid, d0, span)
                    break
        if best is None:
            unscheduled.append({"well_id": cand.well_id, "job_code": cand.job_code,
                                "reason": f"no {equip} window of {need} free day(s) in {horizon_days} d"})
            continue
        rid, d0, span = best
        free[rid] -= set(span)
        assignments.append({"rig_id": rid, "rig_class": rig_class[rid], "well_id": cand.well_id,
                            "job_code": cand.job_code, "start_date": str(d0), "end_date": str(span[-1]),
                            "rig_days": cand.rig_days, "deferred_bbl_avoided_12mo": cand.deferred_bbl_avoided_12mo,
                            "mro_blocker": mro["governing_blocker"]})
    sched = {"field": f, "as_of": str(as_of), "horizon_days": horizon_days, "rig_assignments": assignments,
             "unscheduled": unscheduled,
             "rigless_bypassed_to_surface_crews": [r.well_id for r in ranked.rigless_queue]}
    return ToolResult(ToolStatus.OK, sched, [],
                      f"Scheduled {len(assignments)} rig job(s) for {f}; {len(unscheduled)} unscheduled; "
                      f"{len(ranked.rigless_queue)} rigless job(s) to surface crews.",
                      build_provenance("TC-015", params, t0))


# ---------------------------------------------------------------------------
# TC-017 · plot_production()  (data only; TC-017 v2 chart is Stage T)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SeriesPoint:
    d: date
    value: float | None
    source: Literal["ALLOCATED", "TESTED", "NULL"]


@dataclass(frozen=True)
class InterventionMarker:
    d: date
    job_code: JobCode
    label: str
    outcome: Literal["SUCCESS", "PARTIAL", "FAILED", "UNKNOWN"]


@dataclass(frozen=True)
class ProductionSeries:
    well_id: WellId
    series: dict[str, list[SeriesPoint]]
    units: dict[str, str]
    axis_assignment: dict[str, Literal["LEFT", "RIGHT"]]
    decline_fit: list[SeriesPoint] | None
    interventions: list[InterventionMarker]
    n_producing_days: int
    n_null_days: int


_COLS = {
    "oil": ("oil_rate_bopd", "BOPD", "LEFT"), "water": ("water_rate_bwpd", "BWPD", "LEFT"),
    "gas": ("gas_rate_mscfd", "MSCFD", "LEFT"), "liquid": ("liquid_rate_blpd", "BLPD", "LEFT"),
    "water_cut": ("water_cut_pct", "% (water / (oil + water) * 100)", "RIGHT"),
    "thp": ("thp_kgcm2", "kg/cm2", "RIGHT"), "chp": ("chp_kgcm2", "kg/cm2", "RIGHT"),
    "runtime": ("runtime_hours", "hours/day", "RIGHT"), "gor": ("gor_scf_bbl", "scf/bbl", "RIGHT"),
    "wht": ("wht_degc", "degC", "RIGHT"), "gl_inj_rate": ("gl_inj_rate_mscfd", "MSCFD", "RIGHT"),
    "gl_inj_pressure": ("gl_inj_pressure_kgcm2", "kg/cm2", "RIGHT"),
}


def plot_production(well_id: WellId, months: int = 36, metrics: list[str] | None = None,
                    overlay_decline_fit: bool = True, overlay_interventions: bool = True,
                    as_of: date | None = None) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    metrics = metrics or ["oil", "water_cut"]
    params = {"well_id": well_id, "months": months, "metrics": metrics, "overlay_decline_fit": overlay_decline_fit,
              "overlay_interventions": overlay_interventions, "as_of": str(as_of)}
    if well_master_row(well_id) is None:
        return unavailable("TC-017", params, t0, ["well_id"], f"Well {well_id} not found.")
    start = as_of - timedelta(days=int(months * 30.4375))
    d = well_rows("daily_production", well_id)
    df_w = d[(d["production_date"] >= start) & (d["production_date"] <= as_of)].sort_values("production_date")
    if (df_w["is_producing"] == True).sum() < 90:  # noqa: E712
        return unavailable("TC-017", params, t0, [], f"Fewer than 90 producing days for {well_id}.",
                           status=ToolStatus.INSUFFICIENT_HISTORY)
    series, units, axes = {}, {}, {}
    prod = df_w["is_producing"].to_numpy(dtype=bool)
    dates = df_w["production_date"].tolist()
    src = df_w["data_source"].tolist()
    for m in metrics:
        if m not in _COLS:
            continue
        col, u, ax = _COLS[m]
        vals = df_w[col].to_numpy(dtype=float)
        series[m] = [SeriesPoint(dd, None, "NULL") if (not p or np.isnan(v)) else
                     SeriesPoint(dd, float(v), "TESTED" if s == "TESTED" else "ALLOCATED")
                     for dd, v, p, s in zip(dates, vals, prod, src)]
        units[m], axes[m] = u, ax
    fit_pts = None
    if overlay_decline_fit:
        fit = fit_decline_curve(well_id, as_of=as_of).value
        if fit is not None:
            t = np.array([(dd - fit.fit_origin_date).days for dd in dates], dtype=float)
            q = arps_hyperbolic(np.maximum(t, 0.0), fit.qi_bopd, fit.b, fit.di_per_day)
            fit_pts = [SeriesPoint(dd, round(float(v), 1), "ALLOCATED") for dd, v, tt in zip(dates, q, t) if tt >= 0]
    markers = []
    if overlay_interventions:
        wo = well_rows("workover_history", well_id)
        wo = wo[(~wo["is_censored"].astype(bool)) & (wo["start_date"] >= start) & (wo["start_date"] <= as_of)]
        for r in wo.sort_values("start_date").itertuples(index=False):
            out = str(r.outcome) if r.outcome in ("SUCCESS", "PARTIAL", "FAILED") else "UNKNOWN"
            code = r.catalogue_job_code if isinstance(r.catalogue_job_code, str) else str(r.job_code)
            markers.append(InterventionMarker(r.start_date, code, f"{code} ({out})", out))
    ps = ProductionSeries(well_id, series, units, axes, fit_pts, markers, int(prod.sum()), int((~prod).sum()))
    return ToolResult(ToolStatus.OK, ps, [],
                      f"Plotted {len(series)} series for {well_id} ({ps.n_producing_days} producing days, "
                      f"{ps.n_null_days} shut-in gap days).", build_provenance("TC-017", params, t0))


# ---------------------------------------------------------------------------
# TC-018 · query_wells()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RankedWell:
    rank: int
    well_id: WellId
    oil_rate_bopd: float | None
    expected_bopd: float | None
    gap_bopd: float | None
    residual_pct: float | None
    water_cut_pct: float | None
    status: str
    fit_quality: Confidence | None
    days_to_failure: float | None = None


@dataclass(frozen=True)
class WellRanking:
    order_by: str
    direction: str
    rows: list[RankedWell]
    n_eligible: int
    n_excluded: int
    excluded_reasons: dict[str, int]
    caveat: str | None


def query_wells(field: str, as_of: date | None = None,
                order_by: Literal["oil_rate_bopd", "decline_residual_pct", "deferred_bopd", "days_to_failure",
                                  "water_cut_pct"] = "decline_residual_pct",
                direction: Literal["ASC", "DESC"] = "ASC", limit: int = 10, filters: dict | None = None) -> ToolResult:
    t0 = time.perf_counter()
    as_of = _as_of(as_of)
    params = {"field": field, "as_of": str(as_of), "order_by": order_by, "direction": direction, "limit": limit,
              "filters": filters}
    f = resolve_field(field or "")
    if f is None:
        return unavailable("TC-018", params, t0, [f"field:{field}"], f"Unknown field '{field}'.")
    dp = load_table("daily_production", f)
    day = dp[dp["production_date"] == as_of]
    wm = load_table("well_master").set_index("well_id")
    filters = filters or {}
    if filters.get("cluster_id"):
        day = day[day["cluster_id"] == filters["cluster_id"]]
    if filters.get("lift_type"):
        day = day[day["well_id"].map(wm["lift_type"]) == filters["lift_type"]]
    prod = day[day["is_producing"] == True]  # noqa: E712
    reasons = {"SHUT_IN_AT_AS_OF": int((day["is_producing"] == False).sum())}  # noqa: E712
    records = []
    for r in prod.itertuples(index=False):
        fit = fit_decline_curve(r.well_id, as_of=as_of)
        if fit.value is None:
            reasons["NO_DECLINE_FIT"] = reasons.get("NO_DECLINE_FIT", 0) + 1
            if order_by in ("decline_residual_pct", "deferred_bopd"):
                continue
        v = fit.value
        dtf = None
        if order_by == "days_to_failure":
            pf = predict_failure(r.well_id, as_of=as_of).value
            dtf = pf.ettf_days if pf else None
            if dtf is None:
                reasons["NO_FAILURE_PREDICTION"] = reasons.get("NO_FAILURE_PREDICTION", 0) + 1
                continue
        oil = round(float(r.oil_rate_bopd), 1)
        records.append(RankedWell(0, r.well_id, oil, v.expected_bopd if v else None,
                                  round(oil - v.expected_bopd, 1) if v else None, v.residual_pct if v else None,
                                  round(float(r.water_cut_pct), 1), "PRODUCING", v.fit_quality if v else None, dtf))
    rev = direction == "DESC"
    key = {"oil_rate_bopd": lambda x: x.oil_rate_bopd, "water_cut_pct": lambda x: x.water_cut_pct,
           "deferred_bopd": lambda x: x.gap_bopd, "days_to_failure": lambda x: x.days_to_failure}.get(
        order_by, lambda x: x.residual_pct)
    records.sort(key=lambda x: (key(x) if key(x) is not None else 0.0, x.well_id), reverse=rev)
    caveat = None
    if order_by == "oil_rate_bopd":  # TC-018.2
        caveat = ("Absolute rate ranking is misleading on mature wells: a low-rate well may be exactly on its own "
                  "expected decline, while a higher-rate well 30-40% below its own curve is losing far more "
                  "recoverable barrels.")
    rows = [replace(rec, rank=i + 1) for i, rec in enumerate(records[:limit])]
    wr = WellRanking(order_by, direction, rows, len(records), sum(reasons.values()), reasons, caveat)
    return ToolResult(ToolStatus.OK, wr, [], f"Returned top {len(rows)} {f} wells ordered by {order_by} ({direction}).",
                      build_provenance("TC-018", params, t0))


for _c in (_offsets_cached, _mech_cached, _predict_cached, _trigger_b, _field_hazards, _scan_field, _rank_field,
           _coxph):
    register_cache(_c.cache_clear)

__all__ = [n for n in dir() if not n.startswith("_")]
_ = FIELD_CONFIGS
