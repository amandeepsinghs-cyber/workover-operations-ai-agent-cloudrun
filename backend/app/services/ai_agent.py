"""
AI Conversational Agent & Prescriptive Recommendations Engine for Geleki Field (Assam, India).
Integrates Google Gemini 2.5 Flash with deep Geleki brownfield context (ONGC Assam Asset),
and includes a deterministic local petroleum engineering diagnostic fallback
tailored to Tipam/Barail sands, high water cut, paraffin wax choking, and continuous gas lift.
"""

import os
import json
from typing import Dict, Any, List

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def build_well_context(well: Dict[str, Any]) -> str:
    """Builds comprehensive operational context for Geleki well prompt injection."""
    current = well["current_metrics"]
    summary = well.get("telemetry_summary", {})
    workovers = well.get("workovers", [])
    reports = well.get("reports", {})

    wo_lines = []
    for wo in workovers:
        wo_lines.append(
            f"- [{wo['date']}] {wo['type']} by {wo['contractor']} | Cost: ${wo['cost_usd']:,} | "
            f"Outcome: {wo['outcome']} | Flow Impact: +{wo['flow_delta_bopd']} BOPD\n"
            f"  Details: {wo['description']}"
        )
    wo_text = "\n".join(wo_lines) if wo_lines else "No recorded major workovers."

    # Extract Reports
    wcr = reports.get("completion_report", {})
    dwr = reports.get("daily_workover_report", {})
    bhp = reports.get("bottomhole_pressure_survey", {})
    lab = reports.get("water_and_scale_lab_report", {})

    dwr_logs = "\n".join(
        [f"    * {log['time']}: {log['activity']}" for log in dwr.get("hourly_logs", [])]
    )

    casing_text = ", ".join(
        [f"{c['string']} to {c['depth_m']}m ({c['cement_class']})" for c in wcr.get("casing_policy", [])]
    )

    perf_text = ", ".join(
        [f"{p['top_depth_m']}-{p['bottom_depth_m']}m ({p['formation']}, {p['shots_per_meter']} spm, {p['status']})" for p in wcr.get("perforated_intervals", [])]
    )

    crude = wcr.get("crude_assay", {})
    ionic = lab.get("ionic_constituents_mg_l", {})
    scale = lab.get("scaling_tendency_analysis", {})

    context = f"""
=== GELEKI FIELD ASSET PROFILE: {well['name']} ({well['id']}) ===
- Operator: ONGC (Assam Asset, Sivasagar)
- Field Type: Mature Brownfield (Producing since ~1968)
- Basin: Assam-Arakan Basin | Formation: {well['formation']}
- Artificial Lift: {well['lift_type']} (Connected to Geleki Gas Gathering Station Network)
- Location Coordinates: Lat {well['coordinates']['lat']}°N, Lng {well['coordinates']['lng']}°E

=== CURRENT TELEMETRY (TODAY) ===
- Oil Production: {current['oil_bopd']} BOPD
- Dissolved Gas Flow: {current['gas_mcfd']} MCFD
- Water Cut: {current['water_cut_pct']}% (Brownfield secondary water injection recovery)
- Tubing Head Pressure: {current['tubing_pressure_psi']} psi
- Casing / Injection Pressure: {current['casing_pressure_psi']} psi
- Surface Choke Opening: {current['choke_pct']}%
- Operational Uptime: {current['uptime_pct']}%

=== 24-MONTH HISTORICAL TELEMETRY SUMMARY ===
- Peak Production: {summary.get('peak_oil_bopd', 'N/A')} BOPD
- Minimum Production: {summary.get('min_oil_bopd', 'N/A')} BOPD
- 24-Month Average Flow: {summary.get('avg_oil_bopd', 'N/A')} BOPD
- Total Interventions: {summary.get('total_workovers', 0)}
- Cumulative Workover Expenditure: ${summary.get('total_workover_spend_usd', 0):,}

=== CHRONOLOGICAL WORKOVER & INTERVENTION LOG ===
{wo_text}

=== ENGINEERING REPORTS DOSSIER ===
1. WELL COMPLETION REPORT [Ref: {wcr.get('report_id', 'N/A')}]
   - Spud Date: {wcr.get('spud_date', 'N/A')} | Completion: {wcr.get('completion_date', 'N/A')}
   - Total Depth: {wcr.get('total_depth_m', 'N/A')}m | Target: {wcr.get('target_formation', 'N/A')}
   - Casing Policy: {casing_text}
   - Perforations: {perf_text}
   - Crude Assay: API Gravity {crude.get('api_gravity', 'N/A')}°, Wax Content {crude.get('paraffin_wax_pct', 'N/A')}%, Pour Point {crude.get('pour_point_c', 'N/A')}°C

2. DAILY WORKOVER SHIFT REPORT [Ref: {dwr.get('report_id', 'N/A')}]
   - Date: {dwr.get('date', 'N/A')} | Rig: {dwr.get('workover_rig', 'N/A')}
   - Supervising Engineer: {dwr.get('supervising_engineer', 'N/A')}
   - Contractor: {dwr.get('contractor', 'N/A')} | Shift: {dwr.get('shift_hours', 'N/A')}
   - Hourly Execution Logs:
{dwr_logs}
   - Outcome Summary: {dwr.get('outcome_summary', 'N/A')}

3. BOTTOMHOLE PRESSURE & SONOLOG SURVEY [Ref: {bhp.get('report_id', 'N/A')}]
   - Survey Date: {bhp.get('survey_date', 'N/A')} | Datum Depth: {bhp.get('datum_depth_m_tvd', 'N/A')}m TVD
   - Static BHP (SBHP): {bhp.get('static_bottomhole_pressure_sbhp_psi', 'N/A')} psi
   - Flowing BHP (FBHP): {bhp.get('flowing_bottomhole_pressure_fbhp_psi', 'N/A')} psi
   - Drawdown: {bhp.get('drawdown_psi', 'N/A')} psi | Productivity Index: {bhp.get('productivity_index_pi', 'N/A')} BOPD/psi
   - Sonolog Fluid Level: {bhp.get('sonolog_fluid_level_m', 'N/A')}m from surface
   - Fluid Gradient: {bhp.get('fluid_gradient_psi_ft', 'N/A')} psi/ft | Gas Lift: {bhp.get('gas_lift_status', 'N/A')}

4. PRODUCED WATER CHEMISTRY & SCALE ASSAY [Ref: {lab.get('report_id', 'N/A')}]
   - Sample Date: {lab.get('sample_date', 'N/A')} | Tested Water Cut: {lab.get('water_cut_tested_pct', 'N/A')}%
   - TDS: {lab.get('total_dissolved_solids_tds_mg_l', 'N/A')} mg/L | pH @ 25°C: {lab.get('ph_at_25c', 'N/A')} | SG: {lab.get('specific_gravity', 'N/A')}
   - Key Ions (mg/L): Cl: {ionic.get('chloride_cl', 'N/A')}, Na: {ionic.get('sodium_na', 'N/A')}, Ca: {ionic.get('calcium_ca', 'N/A')}, Mg: {ionic.get('magnesium_mg', 'N/A')}, Ba: {ionic.get('barium_ba', 'N/A')}, SO4: {ionic.get('sulfate_so4', 'N/A')}
   - Scaling Tendency: CaCO3: {scale.get('calcium_carbonate_caco3', 'N/A')} (Index: {scale.get('stiff_davis_index', 'N/A')}), BaSO4: {scale.get('barium_sulfate_baso4', 'N/A')}
   - Chemist Recommendation: {lab.get('chemist_recommendation', 'N/A')}
==================================================
"""
    return context.strip()


