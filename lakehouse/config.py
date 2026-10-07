"""Single source of truth for the WellPulse medallion lakehouse (SDD §15, Stage X).

Everything that names a GCP resource lives here so DDL generation, loaders, the Dataform
project and ``backend/app/data_access/bigquery_repo.py`` agree.

Environment overrides use explicit ``WELLPULSE_*`` names because the developer shell exports
``GOOGLE_CLOUD_PROJECT`` for a different project (see stage brief).
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ID = os.getenv("WELLPULSE_BQ_PROJECT", "workover-operations-agentic-ai")
LOCATION = os.getenv("WELLPULSE_BQ_LOCATION", "asia-south1")
BUCKET = os.getenv("WELLPULSE_LAKEHOUSE_BUCKET", "workover-operations-agentic-ai-datalake")

BRONZE_DATASET = "wellpulse_bronze"
SILVER_DATASET = "wellpulse_silver"
GOLD_DATASET = "wellpulse_gold"

BRONZE_PREFIX = "bronze"
DOCUMENTS_PREFIX = "documents"
SILVER_EXPORTS_PREFIX = "silver_exports"

# Bronze batch partition (``dt=``). The landing files were produced by the generator run of
# 2026-09-23 (= AS_OF, D-15); re-uploading the same batch overwrites the same objects, so the
# loader is idempotent.
BRONZE_DT = os.getenv("WELLPULSE_BRONZE_DT", "2026-09-23")
AS_OF = "2026-09-23"

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDING_DIR = Path(os.getenv("WELLPULSE_LANDING_DIR", str(REPO_ROOT / "backend" / "app" / "data" / "landing")))
DATA_DIR = LANDING_DIR.parent

# Resource + job labels (resource attribution; SDD §15.3).
LABELS = {"app": "wellpulse", "stage": "x", "datacloud": "jetski"}

# Hard cap per query (cost control, SDD §15.3). The whole Silver layer is < 200 MB.
MAX_BYTES_BILLED = int(os.getenv("WELLPULSE_BQ_MAX_BYTES", str(2 * 1024**3)))

# Lineage columns added by the lakehouse (not present in the landing contract).
#   _source_row     0-based row ordinal inside the landing file (added in Bronze; preserves file order)
#   _landing_folder hive partition key: asset | geleki | lakwa | lakhmani
#   _bronze_dt      hive partition key: batch date
#   _silver_loaded_at load timestamp (Silver only)
LAKEHOUSE_COLUMNS = ["_source_row", "_landing_folder", "_bronze_dt", "_silver_loaded_at"]

# Natural keys (verified unique on the Stage N landing data) used for Silver de-duplication/MERGE.
TABLE_KEYS: dict[str, list[str]] = {
    "daily_production": ["well_id", "production_date"],
    "well_master": ["well_id"],
    "workover_history": ["workover_id"],
    "well_status_history": ["episode_id"],
    "well_tests": ["test_id"],
    "casing_tally": ["well_id", "string_type"],
    "tubing_string": ["well_id", "seq"],
    "perforation_intervals": ["well_id", "zone", "top_m", "perf_date"],
    "pressure_surveys": ["survey_id"],
    "formation_tops": ["well_id", "formation"],
    "operations_events": ["event_id"],
    "document_index": ["doc_id"],
    "well_offsets": ["well_id", "offset_well_id"],
    "well_run": ["run_date", "well_id"],
    "decision_log": ["decision_id"],
    "draft_plan": ["draft_plan_id"],
    "cluster_master": ["cluster_id"],
    "facility_master": ["facility_id"],
    "field_master": ["field"],
    "field_targets": ["field", "month"],
    "job_catalogue": ["job_code"],
    "mro_inventory": ["item_code", "base"],
    "rig_calendar": ["rig_id", "date"],
}

# Physical design of Silver (SDD §15.1). daily_production: PARTITION BY production_date
# CLUSTER BY field, well_id (V§5). Well-keyed tables cluster by well_id; reference tables by key.
SILVER_PARTITION: dict[str, str] = {"daily_production": "production_date"}
SILVER_CLUSTER: dict[str, list[str]] = {
    "daily_production": ["field", "well_id"],
    "cluster_master": ["field", "cluster_id"],
    "facility_master": ["field", "facility_id"],
    "field_master": ["field"],
    "field_targets": ["field", "month"],
    "job_catalogue": ["job_code"],
    "mro_inventory": ["item_code"],
    "rig_calendar": ["rig_id"],
}
DEFAULT_CLUSTER = ["well_id"]

# BigQuery type for each Arrow type found in the landing parquet.
ARROW_TO_BQ = {
    "string": "STRING",
    "large_string": "STRING",
    "double": "FLOAT64",
    "float": "FLOAT64",
    "int64": "INT64",
    "int32": "INT64",
    "bool": "BOOL",
    "date32[day]": "DATE",
    "timestamp[us]": "TIMESTAMP",
    "timestamp[ns]": "TIMESTAMP",
    "timestamp[us, tz=UTC]": "TIMESTAMP",
    # all-NULL columns (e.g. well_master.max_dls_deg_30m) are written to Bronze as float64
    "null": "FLOAT64",
}


def fq(dataset: str, table: str) -> str:
    """Fully-qualified, back-quoted BigQuery table name."""
    return f"`{PROJECT_ID}.{dataset}.{table}`"


def gcs(*parts: str) -> str:
    return "gs://" + "/".join([BUCKET, *[p.strip("/") for p in parts]])


def landing_tables() -> dict[str, list[Path]]:
    """{table: [landing parquet paths]} in the folder order the parquet repository uses."""
    order = ["geleki", "lakwa", "lakhmani", "asset"]
    out: dict[str, list[Path]] = {}
    for folder in order:
        for p in sorted((LANDING_DIR / folder).glob("*.parquet")):
            out.setdefault(p.stem, []).append(p)
    return out
