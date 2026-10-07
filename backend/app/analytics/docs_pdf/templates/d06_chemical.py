"""Template for D06: Chemical Treatment Log (IC-04 wax and IC-05 scale)."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import (
    Block,
    Bullets,
    Callout,
    DocSpec,
    H,
    KV,
    P,
    Signoff,
    Table,
)


def _procedure_and_safety(job_code: str) -> tuple[list[str], str]:
    if job_code == "WAX_HOTOIL":
        steps = [
            "Rig up hot oiler circulation unit to wellhead and perform pressure test on surface lines.",
            "Circulate heated fluid down tubing string and return through casing-tubing annulus.",
            "Continue thermal circulation to dissolve and displace paraffin wax accumulation.",
            "Displace conduit volume with clean fluid and divert returns to production separator.",
            "Bleed down surface equipment, rig down circulation lines, and restore well flow.",
        ]
        safety = (
            "Safety controls: High thermal burn risk and elevated circulation pressure. "
            "Station hot oiler upwind from wellhead. Maintain electrical bonding and grounding "
            "between mobile unit and wellhead to eliminate static ignition hazards. "
            "Clear non-essential personnel from high-pressure piping corridors."
        )
    elif job_code == "WAX_SOLVENT":
        steps = [
            "Spot chemical transport tanker and high-pressure pumping unit in designated location.",
            "Pressure test injection lines against closed wellhead master valve with clean water.",
            "Pump aromatic solvent batch into tubing string to cover the targeted wax deposition interval.",
            "Shut in well to facilitate chemical dissolution and soaking of stubborn paraffin deposits.",
            "Flow back dissolved solvent and mobilized wax mixture to dedicated field disposal tank.",
        ]
        safety = (
            "Safety controls: Volatile aromatic hydrocarbon solvents present severe flammability, "
            "vapor inhalation, and dermal exposure hazards. Mandatory organic vapor respirators "
            "and impervious chemical gloves. Position fire suppression equipment on standby and "
            "enforce strict elimination of all ignition sources."
        )
    elif job_code == "WAX_SCRAPE":
        steps = [
            "Rig up wireline unit, lubricator assembly, and mechanical paraffin scraper toolstring.",
            "Pressure test lubricator seals and equalize pressure with tubing head before opening master valve.",
            "Run mechanical scraper in progressive passes across the paraffin deposition zone.",
            "Retrieve wireline scraper toolstring to surface lubricator and inspect recovered wax debris.",
            "Flush loose wax cuttings through flowline to group gathering station.",
        ]
        safety = (
            "Safety controls: Wireline pressure containment and mechanical handling risks. "
            "Verify lubricator bleed-off valve operation and packing gland integrity. "
            "Monitor wireline tension continuously to prevent line breakage or tool hang-up against wax bridges."
        )
    elif job_code == "WAX_INHIBITOR":
        steps = [
            "Rig up chemical injection skid and connect high-pressure hose to wellhead injection port.",
            "Pump chemical pre-flush to condition conduit surfaces.",
            "Inject concentrated wax inhibitor chemical slug down tubing below formation breakdown pressure.",
            "Displace inhibitor solution into near-wellbore matrix with filtered aqueous overflush.",
            "Shut in well for designated chemical adsorption period before returning to continuous production.",
        ]
        safety = (
            "Safety controls: Pressurized chemical pumping and skin contact hazards. "
            "Monitor pump discharge pressure to avoid exceeding formation breakdown limits. "
            "Ensure emergency eyewash and chemical neutralization supplies are immediately accessible."
        )
    elif job_code == "WAX_HEATER":
        steps = [
            "Rig up service unit over wellhead and position downhole heater control console.",
            "Conduct electrical insulation resistance and continuity checks on heating cable.",
            "Run downhole electric heater assembly to depth adjacent to the wax precipitation zone.",
            "Pack off and seal electric cable at wellhead penetration hanger.",
            "Commission surface control panel, verify electrical grounding, and energize heating system.",
        ]
        safety = (
            "Safety controls: High-voltage electrical hazards and wellhead pressure seal integrity. "
            "Implement lockout and tagout procedures on surface electrical feed during cable termination. "
            "Verify wellhead feed-through packoff pressure rating."
        )
    elif job_code == "SCALE_ACID_BULLHEAD":
        steps = [
            "Rig up acid pump truck and acid-resistant discharge lines to wellhead injection manifold.",
            "Perform hydrostatic pressure test of treating lines prior to acid introduction.",
            "Bullhead inhibited acid solution down tubing string to dissolve carbonate mineral scale.",
            "Displace acid formulation with neutral aqueous overflush and allow controlled soaking contact time.",
            "Flow back spent acid reaction products to neutralization containment vessel for treatment.",
        ]
        safety = (
            "Safety controls: Severe corrosive chemical hazard and toxic vapor generation. "
            "Personnel must wear full acid splash suits, full face shields, and chemical gauntlets. "
            "Maintain neutralization solutions and emergency drench showers on location."
        )
    elif job_code == "SCALE_INHIBITOR":
        steps = [
            "Rig up chemical treatment unit and connect to wellhead bullhead connection.",
            "Pump chemical pre-flush spacer to prepare formation matrix and pipe surfaces.",
            "Squeeze scale inhibitor solution down tubing and penetrate into near-wellbore pore volume.",
            "Displace chemical pill with filtered water overflush to establish radial treatment barrier.",
            "Shut in well for chemical retention and adsorption onto formation mineral surfaces.",
            "Return well to production with controlled choke to observe residual inhibitor concentration.",
        ]
        safety = (
            "Safety controls: Pressurized chemical fluid injection and chemical handling hazards. "
            "Inspect line fittings and pressure pop-off safety valves before pumping. "
            "Enforce proper chemical personal protective equipment during chemical transfer and mixing."
        )
    else:
        steps = [
            "Rig up specialized mobile pumping equipment and connect to wellhead treating iron.",
            "Perform hydrostatic pressure integrity test on surface piping.",
            "Pump designated chemical treatment package downhole according to approved engineering procedure.",
            "Displace chemical volume and monitor wellhead pressure response.",
            "Return well to production lineup and verify normal fluid circulation to gathering facility.",
        ]
        safety = (
            "Safety controls: Comply with field safety protocols and permit to work provisions. "
            "Verify line pressure containment and enforce standard personal protective equipment throughout operations."
        )
    return steps, safety


def build(spec: DocSpec) -> list[Block]:
    summary_pairs = [
        ("Workover ID", "{workover_id}"),
        ("Job description", "{job_name}"),
        ("Catalogue job code", "{catalogue_job_code}"),
        ("Intervention class", "{intervention_class} ({ic_label})"),
        ("Execution start", "{start_date}"),
        ("Execution completion", "{end_date}"),
        ("Elapsed duration", "{calendar_days} calendar days"),
        ("Operational mode", "Rigless: {is_rigless}"),
        ("Primary equipment", "{equipment}"),
        ("Cost classification", "{cost_band}"),
        ("Operating procedure", "{sop_doc_id}"),
        ("Production formation", "{current_zone}"),
    ]
    if spec.has("rig_id") and not spec.is_("rig_id", "not recorded"):
        summary_pairs.extend([
            ("Assigned rig unit", "{rig_id}"),
            ("Recorded rig duration", "{rig_days} days"),
        ])
    else:
        summary_pairs.extend([
            ("Rig requirement", "{requires_rig}"),
            ("Estimated duration", "{est_days} days"),
        ])

    trigger_pairs = [
        ("Surveillance window", "{window_days} producing days"),
        ("Pre-job active days", "{pre_producing_days} days"),
        ("Pre-treatment THP", "{pre_thp_avg} ksc"),
        ("Pre-treatment WHT", "{pre_wht_avg} degC"),
        ("Pre-treatment oil rate", "{pre_oil_avg} BOPD"),
        ("Pre-treatment water cut", "{pre_wc_avg}"),
        ("Pre-treatment gas-oil ratio", "{pre_gor_avg} scf/bbl"),
        ("Pre-treatment liquid rate", "{pre_liquid_avg} BLPD"),
    ]

    if spec.is_("job_code", "JOB_WAX"):
        trigger_context = (
            "Paraffin deposition in the upper wellbore tubing and surface lines restricts flow area, "
            "causing progressive elevation in tubing head pressure and suppression of wellhead temperature. "
            "Wax precipitation is aggravated by ambient surface cooling across gathering headers."
        )
    elif spec.is_("job_code", "JOB_SCALE"):
        trigger_context = (
            "Mineral scale accumulation across tubing perfs and completion accessories restricts liquid influx, "
            "causing sudden productivity decline. Diagnostic surveillance indicates supersaturation and scaling "
            "tendency under producing temperatures and pressures."
        )
    else:
        trigger_context = (
            "Wellbore deposition restricts flow velocity and increases hydraulic backpressure. "
            "Routine surveillance triggers chemical intervention to clean the completion string."
        )

    cat_code = str(spec.raw.get("catalogue_job_code", ""))
    steps, safety_text = _procedure_and_safety(cat_code)

    results_pairs = [
        ("Pre-treatment oil rate", "{pre_oil_avg} BOPD"),
        ("Post-treatment oil rate", "{post_oil_avg} BOPD"),
        ("Oil rate change (delta)", "{delta_oil} BOPD"),
        ("Recorded net uplift", "{uplift_bopd} BOPD"),
        ("Pre-treatment water cut", "{pre_wc_avg}"),
        ("Post-treatment water cut", "{post_wc_avg}"),
        ("Water cut change (delta)", "{delta_wc}"),
        ("Overall job outcome", "{outcome}"),
        ("Pre-treatment THP", "{pre_thp_avg} ksc"),
        ("Post-treatment THP", "{post_thp_avg} ksc"),
        ("THP variance (delta)", "{delta_thp} ksc"),
        ("Tubing damage reset", "{damage_reset_frac}"),
        ("Pre-treatment WHT", "{pre_wht_avg} degC"),
        ("Post-treatment WHT", "{post_wht_avg} degC"),
        ("WHT variance (delta)", "{delta_wht} degC"),
        ("Run life post-job", "{run_life_days} days"),
        ("Pre-treatment GOR", "{pre_gor_avg} scf/bbl"),
        ("Post-treatment GOR", "{post_gor_avg} scf/bbl"),
    ]

    if spec.is_("outcome", "SUCCESS"):
        outcome_callout = Callout(
            "Treatment achieved successful outcome. Wellbore deposition was effectively cleared, "
            "restoring production rate and stabilizing flow parameters with positive uplift.",
            tone="success",
        )
    elif spec.is_("outcome", "PARTIAL"):
        outcome_callout = Callout(
            "Treatment achieved partial success. Temporary production improvement was recorded, "
            "though residual restriction or rapid deposition re-accumulation limits total recovery.",
            tone="warning",
        )
    elif spec.is_("outcome", "FAILED"):
        outcome_callout = Callout(
            "Treatment did not achieve expected production restoration. Restriction persists "
            "or flow impairment indicates mechanical obstruction requiring comprehensive workover.",
            tone="danger",
        )
    else:
        outcome_callout = Callout(
            "Treatment execution completed. Production parameters continue under field surveillance "
            "to assess long-term flow stability and cleanout response.",
            tone="info",
        )

    history_prose = (
        "Recorded prior chemical interventions in this class for well {well_id}: "
        "{n_prior_treatments} treatments."
    )
    if spec.has("days_since_last_treatment"):
        history_prose = (
            "Recorded prior chemical interventions in this class for well {well_id}: "
            "{n_prior_treatments} treatments. "
            "Interval elapsed since preceding treatment: {days_since_last_treatment} days."
        )

    n_priors = spec.raw.get("n_prior_treatments")
    has_prior_treatments = n_priors is not None and n_priors > 0

    if has_prior_treatments:
        recurrence_remark = (
            "Deposition recurrence confirms an ongoing tendency toward paraffin wax or mineral scale "
            "precipitation. Operating conditions favor persistent deposit accumulation, demonstrating "
            "that single batch cleanout treatments provide only temporary conduit clearance."
        )
    else:
        recurrence_remark = (
            "No prior chemical treatments are recorded in this class for this well. "
            "This event represents an isolated cleanout or initial baseline chemical application."
        )

    recs = [
        "Maintain daily surveillance of tubing head pressure and wellhead temperature at {facility_name} to detect early restriction symptoms.",
        "Monitor choke manifold and surface gathering lines for deposition buildup during regular maintenance rounds.",
    ]
    if has_prior_treatments:
        recs.append(
            "Due to repeated deposition history ({n_prior_treatments} prior interventions), transition from reactive "
            "batch cleanout to a continuous chemical inhibitor injection programme or scheduled slip-stream squeeze treatments."
        )
        recs.append(
            "Evaluate surface flowline insulation or heating at wellhead to prevent fluid cooling below wax appearance temperature."
        )
    else:
        recs.append(
            "Given the absence of prior deposition history, continue standard surveillance over subsequent quarters before committing capital to permanent chemical injection skids."
        )

    if spec.is_("job_code", "JOB_SCALE") or spec.is_("mechanism_code", "SCALE"):
        recs.append(
            "Collect produced water samples for laboratory scaling index determination and mineral saturation analysis across fluctuating water cut."
        )
    else:
        recs.append(
            "Coordinate periodic wireline drift runs to verify open tubing bore and prevent severe flow restriction."
        )

    blocks: list[Block] = [
        H("Treatment summary"),
        KV(summary_pairs, cols=2),
        H("Surveillance trigger and pre-treatment baseline"),
        P(
            "Candidate selection and surveillance trigger: {selection_evidence}. "
            "Pre-treatment baseline represents production surveillance across the "
            "{window_days}-day window preceding job mobilization."
        ),
        KV(trigger_pairs, cols=2),
        P(trigger_context),
        H("Treatment procedure and execution"),
        P("Execution summary for {job_name} ({catalogue_job_code}) conducted under {sop_doc_id}:"),
        Bullets(steps, numbered=True),
        H("Operational safety and hazard controls", level=2),
        P(safety_text, style="note"),
        H("Post-treatment results and production response"),
        KV(results_pairs, cols=2),
        outcome_callout,
        H("Intervention history and deposition recurrence"),
        P(history_prose),
        P(recurrence_remark),
        Table(
            "prior_treatments",
            [
                ("workover_id", "Workover ID"),
                ("start_date", "Start Date"),
                ("catalogue_job_code", "Job Code"),
                ("pre_job_oil_bopd", "Pre Oil (BOPD)"),
                ("post_job_oil_bopd", "Post Oil (BOPD)"),
                ("outcome", "Outcome"),
            ],
            title="Recorded prior intervention history",
            max_rows=6,
            empty_text="No prior chemical treatments recorded for this well.",
        ),
        H("Engineering recommendations"),
        Bullets(recs),
        Signoff(["Chemical Engineer", "Production Superintendent", "Asset Operations Manager"]),
    ]

    return blocks
