"""TC-027 ``compare_interventions`` — six-dimension counterfactual with a diagnostic-fit veto (SDD §9.2, F-13).

Answers "why this job and not that one?" (verbatim T2: "why not just wax removal? … perforation … super deep").
Every cell is computed by an existing tool; the agent narrates and adds no arguments:

====================  =====================================================================================
1 diagnostic_fit      TC-022 :func:`~.nba.diagnostic_fit` over TC-002 / TC-005 / TC-003 / TC-004 and the latest
                      two ``pressure_surveys`` rows (SBHP, PI); the D5 cement-bond-log isolation assessment is
                      quoted as supporting evidence for water / integrity classes
2 well_history        prior attempts of each job's class on this well (+ related water-control attempts for
                      water classes) from ``workover_history`` with the D2 report / D8 RCA document ids
3 field_efficacy      TC-022 Beta-smoothed ``p_success`` with its n (field × class × lift, this well, asset prior)
4 execution           catalogue rig / rigless, unit type, rig-days, duration band, cost band; TC-011 MRO; rig slot
5 value               TC-022 score = deferred bbl × p_success ÷ rig-days × risk discount (bbl per rig-day)
6 verdict             rule below
====================  =====================================================================================

**Verdict rule.** Diagnostic fit decides first: ``CONTRADICTED`` (✘) loses regardless of cost or value (veto);
``FIT`` (✔) beats ``UNCLEAR`` (?). With equal fit the higher value wins; a value margin < 10 % is ``CLOSE`` (honest
concession, BDD-F13-S03). If the recommended job is the one that is ✘, the verdict is ``ALTERNATIVE_PREFERRED``.
Both ✘ → ``NEITHER_FITS``. No currency anywhere (D-1).

Job names may be catalogue codes (``CEMENT_SQUEEZE``), class ids (``IC-04``), class names (``WAX_REMOVAL``,
``WATER_SHUTOFF_SQUEEZE``, ``REPERFORATION``) or archetypes ("Squeeze / Water Shut-off"); classes resolve to the
best job of that class for the well (:func:`~.nba.select_job`).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

from app import settings

from .common import ToolResult, ToolStatus, WellId, build_provenance, load_yaml, register_cache, unavailable
from .nba import (
    CONTRADICTED,
    FIT,
    FIT_ORDER,
    FIT_SYMBOL,
    UNCLEAR,
    WATER_CLASSES,
    CandidateEval,
    WellEvidence,
    _catalogue,
    _doc_store,
    _well_docs,
    evaluate_job,
    ic_labels,
    job_ic,
    recommend_next_best_action,
    select_job,
    well_evidence,
)

TOOL_ID = "TC-027"
CLOSE_MARGIN_PCT = 10.0
INTEGRITY_CLASSES = WATER_CLASSES | {"IC-14"}

# keyword -> class, for free-text names ("why not just wax removal?")
_KEYWORDS: list[tuple[str, str]] = [
    ("NOJOB", "IC-15"), ("SQUEEZE", "IC-11"), ("WSO", "IC-11"), ("WATERSHUTOFF", "IC-11"), ("GEL", "IC-11"),
    ("CHOKE", "IC-13"), ("CONING", "IC-13"), ("STRADDLE", "IC-12"), ("ZONAL", "IC-12"), ("ISOLAT", "IC-12"),
    ("REPERF", "IC-10"), ("PERFORAT", "IC-10"), ("ACID", "IC-09"), ("STIMUL", "IC-09"), ("FRAC", "IC-09"),
    ("WAX", "IC-04"), ("PARAFFIN", "IC-04"), ("SCALE", "IC-05"), ("SAND", "IC-06"), ("GLV", "IC-07"),
    ("GASLIFT", "IC-07"), ("PUMP", "IC-01"), ("ROD", "IC-02"), ("TUBING", "IC-03"), ("LIFTOPT", "IC-08"),
    ("ESP", "IC-08"), ("SURFACE", "IC-14"), ("CASING", "IC-14"),
]


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def resolve_job(name: str, ev: WellEvidence) -> tuple[str, str] | None:
    """(catalogue job_code, how it was resolved) for a user-supplied job / class name."""
    from .intervention_classifier import IC_NAMES

    n = _norm(name)
    if not n:
        return None
    cat = _catalogue()
    for j in cat.index:
        if _norm(j) == n:
            return str(j), f"catalogue job {j}"
    labels = ic_labels()
    ic = None
    m = re.fullmatch(r"IC(\d{1,2})", n)
    if m:
        ic = f"IC-{int(m.group(1)):02d}"
    if ic is None:
        ic = next((k for k, v in IC_NAMES.items() if _norm(v) == n), None)
    if ic is None:
        ic = next((k for k, v in labels.items() if _norm(v) == n), None)
    if ic is None:
        arch = load_yaml("ic_map.yaml").get("archetypes", {})
        for k, v in arch.items():
            if _norm(k) == n:
                ic = v if isinstance(v, str) else v.get("ic")
    if ic is None:
        ic = next((c for kw, c in _KEYWORDS if kw in n), None)
    if ic is None or ic not in labels:
        return None
    job, why = select_job(ic, ev)
    return job, f"class {ic} ({labels[ic]}) -> {job}: {why}"


# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Cell:
    summary: str
    symbol: str | None
    values: dict


@dataclass(frozen=True)
class Row:
    dimension: str
    title: str
    recommended: Cell
    alternative: Cell
    winner: str | None
    evidence_refs: list[str]


@dataclass(frozen=True)
class JobRef:
    job_code: str
    job_name: str
    ic: str
    ic_label: str
    requested_as: str
    resolution: str


@dataclass(frozen=True)
class Counterfactual:
    well_id: WellId
    as_of: date
    recommended: JobRef
    alternative: JobRef
    rows: list[Row]
    verdict: str
    deciding_dimension: str
    margin_pct: float | None
    verdict_text: str
    citations: list[dict]
    pressure_survey: dict | None
    flags: list[str] = field(default_factory=list)


def _cbl_facts(well_id: WellId) -> list[dict]:
    st = _doc_store()
    d = _well_docs(well_id)
    if st is None or d.empty:
        return []
    out = []
    for r in d[d["doc_type"] == "D05"].sort_values("doc_date").itertuples(index=False):
        f = (st.root / r.path).with_name(f"{r.doc_id}.facts.json")
        facts = json.loads(f.read_text()).get("facts", {}) if f.exists() else {}
        out.append({"doc_id": str(r.doc_id), "title": r.title, "doc_date": str(r.doc_date),
                    "isolation_assessment": facts.get("isolation_assessment"),
                    "assessment_basis": facts.get("assessment_basis")})
    return out


def _winner(a: float | None, b: float | None, higher_better: bool = True, tol: float = 1e-9) -> str | None:
    if a is None or b is None:
        return None
    if abs(a - b) <= tol:
        return "TIE"
    return "RECOMMENDED" if (a > b) == higher_better else "ALTERNATIVE"


def _fit_row(rc: CandidateEval, ac: CandidateEval, ev: WellEvidence, cbl: list[dict]) -> Row:
    ps = ev.pressure
    ps_txt = ""
    ps_vals: dict = {}
    refs = ["TC-002 chan_diagnostic", "TC-005 detect_mechanical_signature", "TC-003 fillage_proxy",
            "TC-004 check_offsets"]
    if ps:
        lt = ps["latest"]
        ps_vals = {"survey_id": lt["survey_id"], "survey_date": str(lt["survey_date"]), "sbhp_kgcm2": lt["sbhp_kgcm2"],
                   "pi_bpd_per_kgcm2": lt["pi_bpd_per_kgcm2"], "sbhp_change_pct": ps["sbhp_change_pct"],
                   "pi_change_pct": ps["pi_change_pct"]}
        ps_txt = (f" | pressure survey {lt['survey_date']}: SBHP {lt['sbhp_kgcm2']} kg/cm2, PI {lt['pi_bpd_per_kgcm2']} "
                  f"bpd/kg/cm2" + (f" (SBHP {ps['sbhp_change_pct']:+.1f}%, PI {ps['pi_change_pct']:+.1f}% vs "
                                   f"{ps['previous']['survey_date']})" if ps.get("previous") else ""))
        refs.append(f"pressure_surveys:{lt['survey_id']}")
        if ps.get("doc_id"):
            refs.append(ps["doc_id"])
    else:
        ps_txt = " | no pressure survey on or before as_of"
        refs.append("pressure_surveys:none")

    def cell(c: CandidateEval) -> Cell:
        extra = ""
        if c.ic in INTEGRITY_CLASSES and cbl:
            last = cbl[-1]
            extra = (f" | cement bond log {last['doc_id']} ({last['doc_date'][:4]}): isolation "
                     f"{last['isolation_assessment']} ({last['assessment_basis']})")
        return Cell(f"{c.fit_symbol} {c.fit_evidence}{extra}{ps_txt}", c.fit_symbol,
                    {"diagnostic_fit": c.diagnostic_fit, **ps_vals})

    if any(c.ic in INTEGRITY_CLASSES for c in (rc, ac)):
        refs += [x["doc_id"] for x in cbl]
    w = _winner(FIT_ORDER[rc.diagnostic_fit], FIT_ORDER[ac.diagnostic_fit])
    return Row("diagnostic_fit", "1 · Diagnostic fit (Chan, signature, fillage, offsets, pressure survey)",
               cell(rc), cell(ac), w, refs)


def _history_cell(c: CandidateEval, ev: WellEvidence) -> tuple[Cell, list[str]]:
    same = [h for h in ev.history if h["intervention_class"] == c.ic]
    related = ([h for h in ev.history if h["intervention_class"] in WATER_CLASSES and h["intervention_class"] != c.ic]
               if c.ic in WATER_CLASSES else [])

    def line(h: dict) -> str:
        rl = f", run life {h['run_life_days']:.0f} d" if h["run_life_days"] is not None else ""
        doc = f" [{h['report_doc_id']}]" if h["report_doc_id"] else ""
        return f"{h['job_code']} {h['start_date']} {h['outcome']}{rl}{doc}"

    parts = [f"{len(same)} prior {c.ic} job(s) on this well" + (": " + "; ".join(line(h) for h in same[:4]) if same else "")]
    if related:
        parts.append("related water-control: " + "; ".join(line(h) for h in related[:3]))
    refs = [x for h in same[:4] + related[:3] for x in (h["report_doc_id"], h["rca_doc_id"]) if x]
    last = same[0] if same else None
    vals = {"n_prior": len(same), "n_prior_failed": sum(1 for h in same if h["outcome"] == "FAILED"),
            "last_date": str(last["start_date"]) if last else None, "last_outcome": last["outcome"] if last else None,
            "last_run_life_days": last["run_life_days"] if last else None, "n_related_water_jobs": len(related),
            "n_related_failed": sum(1 for h in related if h["outcome"] == "FAILED")}
    return Cell(" | ".join(parts), None, vals), refs


def _history_row(rc: CandidateEval, ac: CandidateEval, ev: WellEvidence) -> Row:
    r, rr = _history_cell(rc, ev)
    a, ar = _history_cell(ac, ev)
    rf = r.values["n_prior_failed"] + 0
    af = a.values["n_prior_failed"] + 0
    w = None if rf == af else ("RECOMMENDED" if rf < af else "ALTERNATIVE")
    return Row("well_history", "2 · This well's history (workover_history + reports)", r, a, w,
               ["workover_history"] + list(dict.fromkeys(rr + ar)))


def _efficacy_cell(c: CandidateEval, ev: WellEvidence) -> Cell:
    d = c.p_success_detail
    if c.p_success is None:
        return Cell(f"p_success unavailable (n_asset={d['n_asset']})", None, {"p_success": None, "n": d["n_field"]})
    return Cell(f"p = {c.p_success:.2f} (n = {d['n_field']} {ev.field} {ev.lift_type} {c.ic} jobs, {d['s_field']} "
                f"successful; this well {d['s_well']}/{d['n_well']}; asset prior {d['p_asset']} from {d['n_asset']} jobs)",
                None, {"p_success": c.p_success, "n": d["n_field"], "s_field": d["s_field"], "n_well": d["n_well"],
                       "s_well": d["s_well"], "p_asset": d["p_asset"], "n_asset": d["n_asset"], "alpha": d["alpha"]})


def _exec_cell(c: CandidateEval) -> Cell:
    slot = c.rig_slot or {}
    slot_txt = (f", rig slot {slot.get('rig_id')} from {slot.get('start_date')}" if slot.get("status") == "OK"
                else (f", rig slot: {slot.get('message')}" if slot else ""))
    blk = f" ({c.mro_blocker})" if c.mro_blocker else ""
    return Cell(f"{'rig' if c.requires_rig else 'rigless'} · {c.unit_type} · {c.rig_days} rig-days · duration "
                f"{c.duration_days_min}-{c.duration_days_max} d · cost band {c.cost_band} · MRO {c.mro_status}{blk} · "
                f"earliest start {c.earliest_start_date or 'not determined'}{slot_txt}", None,
                {"requires_rig": c.requires_rig, "unit_type": c.unit_type, "rig_days": c.rig_days,
                 "duration_days_min": c.duration_days_min, "duration_days_max": c.duration_days_max,
                 "cost_band": c.cost_band, "mro_status": c.mro_status, "mro_blocker": c.mro_blocker,
                 "earliest_start_date": str(c.earliest_start_date) if c.earliest_start_date else None})


def _value_cell(c: CandidateEval) -> Cell:
    disc = 1.0 - min(0.45, 0.15 * len(c.risk_flags))
    if c.deferred_bbl_12mo is None or c.p_success is None:
        return Cell(f"value unavailable (TC-009 {c.uplift_status})", None, {"score": c.score})
    rf = f" [{', '.join(c.risk_flags)}]" if c.risk_flags else ""
    return Cell(f"{c.deferred_bbl_12mo:.0f} bbl/12 mo (+{c.uplift_bopd} BOPD) × p {c.p_success:.2f} ÷ "
                f"{max(c.rig_days, 0.5)} rig-days × risk {disc:.2f}{rf} = {c.score} bbl per rig-day", None,
                {"deferred_bbl_12mo": c.deferred_bbl_12mo, "uplift_bopd": c.uplift_bopd, "p_success": c.p_success,
                 "rig_days_used": max(c.rig_days, 0.5), "risk_discount": round(disc, 2), "score": c.score,
                 "risk_flags": ", ".join(c.risk_flags) or None})


def _verdict(rc: CandidateEval, ac: CandidateEval) -> tuple[str, str, float | None, str]:
    hi = max(rc.score, ac.score)
    margin = round((rc.score - ac.score) / hi * 100.0, 1) if hi > 0 else None
    fr, fa = rc.diagnostic_fit, ac.diagnostic_fit
    val_txt = (f"On value the recommended job scores {rc.score} vs {ac.score} bbl per rig-day"
               + (f" (margin {margin:+.1f}%)" if margin is not None else ""))
    if fr == CONTRADICTED and fa == CONTRADICTED:
        return ("NEITHER_FITS", "diagnostic_fit", margin,
                f"Neither job fits the diagnosis: {rc.job_code} ✘ ({rc.fit_evidence}); {ac.job_code} ✘ ({ac.fit_evidence}).")
    if FIT_ORDER[fr] != FIT_ORDER[fa]:
        win, lose = (rc, ac) if FIT_ORDER[fr] > FIT_ORDER[fa] else (ac, rc)
        verdict = "RECOMMENDED_PREFERRED" if win is rc else "ALTERNATIVE_PREFERRED"
        veto = lose.diagnostic_fit == CONTRADICTED
        txt = (f"{win.job_name} ({win.job_code}) is preferred over {lose.job_name} ({lose.job_code}). Deciding "
               f"dimension: diagnostic fit — {win.job_code} {win.fit_symbol}: {win.fit_evidence}; {lose.job_code} "
               f"{lose.fit_symbol}: {lose.fit_evidence}. " + val_txt + "; but "
               + ("a job that does not address the diagnosed mechanism loses regardless of cost or value (veto)."
                  if veto else "a job with direct diagnostic support ranks above one without it."))
        return verdict, "diagnostic_fit", margin, txt
    if margin is None:
        return "CLOSE", "value", None, (f"Both jobs have the same diagnostic fit ({FIT_SYMBOL[fr]}) and no computable "
                                        f"value; engineer judgement needed.")
    if abs(margin) < CLOSE_MARGIN_PCT:
        nxt = ("execution" if rc.rig_days != ac.rig_days else "field_efficacy")
        return "CLOSE", "value", margin, (
            f"Close call: same diagnostic fit ({FIT_SYMBOL[fr]}). {val_txt}, inside the {CLOSE_MARGIN_PCT:.0f}% band. "
            f"The tie-breaker is {nxt.replace('_', ' ')}: {rc.job_code} {rc.rig_days} rig-days / p {rc.p_success} vs "
            f"{ac.job_code} {ac.rig_days} rig-days / p {ac.p_success}.")
    win, lose = (rc, ac) if margin > 0 else (ac, rc)
    return ("RECOMMENDED_PREFERRED" if win is rc else "ALTERNATIVE_PREFERRED", "value", margin,
            f"{win.job_name} ({win.job_code}) is preferred: same diagnostic fit ({FIT_SYMBOL[fr]}). {val_txt}.")


def _citations(rows: list[Row], rc: CandidateEval, ac: CandidateEval, ev: WellEvidence) -> list[dict]:
    st = _doc_store()
    ids: dict[str, str] = {}
    for r in rows:
        for ref in r.evidence_refs:
            if ":" in ref or ref.startswith("TC-") or ref == "workover_history":
                continue
            ids.setdefault(ref, {"diagnostic_fit": "diagnostic evidence", "well_history": "prior job on this well"}
                           .get(r.dimension, r.dimension))
    for c in (rc, ac):
        if c.sop_doc_id:
            ids.setdefault(c.sop_doc_id, f"SOP for {c.job_code}")
    out = []
    for doc_id, why in ids.items():
        meta = st.doc(doc_id) if st is not None else None
        if meta is None:
            continue  # only documents that resolve via /api/docs/{id}.pdf are cited
        out.append({"doc_id": doc_id, "title": meta.get("title"), "doc_type": meta.get("doc_type"),
                    "doc_date": str(meta.get("doc_date")) if meta.get("doc_date") else None,
                    "url": f"/api/docs/{doc_id}.pdf", "why": why})
    return out


def compare_interventions(well_id: WellId, recommended_job: str | None = None, alternative_job: str = "",
                          as_of: date | None = None) -> ToolResult:
    return _cf_cached(str(well_id).strip().upper(), (recommended_job or "").strip(), (alternative_job or "").strip(),
                      as_of or settings.AS_OF)


@lru_cache(maxsize=512)
def _cf_cached(well_id: WellId, recommended_job: str, alternative_job: str, as_of: date) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "recommended_job": recommended_job or None, "alternative_job": alternative_job,
              "as_of": str(as_of)}
    ev = well_evidence(well_id, as_of)
    if ev is None:
        return unavailable(TOOL_ID, params, t0, ["well_id"], f"Well {well_id} not found.")
    if not alternative_job:
        return unavailable(TOOL_ID, params, t0, ["alternative_job"], "Name the alternative job to compare against.")
    flags: list[str] = []
    if recommended_job:
        rr = resolve_job(recommended_job, ev)
        if rr is None:
            return unavailable(TOOL_ID, params, t0, ["recommended_job"], f"Unknown job or class '{recommended_job}'.")
        rec_req = recommended_job
    else:
        nba = recommend_next_best_action(well_id, as_of=as_of)
        if nba.value is None or not nba.value.actions:
            return unavailable(TOOL_ID, params, t0, ["recommended_job"],
                               f"No TC-022 recommendation for {well_id} to defend ({nba.message}); name one.")
        j = nba.value.actions[0].job_code
        rr, rec_req = (j, f"TC-022 rank 1 for {well_id}"), "NBA_RANK_1"
        flags += [f for f in nba.value.flags if f in ("MODEL_PHYSICS_DISAGREEMENT", "G1_CONING_GUARDRAIL",
                                                       "G2_RESERVOIR_DECLINE")]
    ar = resolve_job(alternative_job, ev)
    if ar is None:
        return unavailable(TOOL_ID, params, t0, ["alternative_job"], f"Unknown job or class '{alternative_job}'.")
    if ar[0] == rr[0]:
        return unavailable(TOOL_ID, params, t0, ["alternative_job"],
                           f"'{alternative_job}' resolves to the recommended job {rr[0]}; name a different job.")
    rc, ac = evaluate_job(rr[0], ev, rr[1]), evaluate_job(ar[0], ev, ar[1])
    labels = ic_labels()

    def ref(c: CandidateEval, req: str, how: str) -> JobRef:
        return JobRef(c.job_code, c.job_name, c.ic, labels.get(c.ic, c.ic), req, how)

    cbl = _cbl_facts(well_id)
    rows = [_fit_row(rc, ac, ev, cbl), _history_row(rc, ac, ev)]
    rows.append(Row("field_efficacy", "3 · Field efficacy (p_success with n)", _efficacy_cell(rc, ev),
                    _efficacy_cell(ac, ev), _winner(rc.p_success, ac.p_success, tol=0.005),
                    ["TC-022 p_success_beta", "workover_history"]))
    rows.append(Row("execution", "4 · Execution (rig / rigless, rig-days, cost band, MRO)", _exec_cell(rc), _exec_cell(ac),
                    _winner(rc.rig_days, ac.rig_days, higher_better=False),
                    ["job_catalogue", "TC-011 check_mro", "rig_calendar"]))
    rows.append(Row("value", "5 · Value (deferred bbl per rig-day, risk-adjusted)", _value_cell(rc), _value_cell(ac),
                    _winner(rc.score, ac.score), ["TC-009 estimate_uplift", "TC-022 score"]))
    verdict, deciding, margin, text = _verdict(rc, ac)
    win = {"RECOMMENDED_PREFERRED": "RECOMMENDED", "ALTERNATIVE_PREFERRED": "ALTERNATIVE"}.get(verdict)
    rows.append(Row("verdict", "6 · Verdict",
                    Cell("preferred" if win == "RECOMMENDED" else ("close" if verdict == "CLOSE" else "not preferred"),
                         None, {"verdict": verdict}),
                    Cell("preferred" if win == "ALTERNATIVE" else ("close" if verdict == "CLOSE" else "not preferred"),
                         None, {"verdict": verdict}),
                    win if win else ("TIE" if verdict == "CLOSE" else None), [f"deciding: {deciding}"]))
    if as_of != settings.AS_OF:
        flags.append("AS_OF_OVERRIDE")
    if rc.diagnostic_fit == CONTRADICTED and verdict == "ALTERNATIVE_PREFERRED":
        flags.append("RECOMMENDED_JOB_CONTRADICTED")
    val = Counterfactual(well_id=well_id, as_of=as_of, recommended=ref(rc, rec_req, rr[1]),
                         alternative=ref(ac, alternative_job, ar[1]), rows=rows, verdict=verdict,
                         deciding_dimension=deciding, margin_pct=margin, verdict_text=text,
                         citations=_citations(rows, rc, ac, ev), pressure_survey=ev.pressure, flags=flags)
    status = ToolStatus.OK if FIT in (rc.diagnostic_fit, ac.diagnostic_fit) or verdict != "CLOSE" else ToolStatus.LOW_CONFIDENCE
    if UNCLEAR == rc.diagnostic_fit == ac.diagnostic_fit and verdict == "CLOSE":
        status = ToolStatus.LOW_CONFIDENCE
    return ToolResult(status, val, [], f"{well_id}: {rc.job_code} vs {ac.job_code} -> {verdict} "
                                       f"(deciding: {deciding}" + (f", margin {margin:+.1f}%" if margin is not None else "")
                      + ").", build_provenance(TOOL_ID, params, t0))


register_cache(_cf_cached.cache_clear)
