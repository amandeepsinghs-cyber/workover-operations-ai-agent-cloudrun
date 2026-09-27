"""
Synthetic Well Telemetry, Workover History, and Technical Engineering Dossier Generator
for Geleki Field (Assam, India • ONGC).
Simulates 50 realistic brownfield oil & gas wells with:
- 24 months (730 days) of daily production telemetry
- Authentic high water cut progression and paraffin wax deposition anomalies
- Multi-page technical engineering reports:
  1. Well Completion Report & Geologic Dossier (WCR)
  2. Daily Workover Report (DWR / Shift Log) with engineer in-charge & hourly narrative
  3. Bottomhole Pressure Survey (BHP & Sonolog Fluid Level)
  4. Produced Water & Scale Chemistry Lab Assay
"""

import json
import math
import os
import random
from datetime import datetime, timedelta

DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "wells_data.json")

# Geleki Field Formations (Tipam, Barail, Kopili)
FORMATIONS = [
    ("Tipam Sand TS-1", "Geleki North Block, Assam"),
    ("Tipam Sand TS-2", "Geleki Central Block, Assam"),
    ("Tipam Sand TS-3", "Geleki Main Anticlinal Block, Assam"),
    ("Tipam Sand TS-4", "Geleki South Block, Assam"),
    ("Tipam Sand TS-6", "Geleki East Flank, Assam"),
    ("Barail Main Sand (BMS)", "Geleki Deep Pool, Assam"),
    ("Barail Coal Shale (BCS)", "Geleki West Block, Assam"),
    ("Kopili Formation", "Geleki Sub-Thrust Block, Assam"),
]

LIFT_TYPES = [
    "Continuous Gas Lift",
    "Continuous Gas Lift",
    "Continuous Gas Lift",
    "Sucker Rod Pump (SRP)",
    "Electric Submersible Pump (ESP)",
]

WORKOVER_TYPES = [
    {
        "type": "Hot Oil Circulation & Paraffin Wax Scraping",
        "contractor": "ONGC Well Services / Oilchem Assam",
        "cost_range": (14000, 24000),
        "desc_template": "Circulated 60 bbl heated crude (85°C) with xylene-based wax dispersant to dissolve severe paraffin choking in 2-7/8\" tubing.",
        "delta_range": (20.0, 55.0),
    },
    {
        "type": "Gas Lift Valve (GLV) Slickline Replacement",
        "contractor": "ONGC Wireline Services Group",
        "cost_range": (12000, 22000),
        "desc_template": "Retrieved cut 1\" Camco orifice valve from side pocket mandrel #3. Reset injection pressure to 850 psi line pressure from GGS-2.",
        "delta_range": (25.0, 60.0),
    },
    {
        "type": "Water Shut-Off (WSO) Polymer Gel Squeeze",
        "contractor": "Halliburton India / ONGC IOR Cell",
        "cost_range": (45000, 75000),
        "desc_template": "Injected 250 bbl cross-linked polyacrylamide gel plug into lower watered-out Tipam TS-4 perforations to arrest channel flow.",
        "delta_range": (35.0, 85.0),
    },
    {
        "type": "Mud Acid Matrix Stimulation (12:3 HCl:HF)",
        "contractor": "SLB Production Enhancement / ONGC",
        "cost_range": (38000, 62000),
        "desc_template": "Bullheaded 3,500 gal 12:3 Mud Acid with corrosion inhibitor and iron sequestering agent across 25 ft Tipam sand to clear clay fines.",
        "delta_range": (40.0, 95.0),
    },
    {
        "type": "Tipam Sand Cleanout & Gravel Pack Screen",
        "contractor": "Baker Hughes India Operations",
        "cost_range": (52000, 88000),
        "desc_template": "Coiled tubing nitrogen cleanout of 180 ft accumulated loose Tipam formation sand. Installed 20/40 mesh standalone wire-wrapped screen.",
        "delta_range": (30.0, 70.0),
    },
    {
        "type": "Layer Transfer / Re-completion to TS-2 Sand",
        "contractor": "ONGC Workover Rig #14 (Jorhat / Nazira)",
        "cost_range": (65000, 115000),
        "desc_template": "Set cast-iron bridge plug (CIBP) at 2,820m. Perforated virgin Tipam TS-2 sand interval (2,640-2,652m) at 4 SPF using hollow steel carrier guns.",
        "delta_range": (50.0, 120.0),
    },
]

