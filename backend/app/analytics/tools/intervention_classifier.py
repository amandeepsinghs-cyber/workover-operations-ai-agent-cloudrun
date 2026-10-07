"""TC-021 ``classify_intervention`` — calibrated ML intervention classifier (SDD §8, F-03, Stage Q).

Returns the top-k of 15 intervention classes (IC-01…IC-15) with calibrated probabilities, the top signed
feature contributions for the top-1 class, the model version and the holdout quality numbers — read from
``analytics/model/intervention_classifier_metrics.json`` (never from memory; BDD-F03-S03).

* Features: :func:`app.analytics.model.features.build_features` at snapshot ``as_of + 1 d`` (data through
  ``as_of``), the same function the training script uses (train = serve).
* ``INSUFFICIENT_HISTORY`` when the well has < 90 days of production before ``as_of`` or no producing window
  (BDD-F03-S05); no class is returned.
* ``LOW_CONFIDENCE`` when the calibrated top-1 probability is below :data:`LOW_CONFIDENCE_THRESHOLD`
  (classes are still returned, flagged).
* ``UNAVAILABLE`` with flag ``ML_UNAVAILABLE`` when the artefact is missing or Gate Q did not pass; TC-022 then
  runs physics-only (SDD §8.3).
* Contributions are exact path-dependent TreeSHAP values (Lundberg et al. 2018, Alg. 2) of the mean raw
  margin of the served boosters (one per calibration fold) for the top-1 class; they add up to the margin (tested). ``shap`` itself cannot be
  locked for this project (py3.11 + darwin-x86 split needs llvmlite < 0.46), so the algorithm is implemented
  here (~60 lines) instead of changing the project's environments.
* ESP: V§2 WS-3 "ESP Replacement" maps to IC-08; the dataset has no ESP wells (SDD §8.1) — disclosed.
"""

from __future__ import annotations

import json
import pickle
import threading
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

from app import settings
from app.analytics.model.features import FEATURE_LABELS, build_features, to_vector

from .common import (
    ToolResult,
    ToolStatus,
    WellId,
    build_provenance,
    load_yaml,
    register_cache,
    unavailable,
    well_master_row,
)

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
PKL_PATH = MODEL_DIR / "intervention_classifier_v1.pkl"
METRICS_PATH = MODEL_DIR / "intervention_classifier_metrics.json"
LOW_CONFIDENCE_THRESHOLD = 0.40   # fixed a priori (not tuned); holdout coverage at it is in the metrics file
N_CONTRIBUTIONS = 5

IC_NAMES = {
    "IC-01": "SRP_PUMP_CHANGE", "IC-02": "ROD_STRING_REPAIR", "IC-03": "TUBING_LEAK_REPAIR",
    "IC-04": "WAX_REMOVAL", "IC-05": "SCALE_REMOVAL", "IC-06": "SAND_CLEANOUT",
    "IC-07": "GAS_LIFT_VALVE_CHANGE", "IC-08": "LIFT_OPTIMISATION_CONVERSION", "IC-09": "MATRIX_STIMULATION",
    "IC-10": "PERFORATION_WORK", "IC-11": "WATER_SHUT_OFF_SQUEEZE", "IC-12": "ZONAL_ISOLATION",
    "IC-13": "CONING_CONTROL", "IC-14": "SURFACE_INTEGRITY_REPAIR", "IC-15": "NO_JOB_JUSTIFIED",
}
ESP_NOTE = ("ESP replacement (V§2 WS-3) maps to IC-08 Lift optimisation / conversion; there are no ESP wells in "
            "this dataset (lift types SRP, GAS_LIFT, NATURAL, PCP).")


@dataclass(frozen=True)
class ClassProb:
    ic: str
    name: str
    label: str
    display: str
    prob: float


@dataclass(frozen=True)
class Contribution:
    feature: str
    description: str
    value: float | None
    shap: float
    direction: str          # "↑" raises the top-1 class score, "↓" lowers it


@dataclass(frozen=True)
class InterventionPrediction:
    well_id: WellId
    as_of: date
    snapshot_date: date
    window_end: date
    top_k: list[ClassProb]
    contributions: list[Contribution]
    contributions_basis: str
    model_version: str
    holdout_macro_f1: float | None
    holdout_top3_accuracy: float | None
    holdout_ece: float | None
    baseline_macro_f1: float | None
    low_confidence_threshold: float
    low_confidence: bool
    gate_q_passed: bool
    trained_as_of: str | None
    disclosure: str
    esp_note: str = ESP_NOTE
    flags: list[str] = field(default_factory=list)


