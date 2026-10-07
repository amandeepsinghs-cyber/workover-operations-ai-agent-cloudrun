"""Well construction table generators (casing, tubing, perforations).

Stage N / WellPulse v0.4 synthetic data generation.
"""

from datetime import date

import numpy as np
import pandas as pd


def generate_casing_tally(wells: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Generate casing tally table for given wells.

    Columns:
        well_id, field, cluster_id, string_type, od_in, weight_ppf, grade,
        top_m, shoe_m, cement_top_m, install_date
    """
    rng = np.random.default_rng(seed)
    columns = [
        "well_id",
        "field",
        "cluster_id",
        "string_type",
        "od_in",
        "weight_ppf",
        "grade",
        "top_m",
        "shoe_m",
        "cement_top_m",
        "install_date",
    ]
    if wells.empty:
        return pd.DataFrame(columns=columns)

    records = []
    for _, row in wells.iterrows():
        wid = row["well_id"]
        fld = row["field"]
        cid = row["cluster_id"]
        comp_date: date = row["completion_date"]
        perf_top_m = float(row["perf_top_m"])
        td_md_m = float(row["total_depth_md_m"])
        casing_size = float(row["casing_size_in"])

        # 1. CONDUCTOR
        cond_shoe = round(float(rng.uniform(40.0, 80.0)), 1)
        records.append({
            "well_id": wid,
            "field": fld,
            "cluster_id": cid,
            "string_type": "CONDUCTOR",
            "od_in": 20.0,
            "weight_ppf": 94.0,
            "grade": "K-55",
            "top_m": 0.0,
            "shoe_m": cond_shoe,
            "cement_top_m": 0.0,
            "install_date": comp_date,
        })

        # 2. SURFACE
        surf_shoe = round(float(rng.uniform(450.0, 750.0)), 1)
        records.append({
            "well_id": wid,
            "field": fld,
            "cluster_id": cid,
            "string_type": "SURFACE",
            "od_in": 13.375,
            "weight_ppf": 54.5,
            "grade": "J-55",
            "top_m": 0.0,
            "shoe_m": surf_shoe,
            "cement_top_m": 0.0,
            "install_date": comp_date,
        })

        # 3. PRODUCTION
        if np.isclose(casing_size, 5.5):
            prod_weight = float(rng.choice([15.5, 17.0]))
            prod_grade = str(rng.choice(["J-55", "N-80"], p=[0.4, 0.6]))
        elif np.isclose(casing_size, 7.0):
            prod_weight = float(rng.choice([23.0, 26.0]))
            prod_grade = str(rng.choice(["N-80", "L-80"], p=[0.5, 0.5]))
        else:
            prod_weight = 17.0
            prod_grade = "N-80"

        prod_shoe = round(float(td_md_m - rng.uniform(2.0, 10.0)), 1)
        drawn_cement_depth = perf_top_m - rng.uniform(300.0, 900.0)
        prod_cement_top = round(float(max(surf_shoe - 100.0, drawn_cement_depth)), 1)

        records.append({
            "well_id": wid,
            "field": fld,
            "cluster_id": cid,
            "string_type": "PRODUCTION",
            "od_in": casing_size,
            "weight_ppf": prod_weight,
            "grade": prod_grade,
            "top_m": 0.0,
            "shoe_m": prod_shoe,
            "cement_top_m": prod_cement_top,
            "install_date": comp_date,
        })

    return pd.DataFrame(records, columns=columns)


def generate_tubing_string(
    wells: pd.DataFrame, workovers: pd.DataFrame, seed: int
) -> pd.DataFrame:
    """Generate tubing string components for given wells and workovers history.

    Columns:
        well_id, field, cluster_id, seq, component, od_in, length_m, top_m,
        install_date, workover_id
    """
    rng = np.random.default_rng(seed)
    columns = [
        "well_id",
        "field",
        "cluster_id",
        "seq",
        "component",
        "od_in",
        "length_m",
        "top_m",
        "install_date",
        "workover_id",
    ]
    if wells.empty:
        return pd.DataFrame(columns=columns)

    target_jobs = {"TUBING_REPLACE", "PUMP_OVERHAUL", "GLV_REPLACE", "LIFT_CONVERSION"}
    has_workovers = workovers is not None and not workovers.empty

    records = []
    for _, row in wells.iterrows():
        wid = row["well_id"]
        fld = row["field"]
        cid = row["cluster_id"]
        comp_date: date = row["completion_date"]
        lift_type = str(row["lift_type"])
        tubing_size = float(row["tubing_size_in"])
        perf_top_m = float(row["perf_top_m"])

        install_date = comp_date
        workover_id = None

        if has_workovers:
            w_wo = workovers[
                (workovers["well_id"] == wid)
                & (~workovers["is_censored"].fillna(False).astype(bool))
                & (workovers["catalogue_job_code"].isin(target_jobs))
            ]
            if not w_wo.empty:
                latest = w_wo.sort_values(
                    by=["end_date", "start_date"], ascending=False
                ).iloc[0]
                install_date = latest["end_date"]
                workover_id = latest["workover_id"]

        components = []
        if lift_type == "SRP":
            psd = float(row["pump_setting_depth_m"])
            # TUBING from 0 to pump_setting_depth_m
            tubing_len = round(psd, 1)
            components.append(("TUBING", tubing_len, 0.0))
            # PUMP length 7.3
            curr_top = round(tubing_len, 1)
            components.append(("PUMP", 7.3, curr_top))
            # TUBING_ANCHOR length 1.0
            curr_top = round(curr_top + 7.3, 1)
            components.append(("TUBING_ANCHOR", 1.0, curr_top))

        elif lift_type == "GAS_LIFT":
            n = int(rng.choice([4, 5]))
            depths = [
                round(float(d), 1)
                for d in np.linspace(600.0, perf_top_m - 100.0, n)
            ]
            curr_top = 0.0
            for d in depths:
                tubing_len = round(float(d - curr_top), 1)
                components.append(("TUBING", tubing_len, curr_top))
                curr_top = round(curr_top + tubing_len, 1)
                components.append(("GLM", 2.4, curr_top))
                curr_top = round(curr_top + 2.4, 1)

            target = round(float(perf_top_m - 30.0), 1)
            tubing_len = round(float(target - curr_top), 1)
            components.append(("TUBING", tubing_len, curr_top))
            curr_top = round(curr_top + tubing_len, 1)
            components.append(("PACKER", 1.5, curr_top))

        elif lift_type == "NATURAL":
            target = round(float(perf_top_m - 30.0), 1)
            components.append(("TUBING", target, 0.0))
            components.append(("PACKER", 1.5, target))

        for seq, (comp_name, length_m, top_m) in enumerate(components, start=1):
            records.append({
                "well_id": wid,
                "field": fld,
                "cluster_id": cid,
                "seq": seq,
                "component": comp_name,
                "od_in": tubing_size,
                "length_m": round(float(length_m), 1),
                "top_m": round(float(top_m), 1),
                "install_date": install_date,
                "workover_id": workover_id,
            })

    return pd.DataFrame(records, columns=columns)


def generate_perforation_intervals(
    wells: pd.DataFrame, workovers: pd.DataFrame, seed: int
) -> pd.DataFrame:
    """Generate perforation intervals for given wells and workovers history.

    Columns:
        well_id, field, cluster_id, zone, top_m, bottom_m, spf, perf_date, status
    """
    rng = np.random.default_rng(seed)
    columns = [
        "well_id",
        "field",
        "cluster_id",
        "zone",
        "top_m",
        "bottom_m",
        "spf",
        "perf_date",
        "status",
    ]
    if wells.empty:
        return pd.DataFrame(columns=columns)

    has_workovers = workovers is not None and not workovers.empty

    records = []
    for _, row in wells.iterrows():
        wid = row["well_id"]
        fld = row["field"]
        cid = row["cluster_id"]
        current_zone = str(row["current_zone"])
        comp_date: date = row["completion_date"]
        perf_top_m = float(row["perf_top_m"])
        perf_bottom_m = float(row["perf_bottom_m"])
        td_md_m = float(row["total_depth_md_m"])

        # 1. Primary interval
        primary_spf = int(rng.choice([4, 6], p=[0.6, 0.4]))
        records.append({
            "well_id": wid,
            "field": fld,
            "cluster_id": cid,
            "zone": current_zone,
            "top_m": round(perf_top_m, 1),
            "bottom_m": round(perf_bottom_m, 1),
            "spf": primary_spf,
            "perf_date": comp_date,
            "status": "OPEN",
        })

        # 2. Older lower interval with probability 0.35
        has_older = bool(rng.random() < 0.35)
        if has_older:
            older_top = perf_bottom_m + rng.uniform(5.0, 20.0)
            older_bottom = older_top + rng.uniform(5.0, 15.0)
            older_status = str(rng.choice(["SQUEEZED", "ISOLATED"], p=[0.6, 0.4]))
            if older_bottom <= td_md_m - 2.0:
                records.append({
                    "well_id": wid,
                    "field": fld,
                    "cluster_id": cid,
                    "zone": current_zone,
                    "top_m": round(float(older_top), 1),
                    "bottom_m": round(float(older_bottom), 1),
                    "spf": 4,
                    "perf_date": comp_date,
                    "status": older_status,
                })

        # 3. Workovers
        if has_workovers:
            w_wo = workovers[
                (workovers["well_id"] == wid)
                & (~workovers["is_censored"].fillna(False).astype(bool))
            ].sort_values(by="start_date")

            for _, wo_row in w_wo.iterrows():
                job_code = wo_row.get("catalogue_job_code")
                end_date: date = wo_row["end_date"]
                if job_code == "ADD_PERFORATION":
                    add_top = perf_top_m - rng.uniform(8.0, 20.0)
                    add_bottom = perf_top_m - 1.0
                    records.append({
                        "well_id": wid,
                        "field": fld,
                        "cluster_id": cid,
                        "zone": current_zone,
                        "top_m": round(float(add_top), 1),
                        "bottom_m": round(float(add_bottom), 1),
                        "spf": 6,
                        "perf_date": end_date,
                        "status": "OPEN",
                    })
                elif job_code == "RE_PERFORATION":
                    records.append({
                        "well_id": wid,
                        "field": fld,
                        "cluster_id": cid,
                        "zone": current_zone,
                        "top_m": round(perf_top_m, 1),
                        "bottom_m": round(perf_bottom_m, 1),
                        "spf": 6,
                        "perf_date": end_date,
                        "status": "OPEN",
                    })
                elif job_code in ("CEMENT_SQUEEZE", "STRADDLE_PACKER"):
                    pass

    return pd.DataFrame(records, columns=columns)
