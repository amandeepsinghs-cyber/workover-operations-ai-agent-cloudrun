"""Minimal three-persona RBAC, enforced at the tool / route layer (SDD §16, F-16, D-8, Stage Y).

Anchor (T2): *"if an Executive Director is asking for a particular data versus a field engineer is asking
for a data, what that data can be? … If it is overcomplicating, we can leave it"*.

**Design.** One capability matrix in code (no YAML). Every gate goes through this module:

* REST: ``Depends(rbac.require("field.aggregate"))`` → the resolved persona, or **403**
  ``{status:"UNAVAILABLE", data:null, message:"not permitted for persona FIELD_ENGINEER: field.aggregate", …}``
  (handler registered by :func:`install`). ``X-Persona`` missing → ``ASSET_MANAGER`` (back-compat, SDD §13.1);
  an unknown value → **400** with the same envelope.
* Agent / ADK tool wrappers (Stage V): ``@rbac.gated("field.aggregate")`` on the wrapper; the persona comes
  from :func:`persona_scope` (runner sets it from session state). A denied call returns
  ``ToolResult(UNAVAILABLE, value=None, message="not permitted for persona …: <capability>")`` — the reason
  names the capability only, never data (no leak in the error).
* Live voice: ``app.live.voice_tools`` asks :func:`voice_gate` / :func:`voice_tool_visible`.
* Documents: :func:`doc_type_allowed` (D04 tally / D05 CBL need full ``well.construction``; D10 monthly
  field production report needs ``field.aggregate``; D09 rig schedule needs ``queue.read``).
* Value redaction: :func:`redact` drops ``cost_band`` for FIELD_ENGINEER and turns construction tallies into
  a summary for ED.

**Not a security boundary** (SDD §16.1): the demo persona is a UI switch. Production would map
``X-Goog-Authenticated-User-Email`` (IAP) to a persona via Google Groups.

"Own cluster" (FIELD_ENGINEER on ``field.health`` / ``queue.read``) = the ``cluster_id`` the client sends (the
cluster of the selected well), else the cluster of a given ``well_id``, else env ``WELLPULSE_FE_CLUSTER``;
with none of these the call is denied with a hint. If ``WELLPULSE_FE_CLUSTER`` is set, other clusters are denied.
"""

from __future__ import annotations

import contextvars
import functools
import inspect
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum
from typing import Any

from fastapi import Header, Request
from fastapi.responses import JSONResponse

# ------------------------------------------------------------------------------------------------
# personas
# ------------------------------------------------------------------------------------------------
ED = "ED"
ASSET_MANAGER = "ASSET_MANAGER"
FIELD_ENGINEER = "FIELD_ENGINEER"
PERSONAS: tuple[str, ...] = (ED, ASSET_MANAGER, FIELD_ENGINEER)
DEFAULT_PERSONA = ASSET_MANAGER

PERSONA_LABELS = {
    ED: "Executive Director",
    ASSET_MANAGER: "Asset Manager / Production Engineer",
    FIELD_ENGINEER: "Field Engineer",
}
# Production Engineer maps to ASSET_MANAGER (features.md F-16, D-8).
PERSONA_ALIASES = {
    "ED": ED, "EXECUTIVE_DIRECTOR": ED, "EXECUTIVE DIRECTOR": ED, "EXEC": ED,
    "ASSET_MANAGER": ASSET_MANAGER, "AM": ASSET_MANAGER, "ASSET MANAGER": ASSET_MANAGER,
    "PE": ASSET_MANAGER, "PRODUCTION_ENGINEER": ASSET_MANAGER, "PRODUCTION ENGINEER": ASSET_MANAGER,
    "FIELD_ENGINEER": FIELD_ENGINEER, "FE": FIELD_ENGINEER, "FIELD ENGINEER": FIELD_ENGINEER,
}


class Access(str, Enum):
    FULL = "FULL"
    SUMMARY = "SUMMARY"  # allowed, value redacted to a summary (ED: construction without tallies)
    OWN_CLUSTER = "OWN_CLUSTER"  # allowed only scoped to the persona's own cluster (read-only)
    NONE = "NONE"


