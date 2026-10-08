"""Unit tests for Stage DG tubing_deviation generator (WH-06, WH-08).

Covers:
- tubing_tally schema, joint_no sequence, component types, API nominal lookup.
- Tally bottom matches current tubing_string bottom depth within +-0.01 m.
- TUBING_JOINT lengths strictly in [9.15, 9.75] m and PUP lengths > 0.
- Monotonic depths (top_md_m, bottom_md_m) and joint contiguity.
- GL_MANDREL present only where tubing_string already has them.
- deviation_survey schema, 30m station grid, final station exactly at TD MD.
- Minimum-curvature TVD monotonic non-decreasing and <= MD + 0.01 m.
- Final survey TVD matches well_master.total_depth_tvd_m within 1%.
- Max dogleg severity respects bound (max_dls + 0.2 tolerance).
- Deterministic per-well generation across multiple runs.
- Full coverage across all 3 fields (geleki, lakwa, lakhmani).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.generator.dg import tubing_deviation as td
from app.analytics.generator.dg.common import FIELDS, finalize, load_field


@pytest.fixture(scope="module")
def field_contexts():
    """Load FieldContext for all 3 fields once for tests."""
    return {f: load_field(f) for f in FIELDS}


@pytest.fixture(scope="module")
def generated_tables(field_contexts):
    """Generate DG tables for all 3 fields."""
    return {f: td.generate(ctx) for f, ctx in field_contexts.items()}


# ============================================================================
# tubing_tally tests (WH-06)
# ============================================================================


def test_api_nominal_table_exported():
    """API nominal dictionary must be present and correctly specified."""
    assert hasattr(td, "API_NOMINAL")
    nom = td.API_NOMINAL
    assert 2.375 in nom
    assert 2.875 in nom
    assert 3.5 in nom

    assert nom[2.375] == {"id_in": 1.995, "drift_in": 1.901, "weight_ppf": 4.7}
    assert nom[2.875] == {"id_in": 2.441, "drift_in": 2.347, "weight_ppf": 6.5}
    assert nom[3.5] == {"id_in": 2.992, "drift_in": 2.867, "weight_ppf": 9.3}


def test_no_tubing_wells_constant_exported():
    """Module-level NO_TUBING_WELLS constant must be exported."""
    assert hasattr(td, "NO_TUBING_WELLS")
    assert isinstance(td.NO_TUBING_WELLS, list)


@pytest.mark.parametrize("field_name", FIELDS)
def test_tubing_tally_schema_and_types(field_name, generated_tables):
    """tubing_tally columns and basic types must match the specification."""
    df = generated_tables[field_name]["tubing_tally"]
    expected_cols = [
        "well_id",
        "field",
        "cluster_id",
        "joint_no",
        "component_type",
        "top_md_m",
        "bottom_md_m",
        "length_m",
        "od_in",
        "id_in",
        "drift_in",
        "grade",
        "weight_ppf",
    ]
    assert list(df.columns) == expected_cols
    assert not df.empty


@pytest.mark.parametrize("field_name", FIELDS)
def test_tubing_tally_coverage_rule(field_name, field_contexts, generated_tables):
    """Coverage rule: every well with tubing_string rows has a tally."""
    ctx = field_contexts[field_name]
    ts = ctx.t("tubing_string")
    df = generated_tables[field_name]["tubing_tally"]

    expected_wells = set(ts["well_id"].unique())
    actual_wells = set(df["well_id"].unique())
    assert actual_wells == expected_wells


@pytest.mark.parametrize("field_name", FIELDS)
def test_tally_bottom_matches_tubing_depth(field_name, field_contexts, generated_tables):
    """Tally bottom depth must match cumulative tubing string bottom depth (+-0.01 m)."""
    ctx = field_contexts[field_name]
    ts = ctx.t("tubing_string")
    df = generated_tables[field_name]["tubing_tally"]

    # Calculate expected bottom from current tubing_string (latest install_date)
    for wid, g in ts.groupby("well_id"):
        max_d = g["install_date"].max()
        curr = g[g["install_date"] == max_d]
        expected_bottom = round((curr["top_m"] + curr["length_m"]).max(), 2)

        well_tally = df[df["well_id"] == wid]
        assert not well_tally.empty, f"Well {wid} missing from tally"
        actual_bottom = well_tally["bottom_md_m"].iloc[-1]
        assert abs(actual_bottom - expected_bottom) <= 0.01, (
            f"{wid}: actual bottom {actual_bottom} != expected {expected_bottom}"
        )


@pytest.mark.parametrize("field_name", FIELDS)
def test_joint_lengths_in_range(field_name, generated_tables):
    """All TUBING_JOINT lengths must be in [9.15, 9.75] m and PUP lengths > 0."""
    df = generated_tables[field_name]["tubing_tally"]

    joints = df[df["component_type"] == "TUBING_JOINT"]
    assert not joints.empty
    assert (joints["length_m"] >= 9.15 - 1e-4).all(), "Some TUBING_JOINT lengths < 9.15"
    assert (joints["length_m"] <= 9.75 + 1e-4).all(), "Some TUBING_JOINT lengths > 9.75"

    pups = df[df["component_type"] == "PUP"]
    assert not pups.empty
    assert (pups["length_m"] > 0).all(), "PUP length must be strictly positive"


@pytest.mark.parametrize("field_name", FIELDS)
def test_tubing_tally_depths_monotonic_and_contiguous(field_name, generated_tables):
    """Depths must be strictly increasing and contiguous within each well."""
    df = generated_tables[field_name]["tubing_tally"]

    for wid, g in df.groupby("well_id"):
        # joint_no is 1, 2, ... N
        assert list(g["joint_no"]) == list(range(1, len(g) + 1)), f"{wid}: non-consecutive joint_no"

        top = g["top_md_m"].to_numpy()
        bot = g["bottom_md_m"].to_numpy()
        length = g["length_m"].to_numpy()

        # top_md_m must be strictly increasing
        assert np.all(np.diff(top) > 0), f"{wid}: top_md_m not strictly increasing"
        # bottom_md_m must be strictly increasing
        assert np.all(np.diff(bot) > 0), f"{wid}: bottom_md_m not strictly increasing"
        # bot - top == length
        assert np.all(np.abs((bot - top) - length) <= 0.01), f"{wid}: length_m != bottom - top"
        # Contiguity: each row's top equals previous row's bottom
        assert np.all(np.abs(top[1:] - bot[:-1]) <= 0.01), f"{wid}: gap between joints"


@pytest.mark.parametrize("field_name", FIELDS)
def test_nominal_lookup_and_grade(field_name, generated_tables):
    """id_in, drift_in, weight_ppf, and grade must follow API nominal rules."""
    df = generated_tables[field_name]["tubing_tally"]

    for wid, g in df.groupby("well_id"):
        # Single grade per well across valid tubing sizes
        valid_rows = g[g["od_in"].isin([2.375, 2.875, 3.5])]
        assert not valid_rows.empty
        grades = valid_rows["grade"].unique()
        assert len(grades) == 1, f"{wid}: multiple grades in well"
        assert grades[0] in {"J-55", "N-80"}, f"{wid}: invalid grade {grades[0]}"

        for _, row in valid_rows.iterrows():
            nom = td.API_NOMINAL[row["od_in"]]
            assert abs(row["id_in"] - nom["id_in"]) < 1e-4
            assert abs(row["drift_in"] - nom["drift_in"]) < 1e-4
            assert abs(row["weight_ppf"] - nom["weight_ppf"]) < 1e-4


@pytest.mark.parametrize("field_name", FIELDS)
def test_gl_mandrel_only_where_existing(field_name, field_contexts, generated_tables):
    """GL_MANDREL rows appear ONLY if tubing_string already had GLM / GL_MANDREL."""
    ctx = field_contexts[field_name]
    ts = ctx.t("tubing_string")
    df = generated_tables[field_name]["tubing_tally"]

    wells_with_glm = set(ts[ts["component"].isin(["GLM", "GL_MANDREL"])]["well_id"])
    tally_glm_wells = set(df[df["component_type"] == "GL_MANDREL"]["well_id"])

    # Must be exact match: never invent mandrels
    assert tally_glm_wells == wells_with_glm


# ============================================================================
# deviation_survey tests (WH-08)
# ============================================================================


@pytest.mark.parametrize("field_name", FIELDS)
def test_deviation_survey_schema_and_coverage(field_name, field_contexts, generated_tables):
    """deviation_survey must cover 100% of wells in well_master with exact columns."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master")
    df = generated_tables[field_name]["deviation_survey"]

    expected_cols = [
        "well_id",
        "field",
        "cluster_id",
        "md_m",
        "inc_deg",
        "azi_deg",
        "tvd_m",
        "dls_deg_30m",
    ]
    assert list(df.columns) == expected_cols

    # Coverage: 100% of well_master
    assert set(df["well_id"].unique()) == set(wm["well_id"].unique())