ONGC_ENGINEERS = [
    "Er. B. K. Saikia, Suprtg. Engineer (Production), ONGC Nazira",
    "Er. R. K. Gogoi, Chief Engineer (Well Services), ONGC Sivasagar",
    "Er. D. N. Bora, Dy. General Manager (Reservoir), Assam Asset",
    "Er. Pradip Dutta, Suprtg. Chemist (RGL), ONGC Sibsagar",
    "Er. M. K. Sharma, In-Charge (Workover Group), Nazira Asset Base",
]


def generate_engineering_reports(well_id: str, well_num: int, formation: str, lift_type: str, latest_metrics: dict, workovers: list):
    """Generates authentic multi-page ONGC engineering dossiers and reports for the well."""
    last_wo = workovers[-1] if workovers else {}
    last_wo_date = last_wo.get("date", "2025-09-19")
    last_engineer = ONGC_ENGINEERS[well_num % len(ONGC_ENGINEERS)]

    # 1. Well Completion Report & Geologic Dossier (WCR)
    total_depth_m = 2845 + (well_num % 12) * 55
    perf_top = total_depth_m - 195
    perf_bottom = total_depth_m - 182

    wcr = {
        "report_id": f"ONGC/AA/{well_id}/WCR-HISTORICAL",
        "title": "Well Completion & Initial Production Testing Report",
        "issuing_authority": "Oil and Natural Gas Corporation Ltd. • Assam Asset (Sivasagar)",
        "spud_date": "1983-11-14",
        "completion_date": "1984-03-22",
        "total_depth_m": total_depth_m,
        "target_formation": formation,
        "casing_policy": [
            {"string": '20" Conductor Casing', "depth_m": 80, "cement_class": "Class G Neat"},
            {"string": '13-3/8" Surface Casing', "depth_m": 650, "cement_class": "Class G + 2% CaCl2"},
            {"string": '9-5/8" Production Casing', "depth_m": 2420, "cement_class": "Class G + Silica Flour"},
            {"string": '5-1/2" Production Liner', "depth_m": total_depth_m, "cement_class": "Class G High Temp Slurry"},
        ],
        "tubing_specification": '2-7/8" OD, 6.5 lb/ft, Grade N-80 EUE 8-round thread',
        "perforated_intervals": f"{perf_top:.1f}m - {perf_bottom:.1f}m ({formation}) at 4 SPF, 60° phasing",
        "initial_production_test": {
            "choke_mm": 6.0,
            "oil_rate_bopd": 420.0,
            "gas_rate_mcfd": 280.0,
            "water_cut_pct": 3.8,
            "flowing_tubing_pressure_psi": 580.0,
        },
        "crude_assay": {
            "api_gravity": 31.8,
            "pour_point_celsius": 32.0,
            "wax_content_pct": 14.6,
            "sulfur_wt_pct": 0.22,
            "viscosity_cp": "4.8 cP @ 50°C",
        },
    }

    # 2. Daily Workover Report (DWR / Shift Log)
    dwr = {
        "report_id": f"DWR/ONGC/{well_id}/{last_wo_date.replace('-', '')}",
        "title": "Daily Workover Shift Report & Mechanical Execution Log",
        "issuing_authority": "ONGC Well Services Directorate • Rig Operation Cell, Nazira Base",
        "date": last_wo_date,
        "supervising_engineer": last_engineer,
        "workover_rig": f"ONGC Workover Rig-14 (E-760 1000HP)",
        "operation_type": last_wo.get("type", "Hot Oil Circulation & Paraffin Wax Scraping"),
        "contractor": last_wo.get("contractor", "ONGC Well Services / Oilchem Assam"),
        "job_cost_usd": last_wo.get("cost_usd", 22000),
        "shift_hours": "06:00 to 18:00 hrs (12-hour continuous shift)",
        "hourly_logs": [
            {"time": "06:00 - 07:30", "activity": "Toolbox safety meeting conducted. Reviewed H2S hazards, high-pressure line checks, and PPE protocols."},
            {"time": "07:30 - 09:45", "activity": 'Rigged up 2-7/8" workstring. Tripped in hole. Tagged hard obstruction (paraffin wax/sand bridge) at 1,450m depth.'},
            {"time": "09:45 - 13:15", "activity": f"Hooked up hot oil pumping unit. Pumped 60 bbl heated lease crude (85°C) with 150 liters xylene wax dispersant down tubing at 1.8 bpm. Circulation established."},
            {"time": "13:15 - 15:45", "activity": f"Circulated dissolved wax to test pit. Ran mechanical scraper to {perf_top}m with smooth torque and zero drag."},
            {"time": "15:45 - 17:15", "activity": "Pressure tested production tubing to 1,500 psi for 15 minutes. Recorded zero leak-off. Chart certified."},
            {"time": "17:15 - 18:00", "activity": f"Secured wellhead. Connected flowline to Geleki GGS-2 header. Handed over well to production shift in-charge."},
        ],
        "outcome_summary": f"{last_wo.get('outcome', 'Success')} — Restored production flow by +{last_wo.get('flow_delta_bopd', 30.0)} BOPD above baseline.",
    }

    # 3. Bottomhole Pressure Survey (BHP) & Acoustic Echometer
    sbhp = round(2380.0 + (well_num % 10) * 18.0, 1)
    fbhp = round(sbhp * 0.48, 1)
    fluid_level = round(1180.0 + (well_num % 8) * 25.0, 1)

    bhp_survey = {
        "report_id": f"BHP/ONGC/{well_id}/SURVEY-2025",
        "title": "Subsurface Reservoir Pressure & Fluid Level Acoustic Survey",
        "issuing_authority": "ONGC Reservoir Management & Logging Services • Sivasagar",
        "survey_date": (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d"),
        "datum_depth_m_tvd": total_depth_m - 120,
        "static_bottomhole_pressure_sbhp_psi": sbhp,
        "flowing_bottomhole_pressure_fbhp_psi": fbhp,
        "drawdown_psi": round(sbhp - fbhp, 1),
        "productivity_index_pi": round(latest_metrics["oil_bopd"] / max(1.0, (sbhp - fbhp)), 3),
        "sonolog_fluid_level_m": fluid_level,
        "fluid_gradient_psi_ft": 0.385,
        "gas_lift_status": {
            "injection_pressure_casing_psi": latest_metrics["casing_pressure_psi"],
            "injection_rate_mcfd": round(latest_metrics["gas_mcfd"] * 1.2, 1),
            "operating_valve_depth_m": 1820,
            "status": "Optimum Drawdown / Continuous Aeration",
        },
    }

    # 4. Produced Water & Scale Chemistry Lab Assay
    lab_assay = {
        "report_id": f"LAB/ONGC/CHEM/{well_id}/ASSAY-2025",
        "title": "Produced Water Chemistry & Scale Deposition Potential Assay",
        "issuing_authority": "Regional Geoscience Laboratories (RGL) • ONGC Sivasagar, Assam",
        "sample_date": (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
        "water_cut_tested_pct": latest_metrics["water_cut_pct"],
        "total_dissolved_solids_tds_mg_l": 14600 + (well_num % 15) * 80,
        "ph_at_25c": 7.3,
        "specific_gravity": 1.014,
        "ionic_constituents_mg_l": {
            "chloride_cl": 8250,
            "sodium_na": 5120,
            "calcium_ca": 340,
            "magnesium_mg": 92,
            "barium_ba": 14.5,
            "strontium_sr": 22.0,
            "sulfate_so4": 42.0,
            "bicarbonate_hco3": 780,
        },
        "scaling_tendency_analysis": {
            "calcium_carbonate_caco3": "Moderate precipitation risk at surface choke and separator heater-treater.",
            "barium_sulfate_baso4": "Low risk under current injection water compatibility.",
            "iron_sulfide_fes": "Minor trace detected from anaerobic sulfate-reducing bacteria (SRB).",
        },
        "chemist_recommendation": "Maintain continuous injection of 25 ppm phosphonate scale inhibitor and biocide at the Geleki wellhead chemical dosing skid.",
    }

    return {
        "completion_report": wcr,
        "daily_workover_report": dwr,
        "bottomhole_pressure_survey": bhp_survey,
        "water_and_scale_lab_report": lab_assay,
    }


def generate_wells_dataset(num_wells: int = 50, days_history: int = 730):
    random.seed(42)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_history - 1)

    wells = []

    # Geleki Field Bounding Coordinates (Sivasagar District, Assam, India)
    min_lat, max_lat = 26.735, 26.815
    min_lng, max_lng = 94.645, 94.735

    statuses = ["healthy"] * 32 + ["warning"] * 12 + ["failed"] * 6
    random.shuffle(statuses)

    for i in range(num_wells):
        well_num = 101 + i
        well_id = f"GLK-{well_num}"
        formation, basin = random.choice(FORMATIONS)
        lift_type = random.choice(LIFT_TYPES)
        status = statuses[i]

        lat = round(random.uniform(min_lat, max_lat), 5)
        lng = round(random.uniform(min_lng, max_lng), 5)

        initial_oil = random.uniform(110.0, 240.0)
        gor = random.uniform(650.0, 1400.0)
        initial_water_cut = random.uniform(55.0, 72.0)
        casing_pressure_base = random.uniform(450.0, 750.0)
        tubing_pressure_base = random.uniform(180.0, 320.0)

        num_workovers = random.randint(2, 4)
        workover_days = sorted(random.sample(range(60, days_history - 30), num_workovers))
        workovers = []

        for wo_idx, wo_day in enumerate(workover_days):
            wo_date = (start_date + timedelta(days=wo_day)).strftime("%Y-%m-%d")
            wo_tmpl = random.choice(WORKOVER_TYPES)
            cost = random.randint(wo_tmpl["cost_range"][0], wo_tmpl["cost_range"][1])
            delta = round(random.uniform(wo_tmpl["delta_range"][0], wo_tmpl["delta_range"][1]), 1)
            outcome = "Success" if random.random() > 0.18 else "Partial"

            workovers.append({
                "id": f"WO-GLK-{well_num}-{wo_idx+1:02d}",
                "date": wo_date,
                "day_index": wo_day,
                "type": wo_tmpl["type"],
                "cost_usd": cost,
                "contractor": wo_tmpl["contractor"],
                "description": wo_tmpl["desc_template"],
                "outcome": outcome,
                "flow_delta_bopd": delta if outcome == "Success" else round(delta * 0.4, 1),
            })

        wo_map = {wo["day_index"]: wo for wo in workovers}
        telemetry = []

        for day in range(days_history):
            date_str = (start_date + timedelta(days=day)).strftime("%Y-%m-%d")

            b = 0.85
            di = 0.16 / 365.0
            decline_mult = (1.0 + b * di * day) ** (-1.0 / b)
            oil = initial_oil * decline_mult

            water_cut = min(93.0, initial_water_cut + (day / days_history) * 18.0)

            if day in wo_map:
                initial_oil += wo_map[day]["flow_delta_bopd"] * 0.75
                water_cut = max(40.0, water_cut - 12.0)

            if day >= (days_history - 60):
                if status == "failed":
                    oil = max(0.0, oil * (1.0 - (day - (days_history - 60)) / 10.0))
                    if day >= (days_history - 18):
                        oil = 0.0
                        tubing_pressure = random.uniform(15.0, 35.0)
                        casing_pressure = casing_pressure_base + random.uniform(100.0, 200.0)
                    else:
                        tubing_pressure = max(30.0, tubing_pressure_base - 100.0)
                        casing_pressure = casing_pressure_base + 50.0
                elif status == "warning":
                    wax_choke = 0.60 + 0.12 * math.sin(day / 6.0)
                    oil = oil * wax_choke
                    water_cut = min(95.0, water_cut + 12.0)
                    tubing_pressure = max(70.0, tubing_pressure_base - 80.0)
                    casing_pressure = casing_pressure_base + 35.0
                else:
                    noise = random.gauss(1.0, 0.035)
                    oil = oil * noise
                    tubing_pressure = tubing_pressure_base * random.gauss(1.0, 0.025)
                    casing_pressure = casing_pressure_base * random.gauss(1.0, 0.02)
            else:
                noise = random.gauss(1.0, 0.03)
                oil = oil * noise
                tubing_pressure = tubing_pressure_base * random.gauss(1.0, 0.025)
                casing_pressure = casing_pressure_base * random.gauss(1.0, 0.02)

            gas = oil * (gor / 1000.0) * random.gauss(1.0, 0.04)

            telemetry.append({
                "date": date_str,
                "oil_bopd": round(max(0.0, float(oil)), 1),
                "gas_mcfd": round(max(0.0, float(gas)), 1),
                "water_cut_pct": round(min(100.0, max(15.0, float(water_cut))), 1),
                "tubing_pressure_psi": round(max(0.0, float(tubing_pressure)), 1),
                "casing_pressure_psi": round(max(0.0, float(casing_pressure)), 1),
            })

        latest = telemetry[-1]
        uptime_pct = 97.4 if status == "healthy" else (81.2 if status == "warning" else 24.0)
        choke = 32 if status == "healthy" else (16 if status == "warning" else 0)

        clean_workovers = [
            {k: v for k, v in wo.items() if k != "day_index"}
            for wo in workovers
        ]

        current_metrics = {
            "oil_bopd": latest["oil_bopd"],
            "gas_mcfd": latest["gas_mcfd"],
            "water_cut_pct": latest["water_cut_pct"],
            "tubing_pressure_psi": latest["tubing_pressure_psi"],
            "casing_pressure_psi": latest["casing_pressure_psi"],
            "choke_pct": choke,
            "uptime_pct": uptime_pct,
        }

        # Generate Multi-Page Technical Reports Dossier
        reports = generate_engineering_reports(
            well_id=well_id,
            well_num=well_num,
            formation=formation,
            lift_type=lift_type,
            latest_metrics=current_metrics,
            workovers=clean_workovers,
        )

        wells.append({
            "id": well_id,
            "name": f"Geleki #{well_num} ({formation.split()[0]} {formation.split()[1]})",
            "coordinates": {"lat": lat, "lng": lng},
            "basin": "Assam-Arakan Basin, India (ONGC)",
            "formation": formation,
            "lift_type": lift_type,
            "status": status,
            "current_metrics": current_metrics,
            "workovers": clean_workovers,
            "reports": reports,
            "telemetry_summary": {
                "peak_oil_bopd": max(t["oil_bopd"] for t in telemetry),
                "min_oil_bopd": min(t["oil_bopd"] for t in telemetry),
                "avg_oil_bopd": round(sum(t["oil_bopd"] for t in telemetry) / len(telemetry), 1),
                "total_workovers": len(clean_workovers),
                "total_workover_spend_usd": sum(wo["cost_usd"] for wo in clean_workovers),
            },
            "history_730d": telemetry,
        })

    os.makedirs(os.path.dirname(DATA_FILE_PATH), exist_ok=True)
    with open(DATA_FILE_PATH, "w") as f:
        json.dump(wells, f, indent=2)

    print(f"[✓] Generated 24-month Geleki dataset with Technical Reports for {len(wells)} wells at {DATA_FILE_PATH}")
    return wells


def get_all_wells():
    if not os.path.exists(DATA_FILE_PATH):
        return generate_wells_dataset()
    with open(DATA_FILE_PATH, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    generate_wells_dataset()
