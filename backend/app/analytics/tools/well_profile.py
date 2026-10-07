"""TC-029 well_profile and TC-017 v2 well production series (SDD §6.2, F-12, Stage T).

Verbatim T2 *"drill down to one particular well … 2-3 year history or 5 year history … what are the different
interventions happened"*, *"also give information of nearby wells"*; T4 *"reservoir formation … casing/tubing
sizes"*; WS-4 *"casing/tubing tallies, and lithology"*; WS-6 *"temperature … GOR … artificial lift metrics"*.

* ``well_profile`` — identity, construction (casing tally, current tubing string, perforations), lithology
  (``formation_tops``), lift, TC-020 bucket + open status episode, current rates, TC-001 decline residual, last
  well test, last pressure survey, intervention summary and the ``k`` nearest wells **in the same cluster**
  (great-circle distance on ``well_master`` coordinates) with their bucket, status, rate and decline residual.
* ``well_production_series`` (TC-017 v2) — daily series aligned to one ``dates`` array (incl. ``wht_degc``,
  ``gor_scf_bbl``, gas-lift injection rate / pressure), the Arps fit overlay, **every** job that started inside
  the window as a marker (censored / in-progress / no-action jobs included, with their outcome), and older jobs as
  ``historical_interventions`` (BDD-F12-S03). Gas-lift series are reported only for gas-lift wells.

Shape note: ``series`` is ``{metric: [value|null …]}`` aligned to ``dates`` (one shared date axis) rather than
``{metric: [{date, value}]}`` — same information, ~half the payload, and directly zippable into chart rows.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app import settings

from .common import (
    ToolResult, ToolStatus, build_provenance, load_table, unavailable, well_master_row, well_rows,
)

DOC_URL = "/api/docs/{doc_id}.pdf"
EARTH_R_M = 6_371_000.0

# metric -> (daily_production column, unit)
METRICS: dict[str, tuple[str, str]] = {
    "oil": ("oil_rate_bopd", "BOPD"),
    "water": ("water_rate_bwpd", "BWPD"),
    "gas": ("gas_rate_mscfd", "MSCFD"),
    "liquid": ("liquid_rate_blpd", "BLPD"),
    "water_cut": ("water_cut_pct", "%"),
    "gor": ("gor_scf_bbl", "scf/bbl"),
    "wht": ("wht_degc", "degC"),
    "gl_inj_rate": ("gl_inj_rate_mscfd", "MSCFD"),
    "gl_inj_pressure": ("gl_inj_pressure_kgcm2", "kg/cm2"),
    "thp": ("thp_kgcm2", "kg/cm2"),
    "chp": ("chp_kgcm2", "kg/cm2"),
}
DEFAULT_METRICS = ("oil", "water_cut", "gas", "gor", "wht", "gl_inj_rate", "gl_inj_pressure", "thp", "chp")
GL_METRICS = ("gl_inj_rate", "gl_inj_pressure")
# Status-like / rate-like fields: a value only counts on a producing day (NULL otherwise; DC-014)
_RATE_METRICS = frozenset({"oil", "water", "gas", "liquid", "water_cut", "gor"})


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.date()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _row_dict(r: pd.Series | dict, drop: tuple[str, ...] = ("field", "cluster_id", "well_id", "is_prepend")) -> dict:
    items = r.items() if isinstance(r, dict) else r.to_dict().items()
    return {k: _clean(v) for k, v in items if not str(k).startswith("_") and k not in drop}


def _r(x, nd: int = 1):
    x = _clean(x)
    return None if x is None else round(float(x), nd)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def _open_episode(well_id: str, as_of: date) -> dict | None:
    s = well_rows("well_status_history", well_id)
    if s.empty:
        return None
    cur = s[(s["start_date"] <= as_of) & (s["end_date"].isna() | (s["end_date"] >= as_of))]
    if cur.empty:
        return None
    r = cur.sort_values("start_date").iloc[-1]
    return {"status": r["status"], "since": r["start_date"],
            "reason_code": r["reason_code"] if isinstance(r["reason_code"], str) else None}


def _current_rates(well_id: str, as_of: date, n_days: int = 7) -> dict:
    d = well_rows("daily_production", well_id)
    d = d[(d["production_date"] <= as_of) & (d["is_producing"] == True) & d["oil_rate_bopd"].notna()]  # noqa: E712
    if d.empty:
        return {"oil_bopd": None, "water_cut_pct": None, "gas_mscfd": None, "last_producing_date": None,
                "basis": f"mean of last {n_days} producing days <= as_of"}
    last = d.sort_values("production_date").tail(n_days)
    oil, water = float(last["oil_rate_bopd"].sum()), float(last["water_rate_bwpd"].fillna(0).sum())
    return {"oil_bopd": _r(last["oil_rate_bopd"].mean(), 1),
            "water_cut_pct": _r(water / (oil + water) * 100.0, 1) if (oil + water) > 0 else None,
            "gas_mscfd": _r(last["gas_rate_mscfd"].mean(), 1),
            "last_producing_date": last["production_date"].iloc[-1],
            "basis": f"mean of last {n_days} producing days <= as_of"}


def _decline(well_id: str, as_of: date) -> dict:
    from .arps_decline import fit_decline_curve

    r = fit_decline_curve(well_id, as_of=as_of)
    v = r.value
    if v is None:
        return {"residual_pct": None, "expected_bopd": None, "fit_quality": None, "status": r.status.value}
    fq = getattr(v, "fit_quality", None)
    return {"residual_pct": _r(getattr(v, "residual_pct", None), 1), "expected_bopd": _r(getattr(v, "expected_bopd", None), 1),
            "fit_quality": getattr(fq, "value", fq), "status": r.status.value}


def _bucket(well_id: str, as_of: date) -> tuple[str | None, str | None]:
    from .health import well_health

    h = well_health(well_id, as_of=as_of)
    return (h.bucket, h.reason) if h is not None else (None, None)


def _job_names() -> dict[str, str]:
    jc = load_table("job_catalogue")
    return dict(zip(jc["job_code"], jc["job_name"])) if len(jc) and "job_name" in jc.columns else {}


def _workovers(well_id: str, as_of: date) -> pd.DataFrame:
    """Real workover records up to ``as_of``. ``is_censored`` rows (job_code ``NONE_CENSORED``) are run-life
    censoring records for survival analysis, not jobs, so they are never shown as interventions."""
    wo = well_rows("workover_history", well_id)
    wo = wo[wo["start_date"] <= as_of]
    if "is_censored" in wo.columns:
        wo = wo[~wo["is_censored"].fillna(False).astype(bool)]
    return wo.sort_values("start_date")


def _job_code(r) -> str:
    c = getattr(r, "catalogue_job_code", None)
    return c if isinstance(c, str) and c else str(r.job_code)


def _neighbours(wm: dict, as_of: date, k: int) -> tuple[list[dict], str]:
    allw = load_table("well_master")
    lat, lon = wm.get("latitude"), wm.get("longitude")
    basis = (f"{k} nearest wells in the same cluster ({wm.get('cluster_id')}) by great-circle distance on "
             f"well_master coordinates (synthetic locations, D-3)")
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return [], basis + " — subject well has no coordinates"
    pool = allw[(allw["cluster_id"] == wm.get("cluster_id")) & (allw["well_id"] != wm["well_id"])
                & allw["latitude"].notna() & allw["longitude"].notna()]
    dist = sorted(((haversine_m(lat, lon, float(r.latitude), float(r.longitude)), r.well_id, r)
                   for r in pool.itertuples(index=False)), key=lambda x: (x[0], x[1]))[:k]
    names = _job_names()
    out = []
    for dm, wid, r in dist:
        ep = _open_episode(wid, as_of)
        bucket, _ = _bucket(wid, as_of)
        cur = _current_rates(wid, as_of)
        dec = _decline(wid, as_of)
        wo = _workovers(wid, as_of)
        last = wo.iloc[-1] if len(wo) else None
        out.append({
            "well_id": wid, "distance_m": round(dm, 1), "cluster_id": r.cluster_id,
            "same_zone": bool(r.current_zone == wm.get("current_zone")), "zone": r.current_zone,
            "lift_type": r.lift_type, "bucket": bucket, "status": ep["status"] if ep else None,
            "oil_bopd": cur["oil_bopd"], "water_cut_pct": cur["water_cut_pct"],
            "residual_pct": dec["residual_pct"], "fit_quality": dec["fit_quality"],
            "last_job_code": (_job_code(last) if last is not None else None),
            "last_job_name": names.get(_job_code(last)) if last is not None else None,
            "last_job_date": last["start_date"] if last is not None else None,
        })
    return out, basis


@dataclass(frozen=True)
class WellProfile:
    identity: dict
    construction: dict
    lithology: list[dict]
    lift: dict
    status: dict
    current: dict
    decline: dict
    last_test: dict | None
    last_pressure_survey: dict | None
    interventions_summary: dict
    neighbours: list[dict]
    neighbour_basis: str


def _formation_at(tops: pd.DataFrame, depth: float | None) -> str | None:
    if depth is None or tops.empty or pd.isna(depth):
        return None
    hit = tops[(tops["top_md_m"] <= depth) & (tops["bottom_md_m"] >= depth)]
    return str(hit.iloc[0]["formation"]) if len(hit) else None


def well_profile(well_id: str, k_neighbours: int = 4, as_of: date | None = None) -> ToolResult:
    """TC-029. Profile of one well with construction, lithology, lift, status and ``k`` same-cluster neighbours."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    wid = (well_id or "").strip().upper()
    params = {"well_id": wid, "k_neighbours": k_neighbours, "as_of": str(as_of)}
    wm = well_master_row(wid)
    if wm is None:
        return unavailable("TC-029", params, t0, ["well_id"], f"Well {well_id} not found.")
    k = max(1, min(int(k_neighbours or 4), 12))

    tops = well_rows("formation_tops", wid).sort_values("top_md_m")
    casing = well_rows("casing_tally", wid)
    casing = casing[casing["install_date"].isna() | (casing["install_date"] <= as_of)] if "install_date" in casing else casing
    tub = well_rows("tubing_string", wid)
    tub = tub[tub["install_date"].isna() | (tub["install_date"] <= as_of)]
    tub = tub.sort_values(["seq", "install_date"]).groupby("seq").tail(1).sort_values("seq") if len(tub) else tub
    perfs = well_rows("perforation_intervals", wid).sort_values("top_m")

    perf_top = _clean(wm.get("perf_top_m"))
    identity = {
        "well_id": wid, "field": wm["field"], "cluster_id": wm.get("cluster_id"),
        "lat": _clean(wm.get("latitude")), "lon": _clean(wm.get("longitude")),
        "zone": wm.get("current_zone"), "formation": _formation_at(tops, perf_top) or wm.get("current_zone"),
        "spud_date": _clean(wm.get("spud_date")), "completion_date": _clean(wm.get("completion_date")),
        "total_depth_md_m": _clean(wm.get("total_depth_md_m")), "total_depth_tvd_m": _clean(wm.get("total_depth_tvd_m")),
        "perf_top_m": perf_top, "perf_bottom_m": _clean(wm.get("perf_bottom_m")), "well_status": wm.get("status"),
    }
    construction = {
        "casing": [_row_dict(r) for _, r in casing.sort_values("top_m").iterrows()],
        "tubing": [_row_dict(r) for _, r in tub.iterrows()],
        "perfs": [_row_dict(r) for _, r in perfs.iterrows()],
        "casing_size_in": _clean(wm.get("casing_size_in")), "tubing_size_in": _clean(wm.get("tubing_size_in")),
    }
    lithology = [_row_dict(r) for _, r in tops.iterrows()]
    lift_keys = ("lift_type", "pump_type", "plunger_diameter_in", "stroke_length_in", "pump_setting_depth_m",
                 "rod_string_grade", "casing_vented")
    lift = {kk: _clean(wm.get(kk)) for kk in lift_keys if _clean(wm.get(kk)) is not None}

    bucket, reason = _bucket(wid, as_of)
    ep = _open_episode(wid, as_of)
    status = {"bucket": bucket, "reason": reason, "episode_status": ep["status"] if ep else None,
              "episode_since": ep["since"] if ep else None, "reason_code": ep["reason_code"] if ep else None}

    tests = well_rows("well_tests", wid)
    tests = tests[tests["test_date"] <= as_of].sort_values("test_date")
    surveys = well_rows("pressure_surveys", wid)
    surveys = surveys[surveys["survey_date"] <= as_of].sort_values("survey_date")

    wo = _workovers(wid, as_of)
    last = wo.iloc[-1] if len(wo) else None
    names = _job_names()
    isum = {"total": int(len(wo)),
            "last_job_code": _job_code(last) if last is not None else None,
            "last_job_name": names.get(_job_code(last)) if last is not None else None,
            "last_job_date": last["start_date"] if last is not None else None,
            "last_outcome": str(last["outcome"]) if last is not None else None}

    neigh, basis = _neighbours(wm, as_of, k)
    val = WellProfile(identity=identity, construction=construction, lithology=lithology, lift=lift, status=status,
                      current=_current_rates(wid, as_of), decline=_decline(wid, as_of),
                      last_test=_row_dict(tests.iloc[-1]) if len(tests) else None,
                      last_pressure_survey=_row_dict(surveys.iloc[-1]) if len(surveys) else None,
                      interventions_summary=isum, neighbours=neigh, neighbour_basis=basis)
    missing = [n for n, ok in (("casing_tally", len(casing)), ("tubing_string", len(tub)),
                               ("formation_tops", len(tops))) if not ok]
    msg = (f"{wid} ({wm['field']}/{wm.get('cluster_id')}): {identity['zone']} zone, {lift.get('lift_type')}, "
           f"bucket {bucket}; {len(construction['casing'])} casing strings, {len(lithology)} formation tops, "
           f"{isum['total']} interventions; {len(neigh)} same-cluster neighbours.")
    st = ToolStatus.OK if not missing else ToolStatus.LOW_CONFIDENCE
    return ToolResult(st, val, missing, msg, build_provenance("TC-029", params, t0))


