"""Unit tests for well construction, formation tops, and pressure survey generators."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics.generator.construction import (
    generate_casing_tally,
    generate_perforation_intervals,
    generate_tubing_string,
)
from app.analytics.generator.formation_tops import generate_formation_tops
from app.analytics.generator.pressure_surveys import generate_pressure_surveys


@pytest.fixture
def synthetic_data():
    wells = pd.DataFrame([
        {
            "well_id": "W-001",
            "field": "Geleki",
            "cluster_id": "CL-01",
            "completion_date": date(2010, 1, 15),
            "current_zone": "Tipam",
            "perf_top_m": 2700.0,
            "perf_bottom_m": 2750.0,
            "total_depth_md_m": 2850.0,
            "total_depth_tvd_m": 2830.0,
            "lift_type": "SRP",
            "pump_setting_depth_m": 2600.0,
            "tubing_size_in": 2.875,
            "casing_size_in": 5.5,
        },
        {
            "well_id": "W-002",
            "field": "Geleki",
            "cluster_id": "CL-01",
            "completion_date": date(2011, 3, 20),
            "current_zone": "Tipam",
            "perf_top_m": 2720.0,
            "perf_bottom_m": 2760.0,
            "total_depth_md_m": 2860.0,
            "total_depth_tvd_m": 2840.0,
            "lift_type": "GAS_LIFT",
            "pump_setting_depth_m": None,
            "tubing_size_in": 3.5,
            "casing_size_in": 7.0,
        },
        {
            "well_id": "W-003",
            "field": "Geleki",
            "cluster_id": "CL-02",
            "completion_date": date(2012, 5, 10),
            "current_zone": "Barail",
            "perf_top_m": 3300.0,
            "perf_bottom_m": 3350.0,
            "total_depth_md_m": 3480.0,
            "total_depth_tvd_m": 3450.0,
            "lift_type": "NATURAL",
            "pump_setting_depth_m": None,
            "tubing_size_in": 2.875,
            "casing_size_in": 5.5,
        },
        {
            "well_id": "W-004",
            "field": "Geleki",
            "cluster_id": "CL-02",
            "completion_date": date(2013, 7, 25),
            "current_zone": "Barail",
            "perf_top_m": 3320.0,
            "perf_bottom_m": 3370.0,
            "total_depth_md_m": 3500.0,
            "total_depth_tvd_m": 3470.0,
            "lift_type": "SRP",
            "pump_setting_depth_m": 3200.0,
            "tubing_size_in": 3.5,
            "casing_size_in": 7.0,
        },
        {
            "well_id": "W-005",
            "field": "Geleki",
            "cluster_id": "CL-03",
            "completion_date": date(2014, 9, 14),
            "current_zone": "Lakadong",
            "perf_top_m": 3900.0,
            "perf_bottom_m": 3950.0,
            "total_depth_md_m": 4050.0,
            "total_depth_tvd_m": 4010.0,
            "lift_type": "GAS_LIFT",
            "pump_setting_depth_m": None,
            "tubing_size_in": 2.875,
            "casing_size_in": 5.5,
        },
        {
            "well_id": "W-006",
            "field": "Geleki",
            "cluster_id": "CL-03",
            "completion_date": date(2015, 11, 2),
            "current_zone": "Lakadong",
            "perf_top_m": 3920.0,
            "perf_bottom_m": 3970.0,
            "total_depth_md_m": 4080.0,
            "total_depth_tvd_m": 4040.0,
            "lift_type": "NATURAL",
            "pump_setting_depth_m": None,
            "tubing_size_in": 3.5,
            "casing_size_in": 7.0,
        },
    ])

    workovers = pd.DataFrame([
        {
            "workover_id": "WO-001",
            "well_id": "W-001",
            "start_date": date(2018, 5, 1),
            "end_date": date(2018, 5, 8),
            "catalogue_job_code": "TUBING_REPLACE",
            "is_censored": False,
        },
        {
            "workover_id": "WO-002",
            "well_id": "W-002",
            "start_date": date(2019, 2, 10),
            "end_date": date(2019, 2, 16),
            "catalogue_job_code": "ADD_PERFORATION",
            "is_censored": False,
        },
    ])

    daily_rows = []
    base_date = date(2018, 1, 1)
    for w_idx in range(1, 7):
        wid = f"W-{w_idx:03d}"
        for d in range(0, 2600, 7):
            p_date = base_date + timedelta(days=d)
            daily_rows.append({
                "well_id": wid,
                "production_date": p_date,
                "liquid_rate_blpd": 125.0 + float(w_idx * 5),
                "is_producing": True,
            })
    daily = pd.DataFrame(daily_rows)

    return wells, workovers, daily


def test_determinism(synthetic_data):
    wells, workovers, daily = synthetic_data
    seed = 42

    # casing tally determinism
    c1 = generate_casing_tally(wells, seed)
    c2 = generate_casing_tally(wells, seed)
    assert c1.equals(c2)

    # tubing string determinism
    t1 = generate_tubing_string(wells, workovers, seed)
    t2 = generate_tubing_string(wells, workovers, seed)
    assert t1.equals(t2)

    # perforation intervals determinism
    p1 = generate_perforation_intervals(wells, workovers, seed)
    p2 = generate_perforation_intervals(wells, workovers, seed)
    assert p1.equals(p2)

    # formation tops determinism
    f1 = generate_formation_tops(wells, seed)
    f2 = generate_formation_tops(wells, seed)
    assert f1.equals(f2)

    # pressure surveys determinism
    s1 = generate_pressure_surveys(
        wells, daily, date(2019, 1, 1), date(2024, 12, 31), seed
    )
    s2 = generate_pressure_surveys(
        wells, daily, date(2019, 1, 1), date(2024, 12, 31), seed
    )
    assert s1.equals(s2)


def test_column_lists(synthetic_data):
    wells, workovers, daily = synthetic_data
    seed = 123

    casing = generate_casing_tally(wells, seed)
    assert list(casing.columns) == [
        "well_id",
        "field",
        "cluster_id",
        "string_type",
        "od_in",
        "weight_ppf",
        "grade",
        "top_m",
        "shoe_m",
        "cement_top_m",
        "install_date",
    ]

    tubing = generate_tubing_string(wells, workovers, seed)
    assert list(tubing.columns) == [
        "well_id",
        "field",
        "cluster_id",
        "seq",
        "component",
        "od_in",
        "length_m",
        "top_m",
        "install_date",
        "workover_id",
    ]

    perfs = generate_perforation_intervals(wells, workovers, seed)
    assert list(perfs.columns) == [
        "well_id",
        "field",
        "cluster_id",
        "zone",
        "top_m",
        "bottom_m",
        "spf",
        "perf_date",
        "status",
    ]

    formations = generate_formation_tops(wells, seed)
    assert list(formations.columns) == [
        "well_id",
        "field",
        "cluster_id",
        "formation",
        "top_md_m",
        "bottom_md_m",
        "lithology",
    ]

    surveys = generate_pressure_surveys(
        wells, daily, date(2019, 1, 1), date(2024, 12, 31), seed
    )
    assert list(surveys.columns) == [
        "well_id",
        "field",
        "cluster_id",
        "survey_id",
        "survey_date",
        "sbhp_kgcm2",
        "fbhp_kgcm2",
        "pi_bpd_per_kgcm2",
        "fluid_level_m",
        "datum_tvd_m",
    ]


def test_casing_shoes_and_cement(synthetic_data):
    wells, _, _ = synthetic_data
    seed = 999

    casing = generate_casing_tally(wells, seed)
    assert len(casing) == len(wells) * 3

    for wid, group in casing.groupby("well_id", sort=False):
        assert list(group["string_type"]) == [
            "CONDUCTOR",
            "SURFACE",
            "PRODUCTION",
        ]
        shoes = list(group["shoe_m"])
        # Casing shoes increase CONDUCTOR < SURFACE < PRODUCTION
        assert shoes[0] < shoes[1] < shoes[2]

        # cement_top_m <= shoe_m
        for _, row in group.iterrows():
            assert row["cement_top_m"] <= row["shoe_m"]


def test_tubing_string_contiguity_and_components(synthetic_data):
    wells, workovers, _ = synthetic_data
    seed = 555

    tubing = generate_tubing_string(wells, workovers, seed)
    well_map = wells.set_index("well_id")

    for wid, group in tubing.groupby("well_id", sort=False):
        w_meta = well_map.loc[wid]
        # seq starts at 1 and increases monotonically
        assert list(group["seq"]) == list(range(1, len(group) + 1))

        # First top_m is 0.0
        assert group.iloc[0]["top_m"] == 0.0

        # Components are contiguous
        prev_bottom = 0.0
        for _, row in group.iterrows():
            assert np.isclose(row["top_m"], prev_bottom, atol=0.1)
            prev_bottom = round(row["top_m"] + row["length_m"], 1)

        # Lift-type specific assertions
        if w_meta["lift_type"] == "SRP":
            pump_rows = group[group["component"] == "PUMP"]
            assert len(pump_rows) == 1
            # SRP PUMP top equals pump_setting_depth_m
            assert np.isclose(
                pump_rows.iloc[0]["top_m"],
                float(w_meta["pump_setting_depth_m"]),
                atol=0.1,
            )
            assert list(group["component"]) == ["TUBING", "PUMP", "TUBING_ANCHOR"]

        elif w_meta["lift_type"] == "GAS_LIFT":
            # GAS_LIFT has 4-5 GLM rows
            glm_count = (group["component"] == "GLM").sum()
            assert 4 <= glm_count <= 5

        elif w_meta["lift_type"] == "NATURAL":
            assert list(group["component"]) == ["TUBING", "PACKER"]

    # Check workover effect: W-001 had TUBING_REPLACE
    w1_tubing = tubing[tubing["well_id"] == "W-001"]
    assert all(w1_tubing["workover_id"] == "WO-001")
    assert all(w1_tubing["install_date"] == date(2018, 5, 8))

    # W-003 had no workover
    w3_tubing = tubing[tubing["well_id"] == "W-003"]
    assert all(w3_tubing["workover_id"].isna())
    assert all(w3_tubing["install_date"] == date(2012, 5, 10))


def test_perforation_intervals(synthetic_data):
    wells, workovers, _ = synthetic_data
    seed = 777

    perfs = generate_perforation_intervals(wells, workovers, seed)
    well_map = wells.set_index("well_id")

    for _, row in perfs.iterrows():
        wid = row["well_id"]
        td_md_m = float(well_map.loc[wid, "total_depth_md_m"])
        # perforation top_m < bottom_m and bottom_m <= total_depth_md_m
        assert row["top_m"] < row["bottom_m"]
        assert row["bottom_m"] <= td_md_m

    # W-002 had ADD_PERFORATION
    w2_perfs = perfs[perfs["well_id"] == "W-002"]
    # Should have primary plus ADD_PERFORATION (and possibly older)
    add_rows = w2_perfs[w2_perfs["perf_date"] == date(2019, 2, 16)]
    assert len(add_rows) == 1
    assert add_rows.iloc[0]["spf"] == 6
    assert add_rows.iloc[0]["status"] == "OPEN"


def test_formation_tops(synthetic_data):
    wells, _, _ = synthetic_data
    seed = 888

    formations = generate_formation_tops(wells, seed)
    well_map = wells.set_index("well_id")

    for wid, group in formations.groupby("well_id", sort=False):
        w_meta = well_map.loc[wid]
        td_md_m = float(w_meta["total_depth_md_m"])
        perf_top = float(w_meta["perf_top_m"])
        perf_bot = float(w_meta["perf_bottom_m"])
        current_zone = str(w_meta["current_zone"])

        # Start at 0
        assert group.iloc[0]["top_md_m"] == 0.0

        # End at TD
        assert np.isclose(group.iloc[-1]["bottom_md_m"], td_md_m, atol=0.1)

        # Contiguous: each top = previous bottom
        for i in range(1, len(group)):
            assert np.isclose(
                group.iloc[i]["top_md_m"], group.iloc[i - 1]["bottom_md_m"], atol=0.1
            )

        # Zone contains perfs
        zone_rows = group[group["formation"] == current_zone]
        assert len(zone_rows) == 1
        z_row = zone_rows.iloc[0]
        assert z_row["top_md_m"] <= perf_top
        assert z_row["bottom_md_m"] >= perf_bot


def test_pressure_surveys(synthetic_data):
    wells, _, daily = synthetic_data
    seed = 333
    start = date(2018, 1, 1)
    end = date(2024, 12, 31)

    surveys = generate_pressure_surveys(wells, daily, start, end, seed)
    assert not surveys.empty

    for wid, group in surveys.groupby("well_id", sort=False):
        s_dates = list(group["survey_date"])
        # Consecutive intervals in [365, 730] days
        for i in range(1, len(s_dates)):
            delta_days = (s_dates[i] - s_dates[i - 1]).days
            assert 365 <= delta_days <= 730

    # fbhp < sbhp for all surveys
    for _, row in surveys.iterrows():
        assert row["fbhp_kgcm2"] < row["sbhp_kgcm2"]