F, S, OC, N = Access.FULL, Access.SUMMARY, Access.OWN_CLUSTER, Access.NONE

# ------------------------------------------------------------------------------------------------
# capability matrix (SDD §16.2) — the single source of truth
# ------------------------------------------------------------------------------------------------
CAPABILITIES: dict[str, dict[str, Any]] = {
    "field.aggregate": {"desc": "Field roll-ups: field history, field comparison", "tools": ["TC-024", "TC-028"],
                        "routes": ["/api/fields/history", "/api/fields/{field}/history", "/api/fields/compare"]},
    "field.attribution": {"desc": "Decline attribution roll-up for a field / cluster", "tools": ["TC-019 (field)"],
                          "routes": ["/api/fields/{field}/attribution"]},
    "well.attribution": {"desc": "Decline attribution for one well", "tools": ["TC-019 (well)"],
                         "routes": ["/api/wells/{id}/attribution"]},
    "field.health": {"desc": "Health buckets (TC-020)", "tools": ["TC-020"], "routes": ["/api/fields/{field}/health"]},
    "queue.read": {"desc": "Candidate / priority queues, rig schedule", "tools": ["TC-010", "TC-015", "TC-018"],
                   "routes": ["/api/fields/{field}/priority"]},
    "well.diagnostics": {"desc": "Single-well diagnostics + ML classifier", "tools": [f"TC-{i:03d}" for i in range(1, 10)] + ["TC-021"],
                         "routes": ["/api/wells/{id}/classification"]},
    "well.nba": {"desc": "Next best action and counterfactual", "tools": ["TC-022", "TC-027"],
                 "routes": ["/api/wells/{id}/nba", "/api/wells/{id}/compare", "/api/wells/{id}/recommendations"]},
    "well.construction": {"desc": "Well profile / construction; D01, D04, D05", "tools": ["TC-029"],
                          "routes": ["/api/wells/{id}/profile"]},
    "docs.sop_dossier": {"desc": "Documents, SOPs, dossier", "tools": ["TC-023", "TC-026"],
                         "routes": ["/api/docs/*", "/api/wells/{id}/documents", "/api/wells/{id}/dossier"]},
    "cost_band.view": {"desc": "cost_band in any tool return (bands only, never currency)", "tools": ["*"], "routes": ["*"]},
    "live.voice": {"desc": "Gemini Live voice", "tools": [], "routes": ["/ws/live"]},
    # derived (not a row in SDD §16.2, whose routes are 'any'): asset hierarchy, map, KPIs, production series
    "asset.overview": {"desc": "Asset hierarchy, multi-field map, KPI header, single-well production series",
                       "tools": ["TC-016", "TC-017", "TC-025"],
                       "routes": ["/api/fields", "/api/fields/map", "/api/wells/kpis", "/api/wells/{id}/production"]},
}

MATRIX: dict[str, dict[str, Access]] = {
    #                      ED   AM  FE
    "field.aggregate":   {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: N},
    "field.attribution": {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: N},
    "well.attribution":  {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: F},
    "field.health":      {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: OC},
    "queue.read":        {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: OC},
    "well.diagnostics":  {ED: S, ASSET_MANAGER: F, FIELD_ENGINEER: F},
    "well.nba":          {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: F},
    "well.construction": {ED: S, ASSET_MANAGER: F, FIELD_ENGINEER: F},
    "docs.sop_dossier":  {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: F},
    "cost_band.view":    {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: N},
    "live.voice":        {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: F},
    "asset.overview":    {ED: F, ASSET_MANAGER: F, FIELD_ENGINEER: F},
}
assert set(MATRIX) == set(CAPABILITIES), "capability matrix and catalogue disagree"