@pytest.mark.parametrize("field_name", FIELDS)
def test_deviation_survey_stations_grid(field_name, field_contexts, generated_tables):
    """Stations must be every 30m starting at 0, with the final station exactly at TD MD."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master").set_index("well_id")
    df = generated_tables[field_name]["deviation_survey"]

    for wid, g in df.groupby("well_id"):
        td_md = round(float(wm.loc[wid, "total_depth_md_m"]), 2)
        mds = g["md_m"].to_numpy()

        assert mds[0] == 0.0, f"{wid}: station 0 MD != 0.0"
        assert abs(mds[-1] - td_md) <= 0.01, f"{wid}: last station {mds[-1]} != TD MD {td_md}"
        # Strictly increasing
        assert np.all(np.diff(mds) > 0), f"{wid}: MD not strictly increasing"

        # Check 30m spacing for intermediate stations
        if len(mds) > 2:
            steps = np.diff(mds[:-1])
            assert np.allclose(steps, 30.0, atol=0.01), f"{wid}: intermediate stations not 30m"


@pytest.mark.parametrize("field_name", FIELDS)
def test_tvd_monotonic_and_bounded_by_md(field_name, generated_tables):
    """TVD must be monotonic non-decreasing and <= MD + 0.01 m."""
    df = generated_tables[field_name]["deviation_survey"]

    for wid, g in df.groupby("well_id"):
        mds = g["md_m"].to_numpy()
        tvds = g["tvd_m"].to_numpy()

        # Surface station TVD == 0
        assert tvds[0] == 0.0
        # Monotonic non-decreasing
        assert np.all(np.diff(tvds) >= -1e-4), f"{wid}: TVD not monotonic non-decreasing"
        # Bounded by MD
        assert np.all(tvds <= mds + 0.01), f"{wid}: TVD exceeds MD + 0.01"


@pytest.mark.parametrize("field_name", FIELDS)
def test_final_tvd_within_one_percent(field_name, field_contexts, generated_tables):
    """Final TVD at TD must match well_master.total_depth_tvd_m within 1%."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master").set_index("well_id")
    df = generated_tables[field_name]["deviation_survey"]

    for wid, g in df.groupby("well_id"):
        expected_tvd = float(wm.loc[wid, "total_depth_tvd_m"])
        actual_tvd = g["tvd_m"].iloc[-1]
        err_pct = abs(actual_tvd - expected_tvd) / expected_tvd

        assert err_pct < 0.01, f"{wid}: TVD error {err_pct:.4%} >= 1% (actual={actual_tvd}, exp={expected_tvd})"


