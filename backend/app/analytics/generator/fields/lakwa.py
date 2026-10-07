"""Lakwa field config (LKW-, 160 wells, 3 GGS). Natively simulated 2021-10-01 → 2026-09-30.

Story (SDD §5.2): water channelling, pump wear and tubing leaks dominate; logistics are poor and
**deteriorating** (rig waits grow across the window, GGS-II suffers grid power outages), so the
field lands ≈ −18 % vs. its plan (target_bias, F-09). Fixture dates are pinned to AS_OF 2026-09-23.
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

LAKWA = FieldConfig(
    field="Lakwa",
    prefix="LKW-",
    n_wells=160,
    seed=4301,
    asset="Assam",
    centroid=(27.058, 94.640),
    clusters=(
        ClusterConfig("LKW-GGS-I", "GGS", (27.076, 94.624), 0.38, 0.0085),
        ClusterConfig("LKW-GGS-II", "GGS", (27.056, 94.657), 0.34, 0.0085),
        ClusterConfig("LKW-GGS-III", "GGS", (27.040, 94.630), 0.28, 0.0085),
    ),
    facilities=(
        FacilityConfig("LKW-GGS-I", "GGS", "Lakwa Group Gathering Station I", 27.077, 94.626, 7000,
                       ("LKW-GGS-I",), compressor_capacity_mmscfd=1.4),
        FacilityConfig("LKW-GGS-II", "GGS", "Lakwa Group Gathering Station II", 27.055, 94.655, 6500,
                       ("LKW-GGS-II",), compressor_capacity_mmscfd=1.3),
        FacilityConfig("LKW-GGS-III", "GGS", "Lakwa Group Gathering Station III", 27.041, 94.632, 5000,
                       ("LKW-GGS-III",), compressor_capacity_mmscfd=0.9),
        FacilityConfig("LKW-CTF", "CDP", "Lakwa Central Tank Farm & Effluent Plant", 27.060, 94.640, 18000,
                       ("LKW-GGS-I", "LKW-GGS-II", "LKW-GGS-III"), water_handling_bwpd=52000),
    ),
    zones={"Tipam": 0.55, "Barail": 0.40, "Lakadong": 0.05},
    lift_mix={"SRP": 0.65, "GAS_LIFT": 0.25, "NATURAL": 0.10},
    mechanism_weights={
        "SRP": {"PUMP_OVERHAUL": 0.16, "ROD_REPLACE": 0.10, "TUBING_REPLACE": 0.13, "WAX_HOTOIL": 0.04,
                "WAX_SCRAPE": 0.03, "SCALE_ACID_BULLHEAD": 0.03, "SCALE_INHIBITOR": 0.015,
                "SAND_CLEANOUT": 0.035, "LIFT_OPTIM": 0.035, "GAS_SEP_INSTALL": 0.015,
                "LIFT_CONVERSION": 0.015, "MATRIX_ACID": 0.03, "HYDRAULIC_FRAC": 0.012,
                "RE_PERFORATION": 0.03, "ADD_PERFORATION": 0.015, "CEMENT_SQUEEZE": 0.07,
                "POLYMER_GEL": 0.025, "STRADDLE_PACKER": 0.04, "ZONE_TRANSFER": 0.012,
                "CHOKE_BACK": 0.03, "SURFACE_REPAIR": 0.05, "CASING_REPAIR": 0.02,
                "NO_JOB_JUSTIFIED": 0.04, "PLUG_ABANDON": 0.004},
        "GAS_LIFT": {"GLV_REPLACE": 0.24, "LIFT_OPTIM": 0.09, "LIFT_CONVERSION": 0.03,
                     "TUBING_REPLACE": 0.10, "WAX_HOTOIL": 0.05, "SAND_CLEANOUT": 0.05,
                     "SCALE_ACID_BULLHEAD": 0.03, "MATRIX_ACID": 0.04, "RE_PERFORATION": 0.03,
                     "CEMENT_SQUEEZE": 0.08, "STRADDLE_PACKER": 0.04, "POLYMER_GEL": 0.02,
                     "CHOKE_BACK": 0.04, "SURFACE_REPAIR": 0.06, "CASING_REPAIR": 0.02,
                     "NO_JOB_JUSTIFIED": 0.05},
        "NATURAL": {"WAX_HOTOIL": 0.11, "WAX_SOLVENT": 0.05, "SAND_CLEANOUT": 0.09,
                    "SCALE_ACID_BULLHEAD": 0.06, "SURFACE_REPAIR": 0.11, "MATRIX_ACID": 0.08,
                    "RE_PERFORATION": 0.06, "ADD_PERFORATION": 0.03, "CEMENT_SQUEEZE": 0.09,
                    "STRADDLE_PACKER": 0.05, "CHOKE_BACK": 0.10, "NO_JOB_JUSTIFIED": 0.08,
                    "LIFT_CONVERSION": 0.04, "TUBING_REPLACE": 0.03, "ZONE_TRANSFER": 0.02},
    },
    ops_event_rates={
        "GRID_POWER_OUTAGE": 2.0,                 # cluster events / yr
        "GRID_POWER_OUTAGE:LKW-GGS-II": 11.0,     # GGS-II feeder is the weak link (LKW-088 story)
        "BANDH_ACCESS_LOSS": 1.2,                 # field events / yr
        "FLOOD_ACCESS_LOSS": 0.4,                 # cluster events / monsoon
        "CHOKE_CHANGE": 0.5, "SPM_CHANGE": 0.4, "GL_RATE_CHANGE": 0.6,
    },
    target_bias=-0.18,
    fixtures={
        "LKW-047": FixtureSpec("LKW-047", "PUMP_CHANGE_AFTER_WAITS", "SRP", "LKW-GGS-I", "Tipam", {
            "precursor_start": "2026-04-01", "failure_date": "2026-05-15",
            "wait_on_rig_days": 41, "wait_on_material_days": 12, "repair_days": 3,
            "job": "PUMP_OVERHAUL", "outcome": "SUCCESS"}),
        "LKW-112": FixtureSpec("LKW-112", "CHANNELLING", "SRP", "LKW-GGS-III", "Tipam", {
            "signature_days": 90, "oil_drop_last_days": 25, "oil_drop_frac": 0.31}),
        "LKW-088": FixtureSpec("LKW-088", "GGS_POWER_OUTAGES", "SRP", "LKW-GGS-II", "Barail", {
            "note": "GGS-II cluster outages; the well itself has no mechanical downtime in the 180-day window"}),
    },
    reservoir=ReservoirRanges(
        q_i_bopd=(25.0, 120.0), b=(0.50, 0.90), d_i_per_yr=(0.07, 0.14), wc_init_pct=(62.0, 84.0),
        wc_slope_pp_per_yr=(1.5, 4.5), thp_kgcm2=(8.5, 13.5), chp_kgcm2=(13.0, 21.0),
        gor_scf_bbl=(220.0, 520.0), wht_degc=(36.0, 52.0), gl_inj_rate_mscfd=(250.0, 550.0),
        gl_inj_pressure_kgcm2=(55.0, 72.0),
    ),
    downtime=DowntimeModel(
        uptime_weibull_k=2.0, uptime_scale_days=230.0,
        rig_wait_median_days_start=14.0, rig_wait_median_days_end=48.0, rig_wait_sigma=0.55,
        p_wait_on_material=0.25, material_wait_median_days=9.0,
        p_permit_delay=0.06, p_crew_unavailable=0.06, p_deferred_maintenance=0.30,
        outcome_p=(0.60, 0.25, 0.15),
        # Deferred preventive maintenance: mean run life shortens across the window (N-D10). With rig
        # waits alone (14→48 d) the QTD gap was −8.8 %; failure frequency drift is the second real lever.
        uptime_scale_days_end=120.0,
    ),
    idle_fraction=0.05,
    boundary_radius_deg=0.045,
    fluid_props={
        "crude": {"api_gravity": 28.5, "pour_point_celsius": 30.0, "wax_content_pct": 12.0,
                  "sulfur_wt_pct": 0.18, "viscosity_cp_50c": 6.2},
        "water": {"tds_mg_l": 11800, "ph_at_25c": 7.6, "specific_gravity": 1.011,
                  "ions_mg_l": {"chloride_cl": 6400, "sodium_na": 4100, "calcium_ca": 290, "magnesium_mg": 70,
                                "barium_ba": 9.5, "strontium_sr": 15.0, "sulfate_so4": 55.0,
                                "bicarbonate_hco3": 910}},
    },
)