def query_local_petroleum_expert(
    well: Dict[str, Any], user_message: str, language: str = "hinglish"
) -> Dict[str, Any]:
    """
    Snappy, Conversational Geleki Petroleum Field Diagnostic Engine.
    Hard-capped to 2-3 punchy, natural sentences (35-45 words).
    Bilingual: Hinglish (conversational Hindi+English), English, or Pure Hindi.
    """
    current = well["current_metrics"]
    status = well["status"]
    workovers = well.get("workovers", [])
    reports = well.get("reports", {})
    wcr = reports.get("completion_report", {})
    dwr = reports.get("daily_workover_report", {})
    bhp = reports.get("bottomhole_pressure_survey", {})
    lab = reports.get("water_and_scale_lab_report", {})

    last_wo = workovers[-1] if workovers else None
    user_lower = user_message.lower()
    lang = (language or "hinglish").lower()

    text_response = ""
    recommendation = None

    sup_eng = dwr.get("supervising_engineer", "Er. R. K. Gogoi").split(",")[0]
    rig = dwr.get("workover_rig", "Rig-14")
    sbhp = bhp.get("static_bottomhole_pressure_sbhp_psi", 2400.0)
    fbhp = bhp.get("flowing_bottomhole_pressure_fbhp_psi", 1150.0)
    drawdown = bhp.get("drawdown_psi", sbhp - fbhp)
    fluid_level = bhp.get("sonolog_fluid_level_m", 1300.0)
    tds = lab.get("total_dissolved_solids_tds_mg_l", 15500)
    total_spend = sum(w["cost_usd"] for w in workovers)

    # 1. Supervising Engineer, Rig, Shift Logs, or Tagged Wax/Sand Depth
    if any(k in user_lower for k in ["supervising", "supervisor", "engineer", "rig", "shift log", "hourly", "tagged", "depth", "who ran", "who worked", "who supervised", "what rig", "kisne", "kya depth"]):
        gain = f"+{last_wo['flow_delta_bopd']}" if last_wo else "+50"
        wo_date = last_wo["date"] if last_wo else "recent"

        if lang == "hinglish":
            text_response = (
                f"{well['name']} ka last workover {wo_date} ko {sup_eng} ne supervise kiya tha {rig} par. "
                f"Crew ne 1,450 meters par wax aur sand bridge tag karke hot oil se clean kiya, jisse production mein {gain} BOPD ka gain mila."
            )
        elif lang == "hindi":
            text_response = (
                f"{well['name']} का पिछला वर्कओवर {sup_eng} की देखरेख में {rig} पर हुआ था। "
                f"टीम ने 1,450 मीटर पर वैक्स ब्लॉकेज साफ किया, जिससे उत्पादन में {gain} बीओपीडी की बढ़ोतरी दर्ज हुई।"
            )
        else:
            text_response = (
                f"{well['name']}'s last workover was supervised by {sup_eng} on {rig}. "
                f"The crew tagged and cleared a paraffin wax bridge at 1,450 meters, regaining {gain} BOPD in net flow."
            )

    # 2. Bottomhole Pressure (BHP), Sonolog, Fluid Level, Reservoir Drawdown
    elif any(k in user_lower for k in ["bhp", "bottomhole", "bottom-hole", "bottom hole", "reservoir pressure", "static pressure", "flowing pressure", "sbhp", "fbhp", "drawdown", "sonolog", "fluid level", "pressure", "prashar"]):
        if lang == "hinglish":
            text_response = (
                f"Subsurface survey ke mutabiq static pressure {sbhp:.0f} psi aur flowing pressure {fbhp:.0f} psi hai, jisse {drawdown:.0f} psi ka drawdown mil raha hai. "
                f"Acoustic sonolog pe liquid level surface se {fluid_level:.0f} meters niche steady mila hai."
            )
        elif lang == "hindi":
            text_response = (
                f"सबसरफेस सर्वे में स्टैटिक प्रेशर {sbhp:.0f} पीएसआई और फ्लोइंग प्रेशर {fbhp:.0f} पीएसआई दर्ज हुआ, यानी {drawdown:.0f} पीएसआई का ड्रॉडाउन है। "
                f"सोनलॉग के अनुसार लिक्विड लेवल सतह से {fluid_level:.0f} मीटर गहराई पर है।"
            )
        else:
            text_response = (
                f"Subsurface surveys record a static pressure of {sbhp:.0f} psi and flowing pressure of {fbhp:.0f} psi, yielding a {drawdown:.0f} psi drawdown. "
                f"The acoustic sonolog confirms the liquid column at {fluid_level:.0f} meters."
            )

    # 3. Water Chemistry, Scale Deposition, Lab Assay, Ionic Constituents
    elif any(k in user_lower for k in ["water cut", "water assay", "lab", "scale", "scaling", "calcium", "barium", "chloride", "tds", "ph", "chemist", "chemistry", "pani"]):
        if lang == "hinglish":
            text_response = (
                f"Produced water lab assay mein TDS {tds:,} mg/L mila hai aur Stiff-Davis index positive hone se surface choke pe CaCO3 scale ka risk hai. "
                f"Lead geochemist ne wellhead skid se continuous phosphonate scale inhibitor inject karne ki recommendation di hai."
            )
        elif lang == "hindi":
            text_response = (
                f"वॉटर लैब टेस्ट में टीडीएस {tds:,} मिलीग्राम/लीटर मिला है और सरफेस चोक पर कैल्शियम कार्बोनेट स्केल का खतरा है। "
                f"केमिस्ट ने निरंतर फॉस्फोनेट स्केल इनहिबिटर डोजिंग की सलाह दी है।"
            )
        else:
            text_response = (
                f"Produced water analysis shows {tds:,} mg/L TDS with a positive Stiff-Davis index indicating calcium carbonate scale potential at the surface choke. "
                f"The lab recommends continuous phosphonate scale inhibitor dosing."
            )

    # 4. Well Completion, Casing, Perforation, Spud Date
    elif any(k in user_lower for k in ["completion", "spud", "casing", "perforation", "interval", "total depth", "crude assay", "pour point", "wax content", "api gravity"]):
        td = wcr.get("total_depth_m", 3120)
        wax = wcr.get("crude_assay", {}).get("paraffin_wax_pct", 14.5)
        if lang == "hinglish":
            text_response = (
                f"{well['name']} ki total depth {td} meters hai {well['formation']} formation mein. "
                f"Geleki crude mein {wax}% paraffin wax aur 32°C pour point hai, isliye regular hot oil flush aur pour-point depressant zaroori hota hai."
            )
        elif lang == "hindi":
            text_response = (
                f"{well['name']} की कुल गहराई {td} मीटर है। "
                f"गेलेकी क्रूड में {wax}% पैराफिन वैक्स और 32 डिग्री सेल्सियस पोर पॉइंट है, जिसके लिए नियमित हॉट ऑयल ट्रीटमेंट जरूरी है।"
            )
        else:
            text_response = (
                f"{well['name']} was completed to {td} meters total depth in the {well['formation']}. "
                f"Geleki crude carries a high {wax}% paraffin wax content with a 32°C pour point, requiring routine thermal remediation."
            )

    # 5. Last Workover / History
    elif any(k in user_lower for k in ["last workover", "previous intervention", "pichla", "kya hua tha", "history"]):
        if last_wo:
            flow_gain = f"+{last_wo['flow_delta_bopd']}"
            if lang == "hinglish":
                text_response = (
                    f"{well['name']} pe last operation {last_wo['type']} tha jo {last_wo['date']} ko {last_wo['contractor']} ne kiya. "
                    f"Job cost ${last_wo['cost_usd']:,} rahi aur successful execution ke baad production {flow_gain} BOPD badh gaya."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} पर अंतिम कार्य {last_wo['date']} को {last_wo['type']} था। "
                    f"इस पर ${last_wo['cost_usd']:,} का खर्च आया और उत्पादन में {flow_gain} बीओपीडी का इजाफा हुआ।"
                )
            else:
                text_response = (
                    f"The most recent intervention on {well['name']} was a {last_wo['type']} on {last_wo['date']} by {last_wo['contractor']}. "
                    f"At a cost of ${last_wo['cost_usd']:,}, it successfully delivered a {flow_gain} BOPD net production gain."
                )
        else:
            text_response = (
                f"{well['name']} pe pichle 24 mahino mein koi major workover logged nahi hai."
                if lang == "hinglish"
                else f"No major workovers have been logged on {well['name']} in the past 24 months."
            )

    # 6. Why decline / failed / warning / status
    elif any(k in user_lower for k in ["why", "decline", "drop", "fail", "kyu", "gir gaya", "kam kyu", "kharab"]):
        if status == "failed":
            if lang == "hinglish":
                text_response = (
                    f"{well['name']} abhi offline hai kyunki production 0 BOPD ho gaya hai aur tubing pressure {current['tubing_pressure_psi']} psi tak gir gaya hai. "
                    f"Diagnosis ke mutabiq continuous gas lift valve fail ho gaya hai ya formation sand tubing mein bridge ho gayi hai. Workover rig bulana padega."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} अभी शटडाउन है क्योंकि प्रेशर गिरकर {current['tubing_pressure_psi']} पीएसआई हो गया है। "
                    f"गैस लिफ्ट वॉल्व खराब होने या सैंड ब्रिजिंग का संदेह है। वर्कओवर रिग मोबिलाइज करना होगा।"
                )
            else:
                text_response = (
                    f"{well['name']} is offline due to a complete tubing pressure drop to {current['tubing_pressure_psi']} psi. "
                    f"Diagnostic signatures indicate either a parted gas lift valve or heavy formation sand bridging, requiring an immediate rig workover."
                )
        elif status == "warning":
            if lang == "hinglish":
                text_response = (
                    f"{well['name']} warning status pe hai kyunki water cut {current['water_cut_pct']}% tak badh gaya hai aur wax deposition ki wajah se tubing choke ho rahi hai. "
                    f"Production girkar {current['oil_bopd']} BOPD reh gaya hai. Immediate hot oil xylene treatment aur polymer gel squeeze recommend karta hoon."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} वार्निंग स्थिति में है क्योंकि वाटर कट {current['water_cut_pct']}% पहुंच गया है और वैक्स से ट्यूबिंग चोक हो रही है। "
                    f"उत्पादन घटकर {current['oil_bopd']} बीओपीडी रह गया है। हॉट ऑयल फ्लश की तुरंत जरूरत है।"
                )
            else:
                text_response = (
                    f"{well['name']} is under warning status as water cut surged to {current['water_cut_pct']}% and paraffin wax is choking the production string. "
                    f"Flow has dropped to {current['oil_bopd']} BOPD; I recommend immediate hot oiling and a polymer water shut-off."
                )
        else:
            if lang == "hinglish":
                text_response = (
                    f"{well['name']} bilkul smooth chal raha hai {current['oil_bopd']} BOPD production aur {current['water_cut_pct']}% water cut ke sath. "
                    f"Gas lift injection pressure {current['casing_pressure_psi']} psi pe steady hai aur koi active mechanical issue nahi hai."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} पूरी तरह स्थिर है और {current['oil_bopd']} बीओपीडी का उत्पादन दे रहा है। "
                    f"गैस लिफ्ट प्रेशर {current['casing_pressure_psi']} पीएसआई पर संतुलित है और कोई समस्या नहीं है।"
                )
            else:
                text_response = (
                    f"{well['name']} is operating stably at {current['oil_bopd']} BOPD with {current['water_cut_pct']}% water cut. "
                    f"Gas lift injection remains optimal at {current['casing_pressure_psi']} psi with healthy uptime."
                )

    # 7. Cost / Spend
    elif any(k in user_lower for k in ["cost", "spend", "budget", "kharcha", "rupaye", "dollars"]):
        last_name = last_wo["type"] if last_wo else "routine maintenance"
        if lang == "hinglish":
            text_response = (
                f"Pichle 24 mahino mein {well['name']} pe kul ${total_spend:,} kharch hua hai across {len(workovers)} operations. "
                f"Isme sabse bada kharcha {last_name} ka tha."
            )
        elif lang == "hindi":
            text_response = (
                f"पिछले 24 महीनों में {well['name']} पर कुल ${total_spend:,} का खर्च हुआ है {len(workovers)} ऑपरेशन्स में। "
                f"सबसे मुख्य खर्च {last_name} पर हुआ।"
            )
        else:
            text_response = (
                f"Total intervention spend on {well['name']} over the last 24 months is ${total_spend:,} across {len(workovers)} jobs, "
                f"led primarily by the {last_name}."
            )

    # 8. General Overview Fallback
    else:
        status_label = "Optimal" if status == "healthy" else ("Needs Attention" if status == "warning" else "Failed")
        if lang == "hinglish":
            text_response = (
                f"Namaste! {well['name']} Geleki Field mein {well['formation']} formation se abhi {current['oil_bopd']} BOPD de raha hai ({status_label}). "
                f"Water cut {current['water_cut_pct']}% hai. Aap mujhse workover history, wax problem, ya recommendations ke baare mein puch sakte hain."
            )
        elif lang == "hindi":
            text_response = (
                f"नमस्ते! {well['name']} अभी {current['oil_bopd']} बीओपीडी का उत्पादन दे रहा है। "
                f"वाटर कट {current['water_cut_pct']}% है। आप वर्कओवर इतिहास या सुधार योजनाओं के बारे में पूछ सकते हैं।"
            )
        else:
            text_response = (
                f"{well['name']} is currently producing {current['oil_bopd']} BOPD with {current['water_cut_pct']}% water cut under {status_label} status. "
                f"Feel free to ask about workover history, wax choking, or recommended interventions."
            )

    if any(k in user_lower for k in ["recommend", "fix", "action", "upay", "kya karein", "solution"]) or status in ("warning", "failed"):
        recommendation = generate_structured_recommendation(well)

    return {
        "response": text_response,
        "recommendation": recommendation,
        "engine": "local-geleki-petroleum-expert-v1",
        "well_id": well["id"],
        "language": lang,
    }


