"""Stage Y — RBAC (F-16, SDD §16) and multi-field GIS API contracts (F-17). Gate Y evidence.

Run: ``uv run pytest tests/unit/test_rbac.py -q``
"""

from __future__ import annotations

import pytest

from app.agent import rbac
from app.analytics.tools.common import ToolResult, ToolStatus

ED, AM, FE = "ED", "ASSET_MANAGER", "FIELD_ENGINEER"
H = {p: {"X-Persona": p} for p in (ED, AM, FE)}


# ------------------------------------------------------------------------------------------------ matrix
def test_rbac_matrix_matches_sdd_16_2():
    expected = {  # SDD §16.2 (✔ = FULL, summary = SUMMARY, own cluster = OWN_CLUSTER, ✘ = NONE)
        "field.aggregate": ("FULL", "FULL", "NONE"),
        "field.attribution": ("FULL", "FULL", "NONE"),
        "well.attribution": ("FULL", "FULL", "FULL"),
        "field.health": ("FULL", "FULL", "OWN_CLUSTER"),
        "queue.read": ("FULL", "FULL", "OWN_CLUSTER"),
        "well.diagnostics": ("SUMMARY", "FULL", "FULL"),
        "well.nba": ("FULL", "FULL", "FULL"),
        "well.construction": ("SUMMARY", "FULL", "FULL"),
        "docs.sop_dossier": ("FULL", "FULL", "FULL"),
        "cost_band.view": ("FULL", "FULL", "NONE"),
        "live.voice": ("FULL", "FULL", "FULL"),
    }
    for cap, (ed, am, fe) in expected.items():
        assert (rbac.access(ED, cap).value, rbac.access(AM, cap).value, rbac.access(FE, cap).value) == (ed, am, fe), cap
    assert rbac.capability_for_tool("TC-024") == "field.aggregate"
    assert rbac.capability_for_tool("TC-019") == "field.attribution"
    assert rbac.capability_for_tool("TC-019", well_scope=True) == "well.attribution"
    assert rbac.capability_for_tool("TC-029") == "well.construction"


def test_rbac_persona_resolution():
    assert rbac.resolve_persona(None) == AM and rbac.resolve_persona("") == AM  # SDD §13.1 default
    assert rbac.resolve_persona("production_engineer") == AM  # PE → ASSET_MANAGER (D-8)
    assert rbac.resolve_persona("fe") == FE and rbac.resolve_persona("Executive Director") == ED
    assert rbac.resolve_persona("nope") == AM
    with pytest.raises(rbac.UnknownPersona):
        rbac.resolve_persona("nope", strict=True)


def test_rbac_me_capabilities_matches_matrix(client):
    for p in (ED, AM, FE):
        r = client.get("/api/me/capabilities", headers=H[p])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["persona"] == p
        assert d["access"] == {c: rbac.MATRIX[c][p].value for c in rbac.MATRIX}
        assert set(d["capabilities"]) == {c for c in rbac.MATRIX if rbac.MATRIX[c][p] is not rbac.Access.NONE}
    assert client.get("/api/me/capabilities").json()["data"]["persona"] == AM
    fe = client.get("/api/me/capabilities", headers=H[FE]).json()["data"]
    assert set(fe["denied"]) == {"field.aggregate", "field.attribution", "cost_band.view"}
    bad = client.get("/api/me/capabilities", headers={"X-Persona": "CEO"})
    assert bad.status_code == 400 and bad.json()["status"] == "UNAVAILABLE"


# ------------------------------------------------------------------------------------------------ REST gating
@pytest.mark.parametrize("path,cap", [
    ("/api/fields/compare", "field.aggregate"),
    ("/api/fields/history", "field.aggregate"),
    ("/api/fields/Lakwa/history", "field.aggregate"),
    ("/api/fields/Lakwa/attribution", "field.attribution"),
])
def test_rbac_field_engineer_denied_rollups(client, path, cap):
    r = client.get(path, headers=H[FE])
    assert r.status_code == 403
    body = r.json()
    assert body["status"] == "UNAVAILABLE" and body["data"] is None  # no data leak in the error
    assert body["message"] == f"not permitted for persona FIELD_ENGINEER: {cap}"
    for p in (ED, AM):
        ok = client.get(path, headers=H[p])
        assert ok.status_code == 200 and ok.json()["status"] == "OK", (p, path)


