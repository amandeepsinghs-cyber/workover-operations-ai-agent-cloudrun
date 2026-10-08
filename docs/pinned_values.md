# WellPulse v0.5 — Pinned Values (Gates N, P, Q, R, NN, FR, DF)

> **Answer first:** the Stage N synthetic data hits every Gate N target, Stage Q/R classifier and NBA are pinned, and Stage v0.5 pins deterministic parameters for DG synthetic tables, multimodal success model (NN), field report (FR), and demo flow eval (DF). The values below are the
> exact numbers BDD scenarios assert (they replace placeholders).
> Data window 2021-10-01..2026-09-30, AS_OF 2026-09-23; seeds: Geleki 42, Lakwa 4301, Lakhmani 4402 (Geleki prepend 4242); DG seed 20261008.

## 1. Wells, clusters and rows

| Field | Wells | Clusters (GGS) | daily_production rows | Window | workover_history rows |
|---|---|---|---|---|---|
| Geleki | 142 | 3 | 259,292 | 2021-10-01..2026-09-30 | 1,328 |
| Lakwa | 160 | 3 | 292,160 | 2021-10-01..2026-09-30 | 1,722 |
| Lakhmani | 110 | 2 | 200,860 | 2021-10-01..2026-09-30 | 952 |

- History points per well for the 5-year range (2021-10-01..AS_OF 2026-09-23): **1819** (`/api/wells/{id}/history?range=5y`).

## 2. Field production gap vs target (F-09)

QTD window 2026-07-01..2026-09-23; trailing-12-month window 2025-09-24..2026-09-23. Target = monthly healthy-state potential × 2021-10..2023-09 plan efficiency (decision N-D5).

| Field | QTD gap (pinned) | Trailing-12m gap | Design target | Gate |
|---|---|---|---|---|
| Geleki | -1.5% | -4.9% | +0% ± 3 pp | PASS |
| Lakwa | -17.6% | -14.7% | -18% ± 3 pp | PASS |
| Lakhmani | -8.5% | -3.3% | -6% ± 3 pp | PASS |

## 3. Fixture wells

- **LKW-047** (Lakwa, GGS-I): pump job `WO-LKW-047-007` starts 2026-07-07; in the 180-day window before it: WAIT_ON_RIG **41** days, WAIT_ON_MATERIAL **12** days (status history); operations_events agree: {'WAIT_ON_MATERIAL': 12, 'WAIT_ON_RIG': 41}.
- **LKM-090** (Lakhmani): decline over its signature window **-18.0%**; offsets: LKM-107 -18.1%, LKM-001 -18.6%, LKM-091 -17.6%, LKM-074 -18.3%, LKM-101 -18.7%, LKM-005 -17.6%; max |residual| **0.6 pp** (contract: ≤ 5 pp).

## 4. Geleki prepend join (2023-10-01)

- 7-day field-total oil before vs after the join: **+1.3%**; per producing well: **+0.3%** (contract: within ±3%).
- Geleki v0.3.0 core rows/columns are hash-identical to `tests/baseline/landing_v030` (`validate --compare-baseline`).

## 5. Intervention classes (non-censored workovers, all fields)

| IC | Rows |
|---|---|
| IC-01 | 329 |
| IC-02 | 348 |
| IC-03 | 411 |
| IC-04 | 451 |
| IC-05 | 116 |
| IC-06 | 291 |
| IC-07 | 289 |
| IC-08 | 330 |
| IC-09 | 141 |
| IC-10 | 140 |
| IC-11 | 191 |
| IC-12 | 125 |
| IC-13 | 87 |
| IC-14 | 324 |
| IC-15 | 140 |

Minimum **87** (contract: ≥ 30 per class).

## 6. Survival model (Gate E regression, `train --exclude-prepend`)

- model_version `coxph-v1.0-geleki`, training rows `v030_core_only`: holdout C-index **0.7128**, Trigger B **0.7061**, episodes 660 (right-censored 12.3%).

## 7. Asset tables

| Table | Rows |
|---|---|
| job_catalogue | 29 |
| mro_inventory | 15 |
| rig_calendar | 915 |
| field_master | 3 |
| cluster_master | 8 |
| facility_master | 11 |
| field_targets | 180 |

