"""Field study and annual review template (type D09).

Handles two variants:
- Annual review documents (per field-year, e.g. FS-GK-2024): comprehensive review
  covering executive summary, production indicators, cluster performance, workover
  campaign, downtime analysis, operational disruptions, field facilities, and outlook.
- Legacy field studies (spec.meta['variant'] == 'legacy_study', e.g. DOC-FIELD-TIPAM-GEOL-2012):
  concise technical evaluation note built from static field facts and inventory tables.
"""
from __future__ import annotations

from app.analytics.docs_pdf.ir import (
    Block,
    Bullets,
    Callout,
    H,
    KV,
    P,
    Table,
)


def _build_legacy(spec) -> list[Block]:
    """Render a legacy technical field study note using static field facts."""
    return [
        H("Technical study overview"),
        Callout("Subject matter: {study_topic}", tone="info"),
        P(
            "This technical study report documents field engineering and geological evaluations "
            "for the {field} field in the {asset} Asset. The study consolidates static field criteria, "
            "reservoir zonation, surface infrastructure, and artificial lift allocation across "
            "{n_wells} field wells grouped into {n_clusters} production clusters."
        ),
        KV(
            [
                ("Study topic", "{study_topic}"),
                ("Asset area", "{asset}"),
                ("Primary reservoirs", "{primary_reservoirs}"),
                ("Total field wells", "{n_wells}"),
                ("Production clusters", "{n_clusters}"),
                ("Field centroid latitude", "{centroid_lat}"),
                ("Field centroid longitude", "{centroid_lon}"),
                ("Baseline record start", "{data_start}"),
                ("Baseline record end", "{data_end}"),
            ],
            cols=2,
            title="Field geographic and reservoir reference",
        ),
        H("Reservoir and stratigraphic framework"),
        P(
            "Hydrocarbon development is sustained across {primary_reservoirs} formations. "
            "Median structural formation tops and reservoir lithologies are summarized below."
        ),
        Table(
            "formation_summary",
            [
                ("formation", "Formation"),
                ("median_top_md_m", "Median top (m MD)"),
                ("wells", "Penetrating wells"),
                ("lithology", "Lithology"),
            ],
            title="Formation stratigraphy summary",
        ),
        H("Infrastructure and operating clusters"),
        P(
            "Production operations rely on surface gathering stations and assigned cluster networks "
            "supporting artificial lift and fluid delivery."
        ),
        Table(
            "facilities",
            [
                ("facility_id", "Facility"),
                ("type", "Type"),
                ("name", "Name"),
                ("capacity_bopd", "Capacity (BOPD)"),
                ("serviced_cluster_ids", "Serviced clusters"),
            ],
            title="Field facilities and handling capacities",
        ),
        Table(
            "lift_mix",
            [
                ("lift_type", "Lift mechanism"),
                ("wells", "Assigned wells"),
            ],
            title="Artificial lift distribution",
        ),
        Table(
            "cluster_list",
            [
                ("cluster_id", "Cluster"),
                ("cluster_type", "Type"),
                ("n_wells", "Wells"),
                ("center_lat", "Latitude"),
                ("center_lon", "Longitude"),
            ],
            title="Operating cluster boundaries",
        ),
        H("Study conclusions and technical context"),
        P(
            "The findings and baseline parameters established in this study provide core reference "
            "guidelines for ongoing reservoir surveillance, well workover planning, and facility operations."
        ),
    ]


