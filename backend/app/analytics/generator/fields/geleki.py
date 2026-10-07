"""Geleki field config (GK-, 142 wells).

The 2023-10-01 → 2026-09-30 core is produced by the frozen ADK v0.3.0 generator
(``generator.v030``, seed 42) and must stay hash-identical to ``landing_v030`` (V-N5).
These numbers DOCUMENT that core (do not change draws) and parameterise only:
  * the 24-month prepend 2021-10-01 → 2023-09-30 (seed 4242, ``generator.prepend``),
  * the append-only gap columns (wht_degc, gl_inj_*), drawn from separate seeded streams,
  * hierarchy / facility reference data.
"""

from __future__ import annotations

from .base import (
    ClusterConfig,
    DowntimeModel,
    FacilityConfig,
    FieldConfig,
    FixtureSpec,
    ReservoirRanges,
)

V030_START = (2023, 10, 1)
PREPEND_SEED = 4242

# v0.3.0 failure-code mix per lift type (copied from v030/production.py draw_failure) — the prepend
# reuses it so the 5-year Geleki history has one consistent mechanism mix.
V030_FAILURE_MIX = {
    "SRP": {"TUBING_LEAK": 0.22, "ROD_PART": 0.18, "WAX": 0.15, "PUMP_WEAR": 0.13, "SURFACE": 0.12,
            "OTHER": 0.08, "SUDDEN_MECH": 0.05, "SAND": 0.05, "SCALE": 0.02},
    "GAS_LIFT": {"GL_INJ_ANOMALY": 0.30, "GL_HEADING": 0.15, "GL_LOADING": 0.12, "WAX": 0.15,
                 "TUBING_LEAK": 0.10, "SAND": 0.08, "SURFACE": 0.06, "SCALE": 0.02, "OTHER": 0.02},
    "NATURAL": {"WAX": 0.35, "SAND": 0.25, "SCALE": 0.10, "SURFACE": 0.20, "OTHER": 0.10},
}

GELEKI = FieldConfig(
    field="Geleki",
    prefix="GK-",
    n_wells=142,
    seed=42,
    asset="Assam",
    centroid=(26.962, 94.814),
    clusters=(
        # Fault-block centres and weights are the v0.3.0 well_master block_centers (frozen).
        ClusterConfig("GK-NE", "FAULT_BLOCK", (26.980, 94.830), 0.45, 0.012),
        ClusterConfig("GK-CENTRAL", "FAULT_BLOCK", (26.955, 94.805), 0.35, 0.012),
        ClusterConfig("GK-SW", "FAULT_BLOCK", (26.935, 94.780), 0.20, 0.012),
    ),
    facilities=(
        # Decision N-D3: v0.3 /api/field/infrastructure points sat ~20 km SW of the GK- wells
        # (they belonged to the retired GLK- layout). Capacities/names are carried over; positions
        # are re-sited inside the GK- fault blocks so the map layer is coherent.
        FacilityConfig("GGS-01", "GGS", "Gas Gathering Station 1 (Geleki South)", 26.930, 94.772, 6000,
                       ("GK-SW",), compressor_capacity_mmscfd=1.2),
        FacilityConfig("GGS-02", "GGS", "Gas Gathering Station 2 (Geleki Central)", 26.952, 94.800, 8500,
                       ("GK-CENTRAL",), compressor_capacity_mmscfd=2.0),
        FacilityConfig("GGS-03", "GGS", "Gas Gathering Station 3 (Geleki North/Barail)", 26.984, 94.836, 5500,
                       ("GK-NE",), compressor_capacity_mmscfd=1.0),
        FacilityConfig("CDP-01", "CDP", "Central Desalting & Effluent Treatment Plant (CDP)", 26.946, 94.790,
                       20000, ("GK-NE", "GK-CENTRAL", "GK-SW"), water_handling_bwpd=45000),
    ),
    zones={"Tipam": 0.45, "Barail": 0.35, "Lakadong": 0.20},
    lift_mix={"SRP": 0.70, "GAS_LIFT": 0.20, "NATURAL": 0.10},
    mechanism_weights={},          # Geleki labels come from catalogue.GELEKI_FAILURE_TO_JOB (K-1)
    ops_event_rates={
        "GRID_POWER_OUTAGE": 1.0,      # cluster events / yr (prepend only; v0.3.0 core is frozen)
        "BANDH_ACCESS_LOSS": 0.5,      # field events / yr
        "FLOOD_ACCESS_LOSS": 0.2,      # cluster events / monsoon
        "CHOKE_CHANGE": 0.2, "SPM_CHANGE": 0.2, "GL_RATE_CHANGE": 0.3,   # well events / yr
    },
    target_bias=0.0,
    fixtures={
        "GK-129": FixtureSpec("GK-129", "CHANNELLING_V030", "SRP", "GK-NE", "Tipam",
                              {"note": "v0.3.0 hero (D-7); docs 1998 CBL, 2019 failed WSO"}),
    },
    reservoir=ReservoirRanges(
        q_i_bopd=(35.0, 165.0), b=(0.55, 0.90), d_i_per_yr=(0.06, 0.13), wc_init_pct=(58.0, 76.0),
        wc_slope_pp_per_yr=(1.5, 4.0), thp_kgcm2=(9.5, 14.5), chp_kgcm2=(14.0, 22.0),
        gor_scf_bbl=(260.0, 560.0), wht_degc=(38.0, 54.0), gl_inj_rate_mscfd=(280.0, 600.0),
        gl_inj_pressure_kgcm2=(56.0, 74.0),
    ),
    downtime=DowntimeModel(
        uptime_weibull_k=2.0, uptime_scale_days=215.0,
        rig_wait_median_days_start=20.0, rig_wait_median_days_end=20.0, rig_wait_sigma=0.9,
        p_wait_on_material=0.10, material_wait_median_days=6.0,
        p_permit_delay=0.03, p_crew_unavailable=0.03, p_deferred_maintenance=0.10,
        outcome_p=(0.66, 0.22, 0.12),
    ),
    idle_fraction=0.045,
    boundary_radius_deg=0.075,
    fluid_props={
        "crude": {"api_gravity": 31.8, "pour_point_celsius": 32.0, "wax_content_pct": 14.6,
                  "sulfur_wt_pct": 0.22, "viscosity_cp_50c": 4.8},
        "water": {"tds_mg_l": 14600, "ph_at_25c": 7.3, "specific_gravity": 1.014,
                  "ions_mg_l": {"chloride_cl": 8250, "sodium_na": 5120, "calcium_ca": 340, "magnesium_mg": 92,
                                "barium_ba": 14.5, "strontium_sr": 22.0, "sulfate_so4": 42.0,
                                "bicarbonate_hco3": 780}},
    },
    native=False,
)
