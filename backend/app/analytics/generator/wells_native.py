"""Native well_master generator for Lakwa / Lakhmani (same 23 columns as v0.3.0 + cluster_id).

Wells are placed around their cluster centre (GGS) and rejection-sampled inside the field
boundary polygon (V-N1). Fixture wells get their scripted lift type / zone / cluster.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .fields.base import FieldConfig
from .geometry import boundary_polygon, point_in_polygon

ZONE_DEPTH = {  # same depth model as v0.3.0 well_master (frozen Geleki uses identical numbers)
    "Tipam": (2750.0, 180.0, 2400.0, 3100.0),
    "Barail": (3300.0, 250.0, 2900.0, 3700.0),
    "Lakadong": (3900.0, 280.0, 3500.0, 4377.0),
}


def generate_native_well_master(cfg: FieldConfig) -> pd.DataFrame:
    rng = np.random.default_rng([cfg.seed, 1])
    n = cfg.n_wells
    well_ids = [f"{cfg.prefix}{i + 1:03d}" for i in range(n)]
    poly = boundary_polygon(cfg)

    cl_ids = [c.cluster_id for c in cfg.clusters]
    cl_w = np.array([c.weight for c in cfg.clusters], dtype=float)
    cluster_of = list(rng.choice(cl_ids, size=n, p=cl_w / cl_w.sum()))
    for fx in cfg.fixtures.values():
        if fx.cluster_id:
            cluster_of[well_ids.index(fx.well_id)] = fx.cluster_id
    cl_by_id = {c.cluster_id: c for c in cfg.clusters}

    lats, lons = [], []
    for cid in cluster_of:
        c = cl_by_id[cid]
        for _ in range(200):
            lat = c.center[0] + rng.normal(0, c.spread_deg)
            lon = c.center[1] + rng.normal(0, c.spread_deg)
            if point_in_polygon(lat, lon, poly):
                break
        lats.append(round(float(lat), 6))
        lons.append(round(float(lon), 6))

    start_c, end_c = date(1966, 1, 1), date(2018, 12, 31)
    total = (end_c - start_c).days
    completion = [start_c + timedelta(days=int(b * total)) for b in rng.beta(2.2, 4.0, size=n)]
    spud = [c - timedelta(days=int(rng.integers(60, 180))) for c in completion]

    zones_k = list(cfg.zones)
    zones = list(rng.choice(zones_k, size=n, p=np.array([cfg.zones[z] for z in zones_k])))
    lifts_k = list(cfg.lift_mix)
    lifts = list(rng.choice(lifts_k, size=n, p=np.array([cfg.lift_mix[k] for k in lifts_k])))
    for fx in cfg.fixtures.values():
        i = well_ids.index(fx.well_id)
        lifts[i] = fx.lift_type
        if fx.zone:
            zones[i] = fx.zone

    perf_top, perf_bot, td_md, td_tvd = [], [], [], []
    for z in zones:
        mu, sd, lo, hi = ZONE_DEPTH[z]
        top = round(float(np.clip(rng.normal(mu, sd), lo, hi)), 1)
        bot = round(top + rng.uniform(12.0, 60.0), 1)
        md = round(bot + rng.uniform(15.0, 90.0), 1)
        perf_top.append(top)
        perf_bot.append(bot)
        td_md.append(md)
        td_tvd.append(round(md * (1.0 - rng.uniform(0.005, 0.030)), 1))

    psd, plunger, stroke, rod, ptype, vented = [], [], [], [], [], []
    fixture_ids = set(cfg.fixtures)
    for i, lt in enumerate(lifts):
        if lt == "SRP":
            d = round(perf_top[i] - rng.uniform(30.0, 150.0), 1)
            p = float(rng.choice([1.25, 1.50])) if d > 2000.0 else float(rng.choice([1.25, 1.50, 1.75, 2.00]))
            psd.append(d)
            plunger.append(p)
            stroke.append(float(rng.choice([54.0, 64.0, 74.0, 86.0, 100.0])))
            rod.append(str(rng.choice(["C", "D", "K"], p=[0.20, 0.50, 0.30])))
            ptype.append(str(rng.choice(["INSERT", "TUBING"], p=[0.75, 0.25])))
            v = bool(rng.choice([False, True], p=[0.88, 0.12]))
            vented.append(False if well_ids[i] in fixture_ids else v)
        else:
            psd.append(None)
            plunger.append(None)
            stroke.append(None)
            rod.append(None)
            ptype.append(None)
            vented.append(False)

    tubing = [2.875 if rng.random() > 0.3 else 3.5 for _ in range(n)]
    casing = [5.5 if rng.random() > 0.25 else 7.0 for _ in range(n)]
    n_idle = int(round(cfg.idle_fraction * n))
    candidates = [i for i, w in enumerate(well_ids) if w not in fixture_ids]
    idle = set(int(i) for i in rng.choice(candidates, size=n_idle, replace=False))

    return pd.DataFrame({
        "well_id": well_ids,
        "field": cfg.field,
        "asset": cfg.asset,
        "latitude": lats,
        "longitude": lons,
        "spud_date": spud,
        "completion_date": completion,
        "current_zone": zones,
        "perf_top_m": perf_top,
        "perf_bottom_m": perf_bot,
        "total_depth_md_m": td_md,
        "total_depth_tvd_m": td_tvd,
        "max_dls_deg_30m": [None] * n,
        "lift_type": lifts,
        "plunger_diameter_in": plunger,
        "stroke_length_in": stroke,
        "pump_setting_depth_m": psd,
        "rod_string_grade": rod,
        "pump_type": ptype,
        "casing_vented": vented,
        "tubing_size_in": tubing,
        "casing_size_in": casing,
        "status": ["IDLE" if i in idle else "ACTIVE" for i in range(n)],
        "cluster_id": cluster_of,
    })
