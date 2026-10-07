"""Runtime document store: document index lookups + TF-IDF page search (TC-026 backing, D-17).

Loaded lazily and cached; ``reload()`` drops the cache (tests / rebuilds).
"""
from __future__ import annotations

import pickle
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.docs_pdf.paths import docs_dir, index_dir

TYPE_ALIASES = {f"D{i}": f"D{i:02d}" for i in range(1, 12)} | {f"D{i:02d}": f"D{i:02d}" for i in range(1, 12)}
_lock = threading.Lock()
_store: "DocStore | None" = None


def norm_doc_types(doc_types: str | list[str] | None) -> list[str] | None:
    if not doc_types:
        return None
    items = doc_types.split(",") if isinstance(doc_types, str) else list(doc_types)
    out = []
    for t in items:
        t = t.strip().upper()
        if not t:
            continue
        if t not in TYPE_ALIASES:
            raise ValueError(f"unknown doc_type {t!r}; expected D1..D11")
        out.append(TYPE_ALIASES[t])
    return out or None


@dataclass
class DocStore:
    docs: pd.DataFrame
    chunks: pd.DataFrame
    vectorizer: Any
    matrix: Any
    built_at: str
    root: Path

    @classmethod
    def load(cls) -> "DocStore | None":
        idx = index_dir()
        need = [idx / "document_index.parquet", idx / "doc_chunks.parquet", idx / "tfidf.pkl"]
        if not all(p.exists() for p in need):
            return None
        docs = pd.read_parquet(need[0])
        chunks = pd.read_parquet(need[1])
        with open(need[2], "rb") as fh:
            tf = pickle.load(fh)  # noqa: S301 - produced by our own index build
        if len(tf["chunk_ids"]) != len(chunks) or tf["chunk_ids"][:1] != chunks["chunk_id"].head(1).tolist():
            raise RuntimeError("tfidf.pkl is not aligned with doc_chunks.parquet; rebuild the index")
        docs = docs.where(pd.notna(docs), None)
        return cls(docs=docs.set_index(pd.Index(docs["doc_id"].to_numpy(), name=None)), chunks=chunks, vectorizer=tf["vectorizer"],
                   matrix=tf["matrix"], built_at=tf.get("built_at", ""), root=docs_dir())

    # ---------------------------------------------------------------- lookups
    def pdf_path(self, doc_id: str) -> Path | None:
        if doc_id not in self.docs.index:
            return None
        p = self.root / self.docs.loc[doc_id, "path"]
        return p if p.exists() else None

    def doc(self, doc_id: str) -> dict | None:
        if doc_id not in self.docs.index:
            return None
        return self.docs.loc[doc_id].to_dict()

    def provenance(self) -> dict:
        return {"tool_id": "TC-026", "source": "data/index (TF-IDF, D-17)", "index_built_at": self.built_at,
                "documents": int(len(self.docs)), "chunks": int(len(self.chunks))}

    def list_for_well(self, well_id: str, doc_types: list[str] | None = None, limit: int = 500) -> list[dict]:
        d = self.docs[self.docs["well_id"] == well_id]
        if doc_types:
            d = d[d["doc_type"].isin(doc_types)]
        d = d.sort_values(["doc_date", "doc_id"], ascending=[False, True]).head(limit)
        return [hit_from_doc(r) for r in d.to_dict("records")]

    def search(self, q: str, well_id: str | None = None, field: str | None = None,
               doc_types: list[str] | None = None, top_k: int = 10) -> list[dict]:
        mask = np.ones(len(self.chunks), dtype=bool)
        if well_id:
            mask &= (self.chunks["well_id"] == well_id).to_numpy()
        if field:
            mask &= (self.chunks["field"].str.lower() == field.lower()).to_numpy() | (self.chunks["field"] == "ALL").to_numpy()
        if doc_types:
            mask &= self.chunks["doc_type"].isin(doc_types).to_numpy()
        rows = np.flatnonzero(mask)
        if not len(rows) or not q.strip():
            return []
        qv = self.vectorizer.transform([q])
        scores = np.asarray((self.matrix[rows] @ qv.T).todense()).ravel()
        order = np.argsort(-scores, kind="stable")
        hits, seen = [], set()
        terms = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9_\-]+", q.lower()) if len(t) > 2]
        for i in order:
            if scores[i] <= 0:
                break
            ch = self.chunks.iloc[rows[i]]
            if ch["doc_id"] in seen:
                continue
            seen.add(ch["doc_id"])
            h = hit_from_doc(self.docs.loc[ch["doc_id"]].to_dict(), page=int(ch["page"]), score=float(scores[i]))
            h["snippet"] = snippet(ch["text"], terms)
            hits.append(h)
            if len(hits) >= top_k:
                break
        return hits


def snippet(text: str, terms: list[str], width: int = 240) -> str:
    low = text.lower()
    pos = min([low.find(t) for t in terms if low.find(t) >= 0] or [0])
    start = max(0, pos - width // 3)
    s = text[start:start + width]
    return ("..." if start else "") + s + ("..." if start + width < len(text) else "")


def hit_from_doc(r: dict, page: int = 1, score: float | None = None) -> dict:
    scanned = not bool(r.get("has_text_layer", True))
    return {
        "doc_id": r["doc_id"], "title": r["title"], "doc_type": r["doc_type_code"], "doc_type_id": r["doc_type"],
        "doc_type_name": r["doc_type_name"], "doc_date": r["doc_date"], "well_id": r.get("well_id"),
        "field": r["field"], "page": page, "pages": int(r.get("pages") or 1), "score": None if score is None else round(score, 4),
        "snippet": None, "uri": f"/api/docs/{r['doc_id']}.pdf#page={page}", "pdf_url": f"/api/docs/{r['doc_id']}.pdf",
        "has_text_layer": not scanned, "scanned": scanned, "flags": ["SCANNED"] if scanned else [],
        "workover_id": r.get("workover_id"), "intervention_class": r.get("intervention_class"), "job_code": r.get("job_code"),
    }


def get_store() -> DocStore | None:
    global _store
    with _lock:
        if _store is None:
            _store = DocStore.load()
        return _store


def reload() -> None:
    global _store
    with _lock:
        _store = None
