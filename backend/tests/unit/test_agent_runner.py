"""Stage V: runner / prompt / config invariants (SDD §12, D-13, K-4)."""

from __future__ import annotations

import pathlib

from app import settings
from app.agent import adk_tools, prompt, runner

APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"


def test_text_model_is_gemini_38_flash_on_vertex():
    assert settings.TEXT_MODEL == "gemini-3.8-flash"
    m = runner.build_model("vertex")
    assert m.model == "gemini-3.8-flash"
    assert m.client_kwargs["vertexai"] is True and m.client_kwargs["project"] == settings.PROJECT_ID


def test_no_gemini_api_key_anywhere_in_app():
    hits = [str(p.relative_to(APP_DIR)) for p in APP_DIR.rglob("*.py") if "GEMINI_API_KEY" in p.read_text("utf-8")]
    assert not hits, hits


def test_tool_registry_is_30_unique_typed_wrappers():
    names = [t.__name__ for t in adk_tools.ALL]
    assert len(names) == 33 and len(set(names)) == 33
    for t in adk_tools.ALL:
        assert (t.__doc__ or "").strip(), t.__name__
        assert "tool_context" in t.__code__.co_varnames[: t.__code__.co_argcount], t.__name__


def test_prompt_carries_persona_ui_context_language_and_disclosure():
    text = prompt.render({"persona": "FIELD_ENGINEER", "ui_field": "Geleki", "ui_well_id": "GK-129",
                          "language": "hinglish", "ui_screen": "map"})
    assert "UI CONTEXT: field=Geleki; selected well=GK-129;" in text
    assert "Field Engineer" in text and "synthetic" in text.lower() and "hinglish" in text.lower()


def test_agent_has_number_guardrail_and_low_temperature():
    a = runner.build_agent(runner.build_model("fake"))
    assert a.after_model_callback is not None and a.before_model_callback is not None
    assert a.generate_content_config.temperature <= 0.2


def test_turns_do_not_mutate_module_state():
    before = (list(adk_tools.ALL), dict(adk_tools.TOOLS_BY_NAME))
    out = runner.run_turn(session_id="mut", persona="ED", field="Geleki", language="english",
                          text="How many wells in Geleki are either sick or have lost production?", mode="fake")
    assert out["tool_calls"]
    assert (list(adk_tools.ALL), dict(adk_tools.TOOLS_BY_NAME)) == before


def test_degraded_reply_when_model_raises(monkeypatch):
    class Boom(Exception):
        pass

    from app.agent.fake_llm import FakeLlm

    class BrokenLlm(FakeLlm):
        async def generate_content_async(self, llm_request, stream=False):
            raise Boom("model down")
            yield  # pragma: no cover

    monkeypatch.setattr(runner, "build_model", lambda mode=None: BrokenLlm())
    runner.reset_runner()
    out = runner.run_turn(session_id="deg", persona="ED", field="Geleki", language="english",
                          text="How many wells in Geleki are either sick or have lost production?", mode="fake")
    runner.reset_runner()
    assert out["status"] == "degraded"