def test_rbac_field_engineer_gets_single_well_sop_documents(client):
    prof = client.get("/api/wells/LKW-047/profile", headers=H[FE])
    assert prof.status_code == 200 and prof.json()["status"] == "OK"
    assert isinstance(prof.json()["data"]["construction"]["casing"], list)  # full mechanical view incl. tallies
    assert client.get("/api/wells/LKW-047/production?months=24", headers=H[FE]).status_code == 200
    docs = client.get("/api/wells/LKW-047/documents", headers=H[FE]).json()
    assert docs["status"] == "OK" and {"D04"} <= {d["doc_type_id"] for d in docs["data"]}
    sop = client.get("/api/docs/search", params={"q": "gas lift valve change-out SOP", "doc_types": "D11"}, headers=H[FE])
    assert sop.status_code == 200 and sop.json()["data"] and all(h["doc_type_id"] == "D11" for h in sop.json()["data"])


def test_rbac_field_engineer_own_cluster_scoping(client):
    r = client.get("/api/fields/Lakwa/health", headers=H[FE])
    assert r.status_code == 403 and "own cluster" in r.json()["message"]
    ok = client.get("/api/fields/Lakwa/health?well_id=LKW-047", headers=H[FE]).json()
    full = client.get("/api/fields/Lakwa/health", headers=H[AM]).json()
    assert ok["status"] == "OK" and ok["data"]["cluster_id"] == "LKW-GGS-I"
    assert sum(ok["data"]["counts"].values()) < sum(full["data"]["counts"].values())
    pq = client.get("/api/fields/Lakwa/priority?well_id=LKW-047", headers=H[FE]).json()
    rows = pq["data"]["rig_queue"] + pq["data"]["rigless_queue"]
    assert rows and {x["cluster_id"] for x in rows} == {"LKW-GGS-I"}
    assert all("cost_band" not in x for x in rows)  # cost_band.view ✘ for FE
    am = client.get("/api/fields/Lakwa/priority", headers=H[AM]).json()
    assert all("cost_band" in x for x in am["data"]["rig_queue"])


def test_rbac_same_question_scoped_ed_vs_field_engineer(client):
    """BDD-F16-S01 (API level): 'Tell me about LKW-047' — ED: summary without casing tallies; FE: tallies."""
    ed = client.get("/api/wells/LKW-047/profile", headers=H[ED]).json()["data"]
    fe = client.get("/api/wells/LKW-047/profile", headers=H[FE]).json()["data"]
    assert ed["construction"]["tallies_redacted"] is True and "casing" not in ed["construction"]
    assert ed["construction"]["casing_strings"] == len(fe["construction"]["casing"])
    assert ed["identity"] == fe["identity"] and ed["status"] == fe["status"]  # same well facts, scoped detail
    # ED keeps field context; FE does not get field roll-ups
    assert client.get("/api/fields/Lakwa/attribution", headers=H[ED]).status_code == 200
    assert client.get("/api/fields/Lakwa/attribution", headers=H[FE]).status_code == 403


def test_rbac_doc_type_gating(client):
    ed_list = client.get("/api/wells/LKW-047/documents", headers=H[ED]).json()["data"]
    assert ed_list and not ({"D04", "D05"} & {d["doc_type_id"] for d in ed_list})
    fe_list = client.get("/api/wells/LKW-047/documents", headers=H[FE]).json()["data"]
    tally = next(d for d in fe_list if d["doc_type_id"] == "D04")
    denied = client.get(f"/api/docs/{tally['doc_id']}.pdf", headers=H[ED])
    assert denied.status_code == 403 and denied.json()["message"].startswith("not permitted for persona ED: well.construction")
    assert client.get(f"/api/docs/{tally['doc_id']}.pdf", headers=H[FE]).status_code == 200
    only_denied = client.get("/api/docs/search", params={"q": "production", "doc_types": "D10"}, headers=H[FE])
    assert only_denied.status_code == 403 and "field.aggregate" in only_denied.json()["message"]
    assert rbac.denied_doc_types(ED) == ["D04", "D05"] and rbac.denied_doc_types(FE) == ["D10"]
    assert rbac.denied_doc_types(AM) == []


