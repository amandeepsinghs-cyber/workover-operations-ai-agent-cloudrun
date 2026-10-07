"""TC-028 field_production_history (Gate T item 2; BDD-F11-S01/S03) — reconciles to well sums and to the
Gold ``field_kpi_monthly`` definitions (lakehouse/dataform/definitions/gold/field_kpi_monthly.sqlx)."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest

from app import settings
from app.analytics.tools.common import ToolStatus, currency_keys, load_table
from app.analytics.tools.field_history import field_production_history


@pytest.fixture(scope="module")
def hist():
    return field_production_history()


def _gold_reference(field: str) -> pd.DataFrame:
    """Pandas transcription of the Gold SQLX (COALESCE→fillna(0); days = distinct dates; AVG(runtime))."""
    d = load_table("daily_production", field)
    d = d[d["production_date"] <= settings.AS_OF].copy()
    d["month"] = pd.to_datetime(d["production_date"]).dt.to_period("M").dt.start_time.dt.date
    for c in ("oil_rate_bopd", "water_rate_bwpd", "gas_rate_mscfd", "liquid_rate_blpd", "runtime_fraction"):
        d[c] = d[c].fillna(0.0)
    d["is_producing"] = d["is_producing"].fillna(False).astype(bool)
    g = d.groupby("month").agg(days=("production_date", "nunique"), wells=("well_id", "nunique"),
                               oil=("oil_rate_bopd", "sum"), water=("water_rate_bwpd", "sum"),
                               gas=("gas_rate_mscfd", "sum"), liquid=("liquid_rate_blpd", "sum"),
                               pwd=("is_producing", "sum"), rf=("runtime_fraction", "mean")).reset_index()
    g["oil_bopd"] = g.oil / g.days
    g["gas_mscfd"] = g.gas / g.days
    g["water_cut_pct"] = g.water / (g.oil + g.water) * 100
    g["producing_wells"] = g.pwd / g.days
    g["uptime_pct"] = g.rf * 100
    t = load_table("field_targets")
    t = t[t.field == field][["month", "target_oil_bopd"]]
    return g.merge(t, on="month", how="left")


def test_60_monthly_points_per_field(hist):
    assert hist.status == ToolStatus.OK
    v = hist.value
    assert set(v.fields) == {"Geleki", "Lakwa", "Lakhmani"}
    assert Counter(r["field"] for r in v.series) == {"Geleki": 60, "Lakwa": 60, "Lakhmani": 60}
    for r in v.series:
        for k in ("oil_bopd", "water_cut_pct", "gas_mscfd"):
            assert r[k] is not None
    last = [r for r in v.series if r["field"] == "Lakwa"][-1]
    assert last["period"].isoformat() == "2026-09-01" and last["is_partial"] is True
    assert last["days_in_period"] == settings.AS_OF.day


def test_reconciles_to_well_sums_within_0_1pct(hist):
    """BDD-F11-S03: field monthly oil = Σ wells' daily oil / days in month (± 0.1 %)."""
    for rc in hist.value.reconciliation:
        assert rc["max_rel_error_pct"] <= 0.1 and rc["periods_checked"] == 60
    for fld in hist.value.fields:
        d = load_table("daily_production", fld)
        d = d[d["production_date"] <= settings.AS_OF].copy()
        d["month"] = pd.to_datetime(d["production_date"]).dt.to_period("M").dt.start_time.dt.date
        per_well = d.groupby(["month", "well_id"])["oil_rate_bopd"].sum().groupby(level=0).sum()
        days = d.groupby("month")["production_date"].nunique()
        for r in (x for x in hist.value.series if x["field"] == fld):
            ref = per_well[r["period"]] / days[r["period"]]
            assert abs(r["oil_bopd"] - ref) / ref <= 1e-3


@pytest.mark.parametrize("field", ["Geleki", "Lakwa", "Lakhmani"])
def test_matches_gold_field_kpi_monthly_definitions(hist, field):
    gold = _gold_reference(field).set_index("month")
    rows = [r for r in hist.value.series if r["field"] == field]
    assert len(rows) == len(gold) == 60
    for r in rows:
        g = gold.loc[r["period"]]
        assert r["days_in_period"] == g.days and r["wells_reporting"] == g.wells
        assert r["oil_bbl"] == pytest.approx(g.oil, rel=1e-6, abs=0.06)
        assert r["oil_bopd"] == pytest.approx(g.oil_bopd, abs=0.051)
        assert r["gas_mscfd"] == pytest.approx(g.gas_mscfd, abs=0.051)
        assert r["water_cut_pct"] == pytest.approx(g.water_cut_pct, abs=0.006)
        assert r["producing_wells"] == pytest.approx(g.producing_wells, abs=0.051)
        assert r["uptime_pct"] == pytest.approx(g.uptime_pct, abs=0.051)
        assert r["target_oil_bopd"] == pytest.approx(g.target_oil_bopd, abs=0.051)


def test_summary_tells_start_end(hist):
    s = {x["field"]: x for x in hist.value.summary}
    for fld, x in s.items():
        assert x["n_periods"] == 60
        assert x["change_pct"] == pytest.approx((x["end_oil"] - x["start_oil"]) / x["start_oil"] * 100, abs=0.06)
        assert x["wc_change_pp"] is not None and x["end_producing_wells"] is not None
    assert all(k in hist.message for k in ("Geleki", "Lakwa", "Lakhmani"))


def test_freq_and_subset():
    r = field_production_history(fields="Lakwa", freq="Q")
    assert r.status == ToolStatus.OK and r.value.fields == ["Lakwa"]
    assert len(r.value.series) == 20  # 2021-Q4 .. 2026-Q3
    assert currency_keys(r.value) == []


def test_unknown_field_refused():
    r = field_production_history(fields=["Rudrasagar"])
    assert r.status == ToolStatus.UNAVAILABLE and "fields" in r.missing_fields
    assert "Geleki" in r.message
