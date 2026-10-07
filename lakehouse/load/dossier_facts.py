"""Gold dossier_facts loader (SDD §15.1, D-17).

Extracts and flattens grounding facts from Stage O generated documents and dossiers
into BigQuery table ``wellpulse_gold.dossier_facts``.

    uv run --project backend python lakehouse/load/dossier_facts.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C

logger = logging.getLogger(__name__)


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


def flatten_facts(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten a nested JSON object into a list of (fact_key, fact_value) pairs.

    Keys use dotted paths and list indices use [i] notation.
    """
    items: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            items.extend(flatten_facts(v, new_prefix))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_prefix = f"{prefix}[{i}]"
            items.extend(flatten_facts(v, new_prefix))
    elif obj is None:
        pass
    elif isinstance(obj, bool):
        items.append((prefix, "true" if obj else "false"))
    else:
        items.append((prefix, str(obj)))
    return items


def parse_fact_number(val_str: str) -> float | None:
    """Parse numeric float from string if valid, excluding booleans and infinities."""
    if val_str.lower() in ("true", "false"):
        return None
    try:
        n = float(val_str)
        if math.isnan(n) or math.isinf(n):
            return None
        return n
    except (ValueError, TypeError):
        return None


def load_landing_document_index() -> pd.DataFrame:
    """Document metadata: Stage O corpus index if present (authoritative), else landing document_index."""
    corpus = C.DATA_DIR / "index" / "document_index.parquet"
    if corpus.exists():
        return pq.read_table(corpus).to_pandas().drop_duplicates(subset=["doc_id"])
    dfs: list[pd.DataFrame] = []
    for folder in ["geleki", "lakwa", "lakhmani", "asset"]:
        p = C.LANDING_DIR / folder / "document_index.parquet"
        if p.exists():
            dfs.append(pq.read_table(p).to_pandas())
    if not dfs:
        return pd.DataFrame(columns=["doc_id", "well_id", "doc_type", "doc_date", "gcs_uri"])
    combined = pd.concat(dfs, ignore_index=True)
    return combined.drop_duplicates(subset=["doc_id"])


def build_facts_frame(
    fact_files: list[Path],
    doc_index: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the normalized DataFrame for gold.dossier_facts from fact JSON files."""
    doc_idx_map: dict[str, dict[str, Any]] = {}
    if doc_index is not None and not doc_index.empty and "doc_id" in doc_index.columns:
        for r in doc_index.to_dict(orient="records"):
            doc_idx_map[str(r["doc_id"])] = r

    rows: list[dict[str, Any]] = []
    now_utc = pd.Timestamp.now(datetime.UTC)

    for p in fact_files:
        raw_bytes = p.read_bytes()
        facts_sha = hashlib.sha256(raw_bytes).hexdigest()
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Skipping malformed facts JSON %s: %s", p, exc)
            continue

        doc_id = p.name[:-11] if p.name.endswith(".facts.json") else p.stem
        pairs = flatten_facts(data)

        # Infer metadata
        well_id: str | None = None
        doc_type: str | None = None
        field: str | None = None

        if doc_id in doc_idx_map:
            meta = doc_idx_map[doc_id]
            well_id = meta.get("well_id")
            doc_type = meta.get("doc_type")
            field = infer_field(well_id)

        if not doc_type:
            if "dossiers" in p.parts:
                doc_type = "DOSSIER"
            else:
                doc_type = p.parent.name

        if not field:
            if "docs_pdf" in p.parts:
                rel = p.relative_to(C.DATA_DIR / "docs_pdf")
                if len(rel.parts) > 1:
                    field = rel.parts[0]
            if not field and well_id:
                field = infer_field(well_id)

        if not well_id:
            m = re.match(r"^(GK-\d+|LKW-\d+|LKM-\d+)", doc_id)
            if m:
                well_id = m.group(1)
                if not field:
                    field = infer_field(well_id)

        for key, val_str in pairs:
            num = parse_fact_number(val_str)
            rows.append(
                {
                    "doc_id": doc_id,
                    "well_id": well_id,
                    "field": field,
                    "doc_type": doc_type,
                    "fact_key": key,
                    "fact_value": val_str,
                    "fact_number": num,
                    "facts_sha256": facts_sha,
                    "_loaded_at": now_utc,
                }
            )

    target_cols = [
        "doc_id",
        "well_id",
        "field",
        "doc_type",
        "fact_key",
        "fact_value",
        "fact_number",
        "facts_sha256",
        "_loaded_at",
    ]
    if not rows:
        empty = pd.DataFrame(columns=target_cols)
        empty["fact_number"] = empty["fact_number"].astype("float64")
        return empty

    df = pd.DataFrame(rows)[target_cols]
    df["fact_number"] = df["fact_number"].astype("float64")
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="Print plan without writing to BigQuery")
    args = ap.parse_args(argv)

    files_docs = list((C.DATA_DIR / "docs_pdf").rglob("*.facts.json"))
    files_dossiers = list((C.DATA_DIR / "dossiers").glob("*.facts.json"))
    all_files = sorted(files_docs + files_dossiers)

    if not all_files:
        print("SKIP: no facts.json files found under docs_pdf/ or dossiers/ (Stage O output pending)")
        return 0

    doc_index = load_landing_document_index()
    facts_df = build_facts_frame(all_files, doc_index=doc_index)

    table_id = f"{C.PROJECT_ID}.{C.GOLD_DATASET}.dossier_facts"
    if args.dry_run:
        print(f"plan: load {len(facts_df)} fact rows from {len(all_files)} files into {table_id} (WRITE_TRUNCATE)")
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
        facts_df,
        target_table,
        job_config=job_config,
        location=C.LOCATION,
    )
    job.result()

    loaded_table = client.get_table(table_id)
    print(f"loaded {loaded_table.num_rows} rows into {table_id} (source: {len(facts_df)} rows)")
    assert loaded_table.num_rows == len(facts_df), (
        f"Row count mismatch: BQ={loaded_table.num_rows} vs facts={len(facts_df)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
