"""Stage ED-5 (v0.6): TC-035 wax / sand behaviour (F-31)."""
from __future__ import annotations

import random
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.analytics.tools.common import load_table
from app.analytics.tools.wax_sand import wax_sand_behaviour

VERDICTS = {"NOT_PRONE", "FLAGGED_NO_JOBS", "DOWNTIME_ONLY", "ISOLATED", "REPEAT", "PREDICTABLE"}


def _sample(n=20, seed=35):
    return random.Random(seed).sample(sorted(load_table("well_master")["well_id"].astype(str)), n)


def test_hero_wells():
    lkw = wax_sand_behaviour("LKW-019").value
    # waiting on rig for sand must never read as "not sand-prone"
    assert lkw["sand"]["verdict"] == "DOWNTIME_ONLY" and lkw["sand"]["ongoing"]["status"] == "WAITING_ON_RIG"
    gk = wax_sand_behaviour("GK-129").value
    assert gk["wax"]["n_jobs"] >= 1 and gk["sand"]["verdict"] == "NOT_PRONE"
    assert "no sand-rate" in gk["data_note"].lower()


@pytest.mark.parametrize("well", ["GK-129", "LKW-019", "LKM-061"] + _sample())
def test_shape_and_rules(well):
    v = wax_sand_behaviour(well).value
    for k in ("wax", "sand"):
        b = v[k]
        assert b["verdict"] in VERDICTS
        assert len(b["job_dates"]) == min(b["n_jobs"], 10)
        # next-due is predicted only from the well's own repeat cadence
        if b["next_due"] is not None:
            assert b["n_jobs"] >= 2 and b["own_interval_days"] and b["interval_basis"] == "OWN"
            assert date.fromisoformat(b["next_due"]) > date.fromisoformat(b["last_job"]["date"])
        if b["verdict"] == "PREDICTABLE":
            assert b["n_jobs"] >= 3


def test_deterministic():
    assert wax_sand_behaviour("LKM-061").value == wax_sand_behaviour("LKM-061").value


def test_route():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/wells/LKW-019/wax-sand")
    assert r.status_code == 200 and r.json()["data"]["sand"]["verdict"] == "DOWNTIME_ONLY"
    assert c.get("/api/wells/ZZ-999/wax-sand").status_code == 404
