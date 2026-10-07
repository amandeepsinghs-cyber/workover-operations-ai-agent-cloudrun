"""Template for D01: Well Completion Report."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import (
    Block,
    H,
    KV,
    P,
    PageBreak,
    Signoff,
    Table,
)


def build(spec) -> list[Block]:
    blocks: list[Block] = []

    # Section: Well identification and trajectory
    blocks.append(H("Well identification and location"))
    id_pairs = [
        ("Surface latitude", "{latitude}"),
        ("Surface longitude", "{longitude}"),
        ("Production cluster", "{cluster_id}"),
        ("Gathering station", "{facility_name}"),
        ("Spud date", "{spud_date}"),
        ("Completion date", "{completion_date}"),
        ("Drilling duration", "{drilling_days} days"),
        ("Target formation", "{current_zone}"),
        ("Total depth (MD)", "{total_depth_md_m} m MD"),
        ("Total depth (TVD)", "{total_depth_tvd_m} m TVD"),
    ]
    blocks.append(KV(id_pairs, cols=2))
    blocks.append(
        P(
            "Well {well_id} was drilled in the {field} field to appraise and develop "
            "hydrocarbon reserves in the {current_zone} reservoir. Operations reached "
            "a final total depth of {total_depth_md_m} m MD ({total_depth_tvd_m} m TVD) "
            "across a drilling duration of {drilling_days} days. Following completion, "
            "production is routed to {facility_name} under cluster {cluster_id}."
        )
    )

    # Section: Formations and lithology
    blocks.append(H("Geological formations and reservoir lithology"))
    blocks.append(
        P(
            "The well penetrates {n_formations} stratigraphic formations down to total depth. "
            "The primary reservoir section in {current_zone} was encountered at {zone_top_md_m} m MD "
            "and consists of {zone_lithology}."
        )
    )
    blocks.append(
        Table(
            "formations",
            [
                ("formation", "Formation"),
                ("top_md_m", "Top (m MD)"),
                ("bottom_md_m", "Base (m MD)"),
                ("lithology", "Lithology"),
            ],
            title="Stratigraphic tops and lithology",
        )
    )

    # Section: Drilling and casing programme
    blocks.append(H("Drilling and casing programme"))
    blocks.append(
        Table(
            "casing",
            [
                ("string_type", "String"),
                ("top_m", "Top (m)"),
                ("shoe_m", "Shoe (m)"),
                ("cement_top_m", "Cement top (m)"),
                ("install_date", "Date"),
                ("od_in", "OD (in)"),
                ("weight_ppf", "Weight (ppf)"),
                ("grade", "Grade"),
            ],
            title="Casing programme and primary cementing",
        )
    )
    blocks.append(
        P(
            "The well construction features {n_casing_strings} casing strings. Surface casing "
            "shoe is set at {surface_casing_shoe_m} m for environmental isolation. The production "
            "casing string ({prod_casing_od_in} in OD, {prod_casing_weight_ppf} ppf, grade "
            "{prod_casing_grade}) is landed at {prod_casing_shoe_m} m with cement top verified "
            "at {cement_top_m} m, providing {cemented_length_m} m of cemented column. The cement "
            "top sits {cement_above_perf_m} m above the topmost perforation to ensure zonal isolation."
        )
    )

    # Section: Perforations
    blocks.append(PageBreak())
    blocks.append(H("Perforation and reservoir access"))
    blocks.append(
        Table(
            "perfs",
            [
                ("zone", "Zone"),
                ("top_m", "Top (m)"),
                ("bottom_m", "Bottom (m)"),
                ("spf", "SPF"),
                ("perf_date", "Perf Date"),
                ("status", "Status"),
            ],
            title="Perforation record",
        )
    )
    blocks.append(
        P(
            "Primary reservoir access was established on {initial_perf_date} with a shot density "
            "of {initial_spf} shots per foot in the {current_zone} formation. Perforations span "
            "{perf_top_m} m to {perf_bottom_m} m MD across an interval of {perf_interval_m} m. "
            "A total of {n_perf_intervals} perforation intervals are recorded, of which "
            "{n_open_perfs} remain open to production."
        )
    )

    # Section: Completion configuration and artificial lift
    blocks.append(H("Completion configuration and artificial lift"))
    if spec.is_("lift_type", "SRP"):
        lift_pairs = [
            ("Lift method", "{lift_type}"),
            ("Pump type", "{pump_type}"),
            ("Pump seating depth", "{pump_setting_depth_m} m"),
            ("Plunger diameter", "{plunger_diameter_in} in"),
            ("Stroke length", "{stroke_length_in} in"),
            ("Sucker rod grade", "Grade {rod_string_grade}"),
            ("Production tubing OD", "{tubing_size_in} in"),
            ("Casing annulus vented", "{casing_vented}"),
        ]
        blocks.append(KV(lift_pairs, cols=2))
        blocks.append(
            P(
                "The well is placed on artificial lift via a sucker-rod pump (SRP) installation. "
                "Subsurface equipment comprises an API {pump_type} pump seated at "
                "{pump_setting_depth_m} m in {tubing_size_in} in tubing, actuated by API grade "
                "{rod_string_grade} sucker rods. Surface unit kinematics are set to a stroke length "
                "of {stroke_length_in} in with a {plunger_diameter_in} in diameter plunger. "
                "Annular gas venting is configured as {casing_vented}."
            )
        )
    elif spec.is_("lift_type", "GAS_LIFT"):
        lift_pairs = [
            ("Lift method", "{lift_type}"),
            ("Production tubing OD", "{tubing_size_in} in"),
            ("Production casing OD", "{casing_size_in} in"),
            ("Casing annulus vented", "{casing_vented}"),
        ]
        blocks.append(KV(lift_pairs, cols=2))
        blocks.append(
            P(
                "The completion is configured for continuous or intermittent gas lift operations. "
                "High-pressure lift gas is routed down the annulus between the {casing_size_in} in "
                "casing and {tubing_size_in} in tubing string to unload fluid columns and sustain "
                "target production rates into {facility_name}."
            )
        )
    elif spec.is_("lift_type", "NATURAL"):
        lift_pairs = [
            ("Lift method", "{lift_type}"),
            ("Production tubing OD", "{tubing_size_in} in"),
            ("Production casing OD", "{casing_size_in} in"),
            ("Casing annulus vented", "{casing_vented}"),
        ]
        blocks.append(KV(lift_pairs, cols=2))
        blocks.append(
            P(
                "The well is completed as a natural flow producer utilizing reservoir pressure. "
                "Hydrocarbons flow up the {tubing_size_in} in production tubing string set within "
                "{casing_size_in} in casing directly into gathering facilities at {facility_name}."
            )
        )
    else:
        lift_pairs = [
            ("Lift method", "{lift_type}"),
            ("Production tubing OD", "{tubing_size_in} in"),
            ("Production casing OD", "{casing_size_in} in"),
            ("Casing annulus vented", "{casing_vented}"),
        ]
        blocks.append(KV(lift_pairs, cols=2))
        blocks.append(
            P(
                "The well is completed with an artificial lift system categorized as {lift_type}, "
                "configured with {tubing_size_in} in production tubing inside {casing_size_in} in "
                "production casing."
            )
        )

    # Section: Completion remarks and signoff
    blocks.append(H("Completion remarks and operational handover"))
    blocks.append(
        P(
            "All drilling, casing, primary cementing, and completion operations have been concluded "
            "in accordance with the field development programme. The well is placed on {well_status} "
            "status and formally handed over to field production operations."
        )
    )
    blocks.append(
        Signoff(["Drilling Superintendent", "Production Engineer", "Asset Manager"])
    )

    return blocks
