"""SOP library loader (D11). One YAML per intervention class: ``templates/sop/IC-NN.yaml``.

Schema (all strings digit-free; ``{slots}`` may reference D11 facts, see
``templates/slot_catalogue/D11.json``)::

    sop_id: SOP-IC-04            # must equal job_catalogue.sop_doc_id
    intervention_class: IC-04
    title: str
    purpose: str
    scope: str
    applicability: [str]         # diagnostic signatures that call for this class
    roles: [str]
    ppe_and_permits: [str]
    hazards: [{hazard: str, control: str}]
    pre_job_checks: [str]
    procedure: [{phase: str, steps: [str]}]     # rendered as numbered steps ("Step N")
    job_variants: {JOB_CODE: [str]}             # one entry per job_code of the class
    acceptance_criteria: [str]
    post_job: [str]
    lessons_learned: [str]
    references: [str]
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

SOP_DIR = Path(__file__).parent / "templates" / "sop"
REQUIRED = {
    "sop_id": str, "intervention_class": str, "title": str, "purpose": str, "scope": str,
    "applicability": list, "roles": list, "ppe_and_permits": list, "hazards": list, "pre_job_checks": list,
    "procedure": list, "job_variants": dict, "acceptance_criteria": list, "post_job": list,
    "lessons_learned": list, "references": list,
}


@lru_cache(maxsize=32)
def load_sop(ic: str) -> dict | None:
    p = SOP_DIR / f"{ic}.yaml"
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text())


def schema_problems(ic: str, data: dict | None, job_codes: list[str] | None = None) -> list[str]:
    if data is None:
        return [f"{ic}: templates/sop/{ic}.yaml missing"]
    probs = []
    for k, typ in REQUIRED.items():
        if k not in data:
            probs.append(f"{ic}: missing key {k!r}")
        elif not isinstance(data[k], typ):
            probs.append(f"{ic}: key {k!r} must be {typ.__name__}")
    if data.get("intervention_class") != ic:
        probs.append(f"{ic}: intervention_class mismatch ({data.get('intervention_class')})")
    for i, ph in enumerate(data.get("procedure") or []):
        if not isinstance(ph, dict) or not isinstance(ph.get("steps"), list) or not ph.get("phase"):
            probs.append(f"{ic}: procedure[{i}] needs phase + steps list")
    for i, hz in enumerate(data.get("hazards") or []):
        if not isinstance(hz, dict) or not hz.get("hazard") or not hz.get("control"):
            probs.append(f"{ic}: hazards[{i}] needs hazard + control")
    if job_codes:
        missing = sorted(set(job_codes) - set((data.get("job_variants") or {}).keys()))
        if missing:
            probs.append(f"{ic}: job_variants missing job codes {missing}")
    return probs
