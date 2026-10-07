"""Template D04: Wellbore schematic and casing / tubing tally (current configuration)."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import (
    KV,
    Block,
    Bullets,
    DocSpec,
    H,
    P,
    PageBreak,
    Schematic,
    Table,
)


def build(spec: DocSpec) -> list[Block]:
    # Key reference depths
    depth_pairs = [
        ("Total depth MD", "{total_depth_md_m} m"),
        ("Total depth TVD", "{total_depth_tvd_m} m"),
        ("Surface casing shoe", "{surface_casing_shoe_m} m"),
        ("Production casing shoe", "{prod_casing_shoe_m} m"),
        ("Top of cement", "{cement_top_m} m"),
        ("Perforation interval (top / bottom)", "{perf_top_m} / {perf_bottom_m} m"),
        ("Pump intake top", "{pump_top_m} m" if spec.has("pump_top_m") else "{pump_top_m}"),
        ("Tubing anchor top", "{anchor_top_m} m" if spec.has("anchor_top_m") else "{anchor_top_m}"),
        ("Pump setting depth", "{pump_setting_depth_m} m" if spec.has("pump_setting_depth_m") else "{pump_setting_depth_m}"),
        ("Current zone top MD", "{zone_top_md_m} m"),
    ]

    # Lift equipment specification
    lift_pairs = [
        ("Lift mechanism", "{lift_type}"),
        ("Pump type", "{pump_type}"),
        ("Plunger diameter (in)", "{plunger_diameter_in}"),
        ("Surface stroke length (in)", "{stroke_length_in}"),
        ("Sucker rod grade", "{rod_string_grade}"),
        ("Casing annulus vented", "{casing_vented}"),
    ]

    # Casing tally columns
    casing_cols = [
        ("string_type", "String type"),
        ("od_in", "OD (in)"),
        ("weight_ppf", "Weight (ppf)"),
        ("grade", "Grade"),
        ("install_date", "Installed"),
        ("top_m", "Top (m)"),
        ("shoe_m", "Shoe (m)"),
        ("cement_top_m", "TOC (m)"),
    ]

    # Tubing tally columns
    tubing_cols = [
        ("seq", "Seq"),
        ("component", "Component"),
        ("od_in", "OD (in)"),
        ("length_m", "Length (m)"),
        ("top_m", "Top (m)"),
        ("install_date", "Installed"),
        ("workover_id", "Workover"),
    ]

    # Perforations columns
    perf_cols = [
        ("zone", "Zone"),
        ("top_m", "Top (m)"),
        ("bottom_m", "Bottom (m)"),
        ("spf", "SPF"),
        ("perf_date", "Date"),
        ("status", "Status"),
    ]

    # Formation tops columns (lithology column)
    formation_cols = [
        ("formation", "Formation"),
        ("top_md_m", "Top (m MD)"),
        ("bottom_md_m", "Bottom (m MD)"),
        ("lithology", "Lithology"),
    ]

    # Notes
    notes = [
        "Wellbore schematic is a diagrammatic representation and is not to scale.",
        "All depths are measured depth (MD) referenced to the rotary table bushing.",
        "True vertical depth references are recorded where directional surveys exist.",
        "Casing, tubing, perforation, and geological horizons reflect current wellbore status.",
    ]

    blocks: list[Block] = [
        H("Wellbore configuration and reference depths"),
        P(
            "Current wellbore architecture and downhole completion schematic for well {well_id} in {field} field "
            "({facility_name}), completed in the {current_zone} reservoir horizon."
        ),
        KV(depth_pairs, cols=2, title="Key reference depths"),
        Schematic(caption="Wellbore schematic and lithology column (not to scale)"),
        PageBreak(),
        H("Casing program and downhole tally"),
        P(
            "Wellbore casing program consists of {n_casing_strings} casing strings. Production casing string "
            "({prod_casing_grade}, {prod_casing_od_in} in, {prod_casing_weight_ppf} ppf) is landed at "
            "{prod_casing_shoe_m} m with cement top at {cement_top_m} m."
        ),
        Table("casing", casing_cols, title="Casing tally"),
        H("Tubing and bottom hole assembly"),
    ]

    if spec.has("tubing_workover_id"):
        blocks.append(
            P(
                "Current production tubing string was run on {tubing_install_date} during workover "
                "{tubing_workover_id}, comprising {n_tubing_components} tally components."
            )
        )
    else:
        blocks.append(
            P(
                "Current production tubing string was installed on {tubing_install_date}, comprising "
                "{n_tubing_components} tally components."
            )
        )

    blocks.extend([
        Table("tubing", tubing_cols, title="Tubing and BHA tally"),
        H("Perforation and reservoir intervals"),
        P(
            "Perforated interval spans {perf_interval_m} m across {n_perf_intervals} recorded intervals, with "
            "{n_open_perfs} open intervals in {current_zone} formation."
        ),
        Table("perfs", perf_cols, title="Perforation intervals"),
        H("Formation tops and lithology column"),
        P(
            "Stratigraphic column records {n_formations} geological horizons. The current producing reservoir "
            "is {current_zone} with formation top at {zone_top_md_m} m MD, characterized by {zone_lithology}."
        ),
        Table("formations", formation_cols, title="Formation tops and lithology"),
        H("Artificial lift and surface equipment"),
    ])

    if spec.is_("lift_type", "SRP"):
        blocks.append(
            P(
                "Well produces via sucker rod pump lift with {pump_type} pump configuration, utilizing "
                "{rod_string_grade} grade rod string."
            )
        )
    elif spec.is_("lift_type", "GAS_LIFT"):
        blocks.append(P("Well is configured for continuous or intermittent gas lift production."))
    else:
        blocks.append(P("Well produces under natural flow reservoir drive without artificial lift equipment."))

    blocks.extend([
        KV(lift_pairs, cols=2, title="Lift equipment parameters"),
        H("Operational remarks and notes"),
        Bullets(notes),
    ])

    return blocks
