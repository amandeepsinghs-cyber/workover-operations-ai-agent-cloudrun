"""Stage P · TC-019 decline attribution (BDD F-01, SDD §7) — Gate P items 1, 2, 6.

Numbers asserted here are the measured TC-019 outputs pinned at Gate P (docs/pinned_values.md §8);
the structural assertions (conservation, classes, flags) are the BDD contract.
"""

from __future__ import annotations

import pytest

from app import settings
from app.analytics.tools.attribution import CONTROLLABLE, NO_ACTION_FLAG, _well_cached, attribute_decline
from app.analytics.tools.common import ToolStatus, currency_keys, field_well_ids

FIELDS = ("Geleki", "Lakwa", "Lakhmani")


def _comp(v, cls: str, sub: str):
    return next((c for c in v.components if c.factor_class == cls and c.sub_factor == sub), None)


@pytest.mark.parametrize("field", FIELDS)
def test_waterfall_reconciles_for_every_well(field):
    """Gate P1 / BDD-F01-S01: Σ components − gains = total lost oil within 0.5 % for every well."""
    checked = 0
    for wid in field_well_ids(field):
        r = _well_cached(wid, settings.AS_OF, 180)
        if r.value is None:
            assert r.status in (ToolStatus.INSUFFICIENT_HISTORY, ToolStatus.UNAVAILABLE), wid
            continue
        v = r.value
        s = sum(c.bbl for c in v.components) - v.gains_bbl
        tol = max(0.005 * abs(v.total_loss_bbl), 0.1)  # 0.1 bbl = display rounding on near-zero totals
        assert abs(s - v.total_loss_bbl) <= tol, (wid, s, v.total_loss_bbl)
        assert v.reconciliation_error_pct <= 0.5, wid
        assert all(c.bbl > 0 for c in v.components) and all(g.bbl > 0 for g in v.gains), wid
        checked += 1
    assert checked >= len(field_well_ids(field)) - 15  # only wells with no pre-window production are skipped


def test_lkw047_human_process_dominates():
    """BDD-F01-S01: largest class HUMAN_PROCESS incl. WAIT_ON_RIG 41 d + WAIT_ON_MATERIAL 12 d; PUMP_WEAR in EQUIPMENT."""
    r = attribute_decline(well_id="LKW-047", window_days=180)
    v = r.value
    assert r.status == ToolStatus.OK
    assert v.largest_class == "HUMAN_PROCESS"
    rig, mat = _comp(v, "HUMAN_PROCESS", "WAIT_ON_RIG"), _comp(v, "HUMAN_PROCESS", "WAIT_ON_MATERIAL")
    assert rig is not None and rig.days == 41
    assert mat is not None and mat.days == 12
    assert _comp(v, "EQUIPMENT", "PUMP_WEAR") is not None
    # human factor = a function, never a person
    assert rig.responsible_function == "Rig Planning"
    assert mat.responsible_function and "Materials" in mat.responsible_function
    assert v.controllable_pct >= 80.0


def test_lkm090_pure_reservoir_decline_is_uncontrollable():
    """BDD-F01-S03 (pinned at Gate P): SUBSURFACE ≥ 80 %, controllable ≤ 15 %, NO_OPERATIONAL_ACTION flag."""
    v = attribute_decline(well_id="LKM-090", window_days=180).value
    assert v.subsurface_pct >= 80.0
    assert v.controllable_pct <= 15.0
    assert NO_ACTION_FLAG in v.flags
    assert _comp(v, "SUBSURFACE", "RESERVOIR_DECLINE") is not None


def test_lkw088_grid_outage_is_external():
    """BDD-F01-S04: GRID_POWER_OUTAGE classed EXTERNAL and excluded from the controllable share."""
    v = attribute_decline(well_id="LKW-088", window_days=180).value
    g = _comp(v, "EXTERNAL", "GRID_POWER_OUTAGE")
    assert g is not None and g.controllable is False
    assert "EXTERNAL" not in CONTROLLABLE
    ctrl = sum(c.bbl for c in v.components if c.controllable)
    assert abs(100.0 * ctrl / v.gross_loss_bbl - v.controllable_pct) < 0.2


