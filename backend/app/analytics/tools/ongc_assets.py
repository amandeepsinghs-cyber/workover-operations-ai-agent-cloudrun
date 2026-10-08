"""ONGC India asset overview for the map (v0.6 Stage ED-6, F-32 / D-34).

Thirteen ONGC producing assets at **approximate public asset centres**. Only the Assam Asset
(Lakwa, Lakhmani, Geleki) carries live WellPulse data; every other asset gets a handful of
**position-only well name tags** — illustrative names and positions near the public asset centre,
no production numbers, not clickable (D-34). Deterministic (seeded) so the map is stable.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

SOURCE_NOTE = ("Asset centres are approximate, from public ONGC asset information. Well tags outside "
               "Assam are illustrative names and positions only — no data behind them.")

# (asset_id, name, basin, lat, lng, offshore, tag prefix, n_tags, spread_deg)
_ASSETS = [
    ("ASSAM", "Assam Asset", "Assam-Arakan", 26.92, 94.73, False, None, 0, 0.0),
    ("TRIPURA", "Tripura Asset", "Assam-Arakan", 23.83, 91.28, False, "TR", 16, 0.18),
    ("ANKLESHWAR", "Ankleshwar Asset", "Cambay", 21.63, 73.00, False, "ANK", 20, 0.10),
    ("AHMEDABAD", "Ahmedabad Asset", "Cambay", 23.03, 72.58, False, "AHM", 18, 0.10),
    ("MEHSANA", "Mehsana Asset", "Cambay", 23.60, 72.39, False, "MHS", 22, 0.12),
    ("CAMBAY", "Cambay Asset", "Cambay", 22.40, 72.70, False, "CB", 14, 0.08),
    ("RAJAHMUNDRY", "Rajahmundry Asset", "Krishna-Godavari", 17.00, 81.78, False, "RJY", 18, 0.15),
    ("CAUVERY", "Cauvery Asset", "Cauvery", 10.92, 79.84, False, "CV", 16, 0.15),
    ("JODHPUR", "Jodhpur (Rajasthan)", "Rajasthan", 27.95, 72.85, False, "RJ", 10, 0.15),
    ("MUMBAI_HIGH", "Mumbai High Asset", "Western Offshore", 19.40, 71.33, True, "MH", 24, 0.12),
    ("NEELAM_HEERA", "Neelam & Heera Asset", "Western Offshore", 18.60, 72.35, True, "NH", 16, 0.08),
    ("BASSEIN", "Bassein & Satellite Asset", "Western Offshore", 19.30, 72.10, True, "BS", 16, 0.10),
    ("KG_DWN", "Eastern Offshore (KG-DWN-98/2)", "Krishna-Godavari", 16.30, 82.60, True, "KG", 12, 0.10),
]


def _tags(asset_id: str, prefix: str, n: int, lat: float, lng: float, spread: float) -> list[dict]:
    rng = random.Random(f"ongc-{asset_id}")
    out = []
    for i in range(n):
        r = spread * math.sqrt(rng.random())
        a = rng.random() * 2 * math.pi
        out.append({"name": f"{prefix}-{rng.randint(1, 499):03d}" if i else f"{prefix}-001",
                    "lat": round(lat + r * math.sin(a), 5),
                    "lng": round(lng + r * math.cos(a) / max(math.cos(math.radians(lat)), 0.3), 5)})
    # unique names, stable order
    seen, uniq = set(), []
    for t in out:
        if t["name"] not in seen:
            seen.add(t["name"])
            uniq.append(t)
    return uniq


@lru_cache(maxsize=1)
def ongc_assets() -> dict:
    assets = []
    for aid, name, basin, lat, lng, offshore, prefix, n, spread in _ASSETS:
        live = aid == "ASSAM"
        assets.append({
            "asset_id": aid, "name": name, "basin": basin, "lat": lat, "lng": lng,
            "offshore": offshore, "live": live,
            "fields": ["Lakwa", "Lakhmani", "Geleki"] if live else [],
            "well_tags": [] if live else _tags(aid, prefix, n, lat, lng, spread),
        })
    return {"assets": assets, "n_assets": len(assets), "source_note": SOURCE_NOTE,
            "bbox": {"min_lat": 8.0, "max_lat": 29.5, "min_lng": 68.5, "max_lng": 97.5}}