## 8. Placeholders that are NOT pinned at Gate N

- BDD-F01-S03 / S06 loss-attribution shares (SUBSURFACE ≥ 80%, controllable ≤ 15% / ≥ 40%) are outputs of
  the TC-019 attribution tool and are pinned at Gate P, from this same data.

### 8.1 Pinned at Gate P (TC-019 / TC-020, `AS_OF` 2026-09-23, `config_version` 2.0.0-wellpulse)

| Value | Scenario | Contract | Measured |
|---|---|---|---|
| LKM-090 SUBSURFACE share, 180 d | BDD-F01-S03 | ≥ 80% | **100.0%** (RESERVOIR_DECLINE 321.9 bbl via TC-004 + NATURAL_DECLINE 275.4 bbl (TC-001 since-last-workover fit) + WATER_ENCROACHMENT 17.6 bbl; total 614.9 bbl) |
| LKM-090 controllable share, 180 d | BDD-F01-S03 | ≤ 15% | **0.0%**; flag `NO_OPERATIONAL_ACTION_WOULD_HAVE_PREVENTED` |
| Lakwa field controllable share, 90 d | BDD-F01-S06 | ≥ 40% | **68.8%** (total 219,482.3 bbl; unexplained 0.1%) |
| LKW-047, 180 d | BDD-F01-S01 | largest HUMAN_PROCESS | **HUMAN_PROCESS 78.5%** — WAIT_ON_RIG 2,595.4 bbl / 41 d, WAIT_ON_MATERIAL 759.6 bbl / 12 d; EQUIPMENT 21.2% (PUMP_WEAR 774.1 bbl); total 4,275.8 bbl |
| LKW-088, 180 d | BDD-F01-S04 | GRID_POWER_OUTAGE = EXTERNAL | **EXTERNAL 75.4%** (1,001.9 bbl, 12 d), controllable 0.0%; status LOW_CONFIDENCE (unexplained 22.8%: TC-001 fit LOW → natural decline not separated) |
| Waterfall reconciliation | Gate P1 | ≤ 0.5% every well | **0.0%** (exact by construction; 1-dp display residual placed on largest bar) for all wells with a baseline (Geleki 131/142, Lakwa 147/160, Lakhmani 105/110; the rest have no pre-window production → INSUFFICIENT_HISTORY) |
| TC-020 Geleki | BDD-F02-S01 | 142 | OK 88 · AT_RISK 21 · UNDERPERFORMING 5 · NOT_PRODUCING 28 |
| TC-020 Lakwa | BDD-F02-S01 | 160 | OK 90 · AT_RISK 27 · UNDERPERFORMING 0 · NOT_PRODUCING 43 |
| TC-020 Lakhmani | BDD-F02-S01 | 110 | OK 67 · AT_RISK 34 · UNDERPERFORMING 1 (LKM-061) · NOT_PRODUCING 8 |

TC-001 fallback (orchestrator decision): a LOW 36-month fit is refitted on the current cycle (since the last
workover, ≥ 90 post-transient points) and used only if not LOW. Fits used: Geleki 136 FULL_WINDOW (unchanged);
Lakwa 24 full + 5 since-workover, 123 still LOW (89 have < 90 points in the current cycle, 34 have flat/noisy
cycles, median r² 0.15); Lakhmani 30 full + 8 since-workover, 67 LOW. So Lakwa still has 0 UNDERPERFORMING —
the data does not support more (not forced).

### 8.2 Geleki trigger baseline v0.4 vs v0.3.0 fixtures

Accepted by orchestrator: data-driven replaces hard-coded fixtures (integrity first). TC-007 at AS_OF 2026-09-23;
44 of 136 active Geleki wells fire (v0.3.0 fixtures: 7).

