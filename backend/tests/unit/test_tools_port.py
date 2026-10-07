"""Stage P · ADK v0.3.0 tool-contract port (``workover_well_intervention/tests/test_contracts.py``).

The v0.3.0 tests asserted hard-coded fixture values for the seven demo wells. The WellPulse port is
data-driven (no per-well constants), so each contract is re-stated on what the data supports; where
the data-driven value deliberately differs from the v0.3.0 fixture the test documents it (see the
Stage P report: GK-087 Trigger B / ROD_PART, GK-141 injector mechanism, Trigger D percentile).
"""

from __future__ import annotations

import inspect

import pytest

from app.analytics import tools as T
from app.analytics.tools.arps_decline import fit_decline_curve
from app.analytics.tools.candidate_ranking import (
    check_mro,
    check_offsets,
    detect_mechanical_signature,
    generate_draft_plan,
    plot_production,
    query_wells,
    rank_candidates,
    route_intervention,
    trigger_scan,
)
from app.analytics.tools.chan_diagnostic import chan_diagnostic
from app.analytics.tools.common import OffsetVerdict, ToolStatus, currency_keys


# --- TC-001 ---------------------------------------------------------------------------------------
def test_tc001_gk129_residual_below_minus_25():
    r = fit_decline_curve("GK-129")
    assert r.status == ToolStatus.OK
    assert r.value.residual_pct < -25.0
    assert r.provenance["tool_id"] == "TC-001" and r.provenance["as_of"]


def test_tc001_fallback_only_replaces_low_fits():
    """Stage P fallback: OK full-window fits are never replaced (Geleki unchanged); LOW multi-cycle fits may be
    refitted since the last workover, and the refit is used only if it is itself not LOW."""
    from app.analytics.tools.common import field_well_ids

    for wid in field_well_ids("Geleki"):
        v = fit_decline_curve(wid).value
        if v is not None:
            assert v.fit_basis == "FULL_WINDOW", wid
    refits = [fit_decline_curve(w) for w in field_well_ids("Lakhmani")]
    used = [r for r in refits if r.value is not None and r.value.fit_basis.startswith("SINCE_LAST_WORKOVER")]
    assert used and all(r.status == ToolStatus.OK and r.value.r_squared >= 0.5 for r in used)


def test_tc001_unknown_well_unavailable():
    assert fit_decline_curve("ZZ-999").status == ToolStatus.UNAVAILABLE


# --- TC-002 ---------------------------------------------------------------------------------------
def test_tc002_gk129_channelling():
    v = chan_diagnostic("GK-129").value
    assert v.mechanism.value == "CHANNELLING"
    assert v.wor_prime_slope > 0.30
    assert v.paired_injectors == []  # no injector table in v0.4: never invented


def test_tc002_gk103_coning():
    assert chan_diagnostic("GK-103").value.mechanism.value == "CONING"


# --- TC-004 / TC-008 ------------------------------------------------------------------------------
def test_tc004_tc008_gk141_reservoir_decline_no_job():
    off = check_offsets("GK-141").value
    assert off.verdict == OffsetVerdict.RESERVOIR_DECLINE
    route = route_intervention("GK-141", None, off.verdict).value
    assert route.job_code == "NO_JOB_JUSTIFIED"


def test_tc008_channelling_routes_to_cement_squeeze():
    route = route_intervention("GK-129", "CHANNELLING", OffsetVerdict.WELL_SPECIFIC).value
    assert route.job_code == "CEMENT_SQUEEZE" and route.requires_rig


# --- TC-005 ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("well,sig", [("GK-055", "PUMP_WEAR"), ("GK-112", "SCALE"), ("GK-147", "WAX")])
def test_tc005_signatures_from_data(well, sig):
    assert detect_mechanical_signature(well).value.signature.value == sig


