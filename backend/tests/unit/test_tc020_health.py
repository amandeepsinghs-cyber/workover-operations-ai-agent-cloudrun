"""Stage P · TC-020 well-health buckets (BDD F-02, SDD §6.3) — Gate P item 3."""

from __future__ import annotations

import pytest

from app.analytics.tools.common import ToolStatus, currency_keys
from app.analytics.tools.health import BUCKETS, all_fields_counts, classify_well_health, well_health

TOTALS = {"Geleki": 142, "Lakwa": 160, "Lakhmani": 110}


@pytest.mark.parametrize("field,total", sorted(TOTALS.items()))
def test_every_well_in_exactly_one_bucket(field, total):
    r = classify_well_health(field)
    assert r.status == ToolStatus.OK
    v = r.value
    ids = [w.well_id for w in v.wells]
    assert len(ids) == len(set(ids)) == total
    assert sum(v.counts.values()) == total
    assert set(v.counts) == set(BUCKETS)
    assert v.sick_or_lost_count == v.counts["AT_RISK"] + v.counts["UNDERPERFORMING"]
    for w in v.wells:
        assert w.bucket in BUCKETS and w.reason
        if w.bucket == "NOT_PRODUCING":
            assert w.reason_code and isinstance(w.recoverable, bool), w.well_id


def test_buckets_follow_the_rules():
    """NOT_PRODUCING ⇔ open non-PRODUCING episode; UNDERPERFORMING ⇔ 7-day residual ≤ −20 %; AT_RISK ⇔ B/C/D."""
    from app import settings
    from app.analytics.tools.candidate_ranking import trigger_a_state
    from app.analytics.tools.health import _open_episode

    v = classify_well_health("Geleki").value
    for w in v.wells:
        ep = _open_episode(w.well_id, settings.AS_OF)
        assert (w.bucket == "NOT_PRODUCING") == (ep is None or ep["status"] != "PRODUCING"), w.well_id
        if w.bucket == "UNDERPERFORMING":
            assert trigger_a_state(w.well_id, settings.AS_OF)["max_last7_pct"] <= -20.0
        if w.bucket == "AT_RISK":
            assert w.triggers.get("b") or w.triggers.get("c") or w.triggers.get("d"), w.well_id
    # Geleki BDD wells (data-driven; see report for deviations from the v0.3.0 fixtures)
    b = {w.well_id: w.bucket for w in v.wells}
    assert b["GK-129"] == "UNDERPERFORMING"   # residual −30.6 %, CHANNELLING
    assert b["GK-112"] == "UNDERPERFORMING"   # residual −37.4 %, SCALE
    assert b["GK-103"] == "AT_RISK"           # CONING signature + run life


def test_cluster_filter_and_unknown_field():
    r = classify_well_health("Lakwa", cluster_id="LKW-GGS-I")
    assert r.value is not None and all(w.cluster_id == "LKW-GGS-I" for w in r.value.wells)
    assert classify_well_health("Atlantis").status == ToolStatus.UNAVAILABLE
    assert classify_well_health("Lakwa", cluster_id="NOPE").status == ToolStatus.UNAVAILABLE


def test_well_health_lookup_and_no_currency():
    assert well_health("LKW-047").bucket in BUCKETS
    assert well_health("ZZ-001") is None
    assert currency_keys(classify_well_health("Lakhmani").value) == []


# ------------------------------------------------------------------------------------------------
# REST: /api/wells/kpis == TC-020 counts; /api/wells buckets; /api/fields/{f}/health
# ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("field,total", sorted(TOTALS.items()))
def test_kpis_equal_tc020_counts(client, field, total):
    k = client.get(f"/api/wells/kpis?field={field}").json()
    c = classify_well_health(field).value.counts
    assert k["total_wells"] == total
    assert k["healthy_count"] == c["PRODUCING_OK"]
    assert k["warning_count"] == c["AT_RISK"] + c["UNDERPERFORMING"]
    assert k["failed_count"] == c["NOT_PRODUCING"]
    assert k["field"] == field
    assert k["at_risk_count"] == c["AT_RISK"]
    assert k["underperforming_count"] == c["UNDERPERFORMING"]
    assert k["not_producing_count"] == c["NOT_PRODUCING"]


def test_kpis_all_fields(client):
    k = client.get("/api/wells/kpis").json()
    c = all_fields_counts()
    assert k["total_wells"] == sum(TOTALS.values())
    assert k["healthy_count"] == c["PRODUCING_OK"] and k["failed_count"] == c["NOT_PRODUCING"]
    assert k["field"] == "ALL" and k["at_risk_count"] == c["AT_RISK"]
    assert k["underperforming_count"] == c["UNDERPERFORMING"] and k["not_producing_count"] == c["NOT_PRODUCING"]


def test_wells_list_uses_tc020(client):
    wells = client.get("/api/wells").json()
    for w in wells[:50]:
        assert w["health_rule"] == "TC-020"
        assert w["health_bucket"] == well_health(w["id"]).bucket


def test_api_field_health(client):
    resp = client.get("/api/fields/Lakhmani/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK" and sum(body["data"]["counts"].values()) == 110
    assert body["provenance"]["tool_id"] == "TC-020"
    assert client.get("/api/fields/Lakhmani/health?cluster_id=LKM-GGS-I").json()["data"]["cluster_id"] == "LKM-GGS-I"
    assert client.get("/api/fields/Atlantis/health").status_code == 404
