"""Unit tests for Stage DG hazards_fishing generator (WH-13, WH-10).

Covers:
- 100% well coverage for fluid_hazards across all 3 fields (412 wells).
- Exact flag consistency with workover_history failure codes.
- Field bands respected for H2S and CO2 concentrations.
- Hazard classification hierarchy (MODERATE -> LOW -> NONE).
- Fishing records generated only for allowed failure codes (ROD_PART, SUDDEN_MECH, SAND).
- Fishing event dates strictly inside job start_date/end_date window.
- Fishing top_md_m within [0, pump_setting_depth_m] (or tubing depth).
- Determinism across multiple generation runs with fixed seed.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.generator.dg import hazards_fishing as hf
from app.analytics.generator.dg.common import FIELDS, finalize, load_field


@pytest.fixture(scope="module")
def field_contexts():
    """Load FieldContext for all 3 fields once for tests."""
    return {f: load_field(f) for f in FIELDS}


@pytest.fixture(scope="module")
def generated_tables(field_contexts):
    """Generate DG tables for all 3 fields."""
    return {f: hf.generate(ctx) for f, ctx in field_contexts.items()}


# ============================================================================
# fluid_hazards tests (WH-13)
# ============================================================================


def test_field_hazard_bands_exported():
    """Module-level FIELD_HAZARD_BANDS dictionary must be present and citeable."""
    assert hasattr(hf, "FIELD_HAZARD_BANDS")
    bands = hf.FIELD_HAZARD_BANDS
    assert "geleki" in bands
    assert "lakwa" in bands
    assert "lakhmani" in bands

    assert bands["geleki"]["h2s_ppm"] == (0.0, 5.0)
    assert bands["geleki"]["co2_mol_pct"] == (0.5, 2.0)

    assert bands["lakwa"]["h2s_ppm"] == (0.0, 3.0)
    assert bands["lakwa"]["co2_mol_pct"] == (0.3, 1.5)

    assert bands["lakhmani"]["h2s_ppm"] == (0.0, 8.0)
    assert bands["lakhmani"]["co2_mol_pct"] == (0.8, 2.5)


@pytest.mark.parametrize("field_name", FIELDS)
def test_fluid_hazards_coverage_and_schema(field_name, field_contexts, generated_tables):
    """Coverage must be 100% of well_master (one row per well, no duplicates)."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master")
    df = generated_tables[field_name]["fluid_hazards"]

    expected_cols = [
        "well_id",
        "field",
        "cluster_id",
        "h2s_ppm",
        "co2_mol_pct",
        "wax_flag",
        "sand_flag",
        "scale_flag",
        "hazard_class",
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


def test_fluid_hazards_total_well_count(generated_tables):
    """Total wells across all three fields must be 412 (142 + 160 + 110)."""
    total = sum(len(generated_tables[f]["fluid_hazards"]) for f in FIELDS)
    assert total == 412
    assert len(generated_tables["geleki"]["fluid_hazards"]) == 142
    assert len(generated_tables["lakwa"]["fluid_hazards"]) == 160
    assert len(generated_tables["lakhmani"]["fluid_hazards"]) == 110


@pytest.mark.parametrize("field_name", FIELDS)
def test_fluid_hazards_bands_respected(field_name, generated_tables):
    """H2S and CO2 values must fall strictly within the field's defined bands."""
    df = generated_tables[field_name]["fluid_hazards"]
    bands = hf.FIELD_HAZARD_BANDS[field_name]

    h2s_min, h2s_max = bands["h2s_ppm"]
    co2_min, co2_max = bands["co2_mol_pct"]

    # Allow tiny tolerance (0.01) for float rounding
    assert (df["h2s_ppm"] >= h2s_min - 0.01).all()
    assert (df["h2s_ppm"] <= h2s_max + 0.01).all()

    assert (df["co2_mol_pct"] >= co2_min - 0.01).all()
    assert (df["co2_mol_pct"] <= co2_max + 0.01).all()


@pytest.mark.parametrize("field_name", FIELDS)
def test_fluid_hazards_flags_match_workover_history(field_name, field_contexts, generated_tables):
    """Flags must be True iff the well's workover_history has the matching failure_code."""
    ctx = field_contexts[field_name]
    wo = ctx.t("workover_history")
    df = generated_tables[field_name]["fluid_hazards"]

    # Map each well to its set of historical failure codes
    wo_valid = wo[wo["well_id"].notna() & wo["failure_code"].notna()]
    codes_by_well = (
        wo_valid.groupby("well_id")["failure_code"]
        .apply(lambda s: set(s.astype(str).str.strip().str.upper()))
        .to_dict()
    )

    for _, row in df.iterrows():
        wid = row["well_id"]
        codes = codes_by_well.get(wid, set())

        expected_wax = "WAX" in codes
        expected_sand = "SAND" in codes
        expected_scale = "SCALE" in codes

        assert row["wax_flag"] == expected_wax, f"{wid} wax_flag mismatch"
        assert row["sand_flag"] == expected_sand, f"{wid} sand_flag mismatch"
        assert row["scale_flag"] == expected_scale, f"{wid} scale_flag mismatch"


@pytest.mark.parametrize("field_name", FIELDS)
def test_fluid_hazards_hazard_classification(field_name, generated_tables):
    """hazard_class rule: MODERATE if h2s>=5 or co2>=2.0, LOW if any flag, else NONE."""
    df = generated_tables[field_name]["fluid_hazards"]

    allowed_classes = {"NONE", "LOW", "MODERATE"}
    assert set(df["hazard_class"]).issubset(allowed_classes)

    for _, row in df.iterrows():
        h2s = row["h2s_ppm"]
        co2 = row["co2_mol_pct"]
        any_flag = row["wax_flag"] or row["sand_flag"] or row["scale_flag"]
        hz = row["hazard_class"]

        if h2s >= 5.0 or co2 >= 2.0:
            assert hz == "MODERATE", f"Expected MODERATE for h2s={h2s}, co2={co2}"
        elif any_flag:
            assert hz == "LOW", f"Expected LOW for any_flag=True, got {hz}"
        else:
            assert hz == "NONE", f"Expected NONE, got {hz}"


# ============================================================================
# fishing_records tests (WH-10)
# ============================================================================


@pytest.mark.parametrize("field_name", FIELDS)
def test_fishing_records_schema(field_name, generated_tables):
    """fishing_records columns must match the required specification."""
    df = generated_tables[field_name]["fishing_records"]
    expected_cols = [
        "well_id",
        "field",
        "cluster_id",
        "event_id",
        "event_date",
        "fish_type",
        "top_md_m",
        "recovered",
        "workover_id",
    ]
    assert list(df.columns) == expected_cols


@pytest.mark.parametrize("field_name", FIELDS)
def test_fishing_records_only_allowed_failure_codes(field_name, field_contexts, generated_tables):
    """Fishing rows must ONLY be generated for workover jobs with ROD_PART, SUDDEN_MECH, or SAND."""
    ctx = field_contexts[field_name]
    wo = ctx.t("workover_history")
    df = generated_tables[field_name]["fishing_records"]

    if df.empty:
        return

    wo_lookup = wo.set_index("workover_id").to_dict(orient="index")
    allowed_codes = {"ROD_PART", "SUDDEN_MECH", "SAND"}

    for _, row in df.iterrows():
        wo_id = row["workover_id"]
        assert wo_id in wo_lookup, f"workover_id {wo_id} not found in workover_history"
        job = wo_lookup[wo_id]
        fc = job["failure_code"]

        assert fc in allowed_codes, f"Disallowed failure code {fc} for fishing record"

        # Check fish_type mapping rules
        ft = row["fish_type"]
        if fc == "ROD_PART":
            assert ft == "PARTED_RODS", f"Expected PARTED_RODS for ROD_PART, got {ft}"
        elif fc == "SUDDEN_MECH":
            assert ft in {"STUCK_PUMP", "TUBING_PARTED"}, f"Expected STUCK_PUMP or TUBING_PARTED, got {ft}"
        elif fc == "SAND":
            assert ft == "STUCK_PUMP", f"Expected STUCK_PUMP for SAND, got {ft}"


@pytest.mark.parametrize("field_name", FIELDS)
def test_fishing_records_dates_inside_job_window(field_name, field_contexts, generated_tables):
    """event_date must be between start_date and end_date inclusive of the workover job."""
    ctx = field_contexts[field_name]
    wo = ctx.t("workover_history")
    df = generated_tables[field_name]["fishing_records"]

    if df.empty:
        return

    wo_lookup = wo.set_index("workover_id").to_dict(orient="index")

    for _, row in df.iterrows():
        wo_id = row["workover_id"]
        job = wo_lookup[wo_id]
        start_d = job["start_date"]
        end_d = job["end_date"] if pd.notna(job.get("end_date")) else start_d

        if start_d > end_d:
            start_d, end_d = end_d, start_d

        ev_date = row["event_date"]
        assert start_d <= ev_date <= end_d, (
            f"event_date {ev_date} outside [{start_d}, {end_d}] for {wo_id}"
        )


@pytest.mark.parametrize("field_name", FIELDS)
def test_fishing_records_depths_within_range(field_name, field_contexts, generated_tables):
    """top_md_m must be between 0 and pump_setting_depth_m (or tubing depth if missing)."""
    ctx = field_contexts[field_name]
    wm = ctx.t("well_master")
    ts = ctx.t("tubing_string")
    df = generated_tables[field_name]["fishing_records"]

    if df.empty:
        return

    pump_map = wm.set_index("well_id")["pump_setting_depth_m"].to_dict()

    ts_valid = ts.dropna(subset=["top_m", "length_m"]).copy()
    ts_valid["bottom_m"] = ts_valid["top_m"] + ts_valid["length_m"]
    max_tubing_map = ts_valid.groupby("well_id")["bottom_m"].max().to_dict()

    for _, row in df.iterrows():
        wid = row["well_id"]
        top_md = row["top_md_m"]

        pump_d = pump_map.get(wid)
        if pd.notna(pump_d) and float(pump_d) > 0:
            max_allowed = float(pump_d)
        else:
            max_allowed = float(max_tubing_map.get(wid, 3000.0))

        assert 0.0 <= top_md <= max_allowed + 0.1, (
            f"top_md_m {top_md} out of bounds [0.0, {max_allowed}] for well {wid}"
        )


def test_fishing_records_rates_and_recovered(generated_tables):
    """Check that selection probabilities and recovered percentages approximate target rates."""
    all_fish = pd.concat([generated_tables[f]["fishing_records"] for f in FIELDS], ignore_index=True)
    assert len(all_fish) > 100

    # ~85% recovered True
    rec_rate = all_fish["recovered"].mean()
    assert 0.75 <= rec_rate <= 0.95, f"Recovered rate {rec_rate:.2%} not ~85%"

    # Event IDs are unique
    assert all_fish["event_id"].nunique() == len(all_fish)


# ============================================================================
# Determinism and Finalize tests
# ============================================================================


@pytest.mark.parametrize("field_name", FIELDS)
def test_determinism_two_runs_identical(field_name, field_contexts):
    """Running generate(ctx) twice must return bitwise identical DataFrames."""
    ctx = field_contexts[field_name]

    res1 = hf.generate(ctx)
    res2 = hf.generate(ctx)

    pd.testing.assert_frame_equal(res1["fluid_hazards"], res2["fluid_hazards"])
    pd.testing.assert_frame_equal(res1["fishing_records"], res2["fishing_records"])


@pytest.mark.parametrize("field_name", FIELDS)
def test_finalize_adds_lineage(field_name, field_contexts):
    """finalize() from common.py properly attaches is_synthetic and lineage columns."""
    ctx = field_contexts[field_name]
    res = hf.generate(ctx)

    for table_name, df in res.items():
        out = finalize(df, table_name, field_name)
        assert "is_synthetic" in out.columns
        assert bool(out["is_synthetic"].all())
        assert "_source_system" in out.columns
        assert "_source_file" in out.columns
        assert "_batch_id" in out.columns
        assert "_ingested_at" in out.columns
        assert len(out) == len(df)
