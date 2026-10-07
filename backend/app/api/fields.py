"""Field-level analytics routes (SDD §13.2): TC-020 health buckets and TC-019 attribution rollup.

* ``GET /api/fields/{field}/health?cluster_id=``                — ``HealthBuckets`` (any persona)
* ``GET /api/fields/{field}/attribution?cluster_id=&window_days=`` — ``DeclineAttribution`` rollup
  (ED / ASSET_MANAGER only; ``X-Persona`` header, default ``ASSET_MANAGER``)

Responses use the tool envelope ``{status, data, message, missing_fields, provenance}`` (SDD §13.1).
Unknown field → 404 ``{detail}``. No currency (D-1). ``GET /api/fields`` (TC-025) is Stage T's.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from app.analytics.tools.attribution import attribute_decline
from app.analytics.tools.health import classify_well_health
from app.analytics.tools.hierarchy import resolve_field
from app.api.analytics_wells import router as analytics_wells_router

router = APIRouter()
# Stage P's well-level route (/wells/{id}/attribution) rides on this router: one include line in main.py.
router.include_router(analytics_wells_router)

ATTRIBUTION_PERSONAS = frozenset({"ED", "ASSET_MANAGER"})
DEFAULT_PERSONA = "ASSET_MANAGER"


def _field_or_404(field: str) -> str:
    f = resolve_field(field or "")
    if f is None:
        raise HTTPException(status_code=404, detail=f"Field {field} not found")
    return f


@router.get("/fields/{field}/health")
def field_health(field: str, cluster_id: str | None = None):
    f = _field_or_404(field)
    r = classify_well_health(f, cluster_id=cluster_id or None)
    if r.value is None and "cluster_id" in r.missing_fields:
        raise HTTPException(status_code=404, detail=r.message)
    return r.envelope()


@router.get("/fields/{field}/attribution")
def field_attribution(
    field: str,
    cluster_id: str | None = None,
    window_days: int = Query(180, ge=7, le=730),
    x_persona: str | None = Header(None, alias="X-Persona"),
):
    persona = (x_persona or DEFAULT_PERSONA).strip().upper()
    f = _field_or_404(field)
    if persona not in ATTRIBUTION_PERSONAS:
        return JSONResponse(status_code=403, content={
            "status": "UNAVAILABLE", "data": None, "missing_fields": [], "provenance": {},
            "message": f"not permitted for persona {persona}: field attribution is for ED / ASSET_MANAGER"})
    r = attribute_decline(field=f, cluster_id=cluster_id or None, window_days=window_days)
    if r.value is None and "cluster_id" in r.missing_fields:
        raise HTTPException(status_code=404, detail=r.message)
    return r.envelope()
