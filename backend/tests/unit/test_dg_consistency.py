"""Gate DG: cross-table consistency of the written synthetic data-gap parquet (F-22, D-29)."""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.generator.dg.common import FIELDS, LANDING, SOURCE_SYSTEM, load_field
from app.analytics.generator.dg import tubing_deviation, integrity, hazards_fishing

DG_TABLES = ("tubing_tally", "deviation_survey", "barrier_tests", "wellhead_rating",
             "fluid_hazards", "fishing_records")
PER_WELL_FULL = ("deviation_survey", "wellhead_rating", "fluid_hazards")


def _read(field: str, table: str) -> pd.DataFrame:
    p = LANDING / field / f"{table}.parquet"
    if not p.exists():
        pytest.skip(f"{p} not generated; run `python -m app.analytics.generator.dg --field all`")
    return pd.read_parquet(p)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("table", DG_TABLES)
def test_lineage_and_synthetic_flag(field, table):
    df = _read(field, table)
    assert len(df) > 0
    assert df["is_synthetic"].all()
    assert (df["_source_system"] == SOURCE_SYSTEM).all()
    assert df["well_id"].notna().all()


@pytest.mark.parametrize("field", FIELDS)
def test_coverage(field):
    wells = set(pd.read_parquet(LANDING / field / "well_master.parquet")["well_id"])
    for t in PER_WELL_FULL:
        assert set(_read(field, t)["well_id"]) == wells, t
    ts = pd.read_parquet(LANDING / field / "tubing_string.parquet")
    assert set(_read(field, "tubing_tally")["well_id"]) == set(ts["well_id"]) & wells
    for t in DG_TABLES:
        assert set(_read(field, t)["well_id"]) <= wells, f"{t} has unknown wells"


@pytest.mark.parametrize("field", FIELDS)
def test_tally_matches_tubing_and_survey_matches_td(field):
    wm = pd.read_parquet(LANDING / field / "well_master.parquet").set_index("well_id")
    tally = _read(field, "tubing_tally")
    ts = pd.read_parquet(LANDING / field / "tubing_string.parquet")
    deepest = (ts["top_m"] + ts["length_m"]).groupby(ts["well_id"]).max()
    bottom = tally.groupby("well_id")["bottom_md_m"].max()
    # Tally never extends beyond the deepest recorded tubing component.
    assert (bottom <= deepest.reindex(bottom.index) + 0.01).all()
    dev = _read(field, "deviation_survey")
    last = dev.sort_values("md_m").groupby("well_id").tail(1).set_index("well_id")
    assert ((last["md_m"] - wm.loc[last.index, "total_depth_md_m"]).abs() < 0.01).all()
    assert (dev["tvd_m"] <= dev["md_m"] + 0.01).all()


@pytest.mark.parametrize("field", FIELDS)
def test_regeneration_is_deterministic(field):
    ctx = load_field(field)
    for mod in (tubing_deviation, integrity, hazards_fishing):
        for table, df in mod.generate(ctx).items():
            on_disk = _read(field, table)[list(df.columns)].reset_index(drop=True)
            pd.testing.assert_frame_equal(df.reset_index(drop=True), on_disk,
                                          check_dtype=False, check_exact=False, rtol=1e-9)