# --- TC-007 ---------------------------------------------------------------------------------------
def test_tc007_geleki_bdd_wells():
    rows = {r.well_id: r for r in trigger_scan("Geleki").value}
    assert rows["GK-129"].trigger_a == "FLAG" and rows["GK-129"].trigger_c == "CHANNELLING"
    assert rows["GK-112"].trigger_a == "FLAG" and rows["GK-112"].trigger_c == "SCALE"
    assert rows["GK-103"].trigger_c == "CONING"
    assert rows["GK-055"].trigger_c == "PUMP_WEAR"
    assert rows["GK-147"].trigger_c == "WAX"
    # data-driven deviation from the v0.3.0 fixture (documented): GK-087's own run lives (179/302/354 d)
    # put its p50 far above days-since-job, so Trigger B does not fire, and no ROD_PART signal exists.
    assert rows["GK-087"].any_fired is False


def test_tc007_unknown_field():
    assert trigger_scan("Atlantis").status == ToolStatus.UNAVAILABLE


# --- TC-010 ---------------------------------------------------------------------------------------
def test_tc010_rank_without_rupees():
    q = rank_candidates("Geleki").value
    assert q.rig_queue and q.rigless_queue
    assert all(r.cost_band in ("LOW", "MED", "HIGH") for r in q.rig_queue + q.rigless_queue)
    assert currency_keys(q) == []
    refused = {r.well_id if hasattr(r, "well_id") else r[0] for r in q.excluded_refusals}
    assert "GK-141" in refused


# --- TC-011 / TC-013 ------------------------------------------------------------------------------
def test_tc011_mro_returns_feasible_start():
    r = check_mro("CEMENT_SQUEEZE")
    assert r.status == ToolStatus.OK
    assert r.value["earliest_feasible_start"] is not None


def test_tc013_draft_plan_awaits_review():
    plan = generate_draft_plan("GK-129").value
    assert plan["approval_status"] == "AWAITING REVIEW"
    assert currency_keys(plan) == []


# --- TC-017 / TC-018 ------------------------------------------------------------------------------
def test_tc017_plot_has_null_gaps_and_markers():
    ps = plot_production("GK-129").value
    assert ps.n_producing_days > 90
    assert all(p.value is None for p in ps.series["oil"] if p.source == "NULL")
    assert all(m.outcome in ("SUCCESS", "PARTIAL", "FAILED", "UNKNOWN") for m in ps.interventions)


def test_tc018_rate_ranking_has_caveat():
    assert query_wells("Geleki", order_by="oil_rate_bopd").value.caveat
    assert query_wells("Geleki").value.caveat is None


# --- cross-cutting: K-6 (no hero defaults), D-1 (no currency) --------------------------------------
def test_no_gk129_or_geleki_defaults_anywhere():
    for name in T.__all__:
        fn = getattr(T, name)
        if not callable(fn):
            continue
        for p in inspect.signature(fn).parameters.values():
            d = p.default
            if isinstance(d, str):
                assert "GK-" not in d.upper() and "GELEKI" not in d.upper(), (name, p.name, d)


def test_exports_cover_tc001_to_tc020():
    expected = {"fit_decline_curve", "chan_diagnostic", "fillage_proxy", "check_offsets",
                "detect_mechanical_signature", "predict_failure", "trigger_scan", "route_intervention",
                "estimate_uplift", "rank_candidates", "check_mro", "search_well_history", "generate_draft_plan",
                "generate_report", "schedule_rigs", "plot_production", "query_wells", "attribute_decline",
                "classify_well_health"}
    assert expected <= set(T.__all__)


@pytest.mark.parametrize("call", [
    lambda: fit_decline_curve("LKW-047"), lambda: chan_diagnostic("LKM-090"), lambda: check_offsets("LKW-088"),
    lambda: detect_mechanical_signature("GK-055"), lambda: trigger_scan("Lakhmani"),
    lambda: query_wells("Lakwa"), lambda: plot_production("LKW-047"),
])
def test_no_currency_keys_in_tool_values(call):
    assert currency_keys(call().value) == []
