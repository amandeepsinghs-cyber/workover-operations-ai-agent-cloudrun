"""field_targets (SDD §5.3; F-09, decision N-D5).

target_oil_bopd(month) = potential(month) × U_plan
  * potential = Σ over wells of the healthy-state oil rate (Arps decline × persistent productivity at
    the persistent water cut; 0 for idle / plugged wells) — what the field could make if every well were
    up and undegraded.
  * U_plan = realised actual / potential over the first 24 months (2021-10 → 2023-09): the field's
    baseline operating efficiency, used as the plan.
target_uptime_pct = producing well-days / non-idle well-days over the same baseline period.

No target is set from the designed gap; the gap vs. target *emerges* from what happens after the
baseline (Lakwa's deteriorating logistics, GGS-II outages, …) and is measured by ``gap_vs_target``.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

PLAN_START = date(2021, 10, 1)
PLAN_END = date(2023, 9, 30)


def build_field_targets(field: str, potential: pd.Series, daily: pd.DataFrame, idle_wells: set[str]) -> pd.DataFrame:
    """potential: daily field potential (bopd) indexed by date; daily: production rows of the field."""
    d = daily[["well_id", "production_date", "oil_rate_bopd", "is_producing"]].copy()
    d["production_date"] = pd.to_datetime(d["production_date"])
    pot = potential.copy()
    pot.index = pd.to_datetime(pot.index)
    act = d.groupby("production_date")["oil_rate_bopd"].sum().reindex(pot.index, fill_value=0.0)
    lo, hi = pd.Timestamp(PLAN_START), pd.Timestamp(PLAN_END)
    u_plan = float(act[lo:hi].sum() / pot[lo:hi].sum())
    base = d[(d.production_date >= lo) & (d.production_date <= hi) & (~d.well_id.isin(idle_wells))]
    uptime = float(base["is_producing"].mean() * 100.0)
    m = pot.groupby(pot.index.to_period("M")).mean()
    return pd.DataFrame({
        "field": field,
        "month": [p.to_timestamp().date() for p in m.index],
        "target_oil_bopd": (m.to_numpy() * u_plan).round(1),
        "target_uptime_pct": round(uptime, 1),
        "potential_oil_bopd": m.to_numpy().round(1),
        "plan_efficiency": round(u_plan, 4),
    })


def gap_vs_target(targets: pd.DataFrame, daily: pd.DataFrame, start: date, end: date) -> float:
    """Σ actual oil / Σ target oil − 1 over [start, end] (daily target = its month's target rate)."""
    days = pd.date_range(start, end)
    t = targets.copy()
    t["month"] = pd.to_datetime(t["month"]).dt.to_period("M")
    tm = dict(zip(t["month"], t["target_oil_bopd"]))
    tgt = sum(tm[d.to_period("M")] for d in days)
    dd = daily.copy()
    dd["production_date"] = pd.to_datetime(dd["production_date"])
    act = dd[(dd.production_date >= days[0]) & (dd.production_date <= days[-1])]["oil_rate_bopd"].sum()
    return float(act / tgt - 1.0)
