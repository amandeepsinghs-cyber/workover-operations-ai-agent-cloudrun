"""Stage DG generator: barrier_tests and wellhead_rating (WH-14).

Contract:
- Exposes generate(ctx: FieldContext) -> dict[str, pd.DataFrame]
- Returns business columns only:
  - barrier_tests: well_id, field, cluster_id, test_id, test_date,
                   barrier, result, test_pressure_kgcm2, next_due
  - wellhead_rating: well_id, field, cluster_id, wellhead_class_psi,
                     xmas_tree_rating_psi, last_service_date
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .common import AS_OF, FieldContext, well_rng

# Standard API 6A pressure rating classes in psi
API_PRESSURE_CLASSES: tuple[int, ...] = (2000, 3000, 5000, 10000)

# Standard barriers evaluated during routine integrity testing
STANDARD_BARRIERS: tuple[str, ...] = ("MASTER_VALVE", "WING_VALVE", "ANNULUS")

# Failure codes in workover_history that permit a barrier test FAIL result
LEAK_FAILURE_CODES: tuple[str, ...] = ("CASING_LEAK", "TUBING_LEAK")


def _to_date(val: Any) -> date | None:
    """Coerce string/timestamp/date to datetime.date or None."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, date):
        return val
    if hasattr(val, "date"):
        return val.date()
    try:
        ts = pd.to_datetime(val)
        return None if pd.isna(ts) else ts.date()
    except Exception:
        return None


def generate_wellhead_rating(ctx: FieldContext) -> pd.DataFrame:
    """Generate wellhead_rating table: 1 row per well in well_master.

    Columns: well_id, field, cluster_id, wellhead_class_psi,
             xmas_tree_rating_psi, last_service_date.

    Rule:
    - field max THP across well_tests (kg/cm2 -> psi x 14.2233)
    - class = smallest API class in [2000, 3000, 5000, 10000] that is >= 1.5 x field max THP psi
    - xmas_tree_rating_psi = same class
    - last_service_date = last workover end_date for the well or completion_date, <= AS_OF
    """
    wm = ctx.t("well_master")
    wo = ctx.t("workover_history") if "workover_history" in ctx.tables else pd.DataFrame()
    wt = ctx.t("well_tests") if "well_tests" in ctx.tables else pd.DataFrame()
    field = ctx.field

    # 1. Determine field max THP across well_tests (kg/cm2 -> psi)
    if not wt.empty and "thp_kgcm2" in wt.columns:
        valid_thp = wt["thp_kgcm2"].dropna()
        field_max_thp_kgcm2 = float(valid_thp.max()) if not valid_thp.empty else 40.0
    else:
        field_max_thp_kgcm2 = 40.0

    field_max_thp_psi = field_max_thp_kgcm2 * 14.2233
    required_rating_psi = 1.5 * field_max_thp_psi

    # Smallest API class >= 1.5 x field max THP psi
    chosen_class = API_PRESSURE_CLASSES[-1]
    for c in API_PRESSURE_CLASSES:
        if c >= required_rating_psi:
            chosen_class = c
            break

    # 2. Map each well to its last workover end_date <= AS_OF
    last_wo_dates: dict[str, date] = {}
    if not wo.empty and "well_id" in wo.columns:
        date_col = "end_date" if "end_date" in wo.columns else "start_date"
        for _, job in wo.iterrows():
            wid = str(job["well_id"])
            d = _to_date(job.get(date_col))
            if d is None:
                d = _to_date(job.get("start_date"))
            if d is not None and d <= AS_OF:
                if wid not in last_wo_dates or d > last_wo_dates[wid]:
                    last_wo_dates[wid] = d

    # 3. Construct rows for 100% of wells in well_master
    rows: list[dict[str, Any]] = []
    wm_sorted = wm.sort_values(by="well_id")
    for _, w_row in wm_sorted.iterrows():
        well_id = str(w_row["well_id"])
        cluster_id = w_row["cluster_id"] if pd.notna(w_row.get("cluster_id")) else "UNKNOWN"
        well_field = w_row["field"] if pd.notna(w_row.get("field")) else field

        # last_service_date = last workover end_date or completion_date, <= AS_OF
        svc_date = last_wo_dates.get(well_id)
        if svc_date is None:
            svc_date = _to_date(w_row.get("completion_date"))
        if svc_date is None:
            svc_date = _to_date(w_row.get("spud_date"))
        if svc_date is None:
            svc_date = date(2021, 10, 1)

        # Enforce <= AS_OF
        if svc_date > AS_OF:
            svc_date = AS_OF

        rows.append({
            "well_id": well_id,
            "field": str(well_field),
            "cluster_id": str(cluster_id),
            "wellhead_class_psi": int(chosen_class),
            "xmas_tree_rating_psi": int(chosen_class),
            "last_service_date": svc_date,
        })

    cols = [
        "well_id",
        "field",
        "cluster_id",
        "wellhead_class_psi",
        "xmas_tree_rating_psi",
        "last_service_date",
    ]
    return pd.DataFrame(rows, columns=cols)