# Tool contract → capability (SDD §6 / §16.2). TC-019 depends on scope (well vs field).
TOOL_CAPABILITY: dict[str, str] = {
    **{f"TC-{i:03d}": "well.diagnostics" for i in range(1, 10)},
    "TC-010": "queue.read", "TC-015": "queue.read", "TC-018": "queue.read",
    "TC-016": "asset.overview", "TC-017": "asset.overview", "TC-025": "asset.overview",
    "TC-019": "field.attribution",  # well scope → well.attribution (see capability_for_tool)
    "TC-020": "field.health", "TC-021": "well.diagnostics",
    "TC-022": "well.nba", "TC-027": "well.nba",
    "TC-023": "docs.sop_dossier", "TC-026": "docs.sop_dossier",
    "TC-024": "field.aggregate", "TC-028": "field.aggregate",
    "TC-029": "well.construction",
}

# Document type → (capability, minimum access). Everything else → docs.sop_dossier.
DOC_TYPE_RULES: dict[str, tuple[str, Access]] = {
    "D04": ("well.construction", F),  # wellbore schematic + casing / tubing tally (raw tallies)
    "D05": ("well.construction", F),  # cement bond log (casing tally detail)
    "D09": ("queue.read", OC),        # field rig schedule
    "D10": ("field.aggregate", F),    # monthly field production report (field roll-up)
}

COST_KEYS = frozenset({"cost_band", "cost_band_mix"})
_ACCESS_RANK = {N: 0, OC: 1, S: 2, F: 3}


# ------------------------------------------------------------------------------------------------
# errors
# ------------------------------------------------------------------------------------------------
class PermissionDenied(Exception):
    """Raised by REST dependencies; :func:`install` maps it to the UNAVAILABLE envelope (403)."""

    status_code = 403

    def __init__(self, persona: str, capability: str, detail: str = ""):
        self.persona, self.capability, self.detail = persona, capability, detail
        super().__init__(denial_message(persona, capability, detail))

    def envelope(self) -> dict[str, Any]:
        return denied_envelope(self.persona, self.capability, self.detail)


class UnknownPersona(PermissionDenied):
    status_code = 400

    def __init__(self, raw: str):
        self.raw = raw
        Exception.__init__(self, self.message())
        self.persona, self.capability, self.detail = raw, "", ""

    def message(self) -> str:
        return f"unknown persona {self.raw!r}; expected one of {', '.join(PERSONAS)}"

    def envelope(self) -> dict[str, Any]:
        return {"status": "UNAVAILABLE", "data": None, "message": self.message(), "missing_fields": ["persona"],
                "provenance": {"rbac": {"personas": list(PERSONAS)}}}


# ------------------------------------------------------------------------------------------------
# persona resolution
# ------------------------------------------------------------------------------------------------
def normalize_persona(raw: str | None) -> str | None:
    """Canonical persona for ``raw`` (aliases allowed), or None when unknown / empty."""
    if raw is None:
        return None
    key = str(raw).strip().upper().replace("-", "_")
    if not key:
        return None
    return PERSONA_ALIASES.get(key) or PERSONA_ALIASES.get(key.replace("_", " "))


def resolve_persona(raw: str | None, *, strict: bool = False) -> str:
    """Missing → ``DEFAULT_PERSONA``. Unknown → :class:`UnknownPersona` when ``strict`` else the default."""
    if raw is None or not str(raw).strip():
        return DEFAULT_PERSONA
    p = normalize_persona(raw)
    if p is None:
        if strict:
            raise UnknownPersona(str(raw))
        return DEFAULT_PERSONA
    return p


_current: contextvars.ContextVar[str | None] = contextvars.ContextVar("wellpulse_persona", default=None)


@contextmanager
def persona_scope(persona: str | None) -> Iterator[str]:
    """Set the persona for tool wrappers in this context (the Stage V runner wraps each turn)."""
    p = resolve_persona(persona)
    token = _current.set(p)
    try:
        yield p
    finally:
        _current.reset(token)


def current_persona() -> str:
    return _current.get() or DEFAULT_PERSONA


# ------------------------------------------------------------------------------------------------
# matrix queries
# ------------------------------------------------------------------------------------------------
def access(persona: str | None, capability: str) -> Access:
    if capability not in MATRIX:
        raise ValueError(f"unknown capability {capability!r}")
    return MATRIX[capability][resolve_persona(persona)]


def allowed(persona: str | None, capability: str) -> bool:
    return access(persona, capability) is not Access.NONE


