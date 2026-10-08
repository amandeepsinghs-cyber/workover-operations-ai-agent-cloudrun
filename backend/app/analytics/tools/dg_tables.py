"""TC-033 dg_tables: access to the 6 synthetic data-gap tables (Stage DG, F-22, SDD §5.9, §6.2).

Provides deterministic access and summary metrics for:
- tubing_tally (well × joint tally to tubing depth)
- deviation_survey (well × station directional survey every 30m)
- integrity (barrier_tests + wellhead_rating + fluid_hazards + fishing_records)

All data carries is_synthetic=True and _source_system='wellpulse_dg_v1'.
Summary metrics are computed directly from the table data, never typed.
"""

from __future__ import annotations

import math
import time
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app import settings

from .common import (
    ToolResult,
    ToolStatus,
    build_provenance,
    to_jsonable,
    well_master_row,
    well_rows,
)


def _clean_val(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _clean_row(r: dict | pd.Series, drop: tuple[str, ...] = ("field", "cluster_id", "well_id")) -> dict:
    items = r.items() if isinstance(r, dict) else r.to_dict().items()
    return {k: _clean_val(v) for k, v in items if not str(k).startswith("_") and k not in drop}


def _r(x: Any, nd: int = 1) -> float | None:
    x = _clean_val(x)
    return None if x is None else round(float(x), nd)


class DGTableResult(dict):
    """JSON-serialisable dict adhering to ToolResult conventions and direct dict access."""

    def __init__(
        self,
        data: dict | None = None,
        *,
        status: ToolStatus = ToolStatus.OK,
        missing_fields: list[str] | None = None,
        message: str = "",
        provenance: dict | None = None,
    ):
        super().__init__(data or {})
        self.status = status
        self.missing_fields = missing_fields or []
        self.message = message
        self.provenance = provenance or {}

    @property
    def value(self) -> dict | None:
        return self if self.status == ToolStatus.OK else None

    def envelope(self) -> dict:
        return {
            "status": self.status.value,
            "data": dict(self),
            "message": self.message,
            "missing_fields": list(self.missing_fields),
            "provenance": self.provenance,
        }


def _unavailable_result(tool_id: str, params: dict, t0: float, message: str) -> DGTableResult:
    prov = build_provenance(tool_id, params, t0)
    return DGTableResult(
        {"status": ToolStatus.UNAVAILABLE.value, "detail": message, "message": message},
        status=ToolStatus.UNAVAILABLE,
        missing_fields=["well_id"],
        message=message,
        provenance=prov,
    )


def tubing_tally(well_id: str, as_of: date | None = None) -> DGTableResult:
    """TC-033 tubing_tally. Returns joint tally records and computed summary for well_id."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    wid = (well_id or "").strip().upper()
    params = {"well_id": wid, "table": "tubing_tally", "as_of": str(as_of)}

    wm = well_master_row(wid)
    if wm is None:
        return _unavailable_result("TC-033", params, t0, f"Well {well_id} not found.")

    df = well_rows("tubing_tally", wid)
    if not df.empty and "joint_no" in df.columns:
        df = df.sort_values("joint_no").reset_index(drop=True)

    rows = [_clean_row(r) for _, r in df.iterrows()]

    min_drift = round(float(df["drift_in"].min()), 3) if len(df) and df["drift_in"].notna().any() else None
    min_id = round(float(df["id_in"].min()), 3) if len(df) and df["id_in"].notna().any() else None
    max_od = round(float(df["od_in"].max()), 3) if len(df) and df["od_in"].notna().any() else None
    total_len = round(float(df["length_m"].sum()), 2) if len(df) and df["length_m"].notna().any() else 0.0
    max_depth = round(float(df["bottom_md_m"].max()), 2) if len(df) and df["bottom_md_m"].notna().any() else 0.0

    summary = {
        "joint_count": int(len(df)),
        "min_drift": min_drift,
        "min_drift_in": min_drift,
        "min_id_in": min_id,
        "max_od_in": max_od,
        "total_length_m": total_len,
        "max_depth_m": max_depth,
    }

    data = {
        "well_id": wid,
        "is_synthetic": True,
        "as_of": str(as_of),
        "rows": rows,
        "records": rows,
        "summary": summary,
    }
    msg = f"{wid}: tubing_tally with {len(rows)} joints, min drift {min_drift} in, total length {total_len} m."
    prov = build_provenance("TC-033", params, t0)
    return DGTableResult(data, status=ToolStatus.OK, message=msg, provenance=prov)


def deviation_survey(well_id: str, as_of: date | None = None) -> DGTableResult:
    """TC-033 deviation_survey. Returns directional survey stations and computed summary for well_id."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    wid = (well_id or "").strip().upper()
    params = {"well_id": wid, "table": "deviation_survey", "as_of": str(as_of)}

    wm = well_master_row(wid)
    if wm is None:
        return _unavailable_result("TC-033", params, t0, f"Well {well_id} not found.")

    df = well_rows("deviation_survey", wid)
    if not df.empty and "md_m" in df.columns:
        df = df.sort_values("md_m").reset_index(drop=True)

    rows = [_clean_row(r) for _, r in df.iterrows()]

    max_inc = round(float(df["inc_deg"].max()), 2) if len(df) and df["inc_deg"].notna().any() else 0.0
    max_md = round(float(df["md_m"].max()), 2) if len(df) and df["md_m"].notna().any() else 0.0
    max_tvd = round(float(df["tvd_m"].max()), 2) if len(df) and df["tvd_m"].notna().any() else 0.0
    max_dls = round(float(df["dls_deg_30m"].max()), 2) if len(df) and df["dls_deg_30m"].notna().any() else None

    summary = {
        "station_count": int(len(df)),
        "max_inclination": max_inc,
        "max_inclination_deg": max_inc,
        "max_md_m": max_md,
        "max_tvd_m": max_tvd,
        "max_dls_deg_30m": max_dls,
        "is_deviated": bool(max_inc >= 3.0),
    }

    data = {
        "well_id": wid,
        "is_synthetic": True,
        "as_of": str(as_of),
        "rows": rows,
        "records": rows,
        "summary": summary,
    }
    msg = f"{wid}: deviation_survey with {len(rows)} stations, max inclination {max_inc} deg, max TVD {max_tvd} m."
    prov = build_provenance("TC-033", params, t0)
    return DGTableResult(data, status=ToolStatus.OK, message=msg, provenance=prov)


def integrity(well_id: str, as_of: date | None = None) -> DGTableResult:
    """TC-033 integrity. Returns barrier_tests, wellhead_rating, fluid_hazards, fishing_records and summary."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    wid = (well_id or "").strip().upper()
    params = {"well_id": wid, "table": "integrity", "as_of": str(as_of)}

    wm = well_master_row(wid)
    if wm is None:
        return _unavailable_result("TC-033", params, t0, f"Well {well_id} not found.")

    # 1. barrier_tests (≤ as_of)
    bt = well_rows("barrier_tests", wid)
    if not bt.empty and "test_date" in bt.columns:
        bt = bt[bt["test_date"] <= as_of].sort_values("test_date").reset_index(drop=True)
    bt_records = [_clean_row(r) for _, r in bt.iterrows()]

    latest_tests: dict[str, dict] = {}
    if not bt.empty and "barrier" in bt.columns:
        for barrier, g in bt.groupby("barrier", sort=False):
            last_row = g.sort_values("test_date").iloc[-1]
            latest_tests[str(barrier)] = {
                "test_date": _clean_val(last_row["test_date"]),
                "result": str(last_row["result"]),
                "test_pressure_kgcm2": _r(last_row.get("test_pressure_kgcm2")),
                "next_due": _clean_val(last_row.get("next_due")),
            }

    # 2. wellhead_rating
    wh = well_rows("wellhead_rating", wid)
    wh_records = [_clean_row(r) for _, r in wh.iterrows()]
    wh_class = int(wh.iloc[0]["wellhead_class_psi"]) if len(wh) and pd.notna(wh.iloc[0]["wellhead_class_psi"]) else None
    tree_rating = int(wh.iloc[0]["xmas_tree_rating_psi"]) if len(wh) and pd.notna(wh.iloc[0]["xmas_tree_rating_psi"]) else None
    last_service = _clean_val(wh.iloc[0]["last_service_date"]) if len(wh) and "last_service_date" in wh.columns else None

    # 3. fluid_hazards
    fh = well_rows("fluid_hazards", wid)
    fh_records = [_clean_row(r) for _, r in fh.iterrows()]
    hazard_class = str(fh.iloc[0]["hazard_class"]) if len(fh) and pd.notna(fh.iloc[0]["hazard_class"]) else None
    h2s = _r(fh.iloc[0]["h2s_ppm"]) if len(fh) and "h2s_ppm" in fh.columns else None
    co2 = _r(fh.iloc[0]["co2_mol_pct"]) if len(fh) and "co2_mol_pct" in fh.columns else None
    wax = bool(fh.iloc[0]["wax_flag"]) if len(fh) and pd.notna(fh.iloc[0]["wax_flag"]) else False
    sand = bool(fh.iloc[0]["sand_flag"]) if len(fh) and pd.notna(fh.iloc[0]["sand_flag"]) else False
    scale = bool(fh.iloc[0]["scale_flag"]) if len(fh) and pd.notna(fh.iloc[0]["scale_flag"]) else False

    # 4. fishing_records (≤ as_of)
    fr = well_rows("fishing_records", wid)
    if not fr.empty and "event_date" in fr.columns:
        fr = fr[fr["event_date"] <= as_of].sort_values("event_date").reset_index(drop=True)
    fr_records = [_clean_row(r) for _, r in fr.iterrows()]
    fishing_count = int(len(fr))
    unrecovered_count = int(len(fr[fr["recovered"] == False])) if len(fr) and "recovered" in fr.columns else 0

    summary = {
        "latest_barrier_tests": latest_tests,
        "latest_barrier_test_results": {b: t["result"] for b, t in latest_tests.items()},
        "wellhead_class": wh_class,
        "wellhead_class_psi": wh_class,
        "xmas_tree_rating_psi": tree_rating,
        "last_service_date": last_service,
        "hazard_class": hazard_class,
        "h2s_ppm": h2s,
        "co2_mol_pct": co2,
        "wax_flag": wax,
        "sand_flag": sand,
        "scale_flag": scale,
        "fishing_count": fishing_count,
        "unrecovered_fishing_count": unrecovered_count,
    }

    rows_dict = {
        "barrier_tests": bt_records,
        "wellhead_rating": wh_records,
        "fluid_hazards": fh_records,
        "fishing_records": fr_records,
    }

    data = {
        "well_id": wid,
        "is_synthetic": True,
        "as_of": str(as_of),
        "rows": rows_dict,
        "records": rows_dict,
        "barrier_tests": bt_records,
        "wellhead_rating": wh_records,
        "fluid_hazards": fh_records,
        "fishing_records": fr_records,
        "summary": summary,
    }

    msg = (
        f"{wid}: integrity status — wellhead {wh_class} psi, hazard {hazard_class}, "
        f"{len(latest_tests)} barriers tested, {fishing_count} fishing events."
    )
    prov = build_provenance("TC-033", params, t0)
    return DGTableResult(data, status=ToolStatus.OK, message=msg, provenance=prov)
