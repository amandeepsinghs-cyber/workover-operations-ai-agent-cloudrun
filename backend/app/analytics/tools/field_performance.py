"""TC-024 compare_fields — asset-manager field performance (SDD §6.2, F-09, Stage T).

Verbatim T1 *"Which particular field is not performing? … what is the performance at a field level"*;
WS-1 *"production vs. targets, uptime, water cut, and active intervention counts"*.

Per field over the period window ``[window_start, as_of]``:

* ``actual_bopd`` = Σ daily oil / days (NULL = 0; same basis as Gold ``field_kpi_monthly`` / TC-028);
* ``target_bopd`` = mean daily ``field_targets.target_oil_bopd`` (each day takes its month's target), so
  ``gap_pct = actual / target − 1`` is exactly the Gate N pinned definition (``generator.targets.gap_vs_target``);
* ``expected_bopd`` = mean daily ``field_targets.potential_oil_bopd`` (healthy-state potential, N-D5);
* ``uptime_pct`` = mean ``runtime_fraction`` × 100; ``water_cut_pct`` volume-weighted;
* ``health_counts`` = TC-020; ``deferred_by_factor`` = TC-019 field rollup ``by_class`` (bbl) over the same window;
* ``active_interventions`` = wells whose open ``well_status_history`` episode at ``as_of`` is ``UNDER_WORKOVER``
  (SDD §5.4); ``waiting_on_rig`` / ``waiting_on_material`` likewise;
* ``rig_candidates`` / ``rigless_candidates`` = TC-010 queue lengths.

Ranking = ``gap_pct`` ascending (worst first). ``top_driver`` = the largest TC-019 factor class of the worst
field (whatever it is — it is reported with its ``controllable`` flag, never chosen to look controllable).
A field without a target row is excluded from the ranking with a note (BDD-F09-S05).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field as dc_field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from app import settings

from .common import ToolResult, ToolStatus, build_provenance, load_table, register_cache, unavailable
from .hierarchy import ASSET, FIELDS

PERIODS = ("QTD", "MTD", "YTD", "L12M")


@dataclass(frozen=True)
class FieldComparison:
    asset: str
    period: str
    window_start: date
    window_end: date
    rows: list[dict]
    ranking: list[str]
    worst_field: str | None
    top_driver: dict | None
    excluded: list[dict] = dc_field(default_factory=list)


def period_window(period: str, as_of: date) -> tuple[date, date] | None:
    p = (period or "").upper()
    if p == "QTD":
        return date(as_of.year, 3 * ((as_of.month - 1) // 3) + 1, 1), as_of
    if p == "MTD":
        return date(as_of.year, as_of.month, 1), as_of
    if p == "YTD":
        return date(as_of.year, 1, 1), as_of
    if p == "L12M":
        return as_of - timedelta(days=364), as_of
    return None


def _r(x, nd: int = 1):
    if x is None:
        return None
    v = float(x)
    return None if (np.isnan(v) or np.isinf(v)) else round(v, nd)


def _open_status_counts(fld: str, as_of: date) -> dict[str, int]:
    s = load_table("well_status_history", fld)
    if s.empty:
        return {}
    cur = s[(s["start_date"] <= as_of) & (s["end_date"].isna() | (s["end_date"] >= as_of))]
    cur = cur.sort_values("start_date").groupby("well_id").tail(1)
    return {str(k): int(v) for k, v in cur["status"].value_counts().items()}


def _targets(fld: str, start: date, end: date) -> tuple[float | None, float | None, float | None, list[str]]:
    """Mean daily target / potential / target uptime over [start, end]; missing months listed."""
    t = load_table("field_targets")
    t = t[t["field"] == fld] if len(t) else t
    by_m = {pd.Timestamp(r["month"]).to_period("M"): r for _, r in t.iterrows()}
    days = pd.date_range(start, end)
    tg, pot, up, missing = [], [], [], []
    for d in days:
        r = by_m.get(d.to_period("M"))
        if r is None:
            missing.append(str(d.to_period("M")))
            continue
        tg.append(float(r["target_oil_bopd"]))
        pot.append(float(r["potential_oil_bopd"]) if pd.notna(r.get("potential_oil_bopd")) else np.nan)
        up.append(float(r["target_uptime_pct"]) if pd.notna(r.get("target_uptime_pct")) else np.nan)
    if missing:
        return None, None, None, sorted(set(missing))
    return float(np.mean(tg)), float(np.nanmean(pot)) if pot else None, float(np.nanmean(up)) if up else None, []


def _pinned_band(fld: str) -> dict | None:
    try:
        from app.analytics.generator.validate import GAP_TARGET
    except Exception:
        return None
    b = GAP_TARGET.get(fld)
    return {"target_pct": round(b[0] * 100.0, 1), "tol_pp": round(b[1] * 100.0, 1)} if b else None


@lru_cache(maxsize=32)
def _field_row(fld: str, start: date, end: date) -> dict:
    from .attribution import attribute_decline
    from .candidate_ranking import rank_candidates
    from .health import classify_well_health

    d = load_table("daily_production", fld)
    d = d[(d["production_date"] >= start) & (d["production_date"] <= end)]
    n_days = int(d["production_date"].nunique())
    oil = float(d["oil_rate_bopd"].fillna(0.0).sum())
    water = float(d["water_rate_bwpd"].fillna(0.0).sum())
    actual = oil / n_days if n_days else None
    uptime = float(d["runtime_fraction"].fillna(0.0).mean() * 100.0) if len(d) else None
    wc = water / (oil + water) * 100.0 if (oil + water) > 0 else None

    target, potential, tgt_up, missing_months = _targets(fld, start, end)
    gap = (actual / target - 1.0) * 100.0 if (actual is not None and target) else None
    gap_exp = (actual / potential - 1.0) * 100.0 if (actual is not None and potential) else None

    h = classify_well_health(fld, as_of=end)
    hv = h.value
    window_days = (end - start).days + 1
    att = attribute_decline(field=fld, as_of=end, window_days=max(7, window_days))
    av = att.value
    by_class = {k: _r(v["bbl"], 1) for k, v in (av.by_class.items() if av is not None else [])}
    top = None
    if av is not None and av.by_class:
        k, v = max(av.by_class.items(), key=lambda kv: kv[1]["bbl"])
        top = {"field": fld, "factor_class": k, "bbl": _r(v["bbl"], 1), "pct": _r(v["pct"], 1),
               "controllable": bool(v["controllable"])}
    q = rank_candidates(fld, as_of=end).value
    st = _open_status_counts(fld, end)
    band = _pinned_band(fld)
    wm = load_table("well_master")
    return {
        "field": fld,
        "actual_bopd": _r(actual, 1),
        "target_bopd": _r(target, 1),
        "expected_bopd": _r(potential, 1),
        "gap_pct": _r(gap, 1),
        "gap_to_expected_pct": _r(gap_exp, 1),
        "uptime_pct": _r(uptime, 1),
        "target_uptime_pct": _r(tgt_up, 1),
        "water_cut_pct": _r(wc, 1),
        "health_counts": dict(hv.counts) if hv is not None else None,
        "sick_or_lost_count": int(hv.sick_or_lost_count) if hv is not None else None,
        "deferred_by_factor": by_class,
        "deferred_total_bbl": _r(av.total_loss_bbl, 1) if av is not None else None,
        "controllable_pct": _r(av.controllable_pct, 1) if av is not None else None,
        "top_factor": top["factor_class"] if top else None,
        "_top": top,
        "active_interventions": int(st.get("UNDER_WORKOVER", 0)),
        "waiting_on_rig": int(st.get("WAITING_ON_RIG", 0)),
        "waiting_on_material": int(st.get("WAITING_ON_MATERIAL", 0)),
        "status_counts": st,
        "rig_candidates": len(q.rig_queue) if q is not None else None,
        "rigless_candidates": len(q.rigless_queue) if q is not None else None,
        "n_wells": int((wm["field"] == fld).sum()),
        "n_days": n_days,
        "pinned_band": band,
        "in_pinned_band": (abs(gap - band["target_pct"]) <= band["tol_pp"] + 1e-9) if (band and gap is not None) else None,
        "_missing_months": missing_months,
        "_attribution_status": att.status.value,
    }


def compare_fields(asset: str = ASSET, as_of: date | None = None, period: str = "QTD") -> ToolResult:
    """TC-024. Rank the asset's fields by gap to target and name the worst field's top loss driver."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    period = (period or "QTD").upper()
    params = {"asset": asset, "as_of": str(as_of), "period": period}
    if asset and str(asset).strip().upper() not in (ASSET, "ASSAM", "ALL"):
        return unavailable("TC-024", params, t0, ["asset"], f"Unknown asset '{asset}'. Only {ASSET} is in the dataset.")
    win = period_window(period, as_of)
    if win is None:
        return unavailable("TC-024", params, t0, ["period"], f"period must be one of {list(PERIODS)}.")
    start, end = win
    rows, excluded = [], []
    for fld in FIELDS:
        r = dict(_field_row(fld, start, end))
        if r["_missing_months"]:
            r["gap_pct"] = "UNAVAILABLE"
            excluded.append({"field": fld, "reason": f"field_targets missing for {', '.join(r['_missing_months'])}"})
        rows.append(r)
    ranked = sorted((r for r in rows if isinstance(r["gap_pct"], (int, float))), key=lambda r: (r["gap_pct"], r["field"]))
    ranking = [r["field"] for r in ranked]
    worst = ranking[0] if ranking else None
    top = next((r["_top"] for r in rows if r["field"] == worst), None)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in ranked + [r for r in rows if r not in ranked]]
    val = FieldComparison(asset=ASSET, period=period, window_start=start, window_end=end, rows=clean,
                          ranking=ranking, worst_field=worst, top_driver=top, excluded=excluded)
    parts = [f"{r['field']} {r['gap_pct']:+.1f}%" for r in ranked]
    msg = f"{period} {start}..{end} gap to target: " + ", ".join(parts) + "."
    if worst and top:
        msg += (f" Worst: {worst}; top driver {top['factor_class']} ({top['pct']:.1f}% of lost oil, "
                f"{'controllable' if top['controllable'] else 'uncontrollable'}).")
    status = ToolStatus.OK if not excluded else ToolStatus.LOW_CONFIDENCE
    return ToolResult(status, val, [f"field_targets:{e['field']}" for e in excluded], msg,
                      build_provenance("TC-024", params, t0, window_start=str(start), window_end=str(end)))


register_cache(_field_row.cache_clear)
