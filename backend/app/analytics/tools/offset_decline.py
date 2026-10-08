"""TC-033 ``offset_decline_compare`` (v0.6 Stage ED-3, F-29): decline vs. nearby wells → "what is wrong".

Builds on TC-004 ``check_offsets`` (same verdict the diagnosis / NBA engine uses, so screens never disagree)
and adds what an ED wants to *see*:

* monthly oil, water cut and THP for the subject well and its 3–5 nearest same-zone offsets (24 months),
  plus oil normalised to 100 at the start of the window so decline shapes compare directly;
* 12-month trends per well: annual oil decline (log-linear fit), water-cut change (pts), THP change;
* the offsets' latest workover (nearby well history);
* a verdict (``WELL_SPECIFIC`` / ``RESERVOIR_WIDE`` / ``WATER`` / ``RESTORED`` / ``MIXED`` /
  ``INSUFFICIENT``) and one
  plain-language line built only from the numbers above (X-1). Thresholds: ``docs/pinned_values.md`` §ED.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from app import settings
from app.analytics.tools.common import (
    OffsetVerdict,
    ToolResult,
    ToolStatus,
    build_provenance,
    unavailable,
    well_master_row,
    well_rows,
)

TOOL_ID = "TC-033"
MAX_OFFSETS = 5
# Pinned (docs/pinned_values.md §ED): water rule
WC_JUMP_PTS = 10.0  # subject water cut up ≥ 10 pts in 12 months → WATER
WC_AREA_PTS = 5.0  # offsets' median WC up ≥ 5 pts → area-wide water (else well-specific water)
RESTORED_RES_PCT = 10.0  # rising rate and ≥ 10% above own decline curve → RESTORED (recent job worked)


def _monthly(well_id: str, start: date, end: date) -> pd.DataFrame:
    d = well_rows("daily_production", well_id)
    if d.empty:
        return pd.DataFrame(columns=["month", "oil", "wc", "thp", "days"])
    d = d[(d["production_date"] > start) & (d["production_date"] <= end)]
    if "is_producing" in d.columns:
        d = d[d["is_producing"] == True]  # noqa: E712
    d = d[d["oil_rate_bopd"].fillna(0) > 0]
    if d.empty:
        return pd.DataFrame(columns=["month", "oil", "wc", "thp", "days"])
    m = pd.to_datetime(d["production_date"]).dt.to_period("M").astype(str)
    g = d.assign(month=m).groupby("month")
    out = pd.DataFrame({
        "oil": g["oil_rate_bopd"].mean(),
        "wc": g["water_cut_pct"].mean() if "water_cut_pct" in d.columns else np.nan,
        "thp": g["thp_kgcm2"].mean() if "thp_kgcm2" in d.columns else np.nan,
        "days": g.size(),
    }).reset_index()
    return out[out["days"] >= 5].reset_index(drop=True)


def _r(x, nd=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def _trends(m: pd.DataFrame) -> dict:
    """12-month trends from the last 12 monthly points (needs ≥ 6)."""
    last = m.tail(12)
    if len(last) < 6:
        return {"decline_pct_yr": None, "wc_change_pts": None, "thp_change": None, "oil_now_bopd": None}
    y = np.log(np.clip(last["oil"].to_numpy(dtype=float), 0.1, None))
    slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])  # per month
    decline = (1.0 - float(np.exp(slope * 12.0))) * 100.0  # + = declining
    head, tail = last.head(3), last.tail(3)
    return {
        "decline_pct_yr": _r(decline),
        "wc_change_pts": _r(tail["wc"].mean() - head["wc"].mean()),
        "thp_change": _r(tail["thp"].mean() - head["thp"].mean()),
        "oil_now_bopd": _r(tail["oil"].mean()),
    }


def _trend_txt(d) -> str:
    if d is None:
        return "—"
    return f"declining {d}%/yr" if d >= 0 else f"rising {abs(d)}%/yr"


def _series(m: pd.DataFrame) -> list[dict]:
    base = float(m["oil"].head(3).mean()) if not m.empty else 0.0
    return [
        {"month": r.month, "oil_bopd": _r(r.oil), "oil_norm": _r(r.oil / base * 100.0) if base > 0 else None,
         "wc_pct": _r(r.wc), "thp_kgcm2": _r(r.thp)}
        for r in m.itertuples()
    ]


def _last_job(well_id: str, as_of: date, success_only: bool = False) -> dict | None:
    wo = well_rows("workover_history", well_id)
    if wo.empty:
        return None
    wo = wo[wo["start_date"] <= as_of].sort_values("start_date")
    if success_only:  # the job that restored rate: biggest successful uplift in the last 15 months
        wo = wo[(wo["outcome"] == "SUCCESS") & (wo["uplift_bopd"].fillna(0) > 0)
                & (wo["start_date"] >= as_of - timedelta(days=456))]
        wo = wo.sort_values(["uplift_bopd", "start_date"])
    if wo.empty:
        return None
    r = wo.iloc[-1]
    return {"job_code": str(r.get("catalogue_job_code") or r.get("job_code") or "—"),
            "date": str(r["start_date"]), "outcome": str(r.get("outcome") or "—"),
            "uplift_bopd": _r(r.get("uplift_bopd"))}


def _open_status(well_id: str, as_of: date) -> dict | None:
    st = well_rows("well_status_history", well_id)
    if st.empty:
        return None
    st = st[st["start_date"] <= as_of].sort_values("start_date")
    if st.empty:
        return None
    r = st.iloc[-1]
    reason = r.get("reason_code")
    return {"status": str(r["status"]), "since": str(r["start_date"]),
            "reason": None if reason is None or (isinstance(reason, float) and np.isnan(reason)) else str(reason)}


def _offset_ids(well_id: str, base_offsets: list[tuple[str, float, float]]) -> list[tuple[str, float]]:
    if base_offsets:
        return [(oid, dist) for oid, _res, dist in base_offsets][:MAX_OFFSETS]
    o = well_rows("well_offsets", well_id)
    if o.empty:
        return []
    same = o[o["same_zone"] == True]  # noqa: E712
    o = same if len(same) >= 3 else o
    o = o.sort_values("distance_m").head(MAX_OFFSETS)
    return [(str(r.offset_well_id), float(r.distance_m)) for r in o.itertuples()]


def offset_decline_compare(well_id: str, as_of: date | None = None, months: int = 24) -> ToolResult:
    return _cached((well_id or "").strip().upper(), as_of or settings.AS_OF, int(months))


@lru_cache(maxsize=1024)
def _cached(wid: str, as_of: date, months: int) -> ToolResult:
    from app.analytics.tools.candidate_ranking import check_offsets, detect_mechanical_signature

    t0 = time.perf_counter()
    params = {"well_id": wid, "as_of": str(as_of), "months": months}
    if well_master_row(wid) is None:
        return unavailable(TOOL_ID, params, t0, ["well_id"], f"Unknown well {wid}.")
    start = as_of - timedelta(days=int(months * 30.44))

    base = check_offsets(wid, as_of=as_of)
    bv = base.value
    base_verdict = bv.verdict if bv is not None else OffsetVerdict.INSUFFICIENT

    subj_m = _monthly(wid, start, as_of)
    subj_t = _trends(subj_m)
    offsets = []
    for oid, dist in _offset_ids(wid, list(bv.offset_residuals) if bv is not None else []):
        om = _monthly(oid, start, as_of)
        if om.empty:
            continue
        offsets.append({"well_id": oid, "distance_m": _r(dist, 0), **_trends(om),
                        "last_job": _last_job(oid, as_of), "series": _series(om)})

    off_dec = [o["decline_pct_yr"] for o in offsets if o["decline_pct_yr"] is not None]
    off_wc = [o["wc_change_pts"] for o in offsets if o["wc_change_pts"] is not None]
    med_dec = _r(float(np.median(off_dec))) if off_dec else None
    med_wc = _r(float(np.median(off_wc))) if off_wc else None

    # Verdict: water first (it changes the remedy), else the TC-004 verdict.
    water_scope = None
    if subj_t["wc_change_pts"] is not None and subj_t["wc_change_pts"] >= WC_JUMP_PTS:
        verdict = "WATER"
        water_scope = "AREA" if (med_wc is not None and med_wc >= WC_AREA_PTS) else "WELL"
    elif base_verdict == OffsetVerdict.RESERVOIR_DECLINE:
        verdict = "RESERVOIR_WIDE"
    elif base_verdict == OffsetVerdict.WELL_SPECIFIC:
        verdict = "WELL_SPECIFIC"
    elif base_verdict == OffsetVerdict.MIXED:
        verdict = "MIXED"
    else:
        verdict = "INSUFFICIENT"

    subj_job = _last_job(wid, as_of)
    s_res0 = _r(bv.subject_residual_pct) if bv is not None else None
    if (verdict == "MIXED" and subj_t["decline_pct_yr"] is not None and subj_t["decline_pct_yr"] < 0
            and s_res0 is not None and s_res0 >= RESTORED_RES_PCT):
        verdict = "RESTORED"  # rate is above its own decline curve, typically after a successful job
    status_now = _open_status(wid, as_of)

    mech = None
    if verdict in ("WELL_SPECIFIC", "MIXED"):
        md = detect_mechanical_signature(wid, as_of=as_of).value
        if md is not None and str(getattr(md.signature, "value", md.signature)) != "NONE":
            mech = {"signature": str(getattr(md.signature, "value", md.signature)),
                    "evidence": str(getattr(md, "evidence", "") or "")}

    # One plain-language line, numbers only from above.
    s_dec, s_res = subj_t["decline_pct_yr"], (_r(bv.subject_residual_pct) if bv is not None else None)
    o_res = _r(bv.offset_median_residual_pct) if bv is not None else None
    n = len(offsets)
    if verdict == "WATER":
        headline = (f"{wid}: water cut up {subj_t['wc_change_pts']} pts in 12 months"
                    + (f" while offsets rose {med_wc} pts — area-wide water advance."
                       if water_scope == "AREA" else
                       f" while offsets changed {med_wc if med_wc is not None else '—'} pts — water problem in this well "
                       f"(channelling / casing leak / coning)."))
    elif verdict == "WELL_SPECIFIC":
        headline = (f"{wid} is {abs(s_res)}% below its own decline curve while its {n} offsets are at "
                    f"{o_res}% — the problem is in this well (lift / skin / mechanical), not the reservoir."
                    if s_res is not None and o_res is not None else
                    f"{wid} under-performs its offsets — a well-specific problem.")
        if mech:
            headline += f" Signature: {mech['signature'].replace('_', ' ').lower()}."
    elif verdict == "RESERVOIR_WIDE":
        headline = (f"{wid} declines {s_dec}%/yr and its {n} offsets {med_dec}%/yr — the whole area is declining "
                    f"(reservoir depletion); a workover is unlikely to restore rate.")
    elif verdict == "MIXED":
        headline = (f"{wid} changes {_trend_txt(s_dec)} vs. offsets {_trend_txt(med_dec)} — "
                    f"no single clear cause from the offsets; see Diagnosis.")
    elif verdict == "RESTORED":
        ok_job = _last_job(wid, as_of, success_only=True)
        job_txt = (f" by {ok_job['job_code']} on {ok_job['date']} (+{ok_job['uplift_bopd']} bopd)" if ok_job else "")
        headline = (f"{wid} is {s_res}% above its own decline curve — rate was restored{job_txt}; "
                    f"its {n} offsets decline {med_dec if med_dec is not None else '—'}%/yr.")
    else:
        headline = f"Not enough producing offsets to compare {wid} (need ≥ 3)."
    if status_now and status_now["status"] != "PRODUCING":
        headline += (f" Now {status_now['status'].replace('_', ' ').lower()}"
                     + (f" ({status_now['reason'].replace('_', ' ').lower()})" if status_now.get("reason") else "")
                     + f" since {status_now['since']}.")

    value = {
        "well_id": wid, "as_of": str(as_of), "months": months,
        "verdict": verdict, "water_scope": water_scope, "headline": headline,
        "subject": {"well_id": wid, **subj_t, "residual_pct": s_res, "series": _series(subj_m)},
        "offsets": offsets,
        "offsets_median": {"decline_pct_yr": med_dec, "wc_change_pts": med_wc, "residual_pct": o_res},
        "base_verdict_tc004": base_verdict.value,
        "subject_last_job": subj_job,
        "status_now": status_now,
        "mechanical": mech,
    }
    status = ToolStatus.OK if verdict != "INSUFFICIENT" else ToolStatus.INSUFFICIENT_HISTORY
    return ToolResult(status, value, [], headline, build_provenance(TOOL_ID, params, t0, base_tool="TC-004"))