def capabilities_for(persona: str | None) -> dict[str, Any]:
    """Payload of ``GET /api/me/capabilities`` (UI hint only; enforcement is server-side)."""
    p = resolve_persona(persona)
    acc = {c: MATRIX[c][p].value for c in MATRIX}
    return {
        "persona": p,
        "label": PERSONA_LABELS[p],
        "default_persona": DEFAULT_PERSONA,
        "capabilities": [c for c, a in acc.items() if a != Access.NONE.value],
        "denied": [c for c, a in acc.items() if a == Access.NONE.value],
        "access": acc,
        "denied_doc_types": denied_doc_types(p),
        "own_cluster": (os.getenv("WELLPULSE_FE_CLUSTER") or None) if p == FIELD_ENGINEER else None,
        "personas": [{"id": x, "label": PERSONA_LABELS[x]} for x in PERSONAS],
        "matrix": {c: {x: MATRIX[c][x].value for x in PERSONAS} for c in MATRIX},
        "security_note": "demo persona switch (SDD §16.1); not a security boundary",
    }


def capability_for_tool(tool_id: str, *, well_scope: bool = False) -> str:
    tid = tool_id.strip().upper()
    if tid == "TC-019" and well_scope:
        return "well.attribution"
    if tid not in TOOL_CAPABILITY:
        raise ValueError(f"no capability mapped for tool {tool_id!r}")
    return TOOL_CAPABILITY[tid]


def denial_message(persona: str, capability: str, detail: str = "") -> str:
    msg = f"not permitted for persona {persona}: {capability}"
    return f"{msg} ({detail})" if detail else msg


def denied_envelope(persona: str, capability: str, detail: str = "") -> dict[str, Any]:
    """REST / voice denial body. Carries the reason only — never partial data (Gate Y)."""
    return {"status": "UNAVAILABLE", "data": None, "message": denial_message(persona, capability, detail),
            "missing_fields": [], "provenance": {"rbac": {"persona": persona, "capability": capability}}}


def denied(persona: str, capability: str, detail: str = ""):
    """Denied tool return: ``ToolResult(UNAVAILABLE, None, …)`` (SDD §16.2)."""
    from app.analytics.tools.common import ToolResult, ToolStatus

    return ToolResult(ToolStatus.UNAVAILABLE, None, [], denial_message(persona, capability, detail),
                      {"rbac": {"persona": persona, "capability": capability}})


# ------------------------------------------------------------------------------------------------
# own-cluster scoping
# ------------------------------------------------------------------------------------------------
def _cluster_of_well(well_id: str | None) -> str | None:
    if not well_id:
        return None
    try:
        from app.analytics.tools.common import well_master_row

        row = well_master_row(str(well_id).strip().upper())
    except Exception:  # noqa: BLE001 - unknown well → no cluster
        return None
    return (row or {}).get("cluster_id") or None


def scope_cluster(persona: str | None, capability: str, cluster_id: str | None = None,
                  well_id: str | None = None) -> str | None:
    """Return the cluster to use. Unchanged unless the persona's access is OWN_CLUSTER; then a cluster is
    mandatory and must equal ``WELLPULSE_FE_CLUSTER`` when that is set. Raises :class:`PermissionDenied`."""
    p = resolve_persona(persona)
    a = access(p, capability)
    if a is Access.NONE:
        raise PermissionDenied(p, capability)
    if a is not Access.OWN_CLUSTER:
        return cluster_id
    fixed = (os.getenv("WELLPULSE_FE_CLUSTER") or "").strip() or None
    c = (cluster_id or "").strip() or _cluster_of_well(well_id) or fixed
    if not c:
        raise PermissionDenied(p, capability, "limited to own cluster; pass cluster_id of the selected well")
    if fixed and c.upper() != fixed.upper():
        raise PermissionDenied(p, capability, f"limited to own cluster {fixed}")
    return c


# ------------------------------------------------------------------------------------------------
# value redaction
# ------------------------------------------------------------------------------------------------
def _strip_keys(obj: Any, keys: frozenset[str]) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_keys(v, keys) for k, v in obj.items() if k not in keys}
    if isinstance(obj, list):
        return [_strip_keys(x, keys) for x in obj]
    return obj


