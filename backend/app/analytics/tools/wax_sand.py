"""TC-035 ``wax_sand_behaviour`` (v0.6 Stage ED-5, F-31): "is this normal wax / sand — can we predict it?".

For each deposit kind (WAX, SAND) the tool reads, for one well:

* the fluid-hazard flag (``fluid_hazards.wax_flag`` / ``sand_flag``)
* jobs: ``workover_history`` rows with ``failure_code`` == kind or a ``catalogue_job_code`` starting
  ``WAX_`` / ``SAND_`` (excluding censored placeholders)
* downtime: ``well_status_history`` episodes with ``reason_code`` == kind (days, deferred bbl)
* cadence: the median interval between the well's own jobs, compared with the field norm (median of
  per-well median intervals in the same field) → next-due date = last job + own interval (field norm
  when the well has < 2 jobs), and whether it is overdue at ``as_of``.

There are no sand-rate (pptb) or wax-appearance-temperature measurements in the dataset; sand and wax
behaviour are inferred from jobs and downtime only, and the tool says so. Every number comes from the
tables (X-1). Thresholds/definitions are pinned in ``docs/pinned_values.md`` §13.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from app import settings
from app.analytics.tools.common import ToolResult, ToolStatus, build_provenance, load_table, unavailable, well_master_row, well_rows

TOOL_ID = "TC-035"
KINDS = ("WAX", "SAND")
DATA_NOTE = ("No sand-rate (pptb) or wax-appearance-temperature measurements exist in the data; "
             "behaviour is inferred from jobs and downtime.")


def _jobs(wo: pd.DataFrame, kind: str) -> pd.DataFrame:
    if wo.empty:
        return wo
    cat = wo["catalogue_job_code"].fillna("").astype(str)
    m = (wo["failure_code"].astype(str) == kind) | cat.str.startswith(kind + "_")
    m &= wo["outcome"].astype(str) != "CENSORED"
    return wo[m].sort_values("start_date")


def _median_interval(dates: list[date]) -> float | None:
    if len(dates) < 2:
        return None
    gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
    return float(pd.Series(gaps).median()) if gaps else None


@lru_cache(maxsize=8)
def _field_norms(as_of: date) -> dict[tuple[str, str], dict]:
    """(field, kind) → {median_interval_days, wells_with_jobs, wells_in_field}."""
    wo = load_table("workover_history")
    wo = wo[wo["start_date"] <= as_of]
    wm = load_table("well_master")
    out: dict[tuple[str, str], dict] = {}
    for field, wells in wm.groupby("field")["well_id"]:
        sub = wo[wo["well_id"].isin(set(wells))]
        for kind in KINDS:
            j = _jobs(sub, kind)
            per_well = [_median_interval(list(g["start_date"])) for _, g in j.groupby("well_id")]
            per_well = [x for x in per_well if x is not None]
            out[(str(field), kind)] = {
                "median_interval_days": round(float(pd.Series(per_well).median())) if per_well else None,
                "wells_with_jobs": int(j["well_id"].nunique()),
                "wells_in_field": int(len(wells)),
            }
    return out


def _kind_block(wid: str, field: str, kind: str, flag: bool | None, wo: pd.DataFrame, st: pd.DataFrame,
                as_of: date) -> dict:
    j = _jobs(wo, kind)
    dates = list(j["start_date"])
    own = _median_interval(dates)
    norm = _field_norms(as_of).get((field, kind), {})
    field_iv = norm.get("median_interval_days")
    last = None
    if not j.empty:
        r = j.iloc[-1]
        last = {"job_code": str(r["catalogue_job_code"] or r["job_code"]), "date": str(r["start_date"]),
                "outcome": str(r["outcome"]),
                "uplift_bopd": None if pd.isna(r["uplift_bopd"]) else round(float(r["uplift_bopd"]), 1)}
    # Predict only from the well's own repeat cadence; a single job is not a pattern.
    basis = "OWN" if own is not None else None
    next_due = overdue_days = None
    if last and own is not None:
        nd = date.fromisoformat(last["date"]) + timedelta(days=int(round(own)))
        next_due = str(nd)
        overdue_days = max(0, (as_of - nd).days)

    ep = st[st["reason_code"].astype(str) == kind] if not st.empty else st
    dt_days = 0
    deferred = 0.0
    ongoing = None
    for e in ep.itertuples():
        open_ = e.end_date is None or pd.isna(e.end_date) or e.end_date >= as_of
        end = as_of if open_ else e.end_date
        dt_days += max(0, (min(end, as_of) - e.start_date).days + 1)
        deferred += 0.0 if pd.isna(e.deferred_bbl) else float(e.deferred_bbl)
        if open_:
            ongoing = {"status": str(e.status), "since": str(e.start_date)}

    n = len(dates)
    k = kind.lower()
    down = (f"{len(ep)} {k} downtime episode{'s' if len(ep) != 1 else ''} ({dt_days} days"
            + (f", {round(deferred)} bbl deferred" if deferred else "") + ")") if len(ep) else ""
    now = (f" Now {ongoing['status'].replace('_', ' ').lower()} for {k} since {ongoing['since']}." if ongoing else "")
    if n == 0 and not len(ep):
        verdict = "FLAGGED_NO_JOBS" if flag else "NOT_PRONE"
        text = (f"Fluid flagged for {k} but no {k} jobs or downtime on record." if flag
                else f"Not {k}-prone: no {k} flag, jobs or downtime on record.")
    elif n == 0:
        verdict, text = "DOWNTIME_ONLY", f"No {k} jobs yet, but {down}.{now}"
    else:
        verdict = "PREDICTABLE" if own is not None and n >= 3 else ("REPEAT" if own is not None else "ISOLATED")
        text = f"{n} {k} job{'s' if n != 1 else ''}; last {last['job_code'].replace('_', ' ').lower()} on {last['date']} ({last['outcome'].lower()})"
        if own is not None:
            text += f"; repeats every ~{round(own)} days"
            if field_iv:
                rel = "more often than" if own < field_iv * 0.8 else ("less often than" if own > field_iv * 1.25 else "in line with")
                text += f" ({rel} the {field} norm of {field_iv} days)"
            text += f". Next due {next_due}" + (f" — overdue by {overdue_days} days" if overdue_days else "")
        else:
            text += "; single job, no repeat pattern"
        if down:
            text += f". {down[0].upper()}{down[1:]}"
        text += "." + now

    return {"kind": kind, "flag": None if flag is None else bool(flag), "verdict": verdict, "n_jobs": n,
            "last_job": last, "own_interval_days": None if own is None else round(own),
            "field_interval_days": field_iv, "field_wells_with_jobs": norm.get("wells_with_jobs"),
            "field_wells": norm.get("wells_in_field"), "interval_basis": basis, "next_due": next_due,
            "overdue_days": overdue_days, "downtime_episodes": int(len(ep)), "downtime_days": int(dt_days),
            "deferred_bbl": round(deferred), "ongoing": ongoing, "job_dates": [str(d) for d in dates[-10:]],
            "text": text}


def wax_sand_behaviour(well_id: str, as_of: date | None = None) -> ToolResult:
    return _cached((well_id or "").strip().upper(), as_of or settings.AS_OF)


@lru_cache(maxsize=1024)
def _cached(wid: str, as_of: date) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": wid, "as_of": str(as_of)}
    wm = well_master_row(wid)
    if wm is None:
        return unavailable(TOOL_ID, params, t0, ["well_id"], f"Unknown well {wid}.")
    field = str(wm.get("field"))
    wo = well_rows("workover_history", wid)
    wo = wo[wo["start_date"] <= as_of] if not wo.empty else wo
    st = well_rows("well_status_history", wid)
    st = st[st["start_date"] <= as_of] if not st.empty else st
    fh = well_rows("fluid_hazards", wid)
    flags = {"WAX": None, "SAND": None}
    if not fh.empty:
        flags = {"WAX": bool(fh.iloc[0]["wax_flag"]), "SAND": bool(fh.iloc[0]["sand_flag"])}
    blocks = {k.lower(): _kind_block(wid, field, k, flags[k], wo, st, as_of) for k in KINDS}
    summary = f"{wid} — Wax: {blocks['wax']['text']} Sand: {blocks['sand']['text']}"
    value = {"well_id": wid, "field": field, "as_of": str(as_of), **blocks, "summary": summary, "data_note": DATA_NOTE}
    return ToolResult(ToolStatus.OK, value, [], summary, build_provenance(TOOL_ID, params, t0))
