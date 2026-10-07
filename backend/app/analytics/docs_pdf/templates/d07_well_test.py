"""Template for D07: Well Test and Pressure Survey Report."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import (
    Block,
    Bullets,
    Callout,
    H,
    KV,
    P,
    Signoff,
    Table,
)


def build(spec) -> list[Block]:
    blocks: list[Block] = []

    # Section: Survey Results
    blocks.append(H("Bottom-hole pressure survey results"))
    blocks.append(
        P(
            "Bottom-hole pressure survey {survey_id} was conducted on {survey_date} "
            "at datum depth {datum_tvd_m} m TVD for well {well_id} in {field} field ({cluster_id})."
        )
    )
    blocks.append(
        KV(
            [
                ("Survey identifier", "{survey_id}"),
                ("Survey date", "{survey_date}"),
                ("Datum depth (m TVD)", "{datum_tvd_m}"),
                ("Static BHP (ksc)", "{sbhp_kgcm2}"),
                ("Flowing BHP (ksc)", "{fbhp_kgcm2}"),
                ("Drawdown (ksc)", "{drawdown_kgcm2}"),
                ("Productivity index (BPD/ksc)", "{pi_bpd_per_kgcm2}"),
                ("Acoustic fluid level (m)", "{fluid_level_m}"),
            ],
            cols=2,
        )
    )

    # Section: Comparison with Previous Survey
    blocks.append(H("Comparison with previous pressure survey", level=2))
    if spec.has("prev_survey_date"):
        blocks.append(
            KV(
                [
                    ("Previous survey date", "{prev_survey_date}"),
                    ("Previous static BHP (ksc)", "{prev_sbhp_kgcm2}"),
                    ("Pressure change (ksc)", "{sbhp_change_kgcm2}"),
                ],
                cols=3,
            )
        )
        raw_change = spec.raw.get("sbhp_change_kgcm2")
        if raw_change is not None and raw_change < 0:
            blocks.append(
                P(
                    "Static reservoir pressure declined ({sbhp_change_kgcm2} ksc) compared with "
                    "{prev_sbhp_kgcm2} ksc recorded on {prev_survey_date}, indicating cumulative "
                    "drainage and reservoir voidage across the drainage volume."
                )
            )
        elif raw_change is not None and raw_change > 0:
            blocks.append(
                P(
                    "Static reservoir pressure increased ({sbhp_change_kgcm2} ksc) compared with "
                    "{prev_sbhp_kgcm2} ksc recorded on {prev_survey_date}, indicating pressure support "
                    "or local recharge within the completion block."
                )
            )
        else:
            blocks.append(
                P(
                    "Static reservoir pressure remained unchanged ({sbhp_change_kgcm2} ksc) compared with "
                    "{prev_sbhp_kgcm2} ksc recorded on {prev_survey_date}."
                )
            )
    else:
        blocks.append(
            P(
                "No prior pressure survey is on record for this well. Current measurements serve "
                "as the baseline reservoir pressure reference for the completion interval."
            )
        )

    # Section: Associated Production Well Test
    blocks.append(H("Associated production well test"))
    if spec.has("test_id"):
        blocks.append(
            P(
                "Production test {test_id} was conducted on {test_date} with test quality "
                "assessment graded as {test_quality}."
            )
        )
        blocks.append(
            KV(
                [
                    ("Test identifier", "{test_id}"),
                    ("Test date", "{test_date}"),
                    ("Test duration (hr)", "{test_duration_hr}"),
                    ("Oil rate (BOPD)", "{test_oil_rate_bopd}"),
                    ("Water rate (BWPD)", "{test_water_rate_bwpd}"),
                    ("Gas rate (MSCFD)", "{test_gas_rate_mscfd}"),
                    ("Water cut", "{test_water_cut_pct}"),
                    ("GOR (scf/bbl)", "{test_gor_scf_bbl}"),
                    ("Tubing head pressure (ksc)", "{test_thp_kgcm2}"),
                    ("Casing head pressure (ksc)", "{test_chp_kgcm2}"),
                    ("Acoustic fluid level (m)", "{test_fluid_level_m}"),
                    ("Pump intake pressure (ksc)", "{test_pump_intake_p_kgcm2}"),
                    ("Test quality assessment", "{test_quality}"),
                ],
                cols=2,
            )
        )
        if spec.is_("test_quality", "GOOD"):
            blocks.append(
                P(
                    "Well test fluid rates and surface pressures are validated and suitable "
                    "for production allocation and reservoir performance modeling."
                )
            )
        elif spec.is_("test_quality", "SUSPECT"):
            blocks.append(
                Callout(
                    "Well test data is flagged as suspect due to rate fluctuations during gauging; "
                    "follow-up verification test is recommended.",
                    tone="warning",
                )
            )
        elif spec.is_("test_quality", "REJECTED"):
            blocks.append(
                Callout(
                    "Well test data was rejected due to unstable heading or measurement anomalies; "
                    "repeat test is required.",
                    tone="danger",
                )
            )
    else:
        blocks.append(
            Callout(
                "No valid production test was recorded within the observation window near this survey date.",
                tone="info",
            )
        )

    # Section: Recent Tests Table
    blocks.append(
        Table(
            "recent_tests",
            [
                ("test_date", "Date"),
                ("oil_rate_bopd", "Oil (BOPD)"),
                ("water_rate_bwpd", "Water (BWPD)"),
                ("gas_rate_mscfd", "Gas (MSCFD)"),
                ("thp_kgcm2", "THP (ksc)"),
                ("test_quality", "Quality"),
            ],
            title="Recent well test history",
            empty_text="No prior well tests recorded in the surveillance period.",
        )
    )

    # Section: Decline Versus Offset Wells
    blocks.append(
        H("Decline versus offset wells over trailing {decline_window_days} days")
    )
    blocks.append(
        KV(
            [
                ("Evaluation window (days)", "{decline_window_days}"),
                ("Well oil decline", "{well_decline_pct}"),
                ("Offset median decline", "{offset_median_decline_pct}"),
                ("Offset maximum residual", "{offset_max_residual_pp}"),
            ],
            cols=2,
        )
    )

    # Offset decline interpretation
    w_dec = spec.raw.get("well_decline_pct")
    o_dec = spec.raw.get("offset_median_decline_pct")
    if w_dec is not None and o_dec is not None:
        if w_dec < 0 and o_dec < 0:
            blocks.append(
                P(
                    "Production from {well_id} changed by {well_decline_pct} over the trailing "
                    "{decline_window_days} days compared with an offset median trend of {offset_median_decline_pct} "
                    "(maximum residual {offset_max_residual_pp}). Because the well declines in line with "
                    "surrounding offset wells, the trend points to reservoir depletion and regional drainage "
                    "rather than an isolated near-wellbore or mechanical restriction."
                )
            )
        elif w_dec >= 0 and o_dec >= 0:
            blocks.append(
                P(
                    "Production from {well_id} changed by {well_decline_pct} over the trailing "
                    "{decline_window_days} days alongside an offset median trend of {offset_median_decline_pct} "
                    "(maximum residual {offset_max_residual_pp}). Both the subject well and surrounding offsets "
                    "exhibit positive or steady trends, indicating stable pressure support across this reservoir block."
                )
            )
        else:
            blocks.append(
                P(
                    "Production from {well_id} changed by {well_decline_pct} over the trailing "
                    "{decline_window_days} days while offset wells recorded a median trend of {offset_median_decline_pct} "
                    "(maximum residual {offset_max_residual_pp}). A divergence between subject well performance and "
                    "offset trends suggests local wellbore, artificial lift, or completion effects rather than "
                    "broad reservoir depletion."
                )
            )
    else:
        blocks.append(
            P(
                "Production history over the trailing {decline_window_days} days is partially recorded for "
                "{well_id} ({well_decline_pct}) and offset wells ({offset_median_decline_pct}). Trend comparison "
                "remains provisional until additional surveillance data is gathered."
            )
        )

    blocks.append(
        Table(
            "offsets",
            [
                ("offset_well_id", "Offset well"),
                ("distance_m", "Distance (m)"),
                ("same_zone", "Same zone"),
                ("decline_pct", "Decline rate"),
            ],
            title="Surrounding offset well comparison",
            empty_text="No active offset wells identified within the drainage radius.",
        )
    )

    # Section: Lift Context
    blocks.append(H("Artificial lift and completion context"))
    blocks.append(
        KV(
            [
                ("Lift mechanism", "{lift_type}"),
                ("Production zone", "{current_zone}"),
                ("Perforation interval (m)", "{perf_interval_m}"),
                ("Pump setting depth (m)", "{pump_setting_depth_m}"),
            ],
            cols=2,
        )
    )
    if spec.is_("lift_type", "SRP"):
        if spec.has("pump_setting_depth_m"):
            blocks.append(
                P(
                    "The well operates under sucker-rod pump lift with the pump set at depth "
                    "{pump_setting_depth_m} m in the {current_zone} completion interval."
                )
            )
        else:
            blocks.append(
                P(
                    "The well operates under sucker-rod pump lift producing from the "
                    "{current_zone} completion interval."
                )
            )
    elif spec.is_("lift_type", "GAS_LIFT"):
        blocks.append(
            P(
                "The well operates on continuous gas lift, receiving lift gas from the "
                "{cluster_id} compression and distribution network."
            )
        )
    elif spec.is_("lift_type", "NATURAL"):
        blocks.append(
            P(
                "The well produces under natural flow from the {current_zone} reservoir interval."
            )
        )
    else:
        blocks.append(
            P(
                "Artificial lift method is designated as {lift_type} in {field} field."
            )
        )

    # Section: Remarks
    blocks.append(H("Engineering remarks and surveillance recommendations"))
    remarks = [
        "Bottom-hole static pressure ({sbhp_kgcm2} ksc) and flowing pressure ({fbhp_kgcm2} ksc) establish operating drawdown of {drawdown_kgcm2} ksc at datum depth {datum_tvd_m} m TVD.",
    ]
    if spec.has("sbhp_change_kgcm2"):
        remarks.append(
            "Pressure history records a net change of {sbhp_change_kgcm2} ksc since the prior survey ({prev_sbhp_kgcm2} ksc on {prev_survey_date})."
        )
    if spec.has("test_id"):
        remarks.append(
            "Associated well test {test_id} confirms production rate of {test_oil_rate_bopd} BOPD oil and {test_water_rate_bwpd} BWPD water with quality graded as {test_quality}."
        )
    remarks.append(
        "Survey results are entered into the {field} field surveillance database for material balance updating and lift optimization across {facility_name}."
    )
    blocks.append(Bullets(remarks))

    blocks.append(
        Signoff(
            [
                "Field Production Engineer",
                "Reservoir Surveillance Lead",
                "Asset Manager",
            ]
        )
    )

    return blocks
