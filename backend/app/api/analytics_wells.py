"""Well-level analytics routes (SDD §13.2): ``GET /api/wells/{id}/attribution`` (TC-019, any persona).

Kept out of ``wells.py`` (Stage N/X) so Stage P owns only its own route. ``GLK-`` IDs are retired
(404 with a pointer to ``GK-``); unknown wells 404. Envelope ``{status, data, message, missing_fields,
provenance}`` (SDD §13.1); an INSUFFICIENT_HISTORY result is a 200 with that status (not an error).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.analytics.tools.attribution import attribute_decline
from app.analytics.tools.common import well_master_row

router = APIRouter()

RETIRED_DETAIL = "GLK- IDs retired in v0.4; use GK-"


@router.get("/wells/{well_id}/attribution")
def well_attribution(well_id: str, window_days: int = Query(180, ge=7, le=730)):
    wid = well_id.strip().upper()
    if wid.startswith("GLK-"):
        raise HTTPException(status_code=404, detail=RETIRED_DETAIL)
    if well_master_row(wid) is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return attribute_decline(well_id=wid, window_days=window_days).envelope()
