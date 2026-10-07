"""Port of workover_well_intervention/tests/test_contracts.py Gate C + Gate E checks onto the v0.4 Geleki core rows (is_prepend == False).

The ADK tool tests (TC-001..TC-018, agent turns, A2UI) are ported in Stage P/Q when those tools exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app import settings
from app.analytics.model.train import train_and_evaluate

BASELINE_DIR = Path(__file__).resolve().parent.parent / "baseline" / "landing_v030"

if not BASELINE_DIR.exists() or not (BASELINE_DIR / "job_catalogue.parquet").exists():
    pytest.skip(
        f"baseline landing_v030 missing at {BASELINE_DIR}; skipping test_contracts_geleki",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def landing() -> Path:
    """Return landing path if data is generated, else skip."""
    landing_dir = settings.LANDING_DIR
    if not (landing_dir / "asset" / "field_targets.parquet").exists():
        pytest.skip("landing data not generated; run app.analytics.generator.generate")
    return landing_dir


def test_dc001_to_dc004_well_master_invariants(landing: Path) -> None:
    wells = pd.read_parquet(landing / "geleki" / "well_master.parquet")

    # DC-001: 142 wells
    assert len(wells) == 142, f"DC-001: Expected 142 wells, found {len(wells)}"

    # DC-002: no perf_top_m >= perf_bottom_m
    invalid_depths = wells[wells["perf_top_m"] >= wells["perf_bottom_m"]]
    assert len(invalid_depths) == 0, f"DC-002: Found {len(invalid_depths)} wells with perf_top_m >= perf_bottom_m"

    # DC-003: no total_depth_tvd_m > total_depth_md_m
    invalid_tvd = wells[wells["total_depth_tvd_m"] > wells["total_depth_md_m"]]
    assert len(invalid_tvd) == 0, f"DC-003: Found {len(invalid_tvd)} wells with TVD > MD"

    # DC-004: no SRP well with null plunger_diameter_in or stroke_length_in
    srp_wells = wells[wells["lift_type"] == "SRP"]
    missing_geom = srp_wells[srp_wells["plunger_diameter_in"].isna() | srp_wells["stroke_length_in"].isna()]
    assert len(missing_geom) == 0, f"DC-004: Found {len(missing_geom)} SRP wells with missing plunger/stroke geometry"


def test_dc014_null_rates_when_shut_in(landing: Path) -> None:
    daily = pd.read_parquet(landing / "geleki" / "daily_production.parquet")
    core_daily = daily[~daily["is_prepend"].astype(bool)]

    shut_in = core_daily[~core_daily["is_producing"].astype(bool)]
    assert shut_in["oil_rate_bopd"].isna().all(), "DC-014: Shut-in core rows must have NULL oil_rate_bopd"

    producing = core_daily[core_daily["is_producing"].astype(bool)]
    assert producing["oil_rate_bopd"].notna().all(), "DC-014: Producing core rows must have non-NULL oil_rate_bopd"


def test_dc010_liquid_balance(landing: Path) -> None:
    daily = pd.read_parquet(landing / "geleki" / "daily_production.parquet")
    core_daily = daily[~daily["is_prepend"].astype(bool)]
    producing = core_daily[core_daily["is_producing"].astype(bool)]

    diff = (producing["liquid_rate_blpd"] - (producing["oil_rate_bopd"] + producing["water_rate_bwpd"])).abs()
    assert (diff <= 0.15).all(), f"DC-010: Liquid balance violated on {(diff > 0.15).sum()} rows"


def test_at092_availability_identity(landing: Path) -> None:
    wells = pd.read_parquet(landing / "geleki" / "well_master.parquet")
    daily = pd.read_parquet(landing / "geleki" / "daily_production.parquet")
    core_daily = daily[~daily["is_prepend"].astype(bool)]

    total_days = len(core_daily)
    down_days = (~core_daily["is_producing"].astype(bool)).sum()
    frac_down_total = (down_days / total_days) * 100.0

    active_well_ids = wells[wells["status"] == "ACTIVE"]["well_id"].tolist()
    daily_active = core_daily[core_daily["well_id"].isin(active_well_ids)]
    active_down_days = (~daily_active["is_producing"].astype(bool)).sum()
    frac_down_active = (active_down_days / len(daily_active)) * 100.0

    assert abs(frac_down_total - 20.0) <= 1.5, (
        f"AT-092: Measured FRACTION_DOWN_TOTAL {frac_down_total:.2f}% outside 20.0% ± 1.5 pp band"
    )
    assert abs(frac_down_active - 16.3) <= 1.5, (
        f"AT-092: Measured FRACTION_DOWN_ACTIVE {frac_down_active:.2f}% outside 16.3% ± 1.5 pp band"
    )


def test_catalogue_backward_compatibility(landing: Path) -> None:
    jobs = pd.read_parquet(landing / "asset" / "job_catalogue.parquet")
    base_jobs = pd.read_parquet(BASELINE_DIR / "job_catalogue.parquet")

    assert len(jobs) == 29, f"Expected 29 jobs in catalogue, found {len(jobs)}"
    assert list(jobs.iloc[:28]["job_code"]) == list(base_jobs["job_code"]), (
        "First 28 job codes do not match baseline v0.3.0 job codes"
    )
    assert "GLV_REPLACE" in set(jobs["job_code"]), "GLV_REPLACE missing from job catalogue"


def test_dc080_to_dc084_supporting_and_spine_tables(landing: Path) -> None:
    offsets = pd.read_parquet(landing / "geleki" / "well_offsets.parquet")
    assert len(offsets) == 142 * 6, f"DC-080: Expected {142 * 6} offset pairs, found {len(offsets)}"

    mro = pd.read_parquet(landing / "asset" / "mro_inventory.parquet")
    assert len(mro) >= 10, f"DC-081: MRO inventory incomplete, found {len(mro)} rows < 10"

    rigs = pd.read_parquet(landing / "asset" / "rig_calendar.parquet")
    assert rigs["rig_id"].nunique() == 15, (
        f"DC-082: Expected 15 unique rig_ids, found {rigs['rig_id'].nunique()}"
    )

    docs = pd.read_parquet(landing / "geleki" / "document_index.parquet")
    assert len(docs) >= 40, f"DC-084: Expected >= 40 documents, found {len(docs)}"

    well_run = pd.read_parquet(landing / "geleki" / "well_run.parquet")
    assert len(well_run) == 142, f"DC-060: Expected 142 rows in well_run, found {len(well_run)}"
    assert well_run["tool_trace"].notna().all(), "DC-064: Found NULL tool_trace in well_run"

    draft_plan = pd.read_parquet(landing / "geleki" / "draft_plan.parquet")
    assert len(draft_plan) >= 5, f"Expected >= 5 rows in draft_plan, found {len(draft_plan)}"

    decision_log = pd.read_parquet(landing / "geleki" / "decision_log.parquet")
    assert len(decision_log) >= 3, f"Expected >= 3 rows in decision_log, found {len(decision_log)}"

    lineage_cols = ("_ingested_at", "_source_system", "_source_file", "_batch_id")
    for col in lineage_cols:
        assert col in well_run.columns, f"Missing lineage column {col} in well_run"


def test_gate_e_survival_model(landing: Path, tmp_path: Path) -> None:
    passed = train_and_evaluate(landing, tmp_path, exclude_prepend=True)
    assert passed is True, "train_and_evaluate returned False"

    metrics_path = tmp_path / "survival_model_metrics.json"
    assert metrics_path.exists(), f"Metrics file missing at {metrics_path}"

    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    c_index = metrics["holdout_c_index"]
    tb_c_index = metrics["trigger_b_c_index"]

    assert c_index == 0.7128, f"Expected holdout_c_index == 0.7128, got {c_index}"
    assert 0.65 <= c_index <= 0.72, f"C-index {c_index} outside target band [0.65, 0.72]"
    assert c_index > tb_c_index, f"C-index {c_index} not greater than Trigger B C-index {tb_c_index}"


def test_k1_core_workovers(landing: Path) -> None:
    wo = pd.read_parquet(landing / "geleki" / "workover_history.parquet")
    core_wo = wo[~wo["is_prepend"].astype(bool)]
    nc = core_wo[~core_wo["is_censored"].astype(bool)]

    assert nc["catalogue_job_code"].notna().all(), (
        "K-1: Found non-censored core workovers with NULL catalogue_job_code"
    )
    assert nc["intervention_class"].notna().all(), (
        "K-1: Found non-censored core workovers with NULL intervention_class"
    )
    assert "job_code" in core_wo.columns, "K-1: job_code column dropped from workover_history"
