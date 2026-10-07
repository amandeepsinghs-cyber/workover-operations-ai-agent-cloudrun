"""Shared pytest fixtures for the WellPulse backend.

Tests never call a real model: the ADK agent runs on the deterministic ``FakeLlm``
(``settings.AGENT_LLM = "fake"``) unless a test is marked ``live_llm`` and
``WELLPULSE_LIVE_LLM=1`` is set.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _fake_agent_llm(monkeypatch, request):
    from app import settings
    from app.agent import runner

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    live = request.node.get_closest_marker("live_llm") is not None and os.environ.get("WELLPULSE_LIVE_LLM") == "1"
    monkeypatch.setattr(settings, "AGENT_LLM", "vertex" if live else "fake")
    runner.reset_runner()
    yield
    runner.reset_runner()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
