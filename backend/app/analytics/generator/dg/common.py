"""Shared helpers for Stage DG generators (orchestrator-owned contract).

Every generator module exposes ``generate(ctx: FieldContext) -> dict[str, pd.DataFrame]``.
Keys are table names, and each value is a DataFrame of business columns only.
``finalize()`` adds the lineage columns.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

DG_SEED = 20261008
SOURCE_SYSTEM = "wellpulse_dg_v1"
BATCH_ID = "dg_v1_20261008"
AS_OF = date(2026, 9, 23)
FIELDS = ("geleki", "lakwa", "lakhmani")
LANDING = Path(__file__).resolve().parents[2].parent / "data" / "landing"

# Existing tables a generator may read (read-only).
INPUT_TABLES = (
    "well_master", "tubing_string", "casing_tally", "perforation_intervals",
    "formation_tops", "workover_history", "well_tests", "pressure_surveys",
    "well_status_history",
)


@dataclass
class FieldContext:
    field: str
    tables: dict[str, pd.DataFrame]

    def t(self, name: str) -> pd.DataFrame:
        return self.tables[name]


def load_field(field: str, landing: Path = LANDING) -> FieldContext:
    tables = {}
    for name in INPUT_TABLES:
        p = landing / field / f"{name}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            tables[name] = df[[c for c in df.columns if not c.startswith("_")]]
    return FieldContext(field=field, tables=tables)


def well_rng(well_id: str, salt: str) -> np.random.Generator:
    """Deterministic per-well RNG, independent of iteration order."""
    h = int(hashlib.sha256(f"{DG_SEED}:{salt}:{well_id}".encode()).hexdigest()[:16], 16)
    return np.random.default_rng(h)


def finalize(df: pd.DataFrame, table: str, field: str) -> pd.DataFrame:
    df = df.copy()
    df["is_synthetic"] = True
    df["_ingested_at"] = pd.Timestamp("2026-10-08T00:00:00Z")
    df["_source_system"] = SOURCE_SYSTEM
    df["_source_file"] = f"landing/{field}/{table}.parquet"
    df["_batch_id"] = BATCH_ID
    return df
