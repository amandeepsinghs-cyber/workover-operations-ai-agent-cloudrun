"""Export Silver tables from BigQuery to GCS Parquet (SDD §15.1, D-17).

Layout: ``gs://<bucket>/silver_exports/<table>/dt=<BRONZE_DT>/<table>-*.parquet``

Exports all typed Silver tables (including doc_chunks) to snappy-compressed Parquet
for offline analytics, backup, and downstream validation. Skips empty tables.

    uv run --project backend python lakehouse/load/export_silver.py [--dry-run] [--tables daily_production,well_master]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="List plan without executing BigQuery extract jobs")
    ap.add_argument("--tables", default="", help="Comma-separated table names to export (default: all Silver tables)")
    args = ap.parse_args(argv)

    all_tables = list(C.TABLE_KEYS.keys()) + ["doc_chunks"]
    if args.tables:
        wanted = {t.strip() for t in args.tables.split(",") if t.strip()}
        tables = [t for t in all_tables if t in wanted]
    else:
        tables = all_tables

    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound

    client = bigquery.Client(project=C.PROJECT_ID, location=C.LOCATION)

    for t in tables:
        table_ref = f"{C.PROJECT_ID}.{C.SILVER_DATASET}.{t}"
        dest_uri = f"gs://{C.BUCKET}/{C.SILVER_EXPORTS_PREFIX}/{t}/dt={C.BRONZE_DT}/{t}-*.parquet"

        try:
            table_obj = client.get_table(table_ref)
        except NotFound:
            print(f"table missing: {table_ref}")
            continue

        if table_obj.num_rows == 0:
            print(f"skip {t}: table is empty (0 rows)")
            continue

        if args.dry_run:
            print(f"plan: export {table_ref} ({table_obj.num_rows} rows) -> {dest_uri}")
            continue

        job_config = bigquery.ExtractJobConfig(
            destination_format="PARQUET",
            compression="SNAPPY",
            labels=C.LABELS,
        )
        extract_job = client.extract_table(
            table_ref,
            dest_uri,
            job_config=job_config,
            location=C.LOCATION,
        )
        extract_job.result()
        print(f"exported {t}: {table_obj.num_rows} rows -> {dest_uri}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
