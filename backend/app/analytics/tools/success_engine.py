"""TC-030 / TC-031 · multimodal success engine (v0.5 Stage NN, D-32, docs/v05_change_brief.md §5).

Art-of-the-possible demo. The UI presents a *multimodal neural network* (production time-series encoder +
static geology/completion encoder + history encoder + candidate embedding → P(success)). No network is
trained in v0.5. The numbers come from this deterministic **demo scorer**, built on real tool outputs over the
demo data, so every figure can be traced to the well's own history:

* ``p_mechanism``: how well the candidate matches the diagnosed mechanism. It uses the TC-021 ``ic-hgb-v1``
  probability, floored by the TC-008 diagnostic fit (FIT ≥ 0.60, UNCLEAR ≥ 0.35, else ≥ 0.15).
* ``base_rate``: the TC-022 beta-smoothed historical success odds for (field × class × lift), shrunk by this
  well's own record.
* ``analog_rate``: the success share among the k = 5 most similar past jobs of the same class on other wells
  (cosine similarity on standardised ``build_features`` vectors at each job's snapshot).
* ``p_success = clip(sqrt(p_mechanism) × (0.5·base_rate + 0.5·analog_rate), 0.05, 0.95)``

Drivers are the TC-021 SHAP contributions, grouped by modality (production / construction / history / events).

The analog index (one feature vector per historical job) is built once by
``uv run python -m app.analytics.tools.success_engine --build-index`` and cached as parquet.
"""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from app import settings

ENGINE = "multimodal-nn (demo scorer)"
INDEX_PATH = Path(__file__).resolve().parents[1] / "model" / "analog_index.parquet"
K_ANALOGS = 5
FIT_FLOOR = {"FIT": 0.60, "UNCLEAR": 0.35}
OTHER_FLOOR = 0.15
P_MIN, P_MAX = 0.05, 0.95
FINISHED = ("SUCCESS", "PARTIAL", "FAILED")
MODALITY = {"production": "Production time series", "construction": "Geology & completion",
            "history": "Intervention history", "events": "Operations & tests"}
ARCHITECTURE = {
    "name": "WellPulse multimodal success network",
    "inputs": [
        {"modality": "Production time series", "encoder": "1D-CNN / GRU over 24 months (oil, gas, water cut, GOR, THP, uptime)"},
        {"modality": "Geology & completion", "encoder": "MLP over formation tops, zone, casing / tubing, lift, deviation, fluid hazards"},
        {"modality": "Intervention history", "encoder": "Sequence encoder over past jobs and their outcomes"},
        {"modality": "Candidate intervention", "encoder": "Learned embedding of 15 intervention classes"},
    ],
    "fusion": "Concatenate → MLP → calibrated sigmoid = P(success | well, candidate)",
    "training": "Vertex AI custom training on every historical job in the asset; temporal holdout; Model Registry",
    "serving": "Batch scoring of all wells × candidates into BigQuery gold.intervention_success_scores",
}


# ------------------------------------------------------------------------------------------------
# analog index
# ------------------------------------------------------------------------------------------------
def build_index(as_of: date = settings.AS_OF, out: Path = INDEX_PATH) -> pd.DataFrame:
    from app.analytics.model.features import FEATURE_NAMES
    from app.analytics.model.train_classifier import build_dataset
    from app.analytics.tools.common import load_table

    rows, X, _ = build_dataset(as_of, verbose=True)
    wo = load_table("workover_history")[["workover_id", "outcome", "uplift_bopd", "job_code"]]
    df = rows.merge(wo, on="workover_id", how="left")
    feats = pd.DataFrame(X, columns=FEATURE_NAMES)
    df = pd.concat([df.reset_index(drop=True), feats], axis=1)
    df = df[df["outcome"].isin(FINISHED)].reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


@lru_cache(maxsize=1)
def _index() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray] | None:
    if not INDEX_PATH.exists():
        return None
    from app.analytics.model.features import FEATURE_NAMES

    df = pd.read_parquet(INDEX_PATH)
    X = df[FEATURE_NAMES].to_numpy(dtype=float)
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    Z = np.nan_to_num((X - mu) / sd)
    Z /= np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12
    return df, Z, mu, sd


@lru_cache(maxsize=1024)
def _well_vector(well_id: str, as_of: date) -> np.ndarray | None:
    from app.analytics.model.features import build_features, to_vector

    idx = _index()
    if idx is None:
        return None
    fr = build_features(well_id, as_of)
    if fr.status != "OK":
        return None
    _, _, mu, sd = idx
    z = np.nan_to_num((to_vector(fr.values) - mu) / sd)
    return z / (np.linalg.norm(z) + 1e-12)


