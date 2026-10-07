"""TC-021 feature pipeline (SDD §8.2): ``build_features(well_id, s)`` — the same function for training and serving.

A snapshot ``s`` is the first day the model is NOT allowed to see. Training uses ``s = start_date − 7 d`` of a
non-censored ``workover_history`` row; serving uses ``s = as_of + 1 d`` (data through ``as_of`` inclusive).

Leakage guard (Gate Q): every dated table is read through :func:`_before`, which keeps rows dated strictly
``< s``. Columns that encode the *decision* or the *future* are never read:

* ``workover_history``: only rows that **ended** before ``s``; never ``failure_code`` / ``job_code`` of the
  labelled job, never ``is_prepend``.
* ``daily_production``: never ``downtime_reason`` values other than the external ones (POWER_OUTAGE, BANDH,
  FLOOD) — a failure-coded downtime reason *is* the diagnosis (K-1); never ``data_source`` / ``is_prepend``.
* ``operations_events``: only set-point changes (CHOKE / SPM / GL_RATE). WAIT_ON_RIG / WAIT_ON_MATERIAL /
  PERMIT / CREW / DEFERRED_MAINTENANCE reveal that a job was already chosen; ``trigger_ref`` names the future job.
* ``well_status_history``: not read (its ``reason_code`` / ``workover_id`` carry the diagnosis).
* ``tubing_string``: not read — it holds only the *current* string, whose ``install_date`` is the latest rig job
  (it would reveal whether a rig job happens after ``s``). Tubing age is derived from prior jobs instead.
* ``perforation_intervals``: only rows with ``perf_date < s`` (re-/add-perforation jobs append rows dated at
  the job end).
* ``well_master``: design columns only (never ``status``, which is today's state).

The production window is anchored at the last producing day before ``s`` (``anchor``) so that a well that is
already down at ``s`` is described by the precursor it showed while it was still running; ``down_at_snapshot``
is a binary symptom (the well has stopped), deliberately without the down-duration (which would encode the
rig-wait and therefore the rig/rigless decision).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

WINDOW_DAYS = 90               # production window (SDD §8.2: "90 d before s")
MAX_ANCHOR_GAP_DAYS = 365      # last producing day must be within a year of s
MIN_PRODUCING_DAYS = 20        # in the window
MIN_HISTORY_DAYS = 90          # daily rows before s (BDD-F03-S05: < 90 days ⇒ INSUFFICIENT_HISTORY)

IC_CODES = [f"IC-{i:02d}" for i in range(1, 16)]
LIFT_TYPES = ["SRP", "GAS_LIFT", "NATURAL"]   # no PCP well exists in the data (constant feature dropped)
FIELDS = ["Geleki", "Lakwa", "Lakhmani"]
ZONES = ["Tipam", "Barail", "Lakadong"]
OUTCOMES = ["SUCCESS", "PARTIAL", "FAILED", "NO_ACTION"]
EXTERNAL_DOWN = ("POWER_OUTAGE", "BANDH", "FLOOD")
SETPOINT_EVENTS = ("CHOKE_CHANGE", "SPM_CHANGE", "GL_RATE_CHANGE")
GRADE_ORD = {"H-40": 0.0, "J-55": 1.0, "K-55": 1.5, "N-80": 2.0, "L-80": 2.0, "C-95": 2.5, "P-110": 3.0}

# Tables (and the date column used for the as-of cut) that build_features may read.
DATED_TABLES = {
    "daily_production": "production_date",
    "workover_history": "end_date",
    "operations_events": "start_date",
    "well_tests": "test_date",
    "pressure_surveys": "survey_date",
    "perforation_intervals": "perf_date",
    "casing_tally": "install_date",
}
STATIC_TABLES = ("well_master",)


@dataclass(frozen=True)
class FeatureRow:
    status: str                  # "OK" | "INSUFFICIENT_HISTORY" | "UNKNOWN_WELL"
    values: dict[str, float]
    snapshot: date
    anchor: date | None
    message: str = ""


# ------------------------------------------------------------------------------------------------
# data source (repository-backed by default; tests inject truncated / perturbed frames)
# ------------------------------------------------------------------------------------------------
def default_source(table: str, well_id: str) -> pd.DataFrame:
    from app.analytics.tools.common import well_rows

    return well_rows(table, well_id)


def _to_date(x) -> date | None:
    if x is None:
        return None
    if isinstance(x, pd.Timestamp):
        return None if pd.isna(x) else x.date()
    if isinstance(x, date):
        return x
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return pd.Timestamp(x).date()


def _before(df: pd.DataFrame, col: str, s: date) -> pd.DataFrame:
    """Rows dated strictly before ``s`` (rows with a null date are dropped)."""
    if df is None or df.empty:
        return df.iloc[0:0] if df is not None else pd.DataFrame()
    d = df[col].map(_to_date)
    keep = d.notna() & (d < s)
    out = df[keep.to_numpy()].copy()
    out[col] = d[keep].to_numpy()
    return out


# ------------------------------------------------------------------------------------------------
# small numeric helpers (NaN when undefined; HistGradientBoosting handles NaN natively)
# ------------------------------------------------------------------------------------------------
NAN = float("nan")


def _mean(a: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    return float(a.mean()) if a.size else NAN


def _ratio_change(late: float, early: float) -> float:
    if math.isnan(late) or math.isnan(early) or abs(early) < 1e-9:
        return NAN
    return late / early - 1.0


def _slope(t: np.ndarray, y: np.ndarray) -> float:
    m = ~np.isnan(y)
    if m.sum() < 5 or np.ptp(t[m]) == 0:
        return NAN
    return float(np.polyfit(t[m], y[m], 1)[0])


def _cv(a: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    if a.size < 3 or abs(a.mean()) < 1e-9:
        return NAN
    return float(a.std() / a.mean())


def _diff_noise(a: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    if a.size < 4 or abs(a.mean()) < 1e-9:
        return NAN
    return float(np.std(np.diff(a)) / a.mean())


def _autocorr(a: np.ndarray, lag: int) -> float:
    a = a[~np.isnan(a)]
    if a.size < lag + 10:
        return NAN
    t = np.arange(a.size, dtype=float)
    r = a - np.polyval(np.polyfit(t, a, 1), t)
    if r.std() < 1e-9:
        return NAN
    return float(np.corrcoef(r[:-lag], r[lag:])[0, 1])


def _days(a: date | None, b: date | None) -> float:
    return float((a - b).days) if (a is not None and b is not None) else NAN


# ------------------------------------------------------------------------------------------------
# feature groups
# ------------------------------------------------------------------------------------------------
def _production_features(daily: pd.DataFrame, s: date, wm: dict) -> tuple[dict[str, float], date | None, str]:
    f: dict[str, float] = {}
    d = daily.sort_values("production_date")
    if len(d) < MIN_HISTORY_DAYS:
        return f, None, f"{len(d)} daily rows before {s} (< {MIN_HISTORY_DAYS})"
    prod = d[d["is_producing"].astype(bool)]
    if prod.empty:
        return f, None, "no producing day before the snapshot"
    anchor = prod["production_date"].iloc[-1]
    if (s - anchor).days > MAX_ANCHOR_GAP_DAYS:
        return f, None, f"last producing day {anchor} is more than {MAX_ANCHOR_GAP_DAYS} days before {s}"
    w0 = anchor - timedelta(days=WINDOW_DAYS - 1)
    win_all = d[d["production_date"] >= w0]
    p = prod[prod["production_date"] >= w0]
    if len(p) < MIN_PRODUCING_DAYS:
        return f, None, f"{len(p)} producing days in the {WINDOW_DAYS}-day window (< {MIN_PRODUCING_DAYS})"

    t = np.array([(x - w0).days for x in p["production_date"]], dtype=float)

    def col(name: str) -> np.ndarray:
        return p[name].astype(float).to_numpy() if name in p.columns else np.full(len(p), NAN)

    liq, oil, wc = col("liquid_rate_blpd"), col("oil_rate_bopd"), col("water_cut_pct")
    water, gor = col("water_rate_bwpd"), col("gor_scf_bbl")
    thp, chp, wht = col("thp_kgcm2"), col("chp_kgcm2"), col("wht_degc")
    spm, rt = col("spm"), col("runtime_fraction")
    glr, glp = col("gl_inj_rate_mscfd"), col("gl_inj_pressure_kgcm2")
    n = len(p)
    ne, nl = min(30, n // 3), min(14, n // 3)
    E, L = slice(0, ne), slice(n - nl, n)

    liq_e, liq_l = _mean(liq[E]), _mean(liq[L])
    f["prod_days_in_window"] = float(n)
    f["producing_frac_window"] = n / max(1, len(win_all))
    f["liq_change_frac"] = _ratio_change(liq_l, liq_e)
    f["oil_change_frac"] = _ratio_change(_mean(oil[L]), _mean(oil[E]))
    mliq = _mean(liq)
    f["liq_slope_pct_per_day"] = _slope(t, liq) / mliq * 100.0 if mliq and not math.isnan(mliq) else NAN
    moil = _mean(oil)
    f["oil_slope_pct_per_day"] = _slope(t, oil) / moil * 100.0 if moil and not math.isnan(moil) else NAN
    f["wc_last_pct"] = _mean(wc[L])
    f["wc_change_pp"] = _mean(wc[L]) - _mean(wc[E])
    f["wc_slope_pp_per_30d"] = _slope(t, wc) * 30.0
    half = n // 2
    if half >= 5:
        r1 = _mean(wc[max(0, half - 7):half]) - _mean(wc[:7])
        r2 = _mean(wc[-7:]) - _mean(wc[max(0, half - 7):half])
        f["wc_rise_first_half_pp"], f["wc_rise_second_half_pp"] = r1, r2
        f["wc_curvature_pp"] = r2 - r1
    f["gor_change_frac"] = _ratio_change(_mean(gor[L]), _mean(gor[E]))
    thp_e, thp_l = _mean(thp[E]), _mean(thp[L])
    f["thp_change_frac"] = _ratio_change(thp_l, thp_e)
    f["thp_change_kgcm2"] = thp_l - thp_e
    f["chp_change_kgcm2"] = _mean(chp[L]) - _mean(chp[E])
    f["thp_slope_per_30d"] = _slope(t, thp) * 30.0
    f["chp_slope_per_30d"] = _slope(t, chp) * 30.0
    f["wht_change_degc"] = _mean(wht[L]) - _mean(wht[E])
    f["wht_slope_per_30d"] = _slope(t, wht) * 30.0
    f["spm_mean"] = _mean(spm)
    f["spm_change"] = _mean(spm[L]) - _mean(spm[E])
    f["runtime_last"] = _mean(rt[L])
    f["runtime_change"] = _mean(rt[L]) - _mean(rt[E])
    cv_e, cv_l = _cv(liq[E]), _cv(liq[L])
    f["liq_cv_late"] = cv_l
    f["liq_cv_ratio"] = cv_l / cv_e if (cv_e and not math.isnan(cv_e) and not math.isnan(cv_l)) else NAN
    dn_e, dn_l = _diff_noise(liq[E]), _diff_noise(liq[L])
    f["liq_diffnoise_ratio"] = dn_l / dn_e if (dn_e and not math.isnan(dn_e) and not math.isnan(dn_l)) else NAN
    step_n = min(10, n // 4)
    rest = liq[:-step_n] if step_n else liq
    med = float(np.nanmedian(rest)) if rest.size else NAN
    f["liq_step_frac"] = _ratio_change(_mean(liq[-step_n:]) if step_n else NAN, med)
    f["liq_autocorr_lag5"] = _autocorr(liq[-min(n, 60):], 5)
    # Short horizon: the last 5 producing days vs the 30 before them (rod part / tubing leak / surface
    # precursors last 3–20 days and would be diluted in the 14-day "late" block).
    if n >= 20:
        S, B = slice(n - 5, n), slice(max(0, n - 35), n - 5)
        f["liq_change_5d"] = _ratio_change(_mean(liq[S]), _mean(liq[B]))
        f["thp_change_5d"] = _mean(thp[S]) - _mean(thp[B])
        f["chp_change_5d"] = _mean(chp[S]) - _mean(chp[B])
        f["runtime_change_5d"] = _mean(rt[S]) - _mean(rt[B])
        f["wc_change_5d"] = _mean(wc[S]) - _mean(wc[B])
        dn_b, dn_s = _diff_noise(liq[B]), _diff_noise(liq[max(0, n - 8):n])
        f["liq_diffnoise_ratio_5d"] = dn_s / dn_b if (dn_b and not math.isnan(dn_b) and not math.isnan(dn_s)) else NAN
    f["gl_rate_change_frac"] = _ratio_change(_mean(glr[L]), _mean(glr[E]))
    f["gl_press_change_kgcm2"] = _mean(glp[L]) - _mean(glp[E])
    # Chan WOR diagnostic (TC-002 idea): log10 WOR slope and its change between halves
    with np.errstate(divide="ignore", invalid="ignore"):
        lwor = np.log10(np.where((oil > 0) & (water > 0), water / oil, np.nan))
    f["log_wor_slope_per_30d"] = _slope(t, lwor) * 30.0
    if half >= 5:
        f["log_wor_slope_change"] = (_slope(t[half:], lwor[half:]) - _slope(t[:half], lwor[:half])) * 30.0
    # Fillage gap (TC-003 idea, SRP only): theoretical displacement vs liquid
    if str(wm.get("lift_type")) == "SRP" and not pd.isna(wm.get("plunger_diameter_in")) and not pd.isna(wm.get("stroke_length_in")):
        ap = math.pi / 4.0 * float(wm["plunger_diameter_in"]) ** 2
        theo = 0.1166 * ap * float(wm["stroke_length_in"]) * spm * rt
        with np.errstate(divide="ignore", invalid="ignore"):
            gap = np.where(theo > 0.1, (theo - liq) / theo, np.nan)
        f["fillage_gap_late"] = _mean(gap[L])
        f["fillage_gap_change"] = _mean(gap[L]) - _mean(gap[E])
    # Decline residual: late oil vs a log-linear fit on the 9 months before the window
    base = prod[(prod["production_date"] < w0) & (prod["production_date"] >= w0 - timedelta(days=270))]
    if len(base) >= 60:
        tb = np.array([(x - w0).days for x in base["production_date"]], dtype=float)
        ob = base["oil_rate_bopd"].astype(float).to_numpy()
        ok = ob > 0
        if ok.sum() >= 60:
            k, c0 = np.polyfit(tb[ok], np.log(ob[ok]), 1)
            k = min(k, 0.0)   # a decline baseline never extrapolates growth
            exp_l = float(np.exp(c0 + k * float(np.mean(t[L]))))
            f["decline_residual_pct"] = (_mean(oil[L]) / exp_l - 1.0) * 100.0 if exp_l > 0 else NAN
            f["oil_vs_prior_9m_frac"] = _ratio_change(_mean(oil[L]), float(np.mean(ob)))
    # Downtime mix (external reasons only) and the binary "stopped" symptom
    reasons = win_all["downtime_reason"].astype(object)
    f["external_down_frac"] = float(reasons.isin(EXTERNAL_DOWN).mean())
    pre = win_all[win_all["production_date"] <= anchor]
    f["nonproducing_frac_before_anchor"] = float((~pre["is_producing"].astype(bool) & ~pre["downtime_reason"].isin(EXTERNAL_DOWN)).mean())
    last_day = d["production_date"].iloc[-1]
    f["down_at_snapshot"] = 1.0 if (anchor < last_day and not bool(d["downtime_reason"].iloc[-1] in EXTERNAL_DOWN)) else 0.0
    return f, anchor, ""


def _construction_features(wm: dict, casing: pd.DataFrame, perfs: pd.DataFrame, s: date) -> dict[str, float]:
    f: dict[str, float] = {}
    lt = str(wm.get("lift_type"))
    for x in LIFT_TYPES:
        f[f"lift_{x}"] = 1.0 if lt == x else 0.0
    for x in FIELDS:
        f[f"field_{x}"] = 1.0 if str(wm.get("field")) == x else 0.0
    for x in ZONES:
        f[f"zone_{x}"] = 1.0 if str(wm.get("current_zone")) == x else 0.0

    def num(k: str) -> float:
        v = wm.get(k)
        try:
            return float(v) if v is not None and not pd.isna(v) else NAN
        except (TypeError, ValueError):
            return NAN

    f["tvd_m"] = num("total_depth_tvd_m")
    f["md_m"] = num("total_depth_md_m")
    f["perf_top_m"] = num("perf_top_m")
    f["perf_interval_m"] = num("perf_bottom_m") - num("perf_top_m")
    f["pump_setting_depth_m"] = num("pump_setting_depth_m")
    f["plunger_diameter_in"] = num("plunger_diameter_in")
    f["stroke_length_in"] = num("stroke_length_in")
    f["casing_size_in"] = num("casing_size_in")
    f["tubing_size_in"] = num("tubing_size_in")
    f["casing_vented"] = 1.0 if bool(wm.get("casing_vented")) else 0.0
    comp = _to_date(wm.get("completion_date"))
    f["well_age_days"] = _days(s, comp)
    pc = casing[casing["string_type"] == "PRODUCTION"] if len(casing) else casing
    if len(pc):
        r = pc.sort_values("install_date").iloc[-1]
        f["prod_casing_od_in"] = float(r["od_in"])
        f["prod_casing_weight_ppf"] = float(r["weight_ppf"])
        f["prod_casing_grade_ord"] = GRADE_ORD.get(str(r["grade"]), NAN)
        f["prod_casing_age_days"] = _days(s, _to_date(r["install_date"]))
        ct = float(r["cement_top_m"]) if not pd.isna(r["cement_top_m"]) else NAN
        f["cement_top_to_perf_m"] = f["perf_top_m"] - ct
    if len(perfs):
        st = perfs["status"].astype(str)
        f["perf_n_intervals"] = float(len(perfs))
        f["perf_n_open"] = float((st == "OPEN").sum())
        f["perf_n_squeezed"] = float((st == "SQUEEZED").sum())
        f["perf_n_isolated"] = float((st == "ISOLATED").sum())
        op = perfs[st == "OPEN"]
        f["perf_open_length_m"] = float((op["bottom_m"] - op["top_m"]).sum())
        f["perf_open_spf_mean"] = float(op["spf"].mean()) if len(op) else NAN
        later = perfs[perfs["perf_date"] > comp] if comp else perfs.iloc[0:0]
        f["perf_n_added_since_completion"] = float(len(later))
        f["days_since_last_perf"] = _days(s, max(perfs["perf_date"]))
    else:
        f["perf_n_intervals"] = 0.0
    return f


def _history_features(wo: pd.DataFrame, s: date, comp: date | None) -> dict[str, float]:
    f: dict[str, float] = {}
    if len(wo):
        wo = wo[~wo["is_censored"].astype(bool) & wo["intervention_class"].notna()]
        wo = wo[wo["start_date"].map(_to_date) < s].sort_values("start_date")
    counts = wo["intervention_class"].value_counts().to_dict() if len(wo) else {}
    for ic in IC_CODES:
        f[f"prior_n_{ic}"] = float(counts.get(ic, 0))
    f["prior_n_jobs"] = float(len(wo))
    s24 = s - timedelta(days=730)
    if len(wo):
        sd = wo["start_date"].map(_to_date)
        recent = wo[(sd >= s24).to_numpy()]
        f["jobs_24m"] = float(len(recent))
        f["failed_jobs_24m"] = float((recent["outcome"] == "FAILED").sum())
        f["rig_jobs_24m"] = float((~recent["is_rigless"].astype(bool)).sum())
        last = wo.iloc[-1]
        lic = str(last["intervention_class"])
        for ic in IC_CODES:
            f[f"last_is_{ic}"] = 1.0 if lic == ic else 0.0
        for o in OUTCOMES:
            f[f"last_outcome_{o}"] = 1.0 if str(last["outcome"]) == o else 0.0
        f["days_since_last_job"] = _days(s, _to_date(last["end_date"]))
        f["last_run_life_days"] = float(last["run_life_days"]) if not pd.isna(last["run_life_days"]) else NAN
        f["last_rig_days"] = float(last["rig_days"]) if not pd.isna(last["rig_days"]) else NAN
        f["last_is_rigless"] = 1.0 if bool(last["is_rigless"]) else 0.0
        rl = wo["run_life_days"].astype(float)
        f["mean_run_life_days"] = float(rl.mean()) if rl.notna().any() else NAN
        rig = wo[~wo["is_rigless"].astype(bool)]
        last_rig_end = _to_date(rig["end_date"].iloc[-1]) if len(rig) else None
        f["tubing_age_proxy_days"] = _days(s, last_rig_end or comp)
    else:
        f["jobs_24m"] = f["failed_jobs_24m"] = f["rig_jobs_24m"] = 0.0
        for ic in IC_CODES:
            f[f"last_is_{ic}"] = 0.0
        for o in OUTCOMES:
            f[f"last_outcome_{o}"] = 0.0
        f["tubing_age_proxy_days"] = _days(s, comp)
    return f


def _event_test_survey_features(ev: pd.DataFrame, tests: pd.DataFrame, surv: pd.DataFrame, s: date,
                                anchor: date) -> dict[str, float]:
    f: dict[str, float] = {}
    w0 = anchor - timedelta(days=WINDOW_DAYS - 1)
    e = ev[ev["start_date"] >= w0] if len(ev) else ev
    for et in SETPOINT_EVENTS:
        f[f"n_{et.lower()}_window"] = float((e["event_type"] == et).sum()) if len(e) else 0.0
    t = tests[tests["test_date"] >= s - timedelta(days=180)].sort_values("test_date") if len(tests) else tests
    if len(t):
        fl = t["fluid_level_m"].astype(float).to_numpy()
        pip = t["pump_intake_p_kgcm2"].astype(float).to_numpy()
        f["test_fluid_level_last_m"] = _mean(fl[-1:])
        f["test_fluid_level_change_m"] = _mean(fl[-2:]) - _mean(fl[:2]) if len(fl) >= 4 else NAN
        f["test_pip_last_kgcm2"] = _mean(pip[-1:])
        f["test_pip_change_kgcm2"] = _mean(pip[-2:]) - _mean(pip[:2]) if len(pip) >= 4 else NAN
        f["days_since_last_test"] = _days(s, t["test_date"].iloc[-1])
    if len(surv):
        sv = surv.sort_values("survey_date")
        last = sv.iloc[-1]
        f["sbhp_last_kgcm2"] = float(last["sbhp_kgcm2"]) if not pd.isna(last["sbhp_kgcm2"]) else NAN
        f["pi_last"] = float(last["pi_bpd_per_kgcm2"]) if not pd.isna(last["pi_bpd_per_kgcm2"]) else NAN
        f["days_since_survey"] = _days(s, last["survey_date"])
        if len(sv) >= 2:
            prev = sv.iloc[-2]
            f["sbhp_change_kgcm2"] = float(last["sbhp_kgcm2"]) - float(prev["sbhp_kgcm2"])
            f["pi_change_frac"] = _ratio_change(float(last["pi_bpd_per_kgcm2"]), float(prev["pi_bpd_per_kgcm2"]))
    return f


# ------------------------------------------------------------------------------------------------
# public API
# ------------------------------------------------------------------------------------------------
def build_features(well_id: str, s: date, source=None) -> FeatureRow:
    """Features for ``well_id`` from data dated strictly before ``s``.

    ``source(table, well_id) -> DataFrame`` defaults to the process repository; the leakage test passes a
    source whose rows dated ``>= s`` are removed or perturbed and asserts identical output.
    """
    src = source or default_source
    wmd = src("well_master", well_id)
    if wmd is None or wmd.empty:
        return FeatureRow("UNKNOWN_WELL", {}, s, None, f"Well {well_id} not found.")
    wm = wmd.iloc[0].to_dict()
    t = {name: _before(src(name, well_id), col, s) for name, col in DATED_TABLES.items()}
    prod, anchor, why = _production_features(t["daily_production"], s, wm)
    if anchor is None:
        return FeatureRow("INSUFFICIENT_HISTORY", {}, s, None, why)
    vals: dict[str, float] = {}
    vals.update(prod)
    vals.update(_construction_features(wm, t["casing_tally"], t["perforation_intervals"], s))
    vals.update(_history_features(t["workover_history"], s, _to_date(wm.get("completion_date"))))
    vals.update(_event_test_survey_features(t["operations_events"], t["well_tests"], t["pressure_surveys"], s, anchor))
    return FeatureRow("OK", vals, s, anchor, "")


def feature_names() -> list[str]:
    """The fixed, ordered feature schema (built from the group definitions, independent of any well)."""
    return list(FEATURE_NAMES)


def to_vector(values: dict[str, float], names: list[str] | None = None) -> np.ndarray:
    names = names or FEATURE_NAMES
    return np.array([float(values.get(k, NAN)) for k in names], dtype=float)


FEATURE_GROUPS: dict[str, list[str]] = {
    "production": [
        "prod_days_in_window", "producing_frac_window", "liq_change_frac", "oil_change_frac",
        "liq_slope_pct_per_day", "oil_slope_pct_per_day", "wc_last_pct", "wc_change_pp", "wc_slope_pp_per_30d",
        "wc_rise_first_half_pp", "wc_rise_second_half_pp", "wc_curvature_pp", "gor_change_frac",
        "thp_change_frac", "thp_change_kgcm2", "chp_change_kgcm2", "thp_slope_per_30d", "chp_slope_per_30d",
        "wht_change_degc", "wht_slope_per_30d", "spm_mean", "spm_change", "runtime_last", "runtime_change",
        "liq_cv_late", "liq_cv_ratio", "liq_diffnoise_ratio", "liq_step_frac", "liq_autocorr_lag5",
        "liq_change_5d", "thp_change_5d", "chp_change_5d", "runtime_change_5d", "wc_change_5d",
        "liq_diffnoise_ratio_5d",
        "gl_rate_change_frac", "gl_press_change_kgcm2", "log_wor_slope_per_30d", "log_wor_slope_change",
        "fillage_gap_late", "fillage_gap_change", "decline_residual_pct", "oil_vs_prior_9m_frac",
        "external_down_frac", "nonproducing_frac_before_anchor", "down_at_snapshot",
        "n_choke_change_window", "n_spm_change_window", "n_gl_rate_change_window",
        "test_fluid_level_last_m", "test_fluid_level_change_m", "test_pip_last_kgcm2", "test_pip_change_kgcm2",
        "days_since_last_test", "sbhp_last_kgcm2", "pi_last", "days_since_survey", "sbhp_change_kgcm2",
        "pi_change_frac",
    ],
    "construction": (
        [f"lift_{x}" for x in LIFT_TYPES] + [f"field_{x}" for x in FIELDS] + [f"zone_{x}" for x in ZONES]
        + ["tvd_m", "md_m", "perf_top_m", "perf_interval_m", "pump_setting_depth_m",
           "plunger_diameter_in", "stroke_length_in", "casing_size_in", "tubing_size_in", "casing_vented",
           "well_age_days", "prod_casing_od_in", "prod_casing_weight_ppf", "prod_casing_grade_ord",
           "prod_casing_age_days", "cement_top_to_perf_m", "perf_n_intervals", "perf_n_open", "perf_n_squeezed",
           "perf_n_isolated", "perf_open_length_m", "perf_open_spf_mean", "perf_n_added_since_completion",
           "days_since_last_perf"]
    ),
    "history": (
        [f"prior_n_{ic}" for ic in IC_CODES] + ["prior_n_jobs", "jobs_24m", "failed_jobs_24m", "rig_jobs_24m"]
        + [f"last_is_{ic}" for ic in IC_CODES] + [f"last_outcome_{o}" for o in OUTCOMES]
        + ["days_since_last_job", "last_run_life_days", "last_rig_days", "last_is_rigless", "mean_run_life_days",
           "tubing_age_proxy_days"]
    ),
}
FEATURE_NAMES: list[str] = [n for g in FEATURE_GROUPS.values() for n in g]

FEATURE_LABELS: dict[str, str] = {
    "liq_change_frac": "liquid rate change over the window",
    "oil_change_frac": "oil rate change over the window",
    "wc_change_pp": "water-cut rise (pp)",
    "wc_curvature_pp": "water-cut rise shape (late minus early)",
    "thp_change_frac": "tubing-head pressure change",
    "chp_change_kgcm2": "casing pressure change",
    "wht_change_degc": "wellhead temperature change",
    "liq_cv_ratio": "liquid-rate scatter (late vs early)",
    "liq_diffnoise_ratio": "day-to-day liquid noise (late vs early)",
    "liq_step_frac": "liquid step in the last days",
    "gl_rate_change_frac": "gas-lift injection rate change",
    "gl_press_change_kgcm2": "gas-lift injection pressure change",
    "log_wor_slope_per_30d": "Chan WOR slope",
    "fillage_gap_late": "pump fillage gap",
    "decline_residual_pct": "oil vs decline baseline (%)",
    "runtime_change": "runtime fraction change",
    "down_at_snapshot": "well has stopped producing",
}