| Well | v0.3.0 fixture A / B / C / D | v0.4 data-driven A (residual) / B / C / D | Why different |
|---|---|---|---|
| GK-129 | FLAG / F / CHANNELLING / T | FLAG (−30.6%) / F / CHANNELLING / F | D = field P90 hazard, not a fixture |
| GK-141 | WATCH / F / CHANNELLING_OR_INJECTOR / T | WATCH (−20.9%) / F / — / F | no injector table → injector mechanism untestable; still RESERVOIR_DECLINE → NO_JOB_JUSTIFIED |
| GK-103 | WATCH / F / CONING / T | WATCH (−19.5%) / **T** / CONING / F | own run lives: 298 d since job > p50 296 d |
| GK-112 | FLAG / F / SCALE / T | FLAG (−37.4%) / **T** / SCALE / F | 291 d > p50 287 d |
| GK-087 | — / T / ROD_PART / T | — (0.0%) / F / — / F | run lives 179/302/354 d → p50 354 ≫ 206 d; no ROD_PART signal in data |
| GK-055 | WATCH / F / PUMP_WEAR / T | **FLAG** (−40.0%) / F / PUMP_WEAR / F | residual tier from data |
| GK-147 | FLAG / F / WAX / T | **WATCH** (best-of-7 −21.7%) / **T** / WAX / F | residual tier from data; 279 d > p50 254 d |

## 9. Decisions behind these values

- **N-D5** Target = healthy-state potential × baseline plan efficiency; the gap is emergent, measured on QTD.
- **N-D10** Lakwa: rig-wait drift 14→48 d and preventive-maintenance interval drift 230→120 d over the
  window (third calibration attempt; earlier attempts gave −8.8% .. −15.4%). The QTD gap moves ±3 pp
  between seeds, so the pinned value is tied to the committed seeds.
- **N-D12** The Geleki prepend ends with a WAITING_ON_RIG tail for wells whose frozen core starts down,
  which brings the field-total join to the value in §4.
- **N-D9** Health buckets shown in the UI are the interim rule INTERIM_N1 until TC-020 (Stage P).


## 10. Stage Q — TC-021 intervention classifier (Gate Q, `AS_OF` 2026-09-23)

Source: `backend/app/analytics/model/intervention_classifier_metrics.json` (written by
`uv run python -m app.analytics.model.train_classifier --as-of 2026-09-23`; the agent reads quality numbers from
that file only). Model `ic-hgb-v1`: HistGradientBoosting (`class_weight="balanced"`, lr 0.1, 15 leaves, L2 1.0)
× 5 GroupKFold boosters, softmax temperature **1.187** fit on out-of-fold margins. 136 features
(production 59, construction 33 incl. casing / tubing / perforations, history 44).

**Verdict: Gate Q PASSED under orchestrator rulings (2026-10-07).** All metric bars pass on the in-scope holdout
(Q-D1 accepted). LKM-061's criterion is top-2 = {IC-07, IC-04} by ruling Q-R2 (dual-signature fixture). The rulings
were applied without retraining; the metrics JSON records them under `orchestrator_rulings`.

| Gate Q item | Bar | Measured | Pass |
|---|---|---|---|
| Holdout macro-F1 (in scope, 544 jobs 2025-09-24..2026-09-23) | 0.70–0.92 | **0.7437** | ✅ |
| Holdout top-3 accuracy | ≥ 0.90 | **0.9393** | ✅ |
| TC-008 rule baseline macro-F1 (same rows) | — | **0.1887** (341/544 rows have no TC-005/TC-002 mechanism → IC-15) | |
| macro-F1 − baseline | ≥ 0.05 | **+0.555** | ✅ |
| ECE (top-label, 10 bins) | ≤ 0.08 | **0.0243** | ✅ |
| Training support per class | ≥ 30 | min **63** (IC-13) | ✅ |
| Leakage tests | green | 58 tests green (`test_features_no_leakage.py`) | ✅ |
| LKM-023 → IC-06 | top-1 | **IC-06** (p 0.809) | ✅ |
| LKM-061 (GLV + wax) | top-2 = {IC-07, IC-04} (ruling Q-R2; was top-1 IC-07) | IC-04 (p 0.526), IC-07 (p 0.464) | ✅ |

Informational (disclosed in the metrics file, not the gate of record):

| Population | n | macro-F1 | top-3 | ECE | rule baseline macro-F1 |
|---|---|---|---|---|---|
| Full holdout incl. Geleki frozen core | 792 | 0.5985 | 0.7803 | 0.1363 | 0.1485 |
| Geleki frozen core only | 248 | 0.0734 | 0.4315 | 0.4347 | 0.0 |
| Lakwa holdout | 387 | 0.7318 (present classes) | 0.938 | | 0.1776 |
| Lakhmani holdout | 157 | 0.7482 (present classes) | 0.9427 | | 0.2009 |
| Leave-Lakhmani-out (train GK+LKW, test LKM holdout) | 157 | 0.7318 | | | |