def summarize_construction(c: Any) -> Any:
    """ED view of TC-029 construction: sizes, string count, perforated zones — no casing / tubing tallies."""
    if not isinstance(c, dict) or not ({"casing", "tubing"} & set(c)):
        return c
    perfs = c.get("perfs") or []
    return {
        "casing_size_in": c.get("casing_size_in"),
        "tubing_size_in": c.get("tubing_size_in"),
        "casing_strings": len(c.get("casing") or []),
        "tubing_components": len(c.get("tubing") or []),
        "perf_zones": sorted({p.get("zone") for p in perfs if isinstance(p, dict) and p.get("zone")}),
        "open_perf_intervals": sum(1 for p in perfs if isinstance(p, dict) and p.get("status") == "OPEN"),
        "tallies_redacted": True,
        "redaction": "construction summary for ED (no tallies) — SDD §16.2 well.construction",
    }


def redact(persona: str | None, capability: str | None, value: Any) -> Any:
    """Apply value-level rules to a JSON-safe value (dict / list): FE loses ``cost_band``; ED gets a
    construction summary when the capability is ``well.construction``."""
    p = resolve_persona(persona)
    out = value
    if capability == "well.construction" and access(p, capability) is Access.SUMMARY and isinstance(out, dict):
        if "construction" in out:
            out = {**out, "construction": summarize_construction(out["construction"])}
        elif isinstance(out.get("data"), dict) and "construction" in out["data"]:
            out = {**out, "data": {**out["data"], "construction": summarize_construction(out["data"]["construction"])}}
    if not allowed(p, "cost_band.view"):
        out = _strip_keys(out, COST_KEYS)
    return out


def redact_tool_result(persona: str | None, capability: str | None, result: Any) -> Any:
    """ToolResult → ToolResult with a redacted (JSON-safe) value; dicts pass through :func:`redact`."""
    from app.analytics.tools.common import ToolResult, to_jsonable

    if isinstance(result, ToolResult):
        if result.value is None:
            return result
        return ToolResult(result.status, redact(persona, capability, to_jsonable(result.value)),
                          result.missing_fields, result.message, result.provenance)
    if isinstance(result, (dict, list)):
        return redact(persona, capability, result)
    return result


# ------------------------------------------------------------------------------------------------
# tool-wrapper decorator (Stage V ADK wrappers, voice, tests)
# ------------------------------------------------------------------------------------------------
CapabilitySpec = str | Callable[[dict[str, Any]], str]


def _cap(spec: CapabilitySpec, kwargs: dict[str, Any]) -> str:
    return spec(kwargs) if callable(spec) else spec


def attribution_capability(kwargs: dict[str, Any]) -> str:
    """TC-019: well scope → ``well.attribution``; field / cluster scope → ``field.attribution``."""
    return "well.attribution" if (kwargs.get("well_id") or "").strip() else "field.attribution"


def check_call(persona: str | None, capability: str, kwargs: dict[str, Any],
               params: set[str] | None = None) -> tuple[dict[str, Any], str | None]:
    """Gate one call. Returns ``(kwargs, None)`` (kwargs possibly with ``cluster_id`` scoped) or
    ``(kwargs, denial_detail)`` where detail is '' for a plain denial."""
    p = resolve_persona(persona)
    a = access(p, capability)
    if a is Access.NONE:
        return kwargs, ""
    if a is Access.OWN_CLUSTER:
        accepts_cluster = params is None or "cluster_id" in params
        if accepts_cluster:
            try:
                c = scope_cluster(p, capability, kwargs.get("cluster_id"), kwargs.get("well_id"))
            except PermissionDenied as e:
                return kwargs, e.detail
            return {**kwargs, "cluster_id": c}, None
        if (kwargs.get("well_id") or "").strip():
            return kwargs, None  # single-well call inside the persona's remit
        return kwargs, "limited to own cluster; ask about a well or a cluster"
    return kwargs, None


