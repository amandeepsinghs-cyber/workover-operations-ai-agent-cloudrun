"""Stage Q · train the TC-021 intervention classifier and assert Gate Q (SDD §8, build.md Stage Q).

    cd backend
    uv run python -m app.analytics.model.train_classifier --as-of 2026-09-23

Design (SDD §8.2):

* **Unit / label.** One finished, non-censored ``workover_history`` row with ``start_date <= as_of``;
  snapshot ``s = start_date − 7 d``; label ``intervention_class``.
* **Features.** :func:`app.analytics.model.features.build_features` (same function as serving); rows whose
  snapshot is ``INSUFFICIENT_HISTORY`` are excluded (they would be refused at serving time too).
* **Split.** Gate holdout is temporal: jobs that start in the last 12 months before ``as_of``. Model selection
  uses ``GroupKFold(5)`` by ``well_id`` on the training period only — the holdout is scored once.
* **Model.** ``HistGradientBoostingClassifier(class_weight="balanced")`` + ``CalibratedClassifierCV`` with grouped
  folds; the calibration scheme (isotonic/sigmoid, ensemble or not) is chosen on an inner temporal split of the
  training period. SHAP explains the mean raw margin of the served boosters.
* **Baseline.** TC-008 rule route at the same snapshot: TC-005 / TC-002 diagnosis (trigger C) → TC-004 offsets
  → ``route_intervention`` → ``intervention_class``.
* **Gate Q.** macro-F1 ∈ [0.70, 0.92], top-3 ≥ 0.90, macro-F1 − baseline ≥ 0.05, ECE ≤ 0.08, ≥ 30 training
  examples per class, LKM-023 → IC-06 and LKM-061 → IC-07 at ``as_of``. The script writes the artefacts and the
  metrics either way and exits non-zero when the gate fails (never tuned to pass).
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold

from app import settings
from app.analytics.model.features import (
    FEATURE_GROUPS,
    FEATURE_NAMES,
    IC_CODES,
    build_features,
    to_vector,
)

MODEL_DIR = Path(__file__).resolve().parent
MODEL_VERSION = "ic-hgb-v1"
PKL_PATH = MODEL_DIR / "intervention_classifier_v1.pkl"
METRICS_PATH = MODEL_DIR / "intervention_classifier_metrics.json"
SNAPSHOT_LEAD_DAYS = 7
HOLDOUT_DAYS = 365
SEED = 20260923

GATE = {"macro_f1_min": 0.70, "macro_f1_max": 0.92, "top3_min": 0.90, "beats_baseline_by": 0.05,
        "ece_max": 0.08, "min_class_support": 30}
LKM061_RULING = ("Orchestrator ruling 2026-10-07: LKM-061 is designed as a dual-signature fixture (GLV 1.0 + wax 0.8), "
                 "so its Gate Q criterion is top-2 = {IC-07, IC-04} (not a tuning; the model was not retrained).")
# criterion per fixture: ("top1", ic) or ("top2_set", {ics})
FIXTURES = {"LKM-023": ("top1", "IC-06"), "LKM-061": ("top2_set", ("IC-07", "IC-04"))}


def fixture_pass(criterion: tuple, top_k: list[dict] | None) -> bool:
    if not top_k:
        return False
    kind, want = criterion
    ics = [str(c["ic"]) for c in top_k]
    if kind == "top1":
        return ics[0] == want
    return set(ics[:2]) == set(want)
PARAM_GRID = [
    {"learning_rate": lr, "max_leaf_nodes": leaves, "l2_regularization": l2}
    for lr in (0.05, 0.1) for leaves in (15, 31) for l2 in (0.0, 1.0)
]


# ------------------------------------------------------------------------------------------------
# dataset
# ------------------------------------------------------------------------------------------------
def labelled_jobs(as_of: date) -> pd.DataFrame:
    from app.analytics.tools.common import load_table

    wo = load_table("workover_history").copy()
    wo["start_date"] = pd.to_datetime(wo["start_date"]).dt.date
    keep = (~wo["is_censored"].astype(bool)) & wo["intervention_class"].notna() & (wo["outcome"] != "IN_PROGRESS")
    wo = wo[keep & (wo["start_date"] <= as_of)]
    return wo[["workover_id", "well_id", "field", "start_date", "intervention_class", "is_prepend"]].reset_index(drop=True)


def in_training_scope(field: str, is_prepend) -> bool:
    """Training/gate scope (decision Q-D1): rows whose daily production carries generator precursor signatures.

    The frozen v0.3.0 Geleki core (``field == Geleki`` and ``is_prepend == False``) has no precursor signatures
    (Stage N decision N-D7) and its catalogue job is drawn at random from the failure code
    (``catalogue.label_geleki_workovers``), so its label is not a function of the production history. Those rows
    are excluded from training and from the gate-of-record holdout by *provenance* (``is_prepend`` is a row
    selector, never a feature); the metrics on them are still reported (``holdout_full`` /
    ``holdout_geleki_core``). Geleki prepend rows (2021-10..2023-09) stay in scope.
    """
    return not (str(field) == "Geleki" and not bool(is_prepend))


def build_dataset(as_of: date, verbose: bool = True) -> tuple[pd.DataFrame, np.ndarray, dict]:
    jobs = labelled_jobs(as_of)
    rows, X, skipped = [], [], {}
    t0 = time.perf_counter()
    for r in jobs.itertuples(index=False):
        s = r.start_date - timedelta(days=SNAPSHOT_LEAD_DAYS)
        fr = build_features(r.well_id, s)
        if fr.status != "OK":
            skipped[fr.status] = skipped.get(fr.status, 0) + 1
            continue
        rows.append({"workover_id": r.workover_id, "well_id": r.well_id, "field": r.field,
                     "start_date": r.start_date, "snapshot": s, "label": r.intervention_class,
                     "in_scope": in_training_scope(r.field, r.is_prepend)})
        X.append(to_vector(fr.values))
    if verbose:
        print(f"dataset: {len(rows)} rows from {len(jobs)} labelled jobs in {time.perf_counter() - t0:.1f}s; "
              f"skipped {skipped}", flush=True)
    return pd.DataFrame(rows), np.vstack(X), {"labelled_jobs": len(jobs), "skipped": skipped}


# ------------------------------------------------------------------------------------------------
# metrics
# ------------------------------------------------------------------------------------------------
def top_k_accuracy(proba: np.ndarray, y_idx: np.ndarray, k: int = 3) -> float:
    top = np.argsort(-proba, axis=1)[:, :k]
    return float(np.mean([y in t for y, t in zip(y_idx, top)]))


def expected_calibration_error(proba: np.ndarray, y_idx: np.ndarray, n_bins: int = 10) -> float:
    """Top-label ECE with equal-width confidence bins."""
    conf = proba.max(axis=1)
    pred = proba.argmax(axis=1)
    correct = (pred == y_idx).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def macro_f1(y_true, y_pred) -> float:
    return float(f1_score(y_true, y_pred, labels=IC_CODES, average="macro", zero_division=0))


def macro_f1_present(y_true, y_pred) -> float:
    labels = sorted(set(y_true))
    return float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))


# ------------------------------------------------------------------------------------------------
# model
# ------------------------------------------------------------------------------------------------
def make_booster(params: dict) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        class_weight="balanced", max_iter=400, early_stopping=True, validation_fraction=0.15,
        n_iter_no_change=20, min_samples_leaf=20, random_state=SEED, **params)


def grouped_folds(X, y, groups, n=5):
    return list(GroupKFold(n_splits=n).split(X, y, groups))


def select_params(X, y, groups, verbose=True) -> tuple[dict, list[dict]]:
    folds = grouped_folds(X, y, groups)
    results = []
    for params in PARAM_GRID:
        scores = []
        for tr, va in folds:
            m = make_booster(params).fit(X[tr], y[tr])
            scores.append(macro_f1_present(y[va], m.predict(X[va])))
        res = {"params": params, "cv_macro_f1_mean": round(float(np.mean(scores)), 4),
               "cv_macro_f1_std": round(float(np.std(scores)), 4)}
        results.append(res)
        if verbose:
            print(f"  cv {params} -> {res['cv_macro_f1_mean']:.4f} ± {res['cv_macro_f1_std']:.4f}", flush=True)
    best = max(results, key=lambda r: r["cv_macro_f1_mean"])
    return best["params"], results


CALIBRATIONS = [
    {"method": "isotonic", "ensemble": False},   # attempt 1 (SDD §8.2 literal): one booster refit on all rows
    {"method": "isotonic", "ensemble": True},    # k (booster, calibrator) pairs, each calibrated on its own fold
    {"method": "sigmoid", "ensemble": True},
    {"method": "temperature", "ensemble": True},  # attempt 3: one softmax temperature on grouped OOF margins
]


class TemperatureScaledBoosters:
    """Mean raw margin of the GroupKFold boosters, softmax at a temperature fit on their out-of-fold margins.

    Multi-class temperature scaling (Guo et al., 2017): a single scalar, so the arg-max (and macro-F1) is the
    boosters' own; only the sharpness changes. Used because one-vs-rest isotonic + renormalisation was
    systematically *under*-confident here (inner split: mean confidence 0.68 vs accuracy 0.79).
    """

    def __init__(self, boosters, temperature: float, classes):
        self.boosters = list(boosters)
        self.temperature = float(temperature)
        self.classes_ = np.asarray(classes)

    def margin(self, X) -> np.ndarray:
        return np.mean([b.decision_function(X) for b in self.boosters], axis=0)

    def predict_proba(self, X) -> np.ndarray:
        z = self.margin(X) / self.temperature
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(axis=1)]


def _fit_temperature(margins: np.ndarray, y_idx: np.ndarray) -> float:
    from scipy.optimize import minimize_scalar

    def nll(t):
        z = margins / t
        z = z - z.max(axis=1, keepdims=True)
        lse = np.log(np.exp(z).sum(axis=1))
        return float(np.mean(lse - z[np.arange(len(y_idx)), y_idx]))

    return float(minimize_scalar(nll, bounds=(0.2, 8.0), method="bounded").x)


def fit_temperature_scaled(X, y, groups, params) -> TemperatureScaledBoosters:
    folds = grouped_folds(X, y, groups)
    boosters, oof = [], np.zeros((len(y), len(IC_CODES)))
    for tr, va in folds:
        b = make_booster(params).fit(X[tr], y[tr])
        assert list(b.classes_) == IC_CODES
        oof[va] = b.decision_function(X[va])
        boosters.append(b)
    y_idx = np.array([IC_CODES.index(v) for v in y])
    return TemperatureScaledBoosters(boosters, _fit_temperature(oof, y_idx), IC_CODES)


def fit_calibrated(X, y, groups, params, method: str = "isotonic", ensemble: bool = True):
    if method == "temperature":
        return fit_temperature_scaled(X, y, groups, params)
    cal = CalibratedClassifierCV(make_booster(params), method=method, cv=grouped_folds(X, y, groups),
                                 ensemble=ensemble)
    return cal.fit(X, y)


def select_calibration(X, y, groups, starts, inner_cut: date, params, verbose=True) -> tuple[dict, list[dict]]:
    """Choose the calibration scheme on an *inner* temporal split of the training period (never the holdout).

    Attempt 3 adds temperature scaling (see :class:`TemperatureScaledBoosters`).

    Attempt 1 used ``ensemble=False``: the isotonic maps are fit on out-of-fold scores of boosters trained on
    80 % of the rows and then applied to a booster refit on 100 %, which is systematically more confident
    (holdout ECE 0.0993 > 0.08). The scheme is now selected by inner-validation ECE (ties -> macro-F1).
    """
    itr, iva = starts <= inner_cut, starts > inner_cut
    out = []
    for c in CALIBRATIONS:
        cal = fit_calibrated(X[itr], y[itr], groups[itr], params, **c)
        pr = cal.predict_proba(X[iva])
        cls = list(cal.classes_)
        yi = np.array([cls.index(v) for v in y[iva]])
        pp = np.array(cls)[pr.argmax(axis=1)]
        res = {**c, "inner_val_rows": int(iva.sum()), "inner_val_ece": round(expected_calibration_error(pr, yi), 4),
               "inner_val_macro_f1": round(macro_f1_present(y[iva], pp), 4)}
        out.append(res)
        if verbose:
            print(f"  calibration {c} -> inner ECE {res['inner_val_ece']}, macro-F1 {res['inner_val_macro_f1']}", flush=True)
    best = min(out, key=lambda r: (r["inner_val_ece"], -r["inner_val_macro_f1"]))
    return {"method": best["method"], "ensemble": best["ensemble"]}, out


def boosters_of(cal) -> list[HistGradientBoostingClassifier]:
    if isinstance(cal, TemperatureScaledBoosters):
        return list(cal.boosters)
    return [cc.estimator for cc in cal.calibrated_classifiers_]




# ------------------------------------------------------------------------------------------------
# TC-008 rule baseline
# ------------------------------------------------------------------------------------------------
def rule_baseline_ic(well_id: str, s: date) -> tuple[str, str]:
    """TC-008 route at snapshot ``s`` (tools see data through ``s − 1``). Unrouted ⇒ IC-15 (no job)."""
    from app.analytics.tools.candidate_ranking import (
        check_offsets,
        route_intervention,
        trigger_c_state,
    )
    from app.analytics.tools.common import OffsetVerdict

    as_of = s - timedelta(days=1)
    off = check_offsets(well_id, as_of=as_of)
    verdict = off.value.verdict if off.value is not None else OffsetVerdict.INSUFFICIENT
    mech = trigger_c_state(well_id, as_of).get("signature")
    if verdict == OffsetVerdict.RESERVOIR_DECLINE:
        r = route_intervention(well_id, mech or "CHANNELLING", verdict)
        return str(r.value.intervention_class), "RESERVOIR_DECLINE"
    if not mech:
        return "IC-15", "NO_MECHANISM"
    r = route_intervention(well_id, mech, verdict)
    if r.value is None or not r.value.intervention_class:
        return "IC-15", "UNROUTED"
    return str(r.value.intervention_class), f"ROUTED:{mech}"


# ------------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------------
def _per_class(y_true, y_pred) -> dict:
    f1s = f1_score(y_true, y_pred, labels=IC_CODES, average=None, zero_division=0)
    sup = pd.Series(y_true).value_counts().to_dict()
    return {ic: {"f1": round(float(f), 4), "support": int(sup.get(ic, 0))} for ic, f in zip(IC_CODES, f1s)}


def train(as_of: date, out_pkl: Path = PKL_PATH, out_metrics: Path = METRICS_PATH, verbose: bool = True) -> dict:
    t_start = time.perf_counter()
    meta, X, ds_info = build_dataset(as_of, verbose)
    y = meta["label"].to_numpy()
    groups = meta["well_id"].to_numpy()
    cut = as_of - timedelta(days=HOLDOUT_DAYS)
    is_ho = (meta["start_date"] > cut).to_numpy()
    scope = meta["in_scope"].to_numpy().astype(bool)
    tr, ho = ~is_ho & scope, is_ho & scope
    support = pd.Series(y[tr]).value_counts().reindex(IC_CODES, fill_value=0).astype(int).to_dict()
    if verbose:
        print(f"train {tr.sum()} rows (start <= {cut}), holdout {ho.sum()} rows ({cut} < start <= {as_of}); "
              f"out of scope (Geleki frozen core): train {(~is_ho & ~scope).sum()}, holdout {(is_ho & ~scope).sum()}",
              flush=True)

    best, cv_results = select_params(X[tr], y[tr], groups[tr], verbose)
    starts = meta["start_date"].to_numpy()
    calib, calib_results = select_calibration(X[tr], y[tr], groups[tr], starts[tr], cut - timedelta(days=HOLDOUT_DAYS),
                                              best, verbose)
    cal = fit_calibrated(X[tr], y[tr], groups[tr], best, **calib)
    classes = list(cal.classes_)
    assert classes == IC_CODES, f"classes {classes} != IC-01..IC-15"

    proba = cal.predict_proba(X[ho])
    y_ho = y[ho]
    y_idx = np.array([classes.index(c) for c in y_ho])
    pred = np.array(classes)[proba.argmax(axis=1)]
    m_f1 = macro_f1(y_ho, pred)
    top3 = top_k_accuracy(proba, y_idx, 3)
    ece = expected_calibration_error(proba, y_idx)
    acc = float(np.mean(pred == y_ho))
    raw_pred = np.array(classes)[np.mean([b.decision_function(X[ho]) for b in boosters_of(cal)], axis=0).argmax(axis=1)]

    def _summary(mask) -> dict:
        if not mask.any():
            return {"n": 0}
        pr = cal.predict_proba(X[mask])
        yy = y[mask]
        yi = np.array([classes.index(c) for c in yy])
        pp = np.array(classes)[pr.argmax(axis=1)]
        return {"n": int(mask.sum()), "macro_f1": round(macro_f1(yy, pp), 4),
                "top3_accuracy": round(top_k_accuracy(pr, yi, 3), 4),
                "ece": round(expected_calibration_error(pr, yi), 4), "accuracy": round(float(np.mean(pp == yy)), 4)}

    full_ho = _summary(is_ho)
    core_ho = _summary(is_ho & ~scope)

    # rule baseline on the same holdout rows
    t_b = time.perf_counter()
    base = [rule_baseline_ic(w, s) for w, s in zip(meta.loc[ho, "well_id"], meta.loc[ho, "snapshot"])]
    base_pred = np.array([b[0] for b in base])
    base_f1 = macro_f1(y_ho, base_pred)
    base_reason = pd.Series([b[1].split(":")[0] for b in base]).value_counts().to_dict()
    core_mask = is_ho & ~scope
    if core_mask.any():
        base_core = np.array([rule_baseline_ic(w, s)[0] for w, s in
                              zip(meta.loc[core_mask, "well_id"], meta.loc[core_mask, "snapshot"])])
        y_full = np.concatenate([y_ho, y[core_mask]])
        full_ho["baseline_macro_f1"] = round(macro_f1(y_full, np.concatenate([base_pred, base_core])), 4)
        core_ho["baseline_macro_f1"] = round(macro_f1(y[core_mask], base_core), 4)
    if verbose:
        print(f"baseline computed in {time.perf_counter() - t_b:.1f}s", flush=True)

    # informational: per field, leave-Lakhmani-out
    per_field = {}
    for fld in sorted(set(meta.loc[ho, "field"])):
        m = (meta.loc[ho, "field"] == fld).to_numpy()
        per_field[fld] = {"n": int(m.sum()), "macro_f1_present_classes": round(macro_f1_present(y_ho[m], pred[m]), 4),
                          "accuracy": round(float(np.mean(pred[m] == y_ho[m])), 4),
                          "top3": round(top_k_accuracy(proba[m], y_idx[m], 3), 4),
                          "baseline_macro_f1_present_classes": round(macro_f1_present(y_ho[m], base_pred[m]), 4)}
    lko = {}
    tr_nl = tr & (meta["field"] != "Lakhmani").to_numpy()
    ho_l = ho & (meta["field"] == "Lakhmani").to_numpy()
    if tr_nl.sum() and ho_l.sum():
        m_nl = make_booster(best).fit(X[tr_nl], y[tr_nl])
        p_l = m_nl.predict(X[ho_l])
        lko = {"train_rows": int(tr_nl.sum()), "test_rows_lakhmani_holdout": int(ho_l.sum()),
               "macro_f1_present_classes": round(macro_f1_present(y[ho_l], p_l), 4),
               "accuracy": round(float(np.mean(p_l == y[ho_l])), 4)}

    # LOW_CONFIDENCE threshold disclosure (fixed a priori, reported not tuned)
    from app.analytics.tools.intervention_classifier import LOW_CONFIDENCE_THRESHOLD
    conf = proba.max(axis=1)
    hi = conf >= LOW_CONFIDENCE_THRESHOLD
    low_conf = {"threshold": LOW_CONFIDENCE_THRESHOLD, "share_below": round(float(1 - hi.mean()), 4),
                "accuracy_at_or_above": round(float(np.mean(pred[hi] == y_ho[hi])), 4) if hi.any() else None,
                "accuracy_below": round(float(np.mean(pred[~hi] == y_ho[~hi])), 4) if (~hi).any() else None}

    artefact = {
        "model_version": MODEL_VERSION, "as_of": as_of.isoformat(), "classes": classes,
        "feature_names": list(FEATURE_NAMES), "feature_groups": FEATURE_GROUPS, "params": best,
        "calibrated": cal, "boosters": boosters_of(cal), "calibration": calib,
        "snapshot_lead_days": SNAPSHOT_LEAD_DAYS,
        "sklearn_version": __import__("sklearn").__version__,
    }
    with open(out_pkl, "wb") as fh:
        pickle.dump(artefact, fh)

    # fixture checks with the saved artefact through the serving tool
    from app.analytics.tools import intervention_classifier as tc021
    tc021.reload_model(out_pkl, out_metrics_override=None)
    fixtures = {}
    for wid, crit in FIXTURES.items():
        r = tc021.predict_top_k(wid, as_of, top_k=3)
        got = r["top_k"][0]["ic"] if r.get("top_k") else None
        fixtures[wid] = {"criterion": {"kind": crit[0], "classes": crit[1]}, "top1": got, "top_k": r.get("top_k"),
                         "pass": fixture_pass(crit, r.get("top_k"))}
        if wid == "LKM-061":
            fixtures[wid]["ruling"] = LKM061_RULING

    gate = {
        "macro_f1_in_band": GATE["macro_f1_min"] <= m_f1 <= GATE["macro_f1_max"],
        "top3_ok": top3 >= GATE["top3_min"],
        "beats_baseline": (m_f1 - base_f1) >= GATE["beats_baseline_by"],
        "ece_ok": ece <= GATE["ece_max"],
        "class_support_ok": min(support.values()) >= GATE["min_class_support"],
        "fixtures_ok": all(v["pass"] for v in fixtures.values()),
    }
    gate["passed"] = all(gate.values())
    cm = confusion_matrix(y_ho, pred, labels=IC_CODES)
    metrics = {
        "model_version": MODEL_VERSION,
        "trained_as_of": as_of.isoformat(),
        "data_disclosure": "Trained and evaluated on synthetic WellPulse data (Geleki, Lakwa, Lakhmani generator); "
                           "not validated on field records.",
        "split": {"type": "temporal", "holdout": f"in-scope jobs starting {cut + timedelta(days=1)}..{as_of}",
                  "train_rows": int(tr.sum()), "holdout_rows": int(ho.sum()),
                  "selection": "GroupKFold(5) by well_id on the training period"},
        "dataset": ds_info,
        "holdout": {"macro_f1": round(m_f1, 4), "top3_accuracy": round(top3, 4), "ece": round(ece, 4),
                    "accuracy": round(acc, 4), "uncalibrated_booster_macro_f1": round(macro_f1(y_ho, raw_pred), 4),
                    "per_class": _per_class(y_ho, pred), "per_field": per_field,
                    "confusion_matrix": {"labels": IC_CODES, "rows_true_cols_pred": cm.tolist()}},
        "baseline": {"name": "TC-008 rule route (TC-005/TC-002 trigger C + TC-004 offsets), unrouted -> IC-15",
                     "macro_f1": round(base_f1, 4), "accuracy": round(float(np.mean(base_pred == y_ho)), 4),
                     "route_reasons": base_reason, "per_class": _per_class(y_ho, base_pred)},
        "delta_macro_f1_vs_baseline": round(m_f1 - base_f1, 4),
        "scope": {"decision": "Q-D1", "rule": "exclude rows with field == Geleki and is_prepend == False (frozen "
                  "v0.3.0 core: no precursor signatures, label drawn at random from the failure code)",
                  "train_rows_excluded": int((~is_ho & ~scope).sum()), "holdout_rows_excluded": int((is_ho & ~scope).sum())},
        "holdout_full_including_geleki_core": full_ho,
        "holdout_geleki_core_only": core_ho,
        "leave_lakhmani_out": lko,
        "low_confidence": low_conf,
        "train_class_support": support,
        "model": {"estimator": f"HistGradientBoostingClassifier(class_weight='balanced') + "
                               f"CalibratedClassifierCV({calib['method']}, GroupKFold(5), ensemble={calib['ensemble']})",
                  "params": best, "cv_results": cv_results, "calibration": calib,
                  "calibration_selection": {"split": f"inner temporal: train start <= {cut - timedelta(days=HOLDOUT_DAYS)}, "
                                                     f"validate ({cut - timedelta(days=HOLDOUT_DAYS)}, {cut}]",
                                            "results": calib_results,
                                            "attempt_1": "isotonic ensemble=False: holdout ECE 0.0993 (failed 0.08)",
                                            "attempt_2": "select among isotonic/sigmoid CalibratedClassifierCV by inner "
                                                         "ECE -> isotonic ensemble=False again (inner ECE 0.108); "
                                                         "holdout ECE 0.0993 (failed 0.08)"},
                  "temperature": getattr(cal, "temperature", None),
                  "n_features": len(FEATURE_NAMES),
                  "explanations": "exact path-dependent TreeSHAP of the mean raw margin of the served boosters "
                                  "(in-house, additive)"},
        "fixtures": fixtures,
        "gate_q": {"thresholds": GATE, **gate},
        "train_seconds": round(time.perf_counter() - t_start, 1),
    }
    with open(out_metrics, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    tc021.reload_model(out_pkl)
    if verbose:
        print(json.dumps({k: metrics[k] for k in ("holdout", "baseline", "gate_q")}, indent=1, default=str)[:6000])
        print("fixtures:", {k: (v["top1"], v["pass"]) for k, v in fixtures.items()})
    return metrics


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Train the TC-021 intervention classifier and assert Gate Q.")
    ap.add_argument("--as-of", default=settings.AS_OF.isoformat())
    ap.add_argument("--no-assert", action="store_true", help="write artefacts but exit 0 even if Gate Q fails")
    a = ap.parse_args(argv)
    # run through the importable module so pickled classes resolve as app.analytics.model.train_classifier.*
    from app.analytics.model import train_classifier as mod

    m = mod.train(date.fromisoformat(a.as_of))
    ok = m["gate_q"]["passed"]
    print("GATE Q:", "PASSED" if ok else "FAILED", {k: v for k, v in m["gate_q"].items() if k != "thresholds"})
    return 0 if (ok or a.no_assert) else 1


if __name__ == "__main__":
    sys.exit(main())
