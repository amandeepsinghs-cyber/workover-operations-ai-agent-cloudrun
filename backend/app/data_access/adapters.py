"""Table rows → v0.3-compatible REST shapes (SDD §5.8), plus the interim health rule (W-2).

* Units: pressures kg/cm² × 14.2233 → psi; choke 64ths → % open (/64 × 100).
* Null-not-zero (DC-014): non-producing days return ``null`` rates; never 0.
* Currency never leaves the data layer (D-1): workovers carry ``cost_band`` + ``rig_days``.
* Health: since Stage P the bucket comes from **TC-020** (``app.analytics.tools.health``, SDD §6.3);
  the Stage N **INTERIM_N1** rule below is kept only as a fallback for a well TC-020 cannot classify:

    NOT_PRODUCING   open status at AS_OF ≠ PRODUCING, or no production on AS_OF        → "failed"
    UNDERPERFORMING 7-day mean oil ≤ 0.80 × mean of [AS_OF−90, AS_OF−31]               → "warning"
    AT_RISK         ≤ 0.92 ×, or 30-day runtime < 0.90, or WC up ≥ 5 pp              → "warning"
                    (isolated down days, e.g. a one-day GGS power outage, count only
                    through the runtime term: a single cluster trip must not flag a field)
    PRODUCING_OK    otherwise                                                         → "healthy"
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app import settings
from app.analytics.generator.catalogue import IC_LABELS
from app.analytics.generator.fields.base import FieldConfig

PSI = 14.2233
HEALTH_RULE = "INTERIM_N1"
LIFT_LABEL = {"SRP": "Sucker Rod Pump (SRP)", "GAS_LIFT": "Continuous Gas Lift", "NATURAL": "Natural Flow"}
REST_STATUS = {"NOT_PRODUCING": "failed", "UNDERPERFORMING": "warning", "AT_RISK": "warning", "PRODUCING_OK": "healthy"}
OUTCOME = {"SUCCESS": "Success", "PARTIAL": "Partial", "FAILED": "Failed", "NO_ACTION": "No action",
           "IN_PROGRESS": "In progress"}
BASIN = "Assam-Arakan Basin"
HISTORY_DAYS = {"30d": 30, "6m": 180, "1y": 365, "2y": 730, "3y": 1095, "5y": None}


def _f(x, nd: int = 1):
    """float rounded, or None for NaN/None."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(v) else round(v, nd)


def _iso(d) -> str | None:
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return None
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def well_name(row: dict) -> str:
    n = int(str(row["well_id"]).split("-")[-1])
    return f"{row['field']} #{n} ({row['current_zone']})"


# ------------------------------------------------------------------------------------------------
# health (interim)
# ------------------------------------------------------------------------------------------------
def interim_health(daily: pd.DataFrame, status: pd.DataFrame | None) -> tuple[str, str]:
    as_of = settings.AS_OF
    d = daily[daily["production_date"] <= as_of]
    today = d[d["production_date"] == as_of]
    open_status = None
    if status is not None and len(status):
        cur = status[(status["start_date"] <= as_of) & (status["end_date"].isna() | (status["end_date"] >= as_of))]
        if len(cur):
            r = cur.iloc[-1]
            open_status = (r["status"], r["reason_code"])
    if open_status and open_status[0] != "PRODUCING":
        return "NOT_PRODUCING", f"{open_status[0]} ({open_status[1] or 'no reason'}) on {as_of}"
    if not len(today) or not bool(today["is_producing"].iloc[0]):
        return "NOT_PRODUCING", f"no production on {as_of}"
    prod = d[d["is_producing"]]
    last7 = prod[prod["production_date"] > as_of - timedelta(days=7)]
    base = prod[(prod["production_date"] >= as_of - timedelta(days=90)) & (prod["production_date"] <= as_of - timedelta(days=31))]
    last30 = d[d["production_date"] > as_of - timedelta(days=30)]
    if not len(base) or not len(last7):
        return "AT_RISK", "insufficient producing history for a baseline"
    ratio = float(last7["oil_rate_bopd"].mean() / base["oil_rate_bopd"].mean())
    wc_up = float(last7["water_cut_pct"].mean() - base["water_cut_pct"].mean())
    runtime = float(last30["runtime_fraction"].fillna(0.0).mean())
    down30 = int((~last30["is_producing"]).sum())
    if ratio <= 0.80:
        return "UNDERPERFORMING", f"7-day oil at {ratio:.0%} of the 90–31-day baseline"
    reasons = []
    if ratio <= 0.92:
        reasons.append(f"7-day oil at {ratio:.0%} of baseline")
    if runtime < 0.90:
        reasons.append(f"30-day runtime {runtime:.0%}")
    if wc_up >= 5.0:
        reasons.append(f"water cut up {wc_up:.1f} pp")
    if reasons:
        return "AT_RISK", "; ".join(reasons)
    tail = f"; {down30} down day(s) in the last 30" if down30 else ""
    return "PRODUCING_OK", f"7-day oil at {ratio:.0%} of baseline; runtime {runtime:.0%}{tail}"


