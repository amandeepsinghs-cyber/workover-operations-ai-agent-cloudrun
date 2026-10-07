"""Workover and intervention completion report template."""
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
    """Build the document body for a Workover / Intervention Completion Report."""
    blocks: list[Block] = []

    # Section: Job Summary
    summary_pairs = [
        ("Workover ID", "{workover_id}"),
        ("Job Name", "{job_name}"),
        ("Job Code", "{catalogue_job_code}"),
        ("Intervention Class", "{intervention_class} ({ic_label})"),
        ("Job Category", "{job_category}"),
        ("Rig Identifier", "{rig_id}"),
        ("Rigless Execution", "{is_rigless}"),
        ("Start Date", "{start_date}"),
        ("End Date", "{end_date}"),
        ("Calendar Duration", "{calendar_days} days"),
        ("Actual Rig Days", "{rig_days} days"),
        ("Planned Rig Days", "{est_days} days"),
        ("Variance to Plan", "{rig_days_over_plan} days"),
        ("Primary Equipment", "{equipment}"),
        ("Cost Band", "{cost_band}"),
        ("Standard Operating Procedure", "{sop_doc_id}"),
    ]
    blocks.append(H("Job Summary"))
    blocks.append(KV(summary_pairs, cols=2))

    # Section: Reason for Intervention
    blocks.append(H("Reason for Intervention"))
    blocks.append(
        P(
            "Intervention was triggered under failure classification {failure_code} with mechanism "
            "identified as {mechanism_code}. Candidate justification was established from field evidence: "
            "{selection_evidence}."
        )
    )
    if spec.has("pre_oil_avg"):
        blocks.append(
            P(
                "Pre-intervention production baseline established across {window_days} producing days "
                "recorded average crude oil rate of {pre_oil_avg} BOPD at water cut {pre_wc_avg}. "
                "Tubing head pressure averaged {pre_thp_avg} ksc with producing gas-oil ratio of "
                "{pre_gor_avg} scf/bbl ({pre_producing_days} active producing days logged in baseline window)."
            )
        )
    else:
        blocks.append(
            P(
                "Pre-intervention baseline over {window_days} days was not captured as the well recorded "
                "{pre_producing_days} producing days prior to rig move, reflecting shut-in or suspended status."
            )
        )

    # Section: Pre-job Well Status
    blocks.append(H("Pre-Job Well Status and Availability Tracking", level=2))
    blocks.append(
        P(
            "Well operational history within the {lookback_days}-day look-back window logged {wait_on_rig_days} "
            "days waiting on rig, {wait_on_material_days} days waiting on material, and {shut_in_days} days shut-in."
        )
    )
    wait_rig = spec.raw.get("wait_on_rig_days") or 0
    wait_mat = spec.raw.get("wait_on_material_days") or 0
    shut_days = spec.raw.get("shut_in_days") or 0

    if wait_rig > 0 and wait_mat > 0:
        blocks.append(
            P(
                "Mobilization schedule experienced delays attributable to both workover rig queue "
                "({wait_on_rig_days} days) and surface material or equipment procurement constraints "
                "({wait_on_material_days} days)."
            )
        )
    elif wait_rig > 0:
        blocks.append(
            P(
                "Mobilization schedule was delayed due to workover rig availability constraints "
                "({wait_on_rig_days} days waiting on rig)."
            )
        )
    elif wait_mat > 0:
        blocks.append(
            P(
                "Mobilization schedule was impacted by material procurement and staging constraints "
                "({wait_on_material_days} days waiting on material)."
            )
        )
    else:
        blocks.append(
            P(
                "No logistical delays or material procurement hold-ups were incurred prior to rig move."
            )
        )

    if shut_days > 0:
        blocks.append(
            P(
                "The well sustained {shut_in_days} days of shut-in downtime during the look-back window."
            )
        )

    # Section: Operations Summary
    blocks.append(H("Operations Summary"))
    if spec.is_("is_rigless", "Yes"):
        blocks.append(
            P(
                "Operations were conducted as a rigless intervention utilizing specialized {equipment}. "
                "Surface crews performed rigless wellhead access, pressure containment verification, and "
                "fluid servicing on wellsite {well_id} in {field} field without requiring a conventional mast."
            )
        )
    else:
        blocks.append(
            P(
                "Intervention was executed utilizing workover rig package {rig_id} and {equipment}. "
                "Crews completed mast spotting, rig-up, well control kill operations, and string handling "
                "over {calendar_days} calendar days ({rig_days} operational rig days) on well {well_id}."
            )
        )

    cat = spec.raw.get("job_category")
    if cat == "WAX":
        blocks.append(
            P(
                "Paraffin remediation procedure was executed in accordance with {sop_doc_id}. "
                "Wellbore mechanical scraping and hot fluid solvent washes targeted organic wax "
                "deposition in the upper tubing column to eliminate restriction and re-establish conduit flow."
            )
        )
    elif cat == "MECHANICAL":
        blocks.append(
            P(
                "Mechanical restoration was executed under procedure {sop_doc_id}. "
                "Tubing string, downhole pumping assembly, and wellhead integrity items were pulled, "
                "serviced, redressed, and re-run to rectify mechanical failure and secure pressure integrity."
            )
        )
    elif cat == "DEPOSITION":
        blocks.append(
            P(
                "Deposition remediation was executed pursuant to {sop_doc_id}. "
                "Chemical solvent soak and mechanical bailer cleanout targeted scale and particulate "
                "accumulation across the completion interval to restore flow area."
            )
        )
    elif cat == "INFLOW":
        blocks.append(
            P(
                "Inflow stimulation operations were conducted under {sop_doc_id}. "
                "Matrix treatment and perforation washing were applied across reservoir zone {current_zone} "
                "to alleviate near-wellbore skin damage and improve productivity index."
            )
        )
    elif cat == "WATER_CONTROL":
        blocks.append(
            P(
                "Water conformance and shut-off operations followed {sop_doc_id}. "
                "Diagnostic isolation and squeeze cementing were deployed to block water influx "
                "channels and suppress excessive water production from breakthrough zones."
            )
        )
    elif cat == "GAS_LIFT":
        blocks.append(
            P(
                "Gas lift repair and valve changeout were carried out under {sop_doc_id}. "
                "Slickline operations retrieved defective gas lift valves from side pocket mandrels and "
                "installed re-calibrated valves to stabilize annular injection and unloading."
            )
        )
    elif cat == "TERMINAL":
        blocks.append(
            P(
                "Terminal isolation operations were conducted in accordance with abandonment procedure {sop_doc_id}. "
                "Permanent barriers and cement plugs were set to isolate productive horizons and ensure long-term well integrity."
            )
        )
    else:
        blocks.append(
            P(
                "Intervention operations for {job_name} ({catalogue_job_code}) were conducted in alignment "
                "with field operating procedure {sop_doc_id} to restore well operational integrity."
            )
        )

    # Section: Results
    blocks.append(H("Post-Intervention Results and Performance Analysis"))
    if spec.has("post_oil_avg") and spec.has("delta_oil"):
        blocks.append(
            P(
                "Stabilized production observed over {window_days} producing days following completion "
                "recorded average crude rate of {post_oil_avg} BOPD (net change {delta_oil} BOPD) at "
                "water cut of {post_wc_avg} (net change {delta_wc}). Tubing head pressure averaged "
                "{post_thp_avg} ksc (net change {delta_thp} ksc) with casing head pressure of "
                "{post_chp_avg} ksc and producing gas-oil ratio of {post_gor_avg} scf/bbl."
            )
        )
    elif spec.has("post_oil_avg"):
        blocks.append(
            P(
                "Stabilized production observed over {window_days} producing days following completion "
                "recorded average crude rate of {post_oil_avg} BOPD at water cut {post_wc_avg}. "
                "Tubing head pressure averaged {post_thp_avg} ksc with casing head pressure of "
                "{post_chp_avg} ksc and producing gas-oil ratio of {post_gor_avg} scf/bbl."
            )
        )
    else:
        blocks.append(
            P(
                "Post-intervention production logging across the {window_days}-day monitoring window is "
                "pending full well stabilization or deferred due to operational scheduling."
            )
        )

    if spec.has("uplift_bopd"):
        blocks.append(
            P(
                "Direct well test verification established pre-job test rate of {pre_job_oil_bopd} BOPD "
                "versus post-job test rate of {post_job_oil_bopd} BOPD, yielding an immediate uplift of "
                "{uplift_bopd} BOPD. Post-intervention operational run life reached {run_life_days} days "
                "with damage reset factor of {damage_reset_frac}."
            )
        )
    else:
        blocks.append(
            P(
                "Pre-job baseline test rate was logged at {pre_job_oil_bopd} BOPD. Operational run life "
                "following intervention reached {run_life_days} days with damage reset factor of {damage_reset_frac}."
            )
        )

    if spec.is_("outcome", "SUCCESS"):
        if spec.has("uplift_bopd"):
            blocks.append(
                Callout(
                    "JOB OUTCOME: SUCCESS — All intervention objectives were fulfilled. Well {well_id} achieved "
                    "target production restoration with positive test uplift of {uplift_bopd} BOPD, complete "
                    "mechanical reset, and stable flowing parameters.",
                    tone="success",
                )
            )
        else:
            blocks.append(
                Callout(
                    "JOB OUTCOME: SUCCESS — All intervention objectives were fulfilled. Well {well_id} achieved "
                    "target production restoration, complete mechanical reset, and stable flowing parameters.",
                    tone="success",
                )
            )
    elif spec.is_("outcome", "PARTIAL"):
        if spec.has("uplift_bopd"):
            blocks.append(
                Callout(
                    "JOB OUTCOME: PARTIAL — Operational program was executed but production response was limited "
                    "({uplift_bopd} BOPD uplift). Flowing parameters indicate residual inflow restriction or lift "
                    "limitations. Continued surveillance is assigned.",
                    tone="warning",
                )
            )
        else:
            blocks.append(
                Callout(
                    "JOB OUTCOME: PARTIAL — Operational program was executed but production response was limited. "
                    "Flowing parameters indicate residual inflow restriction or lift limitations. Continued "
                    "surveillance is assigned.",
                    tone="warning",
                )
            )
    elif spec.is_("outcome", "FAILED"):
        if spec.has("uplift_bopd"):
            blocks.append(
                Callout(
                    "JOB OUTCOME: FAILED — Intervention did not achieve expected production uplift ({uplift_bopd} BOPD "
                    "uplift). Subsurface inflow or mechanical integrity remained compromised. Root cause investigation "
                    "and remediation review are required.",
                    tone="danger",
                )
            )
        else:
            blocks.append(
                Callout(
                    "JOB OUTCOME: FAILED — Intervention did not achieve expected production restoration. Subsurface "
                    "inflow or mechanical integrity remained compromised. Root cause investigation and remediation "
                    "review are required.",
                    tone="danger",
                )
            )
    else:
        blocks.append(
            Callout(
                "JOB OUTCOME: {outcome} — Intervention concluded with recorded post-job rate of {post_job_oil_bopd} BOPD.",
                tone="info",
            )
        )

    # Section: Tubing Installed
    blocks.append(H("Tubing and Downhole Equipment Installed", level=2))
    blocks.append(
        Table(
            "tubing_installed",
            [
                ("seq", "Seq"),
                ("component", "Component"),
                ("od_in", "OD (in)"),
                ("length_m", "Length (m)"),
                ("top_m", "Top (m)"),
                ("install_date", "Date Installed"),
            ],
            empty_text="No tubing string components or downhole equipment were installed or replaced during this job.",
        )
    )

    # Section: Intervention History
    blocks.append(H("Intervention History and Preceding Jobs", level=2))
    if spec.has("prev_workover_id"):
        blocks.append(
            P(
                "Prior to this operation, {n_prior_jobs} interventions were recorded for well {well_id}. "
                "The immediate preceding job was {prev_workover_id} ({prev_job_code}), concluding on "
                "{prev_end_date} with outcome {prev_outcome} ({days_since_prev} days elapsed between operations)."
            )
        )
    else:
        blocks.append(
            P(
                "Well registry documents {n_prior_jobs} recorded historical interventions. No prior intervention "
                "records are cataloged in the immediate antecedent interval."
            )
        )
    blocks.append(
        Table(
            "job_history",
            [
                ("workover_id", "Job ID"),
                ("start_date", "Start Date"),
                ("end_date", "End Date"),
                ("catalogue_job_code", "Job"),
                ("intervention_class", "Class"),
                ("rig_days", "Rig Days"),
                ("outcome", "Outcome"),
            ],
            max_rows=8,
            empty_text="No historical intervention records logged for this well.",
        )
    )

    # Section: Deferred Production
    blocks.append(H("Deferred Production Accounting", level=2))
    if spec.has("deferred_bbl"):
        blocks.append(
            P(
                "Production loss evaluation attributed to well shut-in and intervention downtime during this "
                "workover cycle totaled {deferred_bbl} bbl of crude oil deferred."
            )
        )
    else:
        blocks.append(
            P(
                "Deferred production accounting was not quantified for this intervention event."
            )
        )

    # Section: Operational References
    blocks.append(H("Operational References and Daily Reports", level=2))
    refs = [
        "Standard operating procedure: field standard {sop_doc_id}.",
        "Daily operational reports: {n_rig_days_reported} daily workover reports (DWR) filed during rig activity.",
    ]
    if spec.has("prev_workover_id"):
        refs.append("Preceding workover file: {prev_workover_id} ({prev_job_code}), concluded {prev_end_date}.")
    if spec.has("next_workover_id"):
        refs.append("Subsequent workover file: {next_workover_id} ({next_job_code}), started {next_start_date}.")
    else:
        refs.append("Subsequent workover file: No subsequent intervention recorded in corpus tracking.")
    blocks.append(Bullets(refs))

    blocks.append(
        Signoff(
            roles=[
                "Prepared by (Wellsite Workover Engineer)",
                "Reviewed by (Production Operations Superintendent)",
                "Approved by (Asset Development Manager)",
            ]
        )
    )

    return blocks
