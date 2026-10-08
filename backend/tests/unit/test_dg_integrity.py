"""Unit tests for Stage DG integrity generator (WH-14).

Covers:
- 100% coverage of well_master for wellhead_rating across all 3 fields (412 wells).
- Rating class is smallest API class in [2000, 3000, 5000, 10000] >= 1.5 x field max THP psi.
- xmas_tree_rating_psi matches wellhead_class_psi.
- last_service_date is <= AS_OF (2026-09-23).
- Barrier test dates strictly within (last WO end, AS_OF].
- next_due = test_date + 180 days.
- SSSV tested only on wells with gas-lift or flowing lift type.
- PACKER tested only on wells with a PACKER component in tubing_string.
- MASTER_VALVE, WING_VALVE, ANNULUS standard.
- FAIL result strictly restricted to wells with CASING_LEAK or TUBING_LEAK history.
- Overall FAIL rate <= 5%.
- test_pressure_kgcm2 = 1.1 x max THP or CHP, rounded to 1 decimal.
- Determinism across multiple runs with fixed seed.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics.generator.dg import integrity
from app.analytics.generator.dg.common import AS_OF, FIELDS, finalize, load_field


@pytest.fixture(scope="module")
def field_contexts():
    """Load FieldContext for all 3 fields once for tests."""
    return {f: load_field(f) for f in FIELDS}


@pytest.fixture(scope="module")
def generated_tables(field_contexts):
    """Generate integrity tables for all 3 fields."""
    return {f: integrity.generate(ctx) for f, ctx in field_contexts.items()}


# ============================================================================
# wellhead_rating tests (WH-14)
# ============================================================================


def test_api_classes_exported():
    """API pressure classes must match standard API 6A classes."""
    assert hasattr(integrity, "API_PRESSURE_CLASSES")
    assert integrity.API_PRESSURE_CLASSES == (2000, 3000, 5000, 10000)


@pytest.mark.parametrize("field_name", FIELDS)
def test_wellhead_rating_coverage_and_schema(field_name, field_contexts, generated_tables):
    """Coverage must be 100% of well_master (one row per well, no duplicates)."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master")
    df = generated_tables[field_name]["wellhead_rating"]

    expected_cols = [
        "well_id",
        "field",
        "cluster_id",
        "wellhead_class_psi",
        "xmas_tree_rating_psi",
        "last_service_date",
    ]
    assert list(df.columns) == expected_cols

    # Exactly 1 row per well in well_master
    assert len(df) == len(wm)
    assert df["well_id"].nunique() == len(wm)
    assert set(df["well_id"]) == set(wm["well_id"])

    # Cluster ID and field match well_master
    wm_clusters = wm.set_index("well_id")["cluster_id"].to_dict()
    for _, row in df.iterrows():
        wid = row["well_id"]
        assert row["cluster_id"] == wm_clusters[wid]
        assert row["field"].lower() == field_name.lower()


def test_wellhead_rating_total_well_count(generated_tables):
    """Total wells across all three fields must be 412 (142 + 160 + 110)."""
    total = sum(len(generated_tables[f]["wellhead_rating"]) for f in FIELDS)
    assert total == 412
    assert len(generated_tables["geleki"]["wellhead_rating"]) == 142
    assert len(generated_tables["lakwa"]["wellhead_rating"]) == 160
    assert len(generated_tables["lakhmani"]["wellhead_rating"]) == 110


@pytest.mark.parametrize("field_name", FIELDS)
def test_wellhead_rating_rules(field_name, field_contexts, generated_tables):
    """Check rating calculation: >= 1.5 x field max THP, API class, and xmas_tree match."""
    ctx = field_contexts[field_name]
    wt = ctx.t("well_tests")
    df = generated_tables[field_name]["wellhead_rating"]

    # Compute expected field max THP in psi
    valid_thp = wt["thp_kgcm2"].dropna()
    max_thp_kgcm2 = float(valid_thp.max()) if not valid_thp.empty else 40.0
    field_max_thp_psi = max_thp_kgcm2 * 14.2233
    required_min_psi = 1.5 * field_max_thp_psi

    api_classes = [2000, 3000, 5000, 10000]
    expected_class = next(c for c in api_classes if c >= required_min_psi)

    for _, row in df.iterrows():
        wh_class = row["wellhead_class_psi"]
        xt_rating = row["xmas_tree_rating_psi"]
        svc_date = row["last_service_date"]

        assert wh_class in api_classes
        assert wh_class >= required_min_psi
        assert wh_class == expected_class
        assert xt_rating == wh_class
        assert svc_date <= AS_OF


