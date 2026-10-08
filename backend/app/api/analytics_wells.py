"""Well-level analytics routes (SDD §13.2): ``GET /api/wells/{id}/attribution`` (TC-019, any persona).

Kept out of ``wells.py`` (Stage N/X) so Stage P owns only its own route. ``GLK-`` IDs are retired
(404 with a pointer to ``GK-``); unknown wells 404. Envelope ``{status, data, message, missing_fields,
provenance}`` (SDD §13.1); an INSUFFICIENT_HISTORY result is a 200 with that status (not an error).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent import rbac
from app.analytics.tools.attribution import attribute_decline
from app.analytics.tools.common import well_master_row

router = APIRouter()

RETIRED_DETAIL = "GLK- IDs retired in v0.4; use GK-"


@router.get("/wells/{well_id}/attribution")
def well_attribution(well_id: str, window_days: int = Query(180, ge=7, le=730),
                     persona: str = Depends(rbac.require("well.attribution"))):
    wid = well_id.strip().upper()
    if wid.startswith("GLK-"):
        raise HTTPException(status_code=404, detail=RETIRED_DETAIL)
    if well_master_row(wid) is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return rbac.redact(persona, "well.attribution", attribute_decline(well_id=wid, window_days=window_days).envelope())


# Stage Q (additive): TC-021 ML intervention classifier (SDD §13.4, BDD-F03-S01/S02/S05).
@router.get("/wells/{well_id}/classification")
def well_classification(well_id: str, top_k: int = Query(3, ge=1, le=15),
                        persona: str = Depends(rbac.require("well.diagnostics"))):
    from app.analytics.tools.intervention_classifier import classify_intervention

    wid = well_id.strip().upper()
    if wid.startswith("GLK-"):
        raise HTTPException(status_code=404, detail=RETIRED_DETAIL)
    if well_master_row(wid) is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return rbac.redact(persona, "well.diagnostics", classify_intervention(well_id=wid, top_k=top_k).envelope())


# Stage R (additive): TC-022 next best action + TC-027 counterfactual (SDD §9.1/9.2, §13.3/13.4).
def _as_of_or_422(as_of: str | None):
    """``as_of`` is honoured only when settings.ALLOW_AS_OF_OVERRIDE is truthy (SDD §13); else 422."""
    if not as_of:
        return None
    from datetime import date

    from app import settings

    if not settings.ALLOW_AS_OF_OVERRIDE:
        raise HTTPException(status_code=422, detail="as_of override disabled (ALLOW_AS_OF_OVERRIDE)")
    try:
        return date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(status_code=422, detail="as_of must be YYYY-MM-DD")


def _known_well_or_404(well_id: str) -> str:
    wid = well_id.strip().upper()
    if wid.startswith("GLK-"):
        raise HTTPException(status_code=404, detail=RETIRED_DETAIL)
    if well_master_row(wid) is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return wid


@router.get("/wells/{well_id}/nba")
def well_next_best_action(well_id: str, top_k: int = Query(3, ge=1, le=5), as_of: str | None = None,
                          persona: str = Depends(rbac.require("well.nba"))):
    from app.analytics.tools.nba import recommend_next_best_action

    wid = _known_well_or_404(well_id)
    env = recommend_next_best_action(wid, as_of=_as_of_or_422(as_of), top_k=top_k).envelope()
    return rbac.redact(persona, "well.nba", env)


@router.get("/wells/{well_id}/recommendations")
def well_recommendations(well_id: str, k: int = Query(3, ge=1, le=5), as_of: str | None = None,
                         persona: str = Depends(rbac.require("well.nba"))):
    """TC-030 (v0.5): top-k with P(success), analogs, drivers, architecture (multimodal engine, D-32)."""
    from app.analytics.tools.success_engine import recommend_interventions

    wid = _known_well_or_404(well_id)
    return rbac.redact(persona, "well.nba", recommend_interventions(wid, as_of=_as_of_or_422(as_of), k=k))


@router.get("/wells/{well_id}/similar")
def well_similar(well_id: str, ic: str = Query(..., alias="class", min_length=4), as_of: str | None = None,
                 persona: str = Depends(rbac.require("well.nba"))):
    """TC-031 (v0.5): look-alike wells that ran the same intervention class, with outcomes."""
    from app.analytics.tools.success_engine import similar_wells

    wid = _known_well_or_404(well_id)
    return similar_wells(wid, ic.strip().upper(), as_of=_as_of_or_422(as_of))


@router.get("/wells/{well_id}/compare")
def well_compare(well_id: str, alternative: str = Query(..., min_length=1), recommended: str | None = None,
                 as_of: str | None = None, persona: str = Depends(rbac.require("well.nba"))):
    from app.analytics.tools.counterfactual import compare_interventions

    wid = _known_well_or_404(well_id)
    env = compare_interventions(wid, recommended_job=recommended or None, alternative_job=alternative,
                                as_of=_as_of_or_422(as_of)).envelope()
    return rbac.redact(persona, "well.nba", env)