# ------------------------------------------------------------------------------------------------
# model + metrics (loaded lazily, reloadable by the training script / tests)
# ------------------------------------------------------------------------------------------------
_lock = threading.RLock()
_STATE: dict = {}


def reload_model(pkl_path: Path | None = None, out_metrics_override: Path | None = None) -> None:
    with _lock:
        _STATE.clear()
        if pkl_path is not None:
            _STATE["pkl_path"] = Path(pkl_path)
        if out_metrics_override is not None:
            _STATE["metrics_path"] = Path(out_metrics_override)
    _cached.cache_clear()


def _model() -> dict | None:
    with _lock:
        if "model" not in _STATE:
            p = _STATE.get("pkl_path", PKL_PATH)
            if Path(p).exists():
                with open(p, "rb") as fh:
                    _STATE["model"] = pickle.load(fh)
            else:
                _STATE["model"] = None
        return _STATE["model"]


def load_metrics() -> dict | None:
    """The metrics JSON written by the training script (the only source of quality numbers)."""
    with _lock:
        if "metrics" not in _STATE:
            p = _STATE.get("metrics_path", METRICS_PATH)
            _STATE["metrics"] = json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else None
        return _STATE["metrics"]


def _ic_labels() -> dict[str, str]:
    with _lock:
        if "labels" not in _STATE:
            cfg = load_yaml("ic_map.yaml")["classes"]
            _STATE["labels"] = {k: str(v["label"]) for k, v in cfg.items()}
        return _STATE["labels"]


# ------------------------------------------------------------------------------------------------
# exact TreeSHAP (path-dependent) for sklearn HistGradientBoosting predictor nodes
# ------------------------------------------------------------------------------------------------
def _extend(m: list, pz: float, po: float, pi: int) -> list:
    m = [e[:] for e in m]
    ln = len(m)
    m.append([pi, pz, po, 1.0 if ln == 0 else 0.0])
    for i in range(ln - 1, -1, -1):
        m[i + 1][3] += po * m[i][3] * (i + 1) / (ln + 1)
        m[i][3] = pz * m[i][3] * (ln - i) / (ln + 1)
    return m


def _unwind(m: list, i: int) -> list:
    m = [e[:] for e in m]
    ln = len(m) - 1
    n = m[ln][3]
    zi, oi = m[i][1], m[i][2]
    for j in range(ln - 1, -1, -1):
        if oi != 0:
            t = m[j][3]
            m[j][3] = n * (ln + 1) / ((j + 1) * oi)
            n = t - m[j][3] * zi * (ln - j) / (ln + 1)
        else:
            m[j][3] = (m[j][3] * (ln + 1)) / (zi * (ln - j))
    for j in range(i, ln):
        m[j][0], m[j][1], m[j][2] = m[j + 1][0], m[j + 1][1], m[j + 1][2]
    return m[:ln]


def tree_shap(nodes: np.ndarray, x: np.ndarray, phi: np.ndarray) -> None:
    """Add the exact SHAP values of one tree's output at ``x`` into ``phi`` (len = n_features)."""
    def hot(j: int) -> int:
        nd = nodes[j]
        v = x[int(nd["feature_idx"])]
        if np.isnan(v):
            return int(nd["left"]) if nd["missing_go_to_left"] else int(nd["right"])
        return int(nd["left"]) if v <= nd["num_threshold"] else int(nd["right"])

    def recurse(j: int, m: list, pz: float, po: float, pi: int) -> None:
        m = _extend(m, pz, po, pi)
        nd = nodes[j]
        if nd["is_leaf"]:
            for i in range(1, len(m)):
                w = sum(e[3] for e in _unwind(m, i))
                phi[m[i][0]] += w * (m[i][2] - m[i][1]) * float(nd["value"])
            return
        d = int(nd["feature_idx"])
        h = hot(j)
        c = int(nd["right"]) if h == int(nd["left"]) else int(nd["left"])
        iz = io = 1.0
        k = next((idx for idx in range(1, len(m)) if m[idx][0] == d), None)
        if k is not None:
            iz, io = m[k][1], m[k][2]
            m = _unwind(m, k)
        rj = float(nd["count"])
        recurse(h, m, iz * float(nodes[h]["count"]) / rj, io, d)
        recurse(c, m, iz * float(nodes[c]["count"]) / rj, 0.0, d)

    recurse(0, [], 1.0, 1.0, -1)