# ============================================================================
# barrier_tests tests (WH-14)
# ============================================================================


@pytest.mark.parametrize("field_name", FIELDS)
def test_barrier_tests_schema(field_name, generated_tables):
    """barrier_tests columns must match the required specification."""
    df = generated_tables[field_name]["barrier_tests"]
    expected_cols = [
        "well_id",
        "field",
        "cluster_id",
        "test_id",
        "test_date",
        "barrier",
        "result",
        "test_pressure_kgcm2",
        "next_due",
    ]
    assert list(df.columns) == expected_cols


@pytest.mark.parametrize("field_name", FIELDS)
def test_barrier_tests_dates_within_range(field_name, field_contexts, generated_tables):
    """Barrier test dates must fall strictly in (last WO end, AS_OF], next_due = test_date + 180."""
    ctx = field_contexts[field_name]
    wo = ctx.t("workover_history")
    wm = ctx.t("well_master")
    df = generated_tables[field_name]["barrier_tests"]

    if df.empty:
        return

    # Map each well to its base date
    last_wo_dates: dict[str, date] = {}
    if not wo.empty and "well_id" in wo.columns:
        date_col = "end_date" if "end_date" in wo.columns else "start_date"
        for _, job in wo.iterrows():
            wid = str(job["well_id"])
            d = integrity._to_date(job.get(date_col))
            if d is None:
                d = integrity._to_date(job.get("start_date"))
            if d is not None and d <= AS_OF:
                if wid not in last_wo_dates or d > last_wo_dates[wid]:
                    last_wo_dates[wid] = d

    wm_comp_dates = {}
    for _, w_row in wm.iterrows():
        wid = str(w_row["well_id"])
        cd = integrity._to_date(w_row.get("completion_date"))
        if cd is None:
            cd = integrity._to_date(w_row.get("spud_date"))
        wm_comp_dates[wid] = cd or date(2021, 10, 1)

    for _, row in df.iterrows():
        wid = row["well_id"]
        t_date = row["test_date"]
        n_due = row["next_due"]

        base_d = last_wo_dates.get(wid, wm_comp_dates.get(wid))
        if base_d is not None:
            assert t_date > base_d, f"test_date {t_date} must be > base_date {base_d} for {wid}"

        assert t_date <= AS_OF, f"test_date {t_date} must be <= AS_OF {AS_OF}"
        assert n_due == t_date + timedelta(days=180), f"next_due {n_due} != test_date {t_date} + 180"