Per-class holdout F1: IC-01 0.876 · IC-02 0.760 · IC-03 0.828 · IC-04 0.882 · IC-05 0.629 · IC-06 0.889 ·
IC-07 0.832 · IC-08 0.846 · IC-09 0.618 · IC-10 0.628 · IC-11 0.725 · IC-12 0.653 · IC-13 0.571 ·
IC-14 0.874 · IC-15 0.546. `LOW_CONFIDENCE` threshold 0.40 (fixed a priori): 7.9% of holdout rows fall
below it; accuracy 0.828 at/above vs 0.233 below.

Calibration attempts (all selected on an inner temporal split of the training period, never on the holdout):

1. Isotonic, `ensemble=False` (SDD §8.2 literal) → holdout ECE **0.0993** (fail).
2. Choose among isotonic/sigmoid `CalibratedClassifierCV` by inner ECE → isotonic `ensemble=False` again
   (inner ECE 0.108) → holdout ECE 0.0993 (fail). The one-vs-rest isotonic + renormalisation was *under*-confident
   (inner: mean confidence 0.68 vs accuracy 0.79).
3. Temperature scaling added as a candidate → chosen (inner ECE 0.0464) → holdout ECE **0.0243** (pass). This
   ensemble flips LKM-061 from IC-07 (attempts 1–2) to IC-04 (attempt 3). Not tuned further.

Decisions:

- **Q-D1 (scope), ACCEPTED by the orchestrator 2026-10-07.** Rows of the frozen v0.3.0 Geleki core (`field = Geleki` and `is_prepend = False`; 522 train,
  248 holdout) are excluded from training and from the gate holdout, by provenance (`is_prepend` selects rows and
  is never a feature). That core has no precursor signatures (N-D7), and its catalogue job is drawn at random from
  the failure code (`catalogue.label_geleki_workovers`). The model scores 0.073 macro-F1 on it. TC-021 flags every
  Geleki prediction `LOW_CONFIDENCE` + `OUTSIDE_TRAINING_SCOPE_GELEKI_CORE`. *The orchestrator may reject Q-D1;
  the full-holdout result (0.5985) then fails the 0.70 floor.* Ruling: accepted; the full-holdout numbers stay
  reported in the table above and in `holdout_full_including_geleki_core`.
- **Q-R2 (LKM-061), orchestrator ruling 2026-10-07.** LKM-061 is designed as GLV (strength 1.0) + wax (0.8). Its Gate Q
  criterion is therefore top-2 = {IC-07, IC-04} instead of top-1 IC-07. This is a ruling on the fixture definition,
  not a tuning; the model was not retrained.
- **Q-R3 (calibration), departure from SDD §8.2, accepted 2026-10-07.** Multi-class temperature scaling replaces
  isotonic `CalibratedClassifierCV`, because one-vs-rest isotonic was under-confident (holdout ECE 0.0993).
  SDD §8.2 is to be updated by the orchestrator.
- **Q-D2 (explanations).** `shap` cannot be locked for this project: the py3.11 + darwin-x86 resolution split
  needs llvmlite < 0.46. Exact path-dependent TreeSHAP is implemented in `tools/intervention_classifier.py`.
  It is verified against brute-force Shapley values and is additive to the raw margin.
- **Q-D3 (artefact paths).** Follows build.md / BDD: `analytics/model/intervention_classifier_v1.pkl` and
  `intervention_classifier_metrics.json`.

## 11. Stage R — TC-022 next best action + TC-027 counterfactual (Gate R, `AS_OF` 2026-09-23)

Sources: `backend/app/analytics/tools/{nba,counterfactual}.py`; tests `backend/tests/unit/{test_tc022_nba,
test_tc027_counterfactual}.py` (32 tests). Score = `deferred_bbl_avoided_12mo × p_success ÷ max(rig_days, 0.5) ×
(1 − min(0.45, 0.15 × risk_flags))`; ranking tiers: guardrail-forced → diagnostic fit ✔ → ? (✘ rejected).
No currency anywhere: cost is `cost_band` + `rig_days` (D-1).

