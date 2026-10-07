"""Standard Operating Procedure template (D11).

One document per intervention class IC-01..IC-14 (doc_id SOP-IC-NN, asset-wide, field 'ALL').
Procedural content is loaded from YAML via app.analytics.docs_pdf.sop.load_sop.
"""
from __future__ import annotations

from app.analytics.docs_pdf.ir import Bullets, Callout, DocSpec, H, KV, P, Signoff, Table
from app.analytics.docs_pdf.sop import load_sop

JOB_CODE_COLUMNS = [
    ("job_code", "Job code"),
    ("job_name", "Job name"),
    ("equipment", "Equipment"),
    ("requires_rig", "Rig required"),
    ("est_days", "Est days"),
    ("cost_band", "Cost band"),
    ("selection_evidence", "Selection criteria"),
]

FIELD_STAT_COLUMNS = [
    ("field", "Field"),
    ("jobs", "Jobs"),
    ("success_pct", "Success rate"),
    ("median_rig_days", "Median rig days"),
    ("median_uplift_bopd", "Median uplift BOPD"),
    ("median_run_life_days", "Median run life days"),
    ("failed", "Failed jobs"),
]

FAILURE_MODE_COLUMNS = [
    ("failure_code", "Failure code"),
    ("failed_jobs", "Failed jobs"),
]

SIGNOFF_ROLES = [
    "Prepared by (Well Services)",
    "Reviewed by (HSE)",
    "Approved by (Asset Manager)",
]


def build(spec: DocSpec):
    ic = str(spec.raw.get("intervention_class") or spec.facts.get("intervention_class") or "")
    sop = load_sop(ic) if ic else None

    blocks = [
        H("Document control"),
        KV(
            [
                ("Document reference", "{doc_id}"),
                ("Intervention class", "{intervention_class}"),
                ("Class description", "{ic_label}"),
                ("Effective date", "{doc_date}"),
                ("Catalogue job codes", "{n_job_codes}"),
                ("Standard equipment", "{equipment_list}"),
                ("Rig required", "{requires_rig_any}"),
                ("Estimated duration", "{est_days_min} to {est_days_max} days"),
            ],
            cols=2,
        ),
    ]

    if sop is None:
        blocks.append(
            Callout(
                "Standard operating procedure text for this intervention class is currently in drafting and pending formal engineering review. Catalogue parameters and field history are provided below.",
                tone="warning",
            )
        )
        blocks.append(H("Catalogue job codes covered"))
        blocks.append(Table("job_codes", JOB_CODE_COLUMNS, title="Catalogue job codes"))
    else:
        # Purpose
        if sop.get("purpose"):
            blocks.append(H("Purpose"))
            blocks.append(P(sop["purpose"]))

        # Scope
        if sop.get("scope"):
            blocks.append(H("Scope"))
            blocks.append(P(sop["scope"]))

        # Applicability + Job codes covered table
        blocks.append(H("Applicability"))
        if sop.get("applicability"):
            blocks.append(Bullets(sop["applicability"]))
        blocks.append(Table("job_codes", JOB_CODE_COLUMNS, title="Job codes covered"))

        # Roles
        if sop.get("roles"):
            blocks.append(H("Roles"))
            blocks.append(Bullets(sop["roles"]))

        # PPE and permits
        if sop.get("ppe_and_permits"):
            blocks.append(H("PPE and permits"))
            blocks.append(Bullets(sop["ppe_and_permits"]))

        # Hazards and controls
        if sop.get("hazards"):
            hazard_pairs = [
                (str(hz["hazard"]), str(hz["control"]))
                for hz in sop["hazards"]
                if isinstance(hz, dict) and hz.get("hazard") and hz.get("control")
            ]
            if hazard_pairs:
                blocks.append(H("Hazards and controls"))
                blocks.append(KV(hazard_pairs, cols=1))

        # Pre-job checks
        if sop.get("pre_job_checks"):
            blocks.append(H("Pre-job checks"))
            blocks.append(Bullets(sop["pre_job_checks"]))

        # Procedure
        if sop.get("procedure"):
            blocks.append(H("Procedure"))
            for phase in sop["procedure"]:
                if isinstance(phase, dict) and phase.get("phase") and phase.get("steps"):
                    blocks.append(H(str(phase["phase"]), level=2))
                    steps = phase["steps"]
                    if isinstance(steps, list):
                        blocks.append(Bullets(steps, numbered=True))
                    elif isinstance(steps, str):
                        blocks.append(Bullets([steps], numbered=True))

        # Job-code variants
        if sop.get("job_variants") and isinstance(sop["job_variants"], dict):
            blocks.append(H("Job-code variants"))
            for code, steps in sop["job_variants"].items():
                if steps:
                    blocks.append(H(str(code), level=2))
                    if isinstance(steps, list):
                        blocks.append(Bullets(steps))
                    elif isinstance(steps, str):
                        blocks.append(Bullets([steps]))

        # Acceptance criteria
        if sop.get("acceptance_criteria"):
            blocks.append(H("Acceptance criteria"))
            blocks.append(Bullets(sop["acceptance_criteria"]))

        # Post-job
        if sop.get("post_job"):
            blocks.append(H("Post-job"))
            blocks.append(Bullets(sop["post_job"]))

    # Field performance of this class
    blocks.append(H("Field performance of this class"))
    blocks.append(Table("field_stats", FIELD_STAT_COLUMNS, title="Historical field performance"))
    blocks.append(
        KV(
            [
                ("Total interventions across fields", "{jobs_all_fields}"),
                ("Overall class success rate", "{success_pct_all}"),
                ("Asset median rig days", "{median_rig_days_all}"),
                ("Asset median oil uplift", "{median_uplift_all} BOPD"),
            ],
            cols=2,
        )
    )
    blocks.append(Table("failure_modes", FAILURE_MODE_COLUMNS, title="Primary historical failure modes"))

    if sop is not None:
        # Lessons learned
        if sop.get("lessons_learned"):
            blocks.append(H("Lessons learned"))
            blocks.append(Bullets(sop["lessons_learned"]))

        # References
        if sop.get("references"):
            blocks.append(H("References"))
            blocks.append(Bullets(sop["references"]))

    # Signoff
    blocks.append(Signoff(SIGNOFF_ROLES))

    return blocks
