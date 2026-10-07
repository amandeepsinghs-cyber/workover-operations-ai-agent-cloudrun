"""
AI Conversational Agent & Prescriptive Recommendations Engine for Geleki Field (Assam, India).
Integrates Google Gemini 2.5 Flash with deep Geleki brownfield context (ONGC Assam Asset),
and includes a deterministic local petroleum engineering diagnostic fallback
tailored to Tipam/Barail sands, high water cut, paraffin wax choking, and continuous gas lift.
"""

import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

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
            f"- [{wo['date']}] {wo['type']} by {wo['contractor']} | Cost band: {wo['cost_band']} ({wo['rig_days']} rig-days) | "
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
        [f"{c['string']} to {c['depth_m']}m ({c['cement_class']})" if isinstance(c, dict) else str(c) for c in wcr.get("casing_policy", [])]
    )

    perfs = wcr.get("perforated_intervals", "")
    if isinstance(perfs, list):
        perf_text = ", ".join([f"{p.get('top_depth_m', '')}-{p.get('bottom_depth_m', '')}m ({p.get('formation', '')})" if isinstance(p, dict) else str(p) for p in perfs])
    else:
        perf_text = str(perfs)

    crude = wcr.get("crude_assay", {})
    ionic = lab.get("ionic_constituents_mg_l", {})
    scale = lab.get("scaling_tendency_analysis", {})

    status = well.get("status", "healthy")
    if status == "failed":
        diag_summary = (
            f"CRITICAL SHUTDOWN / TRIPPED (RED WELL):\n"
            f"- Well {well['name']} tripped offline with production dropping to 0 BOPD.\n"
            f"- Tubing head pressure collapsed to {current['tubing_pressure_psi']} psi while casing pressure built up to {current['casing_pressure_psi']} psi.\n"
            f"- Root Cause: Gas lift operating valve plugged/failed and severe formation sand bridging inside the 2-7/8\" tubing string.\n"
            f"- Immediate Action: Well is shut-in on surface choke (0%). Mobilize ONGC workover rig from Nazira base for coiled tubing nitrogen sand cleanout and valve replacement."
        )
    elif status == "warning":
        diag_summary = (
            f"WARNING / ATTENTION NEEDED (AMBER WELL):\n"
            f"- Well {well['name']} is flowing sub-optimally at {current['oil_bopd']} BOPD.\n"
            f"- Water cut surged to {current['water_cut_pct']}% alongside heavy paraffin wax deposition restricting tubing drift.\n"
            f"- Root Cause: Water breakthrough in lower perforations and wax crystallization below cloud point.\n"
            f"- Immediate Action: Hot oil solvent wash and polymer gel water shut-off (WSO) squeeze required."
        )
    else:
        diag_summary = (
            f"OPTIMAL FLOWING (GREEN WELL):\n"
            f"- Well {well['name']} is producing stably at {current['oil_bopd']} BOPD with {current['water_cut_pct']}% water cut.\n"
            f"- Tubing pressure is healthy at {current['tubing_pressure_psi']} psi and gas lift casing injection is {current['casing_pressure_psi']} psi."
        )

    context = f"""
=== {str(well.get('field', 'Geleki')).upper()} FIELD ASSET PROFILE: {well['name']} ({well['id']}) ===
- Operator: ONGC (Assam Asset, Sivasagar)
- Field Type: Mature Brownfield
- Basin: Assam-Arakan Basin | Formation: {well['formation']}
- Artificial Lift: {well['lift_type']} (Connected to {well.get('field', 'Geleki')} Group Gathering Station {well.get('cluster_id') or ''})
- Location Coordinates: Lat {well['coordinates']['lat']}°N, Lng {well['coordinates']['lng']}°E

=== DIAGNOSTIC STATUS & FAILURE SUMMARY ===
{diag_summary}

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
- Workover Cost-Band Mix: {summary.get('cost_band_mix', {})} | Total Rig-Days: {summary.get('total_rig_days', 0)}

=== CHRONOLOGICAL WORKOVER & INTERVENTION LOG ===
{wo_text}

=== ENGINEERING REPORTS DOSSIER ===
1. WELL COMPLETION REPORT [Ref: {wcr.get('report_id', 'N/A')}]
   - Spud Date: {wcr.get('spud_date', 'N/A')} | Completion: {wcr.get('completion_date', 'N/A')}
   - Total Depth: {wcr.get('total_depth_m', 'N/A')}m | Target: {wcr.get('target_formation', 'N/A')}
   - Casing Policy: {casing_text}
   - Perforations: {perf_text}
   - Crude Assay: API Gravity {crude.get('api_gravity', 'N/A')}°, Wax Content {crude.get('wax_content_pct', crude.get('paraffin_wax_pct', 'N/A'))}%, Pour Point {crude.get('pour_point_celsius', crude.get('pour_point_c', 'N/A'))}°C

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
    total_rig_days = round(sum(w.get("rig_days", 0.0) for w in workovers), 1)
    band_mix = summary_band_mix(workovers)

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
                    f"Job {last_wo['cost_band']} cost band ki thi ({last_wo['rig_days']} rig-days) aur execution ke baad production {flow_gain} BOPD badh gaya."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} पर अंतिम कार्य {last_wo['date']} को {last_wo['type']} था। "
                    f"यह {last_wo['cost_band']} कॉस्ट बैंड का काम था ({last_wo['rig_days']} रिग-दिवस) और उत्पादन में {flow_gain} बीओपीडी का इजाफा हुआ।"
                )
            else:
                text_response = (
                    f"The most recent intervention on {well['name']} was a {last_wo['type']} on {last_wo['date']} by {last_wo['contractor']}. "
                    f"It was a {last_wo['cost_band']} cost-band job ({last_wo['rig_days']} rig-days) and delivered a {flow_gain} BOPD net production change."
                )
        else:
            text_response = (
                f"{well['name']} pe pichle 24 mahino mein koi major workover logged nahi hai."
                if lang == "hinglish"
                else f"No major workovers have been logged on {well['name']} in the past 24 months."
            )

    # 6. What happened / Why decline / failed / warning / status
    elif any(k in user_lower for k in [
        "what happened", "happened", "kya hua", "what is wrong", "what's wrong",
        "why", "decline", "drop", "fail", "tripped", "offline", "shut in", "shut-in",
        "red", "problem", "issue", "trouble", "status", "kyu", "gir gaya", "kam kyu", "kharab"
    ]):
        if status == "failed":
            if lang == "hinglish":
                text_response = (
                    f"{well['name']} abhi offline aur shut-in hai kyunki continuous gas lift valve fail ho gaya hai aur tubing mein sand bridge ban gaya hai, jisse production 0 BOPD aur tubing pressure {current['tubing_pressure_psi']} psi ho gaya hai. "
                    f"Nazira base se ONGC workover rig bula ke coiled tubing cleanout aur valve replace karna padega."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} शटडाउन स्थिति में है क्योंकि गैस लिफ्ट वॉल्व खराब होने और सैंड ब्रिजिंग से ट्यूबिंग प्रेशर {current['tubing_pressure_psi']} पीएसआई तक गिर गया है। "
                    f"उत्पादन पूरी तरह शून्य है और वर्कओवर रिग द्वारा कॉइल्ड ट्यूबिंग क्लीनआउट की आवश्यकता है।"
                )
            else:
                text_response = (
                    f"{well['name']} tripped offline because its continuous gas lift valve failed and heavy formation sand bridged the production tubing, causing oil flow to drop to 0 BOPD and tubing pressure to collapse to {current['tubing_pressure_psi']} psi. "
                    f"The well is currently shut-in while awaiting an ONGC workover rig from Nazira base for coiled-tubing cleanout and valve replacement."
                )
        elif status == "warning":
            if lang == "hinglish":
                text_response = (
                    f"{well['name']} warning status pe hai kyunki water cut {current['water_cut_pct']}% tak badh gaya hai aur wax deposition ki wajah se tubing choke ho rahi hai, jisse production girkar {current['oil_bopd']} BOPD reh gaya hai. "
                    f"Immediate hot oil xylene treatment aur polymer gel water shut-off squeeze recommend karta hoon."
                )
            elif lang == "hindi":
                text_response = (
                    f"{well['name']} वार्निंग स्थिति में है क्योंकि वाटर कट {current['water_cut_pct']}% पहुंच गया है और वैक्स से ट्यूबिंग चोक हो रही है। "
                    f"उत्पादन घटकर {current['oil_bopd']} बीओपीडी रह गया है; हॉट ऑयल फ्लश और वाटर शट-ऑफ की तुरंत जरूरत है।"
                )
            else:
                text_response = (
                    f"{well['name']} is flagged under warning status because water cut has surged to {current['water_cut_pct']}% and heavy paraffin wax deposition is choking the production tubing, reducing flow to {current['oil_bopd']} BOPD. "
                    f"An immediate hot oil solvent wash and polymer gel water shut-off squeeze are required to restore normal productivity."
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
                    f"{well['name']} is flowing stably at {current['oil_bopd']} BOPD with {current['water_cut_pct']}% water cut. "
                    f"Continuous gas lift injection remains optimal at {current['casing_pressure_psi']} psi and all wellhead pressures are normal."
                )

    # 7. Cost / Spend
    elif any(k in user_lower for k in ["cost", "spend", "budget", "kharcha", "rupaye", "dollars"]):
        last_name = last_wo["type"] if last_wo else "routine maintenance"
        if lang == "hinglish":
            text_response = (
                f"{well['name']} pe {len(workovers)} operations hue hain, cost-band mix {band_mix} aur kul {total_rig_days} rig-days. "
                f"Sabse recent job {last_name} thi."
            )
        elif lang == "hindi":
            text_response = (
                f"{well['name']} पर {len(workovers)} ऑपरेशन्स हुए हैं, कॉस्ट-बैंड मिश्रण {band_mix} और कुल {total_rig_days} रिग-दिवस। "
                f"सबसे हालिया काम {last_name} था।"
            )
        else:
            text_response = (
                f"{well['name']} has {len(workovers)} recorded interventions with a cost-band mix of {band_mix} "
                f"and {total_rig_days} total rig-days; the most recent was the {last_name}."
            )

    # 8. General Operational Status & Query Handling
    else:
        status_label = "Optimal" if status == "healthy" else ("Needs Attention" if status == "warning" else "Critical / Failed")
        last_wo_summary = f"Last workover was {last_wo['type']} on {last_wo['date']} (+{last_wo['flow_delta_bopd']} BOPD)." if last_wo else "No major workovers in last 24 months."
        last_wo_hi = f"Pichla workover {last_wo['type']} ({last_wo['date']}) tha (+{last_wo['flow_delta_bopd']} BOPD gain)." if last_wo else "Pichle 24 mahino mein koi major workover nahi hua."

        if lang == "hinglish":
            text_response = (
                f"{well['name']} ({well['formation']}) abhi {current['oil_bopd']} BOPD oil aur {current['gas_mcfd']} MCFD gas par chal raha hai ({status_label}). "
                f"Water cut {current['water_cut_pct']}% aur tubing pressure {current['tubing_pressure_psi']} psi hai. {last_wo_hi}"
            )
        elif lang == "hindi":
            text_response = (
                f"{well['name']} ({well['formation']}) वर्तमान में {current['oil_bopd']} बीओपीडी तेल और {current['gas_mcfd']} एमसीएफडी गैस दे रहा है ({status_label})। "
                f"वाटर कट {current['water_cut_pct']}% और ट्यूबिंग प्रेशर {current['tubing_pressure_psi']} पीएसआई है। अंतिम वर्कओवर {last_wo['date'] if last_wo else 'हाल ही में'} हुआ था।"
            )
        else:
            text_response = (
                f"{well['name']} ({well['formation']}) is producing {current['oil_bopd']} BOPD oil and {current['gas_mcfd']} MCFD gas under {status_label} status. "
                f"Current water cut is {current['water_cut_pct']}% at {current['tubing_pressure_psi']} psi tubing head pressure. {last_wo_summary}"
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


def summary_band_mix(workovers: List[Dict[str, Any]]) -> str:
    mix = {"LOW": 0, "MED": 0, "HIGH": 0}
    for w in workovers:
        mix[w.get("cost_band", "MED")] = mix.get(w.get("cost_band", "MED"), 0) + 1
    return " / ".join(f"{k} {v}" for k, v in mix.items())


_BAND_ORDER = {"LOW": 0, "MED": 1, "HIGH": 2}


def _catalogue_effort(job_codes: tuple) -> Dict[str, Any]:
    """Cost band (highest of the jobs) and rig-days (sum of est_days of rig jobs) from job_catalogue (D-1)."""
    from app.data_access.repository import get_repository

    repo = get_repository()
    jobs = [j for j in (repo.catalogue_job(c) for c in job_codes) if j is not None]
    band = max((str(j["cost_band"]) for j in jobs), key=lambda b: _BAND_ORDER.get(b, 1), default="MED")
    rig_days = round(sum(float(j["est_days"]) for j in jobs if bool(j["requires_rig"])), 1)
    return {"cost_band": band, "rig_days": rig_days, "catalogue_job_codes": list(job_codes)}


def generate_structured_recommendation(well: Dict[str, Any]) -> Dict[str, Any]:
    """Generates structured engineering recommendations for Geleki brownfield wells."""
    status = well["status"]
    formation = well["formation"]

    if status == "failed":
        return {
            "title": f"Mobilize ONGC Workover Rig & Sand Cleanout ({formation})",
            "urgency": "Immediate (Within 48 hrs)",
            "urgency_badge": "critical",
            **_catalogue_effort(('SAND_CLEANOUT', 'GLV_REPLACE')),
            "projected_flow_uplift_bopd": 85.0,
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
            **_catalogue_effort(('WAX_HOTOIL', 'POLYMER_GEL')),
            "projected_flow_uplift_bopd": 45.0,
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
            **_catalogue_effort(('LIFT_OPTIM',)),
            "projected_flow_uplift_bopd": 15.0,
            "action_items": [
                "Calibrate gas lift injection pressure regulator to 820 psi from GGS header.",
                "Dose continuous pour-point depressant (PPD) and wax inhibitor at wellhead chemical injection skid.",
                "Sample effluent water at Geleki GGS separator to monitor residual water cut.",
            ],
            "risk_mitigation": "Monitor casing annulus pressure daily to prevent gas lock at compressor station.",
        }


def call_gemini_api(
    prompt: str,
    audio_bytes: Optional[bytes] = None,
    mime_type: str = "audio/webm",
) -> str:
    """
    Calls Gemini 3.8 Flash using Google Generative Language API.
    Supports both text prompts and inline multimodal audio bytes.
    """
    import base64
    import requests

    api_key = os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

    parts: List[Dict[str, Any]] = [{"text": prompt}]
    if audio_bytes:
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": audio_b64,
            }
        })

    payload = {
        "contents": [{
            "parts": parts,
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    resp = requests.post(url, json=payload, timeout=25)
    if not resp.ok:
        raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"No response candidates from Gemini: {data}")

    parts_resp = candidates[0].get("content", {}).get("parts", [])
    for p in parts_resp:
        if "text" in p:
            return p["text"].strip()
    raise ValueError("No text in Gemini response parts")


def chat_with_well_agent(
    well: Dict[str, Any], user_message: str, language: str = "hinglish"
) -> Dict[str, Any]:
    """
    Main entry point for Geleki well contextual AI copilot powered by Gemini 3.8 Flash.
    Strictly instructs Gemini to be concise (2-3 sentences max) in Hindi + English (Hinglish) or English.
    """
    try:
        context = build_well_context(well)
        lang_instruction = {
            "hinglish": (
                "Speak in natural, conversational Hinglish (a fluid blend of Hindi and English as spoken by ONGC petroleum engineers in Assam, "
                "e.g. 'GK-129 abhi warning state mein hai kyunki water cut 84% tak badh gaya hai... Er. R. K. Gogoi ne last workover mein 1,450m pe wax bridge clean kiya tha. "
                "Immediate hot oil flush recommend karta hoon.'). Keep tone direct, collegial, and authoritative."
            ),
            "english": "Speak in crisp, professional, operational petroleum engineering English.",
            "hindi": "Speak in clean, natural, professional Hindi in proper Devanagari script (स्पष्ट एवं शुद्ध देवनागरी हिंदी). Write smoothly and clearly in Devanagari.",
        }.get((language or "hinglish").lower(), "Speak in natural, conversational Hinglish.")

        prompt = f"""You are WellPulse Copilot, a senior ONGC petroleum and reservoir engineer in the {well.get('field', 'Geleki')} field control room (Assam Asset, Sivasagar).
