"""Field-engineer dossier routes (Stage S, TC-023, F-06; SDD §10.3 / §13.2 / §13.4).

- ``POST /api/wells/{well_id}/dossier``      build the dossier PDF → ``Dossier`` envelope (``{status, data, …}``)
- ``GET  /api/wells/{well_id}/export``       baseline JSON export (FEAT-15, unchanged keys) **plus** ``pdf_url`` /
  ``doc_id`` / ``dossier_url``; ``?format=pdf`` returns the dossier PDF body (``application/pdf``)
- ``GET  /api/files/dossiers/{name}``        a generated ``<well>_<as_of>_<persona>.pdf`` or ``.facts.json``

The export route is registered here and this router is included **before** the wells router in ``main.py`` so it
takes precedence over ``wells.export_well_dossier`` (whose JSON body it reuses verbatim — wells.py is not edited).
``?format=pdf`` returns the PDF directly instead of the SDD's 302 so ``curl -sf -o x.pdf`` (Gate S) and BDD-F06-S01
("a PDF … is returned") both hold.

RBAC: ``docs.sop_dossier`` (every persona, SDD §16.2); the persona (``X-Persona``) shapes the content (FE: no cost
band; ED: construction summary) and is part of the file name. ``as_of`` is honoured only when
``settings.ALLOW_AS_OF_OVERRIDE`` is truthy (same rule as ``/nba``; else 422).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.agent import rbac
from app.analytics.tools.common import ToolStatus
from app.analytics.tools.dossier import build_well_dossier, dossier_path

router = APIRouter()


def _as_of(as_of: str | None):
    from app.api.analytics_wells import _as_of_or_422

    return _as_of_or_422(as_of)


def _known(well_id: str) -> str:
    from app.api.analytics_wells import _known_well_or_404

    return _known_well_or_404(well_id)


def _build(well_id: str, persona: str, as_of: str | None, refresh: bool):
    wid = _known(well_id)
    r = build_well_dossier(wid, persona=persona, as_of=_as_of(as_of), refresh=refresh)
    if r.value is None:
        raise HTTPException(status_code=404 if "not found" in r.message else 503, detail=r.message)
    return r


@router.post("/wells/{well_id}/dossier")
def create_dossier(well_id: str, as_of: str | None = None, refresh: bool = Query(True),
                   persona: str = Depends(rbac.require("docs.sop_dossier"))):
    """TC-023: build the field dossier (generates if absent; ``refresh=false`` reuses a validated file)."""
    return _build(well_id, persona, as_of, refresh).envelope()


@router.get("/wells/{well_id}/export")
def export_well(well_id: str, format: str = Query("json", pattern="^(json|pdf)$"), as_of: str | None = None,
                persona: str = Depends(rbac.require("docs.sop_dossier"))):
    """FEAT-15 JSON export (kept) + ``pdf_url``; ``?format=pdf`` → the F-06 dossier PDF."""
    if format == "pdf":
        r = _build(well_id, persona, as_of, refresh=False)
        path = dossier_path(r.value.file_name)
        if path is None:
            raise HTTPException(status_code=503, detail="dossier PDF missing after build")
        return FileResponse(str(path), media_type="application/pdf",
                            headers={"Content-Disposition": f'inline; filename="{r.value.file_name}"',
                                     "X-Dossier-Status": r.status.value if r.status != ToolStatus.OK else "OK",
                                     "X-Dossier-Data-Sha256": r.value.data_sha256})
    from app.api.wells import export_well_dossier

    body = export_well_dossier(well_id)
    wid = body["well_id"]
    q = f"&as_of={as_of}" if as_of else ""
    body["pdf_url"] = f"/api/wells/{wid}/export?format=pdf{q}"
    body["dossier_url"] = f"/api/wells/{wid}/dossier"
    from datetime import date

    from app import settings
    from app.analytics.tools.dossier import dossier_doc_id

    aso = _as_of(as_of) or settings.AS_OF
    body["doc_id"] = dossier_doc_id(wid, aso if isinstance(aso, date) else settings.AS_OF, rbac.resolve_persona(persona))
    return body


@router.get("/files/dossiers/{name}")
def get_dossier_file(name: str, persona: str = Depends(rbac.require("docs.sop_dossier"))):
    path = dossier_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Dossier file {name} not found")
    media = "application/pdf" if name.endswith(".pdf") else "application/json"
    return FileResponse(str(path), media_type=media, headers={"Content-Disposition": f'inline; filename="{name}"'})
