"""Stage T REST routes (SDD §13.4) + Live voice tools resolve to TC-024 / TC-028 / TC-029."""

from __future__ import annotations

from app.analytics.tools.common import CURRENCY_KEY_RE


def _no_currency_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert not CURRENCY_KEY_RE.search(str(k)), f"{path}.{k}"
            _no_currency_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _no_currency_keys(v, f"{path}[{i}]")


def test_get_fields(client):
    r = client.get("/api/fields")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "OK" and body["provenance"]["tool_id"] == "TC-025"
    f = {x["field"]: x for x in body["data"]["fields"]}
    assert (f["Lakwa"]["n_wells"], len(f["Lakwa"]["clusters"])) == (160, 3)
    assert sum(f["Lakwa"]["health_counts"].values()) == 160
    assert f["Lakwa"]["is_synthetic_geometry"] is True and f["Lakwa"]["centroid"]
    kinds = [ft["properties"]["kind"] for ft in f["Lakwa"]["boundary_geojson"]["features"]]
    assert kinds.count("CLUSTER_POLYGON") == 3


def test_fields_history_and_alias(client):
    r = client.get("/api/fields/history?fields=Geleki,Lakwa,Lakhmani&freq=M")
    assert r.status_code == 200 and r.json()["status"] == "OK"
    assert len(r.json()["data"]["series"]) == 180
    one = client.get("/api/fields/Lakwa/history").json()
    assert one["data"]["fields"] == ["Lakwa"] and len(one["data"]["series"]) == 60
    lakwa_all = [x for x in r.json()["data"]["series"] if x["field"] == "Lakwa"]
    assert [x["oil_bopd"] for x in lakwa_all] == [x["oil_bopd"] for x in one["data"]["series"]]
    assert client.get("/api/fields/history?fields=Rudrasagar").status_code == 404
    assert client.get("/api/fields/history", headers={"X-Persona": "FIELD_ENGINEER"}).status_code == 403


def test_fields_compare(client):
    r = client.get("/api/fields/compare?period=QTD")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["worst_field"] == "Lakwa" and d["top_driver"]["controllable"] is True
    _no_currency_keys(r.json())
    assert client.get("/api/fields/compare?period=WEEK").status_code == 422


def test_fields_map_lakwa(client):
    d = client.get("/api/fields/map?field=Lakwa").json()["data"]
    assert len(d["points"]) == 160 and {p["field"] for p in d["points"]} == {"Lakwa"}
    assert len(d["cluster_polygons"]) == 3
    assert client.get("/api/fields/map?field=Atlantis").status_code == 404


def test_priority(client):
    r = client.get("/api/fields/Lakwa/priority?queue=rig&limit=5")
    assert r.status_code == 200
    d = r.json()["data"]
    assert len(d["rig_queue"]) <= 5 and d["rigless_queue"] == []
    _no_currency_keys(r.json())
    assert client.get("/api/fields/Rudrasagar/priority").status_code == 404


def test_well_profile_and_production(client):
    p = client.get("/api/wells/LKM-061/profile").json()
    assert p["status"] == "OK" and len(p["data"]["neighbours"]) >= 3
    r = client.get("/api/wells/LKM-061/production?months=36&metrics=oil,gor,wht,gl_inj_rate,gl_inj_pressure")
    d = r.json()["data"]
    assert set(d["series"]) == {"oil", "gor", "wht", "gl_inj_rate", "gl_inj_pressure"}
    assert len(d["dates"]) == len(d["series"]["wht"]) and d["gas_lift"] is True
    assert d["interventions"] and all(m["doc_url"] is None or m["doc_url"].startswith("/api/docs/") for m in d["interventions"])
    assert client.get("/api/wells/GLK-001/profile").status_code == 404
    assert client.get("/api/wells/ZZ-1/production").status_code == 404
    assert client.get("/api/wells/GK-129/production?metrics=bogus").status_code == 422


def test_voice_tools_resolve_to_stage_t():
    from app.live import voice_tools as vt

    out = vt.execute_voice_tool("compare_fields", {"period": "QTD"})
    assert out["status"] == "OK" and out["data"]["worst_field"] == "Lakwa"
    assert out["provenance"]["tool_id"] == "TC-024"
    h = vt.execute_voice_tool("field_production_history", {})
    assert h["status"] == "OK" and len(h["data"]["summary"]) == 3 and "series" not in h["data"]
    w = vt.execute_voice_tool("well_profile", {"well_id": "GK-129", "months": 36})
    assert w["status"] == "OK" and len(w["data"]["neighbours"]) >= 3 and w["data"]["interventions_in_window"]
    assert len(vt.declarations_data()) <= 12
