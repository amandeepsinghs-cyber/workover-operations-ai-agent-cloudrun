"""Geleki 24-month prepend 2021-10-01 → 2023-09-30 (seed 4242; V-N5 keeps the v0.3.0 core frozen).

Each Geleki well continues backwards from its frozen v0.3.0 parameters (``t_offset = −730`` on the
same Arps curve, so the curve joins the core at 2023-10-01). The prepend uses the v0.3.0 failure
mix and the K-1 failure→job map, carries precursor signatures, and keeps its last
``ANCHOR_END_DAYS`` clean so the join with the frozen core is continuous (V-N6).
Persistent post-job effects are off: the core starts from the frozen v0.3.0 state.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .fields.geleki import GELEKI, PREPEND_SEED
from .simulate import (
    DAILY_COLS,
    SimResult,
    WellParams,
    WellSim,
    draw_external_events,
    gap_column_bases,
)

PREPEND_START = date(2021, 10, 1)
PREPEND_END = date(2023, 9, 30)
ANCHOR_END_DAYS = 21
TAIL_WAIT_MAX_DAYS = 14
V030_START = date(2023, 10, 1)
GAP_COLS = ["wht_degc", "gl_inj_rate_mscfd", "gl_inj_pressure_kgcm2"]


def prepend_params(v030_params: dict, wells: pd.DataFrame) -> dict[str, WellParams]:
    bases = gap_column_bases(GELEKI, wells, GELEKI.seed)
    out = {}
    for wid in wells["well_id"]:
        v = v030_params[wid]
        lt = v["lift_type"]
        wht, glr, glp = bases[wid]
        out[wid] = WellParams(
            q_i=v["q_i"], b=v["b"], d_i_day=v["d_i_day"], wc_init=v["wc_init"], wc_slope_day=v["wc_slope_day"],
            thp_base=v["thp_base"], chp_base=v["chp_base"], spm_base=v["spm_base"], gor_base=v["gor_base"],
            hazard_mult=v["hazard_mult"], is_idle=v["is_idle"], lift_type=lt, wht_base=wht,
            glr_base=glr if lt == "GAS_LIFT" else None, glp_base=glp if lt == "GAS_LIFT" else None, choke=16)
    return out


def core_start_waits(status: pd.DataFrame) -> dict[str, tuple[str, str | None]]:
    """Wells whose frozen core is down on 2023-10-01 waiting for a rig job → (reason, workover_id)."""
    out = {}
    for wid, g in status.groupby("well_id", sort=False):
        g = g.reset_index(drop=True)
        valid = g[(g.start_date == V030_START) & (g.end_date.isna() | (g.end_date >= g.start_date))]
        if not len(valid):
            continue
        r = valid.iloc[0]
        rig_job = r.status == "UNDER_WORKOVER" and r.is_rigless is not None and not bool(r.is_rigless)
        if r.status == "WAITING_ON_RIG" or rig_job:
            wo = g[(g.status == "UNDER_WORKOVER") & g.workover_id.notna()]["workover_id"]
            out[wid] = (r.reason_code, wo.iloc[0] if len(wo) else None)
    return out


def run_prepend(wells: pd.DataFrame, v030_params: dict, core_waits: dict | None = None) -> SimResult:
    """``wells`` = frozen v0.3.0 well_master + ``cluster_id``."""
    n = (PREPEND_END - PREPEND_START).days + 1
    params = prepend_params(v030_params, wells)
    ext = draw_external_events(GELEKI, n, PREPEND_START, np.random.default_rng([PREPEND_SEED, 3]))
    core_waits = core_waits or {}
    res = SimResult()
    for i, row in enumerate(wells.itertuples(index=False)):
        sim = WellSim(GELEKI, row, params[row.well_id], PREPEND_START, n, -n,
                      np.random.default_rng([PREPEND_SEED, 10, i]), job_mode="v030_mix", ext_events=ext,
                      persistent_effects=False, anchor_end_days=ANCHOR_END_DAYS, is_prepend=True, id_prefix="P",
                      exempt_external_from=n - ANCHOR_END_DAYS, allow_terminal=False)
        sim.build()
        if row.well_id in core_waits:   # the wait the frozen core opens with began inside the prepend
            reason, wo = core_waits[row.well_id]
            k = int(sim.rng.integers(2, TAIL_WAIT_MAX_DAYS + 1))
            sim._mark_down(n - k, n, reason)
            sim._set_status(n - k, n, "WAITING_ON_RIG", reason, None, False)
            sim._event("WAIT_ON_RIG", n - k, n - 1, wo)
        sim.overlay_setpoints()
        sim.overlay_external()
        sim.render(res)
    return res


def prepend_frames(res: SimResult) -> dict[str, pd.DataFrame]:
    daily = pd.DataFrame(res.daily, columns=DAILY_COLS + GAP_COLS)
    return dict(daily_production=daily, well_tests=pd.DataFrame(res.tests),
                well_status_history=pd.DataFrame(res.status), workover_history=pd.DataFrame(res.workovers),
                events=pd.DataFrame(res.events), potential=res.potential)