# ------------------------------------------------------------------------------------------------
# workovers / metrics / summary
# ------------------------------------------------------------------------------------------------
def workover_records(wo: pd.DataFrame | None, cat: pd.DataFrame) -> list[dict]:
    if wo is None or not len(wo):
        return []
    wo = wo[~wo["is_censored"].astype(bool)].sort_values(["start_date", "workover_id"])
    out = []
    for r in wo.itertuples(index=False):
        code = r.catalogue_job_code
        c = cat.loc[code] if code in cat.index else None
        requires_rig = bool(c["requires_rig"]) if c is not None else not bool(r.is_rigless)
        equipment = str(c["equipment"]) if c is not None else ("WORKOVER_RIG" if requires_rig else "SURFACE_CREW")
        crew = r.rig_id if isinstance(r.rig_id, str) and r.rig_id else equipment
        ic = r.intervention_class
        out.append({
            "id": r.workover_id,
            "date": _iso(r.start_date),
            "type": str(c["job_name"]) if c is not None else str(r.job_code),
            "contractor": crew,
            "description": (f"Failure mode {r.failure_code}; catalogue job {code} "
                            f"({IC_LABELS.get(ic, 'unclassified')}); {'rig' if requires_rig else 'rigless'} job."),
            "outcome": OUTCOME.get(r.outcome, str(r.outcome).title()),
            "flow_delta_bopd": _f(r.uplift_bopd) or 0.0,
            "cost_band": str(c["cost_band"]) if c is not None else "MED",
            "rig_days": float(r.rig_days or 0.0),
            "requires_rig": requires_rig,
            "equipment": equipment,
            "intervention_class": ic,
            "intervention_label": IC_LABELS.get(ic, ""),
            "catalogue_job_code": code,
            "end_date": _iso(r.end_date),
            "report_doc_id": r.report_doc_id if isinstance(r.report_doc_id, str) else None,
        })
    return out


def current_metrics(daily: pd.DataFrame) -> tuple[dict, str | None]:
    """Metrics as of ``AS_OF``.

    A well that is not producing on AS_OF reports a *current* oil/gas rate of 0.0 (its present
    state, so fleet totals are right); water cut and pressures are those of the last producing day
    (reported in ``current_metrics_date``). History keeps null-not-zero (DC-014).
    """
    d = daily[daily["production_date"] <= settings.AS_OF]
    prod = d[d["is_producing"]]
    last30 = d[d["production_date"] > settings.AS_OF - timedelta(days=30)]
    uptime = round(float(last30["runtime_fraction"].fillna(0.0).mean() * 100.0), 1) if len(last30) else 0.0
    if not len(prod):
        return ({"oil_bopd": 0.0, "gas_mcfd": 0.0, "water_cut_pct": 0.0, "tubing_pressure_psi": 0.0,
                 "casing_pressure_psi": 0.0, "choke_pct": 0.0, "uptime_pct": uptime}, None)
    r = prod.iloc[-1]
    on_today = r["production_date"] == settings.AS_OF
    return ({
        "oil_bopd": (_f(r["oil_rate_bopd"]) or 0.0) if on_today else 0.0,
        "gas_mcfd": (_f(r["gas_rate_mscfd"]) or 0.0) if on_today else 0.0,
        "water_cut_pct": _f(r["water_cut_pct"]) or 0.0,
        "tubing_pressure_psi": _f(r["thp_kgcm2"] * PSI) or 0.0,
        "casing_pressure_psi": _f(r["chp_kgcm2"] * PSI) or 0.0,
        "choke_pct": (_f(r["choke_size_64th"] / 64.0 * 100.0) or 0.0) if on_today else 0.0,
        "uptime_pct": uptime,
    }, _iso(r["production_date"]))


