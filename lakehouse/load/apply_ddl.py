"""Dry-run, then apply, the lakehouse DDL (Stage X; authorised 2026-10-07).

Every ``lakehouse/ddl/NN_*.sql`` file is split into statements and dry-run first. A file is only
applied after all of its statements dry-run clean. Files are processed in name order because
later files depend on earlier ones (datasets before tables), so dry-run of file N+1 happens after
file N is applied. Statements are ``CREATE ... IF NOT EXISTS``: nothing is replaced or dropped.

    uv run --project backend python lakehouse/load/apply_ddl.py [--dry-run-only] [--files 20_silver_tables.sql]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C

DDL_DIR = Path(__file__).resolve().parents[1] / "ddl"
FORBIDDEN = re.compile(r"^\s*(DROP|TRUNCATE|DELETE|CREATE\s+OR\s+REPLACE)\b", re.IGNORECASE)


def statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in body.split(";\n") if s.strip().rstrip(";").strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run-only", action="store_true")
    ap.add_argument("--files", default="", help="comma-separated file names (default: all)")
    a = ap.parse_args(argv)

    from google.cloud import bigquery

    client = bigquery.Client(project=C.PROJECT_ID, location=C.LOCATION)
    files = sorted(DDL_DIR.glob("[0-9][0-9]_*.sql"))
    if a.files:
        wanted = set(a.files.split(","))
        files = [f for f in files if f.name in wanted]
    for f in files:
        stmts = statements(f.read_text())
        for s in stmts:
            if FORBIDDEN.search(s):
                raise SystemExit(f"refusing destructive statement in {f.name}: {s[:80]}")
        for s in stmts:
            cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, labels=C.LABELS)
            client.query(s.rstrip(";"), job_config=cfg, location=C.LOCATION)
        print(f"dry-run OK  {f.name}  ({len(stmts)} statements)")
        if a.dry_run_only:
            continue
        for s in stmts:
            cfg = bigquery.QueryJobConfig(labels=C.LABELS, maximum_bytes_billed=C.MAX_BYTES_BILLED)
            client.query(s.rstrip(";"), job_config=cfg, location=C.LOCATION).result()
        print(f"applied     {f.name}")
    if not a.dry_run_only:
        label_bronze(client)
    return 0


def label_bronze(client) -> None:
    """External-table DDL rejects OPTIONS(labels); set resource labels through the API instead."""
    n = 0
    for item in client.list_tables(f"{C.PROJECT_ID}.{C.BRONZE_DATASET}"):
        t = client.get_table(item.reference)
        if any(t.labels.get(k) != v for k, v in C.LABELS.items()):
            t.labels = {**t.labels, **C.LABELS}
            client.update_table(t, ["labels"])
            n += 1
    print(f"labelled    {n} bronze tables")


if __name__ == "__main__":
    raise SystemExit(main())