def generate_structured_recommendation(well: Dict[str, Any]) -> Dict[str, Any]:
    """Generates structured engineering recommendations for Geleki brownfield wells."""
    status = well["status"]
    formation = well["formation"]

    if status == "failed":
        return {
            "title": f"Mobilize ONGC Workover Rig & Sand Cleanout ({formation})",
            "urgency": "Immediate (Within 48 hrs)",
            "urgency_badge": "critical",
            "estimated_cost_usd": 68000,
            "projected_flow_uplift_bopd": 85.0,
            "estimated_payback_days": 22,
            "action_items": [
                "Mobilize ONGC workover rig from Nazira base to pull tubing and unseat stuck assembly.",
                "Run coiled tubing with nitrogen foam to circulate out bridged Tipam formation sand.",
                "Install standalone 20/40 mesh gravel pack screen across perforations to arrest future sand ingress.",
                "Replace and recalibrate Gas Lift Valve (GLV) mandrels connected to GGS-2 manifold.",
            ],
            "risk_mitigation": "Equip wellhead with Class IV BOP and continuous H2S scrubbers during tripping.",
        }
    elif status == "warning":
        return {
            "title": "Hot Oil Paraffin Treatment & Water Shut-Off (WSO)",
            "urgency": "High Priority (Within 10 Days)",
            "urgency_badge": "warning",
            "estimated_cost_usd": 28000,
            "projected_flow_uplift_bopd": 45.0,
            "estimated_payback_days": 16,
            "action_items": [
                "Circulate 70 bbl heated lease crude (85°C) with xylene-based wax solvent to dissolve tubing deposition.",
                "Perform mechanical wireline scraper run to gauge tubing drift ID.",
                "Inject cross-linked polyacrylamide polymer gel plug into high water-cut lower perforations.",
                "Optimize gas lift injection rate from GGS compressor to restore stable drawdown.",
            ],
            "risk_mitigation": "Ensure wellhead return temperatures remain above 45°C to prevent re-solidification in flowlines.",
        }
    else:
        return {
            "title": "Continuous Gas Lift Tuning & Flowline Dosing (Geleki GGS)",
            "urgency": "Routine Asset Optimization",
            "urgency_badge": "healthy",
            "estimated_cost_usd": 7500,
            "projected_flow_uplift_bopd": 15.0,
            "estimated_payback_days": 12,
            "action_items": [
                "Calibrate gas lift injection pressure regulator to 820 psi from GGS header.",
                "Dose continuous pour-point depressant (PPD) and wax inhibitor at wellhead chemical injection skid.",
                "Sample effluent water at Geleki GGS separator to monitor residual water cut.",
            ],
            "risk_mitigation": "Monitor casing annulus pressure daily to prevent gas lock at compressor station.",
        }