@pytest.mark.parametrize("field_name", FIELDS)
def test_barrier_tests_barrier_types(field_name, field_contexts, generated_tables):
    """SSSV only if lift_type is gas-lift/flowing; PACKER only if packer present."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master")
    ts = ctx.t("tubing_string")
    df = generated_tables[field_name]["barrier_tests"]

    wm_lifts = wm.set_index("well_id")["lift_type"].fillna("").astype(str).str.upper().to_dict()

    packer_wells = set()
    if not ts.empty and "component" in ts.columns:
        p_rows = ts[ts["component"].astype(str).str.strip().str.upper() == "PACKER"]
        packer_wells = set(p_rows["well_id"].dropna().astype(str))

    for _, row in df.iterrows():
        wid = row["well_id"]
        barrier = row["barrier"]
        lift = wm_lifts.get(wid, "")

        if barrier == "SSSV":
            is_gas_or_flowing = any(term in lift for term in ("GAS", "FLOW", "NATURAL"))
            assert is_gas_or_flowing, f"SSSV barrier on non-gas/flowing well {wid} ({lift})"

        if barrier == "PACKER":
            assert wid in packer_wells, f"PACKER barrier on well {wid} without PACKER component"

        assert barrier in {"MASTER_VALVE", "WING_VALVE", "ANNULUS", "SSSV", "PACKER"}


@pytest.mark.parametrize("field_name", FIELDS)
def test_barrier_tests_fail_rate_and_leak_wells(field_name, field_contexts, generated_tables):
    """FAIL allowed ONLY on wells with CASING_LEAK or TUBING_LEAK; rate <= 5% overall."""
    ctx = field_contexts[field_name]
    wo = ctx.t("workover_history")
    df = generated_tables[field_name]["barrier_tests"]

    if df.empty:
        return

    leak_wells = set()
    if not wo.empty and "failure_code" in wo.columns:
        leaks = wo[wo["failure_code"].astype(str).str.strip().str.upper().isin(["CASING_LEAK", "TUBING_LEAK"])]
        leak_wells = set(leaks["well_id"].dropna().astype(str))

    # All FAIL rows must belong to leak_wells
    fail_rows = df[df["result"] == "FAIL"]
    for wid in fail_rows["well_id"]:
        assert wid in leak_wells, f"FAIL on well {wid} without leak failure code"


def test_overall_barrier_fail_rate(generated_tables):
    """Overall FAIL rate across all 3 fields must be <= 5%."""
    all_tests = pd.concat([generated_tables[f]["barrier_tests"] for f in FIELDS], ignore_index=True)
    assert len(all_tests) > 0

    fail_rate = (all_tests["result"] == "FAIL").mean()
    assert fail_rate <= 0.05, f"Overall fail rate {fail_rate:.2%} exceeds 5%"
    assert (all_tests["result"] == "FAIL").sum() > 0, "Expected at least some FAIL results on leak wells"


@pytest.mark.parametrize("field_name", FIELDS)
def test_barrier_tests_test_pressures(field_name, field_contexts, generated_tables):
    """test_pressure_kgcm2 must be 1.1 x max THP (SSSV/MASTER/WING) or max CHP (ANNULUS/PACKER)."""
    ctx = field_contexts[field_name]
    wt = ctx.t("well_tests")
    df = generated_tables[field_name]["barrier_tests"]

    if df.empty:
        return

    field_median_thp = float(wt["thp_kgcm2"].dropna().median()) if not wt.empty and "thp_kgcm2" in wt.columns else 15.0
    field_median_chp = float(wt["chp_kgcm2"].dropna().median()) if not wt.empty and "chp_kgcm2" in wt.columns else 10.0

    well_max_thp = wt.groupby("well_id")["thp_kgcm2"].max().to_dict() if not wt.empty and "thp_kgcm2" in wt.columns else {}
    well_max_chp = wt.groupby("well_id")["chp_kgcm2"].max().to_dict() if not wt.empty and "chp_kgcm2" in wt.columns else {}

    for _, row in df.iterrows():
        wid = row["well_id"]
        barrier = row["barrier"]
        p = row["test_pressure_kgcm2"]

        if barrier in ("MASTER_VALVE", "WING_VALVE", "SSSV"):
            base = well_max_thp.get(wid, field_median_thp)
            if pd.isna(base) or base <= 0:
                base = field_median_thp
            expected_p = round(1.1 * base, 1)
        else:
            base = well_max_chp.get(wid, field_median_chp)
            if pd.isna(base) or base <= 0:
                base = field_median_chp
            expected_p = round(1.1 * base, 1)

        assert abs(p - expected_p) <= 0.1, f"Pressure mismatch for {wid} {barrier}: {p} vs {expected_p}"


# ============================================================================
# Determinism and Lineage tests
# ============================================================================


@pytest.mark.parametrize("field_name", FIELDS)
def test_determinism_two_runs_identical(field_name, field_contexts):
    """Running generate(ctx) twice must return bitwise identical DataFrames."""
    ctx = field_contexts[field_name]

    res1 = integrity.generate(ctx)
    res2 = integrity.generate(ctx)

    pd.testing.assert_frame_equal(res1["wellhead_rating"], res2["wellhead_rating"])
    pd.testing.assert_frame_equal(res1["barrier_tests"], res2["barrier_tests"])


@pytest.mark.parametrize("field_name", FIELDS)
def test_finalize_adds_lineage(field_name, field_contexts):
    """finalize() from common.py properly attaches is_synthetic and lineage columns."""
    ctx = field_contexts[field_name]
    res = integrity.generate(ctx)

    for table_name, df in res.items():
        out = finalize(df, table_name, field_name)
        assert "is_synthetic" in out.columns
        assert bool(out["is_synthetic"].all())
        assert "_source_system" in out.columns
        assert "_source_file" in out.columns
        assert "_batch_id" in out.columns
        assert "_ingested_at" in out.columns
        assert len(out) == len(df)
