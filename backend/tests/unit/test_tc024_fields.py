"""TC-024 compare_fields (Gate T item 1; BDD-F09-S01/S03/S05)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app import settings
from app.analytics.generator.validate import GAP_TARGET
from app.analytics.tools.common import ToolStatus, currency_keys, load_table, to_jsonable
from app.analytics.tools.field_performance import compare_fields, period_window

CONTROLLABLE = {"HUMAN_PROCESS", "OPERATIONAL", "EQUIPMENT"}
ROW_KEYS = {"actual_bopd", "target_bopd", "gap_pct", "expected_bopd", "uptime_pct", "water_cut_pct",
            "health_counts", "deferred_by_factor", "active_interventions", "rig_candidates", "rigless_candidates"}


@pytest.fixture(scope="module")
def qtd():
    return compare_fields()


def test_lakwa_worst_in_pinned_band_with_controllable_driver(qtd):
    assert qtd.status == ToolStatus.OK
    v = qtd.value
    assert v.period == "QTD" and v.window_start == date(2026, 7, 1) and v.window_end == settings.AS_OF
    assert v.worst_field == "Lakwa" and v.ranking[0] == "Lakwa"
    lakwa = next(r for r in v.rows if r["field"] == "Lakwa")
    tgt, tol = GAP_TARGET["Lakwa"]
    assert abs(lakwa["gap_pct"] - tgt * 100) <= tol * 100
    assert lakwa["in_pinned_band"] is True
    assert v.top_driver["field"] == "Lakwa"
    assert v.top_driver["factor_class"] in CONTROLLABLE and v.top_driver["controllable"] is True
    # the driver is the largest class of the TC-019 rollup, not picked for being controllable
    assert v.top_driver["factor_class"] == max(lakwa["deferred_by_factor"], key=lakwa["deferred_by_factor"].get)


def test_every_field_in_its_pinned_band(qtd):
    for r in qtd.value.rows:
        tgt, tol = GAP_TARGET[r["field"]]
        assert abs(r["gap_pct"] - tgt * 100) <= tol * 100 + 1e-9, r["field"]


def test_gap_matches_independent_daily_definition(qtd):
    """gap = Σ actual / Σ daily target − 1 over the window (generator.targets.gap_vs_target)."""
    s, e = period_window("QTD", settings.AS_OF)
    t = load_table("field_targets")
    for r in qtd.value.rows:
        d = load_table("daily_production", r["field"])
        d = d[(d["production_date"] >= s) & (d["production_date"] <= e)]
        tm = {pd.Timestamp(m).to_period("M"): v for m, v in zip(t[t.field == r["field"]]["month"],
                                                                  t[t.field == r["field"]]["target_oil_bopd"])}
        tg = sum(tm[x.to_period("M")] for x in pd.date_range(s, e))
        assert round((d["oil_rate_bopd"].sum() / tg - 1) * 100, 1) == r["gap_pct"]


def test_kpi_completeness_ws1(qtd):
    for r in qtd.value.rows:
        assert ROW_KEYS <= set(r), ROW_KEYS - set(r)
        assert set(r["health_counts"]) == {"PRODUCING_OK", "AT_RISK", "UNDERPERFORMING", "NOT_PRODUCING"}
        assert sum(r["health_counts"].values()) == r["n_wells"]
        assert isinstance(r["active_interventions"], int) and r["active_interventions"] >= 0
        assert r["rig_candidates"] is not None and r["rigless_candidates"] is not None


def test_active_interventions_are_open_under_workover_episodes(qtd):
    s = load_table("well_status_history", "Lakwa")
    a = settings.AS_OF
    cur = s[(s["start_date"] <= a) & (s["end_date"].isna() | (s["end_date"] >= a))]
    cur = cur.sort_values("start_date").groupby("well_id").tail(1)
    lakwa = next(r for r in qtd.value.rows if r["field"] == "Lakwa")
    assert lakwa["active_interventions"] == int((cur["status"] == "UNDER_WORKOVER").sum())


def test_no_currency_and_jsonable(qtd):
    assert currency_keys(qtd.value) == []
    to_jsonable(qtd.value)


def test_bad_inputs_unavailable():
    assert compare_fields(period="WEEK").status == ToolStatus.UNAVAILABLE
    r = compare_fields(asset="NORTH_SEA")
    assert r.status == ToolStatus.UNAVAILABLE and "asset" in r.missing_fields


def test_missing_target_excluded(monkeypatch):
    """BDD-F09-S05: no field_targets row → gap UNAVAILABLE and the field leaves the ranking."""
    from app.analytics.tools import field_performance as fp

    real = fp.load_table

    def fake(name, field=None):
        df = real(name, field)
        if name == "field_targets":
            return df[df["field"] != "Geleki"]
        return df

    fp._field_row.cache_clear()
    monkeypatch.setattr(fp, "load_table", fake)
    try:
        r = compare_fields(period="MTD")
        assert "Geleki" not in r.value.ranking
        assert any(e["field"] == "Geleki" for e in r.value.excluded)
        assert next(x for x in r.value.rows if x["field"] == "Geleki")["gap_pct"] == "UNAVAILABLE"
        assert r.status == ToolStatus.LOW_CONFIDENCE
    finally:
        fp._field_row.cache_clear()