You are answering a query from a field workover engineer at the wellsite regarding {well['name']}.

Asset Context & Engineering Dossier for {well['name']}:
{context}

Field Engineer's Question: "{user_message}"

CRITICAL VOICE & CHAT RULES:
1. CONCISENESS: EXACTLY 2 TO 3 SENTENCES (35 to 50 words maximum). Answer the specific question asked directly, grounded in {well['name']}'s telemetry, workover history, or technical reports.
2. NO SCRIPT READING: Never recite document numbers, markdown headers, or raw bullet lists.
3. LANGUAGE: {lang_instruction}
4. FACTUALITY: Ground your response strictly in {well['name']}'s specific telemetry, historical workovers, or the 4 engineering reports (WCR, Daily Shift Log, BHP Survey, Water/Scale Lab Assay)."""

        reply_text = call_gemini_api(prompt)

        recommendation = None
        user_lower = user_message.lower()
        if any(k in user_lower for k in ["recommend", "fix", "action", "upay", "solution", "kya karein"]) or well["status"] in ("warning", "failed"):
            recommendation = generate_structured_recommendation(well)

        return {
            "response": reply_text,
            "recommendation": recommendation,
            "engine": "gemini-3.8-flash",
            "well_id": well["id"],
            "language": language,
        }
    except Exception as e:
        print(f"[!] Warning: Gemini API call failed ({e}). Falling back to Local Geleki Petroleum Expert.")
        result = query_local_petroleum_expert(well, user_message, language=language)
        result["note"] = f"Fallback active: {str(e)}"
        return result


