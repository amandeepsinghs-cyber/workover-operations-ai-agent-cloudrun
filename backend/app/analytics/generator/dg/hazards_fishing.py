"""Stage DG generator: fluid_hazards and fishing_records (WH-13, WH-10).

Contract:
- Exposes generate(ctx: FieldContext) -> dict[str, pd.DataFrame]
- Returns business columns only:
  - fluid_hazards: well_id, field, cluster_id, h2s_ppm, co2_mol_pct,
                   wax_flag, sand_flag, scale_flag, hazard_class
  - fishing_records: well_id, field, cluster_id, event_id, event_date,
                     fish_type, top_md_m, recovered, workover_id
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from .common import FieldContext, well_rng

# Field bands for H2S and CO2 concentrations (WH-13).
# Sourced from field reservoir fluid specifications.
FIELD_HAZARD_BANDS: dict[str, dict[str, tuple[float, float]]] = {
    "geleki": {
        "h2s_ppm": (0.0, 5.0),
        "co2_mol_pct": (0.5, 2.0),
    },
    "lakwa": {
        "h2s_ppm": (0.0, 3.0),
        "co2_mol_pct": (0.3, 1.5),
    },
    "lakhmani": {
        "h2s_ppm": (0.0, 8.0),
        "co2_mol_pct": (0.8, 2.5),
    },
}

# Aliases so documentation and external consumers can cite them
FIELD_BANDS = FIELD_HAZARD_BANDS
HAZARD_BANDS = FIELD_HAZARD_BANDS

# Allowed fish types in fishing_records
ALLOWED_FISH_TYPES = (
    "PARTED_RODS",
    "STUCK_PUMP",
    "TUBING_PARTED",
    "JUNK",
)

# Eligible failure codes that can generate fishing records
FISHING_FAILURE_CODES = (
    "ROD_PART",
    "SUDDEN_MECH",
    "SAND",
)


def generate_fluid_hazards(ctx: FieldContext) -> pd.DataFrame:
    """Generate fluid_hazards table: 1 row per well in well_master.

    Columns: well_id, field, cluster_id, h2s_ppm, co2_mol_pct,
             wax_flag, sand_flag, scale_flag, hazard_class (NONE/LOW/MODERATE).
    """
    wm = ctx.t("well_master")
    wo = ctx.t("workover_history") if "workover_history" in ctx.tables else pd.DataFrame()
    field = ctx.field

    bands = FIELD_HAZARD_BANDS.get(
        field,
        {"h2s_ppm": (0.0, 5.0), "co2_mol_pct": (0.5, 2.0)},
    )

    # Extract historical failure codes per well
    codes_by_well: dict[str, set[str]] = {}
    if not wo.empty and "well_id" in wo.columns and "failure_code" in wo.columns:
        wo_valid = wo[wo["well_id"].notna() & wo["failure_code"].notna()]
        codes_by_well = (
            wo_valid.groupby("well_id")["failure_code"]
            .apply(lambda s: set(s.astype(str).str.strip().str.upper()))
            .to_dict()
        )

    rows: list[dict[str, Any]] = []
    # Sort by well_id for deterministic row order
    wm_sorted = wm.sort_values(by="well_id")
    for _, row in wm_sorted.iterrows():
        well_id = str(row["well_id"])
        cluster_id = row["cluster_id"] if pd.notna(row.get("cluster_id")) else "UNKNOWN"
        well_field = row["field"] if pd.notna(row.get("field")) else field

        rng = well_rng(well_id, "fluid_hazards")
        h2s_ppm = round(float(rng.uniform(*bands["h2s_ppm"])), 2)
        co2_mol_pct = round(float(rng.uniform(*bands["co2_mol_pct"])), 2)

        codes = codes_by_well.get(well_id, set())
        wax_flag = "WAX" in codes
        sand_flag = "SAND" in codes
        scale_flag = "SCALE" in codes

        # Hazard class rule:
        # MODERATE if h2s_ppm >= 5 or co2 >= 2.0, LOW if any flag, else NONE.
        if h2s_ppm >= 5.0 or co2_mol_pct >= 2.0:
            hazard_class = "MODERATE"
        elif wax_flag or sand_flag or scale_flag:
            hazard_class = "LOW"
        else:
            hazard_class = "NONE"

        rows.append({
            "well_id": well_id,
            "field": str(well_field),
            "cluster_id": str(cluster_id),
            "h2s_ppm": h2s_ppm,
            "co2_mol_pct": co2_mol_pct,
            "wax_flag": wax_flag,
            "sand_flag": sand_flag,
            "scale_flag": scale_flag,
            "hazard_class": hazard_class,
        })

    cols = [
        "well_id",
        "field",
        "cluster_id",
        "h2s_ppm",
        "co2_mol_pct",
        "wax_flag",
        "sand_flag",
        "scale_flag",
        "hazard_class",
    ]
    return pd.DataFrame(rows, columns=cols)


def generate_fishing_records(ctx: FieldContext) -> pd.DataFrame:
    """Generate fishing_records table: grain well x event.

    Columns: well_id, field, cluster_id, event_id, event_date,
             fish_type (PARTED_RODS/STUCK_PUMP/TUBING_PARTED/JUNK),
             top_md_m, recovered (bool), workover_id.

    Only for workover_history jobs with failure_code:
    - ROD_PART: fish_type PARTED_RODS, ~60% of such jobs
    - SUDDEN_MECH: STUCK_PUMP or TUBING_PARTED, ~40% of such jobs
    - SAND: STUCK_PUMP, ~15% of such jobs
    Never create fishing rows for other failure codes.
    """
    wm = ctx.t("well_master")
    wo = ctx.t("workover_history") if "workover_history" in ctx.tables else pd.DataFrame()
    ts = ctx.t("tubing_string") if "tubing_string" in ctx.tables else pd.DataFrame()
    field = ctx.field

    cols = [
        "well_id",
        "field",
        "cluster_id",
        "event_id",
        "event_date",
        "fish_type",
        "top_md_m",
        "recovered",
        "workover_id",
    ]

    if wo.empty or "failure_code" not in wo.columns:
        return pd.DataFrame(columns=cols)

    # Compute max tubing depth per well from tubing_string as fallback
    max_tubing_depths: dict[str, float] = {}
    if not ts.empty and "well_id" in ts.columns and "top_m" in ts.columns and "length_m" in ts.columns:
        ts_valid = ts.dropna(subset=["top_m", "length_m"]).copy()
        ts_valid["bottom_m"] = ts_valid["top_m"] + ts_valid["length_m"]
        max_tubing_depths = ts_valid.groupby("well_id")["bottom_m"].max().to_dict()

    # Well metadata lookup from well_master
    pump_depth_map: dict[str, float] = {}
    if "pump_setting_depth_m" in wm.columns:
        for wid, pd_val in wm.set_index("well_id")["pump_setting_depth_m"].items():
            if pd.notna(pd_val) and float(pd_val) > 0:
                pump_depth_map[str(wid)] = float(pd_val)

    cluster_map = (
        wm.set_index("well_id")["cluster_id"].to_dict()
        if "cluster_id" in wm.columns
        else {}
    )
    field_map = (
        wm.set_index("well_id")["field"].to_dict()
        if "field" in wm.columns
        else {}
    )

    # Filter to eligible candidate jobs only
    candidate_codes = set(FISHING_FAILURE_CODES)
    candidates = wo[wo["failure_code"].isin(candidate_codes)].copy()
    if candidates.empty:
        return pd.DataFrame(columns=cols)

    # Sort deterministically
    candidates = candidates.sort_values(by=["well_id", "start_date", "workover_id"])

    rows: list[dict[str, Any]] = []

    # Process grouped by well for deterministic per-well RNG stream
    for well_id, grp in candidates.groupby("well_id", sort=True):
        well_id_str = str(well_id)
        rng = well_rng(well_id_str, "fishing")

        # Resolve max depth for this well: pump_setting_depth_m or tubing depth fallback
        if well_id_str in pump_depth_map:
            max_depth = pump_depth_map[well_id_str]
        elif well_id_str in max_tubing_depths and pd.notna(max_tubing_depths[well_id_str]) and max_tubing_depths[well_id_str] > 0:
            max_depth = float(max_tubing_depths[well_id_str])
        else:
            max_depth = 2500.0

        for _, job in grp.iterrows():
            fc = str(job["failure_code"]).strip().upper()
            workover_id = str(job["workover_id"])

            roll = rng.random()
            if fc == "ROD_PART":
                if roll >= 0.60:
                    continue
                fish_type = "PARTED_RODS"
            elif fc == "SUDDEN_MECH":
                if roll >= 0.40:
                    continue
                fish_type = "STUCK_PUMP" if rng.random() < 0.50 else "TUBING_PARTED"
            elif fc == "SAND":
                if roll >= 0.15:
                    continue
                fish_type = "STUCK_PUMP"
            else:
                continue

            # Determine event date within [start_date, end_date] inclusive
            start_date = job["start_date"]
            end_date = job["end_date"] if pd.notna(job.get("end_date")) else start_date
            if pd.isna(start_date):
                start_date = end_date
            if pd.isna(start_date):
                start_date = date(2022, 1, 1)
                end_date = start_date

            if start_date > end_date:
                start_date, end_date = end_date, start_date

            days_span = (end_date - start_date).days
            day_offset = int(rng.integers(0, days_span + 1)) if days_span > 0 else 0
            event_date = start_date + timedelta(days=day_offset)

            # top_md_m between 0 and well's pump_setting_depth_m (or tubing depth if missing)
            raw_top_md = rng.uniform(0.0, max_depth)
            top_md_m = round(float(raw_top_md), 1)
            # Guard against floating-point rounding slightly exceeding max_depth
            top_md_m = min(top_md_m, round(max_depth, 1))
            top_md_m = max(0.0, top_md_m)

            recovered = bool(rng.random() < 0.85)

            well_cluster = cluster_map.get(well_id_str)
            if pd.isna(well_cluster) or well_cluster is None:
                well_cluster = job.get("cluster_id", "UNKNOWN")

            well_field_val = field_map.get(well_id_str)
            if pd.isna(well_field_val) or well_field_val is None:
                well_field_val = job.get("field", field)

            event_id = f"FISH-{workover_id}"

            rows.append({
                "well_id": well_id_str,
                "field": str(well_field_val),
                "cluster_id": str(well_cluster),
                "event_id": event_id,
                "event_date": event_date,
                "fish_type": fish_type,
                "top_md_m": top_md_m,
                "recovered": recovered,
                "workover_id": workover_id,
            })

    return pd.DataFrame(rows, columns=cols)


def generate(ctx: FieldContext) -> dict[str, pd.DataFrame]:
    """Generate both fluid_hazards and fishing_records for field context."""
    return {
        "fluid_hazards": generate_fluid_hazards(ctx),
        "fishing_records": generate_fishing_records(ctx),
    }