def telemetry_summary(daily: pd.DataFrame, workovers: list[dict]) -> dict:
    d = daily[(daily["production_date"] <= settings.AS_OF)
              & (daily["production_date"] > settings.AS_OF - timedelta(days=730))]
    oil = d.loc[d["is_producing"], "oil_rate_bopd"]
    mix = {"LOW": 0, "MED": 0, "HIGH": 0}
    for w in workovers:
        mix[w["cost_band"]] = mix.get(w["cost_band"], 0) + 1
    return {
        "peak_oil_bopd": _f(oil.max()) if len(oil) else 0.0,
        "min_oil_bopd": _f(oil.min()) if len(oil) else 0.0,
        "avg_oil_bopd": _f(oil.mean()) if len(oil) else 0.0,
        "total_workovers": len(workovers),
        "cost_band_mix": mix,
        "total_rig_days": round(sum(w["rig_days"] for w in workovers), 1),
    }


def tc020_health(well_id: str, daily: pd.DataFrame, status: pd.DataFrame | None) -> tuple[str, str, str]:
    """(bucket, reason, rule) from TC-020 (Stage P); INTERIM_N1 only if TC-020 cannot classify the well."""
    from app.analytics.tools.health import HEALTH_RULE as TC020_RULE
    from app.analytics.tools.health import well_health

    h = well_health(well_id)
    if h is not None:
        return h.bucket, h.reason, TC020_RULE
    bucket, reason = interim_health(daily, status)
    return bucket, reason, HEALTH_RULE


def well_summary(row: dict, daily: pd.DataFrame, t: dict, cat: pd.DataFrame) -> dict:
    wos = workover_records(t.get("workover_history"), cat)
    bucket, reason, rule = tc020_health(row["well_id"], daily, t.get("well_status_history"))
    metrics, mdate = current_metrics(daily)
    return {
        "id": row["well_id"],
        "name": well_name(row),
        "coordinates": {"lat": float(row["latitude"]), "lng": float(row["longitude"])},
        "basin": BASIN,
        "formation": row["current_zone"],
        "lift_type": LIFT_LABEL.get(row["lift_type"], row["lift_type"]),
        "status": REST_STATUS[bucket],
        "current_metrics": metrics,
        "telemetry_summary": telemetry_summary(daily, wos),
        "recent_workovers_count": len(wos),
        "workovers": wos,
        "field": row["field"],
        "cluster_id": row.get("cluster_id"),
        "health_bucket": bucket,
        "health_reason": reason,
        "status_reason": reason,
        "health_rule": rule,
        "as_of": settings.AS_OF.isoformat(),
        "current_metrics_date": mdate,
        "spud_date": _iso(row.get("spud_date")),
    }


# ------------------------------------------------------------------------------------------------
# history
# ------------------------------------------------------------------------------------------------
def history_points(daily: pd.DataFrame, range_: str) -> list[dict]:
    days = HISTORY_DAYS.get(range_, 730)
    d = daily[daily["production_date"] <= settings.AS_OF]
    if days is not None:
        d = d[d["production_date"] > settings.AS_OF - timedelta(days=days)]
    out = []
    for r in d.itertuples(index=False):
        p = bool(r.is_producing)
        out.append({
            "date": r.production_date.isoformat(),
            "oil_bopd": _f(r.oil_rate_bopd) if p else None,
            "gas_mcfd": _f(r.gas_rate_mscfd) if p else None,
            "water_cut_pct": _f(r.water_cut_pct) if p else None,
            "tubing_pressure_psi": _f(r.thp_kgcm2 * PSI) if p else None,
            "casing_pressure_psi": _f(r.chp_kgcm2 * PSI) if p else None,
            "water_bwpd": _f(r.water_rate_bwpd) if p else None,
            "liquid_blpd": _f(r.liquid_rate_blpd) if p else None,
            "gor_scf_bbl": _f(r.gor_scf_bbl) if p else None,
            "wht_degc": _f(r.wht_degc) if p else None,
            "gl_inj_rate_mscfd": _f(r.gl_inj_rate_mscfd) if p else None,
            "gl_inj_pressure_psi": _f(r.gl_inj_pressure_kgcm2 * PSI) if (p and r.gl_inj_pressure_kgcm2 == r.gl_inj_pressure_kgcm2) else None,
            "runtime_fraction": _f(r.runtime_fraction, 3),
            "is_producing": p,
            "downtime_reason": r.downtime_reason if isinstance(r.downtime_reason, str) else None,
        })
    return out


