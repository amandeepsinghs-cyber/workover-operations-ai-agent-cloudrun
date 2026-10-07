"""Field-level analytics routes (SDD §13.2): TC-020 health buckets and TC-019 attribution rollup.

* ``GET /api/fields/{field}/health?cluster_id=``                — ``HealthBuckets``
  (``field.health``: ED / ASSET_MANAGER any scope; FIELD_ENGINEER own cluster only — SDD §16.2)
* ``GET /api/fields/{field}/attribution?cluster_id=&window_days=`` — ``DeclineAttribution`` rollup
  (``field.attribution``: ED / ASSET_MANAGER; ``X-Persona`` header, default ``ASSET_MANAGER``)

Responses use the tool envelope ``{status, data, message, missing_fields, provenance}`` (SDD §13.1).
Unknown field → 404 ``{detail}``. No currency (D-1). ``GET /api/fields`` (TC-025) is Stage T's.
RBAC (Stage Y): ``app.agent.rbac`` — denied → 403 UNAVAILABLE envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent import rbac
from app.analytics.tools.attribution import attribute_decline
from app.analytics.tools.health import classify_well_health
from app.analytics.tools.hierarchy import resolve_field
from app.api.analytics_wells import router as analytics_wells_router

router = APIRouter()
# Stage P's well-level route (/wells/{id}/attribution) rides on this router: one include line in main.py.
router.include_router(analytics_wells_router)


def _field_or_404(field: str) -> str:
    f = resolve_field(field or "")
    if f is None:
        raise HTTPException(status_code=404, detail=f"Field {field} not found")
    return f


@router.get("/fields/{field}/health")
def field_health(
    field: str,
    cluster_id: str | None = None,
    well_id: str | None = Query(None, description="FIELD_ENGINEER: selected well → own cluster"),
    persona: str = Depends(rbac.require("field.health")),
):
    f = _field_or_404(field)
    cluster_id = rbac.scope_cluster(persona, "field.health", cluster_id or None, well_id)
    r = classify_well_health(f, cluster_id=cluster_id or None)
    if r.value is None and "cluster_id" in r.missing_fields:
        raise HTTPException(status_code=404, detail=r.message)
    return rbac.redact(persona, "field.health", r.envelope())


@router.get("/fields/{field}/attribution")
def field_attribution(
    field: str,
    cluster_id: str | None = None,
    window_days: int = Query(180, ge=7, le=730),
    persona: str = Depends(rbac.require("field.attribution")),
):
    f = _field_or_404(field)
    r = attribute_decline(field=f, cluster_id=cluster_id or None, window_days=window_days)
    if r.value is None and "cluster_id" in r.missing_fields:
        raise HTTPException(status_code=404, detail=r.message)
    return rbac.redact(persona, "field.attribution", r.envelope())