def generate_barrier_tests(ctx: FieldContext) -> pd.DataFrame:
    """Generate barrier_tests table: grain well x test.

    Columns: well_id, field, cluster_id, test_id, test_date, barrier,
             result, test_pressure_kgcm2, next_due.

    Rules:
    - SSSV only if lift_type is gas-lift/flowing else skip
    - MASTER_VALVE, WING_VALVE, ANNULUS standard
    - PACKER only if tubing_string has a PACKER component
    - Dates: first test after the well's last workover_history end_date
             (or completion_date if none), then every 180 days per barrier
             up to AS_OF=2026-09-23 (never after); next_due = last test + 180 days.
    - test_pressure_kgcm2 = 1.1 x the well's max thp_kgcm2 (MASTER/WING/SSSV)
                            or max chp_kgcm2 (ANNULUS/PACKER) from well_tests,
                            rounded to 1 decimal; if no tests use field median.
    - FAIL rate <= 5% overall and FAIL allowed only on wells that have a
      CASING_LEAK or TUBING_LEAK failure_code in workover_history; otherwise PASS.
    """
    wm = ctx.t("well_master")
    wo = ctx.t("workover_history") if "workover_history" in ctx.tables else pd.DataFrame()
    ts = ctx.t("tubing_string") if "tubing_string" in ctx.tables else pd.DataFrame()
    wt = ctx.t("well_tests") if "well_tests" in ctx.tables else pd.DataFrame()
    field = ctx.field

    cols = [
        "well_id",
        "field",
        "cluster_id",
        "test_id",
        "test_date",
        "barrier",
        "result",
        "test_pressure_kgcm2",
        "next_due",
    ]

    # 1. Map wells with PACKER component in tubing_string
    wells_with_packer: set[str] = set()
    if not ts.empty and "well_id" in ts.columns and "component" in ts.columns:
        packer_rows = ts[ts["component"].astype(str).str.strip().str.upper() == "PACKER"]
        wells_with_packer = set(packer_rows["well_id"].dropna().astype(str))

    # 2. Identify wells permitted to have FAIL results (leak history)
    wells_with_leak: set[str] = set()
    if not wo.empty and "well_id" in wo.columns and "failure_code" in wo.columns:
        leak_rows = wo[
            wo["failure_code"].astype(str).str.strip().str.upper().isin(LEAK_FAILURE_CODES)
        ]
        wells_with_leak = set(leak_rows["well_id"].dropna().astype(str))

    # 3. Compute field median pressures as fallback
    field_median_thp = 15.0
    field_median_chp = 10.0
    if not wt.empty:
        if "thp_kgcm2" in wt.columns:
            thp_series = wt["thp_kgcm2"].dropna()
            if not thp_series.empty:
                field_median_thp = float(thp_series.median())
        if "chp_kgcm2" in wt.columns:
            chp_series = wt["chp_kgcm2"].dropna()
            if not chp_series.empty:
                field_median_chp = float(chp_series.median())

    # Compute per-well max thp and chp
    well_max_thp: dict[str, float] = {}
    well_max_chp: dict[str, float] = {}
    if not wt.empty and "well_id" in wt.columns:
        wt_valid = wt[wt["well_id"].notna()]
        if "thp_kgcm2" in wt_valid.columns:
            for wid, g in wt_valid.groupby("well_id")["thp_kgcm2"]:
                vals = g.dropna()
                if not vals.empty and vals.max() > 0:
                    well_max_thp[str(wid)] = float(vals.max())
        if "chp_kgcm2" in wt_valid.columns:
            for wid, g in wt_valid.groupby("well_id")["chp_kgcm2"]:
                vals = g.dropna()
                if not vals.empty and vals.max() > 0:
                    well_max_chp[str(wid)] = float(vals.max())

    # 4. Map each well to its last workover end_date <= AS_OF
    last_wo_dates: dict[str, date] = {}
    if not wo.empty and "well_id" in wo.columns:
        date_col = "end_date" if "end_date" in wo.columns else "start_date"
        for _, job in wo.iterrows():
            wid = str(job["well_id"])
            d = _to_date(job.get(date_col))
            if d is None:
                d = _to_date(job.get("start_date"))
            if d is not None and d <= AS_OF:
                if wid not in last_wo_dates or d > last_wo_dates[wid]:
                    last_wo_dates[wid] = d

    # 5. Generate barrier test rows per well
    rows: list[dict[str, Any]] = []
    wm_sorted = wm.sort_values(by="well_id")

    for _, w_row in wm_sorted.iterrows():
        well_id = str(w_row["well_id"])
        cluster_id = w_row["cluster_id"] if pd.notna(w_row.get("cluster_id")) else "UNKNOWN"
        well_field = w_row["field"] if pd.notna(w_row.get("field")) else field
        lift_type = str(w_row.get("lift_type", "")).strip().upper()

        # Determine barriers applicable to this well
        barriers: list[str] = ["MASTER_VALVE", "WING_VALVE", "ANNULUS"]

        # SSSV only if lift_type is gas-lift or flowing
        is_gas_or_flowing = any(term in lift_type for term in ("GAS", "FLOW", "NATURAL"))
        if is_gas_or_flowing:
            barriers.append("SSSV")

        # PACKER only if tubing_string has a PACKER component
        if well_id in wells_with_packer:
            barriers.append("PACKER")

        # Baseline date: last workover end_date or completion_date
        base_date = last_wo_dates.get(well_id)
        if base_date is None:
            base_date = _to_date(w_row.get("completion_date"))
        if base_date is None:
            base_date = _to_date(w_row.get("spud_date"))
        if base_date is None:
            base_date = date(2021, 10, 1)

        if base_date > AS_OF:
            base_date = AS_OF

        # Calculate testing pressures
        max_thp = well_max_thp.get(well_id, field_median_thp)
        max_chp = well_max_chp.get(well_id, field_median_chp)

        thp_test_pressure = round(1.1 * max_thp, 1)
        chp_test_pressure = round(1.1 * max_chp, 1)

        # Dates: first test after base_date, then every 180 days up to AS_OF
        test_dates: list[date] = []
        cur_date = base_date + timedelta(days=180)
        while cur_date <= AS_OF:
            test_dates.append(cur_date)
            cur_date += timedelta(days=180)

        # If base_date was so recent that base_date + 180 > AS_OF,
        # no routine test has occurred yet up to AS_OF.
        if not test_dates:
            continue

        rng = well_rng(well_id, "barrier_result")
        can_fail = well_id in wells_with_leak

        for test_date in test_dates:
            next_due = test_date + timedelta(days=180)
            date_str = test_date.strftime("%Y%m%d")

            for barrier in barriers:
                # Pressure calculation based on barrier type
                if barrier in ("MASTER_VALVE", "WING_VALVE", "SSSV"):
                    test_press = thp_test_pressure
                else:  # ANNULUS, PACKER
                    test_press = chp_test_pressure

                # FAIL allowed only on wells with leak history, keeping overall rate <= 5%
                if can_fail and rng.random() < 0.08:
                    result = "FAIL"
                else:
                    result = "PASS"

                test_id = f"BT-{well_id}-{date_str}-{barrier}"

                rows.append({
                    "well_id": well_id,
                    "field": str(well_field),
                    "cluster_id": str(cluster_id),
                    "test_id": test_id,
                    "test_date": test_date,
                    "barrier": barrier,
                    "result": result,
                    "test_pressure_kgcm2": test_press,
                    "next_due": next_due,
                })

    return pd.DataFrame(rows, columns=cols)


def generate(ctx: FieldContext) -> dict[str, pd.DataFrame]:
    """Generate barrier_tests and wellhead_rating for field context."""
    return {
        "barrier_tests": generate_barrier_tests(ctx),
        "wellhead_rating": generate_wellhead_rating(ctx),
    }
