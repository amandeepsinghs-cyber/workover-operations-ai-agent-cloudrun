"""Stage R · TC-022 next best action (BDD F-04 / F-14, SDD §9.1, Gate R)."""

from __future__ import annotations

import dataclasses
import json
from datetime import date

import pytest

from app.analytics.docs_pdf.store import get_store
from app.analytics.tools import nba
from app.analytics.tools.common import ToolStatus, currency_keys, to_jsonable

LKW047_GATE_AS_OF = date(2026, 5, 14)  # last producing day before EP-LKW-047-040 (pinned_values §11 R-D1)


def _nba(well: str, as_of: date | None = None, top_k: int = 3):
    r = nba.recommend_next_best_action(well, as_of=as_of, top_k=top_k)
    assert r.value is not None, r.message
    return r


# ---- Gate R: named wells ----------------------------------------------------------------------------------
@pytest.mark.parametrize("as_of", [LKW047_GATE_AS_OF, date(2026, 7, 6)])
def test_lkw047_action1_pump_overhaul(as_of):
    r = _nba("LKW-047", as_of)
    a1 = r.value.actions[0]
    assert a1.job_code == "PUMP_OVERHAUL" and a1.ic == "IC-01"
    assert a1.diagnostic_fit == nba.FIT
    assert "AS_OF_OVERRIDE" in r.value.flags


def test_lkm090_no_job_justified_names_offsets():
    r = _nba("LKM-090")
    a1 = r.value.actions[0]
    assert a1.job_code == "NO_JOB_JUSTIFIED" and a1.guardrail and a1.guardrail.startswith("G-2")
    assert "G2_RESERVOIR_DECLINE" in r.value.flags
    assert len(r.value.actions) == 1  # every other candidate rejected by G-2
    assert all("G-2" in rj["reason"] or rj["source"] == "ML" for rj in r.value.rejected)
    offsets = r.value.evidence["tc004_offsets"]
    named = [o["well_id"] if isinstance(o, dict) else str(o) for o in (offsets.get("offsets") or [])]
    assert any(w in a1.fit_evidence or w in a1.why for w in named) or "LKM-" in a1.why
    assert a1.sop_doc_id is None  # R-D2: refusal has no SOP
    assert a1.rig_days == 0.0


def test_gk129_cement_squeeze_rank1():
    r = _nba("GK-129")
    a1 = r.value.actions[0]
    assert a1.job_code == "CEMENT_SQUEEZE" and a1.ic == "IC-11" and a1.diagnostic_fit == nba.FIT
    assert "WELL_INTEGRITY" in a1.risk_flags


def test_real_coning_well_choke_back_and_disagreement():
    r = _nba("GK-103")
    a1 = r.value.actions[0]
    assert a1.job_code == "CHOKE_BACK" and a1.guardrail == "G-1 CONING"
    assert {"G1_CONING_GUARDRAIL", "MODEL_PHYSICS_DISAGREEMENT"} <= set(r.value.flags)


def test_chan_negative_fixture_forces_choke_back(monkeypatch):
    """Gate R: Chan dWOR/dt < 0 (coning) + ML says water shut-off → CHOKE_BACK, squeeze demoted, G-3 flag."""
    base = nba.well_evidence("GK-129")
    chan = dict(base.chan or {})
    chan.update(mechanism="CONING", wor_prime_slope=-0.25)
    ml = {"status": "OK", "flags": [], "message": "fixture", "model_version": "fixture",
          "top_k": [{"ic": "IC-11", "label": "Water shut-off (squeeze)", "prob": 0.81},
                    {"ic": "IC-12", "label": "Water shut-off (gel)", "prob": 0.12}]}
    fake = dataclasses.replace(base, chan=chan, ml=ml, water_active=True)
    monkeypatch.setattr(nba, "well_evidence", lambda well_id, as_of=None: fake)
    r = nba._nba_cached.__wrapped__("GK-129", base.as_of, 3)
    a1 = r.value.actions[0]
    assert a1.job_code == "CHOKE_BACK" and a1.guardrail == "G-1 CONING"
    assert {"G1_CONING_GUARDRAIL", "MODEL_PHYSICS_DISAGREEMENT"} <= set(r.value.flags)
    assert r.value.ml_suggestion["ic"] == "IC-11"
    squeeze = [x for x in r.value.rejected if x["job_code"] == "CEMENT_SQUEEZE"]
    assert squeeze and squeeze[0]["demoted_by"] == "G-1" and "coning" in squeeze[0]["reason"]
    assert all(a.ic != "IC-11" for a in r.value.actions)


# ---- ranking, flags, SOPs, currency -----------------------------------------------------------------------
def test_score_formula_and_tiers():
    for well in ("GK-129", "LKM-061", "LKW-047"):
        v = _nba(well).value
        for a in v.actions:
            if a.job_code == "NO_JOB_JUSTIFIED" or a.deferred_bbl_12mo is None or not a.p_success:
                continue
            k = 1.0 - min(nba.RISK_CAP, nba.RISK_STEP * len(a.risk_flags))
            exp = a.deferred_bbl_12mo * a.p_success / max(a.rig_days, 0.5) * k
            assert a.score == pytest.approx(exp, abs=0.11)
        tiers = [0 if a.guardrail else (1 if a.diagnostic_fit == nba.FIT else 2) for a in v.actions]
        assert tiers == sorted(tiers)
        assert [a.rank for a in v.actions] == list(range(1, len(v.actions) + 1))


