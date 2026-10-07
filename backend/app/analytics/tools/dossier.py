"""TC-023 ``build_well_dossier`` — field-engineer pre-job dossier PDF (SDD §10.3, F-06, Stage S).

Verbatim T1 *"when a person is going to the field, the previous history is not there … aggregate all the history and
give it to the person who is going to the field"*; WS-4 *"past intervention histories, well architecture, casing/tubing
tallies, and lithology"*; WS-5 *"hands-free field technician operation"* (the chat / voice card carries 3 highlights).

Pipeline (pure function of tables, tool returns and cited documents — no LLM text inside the PDF):

1. **Assemble** from tool returns only: TC-029 ``well_profile`` (identity, construction, lithology, lift, status, last
   test / survey, same-cluster neighbours), TC-017 v2 ``well_production_series`` (3-year oil series + job markers),
   TC-019 ``attribute_decline`` (180 d), TC-020 bucket (via TC-029), TC-022 ``recommend_next_best_action`` (+ SOP
   phases), TC-027 ``compare_interventions`` (action 1 vs the strongest alternative), ``workover_history`` rows and the
   document store (TC-026 backing: D05 CBL, D08 RCA, D02 reports of failed jobs, the SOP).
2. **Fact slots**: every dynamic string — every number, id, date and tool-generated sentence — enters the PDF through
   :meth:`FactBook.put`, which records ``value`` and ``source`` (table.column / tool.field / derived formula). Static
   labels in this module carry no digits.
3. **Render** with :mod:`app.analytics.docs_pdf.dossier_render` (reportlab platypus + vector wellbore schematic and
   lithology column; vector so schematic labels stay in the text layer and are validated too).
4. **Validate** the PDF (pypdf): every fact value appears; after removing all fact values and the ``Page n of m`` footer
   no digit remains. ``facts.json`` (values, sources, SHA-256 data hash, PDF hash, validation) is written beside it.

RBAC (SDD §16.2): ``docs.sop_dossier`` (all personas). FIELD_ENGINEER has no ``cost_band.view`` → no cost band anywhere
in the PDF; ED has ``well.construction`` = SUMMARY → construction summary instead of casing / tubing tallies.
No currency (D-1). English only (Q-2).

Deviations (documented in the Stage S report): the schematic is reportlab vector graphics, not a matplotlib PNG
(matplotlib is not a dependency, and a raster image would hide schematic numbers from the fact-slot validator);
``?format=pdf`` returns the PDF body (BDD-F06-S01, ``curl -sf`` gate) rather than a 302.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app import settings

from .common import (
    ToolResult,
    ToolStatus,
    build_provenance,
    to_jsonable,
    unavailable,
    well_master_row,
    well_rows,
)

TOOL_ID = "TC-023"
DOSSIER_VERSION = "S1"
MISSING = "not recorded"
UNAVAILABLE_FMT = "UNAVAILABLE — {}"
SECTION_TITLES = (
    "Identity", "Construction & Lithology", "Production Snapshot", "Intervention Timeline", "Repeat Failures",
    "Current Diagnosis & NBA", "Hazards & Lessons", "Logistics", "Source Documents",
)
PERSONA_CODE = {"ED": "ED", "ASSET_MANAGER": "AM", "FIELD_ENGINEER": "FE"}
# density levels tried in order until the PDF fits in 4 pages: timeline rows shown, nearby wells, cite D02 reports
# in the source list (they are already in the timeline), SOP phases listed
COMPACT_LEVELS = (
    {"timeline": 22, "neighbours": 3, "cite_reports": True, "sop_phases": 6},
    {"timeline": 14, "neighbours": 3, "cite_reports": False, "sop_phases": 4},
    {"timeline": 8, "neighbours": 2, "cite_reports": False, "sop_phases": 3},
)
ATTRIBUTION_WINDOW_DAYS = 180
REPEAT_WINDOW_DAYS = 730
PRODUCTION_MONTHS = 36
PDF_URL_FMT = "/api/files/dossiers/{name}"
LAYOUT_RE = re.compile(r"Page\s?\d+\s?of\s?\d+")
WS_RE = re.compile(r"\s+")
DIGIT_RE = re.compile(r"\d")

# glyphs outside WinAnsi (Helvetica) → ASCII, so the text layer round-trips through pypdf exactly
_GLYPHS = {"≤": "<=", "≥": ">=", "−": "-", "′": "'", "″": "''", "→": "->", "←": "<-", "✔": "yes", "✘": "no",
           "✓": "yes", "✗": "no", "≈": "~", "Δ": "delta ", "²": "2", "³": "3", "·": "-", "…": "...",
           "\u00a0": " ", "\u2009": " ", "\u202f": " "}


def _safe(s: str) -> str:
    out = []
    for ch in str(s):
        ch = _GLYPHS.get(ch, ch)
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            out.append("?")
    return "".join(out)


def _fmt(v: Any, nd: int | None = None) -> str | None:
    """Canonical text of a value as it appears in the PDF (same string goes into facts.json)."""
    v = _clean(v)
    if v is None:
        return None
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if nd is not None:
            return f"{v:.{nd}f}"
        r = round(v, 3)
        return str(int(r)) if r == int(r) and abs(r) >= 1000 else repr(r)
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return _safe(str(v)).strip() or None


def _clean(v: Any) -> Any:
    j = to_jsonable(v) if not isinstance(v, (date, datetime)) else v
    if isinstance(j, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}(T.*)?", j):
        return j[:10]
    return j


# =================================================================================================
# fact book
# =================================================================================================
@dataclass
class FactBook:
    """Every dynamic string in the PDF, with its provenance. ``put`` returns the display text."""

    values: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    def put(self, key: str, value: Any, source: str, unit: str = "", nd: int | None = None,
            missing: str = MISSING) -> str:
        s = _fmt(value, nd)
        if s is None:
            return missing
        k, i = key, 1
        while k in self.values and self.values[k] != s:
            i += 1
            k = f"{key}#{i}"
        self.values[k] = s
        self.sources[k] = source
        return f"{s} {unit}" if unit else s

    def text(self, key: str, value: Any, source: str) -> str:
        """A tool-generated sentence (may contain numbers) — kept verbatim as one fact."""
        return self.put(key, value, source)

    def data_hash(self) -> str:
        payload = json.dumps({"values": self.values, "sources": self.sources}, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tool_ref(fb: FactBook, tool_id: str) -> str:
    """Tool contract ids are printed through a fact slot like any other identifier."""
    return fb.put(f"tool.{tool_id}", tool_id, "tool contract id (SDD §6)")


def _unavailable(table: str) -> dict:
    return {"kind": "p", "style": "unavailable", "text": UNAVAILABLE_FMT.format(table)}


def _tool_status(r: ToolResult | None) -> str:
    return r.status.value if r is not None else "UNAVAILABLE"


# =================================================================================================
# output location
# =================================================================================================
def dossier_dir() -> Path:
    env = os.getenv("WELLPULSE_DOSSIER_DIR")
    p = Path(env) if env else Path(__file__).resolve().parents[2] / "data" / "dossiers"
    try:
        p.mkdir(parents=True, exist_ok=True)
        gi = p / ".gitignore"
        if not gi.exists():
            gi.write_text("*\n!.gitignore\n")
        probe = p / ".write_probe"
        probe.write_text("")
        probe.unlink()
    except OSError:  # read-only image (Cloud Run): /tmp-backed (SDD §10.3)
        p = Path("/tmp/wellpulse_dossiers")
        p.mkdir(parents=True, exist_ok=True)
    return p


def dossier_name(well_id: str, as_of: date, persona: str) -> str:
    return f"{well_id}_{as_of.isoformat()}_{PERSONA_CODE.get(persona, persona)}"


def dossier_doc_id(well_id: str, as_of: date, persona: str) -> str:
    return f"DOSSIER-{well_id}-{as_of:%Y%m%d}-{PERSONA_CODE.get(persona, persona)}"


def dossier_path(name: str) -> Path | None:
    """Resolve a served file name (``<name>.pdf`` / ``.facts.json``) inside the dossier dir; None if unsafe/missing."""
    if not re.fullmatch(r"[A-Z]{2,3}-\d{3}_\d{4}-\d{2}-\d{2}_[A-Z]{2}\.(pdf|facts\.json)", name or ""):
        return None
    p = dossier_dir() / name
    return p if p.exists() else None


# =================================================================================================
# result type
# =================================================================================================
@dataclass(frozen=True)
class Dossier:
    doc_id: str
    well_id: str
    as_of: date
    persona: str
    pdf_url: str
    facts_url: str
    file_name: str
    pages: int
    sections: list[str]
    highlights: list[str]
    sources: list[dict]
    n_facts: int
    data_sha256: str
    pdf_sha256: str
    validation: dict
    render_ms: float
    cached: bool = False


# =================================================================================================
# assembly helpers
# =================================================================================================
def _docs_for_well(well_id: str) -> list[dict]:
    try:
        from app.analytics.docs_pdf.store import get_store

        st = get_store()
        return st.list_for_well(well_id, None, 5000) if st is not None else []
    except Exception:  # noqa: BLE001 - corpus optional; sections declare UNAVAILABLE
        return []


def _doc_facts(doc_id: str) -> dict:
    try:
        from app.analytics.docs_pdf.store import get_store

        st = get_store()
        row = st.doc(doc_id) if st is not None else None
        if row is None:
            return {}
        f = (st.root / row["path"]).with_name(f"{doc_id}.facts.json")
        return json.loads(f.read_text()).get("facts", {}) if f.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def _strip_cost(text: str) -> str:
    return re.sub(r",?\s*cost band [A-Z_]+", "", text)


def _workovers(well_id: str, as_of: date):
    wo = well_rows("workover_history", well_id)
    if wo.empty:
        return wo
    wo = wo[wo["start_date"] <= as_of]
    if "is_censored" in wo.columns:
        wo = wo[~wo["is_censored"].fillna(False).astype(bool)]
    return wo.sort_values("start_date")


def _job_code(r) -> str:
    c = getattr(r, "catalogue_job_code", None)
    return c if isinstance(c, str) and c else str(r.job_code)


# =================================================================================================
# section builders (each returns blocks; all dynamic text via the FactBook)
# =================================================================================================
@dataclass
class _Ctx:
    wid: str
    as_of: date
    persona: str
    fb: FactBook
    profile: Any
    series: Any
    attribution: Any
    nba: Any
    cf: Any
    docs: list[dict]
    cited: dict[str, dict]
    tools: dict[str, ToolResult | None]
    tables: dict[str, int]
    full_construction: bool
    show_cost: bool
    highlights: list[str] = field(default_factory=list)
    level: int = 0

    @property
    def lv(self) -> dict:
        return COMPACT_LEVELS[self.level]

    def cite(self, doc: dict, why: str) -> str:
        did = str(doc.get("doc_id"))
        if did not in self.cited:
            self.cited[did] = {**doc, "why": why}
        return self.fb.put(f"doc.{did}.id", did, "document_index.doc_id")


def _sec_identity(c: _Ctx) -> list[dict]:
    fb, p = c.fb, c.profile
    idn, lift, st = p.identity, p.lift, p.status
    pairs = [
        ["Well", fb.put("well_id", idn["well_id"], "well_master.well_id")],
        ["Field", fb.put("field", idn["field"], "well_master.field")],
        ["Cluster", fb.put("cluster_id", idn.get("cluster_id"), "well_master.cluster_id")],
        ["Producing zone", fb.put("zone", idn.get("zone"), "well_master.current_zone")],
        ["Formation at perforations", fb.put("formation", idn.get("formation"), "formation_tops.formation at well_master.perf_top_m")],
        ["Well status", fb.put("well_status", idn.get("well_status"), "well_master.status")],
        ["Spud date", fb.put("spud_date", idn.get("spud_date"), "well_master.spud_date")],
        ["Completion date", fb.put("completion_date", idn.get("completion_date"), "well_master.completion_date")],
        ["Total depth MD", fb.put("td_md", idn.get("total_depth_md_m"), "well_master.total_depth_md_m", "m")],
        ["Total depth TVD", fb.put("td_tvd", idn.get("total_depth_tvd_m"), "well_master.total_depth_tvd_m", "m")],
        ["Perforated interval", fb.put("perf_top", idn.get("perf_top_m"), "well_master.perf_top_m") + " to "
         + fb.put("perf_bottom", idn.get("perf_bottom_m"), "well_master.perf_bottom_m", "m")],
        ["Lift type", fb.put("lift_type", lift.get("lift_type"), "well_master.lift_type")],
        ["Location (synthetic)", fb.put("lat", idn.get("lat"), "well_master.latitude") + ", "
         + fb.put("lon", idn.get("lon"), "well_master.longitude")],
        ["Health bucket", fb.put("bucket", st.get("bucket"), "TC-020 classify_well_health (via TC-029 well_profile)")],
        ["Current status episode", fb.put("episode_status", st.get("episode_status"), "well_status_history.status")
         + " since " + fb.put("episode_since", st.get("episode_since"), "well_status_history.start_date")],
        ["Dossier as of", fb.put("as_of", c.as_of, "request as_of (default settings.AS_OF)")],
    ]
    blocks: list[dict] = [{"kind": "kv", "cols": 2, "pairs": pairs}]
    if lift:
        lp = []
        for key, label, unit in (("pump_type", "Pump type", ""), ("plunger_diameter_in", "Plunger diameter", "in"),
                                 ("stroke_length_in", "Stroke length", "in"), ("pump_setting_depth_m", "Pump setting depth", "m"),
                                 ("rod_string_grade", "Rod string grade", ""), ("casing_vented", "Casing vented", "")):
            if key in lift:
                lp.append([label, fb.put(f"lift.{key}", lift[key], f"well_master.{key}", unit)])
        if lp:
            blocks.append({"kind": "kv", "cols": 3, "pairs": lp})
    return blocks


def _schematic_geom(c: _Ctx) -> dict:
    fb, con, lith = c.fb, c.profile.construction, c.profile.lithology
    td = c.profile.identity.get("total_depth_md_m") or 0.0
    geom: dict = {"td_m": float(td or 0.0) or 1000.0, "formations": [], "casing": [], "tubing": [], "perfs": [],
                  "caption_label": None}
    for i, r in enumerate(lith):
        geom["formations"].append({"top": float(r["top_md_m"]), "bottom": float(r["bottom_md_m"]),
                                   "label": fb.put(f"lith[{i}].formation", r["formation"], "formation_tops.formation")})
    for i, r in enumerate(con["casing"]):
        if r.get("shoe_m") is None:
            continue
        lab = (fb.put(f"casing[{i}].string_type", r.get("string_type"), "casing_tally.string_type") + " "
               + fb.put(f"casing[{i}].od_in", r.get("od_in"), "casing_tally.od_in", "in") + ", shoe "
               + fb.put(f"casing[{i}].shoe_m", r.get("shoe_m"), "casing_tally.shoe_m", "m"))
        geom["casing"].append({"od": float(r.get("od_in") or 0), "top": float(r.get("top_m") or 0),
                               "shoe": float(r["shoe_m"]),
                               "cement_top": None if r.get("cement_top_m") is None else float(r["cement_top_m"]),
                               "label": lab})
    for i, r in enumerate(con["tubing"]):
        top, ln = r.get("top_m"), r.get("length_m")
        if top is None or ln is None:
            continue
        comp = str(r.get("component"))
        lab = None
        if comp != "TUBING":
            lab = (fb.put(f"tubing[{i}].component", comp, "tubing_string.component") + " at "
                   + fb.put(f"tubing[{i}].top_m", top, "tubing_string.top_m", "m"))
        geom["tubing"].append({"top": float(top), "bottom": float(top) + float(ln), "component": comp, "label": lab})
    for i, r in enumerate(con["perfs"]):
        if r.get("top_m") is None or r.get("bottom_m") is None:
            continue
        lab = ("Perfs " + fb.put(f"perf[{i}].zone", r.get("zone"), "perforation_intervals.zone") + " "
               + fb.put(f"perf[{i}].top_m", r.get("top_m"), "perforation_intervals.top_m") + " to "
               + fb.put(f"perf[{i}].bottom_m", r.get("bottom_m"), "perforation_intervals.bottom_m", "m"))
        geom["perfs"].append({"top": float(r["top_m"]), "bottom": float(r["bottom_m"]), "label": lab,
                              "open": str(r.get("status")) == "OPEN"})
    if td:
        geom["caption_label"] = "TD " + fb.put("td_md", td, "well_master.total_depth_md_m", "m MD")
    return geom


def _sec_construction(c: _Ctx) -> list[dict]:
    from app.analytics.docs_pdf.dossier_render import wellbore_schematic

    fb, con, lith = c.fb, c.profile.construction, c.profile.lithology
    blocks: list[dict] = []
    # lithology column table (WS-4, D-19)
    if lith:
        lrows = [[fb.put(f"lith[{i}].formation", r["formation"], "formation_tops.formation"),
                  fb.put(f"lith[{i}].top", r["top_md_m"], "formation_tops.top_md_m"),
                  fb.put(f"lith[{i}].bottom", r["bottom_md_m"], "formation_tops.bottom_md_m"),
                  fb.put(f"lith[{i}].lithology", r.get("lithology"), "formation_tops.lithology")]
                 for i, r in enumerate(lith)]
        lith_tbl = {"kind": "table", "title": "Lithology column (formation tops)",
                    "headers": ["Formation", "Top m MD", "Base m MD", "Lithology"], "rows": lrows,
                    "col_weights": [1.1, 0.8, 0.8, 2.2], "empty_text": UNAVAILABLE_FMT.format("formation_tops")}
    else:
        lith_tbl = _unavailable("formation_tops")
    if not c.full_construction:
        from app.agent.rbac import summarize_construction

        sm = summarize_construction(con)
        pairs = [["Casing size", fb.put("casing_size_in", sm.get("casing_size_in"), "well_master.casing_size_in", "in")],
                 ["Tubing size", fb.put("tubing_size_in", sm.get("tubing_size_in"), "well_master.tubing_size_in", "in")],
                 ["Casing strings", fb.put("n_casing", sm.get("casing_strings"), "count(casing_tally rows)")],
                 ["Tubing components", fb.put("n_tubing", sm.get("tubing_components"), "count(tubing_string rows)")],
                 ["Perforated zones", fb.put("perf_zones", ", ".join(sm.get("perf_zones") or []) or None,
                                             "perforation_intervals.zone")]]
        return [{"kind": "p", "style": "note",
                 "text": "Construction summary only: casing and tubing tallies are restricted for this persona "
                         "(well.construction summary access)."},
                {"kind": "kv", "cols": 2, "pairs": pairs}, lith_tbl]
    geom = _schematic_geom(c)
    drawing = {"kind": "drawing", "drawing": wellbore_schematic(geom, 285, 270),
               "caption": "Wellbore schematic with lithology column (not to scale laterally)."}
    blocks.append({"kind": "columns", "widths": [0.58, 0.42], "left": [drawing], "right": [lith_tbl]})
    # casing tally
    if con["casing"]:
        rows = [[fb.put(f"casing[{i}].string_type", r.get("string_type"), "casing_tally.string_type"),
                 fb.put(f"casing[{i}].od_in", r.get("od_in"), "casing_tally.od_in"),
                 fb.put(f"casing[{i}].weight_ppf", r.get("weight_ppf"), "casing_tally.weight_ppf"),
                 fb.put(f"casing[{i}].grade", r.get("grade"), "casing_tally.grade"),
                 fb.put(f"casing[{i}].top_m", r.get("top_m"), "casing_tally.top_m"),
                 fb.put(f"casing[{i}].shoe_m", r.get("shoe_m"), "casing_tally.shoe_m"),
                 fb.put(f"casing[{i}].cement_top_m", r.get("cement_top_m"), "casing_tally.cement_top_m"),
                 fb.put(f"casing[{i}].install_date", r.get("install_date"), "casing_tally.install_date")]
                for i, r in enumerate(con["casing"])]
        blocks.append({"kind": "table", "title": "Casing tally",
                       "headers": ["String", "OD in", "Weight ppf", "Grade", "Top m", "Shoe m", "Cement top m", "Installed"],
                       "rows": rows, "col_weights": None, "empty_text": UNAVAILABLE_FMT.format("casing_tally")})
    else:
        blocks += [{"kind": "p", "style": "emphasis", "text": "Casing tally"}, _unavailable("casing_tally")]
    if con["tubing"]:
        rows = [[fb.put(f"tubing[{i}].seq", r.get("seq"), "tubing_string.seq"),
                 fb.put(f"tubing[{i}].component", r.get("component"), "tubing_string.component"),
                 fb.put(f"tubing[{i}].od_in", r.get("od_in"), "tubing_string.od_in"),
                 fb.put(f"tubing[{i}].length_m", r.get("length_m"), "tubing_string.length_m"),
                 fb.put(f"tubing[{i}].top_m", r.get("top_m"), "tubing_string.top_m"),
                 fb.put(f"tubing[{i}].install_date", r.get("install_date"), "tubing_string.install_date"),
                 fb.put(f"tubing[{i}].workover_id", r.get("workover_id"), "tubing_string.workover_id")]
                for i, r in enumerate(con["tubing"])]
        blocks.append({"kind": "table", "title": "Tubing string / BHA tally",
                       "headers": ["Seq", "Component", "OD in", "Length m", "Top m", "Installed", "Workover"],
                       "rows": rows, "col_weights": None, "empty_text": UNAVAILABLE_FMT.format("tubing_string")})
    else:
        blocks += [{"kind": "p", "style": "emphasis", "text": "Tubing string / BHA tally"}, _unavailable("tubing_string")]
    if con["perfs"]:
        rows = [[fb.put(f"perf[{i}].zone", r.get("zone"), "perforation_intervals.zone"),
                 fb.put(f"perf[{i}].top_m", r.get("top_m"), "perforation_intervals.top_m"),
                 fb.put(f"perf[{i}].bottom_m", r.get("bottom_m"), "perforation_intervals.bottom_m"),
                 fb.put(f"perf[{i}].spf", r.get("spf"), "perforation_intervals.spf"),
                 fb.put(f"perf[{i}].perf_date", r.get("perf_date"), "perforation_intervals.perf_date"),
                 fb.put(f"perf[{i}].status", r.get("status"), "perforation_intervals.status")]
                for i, r in enumerate(con["perfs"])]
        blocks.append({"kind": "table", "title": "Perforations",
                       "headers": ["Zone", "Top m", "Bottom m", "Shots per ft", "Perforated", "Status"],
                       "rows": rows, "col_weights": None, "empty_text": UNAVAILABLE_FMT.format("perforation_intervals")})
    else:
        blocks += [{"kind": "p", "style": "emphasis", "text": "Perforations"}, _unavailable("perforation_intervals")]
    return blocks


def _sec_production(c: _Ctx) -> list[dict]:
    from app.analytics.docs_pdf.dossier_render import sparkline

    fb, p = c.fb, c.profile
    cur, dec, lt, ps = p.current, p.decline, p.last_test, p.last_pressure_survey
    blocks: list[dict] = []
    pairs = [
        ["Oil rate", fb.put("cur.oil", cur.get("oil_bopd"), "TC-029 current.oil_bopd (daily_production)", "BOPD")],
        ["Water cut", fb.put("cur.wc", cur.get("water_cut_pct"), "TC-029 current.water_cut_pct (daily_production)", "%")],
        ["Gas rate", fb.put("cur.gas", cur.get("gas_mscfd"), "TC-029 current.gas_mscfd (daily_production)", "MSCFD")],
        ["Last producing day", fb.put("cur.last", cur.get("last_producing_date"), "daily_production.production_date")],
        ["Rate basis", fb.text("cur.basis", cur.get("basis"), "TC-029 current.basis")],
        ["Decline expectation", fb.put("dec.exp", dec.get("expected_bopd"), "TC-001 fit_decline_curve.expected_bopd", "BOPD")],
        ["Residual vs decline", fb.put("dec.res", dec.get("residual_pct"), "TC-001 fit_decline_curve.residual_pct", "%")],
        ["Decline fit quality", fb.put("dec.fq", dec.get("fit_quality"), "TC-001 fit_decline_curve.fit_quality")],
    ]
    blocks.append({"kind": "kv", "cols": 2, "pairs": pairs})
    sv = c.series.value if c.series is not None else None
    if sv is not None and sv.dates:
        oil = sv.series.get("oil") or []
        idx = {d: i for i, d in enumerate(sv.dates)}
        marks = [idx[m["date"]] for m in sv.interventions if m["date"] in idx]
        cap = ("Daily oil rate " + fb.put("series.start", sv.window_start, "TC-017 v2 window_start") + " to "
               + fb.put("series.end", sv.window_end, "TC-017 v2 window_end")
               + "; red ticks mark interventions (see Intervention Timeline).")
        blocks.append({"kind": "drawing", "drawing": sparkline(oil, 500, 46, marks), "caption": cap})
    else:
        blocks.append(_unavailable("daily_production"))
    if lt:
        tp = [["Test", fb.put("test.id", lt.get("test_id"), "well_tests.test_id")],
              ["Test date", fb.put("test.date", lt.get("test_date"), "well_tests.test_date")],
              ["Oil", fb.put("test.oil", lt.get("oil_rate_bopd"), "well_tests.oil_rate_bopd", "BOPD")],
              ["Water", fb.put("test.water", lt.get("water_rate_bwpd"), "well_tests.water_rate_bwpd", "BWPD")],
              ["Gas", fb.put("test.gas", lt.get("gas_rate_mscfd"), "well_tests.gas_rate_mscfd", "MSCFD")],
              ["THP", fb.put("test.thp", lt.get("thp_kgcm2"), "well_tests.thp_kgcm2", "kg/cm²")],
              ["CHP", fb.put("test.chp", lt.get("chp_kgcm2"), "well_tests.chp_kgcm2", "kg/cm²")],
              ["Fluid level", fb.put("test.fl", lt.get("fluid_level_m"), "well_tests.fluid_level_m", "m")],
              ["Pump intake pressure", fb.put("test.pip", lt.get("pump_intake_p_kgcm2"), "well_tests.pump_intake_p_kgcm2", "kg/cm²")],
              ["Test quality", fb.put("test.q", lt.get("test_quality"), "well_tests.test_quality")]]
        blocks.append({"kind": "p", "style": "emphasis", "text": "Last well test"})
        blocks.append({"kind": "kv", "cols": 3, "pairs": tp})
    else:
        blocks += [{"kind": "p", "style": "emphasis", "text": "Last well test"}, _unavailable("well_tests")]
    if ps:
        pp = [["Survey", fb.put("ps.id", ps.get("survey_id"), "pressure_surveys.survey_id")],
              ["Survey date", fb.put("ps.date", ps.get("survey_date"), "pressure_surveys.survey_date")],
              ["Static BHP", fb.put("ps.sbhp", ps.get("sbhp_kgcm2"), "pressure_surveys.sbhp_kgcm2", "kg/cm²")],
              ["Flowing BHP", fb.put("ps.fbhp", ps.get("fbhp_kgcm2"), "pressure_surveys.fbhp_kgcm2", "kg/cm²")],
              ["Productivity index", fb.put("ps.pi", ps.get("pi_bpd_per_kgcm2"), "pressure_surveys.pi_bpd_per_kgcm2", "bpd per kg/cm²")],
              ["Datum TVD", fb.put("ps.datum", ps.get("datum_tvd_m"), "pressure_surveys.datum_tvd_m", "m")]]
        blocks.append({"kind": "p", "style": "emphasis", "text": "Last pressure survey"})
        blocks.append({"kind": "kv", "cols": 3, "pairs": pp})
    else:
        blocks += [{"kind": "p", "style": "emphasis", "text": "Last pressure survey"}, _unavailable("pressure_surveys")]
    nb = p.neighbours[: c.lv["neighbours"]]
    if nb:
        rows = [[fb.put(f"nb[{i}].well", n["well_id"], "well_master.well_id (TC-029 neighbours)"),
                 fb.put(f"nb[{i}].dist", n.get("distance_m"), "TC-029 haversine(well_master lat/lon)"),
                 fb.put(f"nb[{i}].zone", n.get("zone"), "well_master.current_zone"),
                 fb.put(f"nb[{i}].lift", n.get("lift_type"), "well_master.lift_type"),
                 fb.put(f"nb[{i}].bucket", n.get("bucket"), "TC-020 bucket"),
                 fb.put(f"nb[{i}].oil", n.get("oil_bopd"), "TC-029 current.oil_bopd"),
                 fb.put(f"nb[{i}].wc", n.get("water_cut_pct"), "TC-029 current.water_cut_pct"),
                 fb.put(f"nb[{i}].job", n.get("last_job_code"), "workover_history.catalogue_job_code") + " "
                 + fb.put(f"nb[{i}].jobdate", n.get("last_job_date"), "workover_history.start_date", missing="")]
                for i, n in enumerate(nb)]
        blocks.append({"kind": "table", "title": "Nearby wells (same cluster)",
                       "headers": ["Well", "Distance m", "Zone", "Lift", "Bucket", "Oil BOPD", "Water cut %", "Last job"],
                       "rows": rows, "col_weights": [0.8, 0.7, 0.7, 0.8, 1.2, 0.7, 0.7, 1.9],
                       "empty_text": UNAVAILABLE_FMT.format("well_master")})
    return blocks


def _sec_timeline(c: _Ctx, wo) -> list[dict]:
    fb = c.fb
    if wo is None or wo.empty:
        return [_unavailable("workover_history")]
    recs = list(wo.itertuples(index=False))
    shown = recs[-c.lv["timeline"]:]
    rows = []
    for r in shown:
        k = f"wo.{r.workover_id}"
        doc = r.report_doc_id if isinstance(getattr(r, "report_doc_id", None), str) else None
        if doc and c.lv["cite_reports"]:
            c.cite({"doc_id": doc, "title": None, "doc_type": "D02", "doc_date": None}, "intervention report")
        rows.append([
            fb.put(f"{k}.start", r.start_date, "workover_history.start_date"),
            fb.put(f"{k}.job", _job_code(r), "workover_history.catalogue_job_code"),
            fb.put(f"{k}.ic", r.intervention_class if isinstance(r.intervention_class, str) else None,
                   "workover_history.intervention_class", missing="-"),
            fb.put(f"{k}.failure", r.failure_code, "workover_history.failure_code", missing="-"),
            fb.put(f"{k}.outcome", r.outcome, "workover_history.outcome"),
            fb.put(f"{k}.rig_days", r.rig_days, "workover_history.rig_days", missing="-"),
            fb.put(f"{k}.run_life", r.run_life_days, "workover_history.run_life_days", missing="-"),
            fb.put(f"{k}.uplift", r.uplift_bopd, "workover_history.uplift_bopd", missing="-"),
            fb.put(f"doc.{doc}.id", doc, "workover_history.report_doc_id", missing="-") if doc else "-",
        ])
    blocks = [{"kind": "table", "title": None,
               "headers": ["Start", "Job", "Class", "Failure", "Outcome", "Rig-days", "Run life d", "Uplift BOPD", "Report"],
               "rows": rows, "col_weights": [0.9, 1.3, 0.6, 1.0, 0.8, 0.6, 0.6, 0.7, 1.6],
               "empty_text": UNAVAILABLE_FMT.format("workover_history")}]
    if len(recs) > len(shown):
        blocks.append({"kind": "p", "style": "note",
                       "text": "Older interventions not listed: " + fb.put("wo.older", len(recs) - len(shown),
                                                                           "count(workover_history) - rows shown")
                       + " (open the well document list for the full record)."})
    blocks.append({"kind": "p", "style": "note",
                   "text": "Intervention count to date: " + fb.put("wo.total", len(recs), "count(workover_history rows, censoring rows excluded)")
                   + "; reports open at /api/docs/<doc_id>.pdf."})
    return blocks


def _sec_repeat(c: _Ctx, wo) -> list[dict]:
    fb = c.fb
    if wo is None or wo.empty:
        return [_unavailable("workover_history")]
    w = wo[wo["failure_code"].notna() & (wo["failure_code"] != "NONE")]
    if w.empty:
        return [{"kind": "p", "style": "body", "text": "No failure-coded interventions recorded for this well."}]
    since = date.fromordinal(c.as_of.toordinal() - REPEAT_WINDOW_DAYS)
    rows, repeats = [], []
    for code, g in sorted(w.groupby("failure_code"), key=lambda kv: (-len(kv[1]), kv[0])):
        n_recent = int((g["start_date"] >= since).sum())
        rl = g["run_life_days"].dropna()
        k = f"rf.{code}"
        rows.append([fb.put(f"{k}.code", code, "workover_history.failure_code"),
                     fb.put(f"{k}.n", len(g), "count(workover_history where failure_code)"),
                     fb.put(f"{k}.n24", n_recent, "count(workover_history where failure_code, start_date in last 730 d)"),
                     fb.put(f"{k}.last", g["start_date"].max(), "max(workover_history.start_date)"),
                     fb.put(f"{k}.rl", float(rl.median()) if len(rl) else None, "median(workover_history.run_life_days)", nd=0,
                            missing="-"),
                     fb.put(f"{k}.failed", int((g["outcome"] == "FAILED").sum()), "count(outcome = FAILED)")])
        if n_recent >= 2:
            repeats.append(code)
    blocks = [{"kind": "table", "title": None,
               "headers": ["Failure mode", "Jobs to date", "Jobs in repeat window", "Last job", "Median run life d", "Jobs FAILED"],
               "rows": rows, "col_weights": [1.4, 0.8, 1.1, 0.9, 1.0, 0.8], "empty_text": ""}]
    blocks.append({"kind": "p", "style": "note",
                   "text": "Repeat window: " + fb.put("rf.since", since, "as_of - 730 d") + " to "
                   + fb.put("as_of", c.as_of, "request as_of (default settings.AS_OF)") + "."})
    if repeats:
        blocks.append({"kind": "callout", "tone": "warning",
                       "text": "Repeat failure pattern: " + ", ".join(fb.put(f"rf.{x}.code", x, "workover_history.failure_code")
                                                                     for x in repeats)
                       + " recurred within the repeat window; check root cause before repeating the same job."})
    return blocks


def _sec_diagnosis(c: _Ctx) -> list[dict]:
    fb, st = c.fb, c.profile.status
    blocks: list[dict] = []
    pairs = [["Health bucket", fb.put("bucket", st.get("bucket"), "TC-020 classify_well_health")],
             ["Bucket reason", fb.text("bucket.reason", st.get("reason"), "TC-020 reason")],
             ["Open episode", fb.put("episode_status", st.get("episode_status"), "well_status_history.status")],
             ["Episode reason", fb.put("episode_reason", st.get("reason_code"), "well_status_history.reason_code", missing="-")]]
    blocks.append({"kind": "kv", "cols": 2, "pairs": pairs})
    a = c.attribution.value if c.attribution is not None else None
    if a is not None:
        blocks.append({"kind": "p", "style": "emphasis", "text": "Decline attribution (" + _tool_ref(fb, "TC-019") + ")"})
        blocks.append({"kind": "p", "style": "body", "text": (
            "Window " + fb.put("attr.ws", a.window_start, "TC-019 window_start") + " to "
            + fb.put("attr.we", a.window_end, "TC-019 window_end") + ": loss "
            + fb.put("attr.total", a.total_loss_bbl, "TC-019 total_loss_bbl", "bbl") + " against baseline "
            + fb.put("attr.base", a.baseline_bopd, "TC-019 baseline_bopd", "BOPD") + "; largest class "
            + fb.put("attr.largest", a.largest_class, "TC-019 largest_class") + "; controllable "
            + fb.put("attr.ctrl", a.controllable_pct, "TC-019 controllable_pct", "%") + ".")})
        rows = []
        for i, comp in enumerate(a.components[:6]):
            g = comp if isinstance(comp, dict) else to_jsonable(comp)
            rows.append([fb.put(f"attr.c{i}.class", g.get("factor_class"), "TC-019 components.factor_class"),
                         fb.put(f"attr.c{i}.sub", g.get("sub_factor"), "TC-019 components.sub_factor"),
                         fb.put(f"attr.c{i}.bbl", g.get("bbl"), "TC-019 components.bbl"),
                         fb.put(f"attr.c{i}.pct", g.get("pct"), "TC-019 components.pct"),
                         fb.put(f"attr.c{i}.days", g.get("days"), "TC-019 components.days", missing="-"),
                         fb.put(f"attr.c{i}.fn", g.get("responsible_function"), "TC-019 components.responsible_function",
                                missing="-")])
        blocks.append({"kind": "table", "title": None,
                       "headers": ["Class", "Sub-factor", "Loss bbl", "Share %", "Days", "Responsible function"],
                       "rows": rows, "col_weights": [1.1, 1.3, 0.7, 0.6, 0.5, 1.4], "empty_text": "No loss components."})
        if a.largest_class:
            c.highlights.append("Largest loss class " + fb.put("attr.largest", a.largest_class, "TC-019 largest_class")
                                + " (" + fb.put("attr.largest_pct", (a.by_class.get(a.largest_class) or {}).get("pct"),
                                                "TC-019 by_class.pct", "%") + " of "
                                + fb.put("attr.total", a.total_loss_bbl, "TC-019 total_loss_bbl", "bbl") + ").")
    else:
        blocks += [{"kind": "p", "style": "emphasis", "text": "Decline attribution (" + _tool_ref(fb, "TC-019") + ")"},
                   _unavailable("attribute_decline (" + _tool_status(c.attribution) + ")")]
    # NBA
    nv = c.nba.value if c.nba is not None else None
    blocks.append({"kind": "p", "style": "emphasis", "text": "Recommended next action (" + _tool_ref(fb, "TC-022") + ")"})
    if nv is None or not nv.actions:
        blocks.append(_unavailable("recommend_next_best_action (" + _tool_status(c.nba) + ")"))
        return blocks
    headers = ["Rank", "Job", "Class", "Diagnostic fit", "p success", "n", "Rig-days", "Score", "SOP"]
    if c.show_cost:
        headers.insert(7, "Cost band")
    rows = []
    for a1 in nv.actions:
        k = f"nba.{a1.rank}"
        row = [fb.put(f"{k}.rank", a1.rank, "TC-022 actions.rank"),
               fb.put(f"{k}.job", a1.job_code, "TC-022 actions.job_code (job_catalogue)"),
               fb.put(f"{k}.ic", a1.ic, "job_catalogue.intervention_class"),
               fb.put(f"{k}.fit", a1.diagnostic_fit, "TC-022 actions.diagnostic_fit"),
               fb.put(f"{k}.p", a1.p_success, "TC-022 actions.p_success", missing="-"),
               fb.put(f"{k}.n", a1.p_success_n, "TC-022 actions.p_success_n"),
               fb.put(f"{k}.rig", a1.rig_days, "TC-022 actions.rig_days"),
               fb.put(f"{k}.score", a1.score, "TC-022 actions.score"),
               fb.put(f"{k}.sop", a1.sop_doc_id, "job_catalogue.sop_doc_id", missing="-")]
        if c.show_cost:
            row.insert(7, fb.put(f"{k}.cost", a1.cost_band, "job_catalogue.cost_band"))
        rows.append(row)
    blocks.append({"kind": "table", "title": None, "headers": headers, "rows": rows, "col_weights": None,
                   "empty_text": ""})
    top = nv.actions[0]
    why = top.why if c.show_cost else _strip_cost(top.why)
    blocks.append({"kind": "callout", "tone": "info", "text": fb.text("nba.1.why", why, "TC-022 actions[0].why")})
    if nv.flags:
        blocks.append({"kind": "p", "style": "note",
                       "text": "Tool flags: " + fb.put("nba.flags", ", ".join(nv.flags), "TC-022 flags")})
    c.highlights.append("Next best action " + fb.put("nba.1.job", top.job_code, "TC-022 actions.job_code (job_catalogue)")
                        + " (" + fb.put("nba.1.ic", top.ic, "job_catalogue.intervention_class") + ")"
                        + (", SOP " + fb.put("nba.1.sop", top.sop_doc_id, "job_catalogue.sop_doc_id") if top.sop_doc_id else "")
                        + ".")
    # SOP
    if top.sop_doc_id:
        c.cite({"doc_id": top.sop_doc_id, "title": top.sop_title, "doc_type": "D11", "doc_date": None}, "SOP for the recommended job")
        blocks.append({"kind": "p", "style": "emphasis",
                       "text": "Standard operating procedure: " + fb.put("sop.title", top.sop_title or top.sop_doc_id,
                                                                         "document_index.title (D11)")})
        phases = top.sop_steps or []
        if phases:
            items = []
            for i, ph in enumerate(phases[: c.lv["sop_phases"]]):
                items.append(fb.text(f"sop.ph{i}", ph.get("phase") or MISSING, f"{top.sop_doc_id} phase title")
                             + " (" + fb.put(f"sop.ph{i}.n", len(ph.get("steps") or []), f"count({top.sop_doc_id} steps)")
                             + " steps)")
            blocks.append({"kind": "bullets", "items": items})
        else:
            blocks.append(_unavailable(f"{top.sop_doc_id} procedure text"))
    # counterfactual
    cv = c.cf.value if c.cf is not None else None
    if cv is not None:
        blocks.append({"kind": "p", "style": "emphasis", "text": "Counterfactual (" + _tool_ref(fb, "TC-027") + "): why this job over the alternative"})
        blocks.append({"kind": "p", "style": "body", "text": (
            "Alternative " + fb.put("cf.alt", cv.alternative.job_code, "TC-027 alternative.job_code") + ": verdict "
            + fb.put("cf.verdict", cv.verdict, "TC-027 verdict") + ", deciding dimension "
            + fb.put("cf.dim", cv.deciding_dimension, "TC-027 deciding_dimension") + ".")})
        vt = cv.verdict_text if c.show_cost else _strip_cost(cv.verdict_text)
        blocks.append({"kind": "p", "style": "note", "text": fb.text("cf.text", vt, "TC-027 verdict_text")})
        for cit in (cv.citations or [])[:4]:
            c.cite(cit, "counterfactual citation")
    return blocks


def _sec_hazards(c: _Ctx, wo) -> list[dict]:
    fb = c.fb
    blocks: list[dict] = []
    nv = c.nba.value if c.nba is not None else None
    flags = list(nv.actions[0].risk_flags) if nv is not None and nv.actions else []
    if flags:
        blocks.append({"kind": "callout", "tone": "danger",
                       "text": "Risk flags on the recommended job: " + fb.put("haz.flags", ", ".join(flags), "TC-022 actions[0].risk_flags")})
    # casing age (well integrity)
    cas = c.profile.construction.get("casing") or []
    inst = [r.get("install_date") for r in cas if r.get("install_date")]
    if inst:
        oldest = min(str(x) for x in inst)
        yrs = round((c.as_of - date.fromisoformat(oldest)).days / 365.25, 1)
        blocks.append({"kind": "p", "style": "body", "text": (
            "Casing installed " + fb.put("haz.casing_install", oldest, "min(casing_tally.install_date)")
            + "; casing age at dossier date " + fb.put("haz.casing_age", yrs, "derived: (as_of - min(casing_tally.install_date)) / 365.25", "years")
            + ".")})
    # documents: CBL (D05), RCA (D08), failed-job reports (D02)
    docs = c.docs
    failed_wo = set()
    if wo is not None and not wo.empty:
        failed_wo = set(wo[wo["outcome"] == "FAILED"]["workover_id"].astype(str))
    lessons = []
    for d in sorted(docs, key=lambda x: str(x.get("doc_date"))):
        if str(d.get("doc_date"))[:10] > c.as_of.isoformat():
            continue
        t = str(d.get("doc_type_id") or d.get("doc_type"))
        why = None
        if t in ("D05", "D5"):
            why = "cement bond log"
        elif t in ("D08", "D8"):
            why = "failure root-cause analysis"
        elif t in ("D02", "D2") and str(d.get("workover_id")) in failed_wo:
            why = "report of a FAILED job"
        if why:
            lessons.append((d, why))
    if lessons:
        rows = []
        for d, why in lessons:
            did = str(d["doc_id"])
            note = why
            if why == "cement bond log":
                f = _doc_facts(did)
                if f.get("isolation_assessment"):
                    note = why + "; isolation " + fb.put(f"doc.{did}.isolation", f.get("isolation_assessment"),
                                                         f"{did} facts.json isolation_assessment")
            rows.append([c.cite(d, why),
                         fb.put(f"doc.{did}.title", d.get("title"), "document_index.title"),
                         fb.put(f"doc.{did}.date", d.get("doc_date"), "document_index.doc_date"),
                         note])
        blocks.append({"kind": "table", "title": "Lessons from documents (cited)",
                       "headers": ["Document", "Title", "Date", "Why it matters"], "rows": rows,
                       "col_weights": [1.3, 2.6, 0.8, 1.6], "empty_text": ""})
    elif not docs:
        blocks.append(_unavailable("document_index"))
    else:
        blocks.append({"kind": "p", "style": "body", "text": "No cement bond log, root-cause note or failed-job report on file for this well."})
    # failed jobs (from rows)
    if failed_wo:
        items = []
        for r in wo[wo["outcome"] == "FAILED"].itertuples(index=False):
            k = f"wo.{r.workover_id}"
            items.append(fb.put(f"{k}.job", _job_code(r), "workover_history.catalogue_job_code") + " on "
                         + fb.put(f"{k}.start", r.start_date, "workover_history.start_date") + " failed (failure mode "
                         + fb.put(f"{k}.failure", r.failure_code, "workover_history.failure_code") + ").")
        blocks.append({"kind": "p", "style": "emphasis", "text": "Failed interventions on this well"})
        blocks.append({"kind": "bullets", "items": items})
        c.highlights.append("Failed jobs on record: " + fb.put("haz.n_failed", len(items), "count(workover_history outcome = FAILED)")
                            + "; see Hazards & Lessons before mobilising.")
    blocks.append({"kind": "p", "style": "note",
                   "text": "Site HSE: follow the SOP well-control and permit-to-work steps; this dossier does not replace the job safety analysis."})
    return blocks


def _sec_logistics(c: _Ctx) -> list[dict]:
    fb = c.fb
    nv = c.nba.value if c.nba is not None else None
    st = c.profile.status
    pairs = [["Field / cluster", fb.put("field", c.profile.identity["field"], "well_master.field") + " / "
              + fb.put("cluster_id", c.profile.identity.get("cluster_id"), "well_master.cluster_id")],
             ["Current episode", fb.put("episode_status", st.get("episode_status"), "well_status_history.status")]]
    if nv is None or not nv.actions:
        return [{"kind": "kv", "cols": 2, "pairs": pairs},
                _unavailable("recommend_next_best_action (" + _tool_status(c.nba) + ")")]
    a = nv.actions[0]
    pairs += [["Job", fb.put("nba.1.job", a.job_code, "TC-022 actions.job_code (job_catalogue)")],
              ["Unit", fb.put("log.unit", a.unit_type, "job_catalogue.equipment")],
              ["Needs rig", fb.put("log.rig", a.requires_rig, "job_catalogue.requires_rig")],
              ["Rig-days", fb.put("nba.1.rig", a.rig_days, "TC-022 actions.rig_days")],
              ["Duration", fb.put("log.dmin", a.duration_days_min, "TC-022 actions.duration_days_min") + " to "
               + fb.put("log.dmax", a.duration_days_max, "TC-022 actions.duration_days_max", "days")],
              ["MRO status", fb.put("log.mro", a.mro_status, "TC-022 actions.mro_status (MRO stock)")],
              ["MRO blocker", fb.put("log.mro_blocker", a.mro_blocker, "TC-022 actions.mro_blocker", missing="-")],
              ["Earliest start", fb.put("log.earliest", a.earliest_start_date, "TC-022 actions.earliest_start_date", missing="-")]]
    slot = a.rig_slot or {}
    if slot:
        if slot.get("status") == "OK":
            pairs.append(["Rig slot", fb.put("log.slot_rig", slot.get("rig_id"), "rig_calendar.rig_id") + " from "
                          + fb.put("log.slot_start", slot.get("start_date"), "rig_calendar free window start")])
        else:
            pairs.append(["Rig slot", fb.put("log.slot_status", slot.get("status"), "TC-022 rig_slot.status")])
            if slot.get("message"):
                pairs.append(["Rig slot note", fb.text("log.slot_msg", slot.get("message"), "TC-022 rig_slot.message")])
    if c.show_cost:
        pairs.append(["Cost band", fb.put("nba.1.cost", a.cost_band, "job_catalogue.cost_band")])
    return [{"kind": "kv", "cols": 2, "pairs": pairs}]


def _sec_sources(c: _Ctx) -> list[dict]:
    fb = c.fb
    tparts = [t + " " + fb.put(f"src.table.{t}", n, f"count({t} rows read for this well)") for t, n in sorted(c.tables.items())]
    blocks: list[dict] = [{"kind": "p", "style": "note", "text": "Tables read (rows for this well): " + "; ".join(tparts) + "."}]
    tparts = []
    for tid, r in c.tools.items():
        prov = (r.provenance if r is not None else {}) or {}
        tparts.append(fb.put(f"src.tool.{tid}", tid, "tool contract id") + " "
                      + fb.put(f"src.tool.{tid}.status", _tool_status(r), "ToolResult.status") + " input hash "
                      + fb.put(f"src.tool.{tid}.hash", prov.get("input_hash"), "provenance.input_hash", missing="-"))
    blocks.append({"kind": "p", "style": "note", "text": "Tool returns: " + "; ".join(tparts) + "."})
    meta = {str(d["doc_id"]): d for d in c.docs}
    drows = []
    for did, d in c.cited.items():
        m = {**d, **{k: v for k, v in meta.get(did, {}).items() if v is not None}}
        drows.append([fb.put(f"doc.{did}.id", did, "document_index.doc_id"),
                      fb.put(f"doc.{did}.title", m.get("title"), "document_index.title"),
                      fb.put(f"doc.{did}.type", m.get("doc_type_id") or m.get("doc_type"), "document_index.doc_type"),
                      fb.put(f"doc.{did}.date", m.get("doc_date"), "document_index.doc_date", missing="-"),
                      m.get("why", "")])
    blocks.append({"kind": "table", "title": "Cited documents (open at /api/docs/<doc_id>.pdf)",
                   "headers": ["Document", "Title", "Type", "Date", "Cited for"], "rows": drows,
                   "col_weights": [1.4, 2.8, 0.5, 0.8, 1.2], "empty_text": UNAVAILABLE_FMT.format("document_index")})
    return blocks


# =================================================================================================
# validation
# =================================================================================================
def _norm(s: str) -> str:
    return WS_RE.sub("", s or "")


def validate_pdf(pdf: Path, facts: dict[str, str]) -> dict:
    """Fact-slot validator: every fact value is in the text layer; no digit outside a fact (or the page footer).

    Values are matched as whole number tokens tolerant of line breaks (``docs_pdf.validate.value_regex``), longest
    first, and blanked out; any digit left afterwards is an un-slotted number.
    """
    from pypdf import PdfReader

    from app.analytics.docs_pdf.validate import value_regex

    pages = [p.extract_text() or "" for p in PdfReader(str(pdf)).pages]
    rest = LAYOUT_RE.sub(" ", "\n".join(pages))
    vals = sorted({v.strip() for v in facts.values() if v and v.strip()}, key=lambda v: len(_norm(v)), reverse=True)
    rxs = [(v, value_regex(v)) for v in vals]
    missing = [v for v, rx in rxs if not rx.search(rest)]
    for _v, rx in rxs:
        rest = rx.sub(" ", rest)
    stray = sorted({m.group(0) for m in re.finditer(r"\S{0,12}\d\S{0,12}", rest)})
    n_digit_facts = sum(1 for v in vals if DIGIT_RE.search(v))
    return {"ok": not missing and not stray, "pages": len(pages), "n_facts": len(vals),
            "n_numeric_facts": n_digit_facts, "missing_values": missing[:20], "stray_digits": stray[:20],
            "traced_pct": 100.0 if not stray else round(100.0 * (1 - len(stray) / max(1, n_digit_facts + len(stray))), 1)}


# =================================================================================================
# TC-023
# =================================================================================================
def _assemble(wid: str, as_of: date, persona: str, override: bool) -> _Ctx:
    from app.agent import rbac

    from .attribution import attribute_decline
    from .counterfactual import compare_interventions
    from .nba import recommend_next_best_action
    from .well_profile import well_production_series

    prof = well_profile(wid, k_neighbours=3, as_of=as_of)
    tools: dict[str, ToolResult | None] = {"TC-029": prof}
    aso = as_of if override else None
    series = well_production_series(wid, months=PRODUCTION_MONTHS, metrics=["oil"], overlay_decline_fit=False, as_of=as_of)
    tools["TC-017"] = series
    attr = attribute_decline(well_id=wid, as_of=as_of, window_days=ATTRIBUTION_WINDOW_DAYS)
    tools["TC-019"] = attr
    nba = recommend_next_best_action(wid, as_of=aso)
    tools["TC-022"] = nba
    cf = None
    nv = nba.value
    if nv is not None and nv.actions and nv.actions[0].job_code != "NO_JOB_JUSTIFIED":
        alt = nv.actions[1].job_code if len(nv.actions) > 1 else next(
            (r.get("job_code") for r in (nv.rejected or []) if r.get("job_code")), None)
        if alt:
            try:
                cf = compare_interventions(wid, nv.actions[0].job_code, alt, as_of=aso)
            except Exception:  # noqa: BLE001 - optional section line
                cf = None
            tools["TC-027"] = cf
    docs = _docs_for_well(wid)
    tables = {}
    for t in ("well_master", "casing_tally", "tubing_string", "perforation_intervals", "formation_tops",
              "daily_production", "well_tests", "pressure_surveys", "workover_history", "well_status_history"):
        try:
            tables[t] = len(well_rows(t, wid)) if t != "well_master" else 1
        except Exception:  # noqa: BLE001
            tables[t] = 0
    tables["document_index"] = len(docs)
    p = rbac.resolve_persona(persona)
    return _Ctx(wid=wid, as_of=as_of, persona=p, fb=FactBook(), profile=prof.value, series=series, attribution=attr,
                nba=nba, cf=cf, docs=docs, cited={}, tools=tools, tables=tables,
                full_construction=rbac.access(p, "well.construction") is rbac.Access.FULL,
                show_cost=rbac.allowed(p, "cost_band.view"))


def _compose(c: _Ctx, wo, level: int, doc_id: str) -> tuple[dict, str]:
    """All nine sections at density ``level`` (fresh FactBook / citations / highlights each time)."""
    c.fb, c.cited, c.highlights, c.level = FactBook(), {}, [], level
    sections = [
        (SECTION_TITLES[0], _sec_identity(c)),
        (SECTION_TITLES[1], _sec_construction(c)),
        (SECTION_TITLES[2], _sec_production(c)),
        (SECTION_TITLES[3], _sec_timeline(c, wo)),
        (SECTION_TITLES[4], _sec_repeat(c, wo)),
        (SECTION_TITLES[5], _sec_diagnosis(c)),
        (SECTION_TITLES[6], _sec_hazards(c, wo)),
        (SECTION_TITLES[7], _sec_logistics(c)),
    ]
    sections.append((SECTION_TITLES[8], _sec_sources(c)))
    fb = c.fb
    if len(c.highlights) < 3:
        isum = c.profile.interventions_summary
        c.highlights.append("Interventions to date " + fb.put("wo.total", isum.get("total"), "count(workover_history rows, censoring rows excluded)")
                            + "; last " + fb.put("isum.last_job", isum.get("last_job_code"), "workover_history.catalogue_job_code")
                            + " on " + fb.put("isum.last_date", isum.get("last_job_date"), "workover_history.start_date")
                            + " (" + fb.put("isum.last_outcome", isum.get("last_outcome"), "workover_history.outcome") + ").")
    sections[0][1].insert(0, {"kind": "callout", "tone": "info",
                              "text": "Key points for the field team: " + " | ".join(c.highlights[:3])})
    data_hash = fb.data_hash()
    doc = {
        "title": "Field dossier: " + fb.put("well_id", c.wid, "well_master.well_id") + " ("
                 + fb.put("field", c.profile.identity["field"], "well_master.field") + ")",
        "subtitle": "Pre-job well history for field dispatch, as of " + fb.put("as_of", c.as_of, "request as_of (default settings.AS_OF)")
                    + "; persona " + fb.put("persona", c.persona, "request persona (X-Persona)") + "; data hash "
                    + fb.put("data_sha256", data_hash[:16], "sha256(facts values + sources), first sixteen hex"),
        "banner": "SYNTHETIC DATA - WellPulse field dossier - built only from tables, tool returns and cited documents",
        "footer_id": fb.put("doc_id", doc_id, "TC-023 doc_id (well, as_of, persona)"),
        "meta": {"title": "WellPulse field dossier " + c.wid, "author": "WellPulse dossier tool", "subject": "Field-engineer dossier"},
        "sections": [{"title": t, "blocks": b} for t, b in sections],
    }
    return doc, data_hash


def build_well_dossier(well_id: str, persona: str | None = None, as_of: date | str | None = None,
                       refresh: bool = True) -> ToolResult:
    """TC-023. Build (or reuse, when ``refresh`` is False and a validated file exists) the field dossier PDF.

    Returns ``ToolResult(value=Dossier)``; UNAVAILABLE for unknown wells or a persona without ``docs.sop_dossier``.
    """
    from app.agent import rbac

    t0 = time.perf_counter()
    p = rbac.resolve_persona(persona)
    wid = (well_id or "").strip().upper()
    if isinstance(as_of, str) and as_of:
        as_of = date.fromisoformat(as_of)
    override = as_of is not None and as_of != settings.AS_OF
    aso: date = as_of or settings.AS_OF  # type: ignore[assignment]
    params = {"well_id": wid, "persona": p, "as_of": aso.isoformat(), "version": DOSSIER_VERSION}
    if not rbac.allowed(p, "docs.sop_dossier"):
        return rbac.denied(p, "docs.sop_dossier", "dossier")
    if wid.startswith("GLK-"):
        return unavailable(TOOL_ID, params, t0, ["well_id"], "GLK- IDs retired in v0.4; use GK-")
    if well_master_row(wid) is None:
        return unavailable(TOOL_ID, params, t0, ["well_id"], f"Well {well_id} not found.")
    name = dossier_name(wid, aso, p)
    out_dir = dossier_dir()
    pdf, facts_file = out_dir / f"{name}.pdf", out_dir / f"{name}.facts.json"
    if not refresh and pdf.exists() and facts_file.exists():
        rec = json.loads(facts_file.read_text())
        if rec.get("version") == DOSSIER_VERSION and rec.get("validation", {}).get("ok"):
            return ToolResult(ToolStatus.OK, _dossier_from_rec(rec, cached=True), [], rec.get("message", ""),
                              build_provenance(TOOL_ID, params, t0, cached=True, data_sha256=rec["data_sha256"]))

    c = _assemble(wid, aso, p, override)
    if c.profile is None:
        return unavailable(TOOL_ID, params, t0, ["well_profile"], f"TC-029 returned no profile for {wid}.")
    wo = _workovers(wid, aso)
    doc_id = dossier_doc_id(wid, aso, p)
    from app.analytics.docs_pdf.dossier_render import render_dossier_pdf

    tmp = pdf.with_suffix(".tmp.pdf")
    t_r = time.perf_counter()
    for level in range(len(COMPACT_LEVELS)):
        doc, data_hash = _compose(c, wo, level, doc_id)
        pages = render_dossier_pdf(doc, tmp)
        if pages <= 4:
            break
    render_ms = round((time.perf_counter() - t_r) * 1000.0, 1)
    fb = c.fb
    validation = validate_pdf(tmp, fb.values)
    os.replace(tmp, pdf)
    pdf_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sources = [{"doc_id": did, "title": (next((x.get("title") for x in c.docs if str(x["doc_id"]) == did), None) or d.get("title")),
                "doc_date": (next((x.get("doc_date") for x in c.docs if str(x["doc_id"]) == did), None) or d.get("doc_date")),
                "why": d.get("why"), "url": f"/api/docs/{did}.pdf"} for did, d in c.cited.items()]
    highlights = c.highlights[:3]
    status = ToolStatus.OK
    missing = [s for s, n in (("casing_tally", len(c.profile.construction["casing"])),
                              ("tubing_string", len(c.profile.construction["tubing"])),
                              ("formation_tops", len(c.profile.lithology))) if not n]
    if missing or not validation["ok"] or not (2 <= pages <= 4):
        status = ToolStatus.LOW_CONFIDENCE
    msg = (f"Dossier {doc_id}: {pages} pages, {len(fb.values)} facts, validation {'OK' if validation['ok'] else 'FAILED'}"
           + (f"; UNAVAILABLE sections for {', '.join(missing)}" if missing else "") + ".")
    rec = {
        "doc_id": doc_id, "version": DOSSIER_VERSION, "well_id": wid, "as_of": aso.isoformat(), "persona": p,
        "file_name": f"{name}.pdf", "pages": pages, "sections": list(SECTION_TITLES), "highlights": highlights,
        "sources": sources, "facts": fb.values, "fact_sources": fb.sources, "data_sha256": data_hash,
        "pdf_sha256": pdf_sha, "validation": validation, "render_ms": render_ms, "message": msg,
        "tools": {k: (_tool_status(v), (v.provenance or {}).get("input_hash") if v is not None else None)
                  for k, v in c.tools.items()},
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    facts_file.write_text(json.dumps(rec, indent=1, default=str))
    return ToolResult(status, _dossier_from_rec(rec), missing, msg,
                      build_provenance(TOOL_ID, params, t0, data_sha256=data_hash, pdf_sha256=pdf_sha,
                                       pages=pages, validation_ok=validation["ok"]))


def _dossier_from_rec(rec: dict, cached: bool = False) -> Dossier:
    name = rec["file_name"]
    return Dossier(doc_id=rec["doc_id"], well_id=rec["well_id"], as_of=date.fromisoformat(rec["as_of"]),
                   persona=rec["persona"], pdf_url=PDF_URL_FMT.format(name=name),
                   facts_url=PDF_URL_FMT.format(name=name.replace(".pdf", ".facts.json")), file_name=name,
                   pages=rec["pages"], sections=rec["sections"], highlights=rec["highlights"], sources=rec["sources"],
                   n_facts=len(rec["facts"]), data_sha256=rec["data_sha256"], pdf_sha256=rec["pdf_sha256"],
                   validation=rec["validation"], render_ms=rec["render_ms"], cached=cached)


# late import keeps the module importable for monkeypatching in tests
from .well_profile import well_profile
