"""WellPulse deterministic analytics tools (SDD §6): the only source of numbers for REST, text and voice.

TC-001…TC-018 are the data-driven port of the ADK v0.3.0 tools (Stage P); TC-019 / TC-020 are new.
"""

from .arps_decline import fit_decline_curve
from .attribution import attribute_decline
from .candidate_ranking import (
    check_mro,
    check_offsets,
    detect_mechanical_signature,
    estimate_uplift,
    fillage_proxy,
    generate_draft_plan,
    generate_report,
    plot_production,
    predict_failure,
    query_wells,
    rank_candidates,
    route_intervention,
    schedule_rigs,
    search_well_history,
    trigger_scan,
)
from .chan_diagnostic import chan_diagnostic
from .common import ToolResult, ToolStatus, reset_caches
from .health import classify_well_health
from .render_well_map import render_well_map

__all__ = [
    "fit_decline_curve",          # TC-001
    "chan_diagnostic",            # TC-002
    "fillage_proxy",              # TC-003
    "check_offsets",              # TC-004
    "detect_mechanical_signature",  # TC-005
    "predict_failure",            # TC-006
    "trigger_scan",               # TC-007
    "route_intervention",         # TC-008
    "estimate_uplift",            # TC-009
    "rank_candidates",            # TC-010
    "check_mro",                  # TC-011
    "search_well_history",        # TC-012
    "generate_draft_plan",        # TC-013
    "generate_report",            # TC-014
    "schedule_rigs",              # TC-015
    "render_well_map",            # TC-016
    "plot_production",            # TC-017
    "query_wells",                # TC-018
    "attribute_decline",          # TC-019
    "classify_well_health",       # TC-020
    "ToolResult",
    "ToolStatus",
    "reset_caches",
]
