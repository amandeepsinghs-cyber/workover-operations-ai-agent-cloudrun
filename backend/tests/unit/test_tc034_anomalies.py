"""Stage ED-4 (v0.6): TC-034 well history anomaly scan (F-30)."""
from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app.analytics.tools.anomalies import MAX_EVENTS, well_anomalies
from app.analytics.tools.common import load_table

TYPES = {"RATE_DROP", "WC_JUMP", "WC_TREND", "THP_SHIFT", "DOWNTIME"}


def _sample(n=15, seed=34):
    return random.Random(seed).sample(sorted(load_table("well_master")["well_id"].astype(str)), n)


def test_hero_wells():
    gk = well_anomalies("GK-129").value
    assert gk["n_total"] >= 1 and (gk["counts"]["WC_JUMP"] + gk["counts"]["WC_TREND"]) >= 1
    lkw = well_anomalies("LKW-019").value
    assert any(e["type"] == "DOWNTIME" and e.get("ongoing") for e in lkw["events"])
    lkm = well_anomalies("LKM-061").value
    assert lkm["n_total"] >= 1


@pytest.mark.parametrize("well", ["GK-129", "LKW-019", "LKM-061"] + _sample())
def test_shape(well):
    v = well_anomalies(well).value
    assert len(v["events"]) <= MAX_EVENTS
    assert v["n_total"] == sum(v["counts"].values())
    dates = [e["date"] for e in v["events"]]
    assert dates == sorted(dates, reverse=True)
    for e in v["events"]:
        assert e["type"] in TYPES and isinstance(e["text"], str) and e["severity"] is not None
        if e["type"] != "DOWNTIME":
            assert e["before"] is not None and e["after"] is not None


def test_deterministic():
    assert well_anomalies("GK-129").value == well_anomalies("GK-129").value


def test_route():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/wells/LKW-019/anomalies")
    assert r.status_code == 200 and r.json()["data"]["well_id"] == "LKW-019"
    assert c.get("/api/wells/ZZ-999/anomalies").status_code == 404
