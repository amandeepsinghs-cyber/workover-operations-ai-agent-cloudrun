"""Unit tests for the repository layer and API routes reading it (SDD §5.7, Stage N)."""

from __future__ import annotations

import pytest

from app import settings
from app.data_access import repository as r
from app.data_access.repository import RetiredWellId, get_repository

if not (settings.LANDING_DIR / "asset" / "field_targets.parquet").exists():
    pytest.skip("Landing parquet data not generated", allow_module_level=True)


def test_list_wells_counts():
    repo = get_repository()
    wells = repo.list_wells()
    assert len(wells) == 412
    geleki = [w for w in wells if w["field"] == "Geleki"]
    lakwa = [w for w in wells if w["field"] == "Lakwa"]
    lakhmani = [w for w in wells if w["field"] == "Lakhmani"]
    assert len(geleki) == 142
    assert len(lakwa) == 160
    assert len(lakhmani) == 110
    assert all(w["id"].startswith("GK-") for w in geleki)
    assert all(w["id"].startswith("LKW-") for w in lakwa)
    assert all(w["id"].startswith("LKM-") for w in lakhmani)


def test_glk_retired_404(client):
    r_well = client.get("/api/wells/GLK-101")
    assert r_well.status_code == 404
    assert r_well.json()["detail"] == "GLK- IDs retired in v0.4; use GK-"

    r_hist = client.get("/api/wells/GLK-101/history")
    assert r_hist.status_code == 404
    assert r_hist.json()["detail"] == "GLK- IDs retired in v0.4; use GK-"

    repo = get_repository()
    with pytest.raises(RetiredWellId):
        repo.get_well("GLK-101")


def test_unknown_well_404(client):
    r_unknown = client.get("/api/wells/NOPE-000")
    assert r_unknown.status_code == 404


