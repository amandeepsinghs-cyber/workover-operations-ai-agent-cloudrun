"""Stage Q · Gate Q leakage test: TC-021 features never use data dated at or after the snapshot.

Three behavioural checks on real training snapshots (``s = start_date − 7 d``):

1. **Truncation invariance** — deleting every row dated ``>= s`` from every dated table leaves the
   features unchanged (including the labelled job itself, which starts at ``s + 7``).
2. **Future perturbation invariance** — scrambling the numbers of every row dated ``>= s`` and appending a
   fake future job leaves the features unchanged.
3. **Decision-column invariance** — scrambling the columns that encode the diagnosis/decision
   (``failure_code``, ``job_code``, ``catalogue_job_code``, ``trigger_ref``, ``is_prepend``, ``data_source``,
   failure-coded ``downtime_reason`` values, WAIT/DEFERRED event types, ``well_master.status``) leaves the
   features unchanged. Plus: only the whitelisted tables are read.
"""

from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics.model.features import (
    DATED_TABLES,
    EXTERNAL_DOWN,
    FEATURE_NAMES,
    STATIC_TABLES,
    build_features,
    default_source,
)
from app.analytics.tools.common import load_table

FIXED = ["LKW-047", "LKM-023", "LKM-061", "GK-129", "LKW-112", "LKM-090"]


def _snapshots(n_random: int = 24) -> list[tuple[str, object]]:
    wo = load_table("workover_history")
    wo = wo[~wo["is_censored"].astype(bool) & wo["intervention_class"].notna()].copy()
    wo["start_date"] = pd.to_datetime(wo["start_date"]).dt.date
    wo = wo[wo["start_date"] >= pd.Timestamp("2022-03-01").date()]
    picks = []
    for w in FIXED:
        g = wo[wo["well_id"] == w].sort_values("start_date")
        if len(g):
            picks.append(g.iloc[-1])
    rnd = wo.sample(n=n_random, random_state=7)
    picks.extend(r for _, r in rnd.iterrows())
    return [(str(r["well_id"]), r["start_date"] - timedelta(days=7)) for r in picks]


SNAPS = _snapshots()


def _dates(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_datetime(df[col], errors="coerce").dt.date


def _same(a: dict, b: dict) -> list[str]:
    bad = []
    for k in set(a) | set(b):
        x, y = a.get(k, math.nan), b.get(k, math.nan)
        if (isinstance(x, float) and math.isnan(x)) and (isinstance(y, float) and math.isnan(y)):
            continue
        if x != y and not (abs(float(x) - float(y)) <= 1e-12):
            bad.append(f"{k}: {x} != {y}")
    return bad


def _truncating_source(s):
    def src(table, well_id):
        df = default_source(table, well_id)
        col = DATED_TABLES.get(table)
        if col is None or df.empty:
            return df
        d = _dates(df, col)
        return df[(d.notna() & (d < s)).to_numpy()]
    return src


def _perturbing_source(s, rng):
    def src(table, well_id):
        df = default_source(table, well_id).copy()
        col = DATED_TABLES.get(table)
        if col is None or df.empty:
            return df
        fut = (_dates(df, col).isna() | (_dates(df, col) >= s)).to_numpy()
        for c in df.columns:
            if c in (col, "well_id", "field", "cluster_id") or not fut.any():
                continue
            if pd.api.types.is_float_dtype(df[c]):
                df.loc[fut, c] = rng.normal(0, 1000, fut.sum())
        if table == "workover_history":
            fake = df.iloc[-1:].copy()
            fake["start_date"] = s
            fake["end_date"] = s + timedelta(days=3)
            fake["intervention_class"] = "IC-06"
            fake["is_censored"] = False
            df = pd.concat([df, fake], ignore_index=True)
        if table == "daily_production" and fut.any():
            df.loc[fut, "is_producing"] = True
        return df
    return src


def _decision_scrambling_source(rng):
    codes = ["PUMP_WEAR", "ROD_PART", "SAND", "WAX", "TUBING_LEAK", "WATER_CHANNELLING", "OTHER"]

    def src(table, well_id):
        df = default_source(table, well_id).copy()
        if df.empty:
            return df
        for c in ("failure_code", "job_code", "catalogue_job_code", "trigger_ref", "data_source", "workover_id",
                  "report_doc_id", "rig_id"):
            if c in df.columns:
                df[c] = rng.permutation(df[c].to_numpy())
        if "is_prepend" in df.columns:
            df["is_prepend"] = ~df["is_prepend"].astype(bool)
        if table == "daily_production":
            m = df["downtime_reason"].notna() & ~df["downtime_reason"].isin(EXTERNAL_DOWN)
            df.loc[m, "downtime_reason"] = rng.choice(codes, m.sum())
        if table == "operations_events":
            m = df["event_type"].isin(["WAIT_ON_RIG", "WAIT_ON_MATERIAL", "PERMIT_DELAY", "CREW_UNAVAILABLE",
                                       "DEFERRED_MAINTENANCE"])
            df.loc[m, "event_type"] = rng.choice(["WAIT_ON_RIG", "DEFERRED_MAINTENANCE"], m.sum())
        if table == "well_master":
            df["status"] = "IDLE"
        return df
    return src


@pytest.mark.parametrize("well_id,s", SNAPS)
def test_truncation_invariance(well_id, s):
    full = build_features(well_id, s)
    cut = build_features(well_id, s, source=_truncating_source(s))
    assert full.status == cut.status, (well_id, s, full.message, cut.message)
    assert full.anchor == cut.anchor
    assert not _same(full.values, cut.values), _same(full.values, cut.values)[:5]


@pytest.mark.parametrize("well_id,s", SNAPS[:12])
def test_future_perturbation_invariance(well_id, s):
    rng = np.random.default_rng(11)
    full = build_features(well_id, s)
    pert = build_features(well_id, s, source=_perturbing_source(s, rng))
    assert full.status == pert.status
    assert not _same(full.values, pert.values), _same(full.values, pert.values)[:5]


@pytest.mark.parametrize("well_id,s", SNAPS[:12])
def test_decision_columns_unused(well_id, s):
    rng = np.random.default_rng(5)
    full = build_features(well_id, s)
    scr = build_features(well_id, s, source=_decision_scrambling_source(rng))
    assert full.status == scr.status
    assert not _same(full.values, scr.values), _same(full.values, scr.values)[:5]


def test_only_whitelisted_tables_are_read():
    seen: set[str] = set()

    def spy(table, well_id):
        seen.add(table)
        return default_source(table, well_id)

    for w, s in SNAPS[:6]:
        build_features(w, s, source=spy)
    assert seen <= set(DATED_TABLES) | set(STATIC_TABLES), seen
    assert "well_status_history" not in seen and "tubing_string" not in seen


def test_snapshots_have_full_schema_and_reach_ok():
    ok = 0
    for w, s in SNAPS:
        fr = build_features(w, s)
        if fr.status == "OK":
            ok += 1
            assert fr.anchor < s
            assert set(fr.values) <= set(FEATURE_NAMES), set(fr.values) - set(FEATURE_NAMES)
    assert ok >= len(SNAPS) * 0.8


def test_feature_groups_cover_construction_and_history():
    """Gate Q item: features include casing, tubing, perforations and prior-job history (verbatim §1)."""
    for f in ("prod_casing_od_in", "tubing_size_in", "perf_n_open", "perf_n_squeezed", "cement_top_to_perf_m"):
        assert f in FEATURE_NAMES
    for f in ("prior_n_IC-06", "last_is_IC-07", "days_since_last_job", "last_run_life_days", "failed_jobs_24m"):
        assert f in FEATURE_NAMES
