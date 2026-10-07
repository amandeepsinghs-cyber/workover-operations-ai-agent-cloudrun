"""Landing parquet -> BRONZE objects in GCS (SDD §15.1, Stage X).

Layout: ``gs://<bucket>/bronze/<table>/dt=<BRONZE_DT>/landing_folder=<folder>/part-000.parquet``

Each object is the landing file as delivered by the generator, with exactly one appended lineage
column ``_source_row`` (0-based row ordinal) so Silver can preserve file order (the parquet
repository's row order) and the BigQuery backend can reproduce it bit-for-bit. All-NULL columns
of Arrow type ``null`` (``well_master.max_dls_deg_30m``) are written as float64 because
BigQuery cannot type a NULL-typed parquet column.

Idempotent: re-running with the same batch overwrites the same object names; objects whose
md5 already matches are skipped. Nothing is ever deleted.

    uv run --project backend python lakehouse/load/bronze_upload.py [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C


def bronze_object_name(table: str, folder: str) -> str:
    return f"{C.BRONZE_PREFIX}/{table}/dt={C.BRONZE_DT}/landing_folder={folder}/part-000.parquet"


def bronze_bytes(path: Path) -> tuple[bytes, int]:
    """Landing file + ``_source_row``; null-typed columns cast to float64."""
    t = pq.read_table(path)
    cols, fields = [], []
    for f, col in zip(t.schema, t.columns):
        if f.type == pa.null():
            col = col.cast(pa.float64())
            f = pa.field(f.name, pa.float64())
        cols.append(col)
        fields.append(f)
    cols.append(pa.array(range(t.num_rows), type=pa.int64()))
    fields.append(pa.field("_source_row", pa.int64()))
    out = pa.Table.from_arrays(cols, schema=pa.schema(fields))
    buf = io.BytesIO()
    pq.write_table(out, buf, compression="snappy")
    return buf.getvalue(), t.num_rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    jobs = [(t, p) for t, paths in C.landing_tables().items() for p in paths]
    bucket = None
    if not a.dry_run:
        from google.cloud import storage

        bucket = storage.Client(project=C.PROJECT_ID).bucket(C.BUCKET)

    def one(job: tuple[str, Path]) -> tuple[str, int, str]:
        table, path = job
        data, n = bronze_bytes(path)
        name = bronze_object_name(table, path.parent.name)
        if bucket is None:
            return name, n, "plan"
        md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
        blob = bucket.get_blob(name)
        if blob is not None and blob.md5_hash == md5:
            return name, n, "skip"
        bucket.blob(name).upload_from_string(data, content_type="application/octet-stream")
        return name, n, "upload"

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(one, jobs))
    total = 0
    for name, n, action in sorted(results):
        total += n
        print(f"{action:6s} gs://{C.BUCKET}/{name}  rows={n}")
    print(f"{len(results)} objects, {total} rows, batch dt={C.BRONZE_DT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