def chat_with_well_agent_audio(
    well: Dict[str, Any],
    audio_bytes: bytes,
    mime_type: str = "audio/webm",
    language: str = "english",
) -> Dict[str, Any]:
    """
    Processes raw voice audio input using Gemini 3.8 Flash multimodal engine.
    Listens directly to the audio recording, understands technical oilfield terminology,
    and returns both the user transcript and a crisp 2-sentence response.
    """
    try:
        context = build_well_context(well)
        lang_instruction = {
            "hinglish": (
                "Speak in natural, conversational Hinglish (a fluid blend of Hindi and English as spoken by ONGC petroleum engineers in Assam). "
                "Keep tone direct, collegial, and authoritative."
            ),
            "english": "Speak in crisp, professional, operational petroleum engineering English.",
            "hindi": "Speak in clean, natural, professional Hindi in proper Devanagari script (स्पष्ट एवं शुद्ध देवनागरी हिंदी). Write smoothly and clearly in Devanagari.",
        }.get((language or "english").lower(), "Speak in crisp, professional, operational petroleum engineering English.")

        prompt = f"""You are WellPulse Voice Copilot, a senior ONGC petroleum and reservoir engineer in the {well.get('field', 'Geleki')} field control room (Assam Asset, Sivasagar).
You are listening to an audio recording sent over the two-way field radio from a workover engineer at the wellsite regarding {well['name']}.

Asset Context & Engineering Dossier for {well['name']}:
{context}

CRITICAL RULES:
1. Listen carefully to what the field engineer asked or stated in the audio clip.
2. In your response, provide EXACTLY 2 TO 3 SENTENCES (35 to 50 words maximum) addressing their question directly.
3. If the engineer asks what happened to this well, and the well is tripped/failed (red well), state that it tripped offline due to failed gas lift valve and sand bridging in the tubing, with tubing pressure collapsed, and that a workover rig cleanout is required.
4. Language: {lang_instruction}
5. Format your output strictly as valid JSON:
{{"user_transcript": "<transcription of what was said in the audio>", "response": "<your 2-3 sentence answer>"}}"""

        reply_raw = call_gemini_api(prompt, audio_bytes=audio_bytes, mime_type=mime_type)

        user_transcript = "Spoken audio query"
        agent_response = reply_raw
        if "{" in reply_raw and "}" in reply_raw:
            try:
                start = reply_raw.index("{")
                end = reply_raw.rindex("}") + 1
                parsed = json.loads(reply_raw[start:end])
                user_transcript = parsed.get("user_transcript", user_transcript)
                agent_response = parsed.get("response", agent_response)
            except Exception:
                pass

        recommendation = None
        if well["status"] in ("warning", "failed") or any(k in agent_response.lower() for k in ["recommend", "cleanout", "workover"]):
            recommendation = generate_structured_recommendation(well)

        return {
            "user_transcript": user_transcript,
            "response": agent_response,
            "recommendation": recommendation,
            "engine": "gemini-3.8-flash-audio",
            "well_id": well["id"],
            "language": language,
        }
    except Exception as e:
        print(f"[!] Warning: Gemini Audio API call failed ({e}). Falling back to Local Geleki Petroleum Expert.")
        default_q = "What happened to this well?"
        result = query_local_petroleum_expert(well, default_q, language=language)
        return {
            "user_transcript": "Voice query: What happened to this well?",
            "response": result["response"],
            "recommendation": result.get("recommendation"),
            "engine": "local-geleki-petroleum-expert-v1",
            "well_id": well["id"],
            "language": language,
            "note": f"Audio fallback active: {str(e)}",
        }

