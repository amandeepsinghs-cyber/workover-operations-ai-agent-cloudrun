"""D05 Cement Bond Log (CBL) interpretation summary template."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import Bullets, Callout, H, KV, P, Table


def build(spec):
    if spec.has("trigger_workover_id"):
        trigger_par = P(
            "This log was run ahead of workover {trigger_workover_id} ({trigger_job_code}); the job history below "
            "covers only operations before the log date."
        )
    else:
        trigger_par = P(
            "No workover is linked to this log run in the source tables; the job history below covers only "
            "operations before the log date."
        )
    blocks = [
        H("Log identification and wellbore geometry"),
        KV(
            [
                ("Log survey date", "{log_date}"),
                ("Well identifier", "{well_id}"),
                ("Production casing string", "{prod_casing_od_in} in, {prod_casing_weight_ppf} ppf, {prod_casing_grade}"),
                ("Logged depth interval", "{cement_top_m} m to {log_bottom_m} m"),
                ("Cemented column length", "{cemented_length_m} m"),
                ("Production casing shoe", "{prod_casing_shoe_m} m"),
            ],
            cols=2,
        ),
        trigger_par,
        KV(
            [
                ("Isolation assessment", "{isolation_assessment}"),
                ("Assessment basis", "{assessment_basis}"),
            ],
            cols=2,
        ),
        H("Cement column and zonal barrier summary"),
        KV(
            [
                ("Top of cement depth", "{cement_top_m} m"),
                ("Top perforation depth", "{perf_top_m} m"),
                ("Cement column above perforations", "{cement_above_perf_m} m"),
                ("Target zone formation top", "{zone_top_md_m} m MD"),
                ("Current production zone", "{current_zone}"),
                ("Target zone lithology", "{zone_lithology}"),
            ],
            cols=2,
        ),
        H("Cement bond evaluation and isolation assessment"),
        P(
            "This evaluation provides a qualitative cement bond and zonal isolation summary for well {well_id}. "
            "In the absence of recorded acoustic amplitude or bond index logs, this interpretation is qualitative; "
            "assessment derived from cement top versus top perforation and the well's water-control history. "
            "Zonal barrier integrity is evaluated relative to the {current_zone} formation top ({zone_top_md_m} m MD) "
            "and perforation interval top ({perf_top_m} m)."
        ),
    ]

    if spec.is_("isolation_assessment", "POOR"):
        blocks.append(
            P(
                "The recorded top of cement ({cement_top_m} m) provides inadequate barrier coverage above the perforated interval "
                "({perf_top_m} m), resulting in {cement_above_perf_m} m of effective cement column above the perforations. "
                "Without sufficient annular seal above the pay zone, the wellbore exhibits severe risk of inter-zonal communication, "
                "channeling, and premature water breakthrough from adjacent water-bearing sands."
            )
        )
        blocks.append(
            Callout(
                "Zonal isolation assessment: POOR. Cement coverage above top perforation ({cement_above_perf_m} m) is insufficient "
                "to guarantee hydraulic isolation for {current_zone}. Annular fluid movement is anticipated.",
                tone="danger",
            )
        )
        rec_bullets = [
            "Prioritize candidate evaluation for remedial cement squeeze across {current_zone} before undertaking further production stimulation.",
            "Perform high-resolution ultrasonic radial cement bond logging following remedial squeeze to verify barrier restoration.",
            "Monitor surface annulus pressure and production water cut on routine surveillance cycles to detect fluid migration.",
        ]
    elif spec.is_("isolation_assessment", "QUESTIONABLE") and spec.is_("assessment_basis", "LOG_REMARK_MICRO_ANNULUS"):
        blocks.append(
            P(
                "The cement column extends {cement_above_perf_m} m above the top perforation depth ({perf_top_m} m), placing the top "
                "of cement at {cement_top_m} m. The log remarks nevertheless record a micro-annulus between the production casing and "
                "the cement sheath. A micro-annulus can provide a path for water to migrate along the pipe into the perforated interval "
                "even where the nominal cement column is long."
            )
        )
        blocks.append(
            Callout(
                "Zonal isolation assessment: QUESTIONABLE (basis: {assessment_basis}). A nominal cement column of {cement_above_perf_m} m "
                "is present above the perforations, but the logged micro-annulus means hydraulic isolation cannot be assumed.",
                tone="warning",
            )
        )
        rec_bullets = [
            "Treat any future rise in water cut on this well as a possible behind-pipe channel before selecting a water shut-off method.",
            "Evaluate a remedial cement squeeze, rather than an inside-casing mechanical isolation, if water shut-off becomes necessary.",
            "Establish regular annulus pressure monitoring to detect channeling behind the production casing string.",
        ]
    elif spec.is_("isolation_assessment", "QUESTIONABLE"):
        blocks.append(
            P(
                "The cement column extends {cement_above_perf_m} m above the top perforation depth ({perf_top_m} m), placing the top "
                "of cement at {cement_top_m} m. However, well records before this log document {n_water_jobs_failed} failed water-control or integrity "
                "operations out of {n_water_jobs} such jobs. The recurrence of water ingress after intervention "
                "indicates probable micro-annular channeling or localized degradation of the cement sheath behind the production casing."
            )
        )
        blocks.append(
            Callout(
                "Zonal isolation assessment: QUESTIONABLE (basis: {assessment_basis}). Although a nominal cement column of {cement_above_perf_m} m is present above "
                "perforations, the record of {n_water_jobs_failed} failed water-control or integrity jobs suggests persistent annular leakage or channeling.",
                tone="warning",
            )
        )
        rec_bullets = [
            "Run advanced diagnostic acoustic and radial cement evaluation before approving subsequent water shut-off interventions.",
            "Review historical water shut-off job execution logs to evaluate mechanical bridge plug isolation versus chemical resin shut-off options.",
            "Establish regular annulus pressure monitoring to detect channeling behind the production casing string.",
        ]
    else:
        blocks.append(
            P(
                "A continuous cement column of {cement_above_perf_m} m is established above the topmost perforation ({perf_top_m} m), "
                "extending upwards to {cement_top_m} m. Well records show {n_water_jobs} water-control or integrity operations with "
                "{n_water_jobs_failed} recorded failures, indicating competent annular containment and effective zonal isolation across the {current_zone} interval."
            )
        )
        blocks.append(
            Callout(
                "Zonal isolation assessment: ADEQUATE. Cement column of {cement_above_perf_m} m above perforations provides competent hydraulic "
                "barrier across {current_zone} without recorded remedial shut-off failures.",
                tone="success",
            )
        )
        rec_bullets = [
            "Maintain regular production surveillance and fluid level tracking under existing lift parameters.",
            "No immediate remedial cementation or casing repair required for zonal isolation across {current_zone}.",
            "Retain baseline cement top and zonal isolation documentation for subsequent workover planning.",
        ]

    blocks.extend(
        [
            H("Subsurface intervals and geological formations"),
            P(
                "Recorded perforation intervals in {current_zone} are summarized below, alongside geological formation tops "
                "identified from open-hole logs during well construction."
            ),
            Table(
                "perfs",
                [
                    ("zone", "Zone"),
                    ("top_m", "Top (m)"),
                    ("bottom_m", "Bottom (m)"),
                    ("spf", "SPF"),
                    ("perf_date", "Date"),
                    ("status", "Status"),
                ],
                title="Perforation intervals",
                max_rows=6,
            ),
            Table(
                "formations",
                [
                    ("formation", "Formation"),
                    ("top_md_m", "Top (m MD)"),
                    ("bottom_md_m", "Bottom (m MD)"),
                    ("lithology", "Lithology"),
                ],
                title="Formation tops and lithology",
                max_rows=8,
            ),
            H("Water-control and wellbore integrity history"),
            P(
                "Before this log, intervention records show {n_water_jobs} water-control and integrity operations on "
                "{well_id}, with {n_water_jobs_failed} failed attempts recorded. Operational outcomes and job classifications are detailed below:"
            ),
            Table(
                "water_jobs",
                [
                    ("workover_id", "Workover ID"),
                    ("start_date", "Date"),
                    ("catalogue_job_code", "Job type"),
                    ("failure_code", "Failure reason"),
                    ("pre_job_oil_bopd", "Pre-job BOPD"),
                    ("post_job_oil_bopd", "Post-job BOPD"),
                    ("outcome", "Outcome"),
                ],
                title="Intervention history (water shut-off and casing repair)",
                max_rows=8,
                empty_text="No prior water-control or integrity remediation operations recorded for this well.",
            ),
            H("Engineering recommendations and integrity surveillance"),
            Bullets(rec_bullets),
        ]
    )

    return blocks
