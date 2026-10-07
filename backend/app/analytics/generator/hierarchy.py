"""Asset hierarchy reference tables (SDD §5.3): field_master, cluster_master, facility_master."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .fields.base import FieldConfig
from .geometry import boundary_polygon, polygon_geojson


def field_boundary(cfg: FieldConfig, wells: pd.DataFrame):
    if cfg.native:
        return boundary_polygon(cfg)
    return boundary_polygon(cfg, wells[["latitude", "longitude"]].to_numpy(dtype=float))


def field_master(cfgs: list[FieldConfig], wells_by_field: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for c in cfgs:
        w = wells_by_field[c.field]
        rows.append(dict(field=c.field, asset=c.asset, prefix=c.prefix, centroid_lat=c.centroid[0],
                         centroid_lon=c.centroid[1], n_wells=len(w),
                         primary_reservoirs=",".join(c.primary_reservoirs),
                         boundary_geojson=polygon_geojson(field_boundary(c, w)), is_synthetic_geometry=True,
                         data_start=c.start, data_end=c.end))
    return pd.DataFrame(rows)


def cluster_master(cfgs: list[FieldConfig], wells_by_field: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for c in cfgs:
        w = wells_by_field[c.field]
        for cl in c.clusters:
            rows.append(dict(cluster_id=cl.cluster_id, field=c.field, cluster_type=cl.cluster_type,
                             polygon_ref=f"{cl.cluster_id}-POLY", center_lat=cl.center[0], center_lon=cl.center[1],
                             n_wells=int((w["cluster_id"] == cl.cluster_id).sum())))
    return pd.DataFrame(rows)


def facility_master(cfgs: list[FieldConfig]) -> pd.DataFrame:
    rows = []
    for c in cfgs:
        for f in c.facilities:
            rows.append(dict(facility_id=f.facility_id, field=c.field, type=f.facility_type, name=f.name, lat=f.lat,
                             lon=f.lon, capacity_bopd=f.capacity_bopd,
                             serviced_cluster_ids=",".join(f.serviced_cluster_ids),
                             compressor_capacity_mmscfd=f.compressor_capacity_mmscfd,
                             water_handling_bwpd=f.water_handling_bwpd))
    return pd.DataFrame(rows)


def nearest_cluster(cfg: FieldConfig, wells: pd.DataFrame) -> list[str]:
    """Geleki: cluster = nearest v0.3.0 fault-block centre."""
    cents = np.array([cl.center for cl in cfg.clusters])
    ids = [cl.cluster_id for cl in cfg.clusters]
    out = []
    for lat, lon in zip(wells["latitude"], wells["longitude"]):
        d = (cents[:, 0] - lat) ** 2 + (cents[:, 1] - lon) ** 2
        out.append(ids[int(np.argmin(d))])
    return out