def _tree_expectation(nodes: np.ndarray) -> float:
    leaves = nodes[nodes["is_leaf"] == 1]
    return float((leaves["value"] * leaves["count"]).sum() / max(1, leaves["count"].sum()))


def shap_for_class(booster, x: np.ndarray, k: int) -> tuple[np.ndarray, float]:
    """(phi, expected_value) for class ``k`` of a fitted HistGradientBoostingClassifier's raw margin."""
    phi = np.zeros(x.shape[0], dtype=float)
    base = float(np.ravel(booster._baseline_prediction)[k]) if np.size(booster._baseline_prediction) > 1 else float(
        np.ravel(booster._baseline_prediction)[0])
    expv = base
    for preds in booster._predictors:
        nodes = preds[k].nodes
        tree_shap(nodes, x, phi)
        expv += _tree_expectation(nodes)
    return phi, expv


def _boosters(art: dict) -> list:
    return list(art.get("boosters") or [art["booster"]])


def shap_for_ensemble(boosters: list, x: np.ndarray, k: int) -> tuple[np.ndarray, float]:
    """SHAP of the mean raw margin of several boosters (SHAP is linear in the model output)."""
    parts = [shap_for_class(b, x, k) for b in boosters]
    return np.mean([p[0] for p in parts], axis=0), float(np.mean([p[1] for p in parts]))


# ------------------------------------------------------------------------------------------------
# inference
# ------------------------------------------------------------------------------------------------
def predict_top_k(well_id: WellId, as_of: date, top_k: int = 3) -> dict:
    """Raw prediction dict (used by the tool and by the training script's fixture check)."""
    art = _model()
    if art is None:
        return {"status": "UNAVAILABLE", "message": "model artefact missing"}
    s = as_of + timedelta(days=1)
    fr = build_features(well_id, s)
    if fr.status != "OK":
        return {"status": fr.status, "message": fr.message}
    names = art["feature_names"]
    x = to_vector(fr.values, names)
    proba = art["calibrated"].predict_proba(x.reshape(1, -1))[0]
    classes = list(art["classes"])
    order = np.argsort(-proba)[: max(1, int(top_k))]
    labels = _ic_labels()
    top = [ClassProb(classes[i], IC_NAMES.get(classes[i], classes[i]), labels.get(classes[i], classes[i]),
                     f"{classes[i]} {IC_NAMES.get(classes[i], classes[i])}", round(float(proba[i]), 4)) for i in order]
    k1 = int(order[0])
    phi, expv = shap_for_ensemble(_boosters(art), x, k1)
    idx = np.argsort(-np.abs(phi))[:N_CONTRIBUTIONS]
    contribs = [Contribution(names[i], FEATURE_LABELS.get(names[i], names[i].replace("_", " ")),
                             None if np.isnan(x[i]) else round(float(x[i]), 4), round(float(phi[i]), 4),
                             "↑" if phi[i] > 0 else "↓") for i in idx if phi[i] != 0]
    return {"status": "OK", "top_k": [c.__dict__ for c in top], "_top": top, "_contribs": contribs,
            "snapshot": s, "anchor": fr.anchor, "shap_expected_value": expv, "model_version": art["model_version"]}


def classify_intervention(well_id: WellId, as_of: date | None = None, top_k: int = 3) -> ToolResult:
    return _cached(str(well_id).strip().upper(), as_of or settings.AS_OF, int(top_k))