@pytest.mark.parametrize("field_name", FIELDS)
def test_max_dls_bound_respected(field_name, field_contexts, generated_tables):
    """Max DLS must satisfy well_master.max_dls_deg_30m (+0.2 tolerance), or physical bound."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master").set_index("well_id")
    df = generated_tables[field_name]["deviation_survey"]

    for wid, g in df.groupby("well_id"):
        max_dls_raw = wm.loc[wid, "max_dls_deg_30m"]
        max_dls_allowed = float(max_dls_raw) + 0.2 if pd.notna(max_dls_raw) else 3.0
        observed_max_dls = g["dls_deg_30m"].max()

        assert observed_max_dls <= max_dls_allowed + 0.01, (
            f"{wid}: max DLS {observed_max_dls} exceeds allowed {max_dls_allowed}"
        )


@pytest.mark.parametrize("field_name", FIELDS)
def test_constant_azimuth_per_well(field_name, generated_tables):
    """Azimuth must be constant for all survey stations of each well."""
    df = generated_tables[field_name]["deviation_survey"]

    for wid, g in df.groupby("well_id"):
        assert g["azi_deg"].nunique() == 1, f"{wid}: multiple azimuths in well"


# ============================================================================
# Determinism and Finalize tests
# ============================================================================


@pytest.mark.parametrize("field_name", FIELDS)
def test_determinism_two_runs_identical(field_name, field_contexts):
    """Running generate(ctx) twice must return bitwise identical DataFrames."""
    ctx = field_contexts[field_name]

    res1 = td.generate(ctx)
    res2 = td.generate(ctx)

    pd.testing.assert_frame_equal(res1["tubing_tally"], res2["tubing_tally"])
    pd.testing.assert_frame_equal(res1["deviation_survey"], res2["deviation_survey"])


@pytest.mark.parametrize("field_name", FIELDS)
def test_finalize_adds_lineage(field_name, field_contexts):
    """finalize() from common.py properly attaches is_synthetic and lineage columns."""
    ctx = field_contexts[field_name]
    res = td.generate(ctx)

    for table_name, df in res.items():
        out = finalize(df, table_name, field_name)
        assert "is_synthetic" in out.columns
        assert bool(out["is_synthetic"].all())
        assert "_source_system" in out.columns
        assert "_source_file" in out.columns
        assert "_batch_id" in out.columns
        assert "_ingested_at" in out.columns
        assert len(out) == len(df)
