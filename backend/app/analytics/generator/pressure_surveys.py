"""Pressure surveys generator.

Stage N / WellPulse v0.4 synthetic data generation.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd


def generate_pressure_surveys(
    wells: pd.DataFrame,
    daily: pd.DataFrame,
    start: date,
    end: date,
    seed: int,
) -> pd.DataFrame:
    """Generate pressure surveys table for given wells over [start, end].

    Columns:
        well_id, field, cluster_id, survey_id, survey_date,
        sbhp_kgcm2, fbhp_kgcm2, pi_bpd_per_kgcm2, fluid_level_m, datum_tvd_m
    """
    rng = np.random.default_rng(seed)
    columns = [
        "well_id",
        "field",
        "cluster_id",
        "survey_id",
        "survey_date",
        "sbhp_kgcm2",
        "fbhp_kgcm2",
        "pi_bpd_per_kgcm2",
        "fluid_level_m",
        "datum_tvd_m",
    ]
    if wells.empty:
        return pd.DataFrame(columns=columns)

    # Pre-group daily by well_id once
    daily_by_well = {}
    if daily is not None and not daily.empty:
        prod_mask = daily["is_producing"].fillna(False).astype(bool)
        df_prod = daily[prod_mask]
        if not df_prod.empty:
            p_dates = df_prod["production_date"]
            if hasattr(p_dates.iloc[0], "date"):
                p_dates_arr = np.array([
                    d.date() if hasattr(d, "date") else d for d in p_dates
                ])
            else:
                p_dates_arr = p_dates.to_numpy()

            rates_arr = df_prod["liquid_rate_blpd"].to_numpy(dtype=float)
            well_ids = df_prod["well_id"].to_numpy()

            for u_wid in np.unique(well_ids):
                w_idx = np.where(well_ids == u_wid)[0]
                daily_by_well[u_wid] = (p_dates_arr[w_idx], rates_arr[w_idx])

    records = []
    for _, row in wells.iterrows():
        wid = row["well_id"]
        fld = row["field"]
        cid = row["cluster_id"]
        perf_top_m = float(row["perf_top_m"])
        td_md_m = float(row["total_depth_md_m"])
        td_tvd_m = float(row["total_depth_tvd_m"])

        datum_tvd_m = round(perf_top_m * td_tvd_m / td_md_m, 1)

        curr_date = start + timedelta(days=int(rng.integers(0, 366)))
        while curr_date <= end:
            # Draw order per survey: normal, uniform
            norm = float(rng.normal(0.0, 3.0))
            u = float(rng.uniform(0.35, 0.65))

            survey_id = f"PS-{wid}-{curr_date:%Y%m%d}"
            years = (curr_date - start).days / 365.25
            sbhp = round(0.085 * datum_tvd_m * (1.0 - 0.02 * years) + norm, 1)
            fbhp = round(sbhp * u, 1)

            # Liquid & pi
            d_start = curr_date - timedelta(days=30)
            d_end = curr_date - timedelta(days=1)
            pi = None
            if wid in daily_by_well:
                w_dates, w_rates = daily_by_well[wid]
                mask = (w_dates >= d_start) & (w_dates <= d_end) & ~np.isnan(w_rates)
                if np.any(mask):
                    liquid = float(np.mean(w_rates[mask]))
                    diff = sbhp - fbhp
                    if diff != 0:
                        pi = round(liquid / diff, 3)

            # fluid_level_m
            fl = np.clip(
                datum_tvd_m - fbhp * 10.0 / 0.9, 50.0, datum_tvd_m - 10.0
            )
            fluid_level_m = round(float(fl), 1)

            records.append({
                "well_id": wid,
                "field": fld,
                "cluster_id": cid,
                "survey_id": survey_id,
                "survey_date": curr_date,
                "sbhp_kgcm2": sbhp,
                "fbhp_kgcm2": fbhp,
                "pi_bpd_per_kgcm2": np.nan if pi is None else float(pi),
                "fluid_level_m": fluid_level_m,
                "datum_tvd_m": datum_tvd_m,
            })

            # Repeatedly add integers(365, 731) days while date <= end
            interval_days = int(rng.integers(365, 731))
            curr_date = curr_date + timedelta(days=interval_days)

    return pd.DataFrame(records, columns=columns)