@lru_cache(maxsize=2048)
def _cached(well_id: WellId, as_of: date, top_k: int) -> ToolResult:
    t0 = time.perf_counter()
    params = {"well_id": well_id, "as_of": str(as_of), "top_k": top_k}
    if well_master_row(well_id) is None:
        return unavailable("TC-021", params, t0, ["well_id"], f"Well {well_id} not found.")
    metrics = load_metrics()
    if _model() is None or metrics is None:
        return unavailable("TC-021", params, t0, ["intervention_classifier_v1.pkl"],
                           "ML_UNAVAILABLE: the intervention classifier artefact or its metrics file is missing; "
                           "use the TC-008 physics route.")
    gate = bool(metrics.get("gate_q", {}).get("passed"))
    if not gate:
        return unavailable("TC-021", params, t0, ["gate_q"],
                           "ML_UNAVAILABLE: the classifier did not pass Gate Q; use the TC-008 physics route.")
    r = predict_top_k(well_id, as_of, top_k)
    if r["status"] != "OK":
        status = ToolStatus.INSUFFICIENT_HISTORY if r["status"] == "INSUFFICIENT_HISTORY" else ToolStatus.UNAVAILABLE
        return ToolResult(status, None, [], f"{well_id}: {r['message']}.", build_provenance("TC-021", params, t0))
    ho, base = metrics.get("holdout", {}), metrics.get("baseline", {})
    top = r["_top"]
    low_prob = top[0].prob < LOW_CONFIDENCE_THRESHOLD
    # Q-D1: Geleki's 2023-10.. production is the frozen v0.3.0 core (no precursor signatures); the model was
    # not trained on those rows and scores near chance on them, so every Geleki prediction is LOW_CONFIDENCE.
    core = metrics.get("holdout_geleki_core_only", {})
    out_of_scope = str(well_master_row(well_id).get("field")) == "Geleki"
    low = low_prob or out_of_scope
    disclosure = (f"Model {metrics.get('model_version')} trained on synthetic WellPulse data as of "
                  f"{metrics.get('trained_as_of')}; on the last-12-month holdout it scored macro-F1 "
                  f"{ho.get('macro_f1')}, top-3 accuracy {ho.get('top3_accuracy')} and ECE {ho.get('ece')}, versus "
                  f"{base.get('macro_f1')} macro-F1 for the TC-008 rule baseline.")
    flags = ["SYNTHETIC_TRAINING_DATA"] + (["LOW_CONFIDENCE"] if low else [])
    if out_of_scope:
        flags.append("OUTSIDE_TRAINING_SCOPE_GELEKI_CORE")
        disclosure += (f" Geleki's recent history (frozen v0.3.0 core) carries no precursor signatures and was "
                       f"excluded from training; on those holdout jobs the model scored macro-F1 "
                       f"{core.get('macro_f1')}, so treat this as low confidence.")
    val = InterventionPrediction(
        well_id=well_id, as_of=as_of, snapshot_date=r["snapshot"], window_end=r["anchor"], top_k=top,
        contributions=r["_contribs"],
        contributions_basis=f"TreeSHAP on the boosters' mean raw score for {top[0].ic} (log-odds scale)",
        model_version=str(r["model_version"]), holdout_macro_f1=ho.get("macro_f1"),
        holdout_top3_accuracy=ho.get("top3_accuracy"), holdout_ece=ho.get("ece"),
        baseline_macro_f1=base.get("macro_f1"), low_confidence_threshold=LOW_CONFIDENCE_THRESHOLD,
        low_confidence=low, gate_q_passed=gate, trained_as_of=metrics.get("trained_as_of"),
        disclosure=disclosure, flags=flags)
    status = ToolStatus.LOW_CONFIDENCE if low else ToolStatus.OK
    msg = (f"{well_id}: top class {top[0].display} (p={top[0].prob:.2f})"
           + (f" — below the {LOW_CONFIDENCE_THRESHOLD:.2f} confidence threshold" if low_prob else "")
           + (" — Geleki core history is outside the training scope" if out_of_scope else "") + ".")
    return ToolResult(status, val, [], msg, build_provenance("TC-021", params, t0, model_version=val.model_version))


def model_quality() -> ToolResult:
    """Quality numbers exactly as written in the metrics JSON (BDD-F03-S03)."""
    t0 = time.perf_counter()
    m = load_metrics()
    if m is None:
        return unavailable("TC-021", {}, t0, ["intervention_classifier_metrics.json"], "ML_UNAVAILABLE: no metrics file.")
    ho, base = m.get("holdout", {}), m.get("baseline", {})
    val = {"model_version": m.get("model_version"), "trained_as_of": m.get("trained_as_of"),
           "holdout_macro_f1": ho.get("macro_f1"), "holdout_top3_accuracy": ho.get("top3_accuracy"),
           "holdout_ece": ho.get("ece"), "baseline_macro_f1": base.get("macro_f1"),
           "delta_macro_f1_vs_baseline": m.get("delta_macro_f1_vs_baseline"),
           "holdout_rows": m.get("split", {}).get("holdout_rows"), "gate_q_passed": m.get("gate_q", {}).get("passed"),
           "scope": m.get("scope"), "holdout_full_including_geleki_core": m.get("holdout_full_including_geleki_core"),
           "data_disclosure": m.get("data_disclosure"), "esp_note": ESP_NOTE}
    return ToolResult(ToolStatus.OK, val, [], "Intervention classifier quality (from the metrics file).",
                      build_provenance("TC-021", {}, t0))


register_cache(lambda: reload_model())
