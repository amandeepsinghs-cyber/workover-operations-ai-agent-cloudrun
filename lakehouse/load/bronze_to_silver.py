"""BRONZE external tables -> SILVER contract tables, with reconciliation (X-F2, SDD §15.1).

For every landing table:
  MERGE wellpulse_silver.<t> USING (de-duplicated Bronze) ON <natural key>
    WHEN MATCHED THEN UPDATE every column   (re-delivered rows replace in place)
    WHEN NOT MATCHED THEN INSERT
De-duplication keeps the latest batch (``dt`` DESC, ``_ingested_at`` DESC, ``_source_row`` DESC)
per natural key (``config.TABLE_KEYS``, verified unique on the Stage N data). MERGE makes the
load idempotent without truncating or dropping anything.

Reconciliation (Gate X "Silver row counts = Bronze = parquet"): per table, the landing parquet
row count, the Bronze external-table count and the Silver count are compared, plus a content
checksum (sum of FARM_FINGERPRINT over the natural key) between Bronze and Silver.

    uv run --project backend python lakehouse/load/bronze_to_silver.py [--tables a,b] [--check-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C


def _client():
    from google.cloud import bigquery

    return bigquery.Client(project=C.PROJECT_ID, location=C.LOCATION)


def _run(client, sql: str):
    from google.cloud import bigquery

    cfg = bigquery.QueryJobConfig(labels=C.LABELS, maximum_bytes_billed=C.MAX_BYTES_BILLED)
    return client.query(sql, job_config=cfg, location=C.LOCATION).result()


def silver_columns(client, table: str) -> list[str]:
    return [f.name for f in client.get_table(f"{C.PROJECT_ID}.{C.SILVER_DATASET}.{table}").schema]


def merge_sql(table: str, columns: list[str]) -> str:
    key = C.TABLE_KEYS[table]
    contract = [c for c in columns if c not in C.LAKEHOUSE_COLUMNS]
    src_cols = ",\n      ".join(
        [f"b.`{c}`" for c in contract + ["_source_row"]]
        + ["b.landing_folder AS `_landing_folder`", "b.dt AS `_bronze_dt`", "CURRENT_TIMESTAMP() AS `_silver_loaded_at`"]
    )
    # FLOAT64 keys (perforation_intervals.top_m) can't be window-partitioned directly
    part = "TO_JSON_STRING(STRUCT(" + ", ".join(f"b.`{k}`" for k in key) + "))"
    on = " AND ".join(f"T.`{k}` = S.`{k}`" for k in key)
    upd = ",\n    ".join(f"`{c}` = S.`{c}`" for c in columns if c not in key)
    ins_cols = ", ".join(f"`{c}`" for c in columns)
    ins_vals = ", ".join(f"S.`{c}`" for c in columns)
    return f"""
MERGE {C.fq(C.SILVER_DATASET, table)} T
USING (
  SELECT
      {src_cols}
  FROM {C.fq(C.BRONZE_DATASET, table)} b
  WHERE TRUE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY {part} ORDER BY b.dt DESC, b._ingested_at DESC, b._source_row DESC) = 1
) S
ON {on}
WHEN MATCHED THEN UPDATE SET
    {upd}
WHEN NOT MATCHED THEN INSERT ({ins_cols}) VALUES ({ins_vals})
"""


def landing_count(table: str) -> int:
    return sum(pq.read_metadata(p).num_rows for p in C.landing_tables()[table])


def reconcile(client, table: str) -> dict:
    key = C.TABLE_KEYS[table]
    fp = "FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(" + ", ".join(f"`{k}`" for k in key) + ")))"
    # sum of fingerprints can overflow INT64: use BIT_XOR + COUNT as an order-free checksum
    sql = f"""
SELECT 'bronze' AS layer, COUNT(*) AS n, BIT_XOR({fp}) AS chk FROM {C.fq(C.BRONZE_DATASET, table)}
UNION ALL
SELECT 'silver', COUNT(*), BIT_XOR({fp}) FROM {C.fq(C.SILVER_DATASET, table)}
"""
    rows = {r["layer"]: (r["n"], r["chk"]) for r in _run(client, sql)}
    out = {
        "table": table,
        "parquet": landing_count(table),
        "bronze": rows["bronze"][0],
        "silver": rows["silver"][0],
        "checksum_match": rows["bronze"][1] == rows["silver"][1],
    }
    out["ok"] = out["parquet"] == out["bronze"] == out["silver"] and out["checksum_match"]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--print-sql", action="store_true")
    a = ap.parse_args(argv)
    tables = [t for t in C.TABLE_KEYS if not a.tables or t in a.tables.split(",")]
    client = _client()
    results = []
    for t in tables:
        if not a.check_only:
            sql = merge_sql(t, silver_columns(client, t))
            if a.print_sql:
                print(sql)
            job = _run(client, sql)
            print(f"merged {t:24s} affected={getattr(job, 'num_dml_affected_rows', None)}")
        r = reconcile(client, t)
        results.append(r)
        print(json.dumps(r))
    bad = [r["table"] for r in results if not r["ok"]]
    print(f"RECONCILIATION: {len(results) - len(bad)}/{len(results)} tables OK" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
