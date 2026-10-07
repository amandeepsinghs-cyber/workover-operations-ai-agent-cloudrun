"""TC-028 field_production_history — 5-year field-wise production (SDD §6.2, F-11, Stage T).

Verbatim T2: *"the past let's say 5 year production data field-wise … aggregated of all the wells"*.

Definitions are **identical to Gold ``wellpulse_gold.field_kpi_monthly``**
(``lakehouse/dataform/definitions/gold/field_kpi_monthly.sqlx``) so the app, the lakehouse and the voice
agent quote the same numbers (Gate X "Gold field_kpi_monthly = TC-028 output"):

* volumes: ``SUM`` of daily allocated rates (NULL → 0, DC-014) over all wells and days ≤ ``end``;
* ``days_in_period`` = distinct production dates in the period; rates = volume / ``days_in_period``;
* ``water_cut_pct`` = ``water_bbl / (oil_bbl + water_bbl) × 100`` (volume-weighted);
* ``producing_wells`` = producing well-days / ``days_in_period``; ``uptime_pct`` = mean ``runtime_fraction`` × 100;
* ``target_oil_bopd`` = day-weighted mean of ``field_targets.target_oil_bopd`` over the period's dates;
  ``gap_pct`` = ``(oil_bopd − target_oil_bopd) / target_oil_bopd × 100``.

``reconciliation`` re-derives each period's oil from per-well monthly sums (an independent group-by path)
and reports the max relative error (BDD-F11-S03: within 0.1 %).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field as dc_field
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from app import settings

from .common import ToolResult, ToolStatus, build_provenance, load_table, register_cache, unavailable
from .hierarchy import FIELDS, resolve_field

FREQS = {"M": "M", "Q": "Q", "Y": "Y"}

DEFINITIONS = {
    "source": "wellpulse_gold.field_kpi_monthly definitions (lakehouse/dataform/definitions/gold/field_kpi_monthly.sqlx)",
    "oil_bopd": "SUM(daily oil_rate_bopd, NULL=0) over wells and days / days_in_period",
    "water_cut_pct": "water_bbl / (oil_bbl + water_bbl) * 100 (volume-weighted)",
    "producing_wells": "producing well-days / days_in_period",
    "uptime_pct": "mean runtime_fraction over all well-days * 100",
    "target_oil_bopd": "day-weighted field_targets.target_oil_bopd",
    "gap_pct": "(oil_bopd - target_oil_bopd) / target_oil_bopd * 100",
}


@dataclass(frozen=True)
class FieldSeries:
    freq: str
    start: date
    end: date
    fields: list[str]
    series: list[dict]
    summary: list[dict]
    reconciliation: list[dict]
    definitions: dict = dc_field(default_factory=lambda: dict(DEFINITIONS))


def _r(x, nd: int = 1):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(v) or np.isinf(v)) else round(v, nd)


def _period_start(d: pd.Series, freq: str) -> pd.Series:
    return pd.to_datetime(d).dt.to_period(freq).dt.start_time.dt.date


def _daily_targets(fld: str, dates: pd.Series) -> pd.Series:
    """Daily target rate (its month's ``target_oil_bopd``) for each date; NaN where no target row."""
    t = load_table("field_targets")
    if t.empty:
        return pd.Series(np.nan, index=dates.index)
    t = t[t["field"] == fld]
    tm = {pd.Timestamp(m).to_period("M"): float(v) for m, v in zip(t["month"], t["target_oil_bopd"])}
    per = pd.to_datetime(dates).dt.to_period("M")
    return per.map(lambda p: tm.get(p, np.nan)).astype(float)


@lru_cache(maxsize=64)
def _field_frame(fld: str, start: date, end: date, freq: str) -> tuple[pd.DataFrame, float, int]:
    d = load_table("daily_production", fld)
    d = d[(d["production_date"] >= start) & (d["production_date"] <= end)]
    if d.empty:
        return pd.DataFrame(), 0.0, 0
    w = pd.DataFrame({
        "production_date": d["production_date"].values,
        "well_id": d["well_id"].values,
        "oil": d["oil_rate_bopd"].fillna(0.0).astype(float).values,
        "water": d["water_rate_bwpd"].fillna(0.0).astype(float).values,
        "gas": d["gas_rate_mscfd"].fillna(0.0).astype(float).values,
        "liquid": d["liquid_rate_blpd"].fillna(0.0).astype(float).values,
        "rf": d["runtime_fraction"].fillna(0.0).astype(float).values,
        "prod": d["is_producing"].fillna(False).astype(bool).values,
    })
    w["period"] = _period_start(w["production_date"], freq)
    g = w.groupby("period", sort=True)
    m = pd.DataFrame({
        "days_in_period": g["production_date"].nunique(),
        "wells_reporting": g["well_id"].nunique(),
        "oil_bbl": g["oil"].sum(),
        "water_bbl": g["water"].sum(),
        "gas_mscf": g["gas"].sum(),
        "liquid_bbl": g["liquid"].sum(),
        "producing_well_days": g["prod"].sum(),
        "mean_rf": g["rf"].mean(),
    })
    # target: mean of the daily target over the distinct dates of the period (= the month value for freq M)
    dates = pd.DataFrame({"production_date": sorted(w["production_date"].unique())})
    dates["period"] = _period_start(dates["production_date"], freq)
    dates["target"] = _daily_targets(fld, dates["production_date"]).values
    tg = dates.groupby("period")["target"].agg(lambda s: float(s.mean()) if s.notna().all() else np.nan)
    m["target_oil_bopd"] = tg

    # reconciliation: per-well monthly sums → field (independent aggregation path)
    pw = w.groupby(["period", "well_id"], sort=False)["oil"].sum().groupby(level=0).sum()
    rel = ((pw - m["oil_bbl"]).abs() / m["oil_bbl"].abs().clip(lower=1e-9)).max()
    return m.reset_index(), float(rel * 100.0), int(len(m))


def _is_partial(period: date, freq: str, days: int) -> bool:
    p = pd.Timestamp(period).to_period(freq)
    return int(days) < int((p.end_time.normalize() - p.start_time.normalize()).days + 1)


def field_production_history(fields: list[str] | str | None = None, start: date | None = None,
                             end: date | None = None, freq: str = "M") -> ToolResult:
    """TC-028. Per-field monthly (or Q / Y) oil, gas, water, water cut, producing wells and uptime."""
    t0 = time.perf_counter()
    if isinstance(fields, str):
        fields = [f for f in (x.strip() for x in fields.split(",")) if f]
    start = start or settings.DATA_START
    end = end or settings.AS_OF
    freq = (freq or "M").upper()
    params = {"fields": fields, "start": str(start), "end": str(end), "freq": freq, "as_of": str(settings.AS_OF)}
    if freq not in FREQS:
        return unavailable("TC-028", params, t0, ["freq"], f"freq must be one of {list(FREQS)}.")
    if start > end:
        return unavailable("TC-028", params, t0, ["start", "end"], "start is after end.")
    if fields and any(f.upper() == "ALL" for f in fields):
        fields = None
    resolved: list[str] = []
    for f in fields or list(FIELDS):
        r = resolve_field(f)
        if r is None:
            return unavailable("TC-028", params, t0, ["fields"],
                               f"Unknown field '{f}'. Fields in the dataset: {', '.join(FIELDS)}.")
        if r not in resolved:
            resolved.append(r)

    series: list[dict] = []
    summary: list[dict] = []
    recon: list[dict] = []
    missing: list[str] = []
    for fld in resolved:
        m, rel_pct, n = _field_frame(fld, start, end, freq)
        if m.empty:
            missing.append(f"daily_production:{fld}")
            continue
        rows = []
        for r in m.itertuples(index=False):
            days = int(r.days_in_period)
            oil_bopd = r.oil_bbl / days
            tgt = None if pd.isna(r.target_oil_bopd) else float(r.target_oil_bopd)
            ow = r.oil_bbl + r.water_bbl
            rows.append({
                "field": fld,
                "period": r.period,
                "days_in_period": days,
                "is_partial": _is_partial(r.period, freq, days),
                "wells_reporting": int(r.wells_reporting),
                "oil_bbl": _r(r.oil_bbl, 1),
                "water_bbl": _r(r.water_bbl, 1),
                "gas_mscf": _r(r.gas_mscf, 1),
                "liquid_bbl": _r(r.liquid_bbl, 1),
                "oil_bopd": _r(oil_bopd, 1),
                "water_bwpd": _r(r.water_bbl / days, 1),
                "gas_mscfd": _r(r.gas_mscf / days, 1),
                "liquid_blpd": _r(r.liquid_bbl / days, 1),
                "water_cut_pct": _r(r.water_bbl / ow * 100.0, 2) if ow > 0 else None,
                "producing_wells": _r(r.producing_well_days / days, 1),
                "uptime_pct": _r(r.mean_rf * 100.0, 1),
                "target_oil_bopd": _r(tgt, 1),
                "gap_pct": _r((oil_bopd - tgt) / tgt * 100.0, 1) if tgt else None,
            })
        series.extend(rows)
        a, b = rows[0], rows[-1]

        def _chg(x, y):
            return _r((y - x) / x * 100.0, 1) if x not in (None, 0) and y is not None else None

        summary.append({
            "field": fld, "start_period": a["period"], "end_period": b["period"],
            "start_oil": a["oil_bopd"], "end_oil": b["oil_bopd"], "change_pct": _chg(a["oil_bopd"], b["oil_bopd"]),
            "start_gas": a["gas_mscfd"], "end_gas": b["gas_mscfd"], "gas_change_pct": _chg(a["gas_mscfd"], b["gas_mscfd"]),
            "start_wc_pct": a["water_cut_pct"], "end_wc_pct": b["water_cut_pct"],
            "wc_change_pp": _r(b["water_cut_pct"] - a["water_cut_pct"], 2)
            if a["water_cut_pct"] is not None and b["water_cut_pct"] is not None else None,
            "start_producing_wells": a["producing_wells"], "end_producing_wells": b["producing_wells"],
            "n_periods": len(rows),
        })
        recon.append({"field": fld, "max_rel_error_pct": round(rel_pct, 6), "periods_checked": n})

    if not series:
        return unavailable("TC-028", params, t0, missing or ["daily_production"], "No production rows in range.")
    val = FieldSeries(freq=freq, start=start, end=end, fields=[s["field"] for s in summary], series=series,
                      summary=summary, reconciliation=recon)
    parts = [f"{s['field']} {s['start_oil']:.0f}→{s['end_oil']:.0f} BOPD ({s['change_pct']:+.1f}%), "
             f"WC {s['wc_change_pp']:+.1f} pp" for s in summary if s["change_pct"] is not None
             and s["wc_change_pp"] is not None]
    msg = (f"{len(summary)} field(s), {summary[0]['n_periods']} {freq} periods {start}..{end}: " + "; ".join(parts) + ".")
    status = ToolStatus.OK if not missing else ToolStatus.LOW_CONFIDENCE
    return ToolResult(status, val, missing, msg, build_provenance("TC-028", params, t0))


register_cache(_field_frame.cache_clear)
