"""Silver doc_chunks loader (SDD §15.1, D-17).

Mirrors the TF-IDF retrieval index over D1-D11 PDFs and SOPs into BigQuery
table ``wellpulse_silver.doc_chunks``. Re-buildable mirror: loaded with WRITE_TRUNCATE.

    uv run --project backend python lakehouse/load/doc_chunks.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C


def infer_field(well_id: Any) -> str | None:
    """Infer field name from standard well ID prefix."""
    if not isinstance(well_id, str):
        return None
    if well_id.startswith("GK-"):
        return "Geleki"
    if well_id.startswith("LKW-"):
        return "Lakwa"
    if well_id.startswith("LKM-"):
        return "Lakhmani"
    return None


def to_date_or_none(d: Any) -> datetime.date | None:
    """Safely convert value to datetime.date or None."""
    if pd.isna(d) or d is None:
        return None
    if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
        return d
    try:
        ts = pd.to_datetime(d)
        return ts.date() if not pd.isna(ts) else None
    except (ValueError, TypeError):
        return None


def load_landing_document_index() -> pd.DataFrame:
    """Read and concatenate document_index from all landing folders."""
    dfs: list[pd.DataFrame] = []
    for folder in ["geleki", "lakwa", "lakhmani", "asset"]:
        p = C.LANDING_DIR / folder / "document_index.parquet"
        if p.exists():
            dfs.append(pq.read_table(p).to_pandas())
    if not dfs:
        return pd.DataFrame(columns=["doc_id", "well_id", "doc_type", "doc_date", "gcs_uri"])
    combined = pd.concat(dfs, ignore_index=True)
    return combined.drop_duplicates(subset=["doc_id"])


def build_chunk_frame(
    df: pd.DataFrame,
    doc_index: pd.DataFrame | None = None,
    file_bytes: bytes | None = None,
) -> pd.DataFrame:
    """Pure transformation of doc_chunks raw frame to typed Silver schema."""
    target_cols = [
        "chunk_id",
        "doc_id",
        "page",
        "chunk_seq",
        "text",
        "well_id",
        "field",
        "doc_type",
        "doc_date",
        "gcs_uri",
        "char_count",
        "index_version",
        "_silver_loaded_at",
    ]
    if df.empty:
        empty_df = pd.DataFrame(columns=target_cols)
        empty_df["page"] = empty_df["page"].astype("Int64")
        empty_df["chunk_seq"] = empty_df["chunk_seq"].astype("Int64")
        empty_df["char_count"] = empty_df["char_count"].astype("Int64")
        return empty_df

    res = df.copy()

    # Index version default = sha256 (first 12 hex) of bytes or placeholder
    default_version = (
        hashlib.sha256(file_bytes).hexdigest()[:12] if file_bytes is not None else "000000000000"
    )
    if "index_version" not in res.columns:
        res["index_version"] = default_version
    else:
        res["index_version"] = res["index_version"].fillna(default_version)

    # Ensure required doc_id / page / text exist
    if "doc_id" not in res.columns:
        res["doc_id"] = ""
    if "page" not in res.columns:
        res["page"] = 1
    if "text" not in res.columns:
        res["text"] = ""

    # Ensure chunk_seq
    if "chunk_seq" not in res.columns:
        res["chunk_seq"] = res.groupby(["doc_id", "page"]).cumcount()
    else:
        cum = res.groupby(["doc_id", "page"]).cumcount()
        res["chunk_seq"] = res["chunk_seq"].fillna(cum)

    # Missing optional columns
    for col in ["well_id", "field", "doc_type", "doc_date", "gcs_uri"]:
        if col not in res.columns:
            res[col] = None

    # Enrich from doc_index landing parquets when missing
    if doc_index is not None and not doc_index.empty and "doc_id" in doc_index.columns:
        idx_dedup = doc_index.drop_duplicates(subset=["doc_id"]).set_index("doc_id")
        for col in ["well_id", "doc_type", "doc_date", "gcs_uri"]:
            if col in idx_dedup.columns:
                mapping = idx_dedup[col].to_dict()
                mapped_vals = res["doc_id"].map(mapping)
                res[col] = res[col].fillna(mapped_vals)

    # Field from well_id prefix if missing
    inferred_fields = res["well_id"].apply(infer_field)
    res["field"] = res["field"].replace("", None).fillna(inferred_fields)

    # char_count and chunk_id
    res["char_count"] = res["text"].fillna("").astype(str).str.len()
    res["chunk_id"] = (
        res["doc_id"].astype(str)
        + ":p"
        + res["page"].fillna(1).astype(int).astype(str)
        + ":c"
        + res["chunk_seq"].fillna(0).astype(int).astype(str)
    )

    # Dates and timestamps
    res["doc_date"] = res["doc_date"].apply(to_date_or_none)
    res["_silver_loaded_at"] = pd.Timestamp.now(datetime.UTC)

    # Types
    res["page"] = res["page"].astype("Int64")
    res["chunk_seq"] = res["chunk_seq"].astype("Int64")
    res["char_count"] = res["char_count"].astype("Int64")
    for col in ["chunk_id", "doc_id", "text", "well_id", "field", "doc_type", "gcs_uri", "index_version"]:
        res[col] = res[col].astype("object")

    return res[target_cols]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="Print plan without writing to BigQuery")
    args = ap.parse_args(argv)

    index_file = C.DATA_DIR / "index" / "doc_chunks.parquet"
    if not index_file.exists():
        print(f"SKIP: index file {index_file} not found (Stage O output pending)")
        return 0

    file_bytes = index_file.read_bytes()
    raw_df = pq.read_table(index_file).to_pandas()
    doc_index = load_landing_document_index()
    chunk_df = build_chunk_frame(raw_df, doc_index=doc_index, file_bytes=file_bytes)

    table_id = f"{C.PROJECT_ID}.{C.SILVER_DATASET}.doc_chunks"
    if args.dry_run:
        print(f"plan: load {len(chunk_df)} rows from {index_file} into {table_id} (WRITE_TRUNCATE)")
        return 0

    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound

    client = bigquery.Client(project=C.PROJECT_ID, location=C.LOCATION)
    try:
        target_table = client.get_table(table_id)
    except NotFound:
        print(f"ERROR: target table {table_id} does not exist. Apply lakehouse/ddl first.")
        return 2

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=target_table.schema,
        labels=C.LABELS,
    )
    job = client.load_table_from_dataframe(
        chunk_df,
        target_table,
        job_config=job_config,
        location=C.LOCATION,
    )
    job.result()

    loaded_table = client.get_table(table_id)
    print(f"loaded {loaded_table.num_rows} rows into {table_id} (source: {len(chunk_df)} rows)")
    assert loaded_table.num_rows == len(chunk_df), (
        f"Row count mismatch: BQ={loaded_table.num_rows} vs parquet={len(chunk_df)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
