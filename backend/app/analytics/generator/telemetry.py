"""Append-only gap columns for the frozen Geleki v0.3.0 core (SDD §5.4, D-19, V-N7).

``wht_degc`` on producing days; ``gl_inj_rate_mscfd`` / ``gl_inj_pressure_kgcm2`` on producing days of
GAS_LIFT wells only; NULL otherwise. Drawn from a dedicated stream (``[42, 78]``) in core row order,
so no v0.3.0 draw is touched. Per-well bases come from ``gap_column_bases`` (shared with the prepend,
so the series join at 2023-10-01).

Physics tie-in: a wax build-up in v0.3.0 raises THP by up to +42 %; WHT falls with it
(−14 °C per +100 % THP above the well's median), matching the native WAX signature (−6 °C at full).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .fields.geleki import GELEKI
from .simulate import gap_column_bases


def core_gap_columns(daily: pd.DataFrame, wells: pd.DataFrame) -> pd.DataFrame:
    bases = gap_column_bases(GELEKI, wells, GELEKI.seed)
    lift = dict(zip(wells.well_id, wells.lift_type))
    rng = np.random.default_rng([GELEKI.seed, 78])
    n = len(daily)
    noise_w = rng.normal(0.0, 0.6, n)
    noise_r = rng.normal(0.0, 0.02, n)
    noise_p = rng.normal(0.0, 0.4, n)
    prod = daily["is_producing"].to_numpy(dtype=bool)
    wid = daily["well_id"].to_numpy()
    thp = daily["thp_kgcm2"].to_numpy(dtype=float)
    thp_med = daily[prod].groupby("well_id")["thp_kgcm2"].median().to_dict()
    doy = pd.to_datetime(daily["production_date"]).dt.dayofyear.to_numpy(dtype=float)
    season = 4.0 * np.sin(2 * math.pi * (doy - 110.0) / 365.25)
    wht_b = np.array([bases[w][0] for w in wid])
    glr_b = np.array([bases[w][1] for w in wid])
    glp_b = np.array([bases[w][2] for w in wid])
    med = np.array([thp_med.get(w, np.nan) for w in wid])
    rel = np.where(np.isfinite(thp) & np.isfinite(med) & (med > 0), np.maximum(0.0, thp / med - 1.0), 0.0)
    wht = np.round(wht_b + season - 14.0 * rel + noise_w, 1)
    is_gl = np.array([lift[w] == "GAS_LIFT" for w in wid])
    glr = np.round(glr_b * (1.0 + noise_r), 1)
    glp = np.round(glp_b + noise_p, 1)
    out = pd.DataFrame(index=daily.index)
    out["wht_degc"] = np.where(prod, wht, np.nan)
    out["gl_inj_rate_mscfd"] = np.where(prod & is_gl, glr, np.nan)
    out["gl_inj_pressure_kgcm2"] = np.where(prod & is_gl, glp, np.nan)
    return out
