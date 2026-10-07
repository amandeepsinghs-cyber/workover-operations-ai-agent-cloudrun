"""Corpus locations (overridable for tests via env vars)."""
from __future__ import annotations

import os
from pathlib import Path

from app.analytics.docs_pdf.facts import FIELDS, TYPE_DIRS
from app.settings import DATA_DIR


def docs_dir() -> Path:
    return Path(os.getenv("WELLPULSE_DOCS_DIR", str(DATA_DIR / "docs_pdf")))


def index_dir() -> Path:
    return Path(os.getenv("WELLPULSE_DOCS_INDEX_DIR", str(DATA_DIR / "index")))


def field_key(field: str) -> str:
    return FIELDS.get(field, "asset")


def doc_dir(field: str, doc_type: str, root: Path | None = None) -> Path:
    return (root or docs_dir()) / field_key(field) / TYPE_DIRS[doc_type]


def pdf_path(field: str, doc_type: str, doc_id: str, root: Path | None = None) -> Path:
    return doc_dir(field, doc_type, root) / f"{doc_id}.pdf"


def facts_path(field: str, doc_type: str, doc_id: str, root: Path | None = None) -> Path:
    return doc_dir(field, doc_type, root) / f"{doc_id}.facts.json"
