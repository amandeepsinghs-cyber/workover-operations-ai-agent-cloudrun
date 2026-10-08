"""Stage ED-3 (v0.6): TC-033 decline vs. nearby wells (F-29)."""
from __future__ import annotations

import random
import re

import pytest
from fastapi.testclient import TestClient

from app.analytics.tools.common import load_table
from app.analytics.tools.offset_decline import offset_decline_compare

VERDICTS = {"WELL_SPECIFIC", "RESERVOIR_WIDE", "WATER", "RESTORED", "MIXED", "INSUFFICIENT"}


def _sample(n=15, seed=33):
    return random.Random(seed).sample(sorted(load_table("well_master")["well_id"].astype(str)), n)


def test_hero_verdicts():
    gk = offset_decline_compare("GK-129").value
    assert gk["verdict"] == "WATER" and gk["water_scope"] == "WELL"  # supports "squeeze, not wax removal"
    lkm = offset_decline_compare("LKM-061").value
    assert lkm["verdict"] == "WELL_SPECIFIC" and lkm["mechanical"]["signature"] == "GL_VALVE"
    lkw = offset_decline_compare("LKW-019").value
    assert lkw["verdict"] == "RESTORED" and "waiting on rig" in lkw["headline"]


@pytest.mark.parametrize("well", ["GK-129", "LKW-019", "LKM-061"] + _sample())
def test_shape_and_number_integrity(well):
    v = offset_decline_compare(well).value
    assert v["verdict"] in VERDICTS
    assert len(v["offsets"]) <= 5
    # every number in the headline appears in the returned data (X-1)
    blob = repr(v)
    for num in re.findall(r"\d+(?:\.\d+)?", v["headline"].replace(well, "")):
        if len(num) >= 2 and not re.fullmatch(r"20\d\d", num):
            assert num in blob, (well, num, v["headline"])
    for s in v["subject"]["series"]:
        assert set(s) == {"month", "oil_bopd", "oil_norm", "wc_pct", "thp_kgcm2"}


def test_deterministic():
    assert offset_decline_compare("GK-129").value == offset_decline_compare("GK-129").value


def test_route():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/wells/GK-129/offset-decline")
    assert r.status_code == 200 and r.json()["data"]["verdict"] == "WATER"
    assert c.get("/api/wells/ZZ-999/offset-decline").status_code == 404
