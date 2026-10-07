"""Stage V: number guardrail (SDD §12.6, BDD-X-S01) — pure helpers and the live after_model callback."""

from __future__ import annotations

import pytest

from app.agent import callbacks
from app.agent.callbacks import MASK, check_text


def test_numbers_present_in_tool_returns_pass():
    payload = {"data": {"sick_or_lost_count": 37, "total_wells": 120, "share": 0.3083, "oil_rate_bopd": 412.56}}
    text = "37 of 120 wells are sick (30.8%); oil rate 412.6 bopd."
    masked, bad = check_text(text, [payload])
    assert bad == [] and masked == text


def test_fabricated_number_is_masked():
    masked, bad = check_text("Uplift would be 987.6 bopd for 37 wells.", [{"data": {"n": 37}}])
    assert bad == ["987.6"]
    assert "987.6" not in masked and MASK in masked and "37" in masked


def test_identifiers_dates_small_ints_and_user_numbers_are_not_flagged():
    text = "GK-129 in IC-08 at L4: 3 steps since 2025-06-30; you asked about the past 5 years."
    masked, bad = check_text(text, [{"as_of": "2025-06-30"}], user_text="past 5 years")
    assert bad == [] and masked == text


def test_numbers_inside_tool_strings_count():
    _, bad = check_text("Deferred 58 bopd.", [{"message": "deferred 58 bopd vs plan"}])
    assert bad == []


def test_rounding_to_reply_precision():
    payload = {"value": 1234.5678}
    assert check_text("about 1234.6", [payload])[1] == []
    assert check_text("about 1234.57", [payload])[1] == []
    assert check_text("about 1240.1", [payload])[1] == ["1240.1"]


@pytest.mark.asyncio
async def test_fabricating_model_gets_masked_end_to_end(monkeypatch):
    """A model that adds a number no tool returned: the runner's reply carries the mask and ok=False."""
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    from app.agent import runner
    from app.agent.fake_llm import FakeLlm

    class LyingLlm(FakeLlm):
        async def generate_content_async(self, llm_request, stream=False):
            async for r in super().generate_content_async(llm_request, stream):
                parts = list(r.content.parts or [])
                if parts and parts[0].text:
                    r = LlmResponse(content=types.Content(role="model", parts=[
                        types.Part(text=parts[0].text + " Expected uplift is 987.6 bopd.")]))
                yield r

    monkeypatch.setattr(runner, "build_model", lambda mode=None: LyingLlm())
    runner.reset_runner()
    reply = await runner.run_turn_async(session_id="lie", user_id="t", persona="ASSET_MANAGER", field="Geleki",
                                        well_id=None, language="english",
                                        text="How many wells in Geleki are either sick or have lost production?",
                                        mode="fake")
    assert "987.6" not in reply["response"] and MASK in reply["response"]
    assert reply["number_check"]["ok"] is False and "987.6" in reply["number_check"]["unmatched"]
    runner.reset_runner()


def test_sanitize_history_compacts_long_lists_only_in_request_copy():
    long = list(range(100))
    out = callbacks.compact_for_model({"series": long, "n": 3})
    assert long == list(range(100))  # source untouched
    assert out["n"] == 3 and len(out["series"]) == callbacks.MAX_LIST + 1
    assert out["series"][-1] == {"_truncated_from": 100}