def test_fixture_wells_resolvable(client):
    for well_id in ["GK-129", "LKW-047", "LKM-090", "LKM-061", "lkw-047"]:
        resp = client.get(f"/api/wells/{well_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == well_id.upper()


def test_null_not_zero_history():
    repo = get_repository()
    for wid in ["GK-129", "LKW-047", "LKM-061"]:
        hist = repo.get_history(wid, "5y")
        assert hist is not None
        assert len(hist) == 1819
        for pt in hist:
            if not pt["is_producing"]:
                assert pt["oil_bopd"] is None
                assert pt["gas_mcfd"] is None
            else:
                assert isinstance(pt["oil_bopd"], (int, float))

    found_well = None
    for w in repo.list_wells():
        hist = repo.get_history(w["id"], "5y")
        if hist is None:
            continue
        non_producing = [pt for pt in hist if not pt["is_producing"]]
        if non_producing:
            for pt in non_producing:
                assert pt["oil_bopd"] is None
            found_well = w["id"]
            break
    assert found_well is not None, "Expected at least one well with non-producing days in 5y history"


def test_history_ranges(client):
    expected_lengths = {
        "30d": 30,
        "6m": 180,
        "1y": 365,
        "2y": 730,
        "3y": 1095,
        "5y": 1819,
    }
    for rng, exp_len in expected_lengths.items():
        resp = client.get(f"/api/wells/GK-129/history?range={rng}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == exp_len
        assert data[-1]["date"] == str(settings.AS_OF)

    resp_invalid = client.get("/api/wells/GK-129/history?range=10y")
    assert resp_invalid.status_code == 422


def test_no_currency_anywhere(client):
    endpoints = [
        client.get("/api/wells").text,
        client.get("/api/wells/kpis").text,
        client.get("/api/wells/LKW-047").text,
        client.get("/api/wells/LKW-047/export").text,
        client.get("/api/wells/LKW-047/workovers").text,
        client.get("/api/wells/LKW-047/reports").text,
        client.post("/api/wells/LKW-047/recommendations").text,
        client.post(
            "/api/wells/GK-129/chat",
            json={"message": "how much did the workovers cost?", "language": "english"},
        ).text,
        client.get("/api/field/infrastructure?field=Lakwa").text,
    ]
    combined = "\n".join(endpoints).lower()
    # "lakh" alone would match the field name Lakhmani; match currency usages only.
    for needle in ("_usd", "payback", "currency", "lakh ", "lakhs", "_lakh", '"inr', "_inr", "$", "₹"):
        assert needle not in combined


def test_workover_cost_band_shape(client):
    resp = client.get("/api/wells/LKW-047")
    assert resp.status_code == 200
    data = resp.json()
    workovers = data["workovers"]
    for wo in workovers:
        assert wo["cost_band"] in {"LOW", "MED", "HIGH"}
        assert isinstance(wo["rig_days"], (int, float)) and wo["rig_days"] >= 0
        assert "cost_usd" not in wo

    telemetry = data["telemetry_summary"]
    mix = telemetry["cost_band_mix"]
    assert set(mix.keys()) == {"LOW", "MED", "HIGH"}
    assert sum(mix.values()) == telemetry["total_workovers"]
    assert telemetry["total_rig_days"] == round(sum(wo["rig_days"] for wo in workovers), 1)


def test_recommendation_cost_band(client):
    resp = client.post("/api/wells/LKM-061/recommendations")
    assert resp.status_code == 200
    rec = resp.json()["recommendation"]
    assert rec["cost_band"] in {"LOW", "MED", "HIGH"}
    assert isinstance(rec["rig_days"], (int, float))
    assert isinstance(rec["catalogue_job_codes"], list) and len(rec["catalogue_job_codes"]) > 0
    assert "estimated_cost_usd" not in rec
    assert "estimated_payback_days" not in rec


def test_interim_health(client):
    resp = client.get("/api/wells")
    assert resp.status_code == 200
    wells = resp.json()
    status_map = {
        "NOT_PRODUCING": "failed",
        "UNDERPERFORMING": "warning",
        "AT_RISK": "warning",
        "PRODUCING_OK": "healthy",
    }
    field_statuses: dict[str, set[str]] = {}
    for w in wells:
        assert w["health_rule"] == "INTERIM_N1"
        assert w["health_bucket"] in {"NOT_PRODUCING", "UNDERPERFORMING", "AT_RISK", "PRODUCING_OK"}
        assert w["status"] == status_map[w["health_bucket"]]
        assert isinstance(w["health_reason"], str) and len(w["health_reason"].strip()) > 0
        field_statuses.setdefault(w["field"], set()).add(w["status"])

    for field_name, statuses in field_statuses.items():
        for expected_status in ("healthy", "warning", "failed"):
            assert expected_status in statuses, f"Missing {expected_status} in field {field_name}"


def test_field_infrastructure(client):
    resp_default = client.get("/api/field/infrastructure")
    assert resp_default.status_code == 200
    assert resp_default.json()["field"] == "Geleki"

    resp_lakwa = client.get("/api/field/infrastructure?field=Lakwa")
    assert resp_lakwa.status_code == 200
    lakwa_ggs = [s for s in resp_lakwa.json()["gathering_stations"] if s["type"] == "GGS"]
    assert len(lakwa_ggs) == 3

    resp_lakhmani = client.get("/api/field/infrastructure?field=Lakhmani")
    assert resp_lakhmani.status_code == 200
    lakhmani_ggs = [s for s in resp_lakhmani.json()["gathering_stations"] if s["type"] == "GGS"]
    assert len(lakhmani_ggs) == 2

    for prefix, resp in [("GK-", resp_default), ("LKW-", resp_lakwa), ("LKM-", resp_lakhmani)]:
        for station in resp.json()["gathering_stations"]:
            for key, val in station.items():
                assert val is not None, f"Property {key} is None in station {station['id']}"
                if isinstance(val, dict):
                    for sub_k, sub_v in val.items():
                        assert sub_v is not None, f"Property {key}.{sub_k} is None in station {station['id']}"
            if station["type"] == "GGS":
                assert all(wid.startswith(prefix) for wid in station["serviced_wells"])

    resp_nowhere = client.get("/api/field/infrastructure?field=Nowhere")
    assert resp_nowhere.status_code == 404


def test_kpis_field_filter(client):
    resp = client.get("/api/wells/kpis?field=Lakwa")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_wells"] == 160
    assert data["healthy_count"] + data["warning_count"] + data["failed_count"] == 160


def test_list_filter_field(client):
    resp_field = client.get("/api/wells?field=Lakhmani")
    assert resp_field.status_code == 200
    data_field = resp_field.json()
    assert len(data_field) == 110
    assert all(w["field"] == "Lakhmani" for w in data_field)

    resp_search = client.get("/api/wells?search=GK")
    assert resp_search.status_code == 200
    data_search = resp_search.json()
    assert len(data_search) > 0
    assert all("GK" in w["id"] for w in data_search)


def test_bigquery_backend_not_implemented(monkeypatch):
    old = r._repo
    try:
        r._repo = None
        monkeypatch.setenv("DATA_BACKEND", "bigquery")
        with pytest.raises(NotImplementedError):
            r.get_repository()
    finally:
        r._repo = old
