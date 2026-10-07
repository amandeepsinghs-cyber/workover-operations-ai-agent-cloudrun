"""SRP survival model (CoxPH) — port of the ADK Stage E ``model/train.py`` onto the v0.4 landing layout.

    uv run python -m app.analytics.model.train --exclude-prepend

``--exclude-prepend`` trains on exactly the frozen Geleki v0.3.0 rows (daily ``is_prepend = False``,
workovers ``is_prepend = False``) and must reproduce the v0.3.0 holdout C-index (0.7128, Gate N).
Without the flag the 24-month prepend is included and artifacts get a ``_with_prepend`` suffix, so the
pinned v0.3.0 model (``coxph_srp_v1.pkl`` / ``coxph-v1.0-geleki``) is never overwritten by it.
Modelling logic, seeds, penalizer and split are unchanged from v0.3.0.
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index

from app import settings

BASE_DAILY = ["well_id", "production_date", "liquid_rate_blpd", "water_cut_pct", "chp_kgcm2", "spm",
              "runtime_fraction", "is_producing"]
EXPECTED_C_INDEX = 0.7128


def build_srp_survival_dataset(landing: Path, exclude_prepend: bool) -> pd.DataFrame:
    g = landing / "geleki"
    wells = pd.read_parquet(g / "well_master.parquet")
    daily = pd.read_parquet(g / "daily_production.parquet", columns=BASE_DAILY + ["is_prepend"])
    workovers = pd.read_parquet(g / "workover_history.parquet")
    if exclude_prepend:
        daily = daily[~daily["is_prepend"].astype(bool)]
        workovers = workovers[~workovers["is_prepend"].astype(bool)]
    workovers = workovers[workovers["outcome"] != "IN_PROGRESS"]

    srp_wells = wells[wells["lift_type"] == "SRP"].copy()
    srp_ids = set(srp_wells["well_id"])

    prod_daily = daily[(daily["well_id"].isin(srp_ids)) & (daily["is_producing"] == True)]
    well_agg = (
        prod_daily.groupby("well_id")
        .agg(
            liquid_rate_blpd=("liquid_rate_blpd", "mean"),
            water_cut_pct=("water_cut_pct", "mean"),
            chp_kgcm2=("chp_kgcm2", "mean"),
            spm=("spm", "mean"),
            runtime_fraction=("runtime_fraction", "mean"),
        )
        .reset_index()
    )

    df_feat = srp_wells[["well_id", "completion_date", "plunger_diameter_in", "stroke_length_in"]].merge(
        well_agg, on="well_id", how="inner"
    )
    df_feat["completion_date"] = pd.to_datetime(df_feat["completion_date"]).dt.date
    df_feat["well_age_days"] = df_feat["completion_date"].apply(lambda d: (settings.AS_OF - d).days)

    ap = (math.pi / 4.0) * (df_feat["plunger_diameter_in"] ** 2)
    theo_blpd = 0.1166 * ap * df_feat["stroke_length_in"] * df_feat["spm"] * df_feat["runtime_fraction"]
    df_feat["pump_fillage_gap_blpd"] = np.maximum(0.0, theo_blpd - df_feat["liquid_rate_blpd"])
    df_feat["wc_squared_norm"] = (df_feat["water_cut_pct"] / 75.0) ** 2

    wo_srp = workovers[
        (workovers["well_id"].isin(srp_ids)) & (workovers["run_life_days"].notna()) & (workovers["run_life_days"] > 15)
    ].copy()
    wo_srp["start_date"] = pd.to_datetime(wo_srp["start_date"]).dt.date
    wo_srp = wo_srp.sort_values(["well_id", "start_date"])

    wo_srp["prior_run_life_days"] = wo_srp.groupby("well_id")["run_life_days"].shift(1)
    median_rl = float(wo_srp["run_life_days"].median())
    wo_srp["prior_run_life_days"] = wo_srp["prior_run_life_days"].fillna(median_rl)

    df_surv = wo_srp.merge(
        df_feat[["well_id", "liquid_rate_blpd", "water_cut_pct", "wc_squared_norm", "pump_fillage_gap_blpd",
                 "chp_kgcm2", "well_age_days"]],
        on="well_id",
        how="inner",
    )
    df_surv["duration"] = df_surv["run_life_days"].astype(float)
    df_surv["event"] = (~df_surv["is_censored"].astype(bool)).astype(int)

    rng = np.random.default_rng(42)
    df_surv["liquid_rate_obs"] = df_surv["liquid_rate_blpd"] * rng.normal(1.0, 0.29, size=len(df_surv))
    df_surv["wc_sq_obs"] = df_surv["wc_squared_norm"] * rng.normal(1.0, 0.29, size=len(df_surv))
    df_surv["fillage_gap_obs"] = df_surv["pump_fillage_gap_blpd"] + rng.normal(0.0, 16.0, size=len(df_surv))
    df_surv["chp_obs"] = df_surv["chp_kgcm2"] + rng.normal(0.0, 2.5, size=len(df_surv))
    return df_surv


def train_and_evaluate(landing: Path, model_dir: Path, exclude_prepend: bool) -> bool:
    df = build_srp_survival_dataset(landing, exclude_prepend)
    n_total = len(df)
    n_cens = int((df["event"] == 0).sum())
    print(f"Dataset ({'v0.3.0 rows only' if exclude_prepend else 'incl. prepend'}): {n_total} SRP episodes "
          f"({n_total - n_cens} failures, {n_cens} censored [{n_cens / n_total:.1%}])")

    unique_wells = sorted(df["well_id"].unique())
    split_idx = int(len(unique_wells) * 0.70)
    train_wells = set(unique_wells[:split_idx])
    holdout_wells = set(unique_wells[split_idx:])
    feature_cols = ["liquid_rate_obs", "wc_sq_obs", "fillage_gap_obs", "chp_obs", "well_age_days"]
    train_df = df[df["well_id"].isin(train_wells)][feature_cols + ["duration", "event"]].copy()
    test_df = df[df["well_id"].isin(holdout_wells)][feature_cols + ["duration", "event", "prior_run_life_days"]].copy()

    cph = CoxPHFitter(penalizer=0.15)
    cph.fit(train_df, duration_col="duration", event_col="event")
    pred_hazard = cph.predict_partial_hazard(test_df[feature_cols]).to_numpy().ravel()
    c_model = float(concordance_index(test_df["duration"].to_numpy(), -pred_hazard, test_df["event"].to_numpy()))
    tb = (test_df["liquid_rate_obs"] / np.maximum(test_df["prior_run_life_days"], 30.0)).to_numpy()
    c_tb = float(concordance_index(test_df["duration"].to_numpy(), -tb, test_df["event"].to_numpy()))
    print(f"  CoxPH holdout C-index : {c_model:.4f}   (v0.3.0 pinned {EXPECTED_C_INDEX})")
    print(f"  Trigger B C-index     : {c_tb:.4f}")

    suffix = "" if exclude_prepend else "_with_prepend"
    model_dir.mkdir(parents=True, exist_ok=True)
    with open(model_dir / f"coxph_srp_v1{suffix}.pkl", "wb") as f:
        pickle.dump(cph, f)
    payload = {
        "model_version": "coxph-v1.0-geleki",
        "lift_subset": "SRP_ONLY",
        "training_rows": "v030_core_only" if exclude_prepend else "v030_core_plus_prepend",
        "n_episodes_total": n_total,
        "n_episodes_train": len(train_df),
        "n_episodes_holdout": len(test_df),
        "right_censored_fraction": round(n_cens / n_total, 4),
        "holdout_c_index": round(c_model, 4),
        "trigger_b_c_index": round(c_tb, 4),
        "c_index_gain_over_trigger_b": round(c_model - c_tb, 4),
        "target_band": [0.65, 0.72],
        "gates_passed": bool(0.65 <= c_model <= 0.72 and c_model > c_tb),
        "coefficients": cph.summary[["coef", "exp(coef)", "p"]].to_dict(orient="index"),
    }
    with open(model_dir / f"survival_model_metrics{suffix}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    if exclude_prepend and round(c_model, 4) != EXPECTED_C_INDEX:
        print(f"GATE N FAILED: C-index {c_model:.4f} != {EXPECTED_C_INDEX}")
        return False
    return bool(0.65 <= c_model <= 0.72 and c_model > c_tb) or not exclude_prepend


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude-prepend", action="store_true")
    ap.add_argument("--landing", default=str(settings.LANDING_DIR))
    ap.add_argument("--model-dir", default=str(settings.MODEL_DIR))
    a = ap.parse_args(argv)
    return 0 if train_and_evaluate(Path(a.landing), Path(a.model_dir), a.exclude_prepend) else 1


if __name__ == "__main__":
    sys.exit(main())
