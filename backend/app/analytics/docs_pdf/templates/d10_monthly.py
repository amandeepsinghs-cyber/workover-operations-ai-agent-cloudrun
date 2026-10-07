"""Template for D10: Monthly Field Production Report.

Generates monthly performance reports per field-month with headline KPIs,
commentary branching on target gap and month-on-month trend, cluster production,
top producing wells, intervention activity, downtime deferment, operational events,
and forward-looking action items.
"""
from __future__ import annotations

from app.analytics.docs_pdf.ir import (
    Callout,
    H,
    KV,
    P,
    Signoff,
    Table,
    Bullets,
)


def build(spec):
    blocks = []

    # 1. Headline KPIs
    blocks.append(H("Monthly Field Performance Summary"))
    kpi_pairs = [
        ("Reporting Period", "{month_label}"),
        ("Average Oil Rate", "{avg_oil_bopd} BOPD"),
        ("Target Oil Rate", "{target_oil_bopd} BOPD"),
        ("Target Variance", "{gap_vs_target_pct}"),
    ]
    if spec.has("mom_change_pct"):
        kpi_pairs.append(("Month on Month Change", "{mom_change_pct}"))
    kpi_pairs.extend([
        ("Gross Oil Production", "{oil_bbl} bbl"),
        ("Produced Water Volume", "{water_bbl} bbl"),
        ("Associated Gas Volume", "{gas_mscf} MSCF"),
        ("Average Water Cut", "{avg_water_cut_pct}"),
        ("Average Gas Oil Ratio", "{avg_gor_scf_bbl} scf/bbl"),
        ("Active Producing Wells", "{active_wells} of {wells_total} wells"),
        ("Field Operating Uptime", "{uptime_pct} vs target {target_uptime_pct}"),
        ("Deferred Oil Volume", "{deferred_bbl} bbl"),
    ])
    blocks.append(KV(kpi_pairs, cols=2))

    # 2. Commentary prose
    blocks.append(H("Production Commentary and Operational Review"))

    raw_gap = spec.raw.get("gap_vs_target_pct")
    if raw_gap is not None and raw_gap >= 0:
        blocks.append(
            P(
                "During {month_label}, {field} field delivered an average crude production rate of "
                "{avg_oil_bopd} BOPD against the monthly target of {target_oil_bopd} BOPD, achieving a "
                "favorable variance of {gap_vs_target_pct}. Production targets were successfully met "
                "through sustained artificial lift efficiency and stable reservoir draw across primary "
                "gathering stations."
            )
        )
        blocks.append(
            Callout(
                "Field production exceeded monthly target by {gap_vs_target_pct}, supported by active well "
                "availability and facility uptime.",
                tone="success",
            )
        )
    else:
        blocks.append(
            P(
                "During {month_label}, {field} field produced at an average crude rate of {avg_oil_bopd} BOPD "
                "compared with the planned target of {target_oil_bopd} BOPD, reflecting a shortfall of "
                "{gap_vs_target_pct}. Production delivery was constrained by unscheduled well downtime, "
                "artificial lift operational interruptions, and deferred production of {deferred_bbl} bbl."
            )
        )
        blocks.append(
            Callout(
                "Field production operated below monthly target by {gap_vs_target_pct}; corrective well "
                "servicing and artificial lift stabilization are underway.",
                tone="warning",
            )
        )

    raw_mom = spec.raw.get("mom_change_pct")
    if spec.has("mom_change_pct") and raw_mom is not None and raw_mom == raw_mom:
        if raw_mom >= 0:
            blocks.append(
                P(
                    "Month on month performance demonstrated positive momentum, with crude oil rate shifting "
                    "by {mom_change_pct} relative to the previous month baseline of {prev_avg_oil_bopd} BOPD. "
                    "Upward trajectory was assisted by intervention uplift and restoration of shut-in capacity."
                )
            )
        else:
            blocks.append(
                P(
                    "Month on month production reflected a contraction of {mom_change_pct} from the prior month "
                    "average of {prev_avg_oil_bopd} BOPD. The downward variance was influenced by natural reservoir "
                    "decline, water cut encroachment averaging {avg_water_cut_pct}, and temporary flowline bottlenecks."
                )
            )
    else:
        blocks.append(
            P(
                "Baseline reporting for the initial monitored period established average crude output of "
                "{avg_oil_bopd} BOPD across {active_wells} active wells, providing reference datum for subsequent "
                "operational tracking."
            )
        )

    blocks.append(
        P(
            "Fluid production over the period comprised {oil_bbl} bbl of gross crude oil and {water_bbl} bbl of "
            "formation water, corresponding to an average field water cut of {avg_water_cut_pct}. Associated "
            "gas production reached {gas_mscf} MSCF with a mean operating gas oil ratio of {avg_gor_scf_bbl} scf/bbl, "
            "handled through field gathering facilities.",
            style="note",
        )
    )

    # 3. Production by cluster
    blocks.append(H("Production by Gathering Station Cluster"))
    blocks.append(
        P(
            "Total field production is gathered across group gathering stations (GGS) within {field} field. "
            "Production distribution and average flow rates per cluster during the period are detailed below:"
        )
    )
    blocks.append(
        Table(
            "clusters",
            [
                ("cluster_id", "Cluster / GGS"),
                ("wells", "Active Wells"),
                ("oil", "Gross Oil (bbl)"),
                ("avg_oil_bopd", "Average Rate (BOPD)"),
            ],
            title="Gathering Station Cluster Production",
        )
    )

    # 4. Top producing wells
    blocks.append(H("Top Producing Wells"))
    blocks.append(
        P(
            "The leading oil producing wells contributing to monthly output, based on cumulative volume and "
            "producing days on stream:"
        )
    )
    blocks.append(
        Table(
            "top_wells",
            [
                ("well_id", "Well"),
                ("oil", "Monthly Oil (bbl)"),
                ("avg_oil_bopd", "Average Rate (BOPD)"),
                ("days_on", "Days On"),
            ],
            title="Top Oil Producing Wells",
            max_rows=10,
        )
    )

    # 5. Interventions started in the month
    blocks.append(H("Well Interventions and Workover Activity"))
    if spec.has("job_success_pct"):
        blocks.append(
            P(
                "During {month_label}, a total of {n_jobs} well interventions were initiated across the field, "
                "utilizing {rig_days_used} rig days. Recorded job outcomes yielded a success rate of {job_success_pct}, "
                "with {n_jobs_failed} failed operations and total production uplift of {uplift_bopd_total} BOPD."
            )
        )
    else:
        blocks.append(
            P(
                "During {month_label}, {n_jobs} well interventions were initiated across the field, utilizing "
                "{rig_days_used} rig days, with {n_jobs_failed} failed operations recorded during the period."
            )
        )

    int_pairs = [
        ("Interventions Commenced", "{n_jobs}"),
        ("Failed Interventions", "{n_jobs_failed}"),
        ("Rig Days Consumed", "{rig_days_used}"),
        ("Total Production Uplift", "{uplift_bopd_total} BOPD"),
    ]
    if spec.has("job_success_pct"):
        int_pairs.append(("Intervention Success Rate", "{job_success_pct}"))
    blocks.append(KV(int_pairs, cols=2))

    blocks.append(
        Table(
            "jobs_by_class",
            [
                ("intervention_class", "Class"),
                ("ic_label", "Job Description"),
                ("n_jobs", "Jobs"),
                ("n_success", "Success"),
                ("n_failed", "Failed"),
                ("rig_days", "Rig Days"),
                ("uplift_bopd", "Uplift (BOPD)"),
            ],
            title="Interventions Summary by Class",
            max_rows=8,
        )
    )
    blocks.append(
        Table(
            "jobs_started",
            [
                ("well_id", "Well"),
                ("workover_id", "Workover ID"),
                ("catalogue_job_code", "Job Code"),
                ("intervention_class", "Class"),
                ("start_date", "Start Date"),
                ("rig_days", "Rig Days"),
                ("outcome", "Outcome"),
            ],
            title="Interventions Started in Month",
            max_rows=10,
        )
    )

    # 6. Downtime by reason
    blocks.append(H("Downtime and Deferred Production Analysis"))
    blocks.append(
        P(
            "Non-producing well episodes and associated deferment during the monthly period are categorized by "
            "well status and primary reason code, representing total deferred volume of {deferred_bbl} bbl:"
        )
    )
    blocks.append(
        Table(
            "downtime",
            [
                ("status", "Status"),
                ("reason_code", "Reason"),
                ("episodes", "Episodes"),
                ("days", "Lost Days"),
                ("deferred_bbl", "Deferred (bbl)"),
            ],
            title="Downtime and Deferment by Reason",
            max_rows=8,
        )
    )

    # 7. Operational events
    blocks.append(H("Operational Field Events"))
    blocks.append(
        P(
            "Field operations recorded unscheduled events during the month, classified by operational factor "
            "and controllability:"
        )
    )
    blocks.append(
        Table(
            "events",
            [
                ("event_type", "Event Type"),
                ("factor_class", "Factor Class"),
                ("events", "Events"),
                ("controllable", "Controllable"),
            ],
            title="Operational and Unscheduled Events",
            max_rows=8,
        )
    )

    # 8. Actions for next month
    blocks.append(H("Planned Operational Focus for Next Month"))
    actions = [
        "Prioritize workover candidate selection for wells experiencing severe artificial lift decline or sand ingress in Tipam and Barail reservoirs.",
        "Execute routine gas-lift valve optimization and mandrel inspection across active continuous injection strings.",
        "Coordinate with electrical maintenance teams to mitigate power grid supply interruptions affecting sucker-rod pumping installations.",
        "Continue surface pipeline integrity surveys and header pressure monitoring across gathering station flowlines.",
        "Follow up on non-controllable deferment causes with regional maintenance teams and expedite pulling unit mobilization for pending jobs.",
    ]
    if spec.is_("field", "Geleki"):
        actions.append("Ensure steady gas-lift injection pressure from Geleki compressor station to maintain high-lift wells.")
    elif spec.is_("field", "Lakwa"):
        actions.append("Maintain active monitoring of Lakwa thermal and SRP wells to counter wax deposition.")
    elif spec.is_("field", "Lakhmani"):
        actions.append("Optimize Lakhmani gathering station inlet separators and monitor effluent water disposal handling capacity.")
    blocks.append(Bullets(actions))

    blocks.append(
        Signoff(
            roles=[
                "Prepared by (Production Engineer)",
                "Reviewed by (Asset Manager)",
                "Approved by (Chief General Manager)",
            ]
        )
    )

    return blocks