# ------------------------------------------------------------------------------------------------
# reports (interim: rendered from tables + FieldConfig.fluid_props, same keys as v0.3)
# ------------------------------------------------------------------------------------------------
def _completion_report(row: dict, t: dict, cfg: FieldConfig) -> dict:
    wid = row["well_id"]
    cas = t.get("casing_tally")
    tub = t.get("tubing_string")
    perf = t.get("perforation_intervals")
    tests = t.get("well_tests")
    casing = [] if cas is None else [
        {"string": f'{r.od_in:g}" {r.string_type.title()} Casing ({r.grade}, {r.weight_ppf:g} ppf)',
         "depth_m": _f(r.shoe_m), "cement_class": f"Cemented; top of cement {r.cement_top_m:.0f} m MD"}
        for r in cas.itertuples(index=False)]
    if tub is not None and len(tub):
        comps = ", ".join(f"{r.component} @ {r.top_m:.0f} m" for r in tub.itertuples(index=False) if r.component != "TUBING")
        tubing = f'{tub["od_in"].iloc[0]:g}" OD tubing; {comps or "plain string"}'
    else:
        tubing = "not recorded"
    open_p = perf[perf["status"] == "OPEN"] if perf is not None else None
    perfs = "; ".join(f"{r.top_m:.1f}m - {r.bottom_m:.1f}m ({r.zone}) at {r.spf} SPF" for r in open_p.itertuples(index=False)) \
        if open_p is not None and len(open_p) else "not recorded"
    ipt = {"choke_mm": 0.0, "oil_rate_bopd": 0.0, "gas_rate_mcfd": 0.0, "water_cut_pct": 0.0,
           "flowing_tubing_pressure_psi": 0.0}
    if tests is not None and len(tests):
        r = tests.sort_values("test_date").iloc[0]
        liq = (r["oil_rate_bopd"] or 0) + (r["water_rate_bwpd"] or 0)
        ipt = {"choke_mm": round(16 / 64 * 25.4, 1), "oil_rate_bopd": _f(r["oil_rate_bopd"]),
               "gas_rate_mcfd": _f(r["gas_rate_mscfd"]),
               "water_cut_pct": _f(100.0 * (r["water_rate_bwpd"] or 0) / liq) if liq else 0.0,
               "flowing_tubing_pressure_psi": _f(r["thp_kgcm2"] * PSI), "first_test_in_record": _iso(r["test_date"])}
    crude = cfg.fluid_props.get("crude", {})
    return {
        "report_id": f"{cfg.prefix.rstrip('-')}/WCR/{wid}",
        "title": "Well Completion & Initial Production Testing Report",
        "issuing_authority": f"{cfg.asset} Asset — {cfg.field} field records (synthetic, interim render)",
        "spud_date": _iso(row.get("spud_date")),
        "completion_date": _iso(row.get("completion_date")),
        "total_depth_m": _f(row["total_depth_md_m"]),
        "target_formation": row["current_zone"],
        "casing_policy": casing,
        "tubing_specification": tubing,
        "perforated_intervals": perfs,
        "initial_production_test": ipt,
        "crude_assay": {
            "api_gravity": crude.get("api_gravity", 0.0),
            "pour_point_celsius": crude.get("pour_point_celsius", 0.0),
            "wax_content_pct": crude.get("wax_content_pct", 0.0),
            "sulfur_wt_pct": crude.get("sulfur_wt_pct", 0.0),
            "viscosity_cp": f"{crude.get('viscosity_cp_50c', 0.0)} cP @ 50°C",
        },
    }


