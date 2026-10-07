"""Lakhmani field config (LKM-, 110 wells, 2 GGS). Natively simulated 2021-10-01 → 2026-09-30.

Story (SDD §5.2): gas-lift heavy; sand, gas-lift valves and wax dominate; medium material waits
and bandh access losses; lands ≈ −6 % vs. plan. LKM-061 is the D-7 back-up hero (GLV + wax).
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

LAKHMANI = FieldConfig(
    field="Lakhmani",
    prefix="LKM-",
    n_wells=110,
    seed=4402,
    asset="Assam",
    centroid=(26.874, 94.700),
    clusters=(
        ClusterConfig("LKM-GGS-I", "GGS", (26.884, 94.689), 0.55, 0.0080),
        ClusterConfig("LKM-GGS-II", "GGS", (26.863, 94.712), 0.45, 0.0080),
    ),
    facilities=(
        FacilityConfig("LKM-GGS-I", "GGS", "Lakhmani Group Gathering Station I", 26.885, 94.691, 6000,
                       ("LKM-GGS-I",), compressor_capacity_mmscfd=2.2),
        FacilityConfig("LKM-GGS-II", "GGS", "Lakhmani Group Gathering Station II", 26.862, 94.710, 5000,
                       ("LKM-GGS-II",), compressor_capacity_mmscfd=1.8),
        FacilityConfig("LKM-CDP", "CDP", "Lakhmani Central Desalting Plant", 26.874, 94.700, 12000,
                       ("LKM-GGS-I", "LKM-GGS-II"), water_handling_bwpd=30000),
    ),
    zones={"Tipam": 0.35, "Barail": 0.45, "Lakadong": 0.20},
    lift_mix={"SRP": 0.40, "GAS_LIFT": 0.50, "NATURAL": 0.10},
    mechanism_weights={
        "SRP": {"PUMP_OVERHAUL": 0.12, "ROD_REPLACE": 0.08, "TUBING_REPLACE": 0.07, "WAX_HOTOIL": 0.07,
                "WAX_SOLVENT": 0.03, "WAX_INHIBITOR": 0.025, "WAX_SCRAPE": 0.03, "SAND_CLEANOUT": 0.12,
                "SAND_CONTROL": 0.04, "SCALE_ACID_BULLHEAD": 0.025, "LIFT_OPTIM": 0.04,
                "GAS_SEP_INSTALL": 0.02, "MATRIX_ACID": 0.04, "HYDRAULIC_FRAC": 0.012,
                "RE_PERFORATION": 0.03, "ADD_PERFORATION": 0.02, "CEMENT_SQUEEZE": 0.03,
                "STRADDLE_PACKER": 0.02, "ZONE_TRANSFER": 0.012, "CHOKE_BACK": 0.03,
                "SURFACE_REPAIR": 0.05, "CASING_REPAIR": 0.012, "NO_JOB_JUSTIFIED": 0.05,
                "PLUG_ABANDON": 0.004},
        "GAS_LIFT": {"GLV_REPLACE": 0.23, "LIFT_OPTIM": 0.08, "LIFT_CONVERSION": 0.03,
                     "WAX_HOTOIL": 0.09, "WAX_SOLVENT": 0.04, "WAX_INHIBITOR": 0.03,
                     "SAND_CLEANOUT": 0.10, "SAND_CONTROL": 0.03, "TUBING_REPLACE": 0.05,
                     "MATRIX_ACID": 0.035, "RE_PERFORATION": 0.02, "CEMENT_SQUEEZE": 0.03,
                     "STRADDLE_PACKER": 0.02, "CHOKE_BACK": 0.03, "SURFACE_REPAIR": 0.05,
                     "NO_JOB_JUSTIFIED": 0.05},
        "NATURAL": {"WAX_HOTOIL": 0.14, "WAX_SOLVENT": 0.06, "SAND_CLEANOUT": 0.14,
                    "SAND_CONTROL": 0.04, "SCALE_ACID_BULLHEAD": 0.05, "SURFACE_REPAIR": 0.10,
                    "MATRIX_ACID": 0.07, "RE_PERFORATION": 0.05, "CEMENT_SQUEEZE": 0.05,
                    "STRADDLE_PACKER": 0.03, "CHOKE_BACK": 0.08, "NO_JOB_JUSTIFIED": 0.08,
                    "LIFT_CONVERSION": 0.04, "ADD_PERFORATION": 0.03},
    },
    ops_event_rates={
        "GRID_POWER_OUTAGE": 2.0,
        "BANDH_ACCESS_LOSS": 2.5,
        "FLOOD_ACCESS_LOSS": 0.3,
        "CHOKE_CHANGE": 0.4, "SPM_CHANGE": 0.4, "GL_RATE_CHANGE": 0.8,
    },
    target_bias=-0.06,
    fixtures={
        "LKM-023": FixtureSpec("LKM-023", "SAND_INFLUX", "SRP", "LKM-GGS-I", "Barail", {
            "signature_days": 60, "oil_drop_frac": 0.25, "prior_sand_cleanouts": 2}),
        "LKM-061": FixtureSpec("LKM-061", "GLV_PLUS_WAX", "GAS_LIFT", "LKM-GGS-II", "Tipam", {
            "glv_signature_days": 75, "wax_signature_days": 45}),
        "LKM-090": FixtureSpec("LKM-090", "RESERVOIR_DECLINE", "SRP", "LKM-GGS-I", "Barail", {
            "signature_days": 120, "decline_frac": 0.20, "n_offsets": 6, "offset_decline_frac": 0.19}),
    },
    reservoir=ReservoirRanges(
        q_i_bopd=(30.0, 140.0), b=(0.55, 0.90), d_i_per_yr=(0.06, 0.12), wc_init_pct=(48.0, 74.0),
        wc_slope_pp_per_yr=(1.5, 4.0), thp_kgcm2=(9.5, 15.0), chp_kgcm2=(14.0, 23.0),
        gor_scf_bbl=(380.0, 900.0), wht_degc=(34.0, 50.0), gl_inj_rate_mscfd=(300.0, 650.0),
        gl_inj_pressure_kgcm2=(58.0, 78.0),
    ),
    downtime=DowntimeModel(
        uptime_weibull_k=2.0, uptime_scale_days=250.0,
        rig_wait_median_days_start=13.0, rig_wait_median_days_end=19.0, rig_wait_sigma=0.55,
        p_wait_on_material=0.30, material_wait_median_days=7.0,
        p_permit_delay=0.04, p_crew_unavailable=0.04, p_deferred_maintenance=0.20,
        outcome_p=(0.66, 0.22, 0.12),
    ),
    idle_fraction=0.045,
    boundary_radius_deg=0.040,
    fluid_props={
        "crude": {"api_gravity": 33.0, "pour_point_celsius": 34.0, "wax_content_pct": 16.5,
                  "sulfur_wt_pct": 0.15, "viscosity_cp_50c": 3.9},
        "water": {"tds_mg_l": 16900, "ph_at_25c": 7.1, "specific_gravity": 1.016,
                  "ions_mg_l": {"chloride_cl": 9600, "sodium_na": 5900, "calcium_ca": 420, "magnesium_mg": 105,
                                "barium_ba": 19.0, "strontium_sr": 28.0, "sulfate_so4": 36.0,
                                "bicarbonate_hco3": 690}},
    },
)
