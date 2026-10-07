"""Build the document index + page-level TF-IDF (D-17) from the rendered corpus.

    uv run python -m app.analytics.docs_pdf.index

Outputs (``data/index/``):
- ``document_index.parquet``: one row per document (doc_id, type, field, well, date, title, path, pages,
  bytes, has_text_layer, workover_id, intervention_class, job_code, legacy_doc_type, hero).
- ``doc_chunks.parquet``: one row per page (text from pypdf; scanned documents use ``scanned_text``
  from facts.json and are flagged ``scanned = true``).
- ``tfidf.pkl``: fitted vectorizer + L2-normalised float32 CSR matrix aligned with doc_chunks rows.
- ``corpus_manifest.json``: counts per field/type, bytes, scanned subset, build time (corpus size log).
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from app.analytics.docs_pdf.facts import DOC_TYPES, TYPE_DIRS
from app.analytics.docs_pdf.paths import docs_dir, index_dir
from app.analytics.docs_pdf.validate import extract_text, facts_files

TOKEN_PATTERN = r"(?u)\b[A-Za-z][A-Za-z0-9_\-]+\b"  # words + ids (GK-129, IC-04); bare numbers excluded


def _load(fp: str) -> tuple[dict, list[str]]:
    p = Path(fp)
    rec = json.loads(p.read_text())
    if rec.get("has_text_layer", True):
        pages = extract_text(p.with_name(p.name.replace(".facts.json", ".pdf")))
    else:
        pages = list(rec.get("scanned_text") or [])
    return rec, pages


def build(root: Path, out: Path, workers: int) -> dict:
    t0 = time.time()
    files = [str(p) for p in facts_files(root)]
    if not files:
        raise SystemExit(f"no rendered documents under {root}; run render first")
    pool = get_context("fork").Pool(workers)
    loaded = pool.map(_load, files, chunksize=64)
    pool.close()
    pool.join()
    docs, chunks = [], []
    for fp, (rec, pages) in zip(files, loaded):
        rel = str(Path(fp).relative_to(root)).replace(".facts.json", ".pdf")
        meta = rec.get("meta") or {}
        row = {
            "doc_id": rec["doc_id"], "doc_type": rec["doc_type"], "doc_type_code": TYPE_DIRS[rec["doc_type"]],
            "doc_type_name": DOC_TYPES[rec["doc_type"]], "field": rec["field"], "well_id": rec.get("well_id"),
            "doc_date": rec["doc_date"], "title": rec["title"], "path": rel, "uri": f"/api/docs/{rec['doc_id']}.pdf",
            "pages": int(rec.get("pages") or len(pages) or 1), "bytes": int(rec.get("bytes") or 0),
            "has_text_layer": bool(rec.get("has_text_layer", True)), "workover_id": meta.get("workover_id"),
            "intervention_class": meta.get("intervention_class"), "job_code": meta.get("job_code"),
            "legacy_doc_type": meta.get("legacy_doc_type"), "hero": bool(rec.get("hero")),
            "template": rec.get("template"),
        }
        docs.append(row)
        for i, text in enumerate(pages or [""], start=1):
            chunks.append({"chunk_id": f"{rec['doc_id']}#p{i}", "doc_id": rec["doc_id"], "page": i,
                           "doc_type": rec["doc_type"], "field": rec["field"], "well_id": rec.get("well_id"),
                           "doc_date": rec["doc_date"], "title": rec["title"],
                           "scanned": not row["has_text_layer"], "text": " ".join((text or "").split())})
    di = pd.DataFrame(docs).sort_values(["field", "doc_type", "doc_id"]).reset_index(drop=True)
    ch = pd.DataFrame(chunks).sort_values(["doc_id", "page"]).reset_index(drop=True)
    dup = di["doc_id"].duplicated()
    if dup.any():
        raise SystemExit(f"duplicate doc_ids in corpus: {di.loc[dup, 'doc_id'].head().tolist()}")
    small = len(ch) < 200
    vec = TfidfVectorizer(token_pattern=TOKEN_PATTERN, lowercase=True, sublinear_tf=True, min_df=1 if small else 2,
                          max_df=1.0 if small else 0.9, max_features=60000, dtype=np.float32)
    # title is prepended so short pages still carry their document identity
    X = vec.fit_transform((ch["title"] + " " + ch["text"]).tolist()).astype(np.float32)
    X.indices = X.indices.astype(np.int32)
    out.mkdir(parents=True, exist_ok=True)
    di.to_parquet(out / "document_index.parquet", index=False, compression="zstd")
    ch.to_parquet(out / "doc_chunks.parquet", index=False, compression="zstd")
    with open(out / "tfidf.pkl", "wb") as fh:
        pickle.dump({"vectorizer": vec, "matrix": X, "chunk_ids": ch["chunk_id"].tolist(),
                     "built_at": datetime.now(timezone.utc).isoformat()}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    pdf_bytes = int(di["bytes"].sum())
    facts_bytes = sum(Path(f).stat().st_size for f in files)
    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(), "documents": len(di), "chunks": len(ch),
        "pdf_bytes": pdf_bytes, "facts_json_bytes": facts_bytes,
        "corpus_mb": round((pdf_bytes + facts_bytes) / 1e6, 1),
        "index_mb": round(sum((out / n).stat().st_size for n in ("document_index.parquet", "doc_chunks.parquet", "tfidf.pkl")) / 1e6, 1),
        "by_field_type": {f"{k[0]}/{k[1]}": v for k, v in Counter(zip(di.field, di.doc_type)).items()},
        "scanned": {f"{k[0]}/{k[1]}": v for k, v in Counter(zip(di[~di.has_text_layer].field, di[~di.has_text_layer].doc_type)).items()},
        "vocabulary": len(vec.vocabulary_), "seconds": round(time.time() - t0, 1),
    }
    (out / "corpus_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 4))
    a = ap.parse_args(argv)
    m = build(Path(a.root) if a.root else docs_dir(), Path(a.out) if a.out else index_dir(), a.workers)
    print(f"[index] {m['documents']} documents, {m['chunks']} page chunks, vocabulary {m['vocabulary']}; "
          f"corpus {m['corpus_mb']} MB (PDF {m['pdf_bytes'] / 1e6:.1f} MB + facts {m['facts_json_bytes'] / 1e6:.1f} MB), "
          f"index {m['index_mb']} MB, {m['seconds']}s")
    print(f"[index] scanned subset: {m['scanned']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
