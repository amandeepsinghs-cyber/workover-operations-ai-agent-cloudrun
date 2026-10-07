"""Shared pytest fixtures for the WellPulse backend.

Tests never call Gemini: ``call_gemini_api`` is patched to raise so that the
chat/audio/live routes exercise the deterministic local fallback engine.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _no_gemini(monkeypatch):
    from app.services import ai_agent

    def _raise(*_args, **_kwargs):
        raise RuntimeError("Gemini disabled in tests")

    monkeypatch.setattr(ai_agent, "call_gemini_api", _raise)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
