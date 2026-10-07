"""Template for D03: Daily Workover Report (DWR).

One report per rig day. Compact one-page layout.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.analytics.docs_pdf.ir import Callout, H, KV, P, Signoff, Table

if TYPE_CHECKING:
    from app.analytics.docs_pdf.ir import Block, DocSpec

OPERATIONS_SUMMARY: dict[str, dict[str, str]] = {
    "RIG_UP": {
        "WAX": (
            "Spotted workover unit and auxiliary equipment on location. Held pre-job toolbox meeting with crew. "
            "Killed well with treated brine and hot fluid. Nippled down Christmas tree, nippled up blowout preventer "
            "stack and pressure tested rams. Prepared scraping assembly and wireline tools for paraffin clearing."
        ),
        "MECHANICAL": (
            "Spotted workover unit and equipment packages on site. Conducted safety briefing covering well control. "
            "Killed well with conditioned brine. Nippled down production tree, nippled up blowout preventer stack and "
            "tested rams. Unseated pump and prepared to pull rod string and completion tubing."
        ),
        "DEPOSITION": (
            "Rigged up workover unit, circulation pump and surface tanks. Conducted safety meeting on wellbore pressure. "
            "Bullheaded kill brine into wellbore. Nippled down Christmas tree, installed blowout preventer stack and "
            "function tested rams. Made up cleanout string and prepared sand bailing assembly."
        ),
        "INFLOW": (
            "Moved in and rigged up workover unit. Held toolbox safety briefing with rig crew. Circulated kill brine to "
            "secure well control. Nippled down production tree, nippled up blowout preventer and tested control valves. "
            "Made up workstring and prepared wellbore for interval stimulation."
        ),
        "WATER_CONTROL": (
            "Spotted and rigged up workover unit and high-pressure pumping spreads. Held pre-job safety meeting on pressure "
            "lines. Secured well with heavy kill brine. Nippled down Christmas tree, rigged up blowout preventer stack "
            "and functioned rams. Prepared retrievable bridge plug and squeeze assembly."
        ),
        "GAS_LIFT": (
            "Positioned workover unit and slickline equipment on location. Held safety meeting on pressurized gas safety. "
            "Closed wing valves, equalized casing pressure and circulated kill fluid. Nippled down tree, nippled up "
            "blowout preventer and tested rams. Prepared retrieval tools for gas lift valves."
        ),
        "TERMINAL": (
            "Mobilised workover rig and cementing spreads to site. Conducted site safety briefing and hazard review for "
            "permanent abandonment. Bullheaded kill fluid to secure well. Nippled down wellhead, installed blowout "
            "preventer stack and tested rams. Prepared workstring for mechanical plug setting."
        ),
    },
    "MAIN": {
        "WAX": (
            "Commenced wax remediation operations. Ran mechanical scrapers and wireline cutters through tubing string. "
            "Circulated hot fluid down the annulus to dissolve heavy paraffin deposits. Recovered returns across shaker "
            "screens and inspected wax samples. Continued scraping passes until hole gauge was verified."
        ),
        "MECHANICAL": (
            "Carried out main mechanical repairs. Pulled damaged completion string to surface, inspecting tubular joints "
            "and rods for mechanical wear, parting, or corrosion. Made up replacement string and downhole assembly. Ran "
            "string in hole, seated pump assembly, and pressure tested completion string."
        ),
        "DEPOSITION": (
            "Carried out cleanout operations across the completion interval. Ran wash pipe and bailer assembly to tag "
            "fill depth. Circulated conditioned fluid to flush out sand and fines to surface pits. Monitored returns for "
            "solid content until returns circulated clean."
        ),
        "INFLOW": (
            "Conducted wellbore inflow enhancement operations. Ran perforation workstring to target depth and verified "
            "correlation. Performed shooting and stimulation across designated reservoir intervals. Observed wellhead "
            "pressure response and monitored fluid intake."
        ),
        "WATER_CONTROL": (
            "Executed water shut-off and zonal isolation operations. Set mechanical isolation packer above target zone. "
            "Pumped cement slurry and chemical squeeze fluid into high water-cut perforations. Monitored squeeze "
            "hesitation pressure and held shut-in pressure for curing."
        ),
        "GAS_LIFT": (
            "Conducted gas-lift system maintenance and valve changeout. Ran wireline kickover tools into mandrels. "
            "Retrieved worn gas lift valves and inspected check seats. Redressed and latched replacement valves into "
            "position. Tested gas injection through annulus to confirm operation."
        ),
        "TERMINAL": (
            "Conducted permanent plug and abandonment operations. Set cast iron bridge plug above perforations. Mixed "
            "and spotted balanced cement plugs across open zones. Tagged cement top with workstring and verified plug "
            "depth and integrity with weight and pressure tests."
        ),
    },
    "RIG_DOWN": {
        "WAX": (
            "Completed scraping passes and circulated well clean. Pulled scraping assembly from hole and laid down "
            "workstring. Nippled down blowout preventer stack and nippled up production Christmas tree. Rigged down "
            "workover unit and fluid circulation tanks. Handed over well to production operations."
        ),
        "MECHANICAL": (
            "Completed installation of replacement downhole string. Seated and tested pump and polished rod. Nippled down "
            "blowout preventer stack and re-installed Christmas tree. Rigged down workover mast and auxiliary equipment. "
            "Cleared location and handed well over to field production team."
        ),
        "DEPOSITION": (
            "Finished bailing and cleanout passes with clean returns. Pulled cleanout string and laid down wash pipe. "
            "Nippled down blowout preventer, installed production tree, and tested wellhead seals. Rigged down workover "
            "rig. Restored location and handed well over to production crew."
        ),
        "INFLOW": (
            "Retrieved stimulation assembly and workstring from wellbore. Flow-checked well and verified wellbore control. "
            "Nippled down blowout preventer stack, nippled up production tree, and tested valve seals. Rigged down "
            "workover unit and released rig spreads. Handed over well for flow testing."
        ),
        "WATER_CONTROL": (
            "Drilled out hard cement and pressure tested squeeze interval for shut-off integrity. Pulled drilling string "
            "and laid down tubulars. Nippled down blowout preventer and installed production tree. Rigged down workover "
            "unit, cleaned location, and handed well over to reservoir engineers."
        ),
        "GAS_LIFT": (
            "Confirmed all gas-lift valves seated and tested. Laid down lubricator and slickline equipment. Nippled down "
            "blowout preventer stack and reinstated Christmas tree. Rigged down workover unit and service spreads. "
            "Handed over well to installation team for gas kick-off."
        ),
        "TERMINAL": (
            "Cut and retrieved upper casing string per abandonment procedure. Spotted surface cement plug to surface "
            "wellhead. Cut casing stubs below cellar depth and welded steel abandonment cap with well identification "
            "marker. Rigged down workover unit and cleared site."
        ),
    },
    "SINGLE_DAY": {
        "WAX": (
            "Mobilised pulling unit and crew to location. Held safety meeting. Killed well and rigged up pressure control "
            "equipment. Ran mechanical scraper to clear wax deposits. Circulated well clean, nippled down blowout "
            "preventer, reinstated tree, rigged down unit, and returned well to production."
        ),
        "MECHANICAL": (
            "Mobilised pulling unit and crew to location. Held safety meeting. Killed well and rigged up pressure control "
            "equipment. Pulled parted rod string or defective valve, ran replacement assembly, seated pump, nippled down "
            "blowout preventer, reinstated Christmas tree, rigged down unit, and handed well over to production."
        ),
        "DEPOSITION": (
            "Mobilised pulling unit to site. Held toolbox safety briefing. Killed well and installed blowout preventer. "
            "Ran bailer and cleared sand fill across perforations. Circulated well clean, installed Christmas tree, "
            "rigged down unit, and handed well over to field crew."
        ),
        "INFLOW": (
            "Mobilised unit to location. Conducted safety talk. Secured well and installed pressure control equipment. "
            "Ran workstring, executed targeted interval treatment, circulated wellbore, reinstated wellhead, rigged down "
            "unit, and released well for monitoring."
        ),
        "WATER_CONTROL": (
            "Mobilised workover equipment to location. Held pre-job meeting. Secured well with kill brine and rigged up "
            "blowout preventer. Set temporary bridge plug or isolation tool, performed integrity check, reinstated "
            "production tree, rigged down equipment, and handed well over."
        ),
        "GAS_LIFT": (
            "Mobilised slickline unit to well site. Held safety briefing on gas handling. Equalized well pressures, ran "
            "wireline tools, retrieved and replaced damaged gas lift valves, verified latching, rigged down unit, and "
            "handed well over for gas lift resumption."
        ),
        "TERMINAL": (
            "Mobilised pulling unit to location. Held safety briefing. Killed well, set surface plug, verified pressure "
            "integrity, cut wellhead stubs, welded abandonment plate, rigged down unit, and completed site handover."
        ),
    },
}

DEFAULT_OPERATIONS_SUMMARY: dict[str, str] = {
    "RIG_UP": (
        "Spotted workover unit and auxiliary equipment on site. Held pre-job safety meeting with rig crew. "
        "Secured well with treated brine kill fluid. Nippled down Christmas tree, nippled up blowout preventer stack "
        "and pressure tested rams. Prepared workstring for downhole operations."
    ),
    "MAIN": (
        "Executed main intervention program. Ran workstring in hole, performed scheduled downhole servicing, and "
        "circulated wellbore fluids. Inspected retrieved components at surface and verified mechanical integrity "
        "before preparing final completion assembly."
    ),
    "RIG_DOWN": (
        "Concluded downhole operations and circulated well clean. Laid down workstring and auxiliary tools. "
        "Nippled down blowout preventer stack, installed Christmas tree, and pressure tested seals. Rigged down "
        "workover unit and handed well over to production operations."
    ),
    "SINGLE_DAY": (
        "Mobilised pulling unit to location. Held comprehensive safety meeting. Killed well and rigged up pressure "
        "control equipment. Executed scheduled intervention tasks, verified downhole integrity, reinstated Christmas "
        "tree, rigged down unit, and handed well over to production operations."
    ),
}

NEXT_DAY_PLAN_WITH_SOP: dict[str, str] = {
    "RIG_UP": (
        "Commence main intervention program in accordance with standard operating procedure {sop_doc_id}. "
        "Pull existing completion string, inspect retrieved tubulars, and make up scheduled downhole tool assembly."
    ),
    "MAIN": (
        "Continue scheduled intervention operations per standard operating procedure {sop_doc_id}. Complete downhole "
        "servicing, verify pressure integrity, and prepare completion string for running."
    ),
    "RIG_DOWN": (
        "Complete rig down of workover mast and auxiliary packages. Demobilise crew and equipment from site. "
        "Hand over well to field production team per standard operating procedure {sop_doc_id}."
    ),
    "SINGLE_DAY": (
        "Complete site clearance and hand over well to field production operations in accordance with standard "
        "operating procedure {sop_doc_id}. Monitor wellhead pressures and resume production."
    ),
}

NEXT_DAY_PLAN_WITHOUT_SOP: dict[str, str] = {
    "RIG_UP": (
        "Commence main intervention program in accordance with approved well program. Pull existing completion "
        "string, inspect retrieved tubulars, and make up scheduled downhole tool assembly."
    ),
    "MAIN": (
        "Continue scheduled intervention operations per approved program. Complete downhole servicing, verify "
        "pressure integrity, and prepare completion string for running."
    ),
    "RIG_DOWN": (
        "Complete rig down of workover mast and auxiliary packages. Demobilise crew and equipment from site. "
        "Hand over well to field production team per standard field handover procedures."
    ),
    "SINGLE_DAY": (
        "Complete site clearance and hand over well to field production operations in accordance with standard "
        "procedures. Monitor wellhead pressures and resume production."
    ),
}

DEFAULT_NEXT_DAY_PLAN_WITH_SOP = (
    "Continue scheduled workover operations in accordance with standard operating procedure {sop_doc_id}. "
    "Execute planned work program and maintain well control."
)

DEFAULT_NEXT_DAY_PLAN_WITHOUT_SOP = (
    "Continue scheduled workover operations in accordance with approved well program. "
    "Execute planned work program and maintain well control."
)


def build(spec: DocSpec) -> list[Block]:
    header_pairs = [
        ("Report date", "{report_date}"),
        ("Rig day", "{day_no} of {total_days}"),
        ("Days remaining", "{days_remaining}"),
        ("Rig", "{rig_id}"),
        ("Workover", "{workover_id}"),
        ("Job name", "{job_name}"),
        ("Job code", "{catalogue_job_code}"),
        ("Intervention class", "{intervention_class}"),
        ("Catalogue estimate (days)", "{est_days}"),
        ("Well status", "{well_status_today}"),
    ]

    phase = str(spec.raw.get("phase_code") or "MAIN")
    category = str(spec.raw.get("job_category") or "")
    phase_dict = OPERATIONS_SUMMARY.get(phase, OPERATIONS_SUMMARY["MAIN"])
    summary_text = phase_dict.get(category, DEFAULT_OPERATIONS_SUMMARY.get(phase, DEFAULT_OPERATIONS_SUMMARY["MAIN"]))

    depth_pairs = [
        ("Pump setting depth (m MD)", "{pump_setting_depth_m}"),
        ("Perforation top (m MD)", "{perf_top_m}"),
        ("Artificial lift type", "{lift_type}"),
    ]

    blocks: list[Block] = [
        KV(header_pairs, cols=2, title="Daily operational status"),
        H("Operations summary", level=2),
        P(summary_text),
        KV(depth_pairs, cols=3, title="Wellbore depth references"),
        Table(
            "events_today",
            [
                ("event_type", "Event type"),
                ("factor_class", "Factor class"),
                ("responsible_function", "Responsible function"),
            ],
            title="Operational events and non-productive time",
            empty_text="No non-productive time or operational events recorded for this day.",
        ),
    ]

    if spec.is_("over_plan", "Yes"):
        blocks.append(
            Callout(
                "Operations have exceeded the catalogue baseline estimate of {est_days} days. "
                "Current cumulative rig duration has reached day {day_no} of {total_days}. "
                "Continued intervention approved under operational review.",
                tone="warning",
            )
        )

    blocks.append(H("Health, safety and environment", level=2))
    blocks.append(
        P(
            "Prior to commencing operations, a safety toolbox meeting was conducted with the rig crew covering "
            "job hazards, personal protective equipment, and stop-work authority. Valid work permits and site safety "
            "checks were verified. No HSE incident was recorded in the source tables for this day."
        )
    )

    if spec.has("sop_doc_id"):
        plan_text = NEXT_DAY_PLAN_WITH_SOP.get(phase, DEFAULT_NEXT_DAY_PLAN_WITH_SOP)
    else:
        plan_text = NEXT_DAY_PLAN_WITHOUT_SOP.get(phase, DEFAULT_NEXT_DAY_PLAN_WITHOUT_SOP)

    blocks.append(H("Plan for next day", level=2))
    blocks.append(P(plan_text))

    blocks.append(Signoff(roles=("Tool pusher", "Company representative")))

    return blocks