def _workover_report(row: dict, wos: list[dict], cfg: FieldConfig) -> dict:
    done = [w for w in wos if w["outcome"] != "In progress"]
    wid = row["well_id"]
    if not done:
        return {"report_id": f"DWR/{wid}/NONE", "title": "Daily Workover Shift Report & Mechanical Execution Log",
                "issuing_authority": "Well Services (synthetic, interim render)", "date": settings.AS_OF.isoformat(),
                "supervising_engineer": "Well Services — shift supervisor", "workover_rig": "none",
                "operation_type": "No workover on record", "contractor": "none", "cost_band": "LOW", "rig_days": 0.0,
                "shift_hours": "n/a", "hourly_logs": [], "outcome_summary": "No workover on record for this well."}
    w = done[-1]
    rig = w["requires_rig"]
    logs = [
        {"time": "06:00 - 07:30", "activity": "Toolbox talk; permit to work verified; well killed and secured."},
        {"time": "07:30 - 10:00", "activity": ("Rigged up workover rig; pulled completion string." if rig
                                               else f"Rigged up {w['equipment'].replace('_', ' ').lower()}.")},
        {"time": "10:00 - 15:00", "activity": f"Executed {w['type']} ({w['catalogue_job_code']})."},
        {"time": "15:00 - 17:00", "activity": "Pressure-tested and returned the well to production."},
        {"time": "17:00 - 18:00", "activity": "Handed the well over to the production shift."},
    ]
    return {
        "report_id": f"DWR/{wid}/{w['date'].replace('-', '')}",
        "title": "Daily Workover Shift Report & Mechanical Execution Log",
        "issuing_authority": "Well Services (synthetic, interim render)",
        "date": w["date"],
        "supervising_engineer": "Well Services — shift supervisor",
        "workover_rig": w["contractor"],
        "operation_type": w["type"],
        "contractor": w["contractor"],
        "cost_band": w["cost_band"],
        "rig_days": w["rig_days"],
        "shift_hours": "06:00 to 18:00 hrs (12-hour shift)",
        "hourly_logs": logs,
        "outcome_summary": f"{w['outcome']} — production change {w['flow_delta_bopd']:+.1f} BOPD after the job.",
        "workover_id": w["id"],
        "report_doc_id": w["report_doc_id"],
    }


def _bhp_report(row: dict, t: dict, daily: pd.DataFrame, metrics: dict) -> dict:
    wid = row["well_id"]
    ps = t.get("pressure_surveys")
    ps = ps[ps["survey_date"] <= settings.AS_OF] if ps is not None else None
    tub = t.get("tubing_string")
    gl = row["lift_type"] == "GAS_LIFT"
    prod = daily[daily["is_producing"] & (daily["production_date"] <= settings.AS_OF)]
    last = prod.iloc[-1] if len(prod) else None
    glm = tub[tub["component"] == "GLM"]["top_m"].max() if (tub is not None and gl) else None
    gls = {
        "injection_pressure_casing_psi": _f(last["gl_inj_pressure_kgcm2"] * PSI) if (gl and last is not None) else metrics["casing_pressure_psi"],
        "injection_rate_mcfd": _f(last["gl_inj_rate_mscfd"]) if (gl and last is not None) else 0.0,
        "operating_valve_depth_m": _f(glm) if glm is not None and glm == glm else 0.0,
        "status": "Gas lift — injecting" if gl else f"Not gas lifted ({LIFT_LABEL.get(row['lift_type'])})",
    }
    if ps is None or not len(ps):
        return {"report_id": f"BHP/{wid}/NONE", "title": "Subsurface Reservoir Pressure & Fluid Level Acoustic Survey",
                "issuing_authority": "Reservoir Management (synthetic, interim render)", "survey_date": None,
                "gas_lift_status": gls}
    r = ps.sort_values("survey_date").iloc[-1]
    sbhp, fbhp = r["sbhp_kgcm2"] * PSI, r["fbhp_kgcm2"] * PSI
    pi = r["pi_bpd_per_kgcm2"]
    return {
        "report_id": f"BHP/{wid}/{r['survey_id']}",
        "title": "Subsurface Reservoir Pressure & Fluid Level Acoustic Survey",
        "issuing_authority": "Reservoir Management (synthetic, interim render)",
        "survey_date": _iso(r["survey_date"]),
        "datum_depth_m_tvd": _f(r["datum_tvd_m"]),
        "static_bottomhole_pressure_sbhp_psi": _f(sbhp),
        "flowing_bottomhole_pressure_fbhp_psi": _f(fbhp),
        "drawdown_psi": _f(sbhp - fbhp),
        "productivity_index_pi": _f(pi / PSI, 3) if pi == pi and pi is not None else 0.0,
        "sonolog_fluid_level_m": _f(r["fluid_level_m"]),
        "fluid_gradient_psi_ft": 0.385,
        "gas_lift_status": gls,
        "survey_id": r["survey_id"],
    }


