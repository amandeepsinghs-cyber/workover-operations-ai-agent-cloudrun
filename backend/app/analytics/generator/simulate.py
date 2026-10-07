"""Native production simulator (Lakwa, Lakhmani, Geleki prepend).

One renewal process per well over a daily calendar:

    PRODUCING (Arps decline × persistent productivity) ──precursor signature──▶ event
        FAILURE : down → [WAITING_ON_RIG] → [WAITING_ON_MATERIAL] → UNDER_WORKOVER → PRODUCING
        PLANNED : keeps producing (degraded) until the job, then UNDER_WORKOVER → PRODUCING
        REVIEW  : IC-15 "no job justified" row, no downtime, decline persists
        TERMINAL: plug & abandon → SHUT_IN to the end of the window

Overlays: cluster/field external outages (GRID_POWER_OUTAGE, BANDH_ACCESS_LOSS, FLOOD_ACCESS_LOSS),
operational set-point changes (CHOKE / SPM / GL_RATE), deferred maintenance before rigless jobs.
Every ``operations_events`` row is emitted from the same state arrays that produce the daily rows, so
each event window coincides with down or degraded production days (V-N2).

Honest labels (SDD §8.3): the precursor signature is drawn from the job's family but with a
strength draw, a 12 % chance of an overlapping (confusable) signature family and an 8 % chance of a
weak/absent signature, so a classifier cannot read the label straight off the data.

Determinism: all randomness flows from ``np.random.default_rng([seed, stream, well_index])``; no
wall-clock reads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .catalogue import JOB_SPECS, JOB_TO_IC, PREPEND_FAILURE_TO_JOB, build_job_catalogue
from .fields.base import FieldConfig

_CAT = build_job_catalogue().set_index("job_code")
REQUIRES_RIG = _CAT["requires_rig"].to_dict()
EST_DAYS = _CAT["est_days"].to_dict()

PRECURSOR_DAYS = {
    "PUMP_WEAR": (30, 60), "ROD_PART": (3, 7), "TUBING_LEAK": (5, 12), "WAX": (25, 50), "SCALE": (10, 20),
    "SAND": (30, 60), "GLV": (30, 60), "LIFT": (30, 60), "PI_DECLINE": (60, 120), "PERF": (60, 120),
    "CHANNELLING": (45, 90), "ZONAL": (45, 90), "CONING": (45, 90), "SURFACE": (7, 20), "CASING": (15, 30),
    "RESERVOIR": (60, 120),
}
CONFUSABLE = {
    "PUMP_WEAR": ["LIFT", "SAND"], "ROD_PART": ["TUBING_LEAK", "SURFACE"], "TUBING_LEAK": ["ROD_PART", "PUMP_WEAR"],
    "WAX": ["SCALE", "PI_DECLINE"], "SCALE": ["WAX", "PERF"], "SAND": ["PUMP_WEAR", "PI_DECLINE"],
    "GLV": ["LIFT", "TUBING_LEAK"], "LIFT": ["PUMP_WEAR", "GLV"], "PI_DECLINE": ["PERF", "RESERVOIR"],
    "PERF": ["PI_DECLINE", "SCALE"], "CHANNELLING": ["ZONAL", "CONING"], "ZONAL": ["CHANNELLING", "CASING"],
    "CONING": ["CHANNELLING", "ZONAL"], "SURFACE": ["ROD_PART", "LIFT"], "CASING": ["ZONAL", "TUBING_LEAK"],
    "RESERVOIR": ["PI_DECLINE", "PERF"],
}
P_CONFUSE = 0.12
P_WEAK = 0.08

EXTERNAL_REASON = {"GRID_POWER_OUTAGE": "POWER_OUTAGE", "BANDH_ACCESS_LOSS": "BANDH", "FLOOD_ACCESS_LOSS": "FLOOD"}

DAILY_COLS = [
    "well_id", "production_date", "oil_rate_bopd", "water_rate_bwpd", "gas_rate_mscfd", "liquid_rate_blpd",
    "water_cut_pct", "gor_scf_bbl", "thp_kgcm2", "chp_kgcm2", "choke_size_64th", "spm", "runtime_hours",
    "runtime_fraction", "is_producing", "downtime_reason", "data_source",
]


@dataclass
class WellParams:
    q_i: float
    b: float
    d_i_day: float
    wc_init: float
    wc_slope_day: float
    thp_base: float
    chp_base: float
    spm_base: float | None
    gor_base: float
    hazard_mult: float
    is_idle: bool
    lift_type: str
    wht_base: float = 45.0
    glr_base: float | None = None
    glp_base: float | None = None
    choke: int = 16


@dataclass
class Cycle:
    job: str
    failure_code: str
    is_rigless: bool
    mode: str
    fail_day: int
    sig_start: int
    wait_rig: int = 0
    wait_mat: int = 0
    wait_permit: int = 0
    wait_crew: int = 0
    deferred: int = 0
    repair: int = 0
    outcome: str = "SUCCESS"
    run_life: int = 0
    rig_id: str | None = None
    job_start: int = 0
    job_end: int = 0
    wo_id: str = ""
    report_doc_id: str | None = None


@dataclass
class SimResult:
    daily: list = dc_field(default_factory=list)
    tests: list = dc_field(default_factory=list)
    status: list = dc_field(default_factory=list)
    workovers: list = dc_field(default_factory=list)
    events: list = dc_field(default_factory=list)
    potential: dict = dc_field(default_factory=dict)   # well_id -> np.ndarray potential oil (bopd) per day


# ------------------------------------------------------------------------------------------------
# parameters
# ------------------------------------------------------------------------------------------------
def draw_native_params(cfg: FieldConfig, wells: pd.DataFrame, rng: np.random.Generator) -> dict[str, WellParams]:
    r = cfg.reservoir
    out: dict[str, WellParams] = {}
    raw_h = {}
    for row in wells.itertuples(index=False):
        u = rng.uniform
        lt = row.lift_type
        p = WellParams(
            q_i=float(u(*r.q_i_bopd)), b=float(u(*r.b)), d_i_day=float(u(*r.d_i_per_yr)) / 365.25,
            wc_init=float(u(*r.wc_init_pct)), wc_slope_day=float(u(*r.wc_slope_pp_per_yr)) / 365.25,
            thp_base=float(u(*r.thp_kgcm2)), chp_base=float(u(*r.chp_kgcm2)),
            spm_base=float(rng.choice([6.0, 8.0, 10.0, 12.0])) if lt == "SRP" else None,
            gor_base=float(u(*r.gor_scf_bbl)), hazard_mult=1.0, is_idle=(row.status == "IDLE"), lift_type=lt,
            wht_base=float(u(*r.wht_degc)),
            glr_base=float(u(*r.gl_inj_rate_mscfd)) if lt == "GAS_LIFT" else None,
            glp_base=float(u(*r.gl_inj_pressure_kgcm2)) if lt == "GAS_LIFT" else None,
            choke=int(rng.choice([12, 16, 20, 24])),
        )
        frailty = float(np.clip(rng.gamma(9.0, 1.0 / 9.0), 0.65, 1.55))
        liq = p.q_i / (1.0 - p.wc_init / 100.0)
        stress = 0.45 * (liq / 250.0) ** 1.2 + 0.35 * (p.wc_init / 70.0) ** 2.0 + 0.20
        raw_h[row.well_id] = 0.75 * stress + 0.25 * frailty
        out[row.well_id] = p
    mean_h = float(np.mean([raw_h[w] for w, p in out.items() if not p.is_idle]))
    for w, p in out.items():
        p.hazard_mult = raw_h[w] / mean_h
    return out


def params_from_v030(v030_params: dict, cfg: FieldConfig, wells: pd.DataFrame, rng: np.random.Generator) -> dict[str, WellParams]:
    """Geleki prepend: reuse the frozen v0.3.0 per-well parameters; draw only the gap-column bases."""
    r = cfg.reservoir
    out = {}
    for row in wells.itertuples(index=False):
        v = v030_params[row.well_id]
        lt = v["lift_type"]
        wht = float(rng.uniform(*r.wht_degc))
        glr = float(rng.uniform(*r.gl_inj_rate_mscfd))
        glp = float(rng.uniform(*r.gl_inj_pressure_kgcm2))
        out[row.well_id] = WellParams(
            q_i=v["q_i"], b=v["b"], d_i_day=v["d_i_day"], wc_init=v["wc_init"], wc_slope_day=v["wc_slope_day"],
            thp_base=v["thp_base"], chp_base=v["chp_base"], spm_base=v["spm_base"], gor_base=v["gor_base"],
            hazard_mult=v["hazard_mult"], is_idle=v["is_idle"], lift_type=lt, wht_base=wht,
            glr_base=glr if lt == "GAS_LIFT" else None, glp_base=glp if lt == "GAS_LIFT" else None, choke=16,
        )
    return out


def gap_column_bases(cfg: FieldConfig, wells: pd.DataFrame, seed: int) -> dict[str, tuple[float, float, float]]:
    """(wht_base, glr_base, glp_base) per well from a dedicated stream (shared by prepend and v0.3.0 core)."""
    rng = np.random.default_rng([seed, 77])
    r = cfg.reservoir
    out = {}
    for wid in wells["well_id"]:
        out[wid] = (float(rng.uniform(*r.wht_degc)), float(rng.uniform(*r.gl_inj_rate_mscfd)),
                    float(rng.uniform(*r.gl_inj_pressure_kgcm2)))
    return out


# ------------------------------------------------------------------------------------------------
# signatures
# ------------------------------------------------------------------------------------------------
def _ramp(n: int) -> np.ndarray:
    return np.linspace(1.0 / n, 1.0, n) if n > 0 else np.zeros(0)


def apply_signature(arr: dict, kind: str, a: int, b: int, s: float, p: WellParams) -> None:
    """Write a precursor signature of family ``kind`` with strength ``s`` into arrays over [a, b)."""
    n = b - a
    if n <= 0:
        return
    pr = _ramp(n)
    sl = slice(a, b)
    if kind == "PUMP_WEAR":
        arr["m_liq"][sl] *= 1 - 0.30 * s * pr
        arr["chp_add"][sl] += 4.0 * s * pr ** 1.5
        arr["runtime"][sl] *= 1 - 0.12 * s * pr
    elif kind == "ROD_PART":
        arr["m_liq"][sl] *= 1 - 0.06 * s * pr
        arr["noise"][sl] *= 1 + 1.0 * s
    elif kind == "TUBING_LEAK":
        late = np.clip((pr - 0.6) / 0.4, 0, 1)
        arr["m_liq"][sl] *= (1 - 0.05 * s * pr) * (1 - 0.45 * s * late)
        arr["thp_add"][sl] += -1.5 * s * pr
    elif kind == "WAX":
        arr["thp_add"][sl] += 0.40 * s * pr * p.thp_base
        arr["wht_add"][sl] += -6.0 * s * pr
        arr["m_liq"][sl] *= 1 - 0.25 * s * pr
    elif kind == "SCALE":
        step = (pr > 0.55).astype(float)
        arr["m_liq"][sl] *= 1 - 0.35 * s * step
        arr["thp_add"][sl] += 1.0 * s * step
    elif kind == "SAND":
        arr["m_liq"][sl] *= 1 - 0.22 * s * pr
        arr["noise"][sl] *= 1 + 2.5 * s * pr
        arr["chp_add"][sl] += 1.5 * s * pr
    elif kind == "GLV":
        if p.lift_type == "GAS_LIFT":
            arr["glr_mult"][sl] *= 1 + 0.35 * s * pr
            arr["glp_add"][sl] += -6.0 * s * pr
        arr["m_liq"][sl] *= 1 - 0.30 * s * pr
    elif kind == "LIFT":
        if p.lift_type == "GAS_LIFT":
            osc = np.sin(2 * math.pi * np.arange(n) / 5.0)
            arr["m_liq"][sl] *= 1 - 0.10 * s * pr + 0.12 * s * osc
            arr["glr_mult"][sl] *= 1 + 0.10 * s * osc
        elif p.lift_type == "SRP":
            arr["m_liq"][sl] *= 1 - 0.15 * s * pr
            arr["runtime"][sl] *= 1 - 0.15 * s * pr
            arr["gor_mult"][sl] *= 1 + 0.10 * s * pr
        else:
            arr["thp_add"][sl] += -2.0 * s * pr
            arr["m_liq"][sl] *= 1 - 0.18 * s * pr
    elif kind == "PI_DECLINE":
        arr["m_liq"][sl] *= 1 - 0.25 * s * pr
        arr["thp_add"][sl] += -1.2 * s * pr
        arr["chp_add"][sl] += -1.0 * s * pr
    elif kind == "PERF":
        arr["m_liq"][sl] *= 1 - 0.20 * s * pr
        arr["thp_add"][sl] += -0.8 * s * pr
        arr["chp_add"][sl] += -1.5 * s * pr
    elif kind == "CHANNELLING":
        arr["wc_add"][sl] += 10.0 * s * (((1 + 2.2 * pr) ** 1.12 - 1) / (3.2 ** 1.12 - 1))
        arr["m_liq"][sl] *= 1 + 0.05 * s * pr
    elif kind == "ZONAL":
        arr["wc_add"][sl] += 8.0 * s * np.clip((pr - 0.3) / 0.15, 0, 1)
        arr["m_liq"][sl] *= 1 + 0.04 * s * pr
    elif kind == "CONING":
        arr["wc_add"][sl] += 8.0 * s * (1 - (1 - pr) ** 2.5)
        arr["m_liq"][sl] *= 1 - 0.05 * s * pr
    elif kind == "SURFACE":
        arr["runtime"][sl] *= 1 - 0.40 * s * pr
    elif kind == "CASING":
        arr["chp_add"][sl] += 5.0 * s * pr
        arr["wc_add"][sl] += 6.0 * s * (pr > 0.5)
    elif kind == "RESERVOIR":
        arr["m_liq"][sl] *= 1 - 0.15 * s * pr
        arr["chp_add"][sl] += -0.8 * s * pr
        arr["thp_add"][sl] += -0.5 * s * pr


def _signature_kind(job: str, lift: str, rng: np.random.Generator) -> tuple[str, float]:
    kind = JOB_SPECS[job]["signature"]
    u = rng.random()
    s = float(rng.uniform(0.5, 1.25))
    alt = rng.integers(0, 2)
    if u < P_CONFUSE:
        cand = CONFUSABLE[kind][int(alt)]
        if not (cand == "GLV" and lift != "GAS_LIFT"):
            kind = cand
    if rng.random() < P_WEAK:
        s *= 0.3
    return kind, s


# ------------------------------------------------------------------------------------------------
# external events
# ------------------------------------------------------------------------------------------------
def draw_external_events(cfg: FieldConfig, n_days: int, start: date, rng: np.random.Generator) -> list[dict]:
    rates = cfg.ops_event_rates
    years = n_days / 365.25
    ev: list[dict] = []
    for c in cfg.clusters:
        rate = rates.get(f"GRID_POWER_OUTAGE:{c.cluster_id}", rates.get("GRID_POWER_OUTAGE", 0.0))
        for _ in range(int(rng.poisson(rate * years))):
            d0 = int(rng.integers(0, n_days))
            partial = rng.random() < 0.30
            ev.append(dict(event_type="GRID_POWER_OUTAGE", cluster_id=c.cluster_id, d0=d0,
                           n=1 if partial else int(rng.integers(1, 4)), partial=bool(partial),
                           runtime=float(rng.uniform(0.4, 0.8))))
        # monsoon floods (June-September)
        for yr in range(start.year, start.year + int(math.ceil(years)) + 1):
            if rng.random() < rates.get("FLOOD_ACCESS_LOSS", 0.0):
                d = (date(yr, 6, 1) - start).days + int(rng.integers(0, 120))
                if 0 <= d < n_days:
                    ev.append(dict(event_type="FLOOD_ACCESS_LOSS", cluster_id=c.cluster_id, d0=d,
                                   n=int(rng.integers(2, 6)), partial=False, runtime=0.0))
    for _ in range(int(rng.poisson(rates.get("BANDH_ACCESS_LOSS", 0.0) * years))):
        ev.append(dict(event_type="BANDH_ACCESS_LOSS", cluster_id=None, d0=int(rng.integers(0, n_days)),
                       n=int(rng.integers(1, 3)), partial=False, runtime=0.0))
    ev.sort(key=lambda e: (e["d0"], e["event_type"], e["cluster_id"] or ""))
    return ev


# ------------------------------------------------------------------------------------------------
# main simulation
# ------------------------------------------------------------------------------------------------
FACTOR = {
    "WAIT_ON_RIG": ("HUMAN_PROCESS", True, "Rig Planning"),
    "WAIT_ON_MATERIAL": ("HUMAN_PROCESS", True, "Materials Management (MRO)"),
    "DEFERRED_MAINTENANCE": ("HUMAN_PROCESS", True, "Production Engineering"),
    "PERMIT_DELAY": ("HUMAN_PROCESS", True, "HSE Permits"),
    "CREW_UNAVAILABLE": ("HUMAN_PROCESS", True, "Well Services"),
    "NO_TREATMENT_PROGRAMME": ("HUMAN_PROCESS", True, "Production Chemistry"),
    "CHOKE_CHANGE": ("OPERATIONAL", True, "Production Operations"),
    "SPM_CHANGE": ("OPERATIONAL", True, "Production Operations"),
    "GL_RATE_CHANGE": ("OPERATIONAL", True, "Production Operations"),
    "GRID_POWER_OUTAGE": ("EXTERNAL", False, "External grid supply"),
    "BANDH_ACCESS_LOSS": ("EXTERNAL", False, "External access (civil)"),
    "FLOOD_ACCESS_LOSS": ("EXTERNAL", False, "External access (weather)"),
}


def _lognormal_days(rng, median, sigma, lo, hi) -> int:
    return int(max(lo, min(hi, round(float(median * math.exp(rng.normal(0.0, sigma)))))))


class WellSim:
    """Simulates one well; produces row dicts into a SimResult."""

    def __init__(self, cfg, row, p: WellParams, start: date, n_days: int, t_offset: int, rng, *,
                 job_mode: str, ext_events: list[dict], fixture=None, fixture_window_start: int | None = None,
                 exempt_external_from: int | None = None, persistent_effects: bool = True,
                 anchor_end_days: int = 0, is_prepend: bool = False, id_prefix: str = "", job_override=None,
                 forced_jobs: list | None = None, allow_terminal: bool = True):
        self.cfg, self.row, self.p, self.start, self.n, self.t0, self.rng = cfg, row, p, start, n_days, t_offset, rng
        self.job_mode, self.ext, self.fixture, self.fw0 = job_mode, ext_events, fixture, fixture_window_start
        self.exempt_from = exempt_external_from
        self.persist, self.anchor_end, self.is_prepend, self.idp = persistent_effects, anchor_end_days, is_prepend, id_prefix
        self.job_override = job_override
        self.forced_jobs = list(forced_jobs or [])
        self.allow_terminal = allow_terminal
        self.n_drawn = 0
        n = n_days
        self.a = {k: np.ones(n) for k in ("m_liq", "m_oil", "runtime", "noise", "glr_mult", "gor_mult", "m_ops")}
        self.a.update({k: np.zeros(n) for k in ("wc_add", "thp_add", "chp_add", "wht_add", "glp_add")})
        self.pm = np.ones(n)       # persistent productivity (liquid) multiplier
        self.wcp = np.zeros(n)     # persistent water-cut offset (pp)
        self.down = np.zeros(n, dtype=bool)
        self.reason: list[str | None] = [None] * n
        self.status = ["PRODUCING"] * n
        self.status_reason: list[str | None] = [None] * n
        self.status_wo: list[str | None] = [None] * n
        self.status_rigless: list[bool | None] = [None] * n
        self.choke = np.full(n, p.choke, dtype=float)
        self.spm = np.full(n, p.spm_base if p.spm_base is not None else np.nan)
        self.cycles: list[Cycle] = []
        self.events: list[dict] = []
        self.ep_counter = 0

    # -- helpers ------------------------------------------------------------------------------
    def t(self, d):
        return d + self.t0

    def q_base(self, d):
        p = self.p
        t = self.t(d)
        return p.q_i / ((1.0 + p.b * p.d_i_day * t) ** (1.0 / p.b))

    def wc_base(self, d):
        return min(92.0, self.p.wc_init + self.p.wc_slope_day * self.t(d))

    def _event(self, etype, d0, d1, trigger_ref):
        if d0 >= self.n or d1 < d0:
            return
        d1 = min(d1, self.n - 1)
        fc, ctrl, fn = FACTOR[etype]
        self.events.append(dict(well_id=self.row.well_id, field=self.cfg.field, cluster_id=self.row.cluster_id,
                                start_date=self.start + timedelta(days=d0), end_date=self.start + timedelta(days=d1),
                                event_type=etype, factor_class=fc, controllable=ctrl, responsible_function=fn,
                                trigger_ref=trigger_ref, is_prepend=self.is_prepend))

    def _rig_wait_median(self, d):
        dm = self.cfg.downtime
        frac = d / max(1, self.n - 1)
        if self.is_prepend:
            frac = 0.0
        return dm.rig_wait_median_days_start + (dm.rig_wait_median_days_end - dm.rig_wait_median_days_start) * frac

    def _draw_uptime(self, hazard_boost: float, d: int = 0) -> int:
        dm = self.cfg.downtime
        scale = dm.uptime_scale_days
        if dm.uptime_scale_days_end is not None and not self.is_prepend:
            scale += (dm.uptime_scale_days_end - dm.uptime_scale_days) * d / max(1, self.n - 1)
        u = self.rng.weibull(dm.uptime_weibull_k) * scale / (self.p.hazard_mult * hazard_boost)
        return int(max(20, min(900, round(u))))

    def _draw_job(self, d) -> tuple[str, str, bool]:
        lift = self.p.lift_type
        idx = self.n_drawn
        self.n_drawn += 1
        if idx < len(self.forced_jobs) and self.forced_jobs[idx]:
            job = self.forced_jobs[idx]
            return job, JOB_SPECS[job]["failure_code"], not bool(REQUIRES_RIG[job])
        if self.job_override:
            jobs = self.job_override
            job = str(self.rng.choice(jobs))
            return job, JOB_SPECS[job]["failure_code"], not bool(REQUIRES_RIG[job])
        if self.job_mode == "v030_mix":
            from .fields.geleki import V030_FAILURE_MIX
            mix = V030_FAILURE_MIX[lift]
            codes = list(mix)
            fc = str(self.rng.choice(codes, p=np.array([mix[c] for c in codes])))
            if lift == "SRP":
                rl = fc in ("SURFACE", "SCALE") or (fc == "WAX" and self.rng.random() < 10.0 / 15.0)
            elif lift == "GAS_LIFT":
                rl = fc in ("GL_HEADING", "SURFACE", "SCALE") or (fc == "WAX" and self.rng.random() < 0.20)
            else:
                rl = fc in ("SURFACE", "SCALE")
            w = PREPEND_FAILURE_TO_JOB[(fc, bool(rl))]
            js = list(w)
            job = str(self.rng.choice(js, p=np.array([w[j] for j in js]) / sum(w.values())))
            return job, fc, bool(rl)
        w = self.cfg.mechanism_weights[lift]
        js = list(w)
        pr = np.array([w[j] for j in js], dtype=float)
        job = str(self.rng.choice(js, p=pr / pr.sum()))
        if job == "PLUG_ABANDON" and (d < self.n - 540 or not self.allow_terminal):   # P&A only late in a well's window
            job = "NO_JOB_JUSTIFIED"
        return job, JOB_SPECS[job]["failure_code"], not bool(REQUIRES_RIG[job])

    def _set_status(self, a, b, status, reason=None, wo=None, rigless=None):
        for d in range(max(0, a), min(self.n, b)):
            self.status[d] = status
            self.status_reason[d] = reason
            self.status_wo[d] = wo
            self.status_rigless[d] = rigless

    def _mark_down(self, a, b, reason):
        for d in range(max(0, a), min(self.n, b)):
            self.down[d] = True
            self.reason[d] = reason

    # -- cycle generation ----------------------------------------------------------------------
    def build(self):
        if self.p.is_idle:
            self._mark_down(0, self.n, "OTHER")
            self._set_status(0, self.n, "SHUT_IN", "OTHER")
            return
        limit = self.n if self.fw0 is None else self.fw0
        if self.anchor_end:
            limit = self.n - self.anchor_end
        d = 0
        hazard_boost = 1.0
        # random elapsed run at t=0 so wells are not synchronised
        first = True
        wo_seq = 0
        rv_seq = 0
        while d < limit:
            up = self._draw_uptime(hazard_boost, d)
            if first:
                up = int(self.rng.integers(5, max(6, up)))
                first = False
            fail = d + up
            if fail >= limit:
                break
            job, fc, rigless = self._draw_job(fail)
            spec = JOB_SPECS[job]
            mode = "FAILURE" if self.job_mode == "v030_mix" else spec["mode"]
            kind, s = _signature_kind(job, self.p.lift_type, self.rng)
            lo, hi = PRECURSOR_DAYS[kind]
            sig_len = int(self.rng.integers(lo, hi + 1))
            cyc = Cycle(job=job, failure_code=fc, is_rigless=rigless, mode=mode, fail_day=fail,
                        sig_start=max(d, fail - sig_len), run_life=up)
            dm = self.cfg.downtime
            if mode == "FAILURE" and not rigless:
                cyc.wait_rig = _lognormal_days(self.rng, self._rig_wait_median(fail), dm.rig_wait_sigma, 2, 200)
                if self.rng.random() < dm.p_wait_on_material:
                    cyc.wait_mat = _lognormal_days(self.rng, dm.material_wait_median_days, 0.5, 2, 60)
                if self.rng.random() < dm.p_permit_delay:
                    cyc.wait_permit = int(self.rng.integers(2, 8))
                if self.rng.random() < dm.p_crew_unavailable:
                    cyc.wait_crew = int(self.rng.integers(1, 6))
            if mode == "FAILURE" and rigless and self.rng.random() < dm.p_deferred_maintenance:
                cyc.deferred = int(self.rng.integers(5, 21))
            if mode in ("FAILURE", "PLANNED", "TERMINAL"):
                base = max(1.0, float(EST_DAYS.get(job, 1.0)))
                cyc.repair = int(max(1, math.ceil(base * self.rng.uniform(0.8, 1.6)))) if not rigless else int(self.rng.integers(1, 4))
            op = dm.outcome_p
            cyc.outcome = str(self.rng.choice(["SUCCESS", "PARTIAL", "FAILED"], p=list(op)))
            cyc.rig_id = f"RIG-ASSAM-{int(self.rng.integers(1, 16)):02d}" if not rigless and mode != "REVIEW" else None
            total = cyc.deferred + cyc.wait_rig + cyc.wait_mat + cyc.wait_permit + cyc.wait_crew + cyc.repair
            if fail + total + 3 >= limit and limit < self.n:
                break   # fixture / anchor windows: never start a cycle that cannot finish before them
            # signature (the deferred-maintenance days continue the degraded running)
            sig_end = fail + cyc.deferred
            apply_signature(self.a, kind, cyc.sig_start, min(self.n, sig_end), s, self.p)
            if cyc.deferred:
                self.a["runtime"][fail:min(self.n, sig_end)] *= self.rng.uniform(0.6, 0.85)
                self._event("DEFERRED_MAINTENANCE", fail, min(self.n, sig_end) - 1, None)
            d_cur = sig_end
            if mode == "REVIEW":
                rv_seq += 1
                cyc.wo_id = f"WO-{self.row.well_id}-{self.idp}R{rv_seq:02d}"
                cyc.job_start = cyc.job_end = min(self.n - 1, fail)
                cyc.outcome = "NO_ACTION"
                self.cycles.append(cyc)
                if self.persist:   # the reservoir decline is real and persists
                    end_lvl = self.a["m_liq"][min(self.n - 1, max(cyc.sig_start, fail - 1))]
                    self.pm[fail:] *= end_lvl
                d = fail + 1
                continue
            ep_reason = fc
            waits = [("WAITING_ON_RIG", "WAIT_ON_RIG", cyc.wait_rig), ("WAITING_ON_RIG", "PERMIT_DELAY", cyc.wait_permit),
                     ("WAITING_ON_RIG", "CREW_UNAVAILABLE", cyc.wait_crew),
                     ("WAITING_ON_MATERIAL", "WAIT_ON_MATERIAL", cyc.wait_mat)]
            wo_seq += 1
            for st, etype, nd in waits:
                if nd <= 0 or mode != "FAILURE":
                    continue
                self._mark_down(d_cur, d_cur + nd, fc)
                self._set_status(d_cur, d_cur + nd, st, ep_reason, None, False)
                self._event(etype, d_cur, min(self.n, d_cur + nd) - 1, None)
                d_cur += nd
            if mode == "FAILURE" and rigless:
                pass
            cyc.job_start = d_cur
            cyc.job_end = d_cur + cyc.repair - 1
            cyc.wo_id = f"WO-{self.row.well_id}-{self.idp}{wo_seq:03d}"
            cyc.report_doc_id = f"DOC-SCAN-{self.row.well_id}-{self.idp}{wo_seq:03d}"
            self._mark_down(cyc.job_start, cyc.job_end + 1, fc)
            self._set_status(cyc.job_start, cyc.job_end + 1, "UNDER_WORKOVER", ep_reason, cyc.wo_id, rigless)
            if mode == "FAILURE":   # pre-job days from failure until rig arrives are down too
                pass
            for ev in self.events:
                if ev["trigger_ref"] is None:
                    ev["trigger_ref"] = cyc.wo_id
            self.cycles.append(cyc)
            if mode == "TERMINAL":
                self._mark_down(cyc.job_end + 1, self.n, "PLUGGED_ABANDONED")
                self._set_status(cyc.job_end + 1, self.n, "SHUT_IN", "PLUGGED_ABANDONED")
                return
            self._apply_effect(cyc, kind, s)
            hazard_boost = 1.5 if (cyc.outcome == "FAILED" and spec["effect"] == "RESTORE") else 1.0
            d = cyc.job_end + 1

    def _apply_effect(self, cyc: Cycle, kind: str, s: float):
        if not self.persist:
            return
        a0 = cyc.job_end + 1
        if a0 >= self.n:
            return
        last = max(cyc.sig_start, cyc.fail_day - 1)
        m_end = float(self.a["m_liq"][min(self.n - 1, last)])
        wc_end = float(self.a["wc_add"][min(self.n - 1, last)])
        r = {"SUCCESS": 0.0, "PARTIAL": 0.4, "FAILED": 0.85}[cyc.outcome]
        eff = JOB_SPECS[cyc.job]["effect"]
        cur_pm = float(self.pm[a0])
        cur_wc = float(self.wcp[a0])
        new_pm = cur_pm * (1 - r * (1 - m_end))
        new_wc = cur_wc + r * wc_end
        if eff == "RESTORE" and cyc.outcome == "SUCCESS":
            new_pm = max(new_pm, 1.0) if cur_pm < 1.0 else new_pm
        elif eff in ("STIM", "WSO_STIM"):
            new_pm = min(1.45, new_pm * {"SUCCESS": 1.25, "PARTIAL": 1.08, "FAILED": 0.98}[cyc.outcome])
        elif eff == "STIM_SMALL":
            new_pm = min(1.45, new_pm * {"SUCCESS": 1.12, "PARTIAL": 1.04, "FAILED": 1.0}[cyc.outcome])
        if eff in ("WSO", "WSO_STIM"):
            new_wc = max(-15.0, new_wc - {"SUCCESS": 8.0, "PARTIAL": 3.0, "FAILED": 0.0}[cyc.outcome])
        elif eff == "CONING":
            new_wc = max(-15.0, new_wc - {"SUCCESS": 4.0, "PARTIAL": 1.5, "FAILED": 0.0}[cyc.outcome])
            new_pm *= 0.97
        self.pm[a0:] *= new_pm / cur_pm if cur_pm else 1.0
        self.wcp[a0:] += new_wc - cur_wc

    # -- overlays -----------------------------------------------------------------------------
    def overlay_external(self):
        for e in self.ext:
            if e["cluster_id"] is not None and e["cluster_id"] != self.row.cluster_id:
                continue
            d0, d1 = e["d0"], min(self.n, e["d0"] + e["n"])
            if self.exempt_from is not None and d1 > self.exempt_from and not e.get("scripted"):
                continue
            hit = False
            for d in range(d0, d1):
                if self.down[d]:
                    continue
                hit = True
                if e["partial"]:
                    self.a["runtime"][d] *= e["runtime"]
                else:
                    self.down[d] = True
                    self.reason[d] = EXTERNAL_REASON[e["event_type"]]
                    self.status[d] = "SHUT_IN"
                    self.status_reason[d] = EXTERNAL_REASON[e["event_type"]]
                    self.status_wo[d] = None
                    self.status_rigless[d] = None
            if hit:
                self._event(e["event_type"], d0, d1 - 1, e.get("ref"))

    def overlay_setpoints(self):
        rates = self.cfg.ops_event_rates
        years = self.n / 365.25
        kinds = [("CHOKE_CHANGE", rates.get("CHOKE_CHANGE", 0.0))]
        if self.p.lift_type == "SRP":
            kinds.append(("SPM_CHANGE", rates.get("SPM_CHANGE", 0.0)))
        if self.p.lift_type == "GAS_LIFT":
            kinds.append(("GL_RATE_CHANGE", rates.get("GL_RATE_CHANGE", 0.0)))
        if self.p.is_idle:
            return
        for etype, rate in kinds:
            k = int(self.rng.poisson(rate * years))
            days = sorted(int(x) for x in self.rng.integers(0, self.n, size=k))
            for d in days:
                if self.down[d] or (self.exempt_from is not None and d >= self.exempt_from):
                    continue
                if self.anchor_end and d >= self.n - self.anchor_end:
                    continue
                self.a["runtime"][d] *= 0.92
                if etype == "CHOKE_CHANGE":
                    old = self.choke[d]
                    new = float(np.clip(old + self.rng.choice([-4, 4]), 8, 32))
                    self.choke[d:] = new
                    self.a["m_ops"][d:] *= (new / old) ** 0.3
                elif etype == "SPM_CHANGE":
                    old = self.spm[d]
                    new = float(np.clip(old + self.rng.choice([-2.0, 2.0]), 4.0, 14.0))
                    self.spm[d:] = new
                    self.a["m_ops"][d:] *= (new / old) ** 0.25
                else:
                    f = float(self.rng.choice([0.85, 1.15]))
                    self.a["glr_mult"][d:] *= f
                    self.a["m_ops"][d:] *= 1.0 + (f - 1.0) * 0.2
                self._event(etype, d, d, None)

    # -- render ---------------------------------------------------------------------------------
    def render(self, res: SimResult):
        p, w, n, rng = self.p, self.row.well_id, self.n, self.rng
        a = self.a
        doy = np.array([(self.start + timedelta(days=d)).timetuple().tm_yday for d in range(n)], dtype=float)
        season = 4.0 * np.sin(2 * math.pi * (doy - 110.0) / 365.25)
        is_gl = p.lift_type == "GAS_LIFT"
        next_test = int(rng.integers(14, 24))
        counter = 0
        potential = np.zeros(n)
        oil_series = np.full(n, np.nan)
        prepend = self.is_prepend
        for d in range(n):
            dt = self.start + timedelta(days=d)
            counter += 1
            qb = self.q_base(d)
            if p.is_idle or self.reason[d] == "PLUGGED_ABANDONED":
                potential[d] = 0.0
            else:   # healthy-state oil: Arps × persistent productivity at the persistent water cut
                wc_h = float(np.clip(self.wc_base(d) + self.wcp[d], 1.0, 97.5))
                potential[d] = qb / (1.0 - self.wc_base(d) / 100.0) * self.pm[d] * (1.0 - wc_h / 100.0)
            if self.down[d]:
                res.daily.append(dict(well_id=w, production_date=dt, oil_rate_bopd=None, water_rate_bwpd=None,
                                      gas_rate_mscfd=None, liquid_rate_blpd=None, water_cut_pct=None, gor_scf_bbl=None,
                                      thp_kgcm2=None, chp_kgcm2=None, choke_size_64th=0, spm=None, runtime_hours=0.0,
                                      runtime_fraction=0.0, is_producing=False, downtime_reason=self.reason[d],
                                      data_source="ESTIMATED", wht_degc=None, gl_inj_rate_mscfd=None,
                                      gl_inj_pressure_kgcm2=None))
                continue
            wc0 = self.wc_base(d)
            liq0 = qb / (1.0 - wc0 / 100.0)
            liq = liq0 * self.pm[d] * a["m_liq"][d] * a["m_ops"][d]
            wc = float(np.clip(wc0 + self.wcp[d] + a["wc_add"][d], 1.0, 97.5))
            rt = float(np.clip(a["runtime"][d], 0.05, 1.0))
            oil_true = liq * (1 - wc / 100.0) * a["m_oil"][d] * rt
            is_tested = counter >= next_test
            thp_t = p.thp_base + a["thp_add"][d]
            chp_t = p.chp_base + a["chp_add"][d]
            if is_tested:
                counter = 0
                next_test = int(rng.integers(14, 24))
                src = "TESTED"
                q_oil = round(float(oil_true + rng.normal(0, 0.25) * a["noise"][d]), 1)
                q_water = round(float(q_oil * wc / (100.0 - wc)), 1)
                thp = round(float(thp_t + rng.normal(0, 0.15)), 1)
                chp = round(float(chp_t + rng.normal(0, 0.20)), 1)
            else:
                src = "ALLOCATED"
                nz = float(rng.normal(0, 0.018 * a["noise"][d]))
                q_oil = round(float(oil_true * (1.0 + nz)), 1)
                q_water = round(float(q_oil * wc / (100.0 - wc) * (1.0 + nz * 0.5)), 1)
                thp = round(float(thp_t + rng.normal(0, 0.25 * a["noise"][d])), 1)
                chp = round(float(chp_t + rng.normal(0, 0.30)), 1)
            q_oil = max(1.0, q_oil)
            q_water = max(0.5, q_water)
            q_liq = round(q_oil + q_water, 1)
            wc_calc = round(q_water / q_liq * 100.0, 1)
            years = max(0.0, self.t(d)) / 365.25
            gor = round(float(p.gor_base * (1.0 + 0.04 * years) * a["gor_mult"][d]), 1)
            gas = round(q_oil * gor / 1000.0, 1)
            wht = round(float(p.wht_base + season[d] + 0.01 * (q_liq - liq0) + a["wht_add"][d] + rng.normal(0, 0.6)), 1)
            if is_gl:
                glr = round(float(p.glr_base * a["glr_mult"][d] * (1.0 + rng.normal(0, 0.02))), 1)
                glp = round(float(p.glp_base + a["glp_add"][d] + rng.normal(0, 0.4)), 1)
            else:
                glr = glp = None
            oil_series[d] = q_oil
            res.daily.append(dict(well_id=w, production_date=dt, oil_rate_bopd=q_oil, water_rate_bwpd=q_water,
                                  gas_rate_mscfd=gas, liquid_rate_blpd=q_liq, water_cut_pct=wc_calc, gor_scf_bbl=gor,
                                  thp_kgcm2=thp, chp_kgcm2=chp, choke_size_64th=int(self.choke[d]),
                                  spm=None if p.spm_base is None else float(self.spm[d]),
                                  runtime_hours=round(24.0 * rt, 1), runtime_fraction=round(rt, 3), is_producing=True,
                                  downtime_reason=None, data_source=src, wht_degc=wht, gl_inj_rate_mscfd=glr,
                                  gl_inj_pressure_kgcm2=glp))
            if is_tested:
                res.tests.append(dict(test_id=f"TST-{w}-{dt:%Y%m%d}", well_id=w, test_date=dt, test_duration_hr=24.0,
                                      oil_rate_bopd=q_oil, water_rate_bwpd=q_water,
                                      gas_rate_mscfd=round(float(q_oil * p.gor_base / 1000.0), 1),
                                      thp_kgcm2=thp, chp_kgcm2=chp,
                                      fluid_level_m=round(float(rng.uniform(700, 1600)), 1),
                                      pump_intake_p_kgcm2=round(float(rng.uniform(20, 55)), 1),
                                      test_quality=str(rng.choice(["GOOD", "SUSPECT", "REJECTED"], p=[0.93, 0.05, 0.02])),
                                      is_prepend=prepend))
        res.potential[w] = potential
        self._emit_status(res)
        self.dropped_wo: set[str] = set()
        self._emit_workovers(res, oil_series)
        for e in self.events:
            if e["trigger_ref"] in self.dropped_wo:
                e["trigger_ref"] = None
            res.events.append(e)

    def _emit_status(self, res: SimResult):
        w, n = self.row.well_id, self.n
        key = lambda d: (self.status[d], self.status_reason[d], self.status_wo[d])
        s0 = 0
        for d in range(1, n + 1):
            if d == n or key(d) != key(s0):
                self.ep_counter += 1
                st = self.status[s0]
                open_end = d == n
                deferred = 0.0
                if st != "PRODUCING":
                    deferred = round(float(sum(self.q_base(x) * self.pm[x] for x in range(s0, d)) * 0.8), 1)
                res.status.append(dict(
                    episode_id=f"EP-{w}-{self.idp}{self.ep_counter:03d}", well_id=w, status=st,
                    start_date=self.start + timedelta(days=s0),
                    end_date=None if (open_end and not self.is_prepend) else self.start + timedelta(days=d - 1),
                    reason_code=self.status_reason[s0], is_rigless=self.status_rigless[s0], workover_id=self.status_wo[s0],
                    deferred_bbl=deferred, is_prepend=self.is_prepend))
                s0 = d

    def _emit_workovers(self, res: SimResult, oil: np.ndarray):
        w, n = self.row.well_id, self.n

        def mean_window(a, b):
            a, b = max(0, a), min(n, b)
            v = oil[a:b]
            v = v[~np.isnan(v)]
            return round(float(v.mean()), 1) if len(v) else None

        for c in self.cycles:
            if c.job_start >= n:            # still waiting at the window end: no job row yet
                self.dropped_wo.add(c.wo_id)
                continue
            in_progress = c.mode != "REVIEW" and c.job_end >= n
            # pre = last week before the failure / planned-job date (degraded rate, the true pre-job state)
            pre = mean_window(c.fail_day - 7, c.fail_day)
            post = None if (c.mode in ("REVIEW", "TERMINAL") or in_progress) else mean_window(c.job_end + 1, c.job_end + 8)
            if c.mode == "REVIEW":
                uplift = 0.0
            else:
                uplift = round(post - pre, 1) if (post is not None and pre is not None) else None
            res.workovers.append(dict(
                workover_id=c.wo_id, well_id=w,
                start_date=self.start + timedelta(days=c.job_start),
                end_date=None if in_progress else self.start + timedelta(days=c.job_end),
                job_code=f"JOB_{c.failure_code}", failure_code=c.failure_code, is_rigless=c.is_rigless,
                rig_id=c.rig_id, rig_days=float(c.repair) if (not c.is_rigless and c.mode != "REVIEW") else 0.0,
                pre_job_oil_bopd=pre, post_job_oil_bopd=post, uplift_bopd=uplift,
                outcome="IN_PROGRESS" if in_progress else c.outcome,
                run_life_days=int(c.run_life), is_censored=False,
                damage_reset_frac=0.0 if (c.mode == "REVIEW" or in_progress) else (1.0 if c.outcome == "SUCCESS" else 0.5),
                report_doc_id=None if in_progress else c.report_doc_id, catalogue_job_code=c.job,
                intervention_class=JOB_TO_IC[c.job], is_prepend=self.is_prepend))
        # right-censored current run (as v0.3.0, MS-060). External outages do not reset run life.
        if not self.is_prepend and not self.p.is_idle and self.status[n - 1] in ("PRODUCING", "SHUT_IN") \
                and self.reason[n - 1] in (None, "POWER_OUTAGE", "BANDH", "FLOOD"):
            ends = [c.job_end for c in self.cycles if c.mode != "REVIEW"]
            run_start = max(ends) + 1 if ends else 0
            rl = n - run_start
            if rl >= 20:
                end = self.start + timedelta(days=n - 1)
                res.workovers.append(dict(
                    workover_id=f"WO-{w}-CENS", well_id=w, start_date=end - timedelta(days=rl), end_date=end,
                    job_code="NONE_CENSORED", failure_code="NONE", is_rigless=False, rig_id=None, rig_days=0.0,
                    pre_job_oil_bopd=None, post_job_oil_bopd=None, uplift_bopd=0.0, outcome="CENSORED",
                    run_life_days=int(rl), is_censored=True, damage_reset_frac=0.0, report_doc_id=None,
                    catalogue_job_code=None, intervention_class=None, is_prepend=False))