| Gate R item | Measured | Pass |
|---|---|---|
| LKW-047 action 1 = `PUMP_OVERHAUL` (as-of 2026-05-14, R-D1) | `PUMP_OVERHAUL` IC-01 ✔ (TC-005 PUMP_WEAR; ML IC-01 0.895), p 0.625 (n 162), 3.0 rig-days, MED, score 937.1. Also as-of 2026-07-06: `PUMP_OVERHAUL` (open episode PUMP_WEAR) | ✅ |
| LKM-090 action 1 = `NO_JOB_JUSTIFIED` | `NO_JOB_JUSTIFIED` (G-2 RESERVOIR_DECLINE, offsets named), all other candidates rejected by G-2 | ✅ |
| Chan-negative fixture → `CHOKE_BACK` + `MODEL_PHYSICS_DISAGREEMENT` | Fixture (GK-129 evidence, Chan CONING WOR′ −0.25, ML top IC-11 0.81): `CHOKE_BACK` (G-1), squeeze rejected `demoted_by G-1`. Real data: GK-103 → `CHOKE_BACK` + G1 + MODEL_PHYSICS_DISAGREEMENT (ML top IC-12) | ✅ |
| GK-129 squeeze vs wax removal | `RECOMMENDED_PREFERRED`, deciding `diagnostic_fit` (wax ✘: no THP rise, WHT falling); cites DOC-SCAN-GK-129-2019, RCA-GK-129-2019, DOC-CBL-GK129-1998 (isolation QUESTIONABLE), WT-GK-129-20260120 | ✅ |
| GK-129 squeeze vs re-perforation | `RECOMMENDED_PREFERRED`, deciding `diagnostic_fit` (re-perf ?) | ✅ |
| Counterfactual dimensions | 6 rows: diagnostic fit (row 1 = PS-GK-129-20260120: SBHP 251.4 kg/cm², PI 0.431, PI −50.6 % vs previous), well history, field efficacy (p, n), execution (rig-days, cost band, MRO, rig slot), value, verdict | ✅ |
| Priority ranking (TC-010, `/api/fields/{f}/priority`) | `score_formula` = deferred × p ÷ max(rig_days, 0.5); 10/10 Lakwa rows recompute exactly; cost band on every row | ✅ |
| No ₹ / USD / payback | `currency_keys` empty for NBA, compare, recommendation; `grep estimated_cost_usd\|payback backend/app` → only the D-1 guard code (see R-D9) | ✅ |
| Every action has SOP | Every job action: `SOP-IC-NN` resolves via `/api/docs/{id}.pdf`, ≥ 1 parsed phase with steps, unit type, duration band. All 14 catalogue SOPs parse | ✅ |

Other measured rank-1 actions (AS_OF): GK-129 `CEMENT_SQUEEZE` ✔ p 0.594 (n 15) 8.0 rig-days HIGH, risk
WELL_INTEGRITY + LOGISTICS_DELAY (no 8-day CLASS_I/II rig window in `rig_calendar`); LKM-061 `GLV_REPLACE` ✔
(3 actions); LKW-047 at AS_OF `SCALE_ACID_BULLHEAD` ? (LOW_CONFIDENCE watch-list — pump already changed 2026-07-07).

Decisions:

- **R-D1 (LKW-047 as-of).** Gate evaluated as-of **2026-05-14**, the last producing day before failure episode
  EP-LKW-047-040 (WAITING_ON_RIG 05-15..06-24, WAITING_ON_MATERIAL to 07-06, job WO-LKW-047-007 on 2026-07-07).
  At AS_OF 2026-09-23 the pump has already been replaced, so action 1 is correctly not a pump job. Generator not edited.
- **R-D2 (refusal has no SOP).** `NO_JOB_JUSTIFIED` has `sop_doc_id = null` (catalogue; BDD F14-S02 requires SOPs
  for IC-01..14 only). Every job action has a resolving SOP.
- **R-D3 (G-1 needs water in play).** G-1 fires only when Chan = CONING with WOR′ < 0 **and** the water problem is
  active or a water class is a candidate. 82 wells are Chan-CONING; firing on Chan alone would over-reach.
