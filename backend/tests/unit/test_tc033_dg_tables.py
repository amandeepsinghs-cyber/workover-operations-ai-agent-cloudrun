"""Unit tests for TC-033 dg_tables tools and REST routes (SDD §5.9, §6.2, §13.4, Stage DG)."""

from __future__ import annotations

import pandas as pd
import pytest

from app import settings
from app.analytics.generator.fields import field_of
from app.analytics.tools.common import ToolStatus, currency_keys
from app.analytics.tools.dg_tables import deviation_survey, integrity, tubing_tally

TEST_WELLS = ["GK-129", "LKW-047", "LKM-061"]


def _landing_table(table_name: str, well_id: str) -> pd.DataFrame:
    fld = field_of(well_id)
    assert fld is not None
    p = settings.LANDING_DIR / fld.lower() / f"{table_name}.parquet"
    df = pd.read_parquet(p)
    return df[df["well_id"] == well_id].reset_index(drop=True)


@pytest.mark.parametrize("well_id", TEST_WELLS)
def test_tubing_tally_summary_and_values(well_id: str):
    res = tubing_tally(well_id)
    assert res.status == ToolStatus.OK
    assert res["is_synthetic"] is True
    assert res["well_id"] == well_id
    assert res["as_of"] == str(settings.AS_OF)
    assert "rows" in res and len(res["rows"]) > 0
    assert "summary" in res

    # Recomputation from landing parquet
    df = _landing_table("tubing_tally", well_id)
    s = res["summary"]
    assert s["joint_count"] == len(df)
    assert s["min_drift"] == round(float(df["drift_in"].min()), 3)
    assert s["total_length_m"] == pytest.approx(round(float(df["length_m"].sum()), 2), abs=0.01)
    assert s["max_depth_m"] == pytest.approx(round(float(df["bottom_md_m"].max()), 2), abs=0.01)
    assert currency_keys(res) == []


@pytest.mark.parametrize("well_id", TEST_WELLS)
def test_deviation_survey_summary_and_values(well_id: str):
    res = deviation_survey(well_id)
    assert res.status == ToolStatus.OK
    assert res["is_synthetic"] is True
    assert res["well_id"] == well_id
    assert res["as_of"] == str(settings.AS_OF)
    assert "rows" in res and len(res["rows"]) > 0
    assert "summary" in res

    # Recomputation from landing parquet
    df = _landing_table("deviation_survey", well_id)
    s = res["summary"]
    assert s["station_count"] == len(df)
    assert s["max_inclination"] == round(float(df["inc_deg"].max()), 2)
    assert s["max_md_m"] == round(float(df["md_m"].max()), 2)
    assert s["max_tvd_m"] == round(float(df["tvd_m"].max()), 2)
    assert currency_keys(res) == []


@pytest.mark.parametrize("well_id", TEST_WELLS)
def test_integrity_summary_and_values(well_id: str):
    res = integrity(well_id)
    assert res.status == ToolStatus.OK
    assert res["is_synthetic"] is True
    assert res["well_id"] == well_id
    assert res["as_of"] == str(settings.AS_OF)
    assert "rows" in res
    assert "summary" in res

    # Recomputation from landing parquet
    wh = _landing_table("wellhead_rating", well_id)
    fh = _landing_table("fluid_hazards", well_id)
    fr = _landing_table("fishing_records", well_id)
    bt = _landing_table("barrier_tests", well_id)

    if not fr.empty and "event_date" in fr.columns:
        fr = fr[fr["event_date"] <= settings.AS_OF]
    if not bt.empty and "test_date" in bt.columns:
        bt = bt[bt["test_date"] <= settings.AS_OF]

    s = res["summary"]
    assert s["wellhead_class"] == int(wh.iloc[0]["wellhead_class_psi"])
    assert s["hazard_class"] == str(fh.iloc[0]["hazard_class"])
    assert s["fishing_count"] == len(fr)

    for b, g in bt.groupby("barrier"):
        last = g.sort_values("test_date").iloc[-1]
        assert s["latest_barrier_tests"][str(b)]["result"] == str(last["result"])

    assert currency_keys(res) == []


def test_unknown_well_returns_unavailable():
    assert tubing_tally("ZZ-999").status == ToolStatus.UNAVAILABLE
    assert deviation_survey("ZZ-999").status == ToolStatus.UNAVAILABLE
    assert integrity("ZZ-999").status == ToolStatus.UNAVAILABLE


@pytest.mark.parametrize("well_id", TEST_WELLS)
def test_routes_200_valid_well(client, well_id: str):
    r1 = client.get(f"/api/wells/{well_id}/tubing-tally")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["well_id"] == well_id
    assert d1["is_synthetic"] is True
    assert "rows" in d1 and "summary" in d1

    r2 = client.get(f"/api/wells/{well_id}/deviation")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["well_id"] == well_id
    assert d2["is_synthetic"] is True
    assert "rows" in d2 and "summary" in d2

    r3 = client.get(f"/api/wells/{well_id}/integrity")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["well_id"] == well_id
    assert d3["is_synthetic"] is True
    assert "rows" in d3 and "summary" in d3


@pytest.mark.parametrize("bad_id", ["ZZ-999", "NOPE-000", "GLK-101"])
def test_routes_404_unknown_or_retired_well(client, bad_id: str):
    assert client.get(f"/api/wells/{bad_id}/tubing-tally").status_code == 404
    assert client.get(f"/api/wells/{bad_id}/deviation").status_code == 404
    assert client.get(f"/api/wells/{bad_id}/integrity").status_code == 404