# ------------------------------------------------------------------------------------------------ tool layer
def test_rbac_direct_denied_tool_call_returns_unavailable():
    calls = []

    @rbac.gated("field.aggregate")
    def compare(period: str = "QTD"):
        calls.append(period)
        return ToolResult(ToolStatus.OK, {"secret": 1}, [], "ok", {"tool_id": "TC-024"})

    with rbac.persona_scope(FE):
        r = compare(period="QTD")
    assert isinstance(r, ToolResult) and r.status is ToolStatus.UNAVAILABLE and r.value is None
    assert r.message == "not permitted for persona FIELD_ENGINEER: field.aggregate"
    assert calls == []  # the tool body never ran: no data computed, none leaked
    with rbac.persona_scope(ED):
        assert compare(period="QTD").status is ToolStatus.OK
    assert compare(_persona=FE).status is ToolStatus.UNAVAILABLE


def test_rbac_gated_attribution_scope_and_redaction():
    @rbac.gated(rbac.attribution_capability, envelope=True)
    def attr(well_id: str = "", field: str = ""):
        return {"status": "OK", "data": {"well_id": well_id, "field": field, "cost_band": "MED"}}

    with rbac.persona_scope(FE):
        assert attr(well_id="LKW-047")["data"] == {"well_id": "LKW-047", "field": ""}  # allowed, cost_band dropped
        denied = attr(field="Lakwa")
        assert denied["status"] == "UNAVAILABLE" and denied["data"] is None


def test_rbac_voice_tools_honour_persona():
    from app.live import voice_tools

    fe_names = {t.name for t in voice_tools.tools_for(FE)}
    ed_names = {t.name for t in voice_tools.tools_for(ED)}
    assert {"compare_fields", "field_production_history"} <= ed_names
    assert not ({"compare_fields", "field_production_history"} & fe_names)
    assert {"well_profile", "attribute_decline", "classify_intervention"} <= fe_names
    r = voice_tools.execute_voice_tool("compare_fields", {"period": "QTD"}, FE)
    assert r["status"] == "UNAVAILABLE" and r["data"] is None
    assert r["message"].startswith("not permitted for persona FIELD_ENGINEER")
    assert voice_tools.execute_voice_tool("attribute_decline", {"field": "Lakwa"}, FE)["status"] == "UNAVAILABLE"
    ok = voice_tools.execute_voice_tool("attribute_decline", {"well_id": "LKW-047"}, FE)
    assert ok["status"] != "UNAVAILABLE"
    ed_prof = voice_tools.execute_voice_tool("well_profile", {"well_id": "LKW-047"}, ED)
    assert ed_prof["data"]["construction"]["tallies_redacted"] is True


# ------------------------------------------------------------------------------------------------ GIS (F-17)
def test_gis_map_header_counts_equal_tc020(client):
    kpis = client.get("/api/wells/kpis").json()
    fields = client.get("/api/fields").json()["data"]["fields"]
    m = client.get("/api/fields/map").json()["data"]
    assert sorted(m["fields"]) == ["Geleki", "Lakhmani", "Lakwa"] and len(m["boundaries"]) == 3
    assert all(b.get("is_synthetic_geometry") for b in m["boundaries"])  # D-3 label source
    assert m["cluster_polygons"] and len(m["points"]) == kpis["total_wells"]
    summed = {k: sum(f["health_counts"][k] for f in fields) for k in fields[0]["health_counts"]}
    assert m["counts_by_color"] == summed
    assert summed["AT_RISK"] == kpis["at_risk_count"]
    assert summed["UNDERPERFORMING"] == kpis["underperforming_count"]
    assert summed["NOT_PRODUCING"] == kpis["not_producing_count"]
    assert summed["PRODUCING_OK"] == kpis["healthy_count"]
    for f in fields:
        k = client.get(f"/api/wells/kpis?field={f['field']}").json()
        assert f["health_counts"]["NOT_PRODUCING"] == k["not_producing_count"]
        assert f["health_counts"]["AT_RISK"] == k["at_risk_count"]
    for p in (ED, FE):  # every persona sees the map
        assert client.get("/api/fields/map", headers=H[p]).status_code == 200


def test_gis_drawer_profile_equals_tc029(client):
    import json

    from app.analytics.tools.well_profile import well_profile

    body = client.get("/api/wells/LKW-047/profile", headers=H[AM]).json()
    tool = json.loads(json.dumps(well_profile("LKW-047").envelope()))
    for env in (body, tool):
        env["provenance"].pop("duration_ms", None)  # wall-clock timing, not data
    assert body == tool
