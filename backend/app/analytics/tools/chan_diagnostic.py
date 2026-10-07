"""TC-002 ``chan_diagnostic`` — Chan (SPE-30775) log-log WOR / WOR' water-mechanism diagnostic.

Port of ADK ``tools/chan_diagnostic.py``. Changes in the port (SDD §3.2, rule 1 "never substitute"):

* The v0.3.0 per-well calibration overrides (GK-129 / GK-117 / GK-141 / GK-103 hard-coded slopes,
  r² and injector steps) are **removed**; every well goes through the same computation.
* ``r_squared`` is the real log-log fit quality (v0.3.0 clamped it to [0.45, 0.96], which made the
  ``INDETERMINATE`` branch unreachable).
* The dataset has no injector table, so the paired-injector discriminator (TC-002.5..7) cannot be
  evaluated: ``paired_injectors=[]`` and ``discriminating_evidence`` says so instead of naming
  synthetic injectors. ``INJECTOR_BREAKTHROUGH`` is therefore never asserted from this data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import numpy as np

from app import settings

from .common import (
    Confidence,
    ToolResult,
    ToolStatus,
    WaterMechanism,
    WellId,
    build_provenance,
    register_cache,
    well_master_row,
    well_rows,
)

NO_INJECTOR_NOTE = "no injector data in the dataset; injector breakthrough not testable"


@dataclass(frozen=True)
class ChanDiagnosis:
    well_id: WellId
    mechanism: WaterMechanism
    wor_slope: float
    wor_prime_slope: float
    r_squared: float
    confidence: Confidence
    water_cut_start_pct: float
    water_cut_end_pct: float
    series: list[tuple[date, float, float]]
    paired_injectors: list[WellId]
    injector_rate_step: float | None
    injector_lag_days: int | None
    discriminating_evidence: str | None


def chan_diagnostic(
    well_id: WellId,
    as_of: date | None = None,
    window_days: int = 90,
    min_water_cut_pct: float = 20.0,
) -> ToolResult:
    return _chan_cached(well_id, as_of or settings.AS_OF, int(window_days), float(min_water_cut_pct))


@lru_cache(maxsize=4096)
def _chan_cached(well_id: WellId, as_of: date, window_days: int, min_water_cut_pct: float) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "window_days": window_days,
              "min_water_cut_pct": min_water_cut_pct}

    if well_master_row(well_id) is None:
        return ToolResult(ToolStatus.UNAVAILABLE, None, ["well_id"], f"Well {well_id} not found.",
                          build_provenance("TC-002", params, t0))

    daily = well_rows("daily_production", well_id)
    start_cutoff = as_of - timedelta(days=window_days)
    df_w = daily[
        (daily["production_date"] >= start_cutoff)
        & (daily["production_date"] <= as_of)
        & (daily["is_producing"] == True)  # noqa: E712
    ].sort_values("production_date")

    if len(df_w) < 30:
        return ToolResult(ToolStatus.INSUFFICIENT_HISTORY, None, [],
                          f"Fewer than 30 producing days in {window_days}-day window for {well_id}.",
                          build_provenance("TC-002", params, t0))

    wc_start = float(df_w["water_cut_pct"].iloc[:5].mean())
    wc_end = float(df_w["water_cut_pct"].iloc[-5:].mean())
    if wc_end < min_water_cut_pct:
        return ToolResult(ToolStatus.INSUFFICIENT_HISTORY, None, [],
                          f"Water cut ({wc_end:.1f}%) below {min_water_cut_pct:.1f}% threshold.",
                          build_provenance("TC-002", params, t0))

    # WOR = water / oil, 5-day rolling mean (v0.3.0 numerics)
    wor_raw = (df_w["water_rate_bwpd"].astype(float) / np.maximum(df_w["oil_rate_bopd"].astype(float), 0.5)).to_numpy()
    wor_smooth = np.convolve(wor_raw, np.ones(5) / 5.0, mode="same")
    wor_smooth[:2] = wor_raw[:2]
    wor_smooth[-2:] = wor_raw[-2:]

    t_idx = np.arange(1, len(df_w) + 1, dtype=float)
    log_t = np.log(t_idx)
    log_wor = np.log(np.maximum(wor_smooth, 1e-3))
    wor_slope_fit, wor_intercept = np.polyfit(log_t, log_wor, 1)
    log_wor_pred = wor_slope_fit * log_t + wor_intercept

    dwor_dt = np.gradient(wor_smooth, t_idx)
    wor_prime = np.abs(dwor_dt) + 1e-4
    log_wor_prime = np.log(wor_prime)
    wor_prime_slope_fit, _ = np.polyfit(log_t[4:-2], log_wor_prime[4:-2], 1)

    ss_res = float(np.sum((log_wor - log_wor_pred) ** 2))
    ss_tot = float(np.sum((log_wor - np.mean(log_wor)) ** 2))
    r2 = max(0.0, min(1.0, 1.0 - (ss_res / max(ss_tot, 1e-4))))

    wor_slope = round(float(wor_slope_fit), 2)
    wor_prime_slope = round(float(wor_prime_slope_fit), 2)
    if r2 < 0.40:
        mech, conf = WaterMechanism.INDETERMINATE, Confidence.LOW
        evidence = f"low log-log WOR fit (r²={r2:.2f})"
    elif wor_prime_slope < -0.10:
        mech, conf = WaterMechanism.CONING, Confidence.HIGH
        evidence = f"WOR' slope {wor_prime_slope:+.2f} < -0.10 (self-limiting coning)"
    elif wor_prime_slope > 0.30:
        mech, conf = WaterMechanism.CHANNELLING, Confidence.HIGH
        evidence = f"WOR' slope {wor_prime_slope:+.2f} > +0.30 (accelerating water); {NO_INJECTOR_NOTE}"
    else:
        mech, conf = WaterMechanism.MULTILAYER, Confidence.MEDIUM
        evidence = f"WOR' plateau ({wor_prime_slope:+.2f}) inside [-0.10, +0.30]"

    series_pts = [
        (d, round(float(w), 3), round(float(wp), 4))
        for d, w, wp in zip(df_w["production_date"].iloc[-30:], wor_smooth[-30:], wor_prime[-30:])
    ]
    diag = ChanDiagnosis(
        well_id=well_id,
        mechanism=mech,
        wor_slope=wor_slope,
        wor_prime_slope=wor_prime_slope,
        r_squared=round(r2, 2),
        confidence=conf,
        water_cut_start_pct=round(wc_start, 1),
        water_cut_end_pct=round(wc_end, 1),
        series=series_pts,
        paired_injectors=[],
        injector_rate_step=None,
        injector_lag_days=None,
        discriminating_evidence=evidence,
    )
    status = ToolStatus.LOW_CONFIDENCE if mech == WaterMechanism.INDETERMINATE else ToolStatus.OK
    return ToolResult(status, diag, [],
                      f"Chan diagnostic for {well_id}: {mech.value} (WOR' slope={wor_prime_slope:+.2f}, r²={r2:.2f}).",
                      build_provenance("TC-002", params, t0))


register_cache(_chan_cached.cache_clear)
