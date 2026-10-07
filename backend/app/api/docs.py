"""Document corpus routes (Stage O, SDD §13.4, F-10 / F-14, TC-026 backing).

- ``GET /api/docs/search``            TF-IDF page search (D-17) -> ``DocumentHit[]`` envelope
- ``GET /api/docs/{doc_id}.pdf``      the PDF (``application/pdf``; supports ``#page=N`` client-side)
- ``GET /api/docs/{doc_id}/meta``     index row + facts.json provenance for one document
- ``GET /api/wells/{well_id}/documents``  documents of one well (optionally filtered / searched)

Envelope: ``{status, data, message, missing_fields, provenance}`` (SDD §13.1). When the corpus has not
been built the analytics routes return ``status = UNAVAILABLE`` with the build command in ``message``.

RBAC (Stage Y, SDD §16): ``docs.sop_dossier`` for every persona, plus doc_type gating via
``rbac.doc_type_allowed`` — ED: no D04 tally / D05 CBL (construction summary only); FIELD_ENGINEER: no D10
monthly field production report (field roll-up). Lists / search silently exclude denied types; asking for
only denied types, or opening a denied PDF / meta, → 403 UNAVAILABLE envelope.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.agent import rbac

from app.analytics.docs_pdf.provenance import expand_sources
from app.analytics.docs_pdf.store import get_store, norm_doc_types
from app.data_access.repository import RetiredWellId, get_repository

router = APIRouter()

BUILD_HINT = "document corpus not built: run `uv run python -m app.analytics.docs_pdf.build` in backend/"


def _envelope(status: str, data, message: str = "", provenance: dict | None = None, missing: list | None = None) -> dict:
    return {"status": status, "data": data, "message": message, "missing_fields": missing or [],
            "provenance": provenance or {"tool_id": "TC-026"}}


def _types_or_422(doc_types: str | None) -> list[str] | None:
    try:
        return norm_doc_types(doc_types)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _scoped_types(persona: str, requested: list[str] | None) -> list[str] | None:
    """Doc types this persona may see (None = no filter). Only-denied request → 403 envelope."""
    types = rbac.allowed_doc_types(persona, requested)
    if types is not None and not types:
        raise rbac.PermissionDenied(persona, rbac.doc_type_capability(requested[0] if requested else None),
                                    f"doc_type {','.join(requested or [])}")
    return types


def _check_doc_access(persona: str, store, doc_id: str) -> None:
    row = store.doc(doc_id) if store is not None else None
    if row is not None and not rbac.doc_type_allowed(persona, row.get("doc_type")):
        raise rbac.PermissionDenied(persona, rbac.doc_type_capability(row.get("doc_type")),
                                    f"doc_type {row.get('doc_type')}")


def _check_well(well_id: str) -> None:
    try:
        w = get_repository().get_well(well_id)
    except RetiredWellId:
        raise HTTPException(status_code=404, detail="GLK- IDs retired in v0.4; use GK-")
    if w is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")


@router.get("/docs/search")
def search_documents(
    q: str = Query(..., min_length=1, description="free-text query"),
    well_id: str | None = None,
    field: str | None = None,
    doc_types: str | None = Query(None, description="comma list, e.g. D2,D5"),
    top_k: int = Query(10, ge=1, le=50),
    persona: str = Depends(rbac.require("docs.sop_dossier")),
):
    types = _scoped_types(persona, _types_or_422(doc_types))
    store = get_store()
    if store is None:
        return _envelope("UNAVAILABLE", [], BUILD_HINT, missing=["document_index"])
    hits = store.search(q, well_id=well_id, field=field, doc_types=types, top_k=top_k)
    msg = f"{len(hits)} document(s) matched" if hits else "no document matched the query and filters"
    return _envelope("OK" if hits else "LOW_CONFIDENCE", hits, msg,
                     provenance=store.provenance() | {"query": q, "filters": {"well_id": well_id, "field": field, "doc_types": types}})


@router.get("/docs/{doc_id}.pdf")
def get_document_pdf(doc_id: str, persona: str = Depends(rbac.require("docs.sop_dossier"))):
    store = get_store()
    _check_doc_access(persona, store, doc_id)
    path = store.pdf_path(doc_id) if store is not None else None
    if path is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found" + ("" if store else f" ({BUILD_HINT})"))
    return FileResponse(str(path), media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{doc_id}.pdf"'})


@router.get("/docs/{doc_id}/meta")
def get_document_meta(doc_id: str, persona: str = Depends(rbac.require("docs.sop_dossier"))):
    store = get_store()
    if store is None:
        return _envelope("UNAVAILABLE", None, BUILD_HINT, missing=["document_index"])
    _check_doc_access(persona, store, doc_id)
    row = store.doc(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    facts_file = (store.root / row["path"]).with_name(f"{doc_id}.facts.json")
    facts = json.loads(facts_file.read_text()) if facts_file.exists() else {}
    data = {k: row[k] for k in row} | {"facts": facts.get("facts", {}), "sources": expand_sources(facts) if facts else {},
                                       "tables": list((facts.get("tables") or {}).keys())}
    return _envelope("OK", data, "", provenance=store.provenance() | {"facts_json": str(facts_file.name)})


@router.get("/wells/{well_id}/documents")
def get_well_documents(
    well_id: str,
    doc_types: str | None = Query(None, description="comma list, e.g. D2,D3"),
    q: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    persona: str = Depends(rbac.require("docs.sop_dossier")),
):
    _check_well(well_id)
    types = _scoped_types(persona, _types_or_422(doc_types))
    store = get_store()
    if store is None:
        return _envelope("UNAVAILABLE", [], BUILD_HINT, missing=["document_index"])
    if q:
        hits = store.search(q, well_id=well_id, doc_types=types, top_k=min(limit, 50))
        return _envelope("OK" if hits else "LOW_CONFIDENCE", hits, f"{len(hits)} document(s) matched",
                         provenance=store.provenance() | {"query": q})
    docs = store.list_for_well(well_id, types, limit)
    return _envelope("OK" if docs else "UNAVAILABLE", docs,
                     f"{len(docs)} document(s) for {well_id}" if docs else f"no documents indexed for {well_id}",
                     provenance=store.provenance())
