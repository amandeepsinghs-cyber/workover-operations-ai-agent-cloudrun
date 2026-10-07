"""TC-020 ``classify_well_health`` — four-bucket well-health screen (SDD §6.3, F-02).

Replaces the hard-coded ``["healthy"]*32 + ["warning"]*12 + ["failed"]*6`` status (W-2) and the
Stage N interim rule (``INTERIM_N1``). Evaluated at ``AS_OF`` for **every** well of the field:

| bucket            | rule                                                                              |
|-------------------|-----------------------------------------------------------------------------------|
| ``NOT_PRODUCING`` | open ``well_status_history`` episode ≠ ``PRODUCING`` (reason_code + recoverable)  |
| ``UNDERPERFORMING``| TC-001 residual ≤ −20 % on each of the last 7 producing days (Trigger A rules:   |
|                   | fit not LOW, residual fresh, no choke change in the window)                       |
| ``AT_RISK``       | not above, and Trigger B, C or D fired (TC-007)                                   |
| ``PRODUCING_OK``  | otherwise                                                                         |

``recoverable = False`` when TC-004 says ``RESERVOIR_DECLINE`` or the well is plugged & abandoned.
"Sick or lost production" = ``AT_RISK + UNDERPERFORMING``. Thresholds: ``config/triggers.yaml``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

from app import settings

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

BUCKETS = ("PRODUCING_OK", "AT_RISK", "UNDERPERFORMING", "NOT_PRODUCING")
HEALTH_RULE = "TC-020"
_CFG = load_yaml("triggers.yaml")
_UNDER_PCT = float(_CFG.get("health", {}).get("underperforming_pct", -20.0))
_UNDER_DAYS = int(_CFG.get("health", {}).get("persistence_days", 7))
_UNRECOVERABLE_REASONS = frozenset({"PLUGGED_ABANDONED"})


@dataclass(frozen=True)
class WellHealth:
    well_id: WellId
    bucket: str
    reason: str
    reason_code: str | None
    recoverable: bool | None
    cluster_id: str | None
    since: date | None = None
    triggers: dict = field(default_factory=dict)


@dataclass(frozen=True)
class HealthBuckets:
    field: str
    cluster_id: str | None
    as_of: date
    counts: dict[str, int]
    sick_or_lost_count: int
    total_wells: int
    wells: list[WellHealth]
    rule: str = HEALTH_RULE


def _open_episode(well_id: WellId, as_of: date) -> dict | None:
    s = well_rows("well_status_history", well_id)
    if s.empty:
        return None
    cur = s[(s["start_date"] <= as_of) & (s["end_date"].isna() | (s["end_date"] >= as_of))]
    if cur.empty:
        return None
    r = cur.sort_values("start_date").iloc[-1]
    return {"status": r["status"], "reason_code": r["reason_code"] if isinstance(r["reason_code"], str) else None,
            "start": r["start_date"], "episode_id": r["episode_id"]}


def _reservoir_decline(well_id: WellId, as_of: date) -> bool:
    from .candidate_ranking import check_offsets

    off = check_offsets(well_id, as_of=as_of)
    return off.value is not None and getattr(off.value.verdict, "value", str(off.value.verdict)) == "RESERVOIR_DECLINE"


def _classify(well_id: WellId, as_of: date, scan: dict) -> WellHealth:
    from .candidate_ranking import _trigger_b, trigger_a_state, trigger_c_state

    wm = well_master_row(well_id) or {}
    cl = wm.get("cluster_id")
    ep = _open_episode(well_id, as_of)
    if ep is not None and ep["status"] != "PRODUCING":
        rc = ep["reason_code"]
        recoverable = not (rc in _UNRECOVERABLE_REASONS or wm.get("status") in ("PLUGGED_ABANDONED", "ABANDONED"))
        if recoverable and _reservoir_decline(well_id, as_of):
            recoverable = False
        days = (as_of - ep["start"]).days + 1
        return WellHealth(well_id, "NOT_PRODUCING", f"{ep['status']} ({rc or 'no reason recorded'}) for {days} d "
                          f"since {ep['start'].isoformat()}", rc or ep["status"], recoverable, cl, ep["start"],
                          {"episode_id": ep["episode_id"]})
    if ep is None:
        return WellHealth(well_id, "NOT_PRODUCING", "no open status episode at as_of", "NO_STATUS", None, cl)

    ta = trigger_a_state(well_id, as_of)
    worst = ta.get("max_last7_pct")
    choke = "choke" in str(ta.get("reason") or "")
    if worst is not None and worst <= _UNDER_PCT and not choke:
        return WellHealth(well_id, "UNDERPERFORMING",
                          f"TC-001 residual ≤ {_UNDER_PCT:.0f}% on each of the last {_UNDER_DAYS} producing days "
                          f"(best {worst:+.1f}%, latest {ta.get('residual_pct'):+.1f}%)", "TRIGGER_A", True, cl,
                          triggers={"a_tier": ta.get("tier"), "a_max_last7_pct": worst})

    tr = scan.get(well_id)
    if tr is not None:
        b, c, dd = tr.trigger_b, tr.trigger_c, tr.trigger_d
        ev = {"b_days_since": tr.trigger_b_days_since, "b_p50_days": tr.trigger_b_p50_days,
              "d_ettf_days": tr.trigger_d_ettf_days}
    else:  # well not in the ACTIVE scan population: evaluate B and C directly (D needs the field hazard set)
        tb = _trigger_b(well_id, as_of)
        b, c, dd = bool(tb["fired"]), trigger_c_state(well_id, as_of)["signature"], False
        ev = {"b_days_since": tb["days_since"], "b_p50_days": tb["p50_days"], "d_ettf_days": None}
    if b or c or dd:
        parts = []
        if b:
            parts.append(f"Trigger B: {ev['b_days_since']:.0f} d since last job > p50 run life {ev['b_p50_days']:.0f} d")
        if c:
            parts.append(f"Trigger C: {c} signature")
        if dd:
            parts.append(f"Trigger D: failure hazard ≥ field P90 (ETTF {ev['d_ettf_days']:.0f} d)" if ev["d_ettf_days"]
                         else "Trigger D: failure hazard ≥ field P90")
        code = "TRIGGER_" + "".join(x for x, f in (("B", b), ("C", c), ("D", dd)) if f)
        return WellHealth(well_id, "AT_RISK", "; ".join(parts), code, True, cl,
                          triggers={"b": bool(b), "c": c, "d": bool(dd), **ev})
    res = ta.get("residual_pct")
    why = f"TC-001 residual {res:+.1f}%" if res is not None and ta.get("fit_status") != "LOW_CONFIDENCE" else (
        ta.get("reason") or "no decline fit")
    return WellHealth(well_id, "PRODUCING_OK", f"no trigger fired; {why}", None, True, cl)


@lru_cache(maxsize=64)
def _field_health(fld: str, as_of: date) -> tuple[WellHealth, ...]:
    from .candidate_ranking import _scan_field

    scan = {t.well_id: t for t in _scan_field(fld, as_of)}
    return tuple(_classify(w, as_of, scan) for w in field_well_ids(fld))


def classify_well_health(field: str, as_of: date | None = None, cluster_id: str | None = None) -> ToolResult:
    """TC-020. Every well of ``field`` (optionally one cluster) in exactly one of the four buckets."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    params = {"field": field, "cluster_id": cluster_id, "as_of": str(as_of)}
    fld = resolve_field(field or "")
    if fld is None:
        return unavailable("TC-020", params, t0, ["field"], f"Unknown field '{field}'.")
    wells = list(_field_health(fld, as_of))
    if cluster_id:
        wells = [w for w in wells if w.cluster_id == cluster_id]
        if not wells:
            return unavailable("TC-020", params, t0, ["cluster_id"], f"Cluster {cluster_id} not found in {fld}.")
    counts = {b: sum(1 for w in wells if w.bucket == b) for b in BUCKETS}
    val = HealthBuckets(field=fld, cluster_id=cluster_id or None, as_of=as_of, counts=counts,
                        sick_or_lost_count=counts["AT_RISK"] + counts["UNDERPERFORMING"], total_wells=len(wells),
                        wells=wells)
    scope = f"{fld}/{cluster_id}" if cluster_id else fld
    msg = (f"{scope}: {len(wells)} wells — {counts['PRODUCING_OK']} producing OK, {counts['AT_RISK']} at risk, "
           f"{counts['UNDERPERFORMING']} underperforming, {counts['NOT_PRODUCING']} not producing.")
    return ToolResult(ToolStatus.OK, val, [], msg, build_provenance("TC-020", params, t0, rule=HEALTH_RULE))


def well_health(well_id: WellId, as_of: date | None = None) -> WellHealth | None:
    """Bucket of one well (looked up from its field's cached screen)."""
    as_of = as_of or settings.AS_OF
    wm = well_master_row(well_id)
    if wm is None:
        return None
    for w in _field_health(wm["field"], as_of):
        if w.well_id == well_id:
            return w
    return None


def all_fields_counts(as_of: date | None = None) -> dict[str, int]:
    """Counts summed over every field in ``well_master`` (default view of ``/api/wells/kpis``)."""
    as_of = as_of or settings.AS_OF
    out = {b: 0 for b in BUCKETS}
    for fld in sorted(load_table("well_master")["field"].unique()):
        for w in _field_health(fld, as_of):
            out[w.bucket] += 1
    return out


register_cache(_field_health.cache_clear)