def _build_annual_review(spec) -> list[Block]:
    """Render a field annual review covering production, workovers, downtime, and outlook."""
    blocks: list[Block] = [
        H("Executive summary"),
    ]

    if spec.is_("is_partial_year", "Yes"):
        blocks.append(
            P(
                "This interim review covers operational performance for the partial-year period from "
                "{period_start} to {period_end} ({period_days} calendar days). Field oil production averaged "
                "{avg_oil_bopd} BOPD against an established target rate of {target_oil_bopd} BOPD, "
                "yielding a variance of {gap_vs_target_pct}."
            )
        )
    else:
        blocks.append(
            P(
                "This annual review evaluates field production and operational performance across the full calendar "
                "year spanning {period_start} to {period_end} ({period_days} operating days). Field oil production "
                "averaged {avg_oil_bopd} BOPD compared with the approved target allocation of {target_oil_bopd} BOPD, "
                "reflecting a variance of {gap_vs_target_pct}."
            )
        )

    if spec.has("yoy_change_pct"):
        blocks.append(
            P(
                "Compared with the preceding annual average rate of {prev_avg_oil_bopd} BOPD, field oil delivery "
                "shifted by {yoy_change_pct} on an annual comparison basis."
            )
        )

    blocks.extend(
        [
            H("Production performance"),
            KV(
                [
                    ("Total oil production", "{oil_bbl} bbl"),
                    ("Field potential rate", "{potential_oil_bopd} BOPD"),
                    ("Total water production", "{water_bbl} bbl"),
                    ("Average water cut", "{avg_water_cut_pct}"),
                    ("Total gas production", "{gas_mscf} MSCF"),
                    ("Average gas-oil ratio", "{avg_gor_scf_bbl} scf/bbl"),
                    ("Active producing wells", "{active_wells} of {wells_total} wells"),
                    ("Field operating uptime", "{uptime_pct} (target {target_uptime_pct})"),
                ],
                cols=2,
                title="Production and reservoir indicators",
            ),
            H("Cluster production distribution"),
            Table(
                "clusters",
                [
                    ("cluster_id", "Cluster"),
                    ("wells", "Producing wells"),
                    ("oil", "Total oil (bbl)"),
                    ("avg_oil_bopd", "Average rate (BOPD)"),
                ],
                title="Cluster-level contribution",
            ),
            H("Intervention programme"),
            P(
                "Field operations conducted {n_jobs} well intervention campaigns expending {rig_days_used} rig days. "
                "The workover programme achieved an overall success rate of {job_success_pct}, recording {n_jobs_failed} "
                "failed operations while adding a cumulative initial uplift of {uplift_bopd_total} BOPD."
            ),
            Table(
                "jobs_by_class",
                [
                    ("intervention_class", "Class"),
                    ("ic_label", "Job description"),
                    ("n_jobs", "Jobs"),
                    ("rig_days", "Rig days"),
                    ("uplift_bopd", "Uplift (BOPD)"),
                    ("n_success", "Success"),
                    ("n_failed", "Failed"),
                ],
                title="Intervention performance by class",
                max_rows=8,
            ),
            H("Downtime and deferment"),
            P(
                "Well downtime, workover waiting periods, and surface bottlenecks contributed to an estimated "
                "cumulative deferment of {deferred_bbl} bbl. Non-producing episodes are detailed by root category below."
            ),
            Table(
                "downtime",
                [
                    ("status", "Status"),
                    ("reason_code", "Reason"),
                    ("episodes", "Episodes"),
                    ("days", "Lost days"),
                    ("deferred_bbl", "Deferred oil (bbl)"),
                ],
                title="Downtime episodes and deferment",
            ),
            H("Operational events"),
            P(
                "Field operational event logs summarize major external, equipment, and human process disruptions "
                "impacting daily operations and well uptime."
            ),
            Table(
                "events",
                [
                    ("event_type", "Event type"),
                    ("factor_class", "Factor category"),
                    ("events", "Total events"),
                    ("controllable", "Controllable"),
                ],
                title="Field operational disruption summary",
            ),
            H("Field description and infrastructure"),
            P(
                "The {field} asset comprises {n_wells} total wells across {n_clusters} production clusters. "
                "Drainage targets focus on the {primary_reservoirs} reservoir sequences."
            ),
            Table(
                "facilities",
                [
                    ("facility_id", "Facility"),
                    ("type", "Type"),
                    ("name", "Name"),
                    ("capacity_bopd", "Capacity (BOPD)"),
                    ("serviced_cluster_ids", "Serviced clusters"),
                ],
                title="Surface gathering and processing facilities",
            ),
            Table(
                "lift_mix",
                [
                    ("lift_type", "Lift mechanism"),
                    ("wells", "Well count"),
                ],
                title="Artificial lift allocation",
            ),
            Table(
                "formation_summary",
                [
                    ("formation", "Formation"),
                    ("median_top_md_m", "Median top (m MD)"),
                    ("wells", "Penetrating wells"),
                    ("lithology", "Lithology"),
                ],
                title="Stratigraphic formation summary",
            ),
            H("Outlook and recommendations"),
        ]
    )

    if spec.raw.get("gap_vs_target_pct") is not None and spec.raw["gap_vs_target_pct"] >= 0:
        blocks.extend(
            [
                Callout(
                    "Production targets were achieved for the reporting period with positive target variance "
                    "of {gap_vs_target_pct}. Forward priorities focus on maintaining lift reliability and "
                    "containing water cut development.",
                    tone="success",
                ),
                Bullets(
                    [
                        "Sustain scheduled maintenance routines on artificial lift surface drives and downhole assemblies.",
                        "Track water cut evolution across high-rate wells and evaluate mechanical shut-off candidates.",
                        "Continue proactive well testing and acoustic fluid level monitoring across all active clusters.",
                    ]
                ),
            ]
        )
    else:
        blocks.extend(
            [
                Callout(
                    "Annual production recorded an unfavorable variance of {gap_vs_target_pct} against asset targets. "
                    "Priority actions focus on reducing turnaround time on idle wells, accelerating rig interventions, "
                    "and mitigating power disruption downtime.",
                    tone="warning",
                ),
                Bullets(
                    [
                        "Streamline rig mobilization and minimize waiting-on-rig durations to restore shut-in producers.",
                        "Accelerate high-potential workover candidates and water shut-off treatments across watered-out zones.",
                        "Reinforce electrical power backup systems and coordinate with regional grid authorities to limit tripping.",
                        "Enhance beam pump and artificial lift diagnostic testing to prevent early run life failures.",
                    ]
                ),
            ]
        )

    return blocks


def build(spec) -> list[Block]:
    """Build the document body blocks for document type D09."""
    if spec.meta.get("variant") == "legacy_study":
        return _build_legacy(spec)
    return _build_annual_review(spec)
