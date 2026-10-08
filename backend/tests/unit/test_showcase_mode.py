"""D-33 (v0.6, Stage ED-1): showcase mode — with RBAC enforcement off, nothing is hidden for anyone."""
from __future__ import annotations

import pytest

from app.agent import rbac


@pytest.fixture
def showcase(monkeypatch):
    monkeypatch.setattr(rbac, "ENFORCE", False)
    yield


@pytest.mark.parametrize("persona", rbac.PERSONAS)
def test_every_persona_full_in_showcase(showcase, persona):
    assert all(rbac.access(persona, c) is rbac.Access.FULL for c in rbac.MATRIX)
    caps = rbac.capabilities_for(persona)
    assert caps["denied"] == [] and caps["enforced"] is False
    assert rbac.denied_doc_types(persona) == []


def test_showcase_keeps_construction_and_cost_band(showcase):
    value = {"construction": {"casing": [{"od_in": 7}], "tubing": [], "perfs": []}, "cost_band": "MED"}
    assert rbac.redact("ED", "well.construction", value) == value
    assert rbac.redact("FIELD_ENGINEER", "well.nba", value)["cost_band"] == "MED"


def test_enforced_matrix_still_applies():
    # conftest forces ENFORCE on: the original matrix is intact.
    assert rbac.access("ED", "well.construction") is rbac.Access.SUMMARY
    assert rbac.access("FIELD_ENGINEER", "cost_band.view") is rbac.Access.NONE
    assert rbac.capabilities_for("FIELD_ENGINEER")["enforced"] is True


def test_report_route_shows_cost_band_to_fe_in_showcase(showcase):
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/api/wells/GK-129/report", headers={"X-Persona": "FIELD_ENGINEER"})
    assert r.status_code == 200 and "cost band" in r.text.lower()
