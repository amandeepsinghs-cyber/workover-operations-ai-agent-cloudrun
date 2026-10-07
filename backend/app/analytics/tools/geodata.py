"""Field + cluster (GGS / fault-block) boundary GeoJSON (SDD §5.1, TC-016 v2, decision D-3).

The geometry is **approximate and synthetic** (D-3: every feature carries ``is_synthetic_geometry: true``):

* the field boundary is ``field_master.boundary_geojson`` (Stage N);
* each cluster polygon is the convex hull of that cluster's ``well_master`` locations, pushed out from its
  centroid by a fixed margin so edge wells sit inside — derived from data, never hand-typed coordinates.

Build the files (deterministic; from ``backend/``)::

    uv run python -m app.analytics.tools.geodata

writes ``app/data/geodata/<field>_boundary.geojson`` (geleki, lakwa, lakhmani). ``load_field_geojson`` reads
them back and falls back to building in memory if a file is missing.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from app import settings

from .common import load_table, register_cache

GEODATA_DIR = settings.DATA_DIR / "geodata"
HULL_MARGIN = 0.12      # fractional outward push of hull vertices from the cluster centroid
HULL_MIN_PAD_DEG = 0.002  # minimum outward pad (≈ 200 m) so 1–2 well clusters still get an area


def _ring_close(pts: list[list[float]]) -> list[list[float]]:
    return pts + [pts[0]] if pts and pts[0] != pts[-1] else pts


def _hull(lons: np.ndarray, lats: np.ndarray) -> list[list[float]]:
    pts = np.column_stack([lons, lats])
    cx, cy = float(lons.mean()), float(lats.mean())
    if len(pts) >= 3:
        from scipy.spatial import ConvexHull

        try:
            ring = pts[ConvexHull(pts).vertices]
        except Exception:  # collinear wells
            ring = pts
    else:
        ring = pts
    out = []
    for x, y in ring:
        dx, dy = x - cx, y - cy
        n = float(np.hypot(dx, dy)) or 1.0
        pad = max(n * HULL_MARGIN, HULL_MIN_PAD_DEG)
        out.append([round(x + dx / n * pad, 6), round(y + dy / n * pad, 6)])
    if len(out) < 3:  # degenerate: square around the centroid
        p = HULL_MIN_PAD_DEG * 2
        out = [[round(cx - p, 6), round(cy - p, 6)], [round(cx + p, 6), round(cy - p, 6)],
               [round(cx + p, 6), round(cy + p, 6)], [round(cx - p, 6), round(cy + p, 6)]]
    return _ring_close(out)


def build_field_geojson(field: str) -> dict:
    """FeatureCollection: one FIELD_BOUNDARY + one CLUSTER_POLYGON per cluster of ``field``."""
    feats: list[dict] = []
    fm = load_table("field_master")
    row = fm[fm["field"] == field] if len(fm) else fm
    if len(row) and "boundary_geojson" in row.columns:
        g = row.iloc[0]["boundary_geojson"]
        g = json.loads(g) if isinstance(g, str) else g
        if g:
            feats.append({"type": "Feature",
                          "properties": {"kind": "FIELD_BOUNDARY", "field": field, "name": f"{field} field boundary",
                                         "is_synthetic_geometry": True, "source": "field_master.boundary_geojson"},
                          "geometry": g})
    wm = load_table("well_master")
    wm = wm[(wm["field"] == field) & wm["latitude"].notna() & wm["longitude"].notna()]
    cm = load_table("cluster_master")
    ctype = dict(zip(cm["cluster_id"], cm["cluster_type"])) if len(cm) else {}
    for cid, g in sorted(wm.groupby("cluster_id"), key=lambda kv: str(kv[0])):
        ring = _hull(g["longitude"].to_numpy(float), g["latitude"].to_numpy(float))
        feats.append({"type": "Feature",
                      "properties": {"kind": "CLUSTER_POLYGON", "field": field, "cluster_id": str(cid),
                                     "cluster_type": ctype.get(cid), "name": str(cid), "n_wells": int(len(g)),
                                     "is_synthetic_geometry": True,
                                     "source": "convex hull of well_master locations (+margin)"},
                      "geometry": {"type": "Polygon", "coordinates": [ring]}})
    return {"type": "FeatureCollection", "name": f"{field.lower()}_boundary", "is_synthetic_geometry": True,
            "features": feats}


def geojson_path(field: str) -> Path:
    return GEODATA_DIR / f"{field.lower()}_boundary.geojson"


@lru_cache(maxsize=8)
def load_field_geojson(field: str) -> dict:
    p = geojson_path(field)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return build_field_geojson(field)


def cluster_polygons(field: str) -> list[dict]:
    return [f for f in load_field_geojson(field).get("features", []) if f["properties"].get("kind") == "CLUSTER_POLYGON"]


register_cache(load_field_geojson.cache_clear)


def main() -> int:
    from .hierarchy import FIELDS

    GEODATA_DIR.mkdir(parents=True, exist_ok=True)
    for fld in FIELDS:
        gj = build_field_geojson(fld)
        with open(geojson_path(fld), "w", encoding="utf-8") as f:
            json.dump(gj, f, indent=1, sort_keys=True)
            f.write("\n")
        n = sum(1 for x in gj["features"] if x["properties"]["kind"] == "CLUSTER_POLYGON")
        print(f"{geojson_path(fld).name}: field boundary + {n} cluster polygons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
