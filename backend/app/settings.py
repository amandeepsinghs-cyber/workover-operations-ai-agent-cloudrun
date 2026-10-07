"""Application settings (SDD §4 `settings.py`).

Single source for the fixed as-of date (D-15) and the data backend switch (D-11/§5.7).
Never use ``datetime.now()`` for data semantics: the demo dataset is pinned.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# D-15: fixed demo "today". Every tool/route defaults to this, never to a literal or now().
AS_OF: date = date(2026, 9, 23)

# D-2: 60-month window for all fields.
DATA_START: date = date(2021, 10, 1)
DATA_END: date = date(2026, 9, 30)

# §5.7: parquet (default, local) | bigquery (Stage X).
DATA_BACKEND: str = os.getenv("DATA_BACKEND", "parquet").lower()

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
LANDING_DIR = Path(os.getenv("WELLPULSE_LANDING_DIR", str(DATA_DIR / "landing")))
MODEL_DIR = APP_DIR / "analytics" / "model"

# ---- Stage V: text agent (SDD §12.1, D-13). Vertex AI + ADC only; no API key is read anywhere. ----
# The shell may export a wrong GOOGLE_CLOUD_PROJECT, so the project is explicit (WELLPULSE_PROJECT_ID overrides).
PROJECT_ID: str = os.getenv("WELLPULSE_PROJECT_ID", "workover-operations-agentic-ai")
TEXT_MODEL: str = "gemini-3.8-flash"  # never change (D-13)
TEXT_LOCATION: str = os.getenv("WELLPULSE_TEXT_LOCATION", "global")  # gemini-3.8-flash 404s in us-central1
# "vertex" (default) | "fake" (deterministic scripted LLM for CI / offline demo; tests set this)
AGENT_LLM: str = os.getenv("WELLPULSE_AGENT_LLM", "vertex").lower()
DEFAULT_LANGUAGE: str = os.getenv("WELLPULSE_DEFAULT_LANGUAGE", "hinglish")  # R-1 resolved: Hinglish default

# SDD §13.1: ?as_of= is honoured only when this is on (tests); otherwise settings.AS_OF.
ALLOW_AS_OF_OVERRIDE: bool = os.getenv("ALLOW_AS_OF_OVERRIDE", "").strip().lower() in ("1", "true", "yes")
