"""Stage T asset / drill-down routes (SDD §13.4) — thin wrappers over TC-016 v2, TC-017 v2, TC-024, TC-025,
TC-028, TC-029 and TC-010. Every response is the tool envelope ``{status, data, message, missing_fields,
provenance}`` (SDD §13.1); unknown field / well → 404; no currency (D-1).

* ``GET /api/fields``                               — TC-025 hierarchy + per field health counts (TC-020),
                                                      centroid, boundary GeoJSON (field + cluster polygons)
* ``GET /api/fields/history?fields=&start=&end=&freq=`` — TC-028 ``FieldSeries`` (ED / ASSET_MANAGER)
* ``GET /api/fields/compare?period=``               — TC-024 ``FieldComparison`` (ED / ASSET_MANAGER)
* ``GET /api/fields/map?field=&cluster_id=``        — TC-016 v2 ``WellMap`` (multi-field: omit / ALL / comma list)
* ``GET /api/fields/{field}/history``               — TC-028 for one field (alias)
* ``GET /api/fields/{field}/priority?queue=&limit=`` — TC-010 ``CandidateQueues`` (FE read-only)
* ``GET /api/wells/{id}/profile?k_neighbours=``     — TC-029 ``WellProfile``
* ``GET /api/wells/{id}/production?months=&metrics=`` — TC-017 v2 ``ProductionSeries`` with intervention markers

``/api/fields/{field}/health|attribution`` stay in ``fields.py`` (Stage P); ``/api/field/infrastructure`` stays
in ``wells.py``. Persona comes from ``X-Persona`` (default ``ASSET_MANAGER``) until Stage Y's RBAC lands.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from app.analytics.tools.candidate_ranking import rank_candidates
from app.analytics.tools.common import ToolResult, well_master_row
from app.analytics.tools.field_history import field_production_history
from app.analytics.tools.field_performance import PERIODS, compare_fields
from app.analytics.tools.geodata import load_field_geojson
from app.analytics.tools.health import classify_well_health
from app.analytics.tools.hierarchy import FIELDS, query_hierarchy, resolve_field
from app.analytics.tools.render_well_map import render_well_map
from app.analytics.tools.well_profile import METRICS, well_production_series, well_profile

router = APIRouter()

DEFAULT_PERSONA = "ASSET_MANAGER"
AGGREGATE_PERSONAS = frozenset({"ED", "ASSET_MANAGER"})  # SDD §13.4 / §16 field.aggregate
RETIRED_DETAIL = "GLK- IDs retired in v0.4; use GK-"


def _persona(x_persona: str | None) -> str:
    return (x_persona or DEFAULT_PERSONA).strip().upper()


def _forbidden(persona: str, what: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={
        "status": "UNAVAILABLE", "data": None, "missing_fields": [], "provenance": {},
        "message": f"not permitted for persona {persona}: {what} is for ED / ASSET_MANAGER"})


def _field_or_404(field: str) -> str:
    f = resolve_field(field or "")
    if f is None:
        raise HTTPException(status_code=404, detail=f"Field {field} not found; fields: {', '.join(FIELDS)}")
    return f


def _well_or_404(well_id: str) -> str:
    wid = (well_id or "").strip().upper()
    if wid.startswith("GLK-"):
        raise HTTPException(status_code=404, detail=RETIRED_DETAIL)
    if well_master_row(wid) is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return wid


def _date(s: str | None, name: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{name} must be YYYY-MM-DD")


@router.get("/fields")
def list_fields():
    """TC-025 hierarchy enriched with TC-020 counts and the synthetic field / cluster geometry (D-3)."""
    r = query_hierarchy()
    data = r.value
    for f in data["fields"]:
        h = classify_well_health(f["field"])
        f["health_counts"] = dict(h.value.counts) if h.value is not None else None
        gj = load_field_geojson(f["field"])
        f["boundary_geojson"] = gj
        f["is_synthetic_geometry"] = bool(gj.get("is_synthetic_geometry", True))
        lats = [c["center_lat"] for c in f["clusters"] if c["center_lat"] is not None]
        lons = [c["center_lon"] for c in f["clusters"] if c["center_lon"] is not None]
        f["centroid"] = ({"lat": round(sum(lats) / len(lats), 6), "lon": round(sum(lons) / len(lons), 6)}
                         if lats and lons else None)
    return r.envelope()


@router.get("/fields/history")
def fields_history(
    fields: str | None = Query(None, description="Comma list, e.g. Geleki,Lakwa,Lakhmani (default all)"),
    start: str | None = None,
    end: str | None = None,
    freq: str = Query("M", pattern="^[MQYmqy]$"),
    x_persona: str | None = Header(None, alias="X-Persona"),
):
    persona = _persona(x_persona)
    if persona not in AGGREGATE_PERSONAS:
        return _forbidden(persona, "field production history")
    if fields:
        for f in fields.split(","):
            if f.strip() and f.strip().upper() != "ALL":
                _field_or_404(f.strip())
    return field_production_history(fields=fields, start=_date(start, "start"), end=_date(end, "end"),
                                    freq=freq.upper()).envelope()


@router.get("/fields/compare")
def fields_compare(
    period: str = Query("QTD", description="QTD | MTD | YTD | L12M"),
    x_persona: str | None = Header(None, alias="X-Persona"),
):
    persona = _persona(x_persona)
    if persona not in AGGREGATE_PERSONAS:
        return _forbidden(persona, "field comparison")
    if period.upper() not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period must be one of {list(PERIODS)}")
    return compare_fields(period=period.upper()).envelope()


@router.get("/fields/map")
def fields_map(field: str | None = None, cluster_id: str | None = None, color_by: str = "health"):
    if field and field.strip().upper() != "ALL":
        for f in field.split(","):
            _field_or_404(f.strip())
    r = render_well_map(field=field or None, cluster_id=cluster_id or None, color_by=color_by)
    if r.value is None:
        raise HTTPException(status_code=422, detail=r.message)
    return r.envelope()


@router.get("/fields/{field}/history")
def field_history(
    field: str,
    start: str | None = None,
    end: str | None = None,
    freq: str = Query("M", pattern="^[MQYmqy]$"),
    x_persona: str | None = Header(None, alias="X-Persona"),
):
    persona = _persona(x_persona)
    f = _field_or_404(field)
    if persona not in AGGREGATE_PERSONAS:
        return _forbidden(persona, "field production history")
    return field_production_history(fields=[f], start=_date(start, "start"), end=_date(end, "end"),
                                    freq=freq.upper()).envelope()


@router.get("/fields/{field}/priority")
def field_priority(
    field: str,
    queue: str = Query("all", pattern="^(rig|rigless|all)$"),
    limit: int = Query(20, ge=1, le=200),
):
    f = _field_or_404(field)
    r = rank_candidates(f)
    if r.value is None:
        return r.envelope()
    q = r.value
    rig = q.rig_queue[:limit] if queue in ("rig", "all") else []
    rigless = q.rigless_queue[:limit] if queue in ("rigless", "all") else []
    trimmed = replace(q, rig_queue=rig, rigless_queue=rigless)
    return ToolResult(r.status, trimmed, r.missing_fields, r.message, r.provenance).envelope()


@router.get("/wells/{well_id}/profile")
def well_profile_route(well_id: str, k_neighbours: int = Query(4, ge=1, le=12)):
    wid = _well_or_404(well_id)
    return well_profile(wid, k_neighbours=k_neighbours).envelope()


@router.get("/wells/{well_id}/production")
def well_production_route(
    well_id: str,
    months: int = Query(36, ge=1, le=60, description="24 / 36 / 60"),
    metrics: str | None = Query(None, description=f"comma list of {','.join(METRICS)}"),
):
    wid = _well_or_404(well_id)
    ms = [m.strip() for m in metrics.split(",") if m.strip()] if metrics else None
    if ms:
        bad = [m for m in ms if m not in METRICS]
        if bad:
            raise HTTPException(status_code=422, detail=f"unknown metrics {bad}; valid: {list(METRICS)}")
    return well_production_series(wid, months=months, metrics=ms).envelope()