def gated(capability: CapabilitySpec, *, envelope: bool = False) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for tool wrappers: gate on ``capability`` for :func:`current_persona` (or ``_persona=`` kwarg),
    scope own-cluster calls, redact the return. Denied → ``ToolResult(UNAVAILABLE)`` (or its envelope dict when
    ``envelope=True``). ``inspect.signature`` of the wrapper is the wrapped function's (ADK reflection)."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        params = set(inspect.signature(fn).parameters)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            p = resolve_persona(kwargs.pop("_persona", None) or current_persona())
            bound = dict(kwargs)
            if args:  # positional args → names, so scoping sees well_id / cluster_id
                names = list(inspect.signature(fn).parameters)
                bound.update({names[i]: v for i, v in enumerate(args) if i < len(names)})
            cap = _cap(capability, bound)
            scoped, detail = check_call(p, cap, bound, params)
            if detail is not None:
                d = denied(p, cap, detail)
                return d.envelope() if envelope else d
            result = fn(**{k: v for k, v in scoped.items() if k in params or _has_var_kw(fn)})
            return redact_tool_result(p, cap, result)

        wrapper.rbac_capability = capability  # type: ignore[attr-defined]
        return wrapper

    return deco


def _has_var_kw(fn: Callable[..., Any]) -> bool:
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(fn).parameters.values())


# ------------------------------------------------------------------------------------------------
# Live voice tools (app/live/voice_tools.py) — name → capability
# ------------------------------------------------------------------------------------------------
VOICE_TOOL_CAPABILITY: dict[str, CapabilitySpec] = {
    "fleet_kpis": "asset.overview",
    "list_problem_wells": "queue.read",
    "well_summary": "well.diagnostics",
    "well_workovers": "well.diagnostics",
    "well_recommendation": "well.nba",
    "compare_fields": "field.aggregate",
    "field_production_history": "field.aggregate",
    "attribute_decline": attribution_capability,
    "classify_well_health": "field.health",
    "well_profile": "well.construction",
    "classify_intervention": "well.diagnostics",
    # names Stage R / V may register (pre-mapped so they are gated the moment they land)
    "next_best_action": "well.nba", "recommend_intervention": "well.nba", "nba": "well.nba",
    "compare_interventions": "well.nba", "counterfactual": "well.nba", "compare_alternatives": "well.nba",
    "rank_candidates": "queue.read", "priority_queue": "queue.read", "candidate_queue": "queue.read",
    "search_documents": "docs.sop_dossier", "well_documents": "docs.sop_dossier", "get_sop": "docs.sop_dossier",
    "generate_dossier": "docs.sop_dossier", "dossier": "docs.sop_dossier",
    "query_hierarchy": "asset.overview", "render_well_map": "asset.overview", "well_production": "asset.overview",
}


def voice_tool_capability(name: str, args: dict[str, Any] | None = None) -> str | None:
    spec = VOICE_TOOL_CAPABILITY.get(name)
    return None if spec is None else _cap(spec, args or {})


def voice_tool_visible(name: str, persona: str | None, fallback_personas: frozenset[str] | None = None) -> bool:
    """Whether to declare the tool to the Live model for ``persona``. Unmapped tools fall back to the
    registry's ``personas`` set (pre-Stage-Y behaviour). Dynamic-capability tools stay visible."""
    if not persona or normalize_persona(persona) is None:
        return True
    p = resolve_persona(persona)
    spec = VOICE_TOOL_CAPABILITY.get(name)
    if spec is None:
        return fallback_personas is None or p in fallback_personas
    if callable(spec):
        return True
    return allowed(p, spec)


def voice_gate(name: str, args: dict[str, Any] | None, persona: str | None,
               fallback_personas: frozenset[str] | None = None,
               params: set[str] | None = None) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    """Gate a voice tool call → ``(args, denial_envelope | None, capability | None)``."""
    a = dict(args or {})
    if not persona or normalize_persona(persona) is None:
        return a, None, voice_tool_capability(name, a)
    p = resolve_persona(persona)
    cap = voice_tool_capability(name, a)
    if cap is None:
        if fallback_personas is not None and p not in fallback_personas:
            return a, denied_envelope(p, f"voice tool {name}"), None
        return a, None, None
    scoped, detail = check_call(p, cap, a, params)
    if detail is not None:
        return a, denied_envelope(p, cap, detail), cap
    return scoped, None, cap