- **R-D4 (one job per class).** TC-008 alternatives are candidates; same-class alternatives are rejected with
  their catalogue criterion.
- **R-D5 (diagnostic-fit tiers).** TC-009 uplift is job-independent (decline-restore), so without fit tiers
  rigless jobs win on the rig-days denominator alone. FIT ranks above UNCLEAR in TC-022; TC-027's verdict uses
  the same order (fit first, ✘ is a veto; then value, < 10 % margin = CLOSE), so NBA and compare agree.
- **R-D6 (p_success).** Two-level Beta, α = 5: asset IC prior → field × IC × lift → this well's own record. Only
  finished, non-censored jobs started before `as_of`.
- **R-D7 (rig slot).** First free window in `rig_calendar` for this well alone (WORKOVER_RIG → CLASS_I/CLASS_II).
  The calendar covers only 2026-09-01..10-31; outside it the slot is UNAVAILABLE (not invented).
- **R-D8 (healthy wells).** A PRODUCING_OK well with no diagnosed mechanism gets `LOW_CONFIDENCE` +
  `WELL_HEALTHY_NO_TRIGGER` (watch-list, not a call to mobilise).
- **R-D9 (grep gate).** `grep -rn "estimated_cost_usd\|payback" backend/app` still matches the D-1 *guards*
  (`voice_tools._MONEY_KEY_MARKERS`, `live_prompt.md` "never mention … payback", `common.CURRENCY_KEY_RE`,
  `generator/validate.CURRENCY_TOKENS`) and two docstrings saying "no payback". No response field carries a value.
- **R-D10 (as_of override).** `/nba` and `/compare` accept `as_of` only when `settings.ALLOW_AS_OF_OVERRIDE` is
  truthy (SDD names it; `settings.py` does not define it yet → 422).

Deviations: BDD F04-S01 "3 ranked actions" — candidates (ML ≥ 0.10 + physics route + TC-008 alternatives) after
the fit screen often leave 1–2 actions; flagged `FEWER_THAN_TOP_K`, not padded.

## 12. Stage v0.5 pinned values (DG, NN, FR, DF)

Authoritative targets and parameters for v0.5 stages (from `docs/v05_change_brief.md` canonical source):

| Parameter / Gate Item | Target / Value | Contract / Source | Notes |
|---|---|---|---|
| **DG synthetic seed** | `20261008` | Stage DG deterministic generator | Fixed seed; 100% of 412 wells; `is_synthetic=true`, `_source_system='wellpulse_dg_v1'` (DONE) |
| **Success label mapping** | `SUCCESS` = 1; `PARTIAL` / `FAILED` = 0; `CENSORED`, `NO_ACTION`, `IN_PROGRESS` excluded | Decision D-26 | Label derived from `workover_history.outcome` (~3.6k labelled jobs across 393 wells) |
| **Demo scorer formula** | `clip(p_mechanism(c)^0.5 × (0.5·base_rate + 0.5·analog_rate), 0.05, 0.95)` | Decision D-32 (`success_engine.py`) | Deterministic demo scorer; rounded to 2 dp; presented as multimodal NN in UI |
| **Scorer clipping bounds** | `[0.05, 0.95]` | Decision D-32 | Guaranteed non-extreme probability range |
| **Bayesian shrink prior (base_rate)** | `α = 5` (asset rate prior) | Decision D-32 (`success_engine.py`) | Shrinks field historical rate to asset rate when sample count n is small |
| **Analogs count (k)** | `k = 5` | TC-031 `similar_wells` | Cosine similarity on standardised `build_features` vectors that ran candidate c |
| **Recommendation count (k)** | `k = 3` | TC-030 `recommend_interventions` | Top 3 (primary + 2 alternatives) + `NO_JOB_JUSTIFIED` |
| **Field report latency** | p95 < 3 s | Gate FR | Local server-side Jinja2 render across all 412 wells |
| **Demo flow eval pass rate** | `≥ 90%` | Gate DF (+12 canvas routing cases in `backend/eval/`) | 11-step demo script in chat and voice |
| **NO_JOB_JUSTIFIED threshold** | TBD at Stage NN by orchestrator | Stage NN / Orchestrator decision | Evaluated from best expected value |

