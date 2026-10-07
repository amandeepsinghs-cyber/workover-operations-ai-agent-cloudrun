"""TC-016 render_well_map — data-driven well map renderer (SDD §6.1).

Port of ADK v0.3.0 render_well_map with key architectural changes:
- No hard-coded well sets (urgent_set, flag_set, no_job_set) or default fields/wells ('Geleki', 'GK-129').
- Health classifications are data-driven via TC-020 (classify_well_health).
- No Vega-Lite specs generated on the backend; frontend renders from points, boundaries, facilities.
- Multi-field and cluster filtering support (field=None renders all fields).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import date
from functools import lru_cache
import json
import time
from typing import Any

import pandas as pd

from app import settings
from app.analytics.generator.fields import FIELD_CONFIGS
from app.analytics.tools.common import (
    ToolResult, ToolStatus, build_provenance, load_table, register_cache, unavailable,
)
from app.analytics.tools.health import classify_well_health
from app.analytics.tools.hierarchy import resolve_field
from app.analytics.tools.well_profile import _current_rates  # Stage T: same "current rate" basis as TC-029


@dataclass(frozen=True)
class WellMap:
    fields: list[str]
    points: list[dict]
    boundaries: list[dict]
    facilities: list[dict]
    bbox: dict
    counts_by_color: dict
    # Stage T (TC-016 v2): cluster / GGS polygons (synthetic, D-3) from app/data/geodata/<field>_boundary.geojson
    cluster_polygons: list[dict] = dc_field(default_factory=list)


@lru_cache(maxsize=16)
def _load_boundaries_cached() -> tuple[dict, ...]:
    fm = load_table("field_master")
    if fm.empty or "boundary_geojson" not in fm.columns:
        return ()
    has_syn = "is_synthetic_geometry" in fm.columns
    return tuple(
        {"field": str(r["field"]),
         "geojson": json.loads(r["boundary_geojson"]) if isinstance(r["boundary_geojson"], str) else r["boundary_geojson"],
         **({"is_synthetic_geometry": bool(r["is_synthetic_geometry"])} if has_syn else {})}
        for _, r in fm.iterrows()
    )


@lru_cache(maxsize=16)
def _load_facilities_cached() -> tuple[dict, ...]:
    fac = load_table("facility_master")
    if fac.empty:
        return ()
    cols = [c for c in fac.columns if not c.startswith("_")]
    out = []
    for _, r in fac.iterrows():
        d = {c: None if pd.isna(r[c]) else r[c] for c in cols}
        if d.get("lat") is not None: d["lat"] = float(d["lat"])
        if d.get("lon") is not None: d["lon"] = float(d["lon"])
        d["lng"] = float(d["lng"]) if d.get("lng") is not None else d.get("lon")
        out.append(d)
    return tuple(out)


register_cache(_load_boundaries_cached.cache_clear)
register_cache(_load_facilities_cached.cache_clear)


def render_well_map(
    field: str | None = None,
    highlight_well_ids: list[str] | None = None,
    color_by: str = "health",
    cluster_id: str | None = None,
    as_of: date | None = None,
) -> ToolResult:
    """Render well map points, boundaries, and facilities across fields or a single field/cluster."""
    t0 = time.perf_counter()
    as_of = as_of or settings.AS_OF
    params = {"field": field, "highlight_well_ids": highlight_well_ids, "color_by": color_by,
              "cluster_id": cluster_id, "as_of": str(as_of)}
    if color_by not in ("health", "lift_type"):
        return unavailable("TC-016", params, t0, ["color_by"], f"Unsupported color_by '{color_by}'.")

    if field is not None and str(field).strip().upper() in ("", "ALL"):
        field = None  # TC-016 v2: "ALL" = every field
    if field is not None:
        target_fields = []
        for part in str(field).split(","):  # TC-016 v2: comma list = multi-field map
            fld = resolve_field(part.strip())
            if fld is None:
                return unavailable("TC-016", params, t0, ["field"], f"Unknown field '{part.strip()}'.")
            if fld not in target_fields:
                target_fields.append(fld)
    else:
        target_fields = sorted(list(FIELD_CONFIGS))

    wm = load_table("well_master")
    if field is not None:
        wm = wm[wm["field"].isin(target_fields)]
    if cluster_id is not None:
        wm = wm[wm["cluster_id"] == cluster_id]

    buckets: dict[str, str] = {}
    for f in target_fields:
        h_res = classify_well_health(f, as_of=as_of)
        if h_res.value and hasattr(h_res.value, "wells"):
            buckets.update({w.well_id: w.bucket for w in h_res.value.wells})

    highlight_set = {str(w).strip().upper() for w in (highlight_well_ids or [])}
    points = [{
        "well_id": str(r["well_id"]),
        "field": str(r["field"]),
        "cluster_id": str(r["cluster_id"]) if pd.notna(r["cluster_id"]) else None,
        "lat": float(r["latitude"]) if pd.notna(r["latitude"]) else None,
        "lng": float(r["longitude"]) if pd.notna(r["longitude"]) else None,
        "lift_type": str(r["lift_type"]),
        "status": str(r["status"]),
        "bucket": buckets.get(str(r["well_id"])),
        "highlighted": str(r["well_id"]) in highlight_set,
        "color_key": buckets.get(str(r["well_id"])) if color_by == "health" else str(r["lift_type"]),
        "oil_bopd": _current_rates(str(r["well_id"]), as_of)["oil_bopd"],  # TC-016 v2 (size_by)
    } for _, r in wm.iterrows()]

    from app.analytics.tools.geodata import cluster_polygons as _cluster_polygons

    polys = [p for f in target_fields for p in _cluster_polygons(f)
             if cluster_id is None or p["properties"].get("cluster_id") == cluster_id]

    all_b, all_f = _load_boundaries_cached(), _load_facilities_cached()
    boundaries = [b for b in all_b if b["field"] in target_fields]
    facilities = [f for f in all_f if f.get("field") in target_fields]
    notes = [f"{n} unavailable" for n, has in (("field boundaries", all_b), ("facilities", all_f)) if not has]

    lats = [p["lat"] for p in points if p["lat"] is not None]
    lngs = [p["lng"] for p in points if p["lng"] is not None]
    bbox = {"min_lat": min(lats) if lats else None, "max_lat": max(lats) if lats else None,
            "min_lng": min(lngs) if lngs else None, "max_lng": max(lngs) if lngs else None}

    counts_by_color: dict[str, int] = {
        b: 0 for b in ("PRODUCING_OK", "AT_RISK", "UNDERPERFORMING", "NOT_PRODUCING")
    } if color_by == "health" else {}
    for p in points:
        key = p["color_key"] or "UNCLASSIFIED"  # never invent a bucket for a well TC-020 did not classify
        counts_by_color[key] = counts_by_color.get(key, 0) + 1

    scope = target_fields[0] if len(target_fields) == 1 else "all fields"
    if cluster_id:
        scope = f"{scope} ({cluster_id})"
    msg = f"Map of {len(points)} wells in {scope} coloured by {color_by}." + (f" ({'; '.join(notes)})." if notes else "")

    val = WellMap(fields=target_fields, points=points, boundaries=boundaries, facilities=facilities,
                  bbox=bbox, counts_by_color=counts_by_color, cluster_polygons=polys)
    return ToolResult(ToolStatus.OK, val, [], msg, build_provenance("TC-016", params, t0))
