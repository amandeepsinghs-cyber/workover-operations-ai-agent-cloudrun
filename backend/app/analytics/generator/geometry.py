"""Synthetic field geometry helpers (D-3: synthetic coordinates near Sivasagar)."""

from __future__ import annotations

import math

import numpy as np

from .fields.base import FieldConfig

N_VERTICES = 24


def boundary_polygon(cfg: FieldConfig, wells_latlon: np.ndarray | None = None) -> list[tuple[float, float]]:
    """Closed boundary polygon [(lat, lon), ...].

    Native fields: a circle of ``boundary_radius_deg`` around the centroid (wells are rejection-sampled
    inside it). Geleki (frozen well positions): the smallest centroid-centred circle that contains every
    well, plus a 15 % margin — the polygon is derived from the data, not the other way round.
    """
    lat0, lon0 = cfg.centroid
    r = cfg.boundary_radius_deg
    if wells_latlon is not None and len(wells_latlon):
        d = np.sqrt((wells_latlon[:, 0] - lat0) ** 2 + (wells_latlon[:, 1] - lon0) ** 2)
        r = float(d.max()) * 1.15
    pts = []
    for k in range(N_VERTICES):
        a = 2 * math.pi * k / N_VERTICES
        pts.append((round(lat0 + r * math.sin(a), 6), round(lon0 + r * math.cos(a), 6)))
    pts.append(pts[0])
    return pts


def point_in_polygon(lat: float, lon: float, poly: list[tuple[float, float]]) -> bool:
    """Ray casting; poly is closed [(lat, lon), ...]."""
    inside = False
    for (y1, x1), (y2, x2) in zip(poly[:-1], poly[1:]):
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_cross:
                inside = not inside
    return inside


def polygon_geojson(poly: list[tuple[float, float]]) -> str:
    coords = ",".join(f"[{lon},{lat}]" for lat, lon in poly)
    return '{"type":"Polygon","coordinates":[[' + coords + "]]}"