- No currency anywhere (cost band + rig-days only, D-1).
- No invented numbers.
- No model training or Vertex AI custom training jobs in v0.5 (Decision D-32; production path described in architecture panel).



## 13. Stage ED (v0.6) pinned values

| Value | Pinned | Source | Notes |
|---|---|---|---|
| **TC-033 offsets** | ≤ 5 nearest; same zone if ≥ 3 exist | `offset_decline.py` (`MAX_OFFSETS`), TC-004 | Offsets without producing data in the window are skipped |
| **TC-033 window / trend** | 24 monthly means (≥ 5 producing days per month); trend = log-linear fit of the last 12 months, needs ≥ 6 | `offset_decline.py` | `decline_pct_yr` positive = declining |
| **TC-033 base verdict** | TC-004 `check_offsets`: `RESERVOIR_DECLINE` if \|excess\| ≤ 5 pp and offsets median residual < −10%; `WELL_SPECIFIC` if excess < −15 pp; else `MIXED`; < 3 offsets → `INSUFFICIENT` | `candidate_ranking.py` | Same verdict the diagnosis / NBA engine uses |
| **TC-033 water rule** | Subject WC up ≥ 10 pts in 12 months → `WATER`; scope `AREA` if offsets' median WC up ≥ 5 pts, else `WELL` | `offset_decline.py` (`WC_JUMP_PTS`, `WC_AREA_PTS`) | Checked before the base verdict |
| **TC-033 restored rule** | `MIXED` + rising rate + residual ≥ +10% → `RESTORED`; credited job = biggest successful uplift in the last 15 months | `offset_decline.py` (`RESTORED_RES_PCT`) | |
| **Hero verdicts (AS_OF 2026-09-23)** | GK-129 `WATER` (WELL); LKW-019 `RESTORED` (straddle packer 2025-10-01, now waiting on rig for sand); LKM-061 `WELL_SPECIFIC` (GL valve signature) | `test_tc033_offset_decline.py` | |
| **TC-034 anomaly rules** | RATE_DROP: 7-day mean oil ≤ 70% of prior 30-day median · WC_JUMP: 7-day mean WC ≥ +10 pts · WC_TREND: last-90-day mean WC ≥ +10 pts vs. the same 90 days a year earlier · THP_SHIFT: ≥ 25% and ≥ 2 kg/cm² · DOWNTIME: non-producing episode ≥ 7 days | `anomalies.py` (`RATE_DROP_FRAC`, `WC_JUMP_PTS`, `THP_SHIFT_FRAC`, `THP_SHIFT_MIN`, `DOWNTIME_DAYS`) | Producing days only for signal rules |
| **TC-034 merge / link / cap** | Same-type events within 30 days merged; job linked if it starts within ±30 days; top 12 by severity, newest first | `anomalies.py` (`MERGE_DAYS`, `LINK_DAYS`, `MAX_EVENTS`) | Default window 24 months |
| **TC-035 job match** | `failure_code` = WAX / SAND, or `catalogue_job_code` starts `WAX_` / `SAND_`; `CENSORED` rows excluded; downtime = status episodes with `reason_code` WAX / SAND | `wax_sand.py` | No sand-rate data (stated in every response) |
| **TC-035 cadence** | Own cycle = median gap between the well's jobs (≥ 2 jobs); field norm = median of per-well cycles in the field; next due = last job + own cycle (never from the field norm); PREDICTABLE needs ≥ 3 jobs; "more / less often than norm" at < 0.8× / > 1.25× | `wax_sand.py` | |
| **TC-035 demo wells** | GK-031 wax: 7 jobs, ~178-day cycle vs. Geleki 360, overdue 50 days · LKW-019 sand: DOWNTIME_ONLY, waiting on rig since 2026-09-06 · LKM-068 sand: 3 jobs, predictable | `test_tc035_wax_sand.py`, smoke run 2026-10-08 | |
| **ED-6 India assets** | 13 ONGC assets at approximate public centres; only Assam live; 10–24 position-only tags per other asset within ≤ 0.18° of the centre (seeded by asset id); names shown from zoom 9 | `ongc_assets.py`, `WellMap.tsx` (`TAG_NAME_MIN_ZOOM`) | Tags carry name + lat/lng only (D-34) |
