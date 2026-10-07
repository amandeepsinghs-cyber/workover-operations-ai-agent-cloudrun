"""FieldConfig dataclasses (SDD §5.2).

A field is fully described by one frozen ``FieldConfig``. Geleki's config documents the
frozen ADK v0.3.0 parameters (its core rows are produced by ``generator.v030`` unchanged);
Lakwa and Lakhmani are simulated natively by ``generator.simulate`` from these numbers.

All numbers in the field modules are orchestrator-owned design parameters (DELEGATION.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date


@dataclass(frozen=True)
class ClusterConfig:
    cluster_id: str
    cluster_type: str                 # FAULT_BLOCK (Geleki) | GGS (Lakwa / Lakhmani)
    center: tuple[float, float]       # (lat, lon), synthetic (D-3)
    weight: float                     # share of the field's wells
    spread_deg: float = 0.010         # 1-sigma scatter of well positions around the centre


@dataclass(frozen=True)
class FacilityConfig:
    facility_id: str
    facility_type: str                # GGS | CDP
    name: str
    lat: float
    lon: float
    capacity_bopd: int
    serviced_cluster_ids: tuple[str, ...]
    compressor_capacity_mmscfd: float | None = None
    water_handling_bwpd: int | None = None


@dataclass(frozen=True)
class FixtureSpec:
    """A scripted demo story (D-11). ``kind`` selects the script in ``generator.fixtures``."""

    well_id: str
    kind: str
    lift_type: str
    cluster_id: str | None = None
    zone: str | None = None
    params: dict = dc_field(default_factory=dict)


@dataclass(frozen=True)
class ReservoirRanges:
    """Uniform ranges for per-well production parameters (native simulation)."""

    q_i_bopd: tuple[float, float]
    b: tuple[float, float]
    d_i_per_yr: tuple[float, float]
    wc_init_pct: tuple[float, float]
    wc_slope_pp_per_yr: tuple[float, float]
    thp_kgcm2: tuple[float, float]
    chp_kgcm2: tuple[float, float]
    gor_scf_bbl: tuple[float, float]
    wht_degc: tuple[float, float]
    gl_inj_rate_mscfd: tuple[float, float]
    gl_inj_pressure_kgcm2: tuple[float, float]


@dataclass(frozen=True)
class DowntimeModel:
    """Renewal-process and logistics parameters (native simulation)."""

    uptime_weibull_k: float
    uptime_scale_days: float
    rig_wait_median_days_start: float     # median WAIT_ON_RIG at the window start
    rig_wait_median_days_end: float       # ... and at the window end (linear drift; Lakwa deteriorates)
    rig_wait_sigma: float                 # lognormal sigma
    p_wait_on_material: float
    material_wait_median_days: float
    p_permit_delay: float
    p_crew_unavailable: float
    p_deferred_maintenance: float         # degraded running beyond SLA before a rigless job
    outcome_p: tuple[float, float, float]  # SUCCESS / PARTIAL / FAILED
    uptime_scale_days_end: float | None = None   # if set, Weibull scale drifts linearly to this by the window end


@dataclass(frozen=True)
class FieldConfig:
    field: str
    prefix: str
    n_wells: int
    seed: int
    asset: str
    centroid: tuple[float, float]                  # synthetic, near Sivasagar (D-3)
    clusters: tuple[ClusterConfig, ...]
    facilities: tuple[FacilityConfig, ...]
    zones: dict[str, float]                        # Tipam / Barail / Lakadong mix
    lift_mix: dict[str, float]                     # SRP / GAS_LIFT / NATURAL
    mechanism_weights: dict[str, dict[str, float]]  # lift_type -> catalogue job_code -> weight
    ops_event_rates: dict[str, float]              # per well-year by event_type (stochastic overlay)
    target_bias: float                             # designed field gap vs target (F-09), fraction
    fixtures: dict[str, FixtureSpec]
    reservoir: ReservoirRanges | None = None
    downtime: DowntimeModel | None = None
    primary_reservoirs: tuple[str, ...] = ("Tipam", "Barail", "Lakadong")
    idle_fraction: float = 0.045
    boundary_radius_deg: float = 0.06              # synthetic boundary polygon radius around the centroid
    fluid_props: dict = dc_field(default_factory=dict)  # crude assay / water chemistry reference data
    start: date = date(2021, 10, 1)
    end: date = date(2026, 9, 30)
    native: bool = True                            # False for Geleki (frozen v0.3.0 core + prepend)
