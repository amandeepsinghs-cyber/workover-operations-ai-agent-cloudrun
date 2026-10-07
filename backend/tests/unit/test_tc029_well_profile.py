"""TC-029 well_profile + TC-017 v2 production series (Gate T item 3/4; BDD-F12-S01/S02/S03/S05)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app import settings
from app.analytics.tools.common import ToolStatus, currency_keys, load_table, to_jsonable, well_rows
from app.analytics.tools.well_profile import well_production_series, well_profile


@pytest.mark.parametrize("well_id", ["GK-129", "LKM-061", "LKW-047"])
def test_profile_has_construction_lift_and_3plus_same_cluster_neighbours(well_id):
    r = well_profile(well_id)
    assert r.status == ToolStatus.OK, r.message
    v = r.value
    assert v.identity["formation"] and v.identity["zone"]
    assert v.construction["casing"] and v.construction["tubing"] and v.construction["perfs"]
    assert v.construction["casing_size_in"] and v.construction["tubing_size_in"]
    assert v.lithology and all("lithology" in x for x in v.lithology)
    assert v.lift["lift_type"]
    assert v.status["bucket"] in {"PRODUCING_OK", "AT_RISK", "UNDERPERFORMING", "NOT_PRODUCING"}
    assert len(v.neighbours) >= 3
    wm = load_table("well_master").set_index("well_id")
    for n in v.neighbours:
        assert n["cluster_id"] == v.identity["cluster_id"] == wm.loc[n["well_id"], "cluster_id"]
        assert n["well_id"] != well_id and n["distance_m"] > 0
        assert "bucket" in n and "oil_bopd" in n and "residual_pct" in n
    d = [n["distance_m"] for n in v.neighbours]
    assert d == sorted(d)
    assert currency_keys(v) == []
    to_jsonable(v)


def test_profile_unknown_well():
    assert well_profile("ZZ-999").status == ToolStatus.UNAVAILABLE


@pytest.mark.parametrize("months", [24, 36, 60])
def test_all_in_window_job_markers(months):
    wid = "GK-129"
    r = well_production_series(wid, months=months)
    v = r.value
    start = v.window_start
    wo = well_rows("workover_history", wid)
    real = wo[~wo["is_censored"].astype(bool)]
    in_win = real[(real["start_date"] >= start) & (real["start_date"] <= settings.AS_OF)]
    assert sorted(m["workover_id"] for m in v.interventions) == sorted(in_win["workover_id"])
    older = real[real["start_date"] < start]
    assert len(v.historical_interventions) == len(older)
    assert all(m["date"] >= start for m in v.interventions)
    assert v.dates[0] >= start and v.dates[-1] == settings.AS_OF
    assert start >= settings.AS_OF - timedelta(days=int(months * 30.44) + 2)
    for m in v.interventions:
        assert m["outcome"] and m["job_code"] and m["job_code"] != "NONE_CENSORED"


def test_series_aligned_and_ws6_telemetry_for_gas_lift_well():
    v = well_production_series("LKM-061", months=36, metrics=["oil", "gor", "wht", "gl_inj_rate", "gl_inj_pressure"]).value
    assert v.gas_lift is True
    for m in ("oil", "gor", "wht", "gl_inj_rate", "gl_inj_pressure"):
        assert len(v.series[m]) == len(v.dates)
        assert any(x is not None for x in v.series[m]), m
    assert v.units["wht"] == "degC" and v.units["gl_inj_pressure"] == "kg/cm2"
    d = well_rows("daily_production", "LKM-061").set_index("production_date")
    i = len(v.dates) - 1
    assert v.series["wht"][i] == pytest.approx(float(d.loc[v.dates[i], "wht_degc"]), abs=0.006)


def test_srp_well_has_null_gas_lift_series():
    v = well_production_series("GK-129", months=36).value
    assert v.gas_lift is False
    assert all(x is None for x in v.series["gl_inj_rate"]) and all(x is None for x in v.series["gl_inj_pressure"])
    assert any(x is not None for x in v.series["wht"])


def test_bad_metric_unavailable():
    r = well_production_series("GK-129", metrics=["oil", "bogus"])
    assert r.status == ToolStatus.UNAVAILABLE and "metrics" in r.missing_fields