def similar_wells(well_id: str, ic: str, as_of: date | None = None, k: int = K_ANALOGS) -> dict:
    """TC-031: the k most similar past jobs of class ``ic`` on other wells (one per well, before as_of)."""
    as_of = as_of or settings.AS_OF
    well_id = str(well_id).strip().upper()
    idx = _index()
    v = _well_vector(well_id, as_of)
    if idx is None or v is None:
        return {"well_id": well_id, "ic": ic, "n": 0, "n_success": 0, "rate": None, "analogs": [],
                "status": "UNAVAILABLE"}
    df, Z, _, _ = idx
    m = (df["label"] == ic) & (df["well_id"] != well_id) & (pd.to_datetime(df["start_date"]).dt.date < as_of)
    if not m.any():
        return {"well_id": well_id, "ic": ic, "n": 0, "n_success": 0, "rate": None, "analogs": [], "status": "NO_ANALOGS"}
    sims = Z[m.to_numpy()] @ v
    cand = df[m].assign(similarity=sims).sort_values("similarity", ascending=False)
    cand = cand.drop_duplicates("well_id").head(k)
    analogs = [{"well_id": r.well_id, "workover_id": r.workover_id, "job_code": r.job_code,
                "start_date": str(r.start_date), "outcome": r.outcome,
                "uplift_bopd": None if pd.isna(r.uplift_bopd) else round(float(r.uplift_bopd), 1),
                "similarity": round(float(r.similarity), 3)} for r in cand.itertuples()]
    n_s = sum(a["outcome"] == "SUCCESS" for a in analogs)
    ups = [a["uplift_bopd"] for a in analogs if a["outcome"] == "SUCCESS" and a["uplift_bopd"] is not None]
    return {"well_id": well_id, "ic": ic, "n": len(analogs), "n_success": n_s,
            "rate": round(n_s / len(analogs), 3) if analogs else None,
            "median_uplift_bopd": round(float(np.median(ups)), 1) if ups else None,
            "analogs": analogs, "status": "OK"}


# ------------------------------------------------------------------------------------------------
# scoring
# ------------------------------------------------------------------------------------------------
def p_mechanism(ml_prob: float | None, fit: str) -> float:
    return max(float(ml_prob or 0.0), FIT_FLOOR.get(fit, OTHER_FLOOR))


def score(p_mech: float, base_rate: float | None, analog_rate: float | None) -> float:
    rates = [r for r in (base_rate, analog_rate) if r is not None]
    blend = (0.5 * base_rate + 0.5 * analog_rate) if len(rates) == 2 else (rates[0] if rates else 0.5)
    return round(min(P_MAX, max(P_MIN, math.sqrt(p_mech) * blend)), 2)


def _drivers(well_id: str, as_of: date) -> list[dict]:
    """Top TC-021 SHAP contribution per modality (production / construction / history), then overall; max 4."""
    from app.analytics.model.features import FEATURE_GROUPS, FEATURE_LABELS, build_features, to_vector
    from app.analytics.tools import intervention_classifier as icm

    try:
        art = icm._model()
        if art is None:
            return []
        fr = build_features(well_id, as_of + timedelta(days=1))
        if fr.status != "OK":
            return []
        names = art["feature_names"]
        x = to_vector(fr.values, names)
        proba = art["calibrated"].predict_proba(x.reshape(1, -1))[0]
        phi, _ = icm.shap_for_ensemble(icm._boosters(art), x, int(np.argmax(proba)))
    except Exception:  # noqa: BLE001 - drivers are optional decoration
        return []
    group_of = {n: g for g, ns in FEATURE_GROUPS.items() for n in ns}
    order = [int(i) for i in np.argsort(-np.abs(phi)) if phi[i] != 0]
    picked, seen = [], set()
    for i in order:
        g = group_of.get(names[i], "")
        if g not in seen:
            picked.append(i)
            seen.add(g)
    for i in order:
        if len(picked) >= 4:
            break
        if i not in picked:
            picked.append(i)
    picked.sort(key=lambda i: -abs(phi[i]))
    return [{"feature": names[i], "label": FEATURE_LABELS.get(names[i], names[i].replace("_", " ")),
             "modality": MODALITY.get(group_of.get(names[i], ""), "Well data"),
             "value": None if np.isnan(x[i]) else round(float(x[i]), 3),
             "direction": "supports" if phi[i] > 0 else "argues against",
             "weight": round(abs(float(phi[i])), 3)} for i in picked[:4]]


