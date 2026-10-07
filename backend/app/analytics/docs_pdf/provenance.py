"""Slot provenance helpers.

Per-slot sources ("table.column") are identical for almost every document of a type, so
``facts.json`` stores only the per-document overrides plus ``sources_ref`` pointing at the
type's slot catalogue (``templates/slot_catalogue/DNN.json``). ``expand_sources`` rebuilds
the full slot -> source map for one record (used by ``/api/docs/{id}/meta``).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOGUE_DIR = Path(__file__).parent / "templates" / "slot_catalogue"


@lru_cache(maxsize=16)
def catalogue_sources(doc_type: str) -> dict[str, str]:
    p = CATALOGUE_DIR / f"{doc_type}.json"
    if not p.exists():
        return {}
    cat = json.loads(p.read_text())
    out = {k: v.get("source", "") for k, v in (cat.get("slots") or {}).items()}
    out.update({f"table:{k}": v.get("source", "") for k, v in (cat.get("tables") or {}).items() if isinstance(v, dict)})
    return out


def compact_sources(doc_type: str, sources: dict[str, str]) -> dict[str, str]:
    """Keep only the slots whose source differs from (or is absent in) the type catalogue."""
    base = catalogue_sources(doc_type)
    return {k: v for k, v in sources.items() if base.get(k) != v}


def expand_sources(rec: dict) -> dict[str, str]:
    base = catalogue_sources(rec.get("doc_type", ""))
    used = list((rec.get("facts") or {}).keys())
    full = {k: base.get(k, "") for k in used}
    full.update(rec.get("sources") or {})
    return full
