# WellPulse v0.5 — Change Brief (canonical)

**Version:** 0.5.0-draft · **Date:** 2026-10-08 · **Owner:** orchestrator · **Status:** authoritative source for every v0.5 doc update. If another doc disagrees with this brief, this brief wins until that doc is updated.

> [!IMPORTANT]
> **Answer first: v0.5 turns WellPulse from an "everything at once" well dump into a question-driven answer canvas. It adds a multimodal success model on Vertex AI that ranks the top 3 interventions with P(success), and a printable HTML field report.** Build order: AC → DF → DG → NN → FR → W2. Commit and push after each passed gate.

---

## 1. Why (user feedback, 2026-10-08)

| # | Feedback | v0.5 response |
|---|---|---|
| U-1 | "The moment I ask the first question I get the whole well history at once." | The chat shows short answers only (≤ 3 sentences plus an optional collapsed card). The all-in-one Deep Dive is removed. |
| U-2 | "Every time a user asks a specific question, the relevant data should be shown." | **Answer canvas:** the middle panel shows only the view that matches the question (§3). |
| U-3 | "Expand the middle screen like the map; the agent is the command centre on the right." | Expandable middle panel: the map hides, ESC or the restore button brings it back. The agent stays on the right. |
| U-4 | "Recommendation can't be one; 2–3 interventions, and show how it arrived at it." | Top 3 (primary + 2 alternatives) + `NO_JOB_JUSTIFIED`, each with P(success), uplift, rig-days, cost band, risks; evidence chain, analog wells, top drivers. |
| U-5 | "A multimodal neural network trained on history, geology, casing, production." | Stage NN: multimodal success model on Vertex AI; the HGB model is the baseline; honest holdout comparison. |
| U-6 | "A final report the workover crew takes to the field, with completion diagrams." | Stage FR: HTML field report with ONGC logo, wellbore SVG, job program; printable on A4. |
| U-7 | "Clear delegation; data generation to Argon, grunt work to Flash." | §8 delegation matrix. |

## 2. New stages (append after W in the stage map)

| Stage | Name | Depends on | Gate summary |
|---|---|---|---|
| **AC** | Answer canvas | W | 10 demo phrases route to the correct view; no full-history dump in chat; `npm run build` + `tsc` green; user UI sign-off |
| **DF** | Demo flow & eval | AC | 11-step demo script (§6) passes in chat and voice; eval set +12 canvas-routing cases ≥ 90% |
| **DG** | Data gaps (synthetic) | N | 6 new tables for 100% of wells, `is_synthetic=true`, consistency tests green, lakehouse parity |
| **NN** | Multimodal success engine (demo scorer) | DG | top-3 API with P(success), analogs, drivers, architecture panel (D-32) |
| **FR** | Field report HTML | DG, NN | `GET /api/wells/{id}/report` renders for all wells < 3 s; A4 print; numbers fact-checked; chat shows a one-line link |
| **W2** | Redeploy | all | local container + Cloud Run deploy + smoke 7/7 (adds `/api/wells/GK-129/report`) |