def _lab_report(row: dict, cfg: FieldConfig, metrics: dict) -> dict:
    w = cfg.fluid_props.get("water", {})
    ions = w.get("ions_mg_l", {})
    return {
        "report_id": f"LAB/{row['well_id']}/{cfg.field.upper()}-WATER",
        "title": "Produced Water Chemistry & Scale Deposition Potential Assay",
        "issuing_authority": f"{cfg.field} field water chemistry reference (synthetic, interim render)",
        "sample_date": (settings.AS_OF - timedelta(days=45)).isoformat(),
        "water_cut_tested_pct": metrics["water_cut_pct"],
        "total_dissolved_solids_tds_mg_l": w.get("tds_mg_l", 0),
        "ph_at_25c": w.get("ph_at_25c", 0.0),
        "specific_gravity": w.get("specific_gravity", 0.0),
        "ionic_constituents_mg_l": {k: ions.get(k, 0) for k in (
            "chloride_cl", "sodium_na", "calcium_ca", "magnesium_mg", "barium_ba", "strontium_sr", "sulfate_so4",
            "bicarbonate_hco3")},
        "scaling_tendency_analysis": {
            "calcium_carbonate_caco3": "Moderate precipitation risk at surface choke and heater-treater.",
            "barium_sulfate_baso4": "Low risk at current sulfate levels.",
            "iron_sulfide_fes": "Trace; monitor for sulfate-reducing bacteria.",
        },
        "chemist_recommendation": "Continue scale-inhibitor dosing at the wellhead skid; re-sample after the next workover.",
    }


def well_detail(summary: dict, row: dict, daily: pd.DataFrame, t: dict, cat: pd.DataFrame, cfg: FieldConfig) -> dict:
    out = dict(summary)
    m = summary["current_metrics"]
    out["reports"] = {
        "completion_report": _completion_report(row, t, cfg),
        "daily_workover_report": _workover_report(row, summary["workovers"], cfg),
        "bottomhole_pressure_survey": _bhp_report(row, t, daily, m),
        "water_and_scale_lab_report": _lab_report(row, cfg, m),
    }
    return out


# ------------------------------------------------------------------------------------------------
# field infrastructure
# ------------------------------------------------------------------------------------------------
def field_infrastructure(cfg: FieldConfig, fac: pd.DataFrame, wells: pd.DataFrame, fm) -> dict:
    stations = []
    for r in fac.itertuples(index=False):
        cl = set(str(r.serviced_cluster_ids).split(","))
        st = {"id": r.facility_id, "name": r.name, "coordinates": {"lat": float(r.lat), "lng": float(r.lon)},
              "capacity_bopd": int(r.capacity_bopd), "type": r.type, "serviced_cluster_ids": sorted(cl)}
        if r.compressor_capacity_mmscfd == r.compressor_capacity_mmscfd and r.compressor_capacity_mmscfd is not None:
            st["compressor_capacity_mmscfd"] = float(r.compressor_capacity_mmscfd)
        if r.water_handling_bwpd == r.water_handling_bwpd and r.water_handling_bwpd is not None:
            st["water_handling_bwpd"] = int(r.water_handling_bwpd)
        if r.type == "GGS":
            st["serviced_wells"] = sorted(wells[wells["cluster_id"].isin(cl)]["well_id"].tolist())
        stations.append(st)
    return {
        "field_name": f"{cfg.field} Oil Field ({cfg.asset} Asset)",
        "field": cfg.field,
        "center_coordinates": {"lat": float(fm["centroid_lat"]), "lng": float(fm["centroid_lon"])},
        "gathering_stations": stations,
        "boundary_geojson": fm["boundary_geojson"],
    }


def as_of_timestamp() -> str:
    return f"{settings.AS_OF.isoformat()}T16:00:00Z"


def is_date(x) -> bool:
    return isinstance(x, date)
