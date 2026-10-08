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
in ``wells.py``. RBAC (Stage Y, SDD §16): ``app.agent.rbac`` — persona from ``X-Persona`` (default
``ASSET_MANAGER``); ``field.aggregate`` routes 403 for FIELD_ENGINEER; priority queue is own-cluster for
FIELD_ENGINEER and drops ``cost_band``; the well profile is a construction summary (no tallies) for ED.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent import rbac
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

RETIRED_DETAIL = "GLK- IDs retired in v0.4; use GK-"


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
def list_fields(persona: str = Depends(rbac.require("asset.overview"))):
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
    return rbac.redact(persona, "asset.overview", r.envelope())


@router.get("/fields/history")
def fields_history(
    fields: str | None = Query(None, description="Comma list, e.g. Geleki,Lakwa,Lakhmani (default all)"),
    start: str | None = None,
    end: str | None = None,
    freq: str = Query("M", pattern="^[MQYmqy]$"),
    persona: str = Depends(rbac.require("field.aggregate")),
):
    if fields:
        for f in fields.split(","):
            if f.strip() and f.strip().upper() != "ALL":
                _field_or_404(f.strip())
    return field_production_history(fields=fields, start=_date(start, "start"), end=_date(end, "end"),
                                    freq=freq.upper()).envelope()


@router.get("/fields/compare")
def fields_compare(
    period: str = Query("QTD", description="QTD | MTD | YTD | L12M"),
    persona: str = Depends(rbac.require("field.aggregate")),
):
    if period.upper() not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period must be one of {list(PERIODS)}")
    return rbac.redact(persona, "field.aggregate", compare_fields(period=period.upper()).envelope())


@router.get("/fields/map")
def fields_map(field: str | None = None, cluster_id: str | None = None, color_by: str = "health",
               persona: str = Depends(rbac.require("asset.overview"))):
    if field and field.strip().upper() != "ALL":
        for f in field.split(","):
            _field_or_404(f.strip())
    r = render_well_map(field=field or None, cluster_id=cluster_id or None, color_by=color_by)
    if r.value is None:
        raise HTTPException(status_code=422, detail=r.message)
    return rbac.redact(persona, "asset.overview", r.envelope())


# Stage ED-6 (v0.6): F-32 India view — 13 ONGC assets; non-Assam = position-only well name tags (D-34)
@router.get("/geo/ongc-assets")
def geo_ongc_assets(persona: str = Depends(rbac.require("asset.overview"))):
    from app.analytics.tools.ongc_assets import ongc_assets

    return ongc_assets()


@router.get("/fields/{field}/history")
def field_history(
    field: str,
    start: str | None = None,
    end: str | None = None,
    freq: str = Query("M", pattern="^[MQYmqy]$"),
    persona: str = Depends(rbac.require("field.aggregate")),
):
    f = _field_or_404(field)
    return field_production_history(fields=[f], start=_date(start, "start"), end=_date(end, "end"),
                                    freq=freq.upper()).envelope()


def _in_cluster(rows: list, cluster_id: str | None) -> list:
    if not cluster_id:
        return list(rows)
    c = cluster_id.upper()
    return [x for x in rows if str(getattr(x, "cluster_id", None) or (x.get("cluster_id") if isinstance(x, dict) else "")
                                   or "").upper() == c]


@router.get("/fields/{field}/priority")
def field_priority(
    field: str,
    queue: str = Query("all", pattern="^(rig|rigless|all)$"),
    limit: int = Query(20, ge=1, le=200),
    cluster_id: str | None = Query(None, description="restrict to one GGS cluster (FIELD_ENGINEER: own cluster)"),
    well_id: str | None = Query(None, description="FIELD_ENGINEER: selected well → own cluster"),
    persona: str = Depends(rbac.require("queue.read")),
):
    f = _field_or_404(field)
    cluster_id = rbac.scope_cluster(persona, "queue.read", cluster_id or None, well_id)
    r = rank_candidates(f)
    if r.value is None:
        return r.envelope()
    q = r.value
    rig_all, rigless_all = _in_cluster(q.rig_queue, cluster_id), _in_cluster(q.rigless_queue, cluster_id)
    rig = rig_all[:limit] if queue in ("rig", "all") else []
    rigless = rigless_all[:limit] if queue in ("rigless", "all") else []
    trimmed = replace(q, rig_queue=rig, rigless_queue=rigless)
    if cluster_id:
        trimmed = replace(trimmed, excluded_refusals=_in_cluster(q.excluded_refusals, cluster_id),
                          excluded_unrouted=_in_cluster(q.excluded_unrouted, cluster_id))
    prov = dict(r.provenance or {})
    if cluster_id:
        prov["cluster_id"] = cluster_id
    env = ToolResult(r.status, trimmed, r.missing_fields, r.message, prov).envelope()
    return rbac.redact(persona, "queue.read", env)


@router.get("/wells/{well_id}/profile")
def well_profile_route(well_id: str, k_neighbours: int = Query(4, ge=1, le=12),
                       persona: str = Depends(rbac.require("well.construction"))):
    wid = _well_or_404(well_id)
    return rbac.redact(persona, "well.construction", well_profile(wid, k_neighbours=k_neighbours).envelope())


@router.get("/wells/{well_id}/production")
def well_production_route(
    well_id: str,
    months: int = Query(36, ge=1, le=60, description="24 / 36 / 60"),
    metrics: str | None = Query(None, description=f"comma list of {','.join(METRICS)}"),
    persona: str = Depends(rbac.require("asset.overview")),
):
    wid = _well_or_404(well_id)
    ms = [m.strip() for m in metrics.split(",") if m.strip()] if metrics else None
    if ms:
        bad = [m for m in ms if m not in METRICS]
        if bad:
            raise HTTPException(status_code=422, detail=f"unknown metrics {bad}; valid: {list(METRICS)}")
    return rbac.redact(persona, "asset.overview", well_production_series(wid, months=months, metrics=ms).envelope())