def test_unexplained_surfaces_as_low_confidence():
    """BDD-F01-S05: if UNEXPLAINED > 15 % the status is LOW_CONFIDENCE and the component is returned."""
    seen = 0
    for field in FIELDS:
        for wid in field_well_ids(field):
            r = _well_cached(wid, settings.AS_OF, 180)
            if r.value is None:
                continue
            if r.value.unexplained_pct > 15.0:
                assert r.status == ToolStatus.LOW_CONFIDENCE, wid
                assert any(c.factor_class == "UNEXPLAINED" for c in r.value.components + r.value.gains), wid
                seen += 1
            else:
                assert r.status == ToolStatus.OK, wid
    assert seen >= 1  # e.g. LKW-088 (flat E: TC-001 fit LOW_CONFIDENCE)


def test_lakwa_field_rollup_equals_sum_of_wells():
    """BDD-F01-S06: field total = Σ well totals (±0.5 %); controllable share pinned ≥ 40 %."""
    r = attribute_decline(field="Lakwa", window_days=90)
    v = r.value
    total = sum(w["total_loss_bbl"] for w in v.wells)
    assert abs(total - v.total_loss_bbl) <= 0.005 * abs(v.total_loss_bbl)
    assert abs(sum(c.bbl for c in v.components) - v.gains_bbl - v.total_loss_bbl) <= 0.005 * abs(v.total_loss_bbl)
    assert v.controllable_pct >= 40.0
    assert len(v.wells) + len(v.wells_excluded) == 160


def test_cluster_rollup_and_unknowns():
    r = attribute_decline(field="Lakwa", cluster_id="LKW-GGS-I", window_days=90)
    assert r.value is not None and r.value.scope == "CLUSTER"
    assert attribute_decline(field="Atlantis").status == ToolStatus.UNAVAILABLE
    assert attribute_decline().status == ToolStatus.UNAVAILABLE
    assert attribute_decline(well_id="LKW-047", window_days=3).status == ToolStatus.UNAVAILABLE
    assert attribute_decline(well_id="ZZ-001").status == ToolStatus.UNAVAILABLE


def test_no_currency_in_attribution():
    for kw in ({"well_id": "LKW-047"}, {"field": "Geleki"}):
        assert currency_keys(attribute_decline(**kw).value) == []


# ------------------------------------------------------------------------------------------------
# REST
# ------------------------------------------------------------------------------------------------
def test_api_well_attribution(client):
    resp = client.get("/api/wells/LKW-047/attribution?window_days=180")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"status", "data", "message", "missing_fields", "provenance"}
    d = body["data"]
    assert d["largest_class"] == "HUMAN_PROCESS"
    s = sum(c["bbl"] for c in d["components"]) - d["gains_bbl"]
    assert abs(s - d["total_loss_bbl"]) <= 0.005 * abs(d["total_loss_bbl"])
    assert body["provenance"]["tool_id"] == "TC-019"
    assert client.get("/api/wells/GLK-129/attribution").status_code == 404
    assert client.get("/api/wells/NOPE-000/attribution").status_code == 404


def test_api_field_attribution_persona(client):
    ok = client.get("/api/fields/Lakwa/attribution?window_days=90")  # default persona ASSET_MANAGER
    assert ok.status_code == 200 and ok.json()["data"]["scope"] == "FIELD"
    assert client.get("/api/fields/Lakwa/attribution", headers={"X-Persona": "ED"}).status_code == 200
    fe = client.get("/api/fields/Lakwa/attribution", headers={"X-Persona": "FIELD_ENGINEER"})
    assert fe.status_code == 403 and fe.json()["status"] == "UNAVAILABLE"
    assert client.get("/api/fields/Atlantis/attribution").status_code == 404
