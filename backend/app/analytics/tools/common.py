"""Shared types, table access and provenance for the deterministic tools (SDD §6.1).

Port of ADK ``tools/common.py`` (v0.3.0) made field-aware:

* Tables come from the process repository (``get_repository()``), never from a module-level path.
  Well-keyed tables are the concatenation of the three fields, so every per-well tool works for
  ``GK-`` / ``LKW-`` / ``LKM-`` wells without a field argument (K-6).
* ``as_of`` defaults are ``settings.AS_OF`` (D-15), never a literal date.
* ``to_jsonable`` turns any tool value into JSON-safe data for the REST envelope (SDD §13.1).
* ``currency_keys`` implements rule 8 (D-1): no currency key may appear in a tool value.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app import settings
from app.analytics.generator.fields import FIELD_CONFIGS

WellId = str
JobCode = str

CONFIG_VERSION = "2.0.0-wellpulse"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

ASSET_TABLES = frozenset({"job_catalogue", "mro_inventory", "rig_calendar", "field_master", "cluster_master",
                          "facility_master", "field_targets"})
_DROP_COLS = ("_ingested_at", "_source_system", "_source_file", "_batch_id")


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ToolStatus(str, Enum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    DISCRIMINATOR_UNAVAILABLE = "DISCRIMINATOR_UNAVAILABLE"


class WaterMechanism(str, Enum):
    CONING = "CONING"
    CHANNELLING = "CHANNELLING"
    MULTILAYER = "MULTILAYER"
    NORMAL = "NORMAL_DISPLACEMENT"
    INDETERMINATE = "INDETERMINATE"
    INJECTOR_BREAKTHROUGH = "INJECTOR_BREAKTHROUGH"
    CHANNELLING_OR_INJECTOR = "CHANNELLING_OR_INJECTOR_BREAKTHROUGH"


class OffsetVerdict(str, Enum):
    WELL_SPECIFIC = "WELL_SPECIFIC"
    RESERVOIR_DECLINE = "RESERVOIR_DECLINE"
    MIXED = "MIXED"
    INSUFFICIENT = "INSUFFICIENT"


class MechSignature(str, Enum):
    PUMP_WEAR = "PUMP_WEAR"
    TUBING_LEAK = "TUBING_LEAK"
    WAX = "WAX"
    SCALE = "SCALE"
    ROD_PART = "ROD_PART"
    GAS_INTERFERENCE = "GAS_INTERFERENCE"
    SAND = "SAND"
    GL_VALVE = "GL_VALVE"
    NONE = "NONE"


@dataclass(frozen=True)
class ToolResult:
    status: ToolStatus
    value: Any | None
    missing_fields: list[str]
    message: str
    provenance: dict

    def envelope(self) -> dict:
        """REST envelope ``{status, data, message, missing_fields, provenance}`` (SDD §13.1)."""
        return {
            "status": self.status.value,
            "data": to_jsonable(self.value),
            "message": self.message,
            "missing_fields": list(self.missing_fields),
            "provenance": to_jsonable(self.provenance),
        }


# ------------------------------------------------------------------------------------------------
# table access (repository-backed)
# ------------------------------------------------------------------------------------------------
_lock = threading.RLock()
_TABLES: dict[tuple[str, str | None], pd.DataFrame] = {}
_BY_WELL: dict[str, dict[str, pd.DataFrame]] = {}


def _repo():
    from app.data_access.repository import get_repository

    return get_repository()


def _read_one(folder: str, name: str) -> pd.DataFrame | None:
    repo = _repo()
    reader = getattr(repo, "table", None)
    if callable(reader):  # Stage X repository protocol (SDD §5.7)
        field = None if folder == "asset" else next(f for f in FIELD_CONFIGS if f.lower() == folder)
        return reader(name, field=field)
    landing = Path(getattr(repo, "landing", settings.LANDING_DIR))
    path = landing / folder / f"{name}.parquet"
    if not path.exists():
        return None
    return repo._read(folder, name) if hasattr(repo, "_read") else pd.read_parquet(path)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in _DROP_COLS if c in df.columns])
    for col in df.columns:
        if ("date" in col) and pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.date
    return df


def load_table(name: str, field: str | None = None) -> pd.DataFrame:
    """A landing table; well-keyed tables are concatenated across fields (or one ``field``)."""
    key = (name, field)
    with _lock:
        if key in _TABLES:
            return _TABLES[key]
        if name in ASSET_TABLES:
            df = _read_one("asset", name)
            df = _normalise(df) if df is not None else pd.DataFrame()
        elif field is not None:
            df = load_table(name)
            df = df[df["field"] == field].reset_index(drop=True) if "field" in df.columns and len(df) else df
        else:
            frames = [f for f in (_read_one(fc.lower(), name) for fc in FIELD_CONFIGS) if f is not None and len(f)]
            df = _normalise(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()
            if name == "daily_production" and len(df):
                df = df.sort_values(["well_id", "production_date"]).reset_index(drop=True)
        _TABLES[key] = df
        return df


def well_rows(name: str, well_id: str) -> pd.DataFrame:
    """Rows of a well-keyed table for one well (pre-split once per table for speed)."""
    with _lock:
        split = _BY_WELL.get(name)
        if split is None:
            df = load_table(name)
            split = {k: g for k, g in df.groupby("well_id", sort=False)} if len(df) and "well_id" in df.columns else {}
            _BY_WELL[name] = split
    g = split.get(well_id)
    if g is None:
        return load_table(name).iloc[0:0]
    return g


def well_master_row(well_id: str) -> dict | None:
    g = well_rows("well_master", well_id)
    return None if g.empty else g.iloc[0].to_dict()


def field_well_ids(field: str, active_only: bool = False) -> list[str]:
    wm = load_table("well_master")
    w = wm[wm["field"] == field]
    if active_only:
        w = w[w["status"] == "ACTIVE"]
    return sorted(w["well_id"].tolist())


def reset_caches() -> None:
    """Drop cached tables and memoised tool results (tests / repository swap)."""
    with _lock:
        _TABLES.clear()
        _BY_WELL.clear()
    for fn in _MEMO_RESETTERS:
        fn()


_MEMO_RESETTERS: list = []


def register_cache(fn) -> None:
    _MEMO_RESETTERS.append(fn)


# ------------------------------------------------------------------------------------------------
# provenance + JSON
# ------------------------------------------------------------------------------------------------
def build_provenance(tool_id: str, params: dict, t0: float, **extra: Any) -> dict:
    payload = json.dumps(params, default=str, sort_keys=True)
    prov = {
        "tool_id": tool_id,
        "input_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
        "config_version": CONFIG_VERSION,
        "data_backend": settings.DATA_BACKEND,
        "as_of": str(params.get("as_of", settings.AS_OF.isoformat())),
        "duration_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    }
    prov.update(extra)
    return prov


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses / enums / dates / numpy / NaN into JSON-safe values."""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.date().isoformat()
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return str(obj)


# Rule 8 (D-1): no currency anywhere in a tool value. ``cost_band`` is a band, not an amount.
CURRENCY_KEY_RE = re.compile(r"inr|lakh|crore|usd|cost_usd|payback|npv|rupee|realisation", re.IGNORECASE)


def currency_keys(obj: Any, path: str = "") -> list[str]:
    """Paths of every key in ``obj`` (after ``to_jsonable``) that names a currency amount."""
    out: list[str] = []
    data = to_jsonable(obj)
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            if CURRENCY_KEY_RE.search(k):
                out.append(p)
            out.extend(currency_keys(v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            out.extend(currency_keys(v, f"{path}[{i}]"))
    return out


def unavailable(tool_id: str, params: dict, t0: float, missing: list[str], message: str,
                status: ToolStatus = ToolStatus.UNAVAILABLE, value: Any = None) -> ToolResult:
    return ToolResult(status=status, value=value, missing_fields=missing, message=message,
                      provenance=build_provenance(tool_id, params, t0))


def load_yaml(name: str) -> dict:
    import yaml

    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)