# ------------------------------------------------------------------------------------------------
# documents
# ------------------------------------------------------------------------------------------------
def _doc_type(doc_type: str | None) -> str:
    t = (doc_type or "").strip().upper()
    if len(t) == 2 and t.startswith("D") and t[1].isdigit():
        t = f"D0{t[1]}"
    return t


def doc_type_allowed(persona: str | None, doc_type: str | None) -> bool:
    cap, minimum = DOC_TYPE_RULES.get(_doc_type(doc_type), ("docs.sop_dossier", OC))
    return _ACCESS_RANK[access(persona, cap)] >= _ACCESS_RANK[minimum]


def doc_type_capability(doc_type: str | None) -> str:
    return DOC_TYPE_RULES.get(_doc_type(doc_type), ("docs.sop_dossier", OC))[0]


def denied_doc_types(persona: str | None) -> list[str]:
    return [t for t in (f"D{i:02d}" for i in range(1, 12)) if not doc_type_allowed(persona, t)]


def allowed_doc_types(persona: str | None, requested: list[str] | None = None) -> list[str] | None:
    """Filter list for doc search / listing. ``None`` = no filter needed (persona may see every type)."""
    deny = set(denied_doc_types(persona))
    if requested:
        return [t for t in requested if _doc_type(t) not in deny]
    if not deny:
        return None
    return [t for t in (f"D{i:02d}" for i in range(1, 12)) if t not in deny]


# ------------------------------------------------------------------------------------------------
# FastAPI integration
# ------------------------------------------------------------------------------------------------
def get_persona(x_persona: str | None = Header(None, alias="X-Persona")) -> str:
    """FastAPI dependency: resolved persona (default ASSET_MANAGER; unknown → 400 envelope)."""
    return resolve_persona(x_persona, strict=True)


def require(capability: str) -> Callable[..., str]:
    """FastAPI dependency factory: ``persona = Depends(rbac.require("field.aggregate"))``. Denied →
    403 UNAVAILABLE envelope. OWN_CLUSTER access passes; the route scopes with :func:`scope_cluster`."""
    if capability not in MATRIX:
        raise ValueError(f"unknown capability {capability!r}")

    def dep(x_persona: str | None = Header(None, alias="X-Persona")) -> str:
        p = resolve_persona(x_persona, strict=True)
        if not allowed(p, capability):
            raise PermissionDenied(p, capability)
        return p

    dep.__name__ = f"require_{capability.replace('.', '_')}"
    return dep


async def _permission_denied_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, PermissionDenied)
    return JSONResponse(status_code=exc.status_code, content=exc.envelope())


def install(app: Any) -> None:
    """Register the PermissionDenied / UnknownPersona → envelope handler (one line in ``main.py``)."""
    app.add_exception_handler(PermissionDenied, _permission_denied_handler)
    app.add_exception_handler(UnknownPersona, _permission_denied_handler)



# ------------------------------------------------------------------------------------------------
# Stage V TODO (routes / tools owned by other stages; apply when they are free)
# ------------------------------------------------------------------------------------------------
STAGE_V_TODO = (
    "api/analytics_wells.py: /wells/{id}/attribution → Depends(require('well.attribution')); "
    "/wells/{id}/classification → require('well.diagnostics'); nba/compare → require('well.nba') + redact cost_band",
    "api/wells.py: /wells/{id}/recommendations → require('well.nba') and redact(persona,'well.nba',body); "
    "/wells/{id}/chat → pass persona into the runner (persona_scope)",
    "agent/adk_tools.py: decorate every wrapper with @gated(<capability>) (TOOL_CAPABILITY / attribution_capability)",
    "agent/runner.py: wrap each turn in persona_scope(request persona); ChatReply.persona",
    "services/ai_agent.py: remove persona-agnostic recommendation path once runner lands",
)
