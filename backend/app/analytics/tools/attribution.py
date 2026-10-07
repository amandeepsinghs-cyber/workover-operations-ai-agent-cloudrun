"""TC-019 ``attribute_decline`` — decline root-cause factor attribution (SDD §7, F-01).

Each well's lost oil over the window is split **exactly** into named components, so the parts
always reconcile to the total loss:

``L = Σ_t (q0 − A(t)) = natural + downtime + water + productivity``  (per day, identically)

* ``q0``  — mean producing oil rate (per producing hour, i.e. ``oil / runtime_fraction``) over the
  30 days before the window (extended to 90 days if the well was down for all 30).
* ``E(t)`` — Arps decline from ``q0`` using the TC-001 ``b`` / ``Di`` shape. When the TC-001 fit is
  ``LOW_CONFIDENCE`` or unavailable, ``E`` is held flat and the flag ``NATURAL_DECLINE_NOT_SEPARATED``
  is raised (the decline then lands in the productivity term and is labelled by TC-004 below).
* ``A(t)`` — actual daily oil volume (NULL / missing days → 0); ``rf(t)`` — runtime fraction.

Components (per day):

1. natural decline ``q0 − E`` → ``SUBSURFACE / NATURAL_DECLINE``
2. downtime ``E·(1 − rf)`` → overlapping ``operations_events`` row (earliest start wins; its own
   ``factor_class``), else ``daily_production.downtime_reason``, else the open status episode's
   ``reason_code`` (``config/factor_map.yaml``). Downtime with no recorded cause on a producing day
   is labelled like the productivity term (it is the same degradation).
3. water encroachment ``Liq·max(0, WC − WĈ)/100`` (``WĈ`` = 90-day pre-window WC trend). ``Liq`` is
   already a daily volume (runtime-scaled) so it is **not** multiplied by ``rf`` again (spec ≠ data
   note: SDD §7 row 3 writes ``rf·Liq``, which would double-count runtime on this dataset).
4. productivity ``rf·E − A − water``, labelled in priority order:
   a. overlapping ``DEFERRED_MAINTENANCE`` event → ``HUMAN_PROCESS``;
   b. precursor of a later mechanical status episode (≤ ``precursor_max_days`` before it) → that
      episode's ``reason_code`` class;
   c. trailing open segment: TC-005 signature → its class; TC-002 water mechanism → ``SUBSURFACE``;
   d. a setpoint event (``CHOKE_CHANGE`` / ``SPM_CHANGE`` / ``GL_RATE_CHANGE``) earlier in the window
      → ``OPERATIONAL``;
   e. TC-004 ``RESERVOIR_DECLINE`` → ``SUBSURFACE / RESERVOIR_DECLINE``;
   otherwise ``UNEXPLAINED``.
5. deferred-maintenance re-class: inside an EQUIPMENT/OPERATIONAL-labelled segment the "trigger" is
   the 7th consecutive producing day with ``A / (rf·E) ≤ 0.75`` (``config/sla.yaml``); losses of that
   segment (productivity, and non-human / non-external downtime before the workover starts) accruing
   after trigger + SLA (rig 14 d / rigless 3 d) move to ``HUMAN_PROCESS / DEFERRED_MAINTENANCE``.
6. ``UNEXPLAINED`` is the unlabelled remainder.

Per (factor_class, sub_factor) the signed daily contributions are summed; positive sums are
``components``, negative sums are listed in ``gains`` (never netted silently), so
``Σ components − gains_bbl = total_loss_bbl`` exactly. ``pct`` is the share of the gross loss
(Σ components). Human factor = a process delay attributed to a ``responsible_function``, never a person.
No currency anywhere (D-1).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from app import settings

from .arps_decline import arps_hyperbolic, fit_decline_curve
from .common import (
    ToolResult,
    ToolStatus,
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
from .hierarchy import resolve_field

_FMAP = load_yaml("factor_map.yaml")
_SLA = load_yaml("sla.yaml")
CONTROLLABLE = frozenset(_FMAP["controllable_classes"])
FACTOR_CLASSES = ("SUBSURFACE", "EQUIPMENT", "OPERATIONAL", "HUMAN_PROCESS", "EXTERNAL", "UNEXPLAINED")
SETPOINT_EVENTS = frozenset({"CHOKE_CHANGE", "SPM_CHANGE", "GL_RATE_CHANGE"})
NO_ACTION_FLAG = "NO_OPERATIONAL_ACTION_WOULD_HAVE_PREVENTED"
_WATER_MECHS = frozenset({"CONING", "CHANNELLING", "MULTILAYER", "INJECTOR_BREAKTHROUGH",
                          "CHANNELLING_OR_INJECTOR_BREAKTHROUGH"})


def reason_class(reason: str | None) -> str:
    if not reason:
        return "UNEXPLAINED"
    return _FMAP["reasons"].get(str(reason), "UNEXPLAINED")


def event_class(event_type: str, row_class: str | None = None) -> str:
    if isinstance(row_class, str) and row_class in FACTOR_CLASSES:
        return row_class
    return _FMAP["event_types"].get(str(event_type), "UNEXPLAINED")


@lru_cache(maxsize=1)
def _function_of_event_type() -> dict[str, str]:
    """``responsible_function`` per event type, read from the data (mode)."""
    ev = load_table("operations_events")
    if ev.empty or "responsible_function" not in ev.columns:
        return {}
    g = ev.dropna(subset=["responsible_function"]).groupby("event_type")["responsible_function"]
    return {k: str(v.mode().iloc[0]) for k, v in g}


# ------------------------------------------------------------------------------------------------
# result types
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class AttributionComponent:
    factor_class: str
    sub_factor: str
    bbl: float
    pct: float
    controllable: bool
    evidence_refs: list[str]
    days: int
    responsible_function: str | None = None


@dataclass(frozen=True)
class DeclineAttribution:
    scope: str                      # "WELL" | "FIELD" | "CLUSTER"
    well_id: WellId | None
    field: str | None
    cluster_id: str | None
    window_start: date
    window_end: date
    window_days: int
    baseline_bopd: float
    total_loss_bbl: float
    gross_loss_bbl: float
    components: list[AttributionComponent]
    gains: list[AttributionComponent]
    gains_bbl: float
    by_class: dict[str, dict]
    largest_class: str | None
    controllable_pct: float
    uncontrollable_pct: float
    subsurface_pct: float
    unexplained_pct: float
    reconciliation_error_pct: float
    flags: list[str]
    method_notes: list[str]
    wells: list[dict] = field(default_factory=list)
    wells_excluded: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------------------------------------
# per-well computation
# ------------------------------------------------------------------------------------------------
class _Acc:
    """Signed per-key accumulator: bbl, contributing days, evidence refs."""

    def __init__(self) -> None:
        self.bbl: dict[tuple[str, str], float] = defaultdict(float)
        self.days: dict[tuple[str, str], set] = defaultdict(set)
        self.refs: dict[tuple[str, str], set] = defaultdict(set)
        self.func: dict[tuple[str, str], str] = {}

    def add(self, key: tuple[str, str], bbl: float, day: date, ref: str | None = None,
            func: str | None = None) -> None:
        if bbl == 0.0:
            return
        self.bbl[key] += bbl
        self.days[key].add(day)
        if ref:
            self.refs[key].add(ref)
        if func and key not in self.func:
            self.func[key] = func


def _q0(daily: pd.DataFrame, ws: date) -> tuple[float | None, int]:
    for lookback in (30, 90):
        pre = daily[(daily["production_date"] >= ws - timedelta(days=lookback)) & (daily["production_date"] < ws)]
        pre = pre[(pre["is_producing"] == True) & pre["oil_rate_bopd"].notna()]  # noqa: E712
        if len(pre):
            rf = pre["runtime_fraction"].astype(float).fillna(1.0).clip(lower=0.05, upper=1.0)
            return float((pre["oil_rate_bopd"].astype(float) / rf).mean()), lookback
    return None, 0


def _wc_trend(daily: pd.DataFrame, ws: date, days: int, after: date | None = None):
    lo = ws - timedelta(days=days)
    if after is not None:
        lo = max(lo, after + timedelta(days=1))
    pre = daily[(daily["production_date"] >= lo) & (daily["production_date"] < ws)]
    pre = pre[(pre["is_producing"] == True) & pre["water_cut_pct"].notna()]  # noqa: E712
    if len(pre) < 10:
        return None
    x = np.array([(d - ws).days for d in pre["production_date"]], dtype=float)
    y = pre["water_cut_pct"].astype(float).to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _episodes(status: pd.DataFrame, as_of: date) -> list[dict]:
    if status.empty:
        return []
    s = status[status["start_date"] <= as_of].sort_values("start_date")
    out = []
    for r in s.itertuples(index=False):
        end = r.end_date if isinstance(r.end_date, date) else as_of
        out.append({"id": r.episode_id, "status": r.status, "start": r.start_date, "end": min(end, as_of),
                    "reason": r.reason_code if isinstance(r.reason_code, str) else None,
                    "workover_id": r.workover_id if isinstance(r.workover_id, str) else None,
                    "is_rigless": None if pd.isna(r.is_rigless) else bool(r.is_rigless)})
    return out


def _is_mechanical(ep: dict) -> bool:
    return ep["status"] != "PRODUCING" and ep["reason"] is not None and reason_class(ep["reason"]) not in (
        "EXTERNAL", "UNEXPLAINED")


def _sla_days(is_rigless: bool | None, mechanism: str | None) -> tuple[int, str]:
    if is_rigless is None and mechanism:
        from .candidate_ranking import ROUTING, _catalogue

        job = ROUTING.get(mechanism)
        cat = _catalogue()
        if job and job in cat.index:
            is_rigless = not bool(cat.loc[job, "requires_rig"])
    if is_rigless:
        return int(_SLA["rigless_job_days"]), "rigless"
    return int(_SLA["rig_job_days"]), "rig"


def _open_segment_label(well_id: WellId, as_of: date, notes: list[str]) -> tuple[str, str, str] | None:
    """(class, sub_factor, evidence) for the trailing open segment = Trigger C state (TC-005, then TC-002
    with the same confidence and water-cut-rise rules as TC-007), so attribution and triggers agree."""
    from .candidate_ranking import trigger_c_state

    tc = trigger_c_state(well_id, as_of)
    sig = tc.get("signature")
    if not sig:
        return None
    cls = "SUBSURFACE" if sig in _WATER_MECHS else reason_class(sig)
    return cls, sig, f"{tc.get('source')} {sig}"


def _reservoir_decline(well_id: WellId, as_of: date) -> bool:
    from .candidate_ranking import check_offsets

    off = check_offsets(well_id, as_of=as_of)
    return off.value is not None and getattr(off.value.verdict, "value", str(off.value.verdict)) == "RESERVOIR_DECLINE"


def _well_raw(well_id: WellId, as_of: date, window_days: int) -> dict:
    """Signed per-key contributions for one well (not yet split into components / gains)."""
    ws = as_of - timedelta(days=window_days - 1)
    notes: list[str] = []
    flags: list[str] = []
    daily = well_rows("daily_production", well_id)
    q0, lookback = _q0(daily, ws)
    if q0 is None:
        return {"error": "INSUFFICIENT_HISTORY",
                "message": f"{well_id}: no producing days in the 90 days before {ws.isoformat()}; no baseline q0."}
    if lookback != 30:
        notes.append(f"q0 from {lookback}-day pre-window lookback (well down for the 30 days before the window).")

    # E(t)
    fit = fit_decline_curve(well_id, as_of=as_of)
    tau = np.arange(window_days, dtype=float)
    if fit.status == ToolStatus.OK and fit.value is not None and fit.value.fit_origin_date is not None:
        f = fit.value
        tw = max(0.0, float((ws - f.fit_origin_date).days))
        base = float(arps_hyperbolic(np.array([tw]), 1.0, f.b, f.di_per_day)[0])
        E = q0 * arps_hyperbolic(tw + tau, 1.0, f.b, f.di_per_day) / max(base, 1e-9)
        notes.append(f"E(t) from TC-001 shape b={f.b}, Di={f.di_per_day}/d (fit {f.fit_quality.value}).")
    else:
        E = np.full(window_days, q0)
        flags.append("NATURAL_DECLINE_NOT_SEPARATED")
        notes.append(f"TC-001 fit {fit.status.value}: E(t) held flat at q0; decline is attributed via "
                     "productivity labels (TC-004/TC-005/TC-002).")

    days = [ws + timedelta(days=i) for i in range(window_days)]
    d = daily[(daily["production_date"] >= ws) & (daily["production_date"] <= as_of)].set_index("production_date")
    prod = np.array([bool(d.at[x, "is_producing"]) if x in d.index else False for x in days])

    def col(name: str) -> np.ndarray:
        if name not in d.columns:
            return np.full(window_days, np.nan)
        s = d[name].astype(float)
        return np.array([s.get(x, np.nan) for x in days], dtype=float)

    A = np.where(prod, np.nan_to_num(col("oil_rate_bopd"), nan=0.0), 0.0)
    rf = col("runtime_fraction")
    rf = np.where(prod, np.where(np.isnan(rf), 1.0, rf), 0.0).clip(0.0, 1.0)
    liq = np.nan_to_num(col("liquid_rate_blpd"), nan=0.0)
    wc = col("water_cut_pct")
    dt_reason = [d.at[x, "downtime_reason"] if (x in d.index and "downtime_reason" in d.columns
                                                and isinstance(d.at[x, "downtime_reason"], str)) else None
                 for x in days]

    natural = q0 - E
    downtime = E * (1.0 - rf)

    # events / episodes
    ev = well_rows("operations_events", well_id)
    ev = ev[(ev["start_date"] <= as_of) & (ev["end_date"] >= ws - timedelta(days=0))] if len(ev) else ev
    eps = _episodes(well_rows("well_status_history", well_id), as_of)
    wo = well_rows("workover_history", well_id)

    down_events = [r for r in ev.itertuples(index=False) if r.event_type not in SETPOINT_EVENTS
                   and r.event_type != "DEFERRED_MAINTENANCE"]
    dm_events = [r for r in ev.itertuples(index=False) if r.event_type == "DEFERRED_MAINTENANCE"]
    set_events = sorted([r for r in ev.itertuples(index=False) if r.event_type in SETPOINT_EVENTS
                         and r.start_date >= ws], key=lambda r: r.start_date)

    def episode_on(x: date) -> dict | None:
        for e in eps:
            if e["start"] <= x <= e["end"]:
                return e
        return None

    mech_eps = [e for e in eps if _is_mechanical(e)]
    # collapse chains of consecutive mechanical episodes (WAIT_ON_RIG -> WAIT_ON_MATERIAL -> WORKOVER)
    chains: list[list[dict]] = []
    for e in mech_eps:
        if chains and (e["start"] - chains[-1][-1]["end"]).days <= 1:
            chains[-1].append(e)
        else:
            chains.append([e])

    pmax = int(_FMAP["precursor_max_days"])
    label: list[tuple[str, str, str | None] | None] = [None] * window_days   # productivity label
    seg_of: list[int | None] = [None] * window_days                          # segment index for re-class
    segments: list[dict] = []
    prev_end: date | None = None
    for ch in chains:
        s = ch[0]["start"]
        reason = ch[0]["reason"]
        seg_start = max(s - timedelta(days=pmax), (prev_end + timedelta(days=1)) if prev_end else date.min)
        wo_id = next((e["workover_id"] for e in ch if e["workover_id"]), None)
        rigless = next((e["is_rigless"] for e in ch if e["is_rigless"] is not None), None)
        wo_start = next((e["start"] for e in ch if e["status"] == "UNDER_WORKOVER"), ch[-1]["end"] + timedelta(days=1))
        seg = {"start": seg_start, "end": s - timedelta(days=1), "chain_end": ch[-1]["end"], "wo_start": wo_start,
               "cls": reason_class(reason), "sub": reason, "ref": wo_id or ch[0]["id"], "rigless": rigless}
        segments.append(seg)
        for i, x in enumerate(days):
            if seg_start <= x < s and label[i] is None:
                label[i] = (seg["cls"], reason, seg["ref"])
                seg_of[i] = len(segments) - 1
        prev_end = ch[-1]["end"]

    # water term (3): WĈ = pre-window WC trend fitted only on points after the last workover before the
    # window (a workover steps WC), slope floored at 0 (no extrapolated WC fall), re-anchored to the
    # post-job WC level after any workover that completes inside the window.
    water = np.zeros(window_days)
    last_wo_before = max((c[-1]["end"] for c in chains if c[-1]["end"] < ws and any(
        e["status"] == "UNDER_WORKOVER" for e in c)), default=None)
    trend = _wc_trend(daily, ws, int(_FMAP["water_trend_days"]), after=last_wo_before)
    if trend is not None:
        slope, icpt = max(0.0, trend[0]), trend[1]
        wc_hat = icpt + slope * tau
        for c in chains:
            ce = c[-1]["end"]
            if ws <= ce < as_of and any(e["status"] == "UNDER_WORKOVER" for e in c):
                j0 = (ce - ws).days + 1
                post = [k for k in range(j0, window_days) if prod[k] and not np.isnan(wc[k])][:14]
                if post:
                    lvl = float(np.median(wc[post]))
                    wc_hat[j0:] = lvl + slope * (tau[j0:] - tau[post[0]])
        water = np.where(prod & ~np.isnan(wc), liq * np.maximum(0.0, np.nan_to_num(wc) - wc_hat) / 100.0, 0.0)
    else:
        notes.append("water-cut baseline unavailable (< 10 pre-window WC points since the last workover): "
                     "water term = 0.")
    productivity = rf * E - A - water

    open_start = (prev_end + timedelta(days=1)) if prev_end else date.min
    open_idx = [i for i, x in enumerate(days) if x >= open_start and label[i] is None]
    needs = [i for i in open_idx if prod[i] and abs(productivity[i]) > 0]
    if needs:
        # "is it the well or the reservoir?" first (TC-004), as in the v0.3.0 diagnostic order;
        # only a well-specific shortfall is then given a mechanism (Trigger C = TC-005 / TC-002).
        lab = (("SUBSURFACE", "RESERVOIR_DECLINE", "TC-004 RESERVOIR_DECLINE")
               if _reservoir_decline(well_id, as_of) else _open_segment_label(well_id, as_of, notes))
        if lab is not None:
            seg = {"start": max(open_start, ws), "end": as_of, "chain_end": as_of, "wo_start": as_of + timedelta(days=1),
                   "cls": lab[0], "sub": lab[1], "ref": lab[2], "rigless": None}
            segments.append(seg)
            for i in open_idx:
                label[i] = (lab[0], lab[1], lab[2])
                seg_of[i] = len(segments) - 1
    # setpoint events
    for r in set_events:
        nxt = next((c[0]["start"] for c in chains if c[0]["start"] > r.start_date), as_of + timedelta(days=1))
        for i, x in enumerate(days):
            if r.start_date <= x < nxt and label[i] is None:
                label[i] = (event_class(r.event_type, r.factor_class), r.event_type, r.event_id)
    # post-workover response: a job finished inside (or just before) the window, so q0 was measured on the
    # failing / down well; the open segment's departure from q0 is that job's response (usually a gain).
    if chains and prev_end is not None and prev_end >= ws - timedelta(days=30):
        last = chains[-1]
        wo_ep = next((e for e in last if e["status"] == "UNDER_WORKOVER"), None)
        if wo_ep is not None:
            rc = reason_class(last[0]["reason"])
            for i in open_idx:
                if label[i] is None:
                    label[i] = (rc, "POST_WORKOVER_RESPONSE", wo_ep["workover_id"] or wo_ep["id"])
    # deferred-maintenance events override productivity labels on the days they cover
    for r in dm_events:
        for i, x in enumerate(days):
            if r.start_date <= x <= r.end_date:
                label[i] = ("HUMAN_PROCESS", "DEFERRED_MAINTENANCE", r.event_id)
                seg_of[i] = None

    # deferred-maintenance re-class (SDD §7 row 5)
    ratio_thr = float(_SLA["detect_ratio"])
    persist = int(_SLA["detect_persistence_days"])
    deadline_of: dict[int, date] = {}
    for k, seg in enumerate(segments):
        if seg["cls"] not in ("EQUIPMENT", "OPERATIONAL"):
            continue
        run = 0
        detect: date | None = None
        for i, x in enumerate(days):
            if not (seg["start"] <= x <= seg["end"]) or not prod[i] or rf[i] <= 0:
                continue
            ratio = A[i] / max(rf[i] * E[i], 1e-9)
            run = run + 1 if ratio <= ratio_thr else 0
            if run >= persist:
                detect = x
                break
        if detect is None:
            # degradation may have started before the window: look back over pre-window days
            continue
        sla, kind = _sla_days(seg["rigless"], seg["sub"])
        deadline_of[k] = detect + timedelta(days=sla)
        notes.append(f"{seg['sub']}: degradation trigger {detect.isoformat()} (A/(rf·E) ≤ {ratio_thr} for "
                     f"{persist} d); {kind} SLA {sla} d → losses after {deadline_of[k].isoformat()} re-classed "
                     "HUMAN_PROCESS/DEFERRED_MAINTENANCE.")

    def dm_reclass(i: int, x: date) -> tuple[int, date] | None:
        for k, dl in deadline_of.items():
            seg = segments[k]
            if x > dl and seg["start"] <= x < seg["wo_start"]:
                return k, dl
        return None

    acc = _Acc()
    funcs = _function_of_event_type()
    for i, x in enumerate(days):
        acc.add(("SUBSURFACE", "NATURAL_DECLINE"), float(natural[i]), x, "TC-001" if "NATURAL_DECLINE_NOT_SEPARATED" not in flags else None)
        if water[i]:
            wl = label[i]
            if wl is not None and wl[1] in _WATER_MECHS:
                acc.add(("SUBSURFACE", wl[1]), float(water[i]), x, wl[2])
            else:
                acc.add(("SUBSURFACE", "WATER_ENCROACHMENT"), float(water[i]), x, "WC trend")
        # downtime
        if downtime[i] > 0:
            cands = [r for r in down_events if r.start_date <= x <= r.end_date]
            key = ref = func = None
            if cands:
                r = min(cands, key=lambda r: r.start_date)
                key = (event_class(r.event_type, r.factor_class), r.event_type)
                ref = r.event_id
                func = r.responsible_function if isinstance(r.responsible_function, str) else None
            elif dt_reason[i]:
                key, ref = (reason_class(dt_reason[i]), dt_reason[i]), None
                ep = episode_on(x)
                ref = ep["workover_id"] or ep["id"] if ep else None
            else:
                ep = episode_on(x)
                if ep and ep["status"] != "PRODUCING" and ep["reason"]:
                    key, ref = (reason_class(ep["reason"]), ep["reason"]), ep["workover_id"] or ep["id"]
                elif label[i] is not None:
                    key, ref = (label[i][0], label[i][1]), label[i][2]
                else:
                    key = ("UNEXPLAINED", "UNRECORDED_DOWNTIME")
            ep = episode_on(x)
            dm = dm_reclass(i, x)
            if dm and key[0] not in ("HUMAN_PROCESS", "EXTERNAL") and not (ep and ep["status"] == "UNDER_WORKOVER"):
                key, ref, func = ("HUMAN_PROCESS", "DEFERRED_MAINTENANCE"), segments[dm[0]]["ref"], funcs.get("DEFERRED_MAINTENANCE")
            if key[0] == "HUMAN_PROCESS" and func is None:
                func = funcs.get(key[1])
            acc.add(key, float(downtime[i]), x, ref, func)
        # productivity
        if prod[i] and productivity[i] != 0:
            lab = label[i]
            if lab is None:
                key, ref = ("UNEXPLAINED", "UNEXPLAINED"), None
            else:
                key, ref = (lab[0], lab[1]), lab[2]
            func = funcs.get(key[1]) if key[0] == "HUMAN_PROCESS" else None
            dm = dm_reclass(i, x) if seg_of[i] is not None else None
            if dm and key[0] in ("EQUIPMENT", "OPERATIONAL"):
                key, ref, func = ("HUMAN_PROCESS", "DEFERRED_MAINTENANCE"), segments[dm[0]]["ref"], funcs.get("DEFERRED_MAINTENANCE")
            acc.add(key, float(productivity[i]), x, ref, func)

    total = float(np.sum(q0 - A))
    return {"q0": q0, "total": total, "acc": acc, "flags": flags, "notes": notes, "ws": ws,
            "fit_status": fit.status.value}


def _components(acc_items: dict[tuple[str, str], dict], total: float | None = None) -> tuple[list[AttributionComponent], list[AttributionComponent], float, float]:
    pos = {k: v for k, v in acc_items.items() if v["bbl"] > 1e-9}
    neg = {k: v for k, v in acc_items.items() if v["bbl"] < -1e-9}
    gross = sum(v["bbl"] for v in pos.values())
    gains = -sum(v["bbl"] for v in neg.values())

    def mk(k, v, denom):
        return AttributionComponent(
            factor_class=k[0], sub_factor=k[1], bbl=round(abs(v["bbl"]), 1),
            pct=round(100.0 * abs(v["bbl"]) / denom, 1) if denom > 0 else 0.0,
            controllable=k[0] in CONTROLLABLE, evidence_refs=sorted(v["refs"])[:12], days=int(v["days"]),
            responsible_function=v.get("func") if k[0] == "HUMAN_PROCESS" else None)

    comps = sorted((mk(k, v, gross) for k, v in pos.items()), key=lambda c: -c.bbl)
    gl = sorted((mk(k, v, gains) for k, v in neg.items()), key=lambda c: -c.bbl)
    if comps and total is not None:
        # put the 1-dp rounding residual on the largest bar so Σ bars − gains == total exactly as displayed
        resid = round(round(total, 1) - (sum(c.bbl for c in comps) - sum(g.bbl for g in gl)), 1)
        if resid:
            comps[0] = AttributionComponent(**{**comps[0].__dict__, "bbl": round(comps[0].bbl + resid, 1)})
    return comps, gl, gross, gains


def _summarise(scope, well_id, fld, cluster_id, ws, as_of, window_days, baseline, total, items, flags, notes,
               wells=None, excluded=None) -> tuple[DeclineAttribution, ToolStatus, str]:
    comps, gl, gross, gains = _components(items, total)
    by_class: dict[str, dict] = {}
    for c in FACTOR_CLASSES:
        b = sum(x.bbl for x in comps if x.factor_class == c)
        if b > 0:
            by_class[c] = {"bbl": round(b, 1), "pct": round(100.0 * b / gross, 1) if gross > 0 else 0.0,
                           "controllable": c in CONTROLLABLE}
    largest = max(by_class, key=lambda c: by_class[c]["bbl"]) if by_class else None
    raw_pos = {k: v["bbl"] for k, v in items.items() if v["bbl"] > 1e-9}
    gross_raw = sum(raw_pos.values())

    def share(pred) -> float:
        return round(100.0 * sum(b for k, b in raw_pos.items() if pred(k[0])) / gross_raw, 1) if gross_raw > 0 else 0.0

    controllable_pct = share(lambda c: c in CONTROLLABLE)
    subsurface_pct = share(lambda c: c == "SUBSURFACE")
    unexpl_net = sum(v["bbl"] for k, v in items.items() if k[0].replace("__GAIN__", "") == "UNEXPLAINED")
    unexplained_pct = round(100.0 * abs(unexpl_net) / gross_raw, 1) if gross_raw > 0 else 0.0
    recon = gross_raw - (-sum(v["bbl"] for v in items.values() if v["bbl"] < -1e-9)) - total
    recon_pct = round(100.0 * abs(recon) / max(abs(total), 1e-6), 4)
    flags = list(flags)
    nf = _FMAP["no_action_flag"]
    if subsurface_pct >= nf["min_subsurface_pct"] and controllable_pct <= nf["max_controllable_pct"]:
        flags.append(NO_ACTION_FLAG)
    status = ToolStatus.OK
    if unexplained_pct > float(_FMAP["unexplained_low_confidence_pct"]):
        status = ToolStatus.LOW_CONFIDENCE
        flags.append("UNEXPLAINED_ABOVE_15PCT")
    if total <= 0:
        flags.append("NO_NET_LOSS")
    val = DeclineAttribution(
        scope=scope, well_id=well_id, field=fld, cluster_id=cluster_id, window_start=ws, window_end=as_of,
        window_days=window_days, baseline_bopd=round(baseline, 1), total_loss_bbl=round(total, 1),
        gross_loss_bbl=round(gross_raw, 1), components=comps, gains=gl, gains_bbl=round(gains, 1),
        by_class=by_class, largest_class=largest, controllable_pct=controllable_pct,
        uncontrollable_pct=round(100.0 - controllable_pct - share(lambda c: c == "UNEXPLAINED"), 1) if gross_raw > 0 else 0.0,
        subsurface_pct=subsurface_pct, unexplained_pct=unexplained_pct, reconciliation_error_pct=recon_pct,
        flags=sorted(set(flags)), method_notes=notes, wells=wells or [], wells_excluded=excluded or [])
    subject = well_id or (f"{fld}/{cluster_id}" if cluster_id else fld)
    msg = (f"{subject}: {round(total):,} bbl lost over {window_days} d vs baseline {baseline:.1f} BOPD; "
           f"largest class {largest} ({by_class.get(largest, {}).get('pct', 0)}%); controllable {controllable_pct}%"
           f", unexplained {unexplained_pct}%.")
    return val, status, msg


def _items_from_acc(acc: _Acc) -> dict[tuple[str, str], dict]:
    return {k: {"bbl": acc.bbl[k], "days": len(acc.days[k]), "refs": set(acc.refs[k]), "func": acc.func.get(k)}
            for k in acc.bbl}


@lru_cache(maxsize=4096)
def _well_cached(well_id: WellId, as_of: date, window_days: int) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "window_days": window_days}
    wm = well_master_row(well_id)
    if wm is None:
        return unavailable("TC-019", params, t0, ["well_id"], f"Well {well_id} not found in well_master.")
    raw = _well_raw(well_id, as_of, window_days)
    if "error" in raw:
        return unavailable("TC-019", params, t0, ["daily_production.oil_rate_bopd"], raw["message"],
                           status=ToolStatus.INSUFFICIENT_HISTORY)
    val, status, msg = _summarise("WELL", well_id, wm.get("field"), wm.get("cluster_id"), raw["ws"], as_of,
                                  window_days, raw["q0"], raw["total"], _items_from_acc(raw["acc"]),
                                  raw["flags"], raw["notes"])
    return ToolResult(status=status, value=val, missing_fields=[], message=msg,
                      provenance=build_provenance("TC-019", params, t0, decline_fit_status=raw["fit_status"]))


@lru_cache(maxsize=64)
def _rollup_cached(fld: str, cluster_id: str | None, as_of: date, window_days: int) -> ToolResult:
    t0 = time.perf_counter()
    params = {"field": fld, "cluster_id": cluster_id, "as_of": str(as_of), "window_days": window_days}
    wm = load_table("well_master")
    ids = field_well_ids(fld)
    if cluster_id:
        ids = sorted(wm[(wm["field"] == fld) & (wm["cluster_id"] == cluster_id)]["well_id"].tolist())
        if not ids:
            return unavailable("TC-019", params, t0, ["cluster_id"], f"Cluster {cluster_id} not found in {fld}.")
    items: dict[tuple[str, str], dict] = {}
    gains_items: dict[tuple[str, str], dict] = {}
    total = baseline = 0.0
    wells, excluded = [], []
    for wid in ids:
        r = _well_cached(wid, as_of, window_days)
        if r.value is None:
            excluded.append({"well_id": wid, "status": r.status.value, "reason": r.message})
            continue
        v: DeclineAttribution = r.value
        total += v.total_loss_bbl
        baseline += v.baseline_bopd
        wells.append({"well_id": wid, "total_loss_bbl": v.total_loss_bbl, "largest_class": v.largest_class,
                      "controllable_pct": v.controllable_pct, "status": r.status.value})
        for bucket, comps in ((items, v.components), (gains_items, v.gains)):
            for c in comps:
                k = (c.factor_class, c.sub_factor)
                e = bucket.setdefault(k, {"bbl": 0.0, "days": 0, "refs": set(), "func": c.responsible_function})
                e["bbl"] += c.bbl
                e["days"] += c.days
                e["refs"].add(wid)
    # components and gains are summed separately (never netted across wells)
    merged: dict[tuple[str, str], dict] = {}
    for k, e in items.items():
        merged[k] = e
    for k, e in gains_items.items():
        merged[("__GAIN__" + k[0], k[1])] = {**e, "bbl": -e["bbl"]}
    val, status, msg = _summarise("CLUSTER" if cluster_id else "FIELD", None, fld, cluster_id,
                                  as_of - timedelta(days=window_days - 1), as_of, window_days, baseline, total,
                                  merged, [], [f"Rollup = sum over {len(wells)} wells' components and gains."],
                                  wells=sorted(wells, key=lambda w: -w["total_loss_bbl"]), excluded=excluded)
    # restore real class names on gains
    fixed = [AttributionComponent(**{**g.__dict__, "factor_class": g.factor_class.replace("__GAIN__", ""),
                                     "controllable": g.factor_class.replace("__GAIN__", "") in CONTROLLABLE})
             for g in val.gains]
    val = DeclineAttribution(**{**val.__dict__, "gains": fixed})
    return ToolResult(status=status, value=val, missing_fields=[], message=msg,
                      provenance=build_provenance("TC-019", params, t0, wells_used=len(wells),
                                                  wells_excluded=len(excluded)))


def attribute_decline(well_id: WellId | None = None, field: str | None = None, cluster_id: str | None = None,
                      as_of: date | None = None, window_days: int = 180) -> ToolResult:
    """TC-019. Well-level when ``well_id`` is given, else field (or cluster) rollup = sum over wells."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    window_days = int(window_days)
    params = {"well_id": well_id, "field": field, "cluster_id": cluster_id, "as_of": str(as_of),
              "window_days": window_days}
    if not 7 <= window_days <= 730:
        return unavailable("TC-019", params, t0, ["window_days"], "window_days must be between 7 and 730.")
    if well_id:
        return _well_cached(str(well_id).strip().upper(), as_of, window_days)
    if not field:
        return unavailable("TC-019", params, t0, ["well_id", "field"], "Provide a well_id or a field.")
    fld = resolve_field(field)
    if fld is None:
        return unavailable("TC-019", params, t0, ["field"], f"Unknown field '{field}'.")
    return _rollup_cached(fld, cluster_id or None, as_of, window_days)


register_cache(_well_cached.cache_clear)
register_cache(_rollup_cached.cache_clear)
register_cache(_function_of_event_type.cache_clear)
