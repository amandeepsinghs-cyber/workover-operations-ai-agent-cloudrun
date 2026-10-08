"""TC-034 ``well_anomalies`` (v0.6 Stage ED-4, F-30): "well history — any anomalies?".

Rule-based, deterministic scan of the last ``months`` of daily production and status history.
Event types (thresholds pinned in ``docs/pinned_values.md`` §13):

* ``RATE_DROP``  — 7-day mean oil ≥ 30% below the prior 30-day median (producing days)
* ``WC_JUMP``    — 7-day mean water cut ≥ 10 pts above the prior 30-day median
* ``WC_TREND``   — water cut (90-day mean) ≥ 10 pts above the same 90 days a year earlier
* ``THP_SHIFT``  — 7-day mean THP moves ≥ 25% (and ≥ 2 kg/cm²) from the prior 30-day median
* ``DOWNTIME``   — a non-producing status episode of ≥ 7 days (reason + deferred bbl when recorded)

Events of the same type within 30 days are merged; each is linked to a workover starting within
±30 days. Returns the 12 most severe, newest first. Every number comes from the tables (X-1).
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from app import settings
from app.analytics.tools.common import ToolResult, ToolStatus, build_provenance, unavailable, well_master_row, well_rows

TOOL_ID = "TC-034"
RATE_DROP_FRAC = 0.30
WC_JUMP_PTS = 10.0
THP_SHIFT_FRAC = 0.25
THP_SHIFT_MIN = 2.0
DOWNTIME_DAYS = 7
MERGE_DAYS = 30
LINK_DAYS = 30
MAX_EVENTS = 12


def _r(x, nd=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def _signal_events(d: pd.DataFrame, col: str, kind: str, test) -> list[dict]:
    s = d.set_index("production_date")[col].astype(float)
    if s.dropna().size < 60:
        return []
    recent = s.rolling(7, min_periods=5).mean()
    base = s.shift(7).rolling(30, min_periods=20).median()
    hit = test(recent, base)
    events: list[dict] = []
    last_day = None
    for day, flag in hit.items():
        if not flag:
            continue
        if last_day is not None and (day - last_day).days <= MERGE_DAYS:
            last_day = day
            continue
        last_day = day
        events.append({"type": kind, "date": str(day), "before": _r(base[day]), "after": _r(recent[day])})
    return events


def _wc_trend(d: pd.DataFrame, as_of: date) -> list[dict]:
    """Slow water-cut rise: last-90-day mean vs. the 90 days a year earlier ≥ 10 pts."""
    s = d.set_index("production_date")["water_cut_pct"].astype(float)
    now = s[s.index > as_of - timedelta(days=90)]
    then = s[(s.index > as_of - timedelta(days=455)) & (s.index <= as_of - timedelta(days=365))]
    if now.size < 20 or then.size < 20 or (now.mean() - then.mean()) < WC_JUMP_PTS:
        return []
    return [{"type": "WC_TREND", "date": str(as_of - timedelta(days=365)), "before": _r(then.mean()),
             "after": _r(now.mean())}]


def _downtime(wid: str, start: date, as_of: date) -> list[dict]:
    st = well_rows("well_status_history", wid)
    if st.empty:
        return []
    out = []
    for r in st.itertuples():
        if r.status == "PRODUCING" or r.start_date > as_of:
            continue
        end = r.end_date if (r.end_date is not None and not pd.isna(r.end_date)) else as_of
        end = min(end, as_of)
        if end < start:
            continue
        days = (end - r.start_date).days + 1
        if days < DOWNTIME_DAYS:
            continue
        reason = getattr(r, "reason_code", None)
        out.append({"type": "DOWNTIME", "date": str(r.start_date), "days": int(days), "status": str(r.status),
                    "reason": None if reason is None or pd.isna(reason) else str(reason),
                    "deferred_bbl": _r(getattr(r, "deferred_bbl", None), 0),
                    "ongoing": bool(r.end_date is None or pd.isna(r.end_date) or r.end_date >= as_of)})
    return out


def _link_jobs(events: list[dict], wid: str) -> None:
    wo = well_rows("workover_history", wid)
    if wo.empty:
        return
    for e in events:
        d = date.fromisoformat(e["date"])
        near = wo[(wo["start_date"] >= d - timedelta(days=LINK_DAYS)) & (wo["start_date"] <= d + timedelta(days=LINK_DAYS))]
        if not near.empty:
            j = near.iloc[(near["start_date"].map(lambda x: abs((x - d).days))).argsort().iloc[0]]
            e["linked_job"] = {"job_code": str(j.get("catalogue_job_code") or j.get("job_code")),
                               "date": str(j["start_date"]), "outcome": str(j.get("outcome") or "—")}


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _severity(e: dict) -> float:
    if e["type"] == "DOWNTIME":
        return 1.0 + e["days"] / 30.0 + (2.0 if e.get("ongoing") else 0.0)
    b, a = e.get("before"), e.get("after")
    if b is None or a is None:
        return 0.0
    if e["type"] in ("WC_JUMP", "WC_TREND"):
        return (a - b) / 10.0
    return abs(a - b) / max(abs(b), 0.1) * 3.0


def _describe(e: dict) -> str:
    t = e["type"]
    if t == "RATE_DROP":
        pct = _r((1 - e["after"] / e["before"]) * 100.0, 0) if e["before"] else None
        txt = f"Oil fell {pct}% ({e['before']} → {e['after']} bopd)"
    elif t == "WC_TREND":
        txt = f"Water cut rising steadily over 12 months: {e['before']} → {e['after']}%"
    elif t == "WC_JUMP":
        txt = f"Water cut jumped {e['before']} → {e['after']}%"
    elif t == "THP_SHIFT":
        txt = f"THP shifted {e['before']} → {e['after']} kg/cm²"
    else:
        txt = (f"{e['status'].replace('_', ' ').title()} {e['days']} days"
               + (f" ({e['reason'].replace('_', ' ').lower()})" if e.get("reason") else "")
               + (f", {int(e['deferred_bbl'])} bbl deferred" if e.get("deferred_bbl") else "")
               + (" — ongoing" if e.get("ongoing") else ""))
    if e.get("linked_job"):
        j = e["linked_job"]
        txt += f"; job {j['job_code'].replace('_', ' ').lower()} on {j['date']} ({j['outcome'].lower()})"
    return txt


def well_anomalies(well_id: str, as_of: date | None = None, months: int = 24) -> ToolResult:
    return _cached((well_id or "").strip().upper(), as_of or settings.AS_OF, int(months))


@lru_cache(maxsize=1024)
def _cached(wid: str, as_of: date, months: int) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": wid, "as_of": str(as_of), "months": months}
    if well_master_row(wid) is None:
        return unavailable(TOOL_ID, params, t0, ["well_id"], f"Unknown well {wid}.")
    start = as_of - timedelta(days=int(months * 30.44))

    d = well_rows("daily_production", wid)
    d = d[(d["production_date"] > start - timedelta(days=45)) & (d["production_date"] <= as_of)]
    if "is_producing" in d.columns:
        d = d[d["is_producing"] == True]  # noqa: E712
    d = d[d["oil_rate_bopd"].fillna(0) > 0].sort_values("production_date")

    events: list[dict] = []
    if not d.empty:
        events += _signal_events(d, "oil_rate_bopd", "RATE_DROP", lambda rc, b: rc <= b * (1 - RATE_DROP_FRAC))
        if "water_cut_pct" in d.columns:
            events += _signal_events(d, "water_cut_pct", "WC_JUMP", lambda rc, b: (rc - b) >= WC_JUMP_PTS)
        if "thp_kgcm2" in d.columns:
            events += _signal_events(d, "thp_kgcm2", "THP_SHIFT",
                                     lambda rc, b: ((rc - b).abs() >= THP_SHIFT_MIN) & ((rc - b).abs() >= b.abs() * THP_SHIFT_FRAC))
        if "water_cut_pct" in d.columns:
            events += _wc_trend(d, as_of)
    events = [e for e in events if date.fromisoformat(e["date"]) > start]
    events += _downtime(wid, start, as_of)
    _link_jobs(events, wid)
    for e in events:
        e["severity"] = _r(_severity(e), 2)
        e["text"] = _describe(e)
    top = sorted(events, key=lambda e: -e["severity"])[:MAX_EVENTS]
    top.sort(key=lambda e: e["date"], reverse=True)

    counts = {k: sum(1 for e in events if e["type"] == k) for k in ("RATE_DROP", "WC_JUMP", "WC_TREND", "THP_SHIFT", "DOWNTIME")}
    if top:
        lead = max(top, key=lambda e: e["severity"])
        parts = [_plural(counts["RATE_DROP"], "rate drop"), _plural(counts["WC_JUMP"] + counts["WC_TREND"], "water-cut rise"),
                 _plural(counts["THP_SHIFT"], "THP shift"), _plural(counts["DOWNTIME"], "downtime episode")]
        summary = (f"{wid}: {_plural(len(events), 'anomaly', 'anomalies')} in {months} months "
                   f"({', '.join(p for p in parts if not p.startswith('0 '))}). "
                   f"Most significant: {lead['date']} — {lead['text']}.")
    else:
        summary = f"{wid}: no anomalies in the last {months} months."
    value = {"well_id": wid, "as_of": str(as_of), "months": months, "counts": counts,
             "n_total": len(events), "events": top, "summary": summary}
    return ToolResult(ToolStatus.OK, value, [], summary, build_provenance(TOOL_ID, params, t0))
