"""Stage DG generator: tubing_tally and deviation_survey (Slice 1).

Generates synthetic data-gap tables:
(a) tubing_tally: joint-by-joint tubing tally derived from CURRENT tubing_string rows
(b) deviation_survey: directional survey stations every 30m to TD using minimum curvature
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .common import FieldContext, well_rng

# Exposed constant listing wells with no tubing_string rows
NO_TUBING_WELLS: list[str] = []

# Nominal API Spec 5CT tubing dimensions keyed by od_in
API_NOMINAL: dict[float, dict[str, float]] = {
    2.375: {"id_in": 1.995, "drift_in": 1.901, "weight_ppf": 4.7},
    2.875: {"id_in": 2.441, "drift_in": 2.347, "weight_ppf": 6.5},
    3.5:   {"id_in": 2.992, "drift_in": 2.867, "weight_ppf": 9.3},
}

# Mapping of component names from tubing_string to standardized component_type
COMPONENT_MAP: dict[str, str] = {
    "GLM": "GL_MANDREL",
    "GL_MANDREL": "GL_MANDREL",
    "PUMP": "PUMP",
    "TUBING_ANCHOR": "TUBING_ANCHOR",
    "PACKER": "PACKER",
    "SEAT_NIPPLE": "SEAT_NIPPLE",
    "SEATING_NIPPLE": "SEAT_NIPPLE",
    "NIPPLE": "SEAT_NIPPLE",
    "PUP": "PUP",
}


def _split_tubing_segment(
    top_m: float,
    length_m: float,
    rng: np.random.Generator,
) -> list[tuple[str, float, float, float]]:
    """Split a TUBING row into joints (9.15 - 9.75 m) and a final PUP."""
    target_bottom = round(top_m + length_m, 2)
    curr_top = round(top_m, 2)
    rem = round(target_bottom - curr_top, 2)
    items: list[tuple[str, float, float, float]] = []

    # Leave room for a pup of at least 0.3m.
    # While rem > 9.75 + 1.5, we can safely pick a joint in [9.15, 9.75].
    while rem > 9.75 + 1.5:
        j_len = round(float(rng.uniform(9.15, 9.75)), 2)
        curr_bot = round(curr_top + j_len, 2)
        items.append(("TUBING_JOINT", curr_top, curr_bot, j_len))
        curr_top = curr_bot
        rem = round(target_bottom - curr_top, 2)

    # When remaining length is enough for another joint and a pup of >= 0.3m
    if rem >= 9.15 + 0.3:
        max_j = min(9.75, rem - 0.3)
        if max_j >= 9.15:
            j_len = round(float(rng.uniform(9.15, max_j)), 2)
            curr_bot = round(curr_top + j_len, 2)
            items.append(("TUBING_JOINT", curr_top, curr_bot, j_len))
            curr_top = curr_bot

    pup_len = round(target_bottom - curr_top, 2)
    items.append(("PUP", curr_top, target_bottom, pup_len))
    return items


def _min_curv_step(
    md1: float,
    md2: float,
    inc1_deg: float,
    inc2_deg: float,
    azi1_deg: float,
    azi2_deg: float,
) -> tuple[float, float]:
    """Calculate TVD increment and DLS (deg/30m) between two survey stations."""
    d_md = md2 - md1
    if d_md <= 0.0:
        return 0.0, 0.0

    i1 = np.radians(inc1_deg)
    i2 = np.radians(inc2_deg)
    a1 = np.radians(azi1_deg)
    a2 = np.radians(azi2_deg)

    cos_beta = np.cos(i1) * np.cos(i2) + np.sin(i1) * np.sin(i2) * np.cos(a2 - a1)
    cos_beta = float(np.clip(cos_beta, -1.0, 1.0))
    beta = float(np.arccos(cos_beta))

    if beta < 1e-7:
        rf = 1.0
    else:
        rf = (2.0 / beta) * np.tan(beta / 2.0)

    d_tvd = (d_md / 2.0) * (np.cos(i1) + np.cos(i2)) * rf
    dls = float(np.degrees(beta)) * (30.0 / d_md)
    return float(d_tvd), dls


def generate(ctx: FieldContext) -> dict[str, pd.DataFrame]:
    """Generate business DataFrames for tubing_tally and deviation_survey."""
    field = ctx.field
    wm = ctx.t("well_master")
    ts = ctx.t("tubing_string")

    # Track wells with no tubing_string rows
    wm_well_ids = set(wm["well_id"])
    ts_well_ids = set(ts["well_id"])
    missing_tubing = sorted(list(wm_well_ids - ts_well_ids))
    global NO_TUBING_WELLS
    NO_TUBING_WELLS = missing_tubing

    # ---------------------------------------------------------
    # (a) tubing_tally: grain well x joint
    # ---------------------------------------------------------
    tally_rows: list[dict[str, object]] = []

    # Process each well present in tubing_string in deterministic order
    well_ids_with_ts = sorted(ts["well_id"].unique())
    for well_id in well_ids_with_ts:
        w_ts = ts[ts["well_id"] == well_id]
        if w_ts.empty:
            continue

        # Filter to CURRENT tubing_string rows (latest install_date set)
        max_install_date = w_ts["install_date"].max()
        curr_ts = w_ts[w_ts["install_date"] == max_install_date].sort_values("seq")

        # Deterministic per-well RNG for grade and joint lengths
        rng_tally = well_rng(well_id, "tubing_tally")
        well_grade = str(rng_tally.choice(["J-55", "N-80"]))

        joint_no = 1
        for _, row in curr_ts.iterrows():
            cluster_id = row["cluster_id"]
            comp = str(row["component"]).strip()
            od_raw = float(row["od_in"])
            od = round(od_raw, 3)

            if od in API_NOMINAL:
                nom = API_NOMINAL[od]
                id_in = nom["id_in"]
                drift_in = nom["drift_in"]
                weight_ppf = nom["weight_ppf"]
                grade = well_grade
            else:
                id_in = np.nan
                drift_in = np.nan
                weight_ppf = np.nan
                grade = "UNKNOWN"

            if comp == "TUBING":
                sub_items = _split_tubing_segment(row["top_m"], row["length_m"], rng_tally)
                for ctype, top_md, bot_md, length in sub_items:
                    tally_rows.append({
                        "well_id": well_id,
                        "field": field,
                        "cluster_id": cluster_id,
                        "joint_no": joint_no,
                        "component_type": ctype,
                        "top_md_m": top_md,
                        "bottom_md_m": bot_md,
                        "length_m": length,
                        "od_in": od,
                        "id_in": id_in,
                        "drift_in": drift_in,
                        "grade": grade,
                        "weight_ppf": weight_ppf,
                    })
                    joint_no += 1
            else:
                ctype = COMPONENT_MAP.get(comp, comp)
                top_md = round(float(row["top_m"]), 2)
                length = round(float(row["length_m"]), 2)
                bot_md = round(top_md + length, 2)
                tally_rows.append({
                    "well_id": well_id,
                    "field": field,
                    "cluster_id": cluster_id,
                    "joint_no": joint_no,
                    "component_type": ctype,
                    "top_md_m": top_md,
                    "bottom_md_m": bot_md,
                    "length_m": length,
                    "od_in": od,
                    "id_in": id_in,
                    "drift_in": drift_in,
                    "grade": grade,
                    "weight_ppf": weight_ppf,
                })
                joint_no += 1

    df_tally = pd.DataFrame(tally_rows)
    if df_tally.empty:
        df_tally = pd.DataFrame(columns=[
            "well_id", "field", "cluster_id", "joint_no", "component_type",
            "top_md_m", "bottom_md_m", "length_m", "od_in", "id_in",
            "drift_in", "grade", "weight_ppf",
        ])

    # ---------------------------------------------------------
    # (b) deviation_survey: grain well x station
    # ---------------------------------------------------------
    survey_rows: list[dict[str, object]] = []

    wm_sorted = wm.sort_values("well_id")
    for _, row in wm_sorted.iterrows():
        well_id = str(row["well_id"])
        cluster_id = row["cluster_id"]
        td_md = float(row["total_depth_md_m"])
        td_tvd = float(row["total_depth_tvd_m"])
        max_dls = float(row["max_dls_deg_30m"]) if pd.notna(row.get("max_dls_deg_30m")) else np.nan

        rng_dev = well_rng(well_id, "deviation_survey")
        azi_deg = round(float(rng_dev.uniform(0.0, 360.0)), 2)

        stations_list = list(np.arange(0.0, td_md, 30.0))
        if not stations_list or (td_md - stations_list[-1]) > 1e-3:
            stations_list.append(td_md)
        stations = np.array(stations_list)

        if (td_md - td_tvd) < 5.0:
            # Vertical well profile: slight random walk with inclination < 3 degrees
            incs = np.zeros_like(stations)
            inc_cur = 0.0
            for i in range(1, len(stations)):
                inc_cur = np.clip(inc_cur + float(rng_dev.uniform(-0.3, 0.3)), 0.05, 2.8)
                incs[i] = round(inc_cur, 2)
        else:
            # Deviated build-and-hold profile
            kop_choice = float(rng_dev.choice([400.0, 450.0, 500.0, 550.0, 600.0]))
            kop = min(kop_choice, td_md * 0.25)
            br = 1.0 if np.isnan(max_dls) else min(1.0, max(0.5, max_dls - 0.1))

            def _sim_tvd(i_deg: float) -> float:
                build_len = 30.0 * (i_deg / br)
                eob = kop + build_len
                test_incs = np.zeros_like(stations)
                mb = (stations > kop) & (stations < eob)
                test_incs[mb] = (stations[mb] - kop) / build_len * i_deg
                mh = stations >= eob
                test_incs[mh] = i_deg

                tvd_accum = 0.0
                for idx in range(1, len(stations)):
                    dt, _ = _min_curv_step(
                        stations[idx - 1], stations[idx],
                        test_incs[idx - 1], test_incs[idx],
                        azi_deg, azi_deg,
                    )
                    tvd_accum += dt
                return tvd_accum - td_tvd

            i_sol = brentq(_sim_tvd, 0.1, 75.0)
            build_len = 30.0 * (i_sol / br)
            eob = kop + build_len
            incs = np.zeros_like(stations)
            mb = (stations > kop) & (stations < eob)
            incs[mb] = (stations[mb] - kop) / build_len * i_sol
            mh = stations >= eob
            incs[mh] = i_sol

        cur_tvd = 0.0
        survey_rows.append({
            "well_id": well_id,
            "field": field,
            "cluster_id": cluster_id,
            "md_m": 0.0,
            "inc_deg": 0.0,
            "azi_deg": azi_deg,
            "tvd_m": 0.0,
            "dls_deg_30m": 0.0,
        })

        for i in range(1, len(stations)):
            dt, dls = _min_curv_step(
                stations[i - 1], stations[i],
                incs[i - 1], incs[i],
                azi_deg, azi_deg,
            )
            cur_tvd += dt
            # TVD is monotonic non-decreasing and bounded by MD
            tvd_val = min(round(cur_tvd, 2), round(stations[i], 2))
            survey_rows.append({
                "well_id": well_id,
                "field": field,
                "cluster_id": cluster_id,
                "md_m": round(float(stations[i]), 2),
                "inc_deg": round(float(incs[i]), 2),
                "azi_deg": azi_deg,
                "tvd_m": tvd_val,
                "dls_deg_30m": round(float(dls), 2),
            })

    df_survey = pd.DataFrame(survey_rows)
    if df_survey.empty:
        df_survey = pd.DataFrame(columns=[
            "well_id", "field", "cluster_id", "md_m", "inc_deg", "azi_deg",
            "tvd_m", "dls_deg_30m",
        ])

    return {
        "tubing_tally": df_tally,
        "deviation_survey": df_survey,
    }
