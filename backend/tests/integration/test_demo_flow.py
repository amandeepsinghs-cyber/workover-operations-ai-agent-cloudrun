"""Stage V gate: the F-18 five-level demo flow (BDD-F18-S01) through ``POST /api/chat``.

Default: deterministic ``FakeLlm`` (real ADK Runner, real tool wrappers, RBAC and callbacks).
``live_llm``: the same flow against the real ``gemini-3.8-flash`` on Vertex AI (ADC); runs only with
``WELLPULSE_LIVE_LLM=1``. Every turn also checks BDD-X-S01: no number in the answer that is absent from that
turn's tool returns (``X-Debug-Trace: 1`` exposes ``trace.tool_returns``).
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.agent.callbacks import check_text, prompt_facts

# (id, persona-independent prompt, ui context, tools that must be called, artifact kinds, action screens)
FLOW = [
    ("L1_tell", "Can you give me the past 5 year production data field-wise?", {"field": None, "well_id": None},
     {"field_production_history"}, set(), set()),
    ("L1_plot", "Can you give me a plot?", {"field": None, "well_id": None},
     {"field_production_history"}, {"field_history_chart"}, {"field_history"}),
    ("L2", "How many wells in Geleki are either sick or have lost production?", {"field": "Geleki", "well_id": None},
     {"classify_well_health", "attribute_decline"}, {"health_buckets"}, {"field_health"}),
    ("L3", "Can you give me a priority list of all the wells that need intervention?",
     {"field": "Geleki", "well_id": None}, {"rank_candidates"}, {"priority_queue"}, {"priority"}),
    ("L4", "Tell me more about GK-129 and show me its production history", {"field": "Geleki", "well_id": None},
     {"well_profile", "plot_production"}, {"well_profile", "well_production_chart"}, {"well"}),
    ("L5_nba", "What are the next best recommended interventions?", {"field": "Geleki", "well_id": "GK-129"},
     {"recommend_next_best_action"}, {"nba"}, {"well"}),
    ("L5_why_not", "Why not just wax removal?", {"field": "Geleki", "well_id": "GK-129"},
     {"compare_interventions"}, {"counterfactual"}, {"well"}),
]


def _turn(client, session_id: str, prompt: str, ctx: dict, persona: str = "ASSET_MANAGER", language: str = "english"):
    r = client.post("/api/chat", headers={"X-Persona": persona, "X-Debug-Trace": "1"},
                    json={"message": prompt, "session_id": session_id, "language": language, **ctx})
    assert r.status_code == 200, r.text
    return r.json()


def _assert_numbers_grounded(body: dict, prompt: str) -> None:
    trace = body.get("trace") or {}
    returns = [prompt_facts(trace.get("ui_state")), *(trace.get("tool_returns") or [])]
    _, bad = check_text(body["response"], returns, prompt)
    assert not bad, f"numbers not in tool returns: {bad} — {body['response'][:300]}"
    assert body["number_check"].get("ok", True) is True, body["number_check"]


def test_demo_flow_fake_llm(client):
    sid = f"demo-{uuid.uuid4().hex[:8]}"
    for tid, prompt, ctx, tools, kinds, screens in FLOW:
        body = _turn(client, sid, prompt, ctx)
        called = {c["name"] for c in body["tool_calls"]}
        assert tools <= called, f"{tid}: expected {tools}, called {called}"
        got_kinds = {a["kind"] for a in body["artifacts"]}
        assert kinds <= got_kinds, f"{tid}: artifacts {got_kinds}"
        assert screens <= {a["screen"] for a in body["actions"]}, f"{tid}: actions {body['actions']}"
        assert body["status"] == "ok" and body["engine"] == "adk:fake-llm"
        _assert_numbers_grounded(body, prompt)
        if tid == "L1_tell":
            assert not got_kinds, "BDD-F11-S01: tell first, no chart yet"
        if tid == "L5_nba":
            assert body["recommendation"] and "usd" not in str(body["recommendation"]).lower()


def test_hinglish_l2_turn(client):
    prompt = "Geleki mein kitne wells sick hain ya production lose kar rahe hain?"
    body = _turn(client, f"hi-{uuid.uuid4().hex[:6]}", prompt, {"field": "Geleki"}, persona="ED", language="hinglish")
    assert "classify_well_health" in {c["name"] for c in body["tool_calls"]}
    assert body["language"] == "hinglish"
    _assert_numbers_grounded(body, prompt)


def test_field_engineer_denied_field_aggregate_via_chat(client):
    prompt = "Which field is not performing?"
    body = _turn(client, f"fe-{uuid.uuid4().hex[:6]}", prompt, {}, persona="FIELD_ENGINEER")
    calls = [c for c in body["tool_calls"] if c["name"] == "compare_fields"]
    assert calls and all(c["status"] == "UNAVAILABLE" for c in calls)
    assert not body["artifacts"]


def test_lkm090_no_job_justified(client):
    prompt = "What should we do on LKM-090?"
    body = _turn(client, f"nj-{uuid.uuid4().hex[:6]}", prompt, {"field": "Lakhmani", "well_id": "LKM-090"})
    assert "recommend_next_best_action" in {c["name"] for c in body["tool_calls"]}
    assert "NO_JOB_JUSTIFIED" in str((body.get("trace") or {}).get("tool_returns")) or \
        "no job" in body["response"].lower()
    _assert_numbers_grounded(body, prompt)


def test_sessions_do_not_leak_tool_calls_between_turns(client):
    """K-4: the second turn's tool_calls/artifacts come from that turn only."""
    sid = f"k4-{uuid.uuid4().hex[:6]}"
    _turn(client, sid, "Tell me more about GK-129 and show me its production history", {"field": "Geleki"})
    body = _turn(client, sid, "How many wells in Geleki are either sick or have lost production?", {"field": "Geleki"})
    assert "well_profile" not in {c["name"] for c in body["tool_calls"]}
    assert "well_profile" not in {a["kind"] for a in body["artifacts"]}


# ------------------------------------------------------------------------------------------------
# Real model (gemini-3.8-flash on Vertex AI). Opt-in: WELLPULSE_LIVE_LLM=1.
# ------------------------------------------------------------------------------------------------
live = pytest.mark.skipif(os.environ.get("WELLPULSE_LIVE_LLM") != "1", reason="set WELLPULSE_LIVE_LLM=1")


@pytest.mark.live_llm
@live
def test_demo_flow_live_llm(client):
    sid = f"live-{uuid.uuid4().hex[:8]}"
    failures = []
    for tid, prompt, ctx, tools, _kinds, _screens in FLOW:
        body = _turn(client, sid, prompt, ctx)
        assert body["engine"].startswith("adk:gemini-3.8-flash"), body["engine"]
        called = {c["name"] for c in body["tool_calls"]}
        if not tools <= called:
            failures.append(f"{tid}: expected {sorted(tools)}, called {sorted(called)}")
        trace = body.get("trace") or {}
        returns = [prompt_facts(trace.get("ui_state")), *(trace.get("tool_returns") or [])]
        _, bad = check_text(body["response"], returns, prompt)
        if bad or not body["number_check"].get("ok", True):
            bad = bad or body["number_check"].get("unmatched")
            failures.append(f"{tid}: ungrounded numbers {bad}")
    assert not failures, "\n".join(failures)