def test_every_job_action_has_resolving_sop():
    store = get_store()
    seen = 0
    for well in ("GK-129", "LKM-061", "LKW-047", "GK-103"):
        for a in _nba(well).value.actions:
            if a.job_code == "NO_JOB_JUSTIFIED":
                continue
            assert a.sop_doc_id and a.sop_doc_id.startswith("SOP-IC-")
            assert store.pdf_path(a.sop_doc_id) is not None and store.pdf_path(a.sop_doc_id).exists()
            assert a.sop_url == f"/api/docs/{a.sop_doc_id}.pdf" or a.sop_url.endswith(f"{a.sop_doc_id}.pdf")
            assert a.sop_steps and all(p["steps"] for p in a.sop_steps)
            assert a.unit_type and a.duration_days_max >= a.duration_days_min > 0
            assert a.cost_band in {"LOW", "MED", "HIGH"}
            seen += 1
    assert seen >= 4


def test_catalogue_sops_all_parse():
    cat = nba._catalogue()
    ids = sorted({s for s in cat["sop_doc_id"] if isinstance(s, str)})
    assert len(ids) >= 14
    for sid in ids:
        s = nba.sop_steps(sid)
        assert s is not None and s["phases"], sid


def test_no_currency_in_nba_or_recommendation():
    for well in ("GK-129", "LKM-090", "LKW-047"):
        r = _nba(well)
        assert currency_keys(r.envelope()) == []
        rec = nba.recommendation_from_nba(r)
        assert currency_keys(rec) == []
        blob = json.dumps(to_jsonable(rec)).lower()
        assert "payback" not in blob and "usd" not in blob and "₹" not in blob


def test_p_success_lower_after_failed_squeeze():
    """BDD-F04-S04: this well's failed 2019 WSO straddle (IC-12) pulls its IC-12 p_success below the field rate."""
    ev = nba.well_evidence("GK-129")
    d = nba.p_success_beta("STRADDLE_PACKER", ev)
    assert d["n_well"] >= 1 and d["s_well"] < d["n_well"]
    assert d["p_success"] < d["p_field"]
    clean = dataclasses.replace(ev, well_id="__NO_HISTORY__")
    d0 = nba.p_success_beta("STRADDLE_PACKER", clean)
    assert d0["n_well"] == 0 and d0["p_success"] == d0["p_field"]


def test_p_success_uses_only_jobs_before_as_of():
    ev = nba.well_evidence("LKW-047", LKW047_GATE_AS_OF)
    d_early = nba.p_success_beta("PUMP_OVERHAUL", ev)
    d_now = nba.p_success_beta("PUMP_OVERHAUL", nba.well_evidence("LKW-047"))
    assert d_early["n_asset"] < d_now["n_asset"]


def test_recommendation_object_from_tc022():
    rec = nba.recommendation_from_nba(_nba("GK-129"))
    assert rec["job_code"] == "CEMENT_SQUEEZE" and rec["title"]
    assert rec["catalogue_job_codes"] == ["CEMENT_SQUEEZE"]
    assert rec["action_items"] and rec["sop_doc_id"] == "SOP-IC-11"
    assert isinstance(rec["projected_flow_uplift_bopd"], (int, float))


def test_unknown_well_unavailable():
    r = nba.recommend_next_best_action("ZZ-999")
    assert r.status == ToolStatus.UNAVAILABLE and r.value is None


# ---- routes -----------------------------------------------------------------------------------------------
def test_nba_route(client):
    resp = client.get("/api/wells/GK-129/nba?top_k=3")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"status", "data", "message", "provenance"}
    assert body["data"]["actions"][0]["job_code"] == "CEMENT_SQUEEZE"
    assert body["data"]["job_menu"]
    assert client.get("/api/wells/ZZ-999/nba").status_code == 404
    assert client.get("/api/wells/GLK-129/nba").status_code == 404


def test_nba_route_as_of_gated(client, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, "ALLOW_AS_OF_OVERRIDE", False, raising=False)
    assert client.get("/api/wells/LKW-047/nba?as_of=2026-05-14").status_code == 422
    monkeypatch.setattr(settings, "ALLOW_AS_OF_OVERRIDE", True, raising=False)
    resp = client.get("/api/wells/LKW-047/nba?as_of=2026-05-14")
    assert resp.status_code == 200 and resp.json()["data"]["actions"][0]["job_code"] == "PUMP_OVERHAUL"
    assert client.get("/api/wells/LKW-047/nba?as_of=bad").status_code == 422


def test_recommendations_route_uses_tc022(client):
    resp = client.post("/api/wells/GK-129/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"well_id", "well_name", "status", "recommendation"}
    assert body["recommendation"]["job_code"] == "CEMENT_SQUEEZE"
    assert "estimated_cost_usd" not in resp.text and "payback" not in resp.text.lower()


def test_voice_next_best_action():
    from app.live import voice_tools as vt

    out = vt.execute_voice_tool("next_best_action", {"well_id": "gk-129"})
    assert out["status"] == "OK" and out["data"]["actions"][0]["job_code"] == "CEMENT_SQUEEZE"
    assert "job_menu" not in out["data"] and out["data"]["actions"][0]["sop_phases"]
    assert vt.VOICE_TOOLS["next_best_action"].action_kind == "nba"