def chat_with_well_agent(
    well: Dict[str, Any], user_message: str, language: str = "hinglish"
) -> Dict[str, Any]:
    """
    Main entry point for Geleki well contextual AI copilot.
    Attempts Gemini 2.5 Flash via google-genai; falls back gracefully to local expert.
    Strictly instructs Gemini to be concise (2-3 sentences max) in Hindi + English (Hinglish).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return query_local_petroleum_expert(well, user_message, language=language)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        context = build_well_context(well)

        lang_instruction = {
            "hinglish": "Speak in natural, conversational Hinglish (a fluid blend of Hindi and English code-switching as spoken by ONGC petroleum engineers in Assam, e.g. 'GLK-101 abhi warning state mein hai kyunki water cut 84% tak badh gaya hai... Er. R. K. Gogoi ne last workover supervise kiya tha. Immediate hot oil flush recommend karta hoon.').",
            "english": "Speak in crisp, professional, conversational English.",
            "hindi": "Speak in natural, fluent conversational Hindi (हिंदी).",
        }.get((language or "hinglish").lower(), "Speak in natural, conversational Hinglish.")

        prompt = f"""
You are WellPulse Voice Copilot, a senior ONGC petroleum engineer talking via live voice with a field engineer in the Geleki control room.
Wellhead Operational Data:
{context}

Engineer Query: "{user_message}"

CRITICAL VOICE CONVERSATION RULES:
1. MAXIMUM 2 TO 3 SENTENCES (35 to 45 words total). Keep it punchy, natural, and direct to the point. Never ramble.
2. NO RAW REPORT TEXT: Never recite document IDs, markdown tables, or bulleted lists out loud.
3. LANGUAGE REQUIREMENT: {lang_instruction}
4. Give the operational conclusion and immediate action first.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        recommendation = None
        user_lower = user_message.lower()
        if any(k in user_lower for k in ["recommend", "fix", "action", "upay", "solution"]) or well["status"] in ("warning", "failed"):
            recommendation = generate_structured_recommendation(well)

        return {
            "response": response.text.strip(),
            "recommendation": recommendation,
            "engine": "gemini-2.5-flash",
            "well_id": well["id"],
            "language": language,
        }
    except Exception as e:
        print(f"[!] Warning: Gemini API call failed ({e}). Falling back to Local Geleki Petroleum Expert.")
        result = query_local_petroleum_expert(well, user_message, language=language)
        result["note"] = f"Fallback active: {str(e)}"
        return result