**Order:** AC → DF; DG can start in parallel with AC/DF; NN after DG; FR after DG + NN (FR's layout scaffold may start after DG); W2 last.

## 3. Stage AC — answer canvas (built, uncommitted)

**Views** (`CanvasView`, exported from `frontend/src/components/well/WellDeepDiveDrawer.tsx`):

| View | Shown for (examples) | Content |
|---|---|---|
| `overview` | "tell me about LKW-019", map "Details" | identity, status, latest test, health bucket |
| `production` | "show production history" | oil/gas/water cut/GOR chart with job markers |
| `interventions` | "past interventions", "workover history" | job table: dates, job, rig-days, uplift, outcome, doc link |
| `wellbore` | "casing", "completion", "wellbore diagram" | casing/tubing/perf/formation tops (SVG in FR) |
| `pressures` | "THP / CHP / pressure survey / gas lift" | pressure & temperature series |
| `diagnosis` | "why is it declining", "what's wrong" | health, decline attribution, mechanism |
| `recommendation` | "what should we do", "next best action" | NBA top 3 + NO_JOB (NN in v0.5) |
| `compare` | "why not sand cleanout", "compare" | counterfactual auto-opened |
| `nearby` | "nearby / offset wells" | nearby wells table + map highlight |
| `report` (FR) | "prepare me for the field", "field report" | HTML field report in the expanded panel |

**Routing:** `pickCanvasView(toolKindOrToolName, userText)` in `frontend/src/api/chat.ts`. Order: the keyword table `KW` on user text first, then the `TOOL_TO_KIND` alias map, then `overview`. Applied to every action path (Live `onAction`, chat reply, fallback, chat-card "Open full view"). Any `screen:'well'` action opens the embedded canvas with that view; the overlay drawer is used only on non-map tabs.

**Rules:** the chat never renders a multi-section well history; the "full history" is reached only through `report`. A view switcher (tab strip) is shown in the canvas header; Back closes the canvas.

## 4. Stage DG — synthetic data gaps

Generated for every well in `well_master` (412 wells) and written to `backend/app/data/landing/<field>/<table>.parquet`, then bronze → silver in BigQuery (append-only, D-19 style). Each row gets `is_synthetic=true`, `_source_system='wellpulse_dg_v1'`, `_batch_id`. Fixed seed `20261008`; the generator is deterministic.

| Table | Grain | Key columns | Generation rule (must agree with existing data) | WH section |
|---|---|---|---|---|
| `tubing_tally` | well × joint | `well_id, joint_no, top_md_m, bottom_md_m, od_in, id_in, drift_in, grade, weight_ppf, component_type` | Sum of joint lengths = `tubing_string` depth; OD/ID from `tubing_string`; components (pump/nipple/mandrel/packer) at existing depths | WH-06 |
| `deviation_survey` | well × station | `well_id, md_m, inc_deg, azi_deg, tvd_m` | Station every 30 m to TD; TVD ≤ MD; vertical wells inc < 3°; deviated wells build profile from a well-type flag | WH-08 |
| `barrier_tests` | well × test | `well_id, test_date, barrier, result, test_pressure_kgcm2, next_due` | Dates after last workover end date, ≤ AS_OF; barriers: SSSV/master valve/wing valve/annulus/packer; FAIL rate ≤ 5% and only on wells with annulus-pressure flags | WH-14 |
| `wellhead_rating` | well | `well_id, wellhead_class_psi, xmas_tree_rating_psi, last_service_date` | Class ≥ 1.5 × field max THP (rounded up to the API class) | WH-14 |
| `fluid_hazards` | well | `well_id, h2s_ppm, co2_mol_pct, wax_flag, sand_flag, scale_flag` | H2S/CO2 by field band; wax/sand/scale consistent with the failure codes and job history of that well | WH-13 |
| `fishing_records` | well × event | `well_id, event_date, fish_type, top_md_m, recovered, workover_id` | Only on wells whose `workover_history` has fishing/stuck failure codes; date inside that job's window | WH-10 |

**Consistency tests** (`backend/tests/unit/test_dg_consistency.py`): coverage 100% of wells; tally length within ±1 joint of tubing depth; TVD monotonic and ≤ MD; barrier dates in range; rating ≥ 1.5 × max THP; fishing only where failure codes allow; `is_synthetic` on every row. The `well_history_template.md` data gap register flips GAP → AVAILABLE (synthetic) for these items.

## 5. Stage NN — multimodal success engine (demo, art of the possible)

> [!IMPORTANT]
> **Decision D-32 (user, 2026-10-08): no model is trained in v0.5.** This is an art-of-the-possible showcase. The agent presents a **multimodal neural network** as the engine that ranks interventions. The scores it shows come from a deterministic **demo scorer** over the demo data, so they are stable, believable and consistent with the well's history. The synthetic world is NOT regenerated, and there is no Vertex AI training job in v0.5.

**What the user sees (story):** "The multimodal NN combines the well's production time series, geology, casing/completion and its intervention history, and compares them with every past job in the asset. It ranks the candidates by probability of success."

**Architecture (shown in the "How did you decide?" panel, as a diagram):**
- Inputs:
  1. Production time-series encoder: 24 months of oil, gas, water cut, GOR, THP and uptime, through a 1D-CNN/GRU.
  2. Static encoder: geology, formation tops, casing/tubing/completion, lift type, deviation, fluid hazards.
  3. History encoder: past jobs and their outcomes.
  4. Candidate-intervention embedding (15 classes).
- These are fused by an MLP that outputs P(success) per candidate.
- Training on Vertex AI (custom job + Model Registry) and batch scoring into `gold.intervention_success_scores` are described as the production path.

**Demo scorer (what actually computes the numbers; `backend/app/analytics/tools/success_engine.py`):**
- `p_mechanism(c)`: the existing trained model `ic-hgb-v1` top-k probability for class c (TC-021). This part is real.
- `base_rate(c, field)`: the historical success rate of class c in this field from `workover_history.outcome`, with a Bayesian shrink to the asset rate when n is small.
- `analog_rate(c)`: the success share of class c among the k = 5 most similar wells (cosine on standardised `build_features` vectors) that ran c.
- **P(success | c) = clip(p_mechanism(c)^0.5 × (0.5·base_rate + 0.5·analog_rate), 0.05, 0.95)**, then rounded to 2 dp. The formula is deterministic and pinned, and every input is shown to the user.
- Drivers: the top 3 feature contributions, from SHAP on `ic-hgb-v1` (already computed by TC-021), mapped to plain-English labels.

**Recommendation output (TC-030 `recommend_interventions(well_id, k=3)`):**
- For each candidate: `class, sop_id, p_success, expected_uplift_bopd` (median uplift of the analog jobs), `rig_days`, `cost_band`, `risks[]`, `why[]`, `analogs{n, n_success, well_ids[]}`, `top_drivers[]`.
- `engine: "multimodal-nn (demo scorer)"` in the payload. The UI shows "Multimodal NN".
- Ranking: guardrail-forced candidates first, then P(success), then fewer rig-days. Deferred barrels are the same TC-009 estimate for every job on a well, so they cannot separate candidates.
- `NO_JOB_JUSTIFIED` is shown when the best expected value is below the threshold in `pinned_values.md`.

**Explanation ("How did you decide?"):**
- Evidence chain: signals → mechanism → candidates.
- Analogs (TC-031 `similar_wells`): "5 look-alikes, 4 succeeded", with clickable well ids.
- Drivers.
- The architecture diagram and a one-line methodology.

**Gate NN (demo):**
- Top 3 render for all producing wells.
- p_success is in [0.05, 0.95] and stable across calls.
- Analog counts recompute exactly from data.
- The explanation panel shows all four elements.
- The GK-129, LKW-019 and LKM-061 outputs are reviewed by the orchestrator for plausibility.

## 6. Stage DF — demo flow (11 steps)

Lakwa → LKW-019:
1. Field compare
2. Sick wells
3. Priority list
4. Overview
5. Production
6. Interventions
7. Wellbore
8. Diagnosis
9. Recommendation (top 3)
10. "Why not sand cleanout" (compare)
11. "Prepare me for the field" (report link)

Each step asserts the canvas view, a chat answer of ≤ 3 sentences, and no history dump. The script lives at `docs/demo_flow.md`; the eval cases go in `backend/eval/` (+12 cases).

## 7. Stage FR — field report (HTML)

- **Route:** `GET /api/wells/{id}/report?intervention=<class>` returns `text/html` (TC-032 `field_report`). It is rendered server-side with Jinja2 from tool outputs only, and opens in the expanded middle panel (iframe) with a Print / Save-as-PDF button.
- **Content:** every section WH-01…WH-19 of [`well_history_template.md`](./well_history_template.md), plus:
  - the wellbore SVG
  - the selected intervention's **job program**: steps, equipment / rig class, kill fluid weight (from reservoir pressure), barriers, risks, contingencies, SOP link
  - the rationale: top 3 with P(success), analogs and drivers
- **Branding:** ONGC logo at the top left of the header and in the print footer. The asset is `frontend/public/brand/ongc_logo.svg`, supplied by the user. If the file is missing, a text wordmark "ONGC" is shown. Every page carries a "SYNTHETIC DATA — DEMO" banner.
- **Integrity:** every number comes from a tool, through a `facts.json` sidecar plus a validator (as in the dossier). Flash writes template prose only and never types digits.
- **Chat:** a one-line link "Field report for LKW-019 is ready → open"; voice says the same in one sentence.
- **Gate FR:** renders for all 412 wells; p95 < 3 s locally; A4 print check; the fact validator is at 100%; the SVG renders even when data is missing (placeholders as specified in WH-05).

## 8. Delegation matrix (v0.5)

| Tier | Model | Owns in v0.5 |
|---|---|---|
| **Orchestrator** | current (Opus-class) | This brief; canvas routing; NN architecture, leakage rules, gates; recommendation contract (TC-030/031); fact validator; reviews; git; cloud apply/deploy |
| **Argon** (data workers) | `gemini-3.8-flash-high` via `swarm add` | DG generators (one worker per table group), their consistency tests, the Vertex training-data export script |
| **Flash** | `invoke_subagent` `Model='flash'` | Doc updates, the Jinja2 report template, the SVG drawing component from the spec, the demo script, eval JSON, the model card prose, checklist ticks |

**Rules:** disjoint files per worker; packets list the exact files and acceptance commands; workers never run git or touch GCP except the explicitly assigned upload/training commands; Flash never types digits into prose.

**Parallel waves:**
- **W-a:** docs (Flash ×4)
- **W-b:** DG (Argon ×3: {tubing_tally, deviation_survey}, {barrier_tests, wellhead_rating}, {fluid_hazards, fishing_records}) ∥ DF script (Flash)
- **W-c:** NN training code (orchestrator) ∥ FR template + SVG (Flash)
- **W-d:** integration, tests, W2

## 9. New IDs

| Kind | IDs |
|---|---|
| Features | **F-20** answer canvas · **F-21** expandable middle panel / command centre · **F-22** synthetic data-gap tables · **F-23** multimodal success model on Vertex AI · **F-24** top-3 recommendation with analogs & drivers · **F-25** HTML field report with job program · **F-26** demo flow |
| Tool contracts | **TC-030** `recommend_interventions` · **TC-031** `similar_wells` · **TC-032** `field_report` · **TC-033** `dg_tables` (read access to the 6 DG tables) |
| Routes | `GET /api/wells/{id}/recommendations?k=3` · `GET /api/wells/{id}/similar?class=` · `GET /api/wells/{id}/report` · `GET /api/wells/{id}/tubing-tally` · `GET /api/wells/{id}/deviation` · `GET /api/wells/{id}/integrity` |
| BDD | `BDD-F20-S01…S04`, `F21-S01…S02`, `F22-S01…S03`, `F23-S01…S03`, `F24-S01…S04`, `F25-S01…S04`, `F26-S01…S02` |
| Decisions | **D-25** answer canvas replaces Deep Dive · **D-26** success label definition (§5) · **D-27** Vertex AI custom training + batch scoring, no online endpoint · **D-28** HGB stays as baseline / fallback; serve the better model on holdout · **D-29** DG synthetic tables flagged `is_synthetic` · **D-30** ONGC logo supplied by the user, with a text-wordmark fallback · **D-31** Argon = `gemini-3.8-flash-high` for data generation · **D-32** no model training or data regeneration in v0.5; multimodal NN presented as the engine, numbers from the deterministic demo scorer (supersedes the training/Vertex parts of D-26/D-27/D-28) |
| Milestones | MS-14 AC · MS-15 DF · MS-16 DG · MS-17 NN · MS-18 FR · MS-19 W2 |

## 10. Unchanged constraints

- No currency (cost band + rig-days only).
- Never change the model names (`gemini-3.8-flash` text, `gemini-3.8-live` Live).
- Numbers only from tools or data.
- uv / npm only.
- Never delete cloud resources.
- Commit and push only after a passed gate, with the user's approval.
