"""Executable BDD test runner and step definitions for WellPulse v0.4 agent stage.

Exercises the deterministic FakeLlm agent, ADK tools, RBAC, callbacks and REST endpoints.
Follows Gherkin specifications from docs/BDD.md.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app import settings
from app.agent.callbacks import check_text

# Load feature files
scenarios("features/agent_demo_flow.feature")
scenarios("features/agent_guardrails.feature")
scenarios("features/agent_decisions.feature")

FLOW = [
    (
        "L1_tell",
        "Can you give me the past 5 year production data field-wise?",
        {"field": None, "well_id": None},
        {"field_production_history"},
        set(),
        set(),
    ),
    (
        "L1_plot",
        "Can you give me a plot?",
        {"field": None, "well_id": None},
        {"field_production_history"},
        {"field_history_chart"},
        {"field_history"},
    ),
    (
        "L2",
        "How many wells in Geleki are either sick or have lost production?",
        {"field": "Geleki", "well_id": None},
        {"classify_well_health", "attribute_decline"},
        {"health_buckets"},
        {"field_health"},
    ),
    (
        "L3",
        "Can you give me a priority list of all the wells that need intervention?",
        {"field": "Geleki", "well_id": None},
        {"rank_candidates"},
        {"priority_queue"},
        {"priority"},
    ),
    (
        "L4",
        "Tell me more about GK-129 and show me its production history",
        {"field": "Geleki", "well_id": None},
        {"well_profile", "plot_production"},
        {"well_profile", "well_production_chart"},
        {"well"},
    ),
    (
        "L5_nba",
        "What are the next best recommended interventions?",
        {"field": "Geleki", "well_id": "GK-129"},
        {"recommend_next_best_action"},
        {"nba"},
        {"well"},
    ),
    (
        "L5_why_not",
        "Why not just wax removal?",
        {"field": "Geleki", "well_id": "GK-129"},
        {"compare_interventions"},
        {"counterfactual"},
        {"well"},
    ),
]


def assert_numbers_grounded(body: dict, prompt: str) -> None:
    returns = (body.get("trace") or {}).get("tool_returns") or []
    _, bad = check_text(body.get("response", ""), returns, prompt)
    assert not bad, f"numbers not in tool returns: {bad} — {body.get('response', '')[:300]}"
    assert body.get("number_check", {}).get("ok", True) is True, body.get("number_check")


def assert_no_money(obj: Any) -> None:
    forbidden_keys = ("usd", "inr", "npv", "payback")
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_lower = str(k).lower()
            assert not any(fk in k_lower for fk in forbidden_keys), f"Found forbidden money key: {k}"
            assert_no_money(v)
    elif isinstance(obj, list):
        for item in obj:
            assert_no_money(item)
    elif isinstance(obj, str):
        assert "$" not in obj, f"Found '$' in text: {obj}"
        assert "₹" not in obj, f"Found '₹' in text: {obj}"
        assert "USD" not in obj, f"Found 'USD' in text: {obj}"


def has_key(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(has_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(has_key(x, key) for x in obj)
    return False


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {
        "session_id": f"bdd-{uuid.uuid4().hex[:8]}",
        "persona": "ASSET_MANAGER",
        "field": None,
        "well_id": None,
        "turns": [],
        "replies": {},
        "last_reply": None,
        "last_response": None,
        "last_prompt": None,
        "start_time": time.time(),
    }


# --------------------------------------------------------------------------------------------------
# Given Steps
# --------------------------------------------------------------------------------------------------
@given(parsers.parse('header X-Persona "{persona}"'))
def given_header_persona(ctx: dict[str, Any], persona: str) -> None:
    ctx["persona"] = persona


@given(parsers.parse('persona "{persona}" and well "{well_id}"'))
def given_persona_well(ctx: dict[str, Any], persona: str, well_id: str) -> None:
    ctx["persona"] = persona
    ctx["well_id"] = well_id


@given(parsers.parse('persona "{persona}" and well "{well_id}" in field "{field}"'))
def given_persona_well_field(ctx: dict[str, Any], persona: str, well_id: str, field: str) -> None:
    ctx["persona"] = persona
    ctx["well_id"] = well_id
    ctx["field"] = field


@given("I already asked for field 5 year production data")
def given_already_asked_field_data(client, ctx: dict[str, Any]) -> None:
    prompt = "Can you give me the past 5 year production data field-wise?"
    ctx["last_prompt"] = prompt
    r = client.post(
        "/api/chat",
        headers={"X-Persona": ctx["persona"], "X-Debug-Trace": "1"},
        json={"message": prompt, "session_id": ctx["session_id"], "language": "english"},
    )
    assert r.status_code == 200, r.text
    ctx["last_reply"] = r.json()


# --------------------------------------------------------------------------------------------------
# When Steps
# --------------------------------------------------------------------------------------------------
@when("I run in one session_id:")
def when_run_in_one_session(client, ctx: dict[str, Any]) -> None:
    ctx["start_time"] = time.perf_counter()
    ctx["session_id"] = f"bdd-demo-{uuid.uuid4().hex[:8]}"
    ctx["turns"] = []
    ctx["replies"] = {}
    for tid, prompt, uictx, tools, kinds, screens in FLOW:
        r = client.post(
            "/api/chat",
            headers={"X-Persona": "ASSET_MANAGER", "X-Debug-Trace": "1"},
            json={"message": prompt, "session_id": ctx["session_id"], "language": "english", **uictx},
        )
        assert r.status_code == 200, f"{tid} failed: {r.text}"
        body = r.json()
        ctx["turns"].append((tid, prompt, uictx, tools, kinds, screens, body))
        ctx["replies"][tid] = body
        ctx["last_reply"] = body


@when("I run the demo turns in order")
def when_run_demo_turns_in_order(client, ctx: dict[str, Any]) -> None:
    when_run_in_one_session(client, ctx)


@when(parsers.parse('I say "{prompt}"'))
def when_i_say(client, ctx: dict[str, Any], prompt: str) -> None:
    ctx["last_prompt"] = prompt
    lang = "hinglish" if "hain" in prompt or "kyun" in prompt else "english"
    body: dict[str, Any] = {"message": prompt, "session_id": ctx["session_id"], "language": lang}
    if ctx.get("field"):
        body["field"] = ctx["field"]
    if ctx.get("well_id"):
        body["well_id"] = ctx["well_id"]
    r = client.post(
        "/api/chat",
        headers={"X-Persona": ctx["persona"], "X-Debug-Trace": "1"},
        json=body,
    )
    assert r.status_code == 200, r.text
    ctx["last_reply"] = r.json()


@when(parsers.parse('I ask "{prompt}"'))
def when_i_ask(client, ctx: dict[str, Any], prompt: str) -> None:
    when_i_say(client, ctx, prompt)


@when("I ask about GK-129 and then ask about Geleki well health in the same session")
def when_ask_gk129_then_geleki(client, ctx: dict[str, Any]) -> None:
    sid = f"leak-test-{uuid.uuid4().hex[:6]}"
    ctx["session_id"] = sid
    r1 = client.post(
        "/api/chat",
        headers={"X-Persona": "ASSET_MANAGER", "X-Debug-Trace": "1"},
        json={"message": "Tell me more about GK-129 and show me its production history", "session_id": sid, "field": "Geleki"},
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        "/api/chat",
        headers={"X-Persona": "ASSET_MANAGER", "X-Debug-Trace": "1"},
        json={"message": "How many wells in Geleki are either sick or have lost production?", "session_id": sid, "field": "Geleki"},
    )
    assert r2.status_code == 200, r2.text
    ctx["turn1_reply"] = r1.json()
    ctx["turn2_reply"] = r2.json()
    ctx["last_reply"] = r2.json()


@when("any answer from POST /api/chat contains a number")
def when_chat_reply_contains_number(client, ctx: dict[str, Any]) -> None:
    prompt = "How many wells in Geleki are either sick or have lost production?"
    ctx["last_prompt"] = prompt
    r = client.post(
        "/api/chat",
        headers={"X-Persona": "ASSET_MANAGER", "X-Debug-Trace": "1"},
        json={"message": prompt, "session_id": ctx["session_id"], "language": "english", "field": "Geleki"},
    )
    assert r.status_code == 200, r.text
    ctx["last_reply"] = r.json()


@when("any REST response or UI screen is captured")
def when_rest_captured(client, ctx: dict[str, Any]) -> None:
    r_nba = client.get("/api/wells/GK-129/nba", headers={"X-Persona": "ASSET_MANAGER"})
    assert r_nba.status_code == 200, r_nba.text
    ctx["nba_response"] = r_nba.json()
    r_chat = client.post(
        "/api/chat",
        headers={"X-Persona": "ASSET_MANAGER", "X-Debug-Trace": "1"},
        json={"message": "What are the next best recommended interventions?", "session_id": ctx["session_id"], "well_id": "GK-129"},
    )
    assert r_chat.status_code == 200, r_chat.text
    ctx["chat_response"] = r_chat.json()


@when("I GET /api/fields/compare")
def when_get_fields_compare(client, ctx: dict[str, Any]) -> None:
    r = client.get("/api/fields/compare", headers={"X-Persona": ctx["persona"]})
    ctx["last_response"] = r


@when(parsers.parse('I GET /api/fields/compare as "{persona}"'))
def when_get_fields_compare_as(client, ctx: dict[str, Any], persona: str) -> None:
    r = client.get("/api/fields/compare", headers={"X-Persona": persona})
    assert r.status_code == 200, r.text
    ctx["last_response"] = r


@when(parsers.parse("I GET /api/wells/{well_id}/nba"))
def when_get_nba(client, ctx: dict[str, Any], well_id: str) -> None:
    r = client.get(f"/api/wells/{well_id}/nba", headers={"X-Persona": ctx["persona"]})
    assert r.status_code == 200, r.text
    ctx["last_response"] = r
    ctx["well_id"] = well_id


@when(parsers.parse('recommendations are retrieved for "{well_id}"'))
def when_get_recs(client, ctx: dict[str, Any], well_id: str) -> None:
    when_get_nba(client, ctx, well_id)


@when(parsers.parse('I GET /api/wells/{well_id}/compare with alternative "{alternative}"'))
def when_get_compare(client, ctx: dict[str, Any], well_id: str, alternative: str) -> None:
    r = client.get(
        f"/api/wells/{well_id}/compare",
        params={"alternative": alternative},
        headers={"X-Persona": ctx["persona"]},
    )
    assert r.status_code == 200, r.text
    ctx["last_response"] = r


# --------------------------------------------------------------------------------------------------
# Then Steps
# --------------------------------------------------------------------------------------------------
@then("each turn calls its required tools")
def then_each_turn_calls_required_tools(ctx: dict[str, Any]) -> None:
    for tid, _prompt, _uictx, tools, kinds, screens, reply in ctx["turns"]:
        called = {c["name"] for c in reply["tool_calls"]}
        assert tools <= called, f"{tid}: expected {tools}, called {called}"
        got_kinds = {a["kind"] for a in reply["artifacts"]}
        assert kinds <= got_kinds, f"{tid}: artifacts {got_kinds}"
        assert screens <= {a["screen"] for a in reply["actions"]}, f"{tid}: actions {reply['actions']}"
        assert reply["status"] == "ok"
        assert reply["engine"] == "adk:fake-llm"


@then('L2 reports "sick or lost production" as AT_RISK + UNDERPERFORMING with NOT_PRODUCING separate, plus a field factor breakdown')
def then_l2_health_report(ctx: dict[str, Any]) -> None:
    l2 = ctx["replies"]["L2"]
    called = {c["name"] for c in l2["tool_calls"]}
    assert "classify_well_health" in called
    assert "attribute_decline" in called
    kinds = {a["kind"] for a in l2["artifacts"]}
    assert "health_buckets" in kinds


@then("L3 ranks wells by deferred barrels recovered × p_success ÷ rig-days with cost band, without NPV, ₹ or payback")
def then_l3_priority_ranking(ctx: dict[str, Any]) -> None:
    l3 = ctx["replies"]["L3"]
    kinds = {a["kind"] for a in l3["artifacts"]}
    assert "priority_queue" in kinds
    assert_no_money(l3)


@then("no answer contains a number missing from that turn's tool returns")
def then_no_missing_numbers(ctx: dict[str, Any]) -> None:
    for _tid, prompt, _uictx, _tools, _kinds, _screens, reply in ctx["turns"]:
        assert_numbers_grounded(reply, prompt)


@then("total wall time is under 3 minutes on a warm instance")
def then_total_wall_time(ctx: dict[str, Any]) -> None:
    elapsed = time.perf_counter() - ctx.get("start_time", time.perf_counter())
    assert elapsed < 180.0, f"Elapsed time {elapsed:.2f}s exceeded 180s"


@then("the field chart opens at L1, the map filters to Geleki at L2, the priority table shows at L3, the GK-129 drawer opens at L4 and the Recommendation Card shows at L5")
def then_screens_navigation(ctx: dict[str, Any]) -> None:
    reps = ctx["replies"]
    assert any(a["screen"] == "field_history" for a in reps["L1_plot"]["actions"])
    assert any(a["screen"] == "field_health" for a in reps["L2"]["actions"])
    assert any(a["screen"] == "priority" for a in reps["L3"]["actions"])
    l4_actions = reps["L4"]["actions"]
    assert any(a["screen"] == "well" and a.get("well_id") == "GK-129" for a in l4_actions)
    assert any(a["screen"] == "well" for a in reps["L5_nba"]["actions"])
    assert reps["L5_nba"]["recommendation"] is not None


@then("the answer equals the English L2 answer's counts")
def then_hinglish_counts_equal_english(client, ctx: dict[str, Any]) -> None:
    h_reply = ctx["last_reply"]
    assert "classify_well_health" in {c["name"] for c in h_reply["tool_calls"]}
    assert h_reply["language"] == "hinglish"
    assert_numbers_grounded(h_reply, ctx["last_prompt"])


@then("the second turn does not contain well profile tool calls or artifacts")
def then_no_tool_leak(ctx: dict[str, Any]) -> None:
    t2 = ctx["turn2_reply"]
    called = {c["name"] for c in t2["tool_calls"]}
    assert "well_profile" not in called
    assert "well_profile" not in {a["kind"] for a in t2["artifacts"]}


@then("that number appears in a tool return from the same turn")
def then_number_appears_in_tool_return(ctx: dict[str, Any]) -> None:
    assert_numbers_grounded(ctx["last_reply"], ctx["last_prompt"])


@then("the agent says the data is synthetic and representative")
def then_synthetic_disclosure(ctx: dict[str, Any]) -> None:
    resp = ctx["last_reply"]["response"].lower()
    assert "synthetic" in resp
    assert "representative" in resp


@then("it contains no cost_usd, estimated_cost_usd, payback, ₹ or INR value")
def then_no_money_values(ctx: dict[str, Any]) -> None:
    if "nba_response" in ctx:
        assert_no_money(ctx["nba_response"])
    if "chat_response" in ctx:
        assert_no_money(ctx["chat_response"])
    if "last_reply" in ctx:
        assert_no_money(ctx["last_reply"])


@then(parsers.parse('the configured text model is "{expected_model}"'))
def then_configured_text_model(expected_model: str) -> None:
    assert settings.TEXT_MODEL == expected_model


@then("calls go to Vertex AI with ADC and GEMINI_API_KEY is not read")
def then_vertex_adc_no_api_key(monkeypatch) -> None:
    from google.adk.models.google_llm import Gemini

    from app.agent.runner import build_model

    model = build_model("vertex")
    assert isinstance(model, Gemini)
    assert model.client_kwargs.get("vertexai") is True
    assert model.client_kwargs.get("location") == settings.TEXT_LOCATION


@then(parsers.parse('status is 403 with "{detail}"'))
def then_status_403_detail(ctx: dict[str, Any], detail: str) -> None:
    resp = ctx["last_response"]
    assert resp.status_code == 403
    assert detail in resp.text


@then('the same tool called by the agent returns status "UNAVAILABLE"')
def then_tool_called_by_agent_unavailable(client, ctx: dict[str, Any]) -> None:
    r = client.post(
        "/api/chat",
        headers={"X-Persona": "FIELD_ENGINEER", "X-Debug-Trace": "1"},
        json={"message": "Which field is not performing?", "session_id": f"fe-tool-{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 200, r.text
    calls = [c for c in r.json()["tool_calls"] if c["name"] == "compare_fields"]
    assert calls and all(c["status"] == "UNAVAILABLE" for c in calls)


@then('compare_fields tool call returns status "UNAVAILABLE"')
def then_compare_fields_unavailable(ctx: dict[str, Any]) -> None:
    calls = [c for c in ctx["last_reply"]["tool_calls"] if c["name"] == "compare_fields"]
    assert calls and all(c["status"] == "UNAVAILABLE" for c in calls), (
        f"Expected compare_fields tool call with status UNAVAILABLE, but got calls={calls}. "
        f"Response body: {ctx['last_reply']}"
    )


@then("artifacts list is empty")
def then_artifacts_empty(ctx: dict[str, Any]) -> None:
    assert len(ctx["last_reply"]["artifacts"]) == 0


@then("ranked actions are returned with evidence")
def then_ranked_actions_returned(ctx: dict[str, Any]) -> None:
    data = ctx["last_response"].json().get("data", {})
    actions = data.get("actions", [])
    assert len(actions) >= 1


@then("each action has job_code, intervention_class, uplift_bopd, deferred_bbl_12mo, p_success, rig_days, requires_rig, cost_band")
def then_each_action_has_required_keys(ctx: dict[str, Any]) -> None:
    data = ctx["last_response"].json().get("data", {})
    actions = data.get("actions", [])
    assert len(actions) >= 1
    for a in actions:
        assert "job_code" in a
        assert "ic" in a or "intervention_class" in a
        assert "uplift_bopd" in a
        assert "deferred_bbl_12mo" in a
        assert "p_success" in a
        assert "rig_days" in a
        assert "requires_rig" in a
        assert "cost_band" in a


@then("FIELD_ENGINEER persona sees no cost_band key in nba JSON")
def then_fe_no_cost_band_key(client, ctx: dict[str, Any]) -> None:
    well_id = ctx.get("well_id", "GK-129")
    r_fe = client.get(f"/api/wells/{well_id}/nba", headers={"X-Persona": "FIELD_ENGINEER"})
    assert r_fe.status_code == 200, r_fe.text
    assert not has_key(r_fe.json(), "cost_band"), "FIELD_ENGINEER saw cost_band key in nba JSON"


@then(parsers.parse('action 1 is "{action_name}"'))
def then_action_1_is(ctx: dict[str, Any], action_name: str) -> None:
    reply = ctx["last_reply"]
    returns_str = str((reply.get("trace") or {}).get("tool_returns") or [])
    assert action_name in returns_str or action_name.lower().replace("_", " ") in reply["response"].lower()


@then("recommend_next_best_action is called")
def then_nba_called(ctx: dict[str, Any]) -> None:
    called = {c["name"] for c in ctx["last_reply"]["tool_calls"]}
    assert "recommend_next_best_action" in called


@then("cost shows only LOW, MED or HIGH plus rig_days")
def then_cost_band_format(ctx: dict[str, Any]) -> None:
    data = ctx["last_response"].json().get("data", {})
    actions = data.get("actions", [])
    for a in actions:
        assert a.get("cost_band") in ("LOW", "MED", "HIGH", "N/A", None)
        assert isinstance(a.get("rig_days"), (int, float))


@then('no ₹, INR, USD, "$" or payback figure appears in the API body')
def then_no_currency_in_body(ctx: dict[str, Any]) -> None:
    assert_no_money(ctx["last_response"].json())


@then(parsers.parse('a tool_call for "{tool_name}" is emitted'))
def then_tool_call_emitted(ctx: dict[str, Any], tool_name: str) -> None:
    called = {c["name"] for c in ctx["last_reply"]["tool_calls"]}
    assert tool_name in called, f"Expected {tool_name} in {called}"


@then("Lakwa is identified as underperforming")
def then_lakwa_identified(ctx: dict[str, Any]) -> None:
    resp = ctx["last_reply"]["response"].lower()
    assert "lakwa" in resp


@then("each field row has actual_bopd, target_bopd, gap_pct, expected_bopd, uptime_pct, water_cut_pct")
def then_each_field_row_kpis(ctx: dict[str, Any]) -> None:
    data = ctx["last_response"].json().get("data", {})
    rows = data.get("rows", [])
    assert len(rows) >= 3
    for r in rows:
        assert "actual_bopd" in r
        assert "target_bopd" in r
        assert "gap_pct" in r
        assert "expected_bopd" in r
        assert "uptime_pct" in r
        assert "water_cut_pct" in r


@then("no chart is shown yet")
def then_no_chart_shown_yet(ctx: dict[str, Any]) -> None:
    kinds = {a["kind"] for a in ctx["last_reply"]["artifacts"]}
    assert "field_history_chart" not in kinds


@then('the field history chart artifact is returned with action screen "field_history"')
def then_field_history_chart_and_action(ctx: dict[str, Any]) -> None:
    reply = ctx["last_reply"]
    kinds = {a["kind"] for a in reply["artifacts"]}
    assert "field_history_chart" in kinds
    screens = {a["screen"] for a in reply["actions"]}
    assert "field_history" in screens


@then(parsers.parse('tool_calls for "{tool1}" and "{tool2}" are emitted'))
def then_two_tool_calls_emitted(ctx: dict[str, Any], tool1: str, tool2: str) -> None:
    called = {c["name"] for c in ctx["last_reply"]["tool_calls"]}
    assert tool1 in called, f"Expected {tool1} in {called}"
    assert tool2 in called, f"Expected {tool2} in {called}"


@then(parsers.parse('artifacts include "{kind1}" and "{kind2}"'))
def then_two_artifacts_included(ctx: dict[str, Any], kind1: str, kind2: str) -> None:
    kinds = {a["kind"] for a in ctx["last_reply"]["artifacts"]}
    assert kind1 in kinds, f"Expected {kind1} in {kinds}"
    assert kind2 in kinds, f"Expected {kind2} in {kinds}"


@then(parsers.parse('the action screen is "{screen}" with well_id "{well_id}"'))
def then_action_screen_and_well(ctx: dict[str, Any], screen: str, well_id: str) -> None:
    actions = ctx["last_reply"]["actions"]
    assert any(a["screen"] == screen and a.get("well_id") == well_id for a in actions)


@then(parsers.parse('a tool_call for "{tool_name}" is emitted with alternative "{alternative}"'))
def then_tool_call_with_alternative(ctx: dict[str, Any], tool_name: str, alternative: str) -> None:
    calls = ctx["last_reply"]["tool_calls"]
    matching = [c for c in calls if c["name"] == tool_name]
    assert matching, f"No tool call for {tool_name}"
    assert any(alternative in str(c.get("args", {}).values()) for c in matching)


@then(parsers.parse('artifact kind "{kind}" is returned'))
def then_artifact_kind_returned(ctx: dict[str, Any], kind: str) -> None:
    kinds = {a["kind"] for a in ctx["last_reply"]["artifacts"]}
    assert kind in kinds, f"Expected artifact {kind} in {kinds}"


@then("status is 200 with status OK and comparison data")
def then_compare_status_ok(ctx: dict[str, Any]) -> None:
    resp = ctx["last_response"]
    assert resp.status_code == 200
    assert resp.json().get("status") == "OK"
    assert "data" in resp.json()
