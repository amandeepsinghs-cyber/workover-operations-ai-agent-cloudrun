"""ED-11 (F-41, D-40): `ui_control` — the agent drives the dashboard.

One allow-listed command vocabulary shared by the ADK text agent (``adk_tools_ext.ui_control``) and Live voice
(``live/voice_tools.py``). The tool does no data work: it validates the command and returns it; the runner
turns it into a ``{"kind": "ui", "command": ...}`` action and the browser executes it.

Keep ``UI_ACTIONS`` in sync with ``frontend/src/agent/uiCommands.ts`` (unit test compares the two).
"""
from __future__ import annotations

import re
from typing import Any

# action -> allowed values (None = no value needed; "*" = free text validated elsewhere)
UI_ACTIONS: dict[str, tuple[str, ...] | None] = {
    "map_view": ("india", "assam"),
    "fullscreen": ("on", "off"),
    "basemap": ("satellite", "scada"),
    "flowlines": ("on", "off"),
    "legend": ("on", "off"),
    "zoom": ("in", "out"),
    "focus_field": ("Geleki", "Lakwa", "Lakhmani", "ALL"),
    "focus_cluster": None,  # GGS / cluster id, resolved in the browser (ED-13)
    "focus_well": None,
    "open_well": None,
    "open_screen": ("field_history", "field_compare", "field_health"),
    "panel": ("expand", "restore", "close"),
    "language": ("english", "hinglish", "hindi"),
    "report": ("open", "print", "close"),
    "agent": ("dock", "undock"),
    "health_filter": ("all", "healthy", "attention", "not_producing"),  # ED-14 (D-41), D-38 groups
}
WELL_VIEWS: tuple[str, ...] = (
    "summary", "overview", "production", "interventions", "wellbore", "pressures", "diagnosis",
    "recommendation", "offsets", "history", "nearby",
)
NEEDS_WELL = {"focus_well", "open_well"}

_ALIASES = {
    "fullscreen": {"true": "on", "yes": "on", "enter": "on", "false": "off", "no": "off", "exit": "off"},
    "basemap": {"dark": "scada", "normal": "scada", "street": "scada", "sat": "satellite"},
    "map_view": {"all_india": "india", "national": "india", "asset": "assam"},
    "focus_field": {"all": "ALL", "lakmani": "Lakhmani", "lakhmani": "Lakhmani", "geleki": "Geleki",
                    "lakwa": "Lakwa"},
    "open_screen": {"history": "field_history", "compare": "field_compare", "health": "field_health",
                    "priority": "field_health", "comparison": "field_compare"},
    "health_filter": {"none": "all", "clear": "all", "everything": "all", "reset": "all", "off": "all",
                      "green": "healthy", "ok": "healthy", "producing_ok": "healthy", "producing": "healthy",
                      "amber": "attention", "needs_attention": "attention", "at_risk": "attention",
                      "underperforming": "attention", "red": "not_producing", "failed": "not_producing",
                      "non_producing": "not_producing", "not-producing": "not_producing", "shut": "not_producing",
                      "closed": "not_producing", "band": "not_producing", "dead": "not_producing"},
    "panel": {"maximize": "expand", "maximise": "expand", "shrink": "restore", "hide": "close"},
}
_WELL_RE = re.compile(r"^\s*([A-Za-z]{2,3})[\s-]?(\d{1,3})\s*$")

# ED-14: speech-to-text often spells numbers out ("GGS three", "GK one two nine", "जीके एक दो नौ").
_NUM_WORDS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "shunya": 0, "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6,
    "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10,
}


def spoken_digits(text: str | None) -> str:
    """'GK one two nine' -> 'GK 129'; 'GGS three' -> 'GGS 3'; 'one twenty nine' -> '129'. Digits pass through."""
    out: list[str] = []
    run: list[str] = []
    pending_tens: int | None = None
    for tok in re.split(r"[\s-]+", (text or "").strip()):
        n = _NUM_WORDS.get(tok.lower())
        if n is None and tok.isdigit():
            n = int(tok)
            if len(tok) > 1:  # already a number: keep as written (e.g. "03")
                if pending_tens is not None:
                    run.append(str(pending_tens)); pending_tens = None
                run.append(tok)
                continue
        if n is None:
            if pending_tens is not None:
                run.append(str(pending_tens)); pending_tens = None
            if run:
                out.append("".join(run)); run = []
            if tok:
                out.append(tok)
            continue
        if pending_tens is not None and n < 10:
            run.append(str(pending_tens + n)); pending_tens = None
        else:
            if pending_tens is not None:
                run.append(str(pending_tens)); pending_tens = None
            if n >= 20 and n % 10 == 0:
                pending_tens = n
            else:
                run.append(str(n))
    if pending_tens is not None:
        run.append(str(pending_tens))
    if run:
        out.append("".join(run))
    return " ".join(out)
_VIEW_ALIASES = {"completion": "wellbore", "schematic": "wellbore", "diagram": "wellbore", "jobs": "interventions",
                 "workovers": "interventions", "pressure": "pressures", "offset": "offsets",
                 "recommend": "recommendation", "nba": "recommendation", "anomalies": "history",
                 "wax": "history", "sand": "history"}