# ------------------------------------------------------------------------------------------------
# TC-017 v2
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ProductionSeriesV2:
    well_id: str
    lift_type: str | None
    gas_lift: bool
    months: int
    window_start: date
    window_end: date
    dates: list[date]
    series: dict[str, list]
    units: dict[str, str]
    decline_fit: list | None
    interventions: list[dict]
    historical_interventions: list[dict]
    n_producing_days: int
    n_null_days: int


def well_production_series(well_id: str, months: int = 36, metrics: list[str] | str | None = None,
                           overlay_decline_fit: bool = True, overlay_interventions: bool = True,
                           as_of: date | None = None) -> ToolResult:
    """TC-017 v2. Daily production + WS-6 telemetry with every in-window intervention marker."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    wid = (well_id or "").strip().upper()
    if isinstance(metrics, str):
        metrics = [m.strip() for m in metrics.split(",") if m.strip()]
    metrics = list(metrics or DEFAULT_METRICS)
    params = {"well_id": wid, "months": months, "metrics": metrics, "overlay_decline_fit": overlay_decline_fit,
              "overlay_interventions": overlay_interventions, "as_of": str(as_of)}
    wm = well_master_row(wid)
    if wm is None:
        return unavailable("TC-017", params, t0, ["well_id"], f"Well {well_id} not found.")
    bad = [m for m in metrics if m not in METRICS]
    if bad:
        return unavailable("TC-017", params, t0, ["metrics"], f"Unknown metric(s) {bad}; valid: {list(METRICS)}.")
    months = int(months)
    if months < 1 or months > 60:
        return unavailable("TC-017", params, t0, ["months"], "months must be 1..60.")
    start = max(as_of - timedelta(days=int(round(months * 30.4375))) + timedelta(days=1), settings.DATA_START)
    lift = wm.get("lift_type")
    gas_lift = str(lift).upper() == "GAS_LIFT"

    d = well_rows("daily_production", wid)
    d = d[(d["production_date"] >= start) & (d["production_date"] <= as_of)].sort_values("production_date")
    prod = d["is_producing"].fillna(False).to_numpy(dtype=bool)
    dates = d["production_date"].tolist()
    series, units = {}, {}
    for m in metrics:
        col, unit = METRICS[m]
        if m in GL_METRICS and not gas_lift:
            series[m] = [None] * len(dates)  # not applicable for this lift type (panel hidden in the UI)
            units[m] = unit
            continue
        vals = d[col].to_numpy(dtype=float) if col in d.columns else np.full(len(d), np.nan)
        out = []
        for v, p in zip(vals, prod):
            if np.isnan(v) or (m in _RATE_METRICS and not p):
                out.append(None)
            else:
                out.append(round(float(v), 2))
        series[m], units[m] = out, unit

    fit = None
    if overlay_decline_fit and dates:
        from .arps_decline import arps_hyperbolic, fit_decline_curve

        fv = fit_decline_curve(wid, as_of=as_of).value
        origin = getattr(fv, "fit_origin_date", None) if fv is not None else None
        if fv is not None and origin is not None:
            t = np.array([(dd - origin).days for dd in dates], dtype=float)
            q = arps_hyperbolic(np.maximum(t, 0.0), fv.qi_bopd, fv.b, fv.di_per_day)
            fit = [round(float(v), 1) if tt >= 0 else None for v, tt in zip(q, t)]

    markers, hist = [], []
    if overlay_interventions:
        names = _job_names()
        for r in _workovers(wid, as_of).itertuples(index=False):
            code = _job_code(r)
            doc = r.report_doc_id if isinstance(getattr(r, "report_doc_id", None), str) else None
            outcome = str(r.outcome) if isinstance(r.outcome, str) and r.outcome else "UNKNOWN"
            if r.start_date >= start:
                markers.append({
                    "date": r.start_date, "end_date": _clean(r.end_date), "workover_id": r.workover_id,
                    "job_code": code, "job_name": names.get(code),
                    "intervention_class": r.intervention_class if isinstance(r.intervention_class, str) else None,
                    "outcome": outcome, "rig_days": _r(r.rig_days, 1),
                    "is_rigless": _clean(r.is_rigless), "uplift_bopd": _r(r.uplift_bopd, 1),
                    "doc_id": doc, "doc_url": DOC_URL.format(doc_id=doc) if doc else None,
                })
            else:
                hist.append({"year": r.start_date.year, "date": r.start_date, "job_code": code,
                             "job_name": names.get(code), "outcome": outcome})
    n_prod = int(prod.sum())
    val = ProductionSeriesV2(well_id=wid, lift_type=lift, gas_lift=gas_lift, months=months, window_start=start,
                             window_end=as_of, dates=dates, series=series, units=units, decline_fit=fit,
                             interventions=markers, historical_interventions=hist, n_producing_days=n_prod,
                             n_null_days=int(len(dates) - n_prod))
    status = ToolStatus.OK if n_prod >= 90 else ToolStatus.INSUFFICIENT_HISTORY
    msg = (f"{wid}: {months} months ({start}..{as_of}), {len(series)} series, {n_prod} producing days; "
           f"{len(markers)} interventions in window, {len(hist)} historical.")
    if not gas_lift and any(m in GL_METRICS for m in metrics):
        msg += f" Gas-lift series not applicable (lift type {lift})."
    return ToolResult(status, val, [], msg, build_provenance("TC-017", params, t0, version="v2"))
