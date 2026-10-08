"""Gate NN (demo, D-32): TC-030 / TC-031 multimodal success engine."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analytics.tools import success_engine as se

pytestmark = pytest.mark.skipif(not se.INDEX_PATH.exists(), reason="analog index not built")

WELLS = ["GK-129", "LKW-019", "LKM-061"]


@pytest.mark.parametrize("well", WELLS)
def test_top3_shape_and_bounds(well):
    r = se.recommend_interventions(well)
    assert r["engine"].startswith("multimodal-nn")
    assert len(r["candidates"]) == 3
    ps = [c["p_success"] for c in r["candidates"]]
    assert all(se.P_MIN <= p <= se.P_MAX for p in ps)
    assert [c["rank"] for c in r["candidates"]] == [1, 2, 3]
    assert len({c["job_code"] for c in r["candidates"]}) == 3
    for c in r["candidates"]:
        assert "cost_band" in c and "rig_days" in c
        assert not any(tok in str(c).lower() for tok in ("usd", "rupee", "₹", "npv"))
    assert {"inputs", "fusion", "training", "serving"} <= set(r["architecture"])
    assert r["drivers"], "drivers present"
    assert len({d["modality"] for d in r["drivers"]}) >= 2, "drivers span more than one modality"


@pytest.mark.parametrize("well", WELLS)
def test_deterministic(well):
    a = se.recommend_interventions(well)
    se._well_vector.cache_clear()
    b = se.recommend_interventions(well)
    assert [(c["job_code"], c["p_success"]) for c in a["candidates"]] == \
           [(c["job_code"], c["p_success"]) for c in b["candidates"]]


def test_score_formula():
    assert se.score(0.64, 0.5, 0.7) == round(0.8 * 0.6, 2)
    assert se.score(1.0, 1.0, 1.0) == se.P_MAX
    assert se.score(0.0, 0.5, 0.5) == se.P_MIN
    assert se.p_mechanism(0.1, "FIT") == 0.60 and se.p_mechanism(0.9, "FIT") == 0.9


def test_analogs_recompute_from_index():
    r = se.similar_wells("GK-129", "IC-11")
    idx = pd.read_parquet(se.INDEX_PATH)
    assert r["n"] == len(r["analogs"]) <= se.K_ANALOGS
    assert "GK-129" not in {a["well_id"] for a in r["analogs"]}
    for a in r["analogs"]:
        row = idx[idx["workover_id"] == a["workover_id"]].iloc[0]
        assert row["outcome"] == a["outcome"] and row["label"] == "IC-11"
    assert r["n_success"] == sum(a["outcome"] == "SUCCESS" for a in r["analogs"])


def test_routes():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/wells/GK-129/recommendations?k=3")
    assert r.status_code == 200 and len(r.json()["candidates"]) == 3
    assert c.get("/api/wells/GK-129/similar?class=IC-11").json()["n"] >= 1
    assert c.get("/api/wells/ZZ-999/recommendations").status_code == 404


def test_compact_summary_for_agent():
    s = se.compact_summary("LKW-019")
    assert s["engine"] == "WellPulse multimodal NN" and len(s["candidates"]) == 3
    assert all(isinstance(c["p_success_pct"], int) for c in s["candidates"])