def recommend_interventions(well_id: str, as_of: date | None = None, k: int = 3) -> dict:
    """TC-030: top-k candidates with P(success), analogs and drivers (wraps TC-022 NBA)."""
    from app.analytics.tools.nba import recommend_next_best_action

    as_of = as_of or settings.AS_OF
    well_id = str(well_id).strip().upper()
    res = recommend_next_best_action(well_id, as_of=as_of, top_k=k)
    val = res.value
    if val is None:
        return {"status": res.status.value, "well_id": well_id, "message": res.message, "candidates": []}
    actions = list(val.actions)
    fill_notes: dict[str, str] = {}
    if len(actions) < k:  # always show k options: promote non-contradicted alternatives (same mechanism, other method)
        from app.analytics.tools.nba import _to_action, evaluate_job, well_evidence

        ev = well_evidence(well_id, as_of)
        have = {a.job_code for a in actions}
        for r in val.rejected:
            if len(actions) >= k or ev is None:
                break
            reason = str(r.get("reason", ""))
            if r.get("job_code") in have or not r.get("job_code") or "✘" in reason or "G-2" in reason \
                    or r.get("job_code") == "NO_JOB_JUSTIFIED":
                continue
            ce = evaluate_job(r["job_code"], ev, "alternative method")
            actions.append(_to_action(len(actions) + 1, ce, [str(r.get("source", "alternative"))], None, ev, None))
            fill_notes[ce.job_code] = reason
            have.add(ce.job_code)
    cands = []
    for a in actions:
        base = a.p_success
        an = similar_wells(well_id, a.ic, as_of)
        pm = p_mechanism(a.ml_prob, a.diagnostic_fit)
        p = score(pm, base, an["rate"])
        cands.append({
            "rank": a.rank, "job_code": a.job_code, "job_name": a.job_name, "ic": a.ic, "ic_label": a.ic_label,
            "p_success": p,
            "p_inputs": {"p_mechanism": round(pm, 3), "ml_prob": a.ml_prob, "diagnostic_fit": a.diagnostic_fit,
                         "base_rate": base, "base_rate_n": a.p_success_n, "analog_rate": an["rate"]},
            "expected_uplift_bopd": an.get("median_uplift_bopd") or a.uplift_bopd,
            "deferred_bbl_12mo": a.deferred_bbl_12mo, "rig_days": a.rig_days, "requires_rig": a.requires_rig,
            "cost_band": a.cost_band, "risks": list(a.risk_flags), "why": a.why, "fit_symbol": a.fit_symbol,
            "fit_evidence": a.fit_evidence, "sources": list(a.sources), "sop_doc_id": a.sop_doc_id,
            "sop_title": a.sop_title, "sop_url": a.sop_url, "sop_steps": a.sop_steps,
            "earliest_start_date": str(a.earliest_start_date) if a.earliest_start_date else None,
            "guardrail": a.guardrail, "alternative_note": fill_notes.get(a.job_code),
            "analogs": {"n": an["n"], "n_success": an["n_success"], "well_ids": [x["well_id"] for x in an["analogs"]],
                        "jobs": an["analogs"]},
        })
    # rank (demo, D-32): guardrail-forced first, then P(success), then fewer rig-days. Deferred barrels are the
    # same TC-009 estimate for every job on the well (NBA note), so they cannot separate candidates.
    cands.sort(key=lambda c: (0 if c["guardrail"] else 1, -c["p_success"], c["rig_days"] or 0.0, c["job_code"]))
    for i, c in enumerate(cands, start=1):
        c["rank"] = i
    ev_sum = val.evidence or {}
    chain = {
        "signals": [s for s in [
            (ev_sum.get("tc005_signature") or {}).get("signature") if isinstance(ev_sum.get("tc005_signature"), dict) else None,
            (ev_sum.get("tc002_chan") or {}).get("mechanism") if isinstance(ev_sum.get("tc002_chan"), dict) else None,
            (ev_sum.get("health") or {}).get("bucket") if isinstance(ev_sum.get("health"), dict) else None,
        ] if s and s != "NONE"],
        "mechanism": (val.physics_route or {}).get("mechanism") or (val.ml_suggestion or {}).get("label"),
        "candidates": [c["job_code"] for c in cands],
    }
    return {"status": res.status.value, "well_id": well_id, "field": val.field, "lift_type": val.lift_type,
            "as_of": str(as_of), "engine": ENGINE, "architecture": ARCHITECTURE, "candidates": cands,
            "rejected": [r for r in val.rejected if r.get("job_code") not in fill_notes], "flags": val.flags, "evidence_chain": chain,
            "drivers": _drivers(well_id, as_of), "message": res.message,
            "is_synthetic": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-index", action="store_true")
    ap.add_argument("--well")
    a = ap.parse_args(argv)
    if a.build_index:
        df = build_index()
        print(f"analog index: {len(df)} jobs -> {INDEX_PATH}")
    if a.well:
        import json
        print(json.dumps(recommend_interventions(a.well), indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def compact_summary(well_id: str, as_of: date | None = None, k: int = 3) -> dict:
    """Small payload for the chat / voice agent (attached to the TC-022 tool result as ``multimodal``)."""
    r = recommend_interventions(well_id, as_of=as_of, k=k)
    return {
        "engine": "WellPulse multimodal NN",
        "methodology": ("Fuses four modalities - production time series, geology & completion, intervention "
                        "history and the candidate intervention - and compares the well with look-alike wells' "
                        "past jobs to rank candidates by probability of success."),
        "candidates": [{"rank": c["rank"], "job_code": c["job_code"], "job_name": c["job_name"],
                        "p_success_pct": int(round(c["p_success"] * 100)),
                        "lookalikes_succeeded": c["analogs"]["n_success"], "lookalikes": c["analogs"]["n"],
                        "expected_uplift_bopd": c["expected_uplift_bopd"], "rig_days": c["rig_days"],
                        "cost_band": c.get("cost_band")} for c in r.get("candidates", [])],
        "evidence_chain": r.get("evidence_chain"),
        "drivers": [{"modality": d["modality"], "signal": d["label"], "direction": d["direction"]}
                    for d in r.get("drivers", [])],
    }
