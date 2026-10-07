"""Scripted demo stories (D-11, SDD §5.2) written into a ``WellSim`` inside its fixture window.

The renewal process for a fixture well stops at ``fw0`` (AS_OF − 200 d); the script below then
writes the story into the same state arrays the renderer reads, so daily rows, status episodes,
workover rows and operations_events stay mutually consistent (V-N2, V-N4).

All story numbers come from ``FieldConfig.fixtures[...].params`` (orchestrator-owned).
"""

from __future__ import annotations

from datetime import date

import numpy as np

from .catalogue import JOB_SPECS
from .simulate import Cycle, WellSim, apply_signature

FIXTURE_WINDOW_DAYS = 200          # renewal cycles stop this many days before AS_OF for fixture wells

# Fixture histories: the first renewal cycles of a fixture well take these jobs (None = drawn).
FORCED_HISTORY = {
    "LKW-112": [None, "CEMENT_SQUEEZE"],              # a prior water shut-off with a scanned report (BDD §ask-docs)
    "LKM-023": ["SAND_CLEANOUT", None, "SAND_CLEANOUT"],  # prior_sand_cleanouts = 2
    "LKM-061": [None, "GLV_REPLACE"],
}

# LKW-088 / GGS-II scripted feeder outages inside the 180-day window: (date, days). Cluster-wide.
GGS_II_SCRIPTED_OUTAGES = [
    ("2026-04-08", 2), ("2026-05-02", 1), ("2026-05-27", 3), ("2026-06-19", 1),
    ("2026-07-14", 2), ("2026-08-06", 2), ("2026-09-01", 1),
]


def _idx(sim: WellSim, iso: str) -> int:
    return (date.fromisoformat(iso) - sim.start).days


def expected_oil(sim: WellSim, d: int) -> float:
    """Noise-free oil the renderer would produce on day ``d`` (without the ``m_oil`` multiplier)."""
    a = sim.a
    qb = sim.q_base(d)
    wc0 = sim.wc_base(d)
    liq = qb / (1.0 - wc0 / 100.0) * sim.pm[d] * a["m_liq"][d] * a["m_ops"][d]
    wc = float(np.clip(wc0 + sim.wcp[d] + a["wc_add"][d], 1.0, 97.5))
    rt = float(np.clip(a["runtime"][d], 0.05, 1.0))
    return liq * (1 - wc / 100.0) * rt


def pin_oil_drop(sim: WellSim, a: int, b_incl: int, frac: float) -> None:
    """Make expected oil fall linearly by ``frac`` from the level on day a-1 to day b_incl; hold after."""
    ref = expected_oil(sim, a - 1)
    n = b_incl - a + 1
    for i, d in enumerate(range(a, sim.n)):
        k = min(1.0, (i + 1) / n)
        target = ref * (1.0 - frac * k)
        e = expected_oil(sim, d)
        sim.a["m_oil"][d] = float(np.clip(target / e, 0.0, 1.5)) if e > 0 else 1.0


def script_fixture(sim: WellSim, kind: str, params: dict, as_of_idx: int) -> None:
    n = sim.n
    if kind == "PUMP_CHANGE_AFTER_WAITS":           # LKW-047
        p0, f = _idx(sim, params["precursor_start"]), _idx(sim, params["failure_date"])
        job = params["job"]
        apply_signature(sim.a, JOB_SPECS[job]["signature"], p0, f, 1.0, sim.p)
        seq = len([c for c in sim.cycles if c.mode != "REVIEW"]) + 1
        wo_id = f"WO-{sim.row.well_id}-{seq:03d}"
        cyc = Cycle(job=job, failure_code=JOB_SPECS[job]["failure_code"], is_rigless=False, mode="FAILURE",
                    fail_day=f, sig_start=p0, wait_rig=int(params["wait_on_rig_days"]),
                    wait_mat=int(params["wait_on_material_days"]), repair=int(params["repair_days"]),
                    outcome=params["outcome"], run_life=f - (max([c.job_end for c in sim.cycles], default=-1) + 1),
                    rig_id=f"RIG-ASSAM-{int(sim.rng.integers(1, 16)):02d}")
        fc = cyc.failure_code
        d = f
        for st, etype, nd in (("WAITING_ON_RIG", "WAIT_ON_RIG", cyc.wait_rig),
                              ("WAITING_ON_MATERIAL", "WAIT_ON_MATERIAL", cyc.wait_mat)):
            sim._mark_down(d, d + nd, fc)
            sim._set_status(d, d + nd, st, fc, None, False)
            sim._event(etype, d, d + nd - 1, wo_id)
            d += nd
        cyc.job_start, cyc.job_end, cyc.wo_id = d, d + cyc.repair - 1, wo_id
        cyc.report_doc_id = f"DOC-SCAN-{sim.row.well_id}-{seq:03d}"
        sim._mark_down(cyc.job_start, cyc.job_end + 1, fc)
        sim._set_status(cyc.job_start, cyc.job_end + 1, "UNDER_WORKOVER", fc, wo_id, False)
        sim.cycles.append(cyc)
        sim._apply_effect(cyc, JOB_SPECS[job]["signature"], 1.0)
    elif kind == "CHANNELLING":                      # LKW-112: open (no job yet) at AS_OF
        a = as_of_idx - int(params["signature_days"]) + 1
        apply_signature(sim.a, "CHANNELLING", a, n, 0.8, sim.p)
        b = as_of_idx - int(params["oil_drop_last_days"]) + 1
        pin_oil_drop(sim, b, as_of_idx, float(params["oil_drop_frac"]))
    elif kind == "GGS_POWER_OUTAGES":                # LKW-088: outages come from the scripted cluster events
        pass
    elif kind == "SAND_INFLUX":                      # LKM-023: open sand signature at AS_OF
        a = as_of_idx - int(params["signature_days"]) + 1
        apply_signature(sim.a, "SAND", a, n, 1.0, sim.p)
        pin_oil_drop(sim, a, as_of_idx, float(params["oil_drop_frac"]))
    elif kind == "GLV_PLUS_WAX":                     # LKM-061: GLV failure signature + wax build-up
        apply_signature(sim.a, "GLV", as_of_idx - int(params["glv_signature_days"]) + 1, n, 1.0, sim.p)
        apply_signature(sim.a, "WAX", as_of_idx - int(params["wax_signature_days"]) + 1, n, 0.8, sim.p)
    elif kind == "RESERVOIR_DECLINE":                # LKM-090: shared reservoir decline, no job justified
        a = as_of_idx - int(params["signature_days"]) + 1
        apply_signature(sim.a, "RESERVOIR", a, n, 1.0, sim.p)
        pin_oil_drop(sim, a, as_of_idx, float(params["decline_frac"]))
    elif kind == "RESERVOIR_DECLINE_OFFSET":         # LKM-090 offsets (same zone, nearest)
        a = as_of_idx - int(params["signature_days"]) + 1
        apply_signature(sim.a, "RESERVOIR", a, n, 1.0, sim.p)
        pin_oil_drop(sim, a, as_of_idx, float(params["offset_decline_frac"]))
    else:
        raise ValueError(f"unknown fixture kind {kind}")


def scripted_cluster_events(field: str, start: date) -> list[dict]:
    if field != "Lakwa":
        return []
    out = []
    for iso, nd in GGS_II_SCRIPTED_OUTAGES:
        out.append(dict(event_type="GRID_POWER_OUTAGE", cluster_id="LKW-GGS-II",
                        d0=(date.fromisoformat(iso) - start).days, n=nd, partial=False, runtime=0.0,
                        scripted=True))
    return out
