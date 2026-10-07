"""``BigQueryRepository``: the ``DATA_BACKEND=bigquery`` implementation of ``WellRepository`` (SDD §5.7, Stage X).

Design: it *is* a ``ParquetRepository`` whose single raw-read primitive ``_read(folder, table,
columns)`` is served from the Silver layer (``wellpulse_silver.*``, ``asia-south1``) instead of the
landing files. Every adapter, cache and route therefore runs the same code on both backends, which
is what makes the parquet == BigQuery parity test meaningful (BDD F-15 "Backend parity").

Query rules (SDD §15.3):
- always a ``_landing_folder`` predicate; well-keyed tables also carry ``field`` (cluster pruning);
- ``daily_production`` also carries ``production_date <= AS_OF`` (partition pruning);
- ``ORDER BY _source_row`` so frames keep the landing-file row order;
- ``maximum_bytes_billed`` and job labels ``app=wellpulse, component=api`` on every job;
- results are cached for the process lifetime (inherited ``cached_property`` frames).

Arrow is the interchange format both ways (BigQuery Storage API -> ``pyarrow.Table`` ->
``to_pandas()``), so dtypes match ``pd.read_parquet`` exactly. The one Bronze-time cast
(``well_master.max_dls_deg_30m``: Arrow ``null`` -> FLOAT64) is reversed here so the frame is
identical (all-None object column).
"""

from __future__ import annotations

import os
from functools import cached_property

import pandas as pd

from app import settings
from app.analytics.generator.fields import FIELD_CONFIGS

from .parquet_repo import ParquetRepository

PROJECT_ID = os.getenv("WELLPULSE_BQ_PROJECT", "workover-operations-agentic-ai")
LOCATION = os.getenv("WELLPULSE_BQ_LOCATION", "asia-south1")
SILVER_DATASET = os.getenv("WELLPULSE_BQ_SILVER_DATASET", "wellpulse_silver")
MAX_BYTES_BILLED = int(os.getenv("WELLPULSE_BQ_MAX_BYTES", str(2 * 1024**3)))
JOB_LABELS = {"app": "wellpulse", "component": "api", "stage": "x"}

# Columns the lakehouse adds (lakehouse/config.py LAKEHOUSE_COLUMNS); never returned to callers.
LAKEHOUSE_COLUMNS = ("_source_row", "_landing_folder", "_bronze_dt", "_silver_loaded_at")
# Columns that are Arrow ``null`` in the landing contract (cast to FLOAT64 in Bronze).
NULL_TYPED_COLUMNS = {"well_master": ("max_dls_deg_30m",)}
FIELD_FOLDERS = {f.lower(): f for f in FIELD_CONFIGS}


class BigQueryRepository(ParquetRepository):
    def __init__(self, client=None, project: str = PROJECT_ID, dataset: str = SILVER_DATASET):
        super().__init__()
        self.project = project
        self.dataset = dataset
        self._client = client
        self.queries: list[str] = []  # audit trail (tests assert the pruning predicates)

    @cached_property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project, location=LOCATION)
        return self._client

    @cached_property
    def _schemas(self) -> dict[str, list[str]]:
        """{table: [contract columns in Silver order]} via one INFORMATION_SCHEMA query."""
        sql = (f"SELECT table_name, column_name FROM `{self.project}.{self.dataset}.INFORMATION_SCHEMA.COLUMNS` "
               f"ORDER BY table_name, ordinal_position")
        out: dict[str, list[str]] = {}
        for r in self._query(sql, {}).to_pylist():
            if r["column_name"] not in LAKEHOUSE_COLUMNS:
                out.setdefault(r["table_name"], []).append(r["column_name"])
        return out

    def _query(self, sql: str, params: dict):
        from google.cloud import bigquery

        qp = [bigquery.ScalarQueryParameter(k, t, v) for k, (t, v) in params.items()]
        cfg = bigquery.QueryJobConfig(query_parameters=qp, labels=JOB_LABELS,
                                      maximum_bytes_billed=MAX_BYTES_BILLED)
        self.queries.append(sql)
        job = self.client.query(sql, job_config=cfg, location=LOCATION)
        return job.result().to_arrow(create_bqstorage_client=True)

    # -- the one primitive ParquetRepository reads through ---------------------------------------------
    def _read(self, folder: str, table: str, columns: list[str] | None = None) -> pd.DataFrame:
        contract = self._schemas.get(table)
        if contract is None:
            raise LookupError(f"{self.dataset}.{table} not found in BigQuery (run lakehouse loaders)")
        cols = columns or contract
        select = ", ".join(f"`{c}`" for c in cols)
        where = ["_landing_folder = @folder"]
        params: dict[str, tuple[str, object]] = {"folder": ("STRING", folder)}
        if folder in FIELD_FOLDERS and "field" in contract:
            where.append("field = @field")
            params["field"] = ("STRING", FIELD_FOLDERS[folder])
        if table == "daily_production":
            where.append("production_date <= @as_of")
            params["as_of"] = ("DATE", settings.AS_OF)
        sql = (f"SELECT {select} FROM `{self.project}.{self.dataset}.{table}` "
               f"WHERE {' AND '.join(where)} ORDER BY _source_row")
        df = self._query(sql, params).to_pandas()
        for c in NULL_TYPED_COLUMNS.get(table, ()):
            if c in df.columns and df[c].isna().all():
                df[c] = pd.Series([None] * len(df), dtype=object)
        return df