_LABELS = {
    ("map_view", "india"): "India view", ("map_view", "assam"): "Assam Asset view",
    ("fullscreen", "on"): "Full screen on", ("fullscreen", "off"): "Full screen off",
    ("basemap", "satellite"): "Satellite map", ("basemap", "scada"): "SCADA map",
    ("flowlines", "on"): "Flowlines on", ("flowlines", "off"): "Flowlines off",
    ("legend", "on"): "Legend shown", ("legend", "off"): "Legend hidden",
    ("zoom", "in"): "Zoomed in", ("zoom", "out"): "Zoomed out",
    ("panel", "expand"): "Panel expanded", ("panel", "restore"): "Map restored", ("panel", "close"): "Panel closed",
    ("report", "open"): "Field report opened", ("report", "print"): "Field report printing",
    ("report", "close"): "Field report closed",
    ("agent", "dock"): "Agent docked", ("agent", "undock"): "Agent undocked",
    ("health_filter", "all"): "Showing all wells", ("health_filter", "healthy"): "Showing: Healthy",
    ("health_filter", "attention"): "Showing: Needs attention",
    ("health_filter", "not_producing"): "Showing: Not producing",
}


def _norm_well(raw: str | None) -> str:
    m = _WELL_RE.match(spoken_digits(raw))
    return f"{m.group(1).upper()}-{m.group(2).zfill(3)}" if m else ""


def _norm_cluster(raw: str | None) -> str:
    """'ggs three' -> 'GGS-03'; 'LKW GGS II' -> 'LKW-GGS-II'; 'GK-NE' stays."""
    v = re.sub(r"\s+", "-", spoken_digits(raw).strip().upper())
    v = re.sub(r"-+", "-", v)
    v = re.sub(r"^(GGS)-?(\d)$", r"\1-0\2", v)
    v = re.sub(r"^(GGS)(\d{2})$", r"\1-\2", v)
    return v


def label(cmd: dict[str, Any]) -> str:
    a, v = cmd.get("action"), cmd.get("value") or ""
    if (a, v) in _LABELS:
        return _LABELS[(a, v)]
    if a == "focus_field":
        return "All fields" if v == "ALL" else f"{v} field"
    if a == "focus_well":
        return f"{cmd.get('well_id')} on map"
    if a == "focus_cluster":
        return f"{cmd.get('value')} wells"
    if a == "open_well":
        return f"{cmd.get('well_id')} · {cmd.get('view') or 'overview'}"
    if a == "open_screen":
        return {"field_history": "Field history", "field_compare": "Compare fields",
                "field_health": "Health & priority"}.get(v, v)
    if a == "language":
        return f"Language: {v.title()}"
    return f"{a} {v}".strip()


def validate(action: str, value: str = "", well_id: str = "", view: str = "") -> tuple[dict[str, Any] | None, str]:
    """→ (command, "") when allowed, else (None, reason). Never raises."""
    a = (action or "").strip().lower()
    if a not in UI_ACTIONS:
        return None, f"unknown action '{action}'. Allowed: {', '.join(UI_ACTIONS)}"
    cmd: dict[str, Any] = {"action": a}
    allowed = UI_ACTIONS[a]
    if allowed is not None:
        raw = (value or "").strip()
        key = raw.lower().replace(" ", "_")
        v = _ALIASES.get(a, {}).get(key, raw)
        match = next((x for x in allowed if x.lower() == str(v).lower()), None)
        if match is None:
            return None, f"value for {a} must be one of {', '.join(allowed)}"
        cmd["value"] = match
    if a == "focus_cluster":
        v = _norm_cluster(value)
        if not re.fullmatch(r"[A-Z0-9-]{2,20}", v):
            return None, "focus_cluster needs a GGS or cluster id such as GGS-01 or LKW-GGS-II"
        cmd["value"] = v
    if a in NEEDS_WELL:
        wid = _norm_well(well_id or value)
        if not wid and a == "focus_well":
            return None, "focus_well needs a well_id such as GK-129"
        if wid:
            cmd["well_id"] = wid
        if a == "open_well":
            vw = (view or "overview").strip().lower()
            vw = _VIEW_ALIASES.get(vw, vw)
            if vw not in WELL_VIEWS:
                return None, f"view must be one of {', '.join(WELL_VIEWS)}"
            cmd["view"] = vw
    if a == "report" and well_id:
        wid = _norm_well(well_id)
        if wid:
            cmd["well_id"] = wid
    cmd["label"] = label(cmd)
    return cmd, ""


def run(action: str, value: str = "", well_id: str = "", view: str = "") -> dict[str, Any]:
    """Envelope used by both the ADK tool and the Live voice tool."""
    cmd, err = validate(action, value, well_id, view)
    if cmd is None:
        return {"status": "INVALID", "data": None, "message": err, "missing_fields": [], "provenance": {},
                "tool_id": "UI"}
    return {"status": "OK", "data": {"command": cmd}, "message": f"Done on screen: {cmd['label']}.",
            "missing_fields": [], "provenance": {"tool_id": "UI"}, "tool_id": "UI"}
