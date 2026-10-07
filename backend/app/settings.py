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
