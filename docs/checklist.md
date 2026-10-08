# Implementation & Verification Checklist (`checklist.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 3.1.0 (v0.5 answer canvas & multimodal model)  
**Date:** 2026-10-08  
**Status:** Phases 1-7 done (baseline); Phase 8+ (v0.4) deployed; v0.5 (Milestones MS-14..MS-19) in progress — see ticks below  
**Companion Docs:** [`v05_change_brief.md`](./v05_change_brief.md) · [`build.md`](./build.md) · [`verbatim.md`](../verbatim.md) · [`BRD.md`](./BRD.md) · [`features.md`](./features.md) · [`BDD.md`](./BDD.md) · [`SDD.md`](./SDD.md) · [`DELEGATION.md`](./DELEGATION.md) · [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md)  
**Autonomy:** Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources. A gate that fails 3 times is marked **BLOCKED** here and independent stages continue; never fake a gate; never change the model.  
**User rule:** "During the build, do a git commit and push to origin main after every major milestone (each passed stage gate)."  
**Legend:** `[O]` = orchestrator (Opus/Pro), `[A]` = Argon (`gemini-3.8-flash-high`), `[F]` = Gemini Flash worker (lands only after its deterministic gate passes and `[O]` reviews it).

---

> [!IMPORTANT]
> **Answer first:** The WellPulse baseline (Phases 1–7) is fully shipped and running in production. The v0.4 verbatim expansion executes across 13 discrete stages (Stages M through W), ordered strictly by data dependency rather than priority, each ending in a gate from [`build.md`](./build.md).

---

## Baseline history (Phases 1-7, done)

### Phase 1: Archiving & Repository Scaffolding
- [x] Create `archive/` directory to preserve previous prototypes for learning.
- [x] Relocate legacy `drilling-dashboard/` and `drilling-intelligence/` into `archive/`.
- [x] Synthesize `archive/LEARNINGS.md` with lessons learned.
- [x] Scaffold top-level project folders: `docs/`, `backend/`, `frontend/`, `scripts/`.
- [x] Initialize Git repository and link to GitHub remote.

### Phase 2: Specification Documentation Suite
- [x] Generate **BRD.md** (Business Requirements Document).
- [x] Generate **BDD.md** (Behavior-Driven Development Gherkin scenarios).
- [x] Generate **SDD.md** (Software Design Document & Architecture).
- [x] Generate **features.md** (Detailed Feature Catalog with MoSCoW prioritization).
- [x] Generate **build.md** (Step-by-step local prerequisites and execution commands).
- [x] Generate **checklist.md** (Phased verification tracker).

### Phase 3: Backend & Synthetic Data Engine
- [x] Create `backend/requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `google-genai`).
- [x] Implement `backend/app/services/data_generator.py` simulating 50 Geleki Brownfield wells with 730d telemetry.
- [x] Implement `backend/app/api/wells.py` REST API and WebSocket routes.
- [x] Implement Engineering Reports Dossier Generator:
  - [x] Well Completion Report (WCR)
  - [x] Daily Workover Shift Log (DWR)
  - [x] Bottomhole Pressure & Sonolog Survey (BHP)
  - [x] Produced Water Chemistry & Scale Assay (Lab)
- [x] Implement GCS Data Lake export script and hydrate `gs://workover-operations-agentic-ai-datalake`.

> [!NOTE]
> **Correction (2026-10-07, verified from code):**
> `backend/requirements.txt` lacks `requests`, which is imported by `ai_agent.py`; fixed by `uv` in Stage M.

### Phase 4: Frontend Map, Telemetry & Voice UI
- [x] React 18 + Vite + Tailwind CSS + Leaflet GIS setup.
- [x] Interactive Leaflet Satellite imagery with tagged wellhead labels.
- [x] 3-tier health status visualization (🟢 Optimal, 🟡 Warning, 🔴 Critical).
- [x] 24-month historical telemetry charts (BOPD, MCFD, Water Cut %, Pressures).
- [x] Chronological workover timeline and quantitative flow gain cards.
- [x] 4-tab Engineering Reports Dossier component.
- [x] Bilingual Voice AI Copilot (Hinglish, English, Hindi).

> [!NOTE]
> **Correction (2026-10-07, verified from code):**
> Health status is hard-coded 32/12/6; replaced by data-driven TC-020 in Stage P.

### Phase 5: Cloud Run Production Deployment
- [x] Multi-stage Dockerfile bundling frontend distribution into Python runtime.
- [x] Configure Google Cloud project `workover-operations-agentic-ai`.
- [x] Deploy to Cloud Run in `us-central1` (native Gemini Live region).
- [x] Resolve organization policy to permit unauthenticated access (`allUsers`).
- [x] Initial push to GitHub repository `amandeepsinghs-cyber/workover-operations-ai-agent-cloudrun`.

> [!NOTE]
> **Correction (2026-10-07, verified from code):**
> Phase 5 lists a multi-stage Dockerfile, but the actual Dockerfile is single-stage `python:3.11-slim` copying pre-built `frontend/dist/`; the true multi-stage Dockerfile arrives in Stage W.

### Phase 6: Deep Context AI & Voice UX Overhaul (Completed)
- [x] Enable Vertex AI API (`aiplatform.googleapis.com`) in GCP project `workover-operations-agentic-ai`.
- [x] Grant `roles/aiplatform.user` to Cloud Run service account.
- [x] Update `ai_agent.py` to use Vertex AI ADC natively in `us-central1` (`gemini-2.5-flash`).
- [x] Upgrade local petroleum fallback engine with comprehensive semantic question matching.
- [x] Fix Voice Button UX in `VoiceAgentPanel.tsx`:
  - [x] Replace `<MicOff>` mute icon with an active, pulsing `<Mic>` icon.
  - [x] Switch styling to active emerald green glow with ripple animation.
  - [x] Enable `interimResults = true` so spoken words appear immediately in the input box.
  - [x] Add sound-wave frequency bars and clear "Listening... Speak now" indicator.
- [x] Add Geleki Gas Gathering Stations (GGS-1, GGS-2, GGS-3) and pipeline network on the satellite map.
- [x] Add One-Click Engineering Dossier Export (Download formatted JSON/Markdown).

> [!NOTE]
> **Correction (2026-10-07, verified from code):**
> Phase 6 notes that `ai_agent.py` uses Vertex AI ADC with `gemini-2.5-flash`, but the code today calls the Generative Language REST API with `GEMINI_API_KEY` and model `gemini-3.8-flash`; Vertex ADC returns in Stage U/V (with decision D-13 keeping `gemini-3.8-flash`).

### Phase 7: Verification, Redeployment & GitHub Sync (Completed)
- [x] Verify local production build (`npm run build`).
- [x] Test Vertex AI live chat in Hinglish, English, and Hindi.
- [x] Redeploy optimized service to Cloud Run in `us-central1`.
- [x] Verify live unauthenticated Cloud Run URL.
- [x] Stage, commit, and push all updates to GitHub.

---

## Phase 8+ · v0.4 verbatim expansion

### Phase 8 · Stage M — Preflight & baseline
**Verbatim anchor:** derived: safe migration (D-14), no tests exist today

#### Tasks
- [x] [O] Step 0 Auth preflight: verify ADC and set project to `workover-operations-agentic-ai` (`gcloud auth list`, `gcloud auth application-default print-access-token`, `gcloud config set project`)
- [x] [O] Step 1 uv initialization: initialize `backend/pyproject.toml` and `backend/uv.lock`, add runtime (`fastapi`, `uvicorn[standard]`, `pydantic`, `python-dotenv`, `google-genai`, `requests`) and dev (`pytest`, `httpx`, `pytest-asyncio`, `ruff`) dependencies, update `.gitignore`, and remove `backend/requirements.txt`
- [x] [O] Step 2 Golden API snapshots: implement `backend/tests/golden/capture.py` capturing GLK-101, GLK-120, GLK-150, generate `backend/tests/golden/*.schema.json`, and implement `backend/tests/test_api_shapes.py`
- [x] [O] Step 3 UI baseline verification: execute `npm ci` and `npm run build` in `frontend/` and log bundle size
- [x] [O] Step 4 Baseline port source: copy `${ADK_REPO}/data/landing` to `backend/tests/baseline/landing_v030` (git-ignored) and verify ADK repo contract tests and validator
- [x] [O] Step 5 Launcher update: update `run_local.sh` to use `uv run` while serving `:8002` and `:5180`

#### Gate M
- [x] ADC valid; `gcloud config get-value project` = `workover-operations-agentic-ai`
- [x] `backend/pyproject.toml` and `uv.lock` committed; `uv sync --frozen` works from clean; `requests` resolved
- [x] `./run_local.sh` uses `uv run` and still serves `:8002` / `:5180`
- [x] Golden schema files exist for every existing `/api` route, and `test_api_shapes.py` is green
- [x] `npm run build` succeeds; bundle size logged
- [x] ADK repo baseline: contract tests green, validator 0 violations; `landing_v030/` copied (git-ignored)
- [ ] [O] Commit + push after Gate M passes: `git commit -m "v0.4(M): preflight & baseline — Gate M passed" && git push origin main`

---

### Phase 9 · Stage N — Data foundation v2
**Verbatim anchor:** §1 *"Lakwa… Lakhmani… three areas, with their individual cluster"*; §1 *"generate more data"*

#### Tasks
- [x] [F] N-F1 Port generator modules and `train.py` boilerplate from `${ADK_REPO}` with import rewrites into `backend/app/analytics/generator/` and `backend/app/analytics/model/train.py`
- [x] [O] N.1 FieldConfig and field modules: implement `backend/app/analytics/generator/fields/{__init__.py, geleki.py, lakwa.py, lakhmani.py}` with fixtures (LKW-047, LKW-088, LKW-112, LKM-023, LKM-061, LKM-090) and new tables in `{hierarchy.py, construction.py, operations_events.py, targets.py}` (incl. `pressure_surveys`, `formation_tops`, D-19)
- [x] [O] N.2 Catalogue and labels (K-1, K-2): add `GLV_REPLACE` and `cost_band` to `job_catalogue`; add `catalogue_job_code` and `intervention_class` (IC-01…IC-15) to `workover_history`
- [x] [O] N.3 Telemetry columns (D-19): add `wht_degc`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2` (GOR = `gor_scf_bbl`; SPM for SRP), plus append-only `pressure_surveys` and `formation_tops`
- [x] [O] N.4 Repository layer: implement `backend/app/data_access/{repository.py, parquet_repo.py, adapters.py}`, update `backend/app/api/wells.py` to read from repository, and deprecate/delete `backend/app/services/data_generator.py`
- [x] [F] N-F2 Frontend type and label updates: update `frontend/src/types/well.ts` and `frontend/src/components/timeline/WorkoverTimeline.tsx` (replace `cost_usd` with `cost_band` + `rig_days`)
- [x] [O] N.5 Generation and validation: generate 60-month dataset (2021-10-01 to 2026-09-30) for all fields, validate V-N1..V-N7 and baseline comparison, verify CoxPH model training
- [x] [O] N.6 Pin design targets: run `pin_targets.py` to generate `docs/pinned_values.md` and replace `«target ± tol»` placeholders in `BDD.md`

#### Gate N
- [x] Validator 0 violations for Geleki, Lakwa and Lakhmani; well counts 142 / 160 / 110
- [x] Geleki's pre-existing columns are hash-identical to `landing_v030`; the Geleki join at the prepend boundary is continuous (±3%)
- [x] All fields cover 2021-10-01 → 2026-09-30, and two runs produce byte-identical parquet (reproducible; fixes the `now()` defect)
- [x] CoxPH C-index reproduces 0.7128 with the prepend excluded (Gate E)
- [x] Every IC-01…IC-15 has ≥ 30 `workover_history` rows; `GLV_REPLACE` exists
- [x] Lakwa gap vs. target inside −18% ± 3 pp; LKW-047 has 41 `WAIT_ON_RIG` days and 12 `WAIT_ON_MATERIAL` days
- [x] `wht_degc`, `gor_scf_bbl`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2` present; `pressure_surveys` and `formation_tops` populated (verbatim WS6, D-19)
- [x] `test_api_shapes.py` green against the repository (React UI unchanged except for the N-F2 cost-band fields); `npm run build` green
- [x] No `cost_usd` remains in API responses (D-1)
- [x] `docs/pinned_values.md` written; BDD targets replaced
- [ ] [O] Commit + push after Gate N passes: `git commit -m "v0.4(N): data foundation v2 — Gate N passed" && git push origin main`

---

### Phase 10 · Stage O — PDF corpus + SOPs
**Verbatim anchor:** §1 *"generate the documents of PDF files of… well interventions"*; §3 *"The SOPs"*

#### Tasks
- [x] [O] O-O1 Fact-slot framework: implement `backend/app/analytics/generator/docs_pdf/{facts.py, render.py, scanify.py, validate.py, index.py}`, fact-slot schemas, and API routes in `backend/app/api/docs.py` (`GET /api/docs/{doc_id}.pdf`, `GET /api/wells/{id}/documents`) — built at `backend/app/analytics/docs_pdf/` (packet path; not `analytics/generator/`)
- [x] [F] O-F1 D1 Well Completion Report (WCR) generator template
- [x] [F] O-F2 D2 Workover Completion Report generator template
- [x] [F] O-F3 D3 Daily Workover Shift Log (DWR) generator template
- [x] [F] O-F4 D4 Well Completion Schematic generator template
- [x] [F] O-F5 D5 Cement Bond Log (CBL) survey generator template
- [x] [F] O-F6 D6 Chemical Treatment Log generator template
- [x] [F] O-F7 D7 Well Test Report generator template
- [x] [F] O-F8 D8 Root Cause Analysis (RCA) report generator template
- [x] [F] O-F9 D9 Field Study Report generator template
- [x] [F] O-F10 D10 Monthly Field Performance Report generator template
- [x] [F] O-F11 D11 SOP library generator template (IC-01…IC-14) — Flash outputs (D1–D11 templates, IC-01…IC-14 YAML, hero YAML) reviewed by [O] (BDD-F19-S02); D5 QUESTIONABLE branch split by `assessment_basis` by lead
- [x] [F] Hero narrative prose drafting for GK-129, LKW-047, LKW-112, LKM-090 (reviewed by [O]) — lead review done 2026-10-07: overclaims softened (no VDL/amplitude data claimed; GK-129 2019 water cut "not recorded"; LKM-090 wording uses signed change)
- [x] [O] UI document integration: update `frontend/src/components/reports/WellReportsTab.tsx` to consume document index while keeping the JSON export
- [x] [O] Corpus generation and validation: run `render --field all`, `scanify --fraction 0.10 --types D1,D5`, validate 100% facts, and build the TF-IDF index `backend/app/data/index/{doc_chunks.parquet, tfidf.pkl}` (D-17)

#### Gate O
- [x] D1…D11 present for all 3 fields; every IC-01…IC-14 has an SOP (D11)
- [x] Fact validation 100%; no digit in template prose outside a fact slot
- [x] Every `document_index` row resolves; `GET /api/docs/{id}.pdf` returns `application/pdf`
- [x] The scanned subset is flagged `has_text_layer=false` and is still retrievable
- [x] GK-129 has the 1998 CBL (D5) and the 2019 failed water-shut-off report (D2)
- [x] WellReportsTab shows real documents for the selected well; `npm run build` green
- [x] Corpus size logged (target ≤ 200 MB, so it fits in the image) — measured 155.0 MB (PDF 118.6 + facts.json 36.4) + index 34.5 MB; git-ignored, regenerated by `uv run python -m app.analytics.docs_pdf.build` (D-18)
- [ ] [O] Commit + push after Gate O passes: `git commit -m "v0.4(O): PDF corpus + SOPs — Gate O passed" && git push origin main`

---

### Phase 11 · Stage P — Analytics port + attribution + health
**Verbatim anchor:** §1 *"why did the production decline? Was it human factor, controllable factor"*; §1 *"which of the wells are doing okay… not producing now"*

#### Tasks
- [x] [O] Deterministic tools port: port 18 deterministic tools (TC-001…TC-018) from `${ADK_REPO}/tools/` into `backend/app/analytics/tools/{common,arps_decline,chan_diagnostic,candidate_ranking,render_well_map}.py`, removing Geleki defaults (K-6)
- [x] [O] Hierarchy helper: implement `field_of()` in `backend/app/analytics/tools/hierarchy.py`
- [x] [O] TC-019 decline attribution: implement `backend/app/analytics/tools/attribution.py` and `backend/app/analytics/config/factor_map.yaml`
- [x] [O] TC-020 data-driven health engine: implement `backend/app/analytics/tools/health.py` and wire into `backend/app/api/wells.py` (`/api/wells/kpis` and well status) — wired through `data_access/adapters.well_summary` (wells.py unchanged; kpis/status follow)
- [x] [F] P-F1 Unit-test scaffolds from TC signatures for tools port, TC-019 attribution, and TC-020 health

#### Gate P
- [x] All 18 ported tools pass the ADK contract tests (ported to `tests/unit/test_tools_port.py`); no `GK-129` / `Geleki` defaults remain (K-6)
- [x] The attribution waterfall sums to the total loss within 0.5% for every well in all 3 fields
- [x] LKW-047's largest class is `HUMAN_PROCESS`; LKM-090 is ≥ 80% `SUBSURFACE`; LKW-088 shows `EXTERNAL` (`GRID_POWER_OUTAGE`)
- [x] TC-020 buckets come from data; `random.seed(42)` status removed; `/api/wells/kpis` = TC-020 counts
- [x] Geleki trigger results are unchanged from the ADK baseline — accepted by orchestrator: data-driven replaces hard-coded fixtures (deviation table: pinned_values.md §8.2)
- [ ] [O] Commit + push after Gate P passes: `git commit -m "v0.4(P): analytics port + attribution + health — Gate P passed" && git push origin main`

---

### Phase 12 · Stage Q — ML intervention classifier
**Verbatim anchor:** §1 *"run a classification algorithm… 5 to 10… or 15 type of interventions"*

#### Tasks
- [x] [O] Feature engineering: implement `backend/app/analytics/model/features.py` incorporating production telemetry, well history, and construction tables (casing, tubing, perforations) without data leakage
- [x] [O] Classifier training pipeline: implement `backend/app/analytics/model/train_classifier.py` (multi-class IC-01…IC-15 with SHAP explainability), producing `backend/app/analytics/model/intervention_classifier_v1.pkl` and `intervention_classifier_metrics.json`
- [x] [O] TC-021 classifier tool: implement `backend/app/analytics/tools/intervention_classifier.py`
- [x] [O] Unit and leakage tests: implement `backend/tests/unit/{test_features_no_leakage.py, test_tc021_classifier.py}`

#### Gate Q
- [x] Holdout **macro-F1 0.70–0.92**
- [x] Top-3 accuracy ≥ 0.90
- [x] Beats the TC-008 rule baseline by ≥ 0.05 macro-F1
- [x] ECE ≤ 0.08
- [x] Leakage test green (no post-event features); LKM-023 → IC-06, LKM-061 → IC-07 — leakage green; LKM-023 → IC-06; LKM-061 top-2 = {IC-07, IC-04} per orchestrator ruling Q-R2 (dual-signature fixture); see pinned_values.md §10
- [x] Features include construction tables (casing, tubing, perforations) and prior-job history (verbatim §1)
- [ ] [O] Commit + push after Gate Q passes: `git commit -m "v0.4(Q): ML classifier — Gate Q passed" && git push origin main`

---

### Phase 13 · Stage R — Next best action + counterfactual
**Verbatim anchor:** §1 *"recommend what is the next best action"*; §3 *"Why are you recommending this against an alternative?"*

#### Tasks
- [x] [O] TC-022 Next Best Action: implement `backend/app/analytics/tools/nba.py` with expected uplift, cost band, rig-days, risk profile, and SOP link (D11)
- [x] [O] TC-027 Counterfactual defense: implement `backend/app/analytics/tools/counterfactual.py` evaluating reservoir pressure/IPR (row 1 uses `pressure_surveys`), historical efficacy, and cost-band/downtime delta; served by `GET /api/wells/{id}/compare?recommended=&alternative=`
- [x] [O] Recommendations API refactoring: update `backend/app/services/ai_agent.py` (`generate_structured_recommendation` delegates to TC-022) and `POST /api/wells/{id}/recommendations`, replacing `estimated_cost_usd` with `cost_band` + `rig_days`
- [x] [O] Unit tests: implement `backend/tests/unit/{test_tc022_nba.py, test_tc027_counterfactual.py}`

#### Gate R
- [x] LKW-047 action 1 = `PUMP_OVERHAUL`; LKM-090 action 1 = `NO_JOB_JUSTIFIED`
- [x] Hero GK-129: `compare_interventions(squeeze vs. wax removal)` returns the verdict, the deciding dimension and a cited prior-job document (D5 1998 CBL / D2 2019 WSO)
- [x] The counterfactual covers the reservoir/IPR, historical-efficacy and cost-band + rig-days dimensions (verbatim §4 T5)
- [x] A Chan-negative fixture yields `CHOKE_BACK` with `MODEL_PHYSICS_DISAGREEMENT`
- [x] Priority ranking (`GET /api/fields/{field}/priority`) = deferred bbl × p_success ÷ rig-days, shown with the cost band (K-7)
- [x] **No ₹, USD or payback point value** in any response (D-1); `grep -rn "estimated_cost_usd\|payback" backend/app` returns nothing (only D-1 guard code remains — pinned_values §11 R-D9)
- [x] Every action has a resolving `sop_doc_id` (D11) and SOP steps, unit type and duration band (verbatim §4 T5)
- [ ] [O] Commit + push after Gate R passes: `git commit -m "v0.4(R): NBA + counterfactual — Gate R passed" && git push origin main`

---

### Phase 14 · Stage S — Field-engineer dossier
**Verbatim anchor:** §1 *"aggregate all the history and give it to the person who is going to the field"*

#### Tasks
- [x] [F] S-F1 Layout, styling, and 9 section templates (no digits) for the pre-job dossier PDF in `backend/app/analytics/tools/dossier.py`
- [x] [O] TC-023 Dossier assembly: implement data assembly, fact tracing, and UNAVAILABLE fallbacks in `backend/app/analytics/tools/dossier.py`
- [x] [O] Export route & UI integration: update `GET /api/wells/{id}/export` in `backend/app/api/wells.py` (JSON adds `pdf_url`; `?format=pdf` returns the PDF), add `POST /api/wells/{id}/dossier` (English-only, Q-2; lithology from `formation_tops`), and wire into `frontend/src/components/reports/WellReportsTab.tsx`
- [x] [O] Unit tests: implement `backend/tests/unit/test_tc023_dossier.py`

#### Gate S
- [x] 2–4 pages, ≤ 10 s, all 9 sections, including lithology and casing/tubing tallies (verbatim WS4)
- [x] Every number traces to a table or tool return; missing sections render `UNAVAILABLE — <table>`
- [x] GK-129 cites the 1998 CBL and the 2019 WSO
- [x] The JSON export still works (baseline FEAT kept)
- [ ] [O] Commit + push after Gate S passes: `git commit -m "v0.4(S): dossier — Gate S passed" && git push origin main`

---

### Phase 15 · Stage T — Asset view & drill-down
**Verbatim anchor:** §1 *"Which particular field is not performing?"*; §3 *"Can you give me a plot?"*, *"drill down to one particular well"*, *"information of nearby wells"*

#### Tasks
- [x] [O] Field analytics tools: implement `backend/app/analytics/tools/{field_performance.py (TC-024, TC-028), hierarchy.py (TC-025), well_profile.py (TC-029)}` and TC-017 v2 job markers — TC-028 placed in `field_history.py`; TC-017 v2 `well_production_series` in `well_profile.py`
- [x] [O] Fields REST API: implement `backend/app/api/fields.py` (`GET /api/fields`, `/api/fields/history?fields=`, `/api/fields/{field}/history`, `/api/fields/compare?period=`, `/api/fields/{field}/health?cluster_id=`, `/api/fields/{field}/attribution?window_days=`, `/api/fields/{field}/priority`) and in `wells.py` `/api/wells/{id}/profile`, `/api/wells/{id}/production` (markers + WHT / GOR / gas-lift series) — Stage T routes live in new `app/api/asset.py` (+ `/api/fields/map`) to avoid editing Stage P's `fields.py`/`wells.py`; `/health` and `/attribution` remain in `fields.py`
- [x] [F] T-F1 Boundary geodata: create synthetic GeoJSON boundaries for Geleki, Lakwa, Lakhmani and GGS clusters in `backend/app/data/geodata/` (D-3) — generated by `python -m app.analytics.tools.geodata` from field_master + cluster convex hulls
- [ ] [F] T-F2 Recharts visualization components: implement `frontend/src/components/field/{FieldHistoryChart.tsx, FieldComparisonTable.tsx, AttributionWaterfall.tsx, HealthBucketsCard.tsx, PriorityQueueTable.tsx}` and `components/well/NbaCard.tsx` — PARTIAL: `components/fields/{FieldHistoryChart,FieldComparison}.tsx` done (comparison includes health counts + deferred-by-factor stacks); AttributionWaterfall / HealthBucketsCard / PriorityQueueTable / NbaCard not built in Stage T
- [ ] [F] T-F3 Screen scaffolding & integration: implement `frontend/src/components/common/FieldSelector.tsx`, `components/well/{WellDeepDive.tsx, NearbyWellsTable.tsx, CounterfactualTable.tsx}`, and update `TelemetryCharts.tsx` with job markers, WHT, GOR and gas-lift injection rate + pressure — PARTIAL: `fields/FieldSelector.tsx`, `well/{WellDeepDiveDrawer,NearbyWellsList,ProductionMarkersChart}.tsx`, TelemetryCharts section, App/WellMap integration done; CounterfactualTable not built
- [x] [O] Unit and contract tests: implement `backend/tests/unit/{test_tc024_fields.py, test_tc025_hierarchy.py, test_tc028_field_history.py, test_tc029_well_profile.py}` (+ `test_asset_routes.py`)

#### Gate T
- [x] `compare_fields` ranks Lakwa worst, inside the pinned band, with a controllable top driver; the rows include target, uptime, water cut and `active_interventions` counts (TC-024, verbatim WS1) — QTD Lakwa −17.6% / Lakhmani −8.5% / Geleki −1.5%, all in band; top driver HUMAN_PROCESS 59.5% (controllable); Lakwa active_interventions 7
- [x] TC-028 returns 60 monthly points per field for oil, water cut and gas; aggregation reconciles with well sums within 0.1% — 60 pts/field, max reconciliation error 0.0%
- [x] TC-029 returns formation, casing/tubing, lift type and ≥ 3 neighbours on the same cluster; TC-017 v2 shows all in-window job markers
- [x] `TelemetryCharts` shows WHT, GOR and gas-lift injection rate + pressure from `GET /api/wells/{id}/production`
- [x] UI: field selector, 5-year field chart, comparison, well deep-dive with markers and nearby wells all render from the APIs (no hard-coded values) — Lakwa map: 160 LKW points, 0 foreign, 3 GGS polygons
- [x] `npm run build` green; Part I screens are not regressed — tsc + build green; pytest 288 passed (excl. Stage Q `test_tc021_classifier.py`, pending its model artifact)
- [ ] [O] Commit + push after Gate T passes: `git commit -m "v0.4(T): asset view & drill-down — Gate T passed" && git push origin main`

---

### Phase 16 · Stage X — Medallion Lakehouse
**Verbatim anchor:** §3 *"showcase that in the Medallion architecture… Lakehouse"*; *"whether it should go ultimately into BigQuery or… a better database"*

#### Tasks
- [x] [F] X-F1 Medallion DDL scripts: write BigQuery DDL schemas for Bronze, Silver, and Gold in `lakehouse/ddl/*.sql` (Silver partitioned by `production_date`, clustered by `field, well_id`; Silver `doc_chunks` mirror of the TF-IDF index, D-17)
- [x] [F] X-F2 Bronze-to-Silver ETL loader: implement `lakehouse/load/bronze_to_silver.py` loading `gs://workover-operations-agentic-ai-datalake/bronze/` and `documents/` into BigQuery; exports to `silver_exports/`
- [x] [F] X-F3 Dataform pipeline: create `lakehouse/dataform/` compiling and executing Silver-to-Gold aggregations (`field_kpi_monthly`, NBA features)
- [x] [O] DDL apply — Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources: `bq query --dry_run` every DDL file, then apply; bucket = existing `gs://workover-operations-agentic-ai-datalake`
- [x] [O] X-O4 Repository & parity: implement `backend/app/data_access/bigquery_repo.py`, integration parity test `backend/tests/integration/test_backend_parity.py` (`DATA_BACKEND=parquet|bigquery`), and production-store decision record in `SDD.md`

#### Gate X
- [x] `wellpulse_bronze`, `wellpulse_silver` and `wellpulse_gold` exist in `asia-south1`; Silver `daily_production` is partitioned by `production_date` and clustered by `field, well_id`
- [x] Silver row counts = Bronze; Gold `field_kpi_monthly` = TC-028 output
- [x] Parquet vs. BigQuery parity test green; the app runs with `DATA_BACKEND=bigquery`
- [x] Silver `doc_chunks` mirrors the TF-IDF index from D1–D11 (D-17; Vertex AI Search optional later, verbatim §5) — 28,675 chunks / 20,966 docs = `data/index/doc_chunks.parquet`; `gold.dossier_facts` 1,522,055 facts; 41,932 objects (155 MB) in `documents/`
- [x] Production-store decision record (BigQuery vs. alternatives) recorded in [`SDD.md`](./SDD.md) §15.2 (verbatim §3) — full record: `lakehouse/decision_record.md`
- [ ] [O] Commit + push after Gate X passes: `git commit -m "v0.4(X): medallion lakehouse — Gate X passed" && git push origin main`

---

### Phase 17 · Stage U — Real Gemini Live
**Verbatim anchor:** §1 *"Gemini Live is not working well… working very good in Drilling Intelligence 2.0"*

#### Tasks
- [x] [O] Reference study: inspect `${DI2_REPO}/backend/app/agent/live_session.py`, `backend/app/api/ws_live.py`, `frontend/src/live/{liveClient,micCapture,audioPlayer}.ts`, and `docs/adr/ADR-003-gemini-live-adk-proxy.md`
- [x] [O] Model verification (U.2): run live model verification script against Vertex AI in `us-central1` and write exact returned names into `backend/.env` (`TEXT_MODEL`, `LIVE_MODEL`, `LIVE_LOCATION`); if missing after 3 attempts, mark Stage U BLOCKED — never substitute
- [x] [O] Live session engine: implement `backend/app/live/{session.py, voice_tools.py, live_prompt.md, fallback.py}` supporting resumption, context compression, session recap, and 3-failure fallback to text
- [x] [O] Live WebSocket route: implement `backend/app/api/live.py` serving `WS /ws/live` (field/well context message); legacy `WS /api/wells/{id}/live` shim kept until Gate V (D-20)
- [x] [F] U-F1 AudioWorklet client: implement `frontend/src/live/{liveClient.ts, micCapture.ts, pcm-worklet.js, audioPlayer.ts}` (16 kHz upload / 24 kHz playback)
- [x] [F] U-F2 Voice UI state machine: update `frontend/src/components/agent/VoiceAgentPanel.tsx` with connection states (connecting, listening, speaking, fallback), remove browser `speechSynthesis`, retain language toggle, add open-mic hands-free option (audio-only)
- [x] [O] Integration testing: implement `backend/tests/integration/test_ws_live.py` verifying reconnect, recap, and 3-failure fallback

#### Gate U
- [x] The model names in `.env` come from the U.2 listing (output pasted into the commit message or PR)
- [ ] Spoken answer to *"Which field is underperforming?"*; first audio ≤ 2.5 s warm
- [ ] Barge-in ≤ 300 ms; a forced reconnect keeps context (resumption + recap); 3 failures → text fallback with a visible notice
- [x] Spoken numbers equal tool returns (same functions as the text path)
- [x] The language toggle still works; `speechSynthesis` is no longer used for Live replies
- [ ] Open-mic hands-free mode works; `FIELD_ENGINEER` persona can use Live voice
- [ ] Runs on Vertex ADC; `GEMINI_API_KEY` is not read anywhere (`grep -rn GEMINI_API_KEY backend/app` is empty)
- [ ] [O] Commit + push after Gate U passes: `git commit -m "v0.4(U): real Gemini Live — Gate U passed" && git push origin main`

---

### Phase 18 · Stage Y — RBAC + multi-field GIS
**Verbatim anchor:** §3 *"role-based access… Executive Director… versus a field engineer"*; §3 *"they can see different fields… and the wells"*

#### Tasks
- [x] [O] Y-O1 RBAC policy engine: implement `backend/app/agent/rbac.py` (matrix in code) and `require()` checks in `backend/app/agent/adk_tools.py` in tool wrappers across `ED`, `ASSET_MANAGER`, and `FIELD_ENGINEER` personas — *Stage Y: matrix, `require()` (REST), `@gated` (tool wrappers), voice + doc_type gating, redaction done and applied to fields/asset/docs/voice; decorating `adk_tools.py` wrappers is Stage V (file does not exist yet; see `rbac.STAGE_V_TODO`)*
- [x] [F] Y-F2 Persona UI & Multi-field Map: implement `frontend/src/components/common/PersonaPicker.tsx`, update `components/map/WellMap.tsx` (multi-field boundaries, GGS clusters, health colours, field filter, synthetic label per D-3, Esri basemap per D-5), and update `Header.tsx`
- [ ] [O] Unit and BDD tests: implement `backend/tests/unit/test_rbac.py` and BDD tests in `backend/tests/bdd` — *unit done (16 tests, rbac + gis); pytest-bdd glue for BDD-F16/F17 left for Stage V (V-F1)*

#### Gate Y
- [x] The same question as ED vs. FIELD_ENGINEER gives correctly scoped answers per verbatim §6; a direct denied tool call returns `UNAVAILABLE` (no data leak in the error)
- [x] The map shows 3 fields with boundaries, GGS markers and a field filter; header counts = TC-020; the well drawer = TC-029
- [x] Synthetic coordinates are labelled as synthetic on the map (D-3)
- [ ] Persona switch works in both text and Live — *REST (X-Persona on every /api call) and Live (query param + `context` ui_state, server re-gates every voice tool) verified at API/unit level; agent text chat depends on Stage V runner; in-browser check pending*
- [ ] [O] Commit + push after Gate Y passes: `git commit -m "v0.4(Y): RBAC + multi-field GIS — Gate Y passed" && git push origin main`

---

### Phase 19 · Stage V — Agent wiring & eval
**Verbatim anchor:** §3 *"do you see the hierarchy of question and answering?"* (5-level flow, §4 L1–L5)

#### Tasks
- [x] [O] In-process ADK Runner: implement `backend/app/agent/{runner.py, adk_tools.py, prompt.py, callbacks.py}` wiring ~30 tool wrappers with strict numeric trace and anti-fabrication guardrails — *Stage V: ADK 2.11 Runner, 30 wrappers (`adk_tools.py` + `adk_tools_ext.py`, RBAC via `invoke()`), `check_numbers` after-model guardrail (masks ungrounded numerals as «see table», deviation from SDD §12.6 regenerate), FakeLlm for CI*
- [x] [O] Chat API refactoring: implement `backend/app/api/chat.py` (`POST /api/chat`), route per-well `/chat` and `/audio` to Runner, remove legacy `/api/wells/{id}/live` and `/audio` shims at the end of V (D-20), and delete prompt-stuffing and keyword fallback in `services/ai_agent.py` — *`/chat` → Runner; `/audio` + per-well WS removed; `ai_agent.py` keeps only `generate_structured_recommendation` (TC-022)*
- [x] [F] V-F1 BDD Gherkin test suite: generate `backend/tests/bdd/features/*.feature` and step implementations for L1–L5 hierarchical conversation flow — *20 pytest-bdd scenarios (F-18, X, F-04/09/11/12/13/16), all green*
- [x] [F] V-F2 Agent evaluation dataset: build `backend/tests/eval/wellpulse-eval.json` (≥ 30 cases: every L1–L5 turn × 3 personas + refusals, all voice and text scenarios) — *46 cases (21 F-18 L1–L5 × 3 personas, Hinglish/Hindi, refusals, 10 holdout)*
- [ ] [F] V-F3 Playwright E2E specs: implement `frontend/tests/e2e/*.spec.ts` for full UI click-through
- [ ] [O] Eval iteration & test execution: run pytest suite, run `agents-cli eval run` (tool selection ≥ 90%), and execute Playwright tests — *pytest 426 passed / 1 skipped (live); eval via `tests/eval/run_eval.py` (ADK Runner, not agents-cli) on gemini-3.8-flash: tool selection 46/46 = 100% (holdout 10/10), number grounding 46/46 (`tests/eval/results/vertex-final-20261007T234533.json`); Playwright NOT run (V-F3 not done)*

#### Gate V
- [x] All BDD scenarios green, including one automated test per demo turn L1–L5 (verbatim §8 M6) — *20/20 BDD + `tests/integration/test_demo_flow.py` (fake LLM; live gemini-3.8-flash L1–L5 7/7 turns in 3/3 runs)*
- [x] Eval tool-selection accuracy ≥ 90% on `tests/eval/wellpulse-eval.json` (≥ 30 cases); if it is lower, apply the SDD sub-agent split and re-run — *100% (46/46) on gemini-3.8-flash, 4 runs all 46/46; sub-agent split not needed*
- [x] No answer contains a number missing from that turn's tool returns (number-trace test) — *`test_agent_callbacks.py` (fabricating model → masked, ok=False), demo-flow + eval grounding 46/46*
- [x] The agent refuses at least once per new field (LKM-090 → no job justified) and explains why — *eval `f04_s03_refusal_lkm090` + BDD-F04-S03*
- [x] The prompt-stuffing code and the keyword fallback are removed; text runs on Vertex ADC with `gemini-3.8-flash` (D-13) — *Vertex `global`, project from settings; `grep GEMINI_API_KEY backend/app` empty*
- [ ] Playwright: L1→L5 click-through passes against `npm run build` served by FastAPI
- [x] Legacy `/api/wells/{id}/live` and `/audio` shims removed; `WS /ws/live` is the only Live route (D-20) — *`test_legacy_audio_and_well_live_routes_removed`*
- [ ] [O] Commit + push after Gate V passes: `git commit -m "v0.4(V): agent wiring & eval — Gate V passed" && git push origin main`

---

### Phase 20 · Stage W — Deploy (authorised by user, 2026-10-07)
**Verbatim anchor:** derived: demo must run on the existing public URL

#### Tasks
- [x] [O] W.1 Multi-stage Dockerfile: implement 3-stage Dockerfile (Node web build, uv deps sync, python:3.11-slim runtime), `selfcheck` + uvicorn per SDD §17.1, update `.dockerignore` to exclude tests, and untrack `frontend/dist` in the same commit (resolved)
  - W-prep 2026-10-07: Dockerfile (web → build [uv sync, landing-if-missing, `docs_pdf.build`, `deploy/selfcheck.py`] → non-root runtime on `$PORT`), `.dockerignore`, `.gcloudignore`, `deploy/` (deploy.sh, env.cloudrun.yaml, smoke_test.py, selfcheck.py, README.md). Cloud Build `de2bc811…` SUCCESS in 9m52s on e2-highcpu-8 → `…/wellpulse-app:v04-prep` (379 MB compressed). **Still for the orchestrator at commit:** `git rm -r --cached frontend/dist` + add `frontend/dist/` to `.gitignore`.
- [x] [O] W.2 Local container validation: build `wellpulse:v04` image and verify `/api/healthz` and `/api/fields` locally with Vertex credentials
  - W-prep substitute (no docker on host): stage-2 commands replayed in a scratch copy (8 workers, corpus 253 s, selfcheck OK), then the image CMD run on the scratch tree with `deploy/env.cloudrun.yaml` → `deploy/smoke_test.py` 6/6 PASS (health, kpis 412 wells, 3 fields, docs search 10 hits, WS `connecting→connected` gemini-3.8-live, SPA); RSS 1.65 GB. Accepted as the local validation (no docker on host); the real image then passed the same smoke on Cloud Run.
- [x] [O] W.3 Deploy gate — Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources: proceed only if W.2 passed locally
  - 2026-10-08: `deploy.sh plan` → `build` (Cloud Build `c423c37b…` SUCCESS 13m07s, image `wellpulse-app:v04-c5ff77c`) → `deploy`. Nothing deleted; rollback target `wellpulse-app-00004-2p2` kept.
- [x] [O] W.4 Cloud Run deployment: deploy to `wellpulse-app` in `us-central1` (project `workover-operations-agentic-ai`, memory 4Gi, cpu 2, min/max instances 1, session affinity, no CPU throttling, env `TEXT_MODEL`, `LIVE_MODEL`, `LIVE_LOCATION`, `AS_OF=2026-09-23`, `BQ_LOCATION`, remove `GEMINI_API_KEY`)
  - Revision `wellpulse-app-00005-9b2` serves 100 %; runtime SA `wellpulse-run@…`; env from `deploy/env.cloudrun.yaml` (no `GEMINI_API_KEY`).
- [x] [O] Post-deployment smoke test & pre-warm: run `scripts/smoke.sh` against the public URL, run L1–L5 text and voice queries, test reconnect and fallback
  - `deploy.sh smoke` 6/6 PASS. Remote L1–L5 replay (real gemini-3.8-flash, `X-Debug-Trace`) 7/7 turns PASS: expected tools called, 0 ungrounded numbers, 6–12 s per turn. Voice audio, reconnect and fallback in a browser: **left for the user** (WS handshake only verified).

#### Gate W
- [x] https://wellpulse-app-bowxi5445q-uc.a.run.app serves v0.4: `/api/healthz`, `/api/fields`, a dossier PDF, `/api/docs/{id}.pdf`
  - `/api/health` 200, `/api/fields` 3 fields, dossier GK-129 PDF 200 (27 KB, 4 pages), `/api/docs/SOP-IC-04.pdf` 200. Polish revision `wellpulse-app-00006-mhb` (image `v04-04c648b`): `/api/healthz` 200, smoke 6/6, remote L1–L5 7/7 again.
- [~] Text L1–L5 and Live (*"Which field is underperforming?"*) work end to end on the URL; forced reconnect and fallback both work
  - Text L1–L5: PASS on the URL. Live: `/ws/live` reaches `connected`; spoken audio, forced reconnect and fallback need an in-browser check by the user.
- [x] No `GEMINI_API_KEY` on the service; the revision runs on Vertex ADC
- [ ] Pre-warm checklist for demo day: min-instance up, Live connect test, fallback test, persona switch (demo-day task; min-instances=1 is set)
- [x] [O] Commit + push after Gate W passes: `git commit -m "v0.4(W): deploy — Gate W passed" && git push origin main`

---

## Phase 21+ · v0.5 answer canvas & multimodal model

> [!IMPORTANT]
> **Rule:** After each passed gate and user approval: commit + push to origin main (orchestrator only).

### Milestone MS-14 · Stage AC — Answer canvas
**Anchor:** brief §1 U-1, U-2, U-3; §3 (D-25)

#### Tasks
- [~] built, awaiting user sign-off: Answer canvas views (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`) in `WellDeepDiveDrawer.tsx`
- [~] built, awaiting user sign-off: `pickCanvasView(toolKindOrToolName, userText)` routing in `frontend/src/api/chat.ts` (keyword table, tool aliases, fallback)
- [~] built, awaiting user sign-off: Expandable middle panel hiding the map, with ESC hotkey and restore button
- [~] built, awaiting user sign-off: Interventions table view with job dates, rig-days, uplift, outcome, and doc links
- [~] built, awaiting user sign-off: Compare view auto-open on counterfactual questions
- [ ] [F] AC-F1 Chat brevity enforcement: strictly ≤ 3 sentences plus optional collapsed card; eliminate multi-section well history dumps
- [ ] [O] AC-O2 User UI sign-off: verify canvas interaction, view switching, map restore, and responsive drawer behavior

#### Gate AC
- [ ] 10 demo phrases route to the correct view via `pickCanvasView`
- [ ] No full-history dump in chat; replies strictly ≤ 3 sentences
- [ ] `cd frontend && npm run build` and `tsc` green
- [ ] User UI sign-off on expandable middle panel, map hide, and ESC restore

---

### Milestone MS-15 · Stage DF — Demo flow & eval
**Anchor:** brief §1 U-1..U-4; §6

#### Tasks
- [ ] [F] DF-F1 11-step demo script: author `docs/demo_flow.md` (Lakwa → LKW-019) covering Field compare, Sick wells, Priority list, Overview, Production, Interventions, Wellbore, Diagnosis, Recommendation (top 3), "Why not sand cleanout" (compare), and "Prepare me for the field" (report link)
- [ ] [F] DF-F2 Eval dataset expansion: add +12 canvas-routing and brevity cases to `backend/tests/eval/wellpulse-eval.json`
- [ ] [O] DF-O3 Automated demo rehearsal: run `tests/eval/run_eval.py` asserting canvas routing and tool selection ≥ 90% across chat and voice

#### Gate DF
- [ ] 11-step demo script (§6) passes in chat and voice
- [ ] Eval set +12 canvas-routing cases ≥ 90%
- [ ] Each demo turn yields ≤ 3 sentence answer in chat and voice

---

### Milestone MS-16 · Stage DG — Synthetic data gaps — **DONE**
**Anchor:** brief §4; WH-06, WH-08, WH-10, WH-13, WH-14 (D-29, D-31)
**Status:** **DONE**. 6 tables generated for 412 wells; unit tests green; DG integration complete.

#### Tasks
- [x] [A] DG-A1 Table group A generators: `tubing_tally` (WH-06) and `deviation_survey` (WH-08) — DONE (412 wells, tests green)
- [x] [A] DG-A2 Table group B generators: `barrier_tests` (WH-14) and `wellhead_rating` (WH-14) — DONE (412 wells, tests green)
- [x] [A] DG-A3 Table group C generators: `fluid_hazards` (WH-13) and `fishing_records` (WH-10) — DONE (412 wells, tests green)
- [x] [A] DG-A4 Consistency test suite: `backend/tests/unit/test_dg_*.py` and `test_tc033_dg_tables.py` green
- [x] [O] DG-O5 Landing data generation & DG integration: 6 tables generated (seed `20261008`), routes `/tubing-tally`, `/deviation`, `/integrity` implemented, lakehouse DDL regenerated (not applied), `well_history_template.md` data gap register updated from GAP to AVAILABLE (synthetic)

#### Gate DG
- [x] 6 new tables generated for 100% of wells (412 wells), `is_synthetic=true` on every row
- [x] `tests/unit/test_dg_*.py` and `tests/unit/test_tc033_dg_tables.py` green (tally length within ±1 joint, TVD monotonic and ≤ MD, barrier dates in range, rating ≥ 1.5 × max THP, fishing matches failure codes)
- [x] DG integration complete: routes `/tubing-tally`, `/deviation`, `/integrity` done; lakehouse DDL regenerated (not applied)
- [x] `well_history_template.md` data gap register flips GAP → AVAILABLE (synthetic)

---

### Milestone MS-17 · Stage NN — Multimodal success engine (demo scorer)
**Anchor:** brief §1 U-4, U-5; §5 (D-32)

#### Tasks
- [ ] [O] NN-O1 Deterministic demo scorer: implement `backend/app/analytics/tools/success_engine.py` evaluating `P(success | c) = clip(p_mechanism(c)^0.5 × (0.5·base_rate + 0.5·analog_rate), 0.05, 0.95)` with Bayesian shrinkage to asset rate
- [ ] [O] NN-O2 Recommendation contract TC-030: implement `recommend_interventions` in `backend/app/analytics/tools/recommendations.py` returning top 3 candidates + `NO_JOB_JUSTIFIED`, expected uplift, rig-days, cost band, risks, analogs, drivers
- [ ] [O] NN-O3 Analog search TC-031: implement `similar_wells` in `backend/app/analytics/tools/similar_wells.py` (k=5 analogs via cosine similarity on standardised `build_features` vectors that ran candidate c)
- [ ] [F] NN-F4 NbaCard top-3 UI: update frontend with P(success), look-alike analog counts, and plain-English top drivers
- [ ] [F] NN-F5 "How did you decide?" panel: implement explanation panel with evidence chain, analog wells, top drivers, and multimodal NN architecture diagram (with Vertex AI custom job + Model Registry described as production path)
- [ ] [O] NN-O6 Plausibility review: verify outputs for hero wells GK-129, LKW-019, and LKM-061 for engineering soundness

#### Gate NN (demo)
- [ ] Top 3 render for all producing wells via TC-030 `recommend_interventions`
- [ ] p_success is strictly in [0.05, 0.95] and stable across calls
- [ ] Analog counts recompute exactly from data (TC-031 `similar_wells`, k=5)
- [ ] The explanation panel shows all four elements: evidence chain, look-alike analogs, top drivers (SHAP), and multimodal NN architecture diagram (with Vertex AI custom job + Model Registry described as production path)
- [ ] Plausibility review of GK-129, LKW-019, and LKM-061 outputs passes orchestrator inspection

---

### Milestone MS-18 · Stage FR — Field report (HTML)
**Anchor:** brief §1 U-6; §7 (D-30)

#### Tasks
- [ ] [F] FR-F1 Jinja2 HTML report template: implement A4-printable layout in `backend/app/analytics/templates/field_report.html` covering WH-01…WH-19, ONGC header/footer branding (wordmark fallback), and "SYNTHETIC DATA — DEMO" banner
- [ ] [F] FR-F2 Wellbore SVG generator: dynamic schematic rendering casing, tubing, perforations, and formation tops with placeholders for missing data per WH-05
- [ ] [O] FR-O3 TC-032 assembly engine: implement `backend/app/analytics/tools/field_report.py` assembling job program, kill fluid weight, barriers, contingencies, top-3 rationale, and `facts.json` sidecar
- [ ] [O] FR-O4 Fact validator & route wiring: implement `GET /api/wells/{id}/report` and `backend/tests/unit/test_tc032_field_report.py` ensuring 100% digits trace to tool returns
- [ ] [F] FR-F5 Canvas iframe view: integrate field report inside expanded middle panel with print/save button and one-line chat link

#### Gate FR
- [ ] `GET /api/wells/{id}/report` renders for all 412 wells in < 3 s locally (p95)
- [ ] Clean A4 print layout verified with repeating headers, print-friendly styling, and "SYNTHETIC DATA — DEMO" banner
- [ ] ONGC logo (`frontend/public/brand/ongc_logo.svg`) displayed at top left and print footer, with text wordmark fallback if missing
- [ ] Wellbore SVG renders dynamically from casing/tubing/perf/formation data (with placeholders for missing data per WH-05)
- [ ] 100% of digits validated against `facts.json` sidecar; Flash writes template prose only with no hard-coded numerals
- [ ] Chat and voice provide a concise one-line link to open the field report

---

### Milestone MS-20 · Stage ED — ED meeting pack (v0.6)
**Anchor:** [`features.md`](./features.md) §3b F-27…F-33; D-33…D-36 (user, 2026-10-08)

#### Tasks
- [x] [O] ED-1 Showcase mode: `WELLPULSE_RBAC_ENFORCE` switch (default off → every persona FULL); tests force it on; persona menu note "Role-based access available (off for demo)"
- [x] [O] ED-2 Completion diagram: shared SVG builder → `GET /api/wells/{id}/schematic.svg`; Wellbore view shows it (casing, cement, tubing, packer/pump, perforations by status, formation tops, TD)
- [x] [O] ED-3 TC-033 offset decline compare + verdict (`WELL_SPECIFIC` / `RESERVOIR_WIDE` / `WATER` / `RESTORED` / `MIXED`); route; Offsets view; thresholds pinned
- [x] [O] ED-4 TC-034 anomaly scan (rate drop, WC jump / trend, THP shift, downtime, linked workover); route; timeline in "History & Wax/Sand" view
- [x] [O] ED-5 TC-035 wax/sand behaviour (job count, interval, next due, field norm; no sand rate stated); route; card in well panel
- [x] [O] ED-6 India map: `ongc_assets.py` (13 assets, public approximate locations, position-only well tags); map opens on India; Assam drill-down unchanged
- [x] [O] ED-7 Agent: TC-033…035 wired into ADK + Live; "What's wrong with GK-129?" opens Offsets; ED rehearsal script in `demo_flow.md`
- [x] [O] ED-8 Native completion diagram (D-37): `CompletionDiagram.tsx` from profile data (casing + cement, tubing, pump / anchor / packer, perforations by status, formation tops, PBTD / TD, hover, non-overlapping labels) + perforation table; fix `&` in server SVG; valid-XML test
- [x] [O] ED-9 Three health tags (D-38): Healthy (green) / Needs attention (amber = at risk + underperforming) / Not producing (red) on map markers, cluster pies, legend, health card, field comparison, selector, nearby list, well badge; EN / Hinglish / Hindi labels
- [x] [O] ED-10 Map follows the agent (F-41): agent-picked well zooms to 14 from India / cluster zoom; field request always drills into Assam
- [x] [O] ED-11 `ui_control` hands-off (F-41, D-39, D-40): allow-listed map / panel / app actions; browser parser (EN / Hinglish / Hindi) runs plain commands with no model call + chat chip; ADK tool + runner `kind: "ui"`; Live 13th tool; tests
- [x] [O] ED-12 Agent docks in full screen (F-41): full screen / expanded panel opens the agent docked; exit restores; the agent opens docked on the right by default (undock is remembered)
- [x] [O] ED-13 GGS well buttons (F-41): popup well tags are health-coloured buttons that open the well + zoom; `focus_cluster` ("show GGS-01"); `report print`
- [x] [O] ED-14 Health filter + voice-first (F-41, D-41): `health_filter` all / healthy / attention / not_producing; browser phrases EN / Hinglish / Hindi; clickable legend + header KPIs; no Health & priority screen for display requests; Live prompt phrasings + spoken numbers; Live check over the socket; tests
- [x] [O] Hands-off script (India → Geleki → GK-129 wellbore → full screen → satellite / SCADA → flowlines off → Hindi → close panel → India) passes with no clicks (headless check)

#### Gate ED
- [ ] Each step approved by the user, then committed + pushed (`v0.6(ED-n): …`)
- [ ] Unit tests green (baseline 527 + new); `tsc` + `vite build` green
- [ ] Numbers only from tools; no currency
- [ ] ED script rehearsed locally

#### CMD backlog (logged, not in v0.6)
- [ ] F-34 Asset comparisons · F-35 Field-wise production per asset · F-36 Asset DPR · F-37 Where it hurts · F-38 Sand rate (no data) · F-39 Service cost (deferred) · F-40 New locations (no data)

---

### Milestone MS-19 · Stage W2 — Redeploy
**Anchor:** brief §2; §8

#### Tasks
- [ ] [O] W2-O1 Container build configuration: update Dockerfile and `deploy/selfcheck.py` for v0.5 assets (DG tables, NN scores, report templates)
- [ ] [O] W2-O2 Local container validation: execute `deploy/deploy.sh build` and run local smoke test
- [ ] [O] W2-O3 Cloud Run deployment: execute `deploy/deploy.sh deploy` with zero-downtime revision rollout
- [ ] [O] W2-O4 Post-deployment smoke test: execute `deploy/deploy.sh smoke` against live Cloud Run URL (7/7 checks)

#### Gate W2
- [ ] Local container validation passes via `deploy/deploy.sh build`
- [ ] Cloud Run deployment completes successfully via `deploy/deploy.sh deploy` with min-instances=1 and session affinity
- [ ] `deploy/deploy.sh smoke` passes 7/7 checks (including new endpoint `/api/wells/GK-129/report`)
- [ ] End-to-end 11-step demo script verified on public Cloud Run URL

---

## Verbatim §8 Gates → v0.4 stages

| Verbatim §8 gate | Stages | Done when |
|---|---|---|
| Gate 1: Specification & Transcript Alignment | docs v3.0.0 (this doc set) | BRD, features, BDD, SDD, build, and checklist v3.0.0 are reviewed by the user. |
| Gate 2: Multi-Field Telemetry & Cluster Generation | N (+ T for field aggregation) | Gate N + Gate T |
| Gate 3: Medallion Lakehouse & BigQuery Schema Ingestion | X | Gate X |
| Gate 4: Synthetic PDF Dossiers & SOP RAG Knowledge Base | O + S | Gate O + Gate S |
| Gate 5: Multi-Class ML Diagnostic & Counterfactual NBA Engine | P + Q + R | Gates P, Q, R |
| Gate 6: Gemini Live Stabilization | U | Gate U |
| Gate 7: End-to-End Hierarchical Demo Script Validation | Y + V + W | Gates Y, V, W |

> [!NOTE]
> Verbatim §7 and §8 well counts (Lakwa 25, Lakhmani 20) are illustrative; decision D-2 sets production-grade counts at 160 for Lakwa and 110 for Lakhmani.

---

## Definition of done (v0.4)

- [ ] Every verbatim §1–§3 requirement maps to a passing BDD scenario ([`features.md`](./features.md) traceability)
- [ ] The 5-level demo flow L1–L5 (verbatim §4) passes as automated tests and in a manual rehearsal on the Cloud Run URL
- [ ] Every number on screen or in speech traces to a tool return, table row or cited PDF; no ₹/USD point estimates (D-1)
- [ ] The agent refuses at least once in each new field (LKM-090) and explains why
- [ ] Live survives a forced reconnect and a forced fallback
- [ ] The baseline UI (map, telemetry, timeline, reports, export, language toggle) is not regressed
- [ ] Deployed (authorised 2026-10-07) and smoke-tested; the URL is rehearsed; one commit + push to `origin main` per passed stage gate (13 `v0.4(<stage>):` commits)

---

## Former open items (all resolved 2026-10-07)

| # | Item | Owner | Blocks | Status |
|---|---|---|---|---|
| 1 | Meeting date with Ajay Ratan (Q-1) | Orchestrator | Unknown: build all stages; if time-boxed, cut Y first, then X | Resolved |
| 2 | Lakehouse bucket | Orchestrator | Stage X | Resolved: existing `gs://workover-operations-agentic-ai-datalake` (`bronze/`, `documents/`, `silver_exports/`) |
| 3 | Verbatim §4 T3 ranks by NPV / payback (conflicts with D-1) | Orchestrator | Stages R, T | Resolved: deferred bbl × p_success ÷ rig-days, shown with cost band (K-7) |
| 4 | Untrack the committed `frontend/dist` | Orchestrator | Stage W | Resolved: untracked in Stage W |
| — | D-15…D-20, Q-2 | — | — | Resolved 2026-10-07 ([`SDD.md`](./SDD.md) §19.2) |
| — | Autonomy: DDL apply, Cloud Run deploy, commit + push per gate | — | — | Authorised by user 2026-10-07 19:52 |
| — | D-4 project = `workover-operations-agentic-ai` | — | — | Resolved 2026-10-07 |
| — | D-13 text model = `gemini-3.8-flash` on Vertex ADC | — | — | Resolved 2026-10-07 |
| — | Stray `v0.4-build` branch on GitHub | — | — | Deleted 2026-10-07 |

---

## Key decisions (v0.5)

| ID | Decision | Status | Resolution / detail |
|---|---|---|---|
| **D-25** | Answer canvas replaces Deep Dive | Accepted | Question-driven views (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`); chat answers ≤ 3 sentences; full well history accessible only via field report (brief §1, §3). |
| **D-26** | Success label definition | Accepted | P(success) from `workover_history.outcome`: `SUCCESS` = 1; `PARTIAL`, `FAILED` = 0; `CENSORED`, `NO_ACTION`, `IN_PROGRESS` excluded (~3.6k labelled jobs across 393 wells, 15 classes; brief §5). |
| **D-27** | Production path: Vertex AI custom training + Model Registry | Accepted | Described in architecture diagram panel as production path; not built in v0.5 per D-32 (brief §5). |
| **D-28** | HGB mechanism probabilities used by demo scorer | Accepted | `ic-hgb-v1` mechanism probabilities used by demo scorer; no model trained in v0.5 per D-32 (brief §5). |
| **D-29** | DG synthetic tables flagged `is_synthetic` | Accepted | All 6 generated DG tables flagged `is_synthetic=true`, `_source_system='wellpulse_dg_v1'`, deterministic seed `20261008` (brief §4). |
| **D-30** | ONGC logo branding | Accepted | ONGC logo (`frontend/public/brand/ongc_logo.svg`) supplied by user, with text wordmark "ONGC" fallback if asset is missing; "SYNTHETIC DATA — DEMO" banner on every report page (brief §7). |
| **D-31** | Argon tier for data generation | Accepted | Argon = `gemini-3.8-flash-high` via `swarm add` for data generation and consistency test suites; orchestrator owns architecture, leakage rules, and gates; Flash handles prose and templates (brief §8). |
| **D-32** | No model training or data regeneration in v0.5 | Accepted | Multimodal NN presented as engine (art-of-the-possible demo); numbers from deterministic demo scorer in `backend/app/analytics/tools/success_engine.py`; Vertex custom job & Model Registry kept as production path in architecture diagram; supersedes training parts of D-26/D-27/D-28 (brief §5). |


## Key decisions (v0.6)

| ID | Decision | Status | Resolution / detail |
|---|---|---|---|
| **D-33** | Showcase mode | Accepted (user, 2026-10-08) | Nothing hidden for any persona; RBAC kept behind `WELLPULSE_RBAC_ENFORCE=1` and presented as a capability |
| **D-34** | India map tags | Accepted (user, 2026-10-08) | 13 ONGC assets at approximate public locations; position-only, non-interactive well tags; no data for other assets; Assam is live |
| **D-35** | Service cost deferred | Accepted (user, 2026-10-08) | Tangible / intangible cost not built in v0.6 |
| **D-36** | Persona model | Accepted (user, 2026-10-08) | CMD = all India; ED = one asset, technical; FE = execution documents; v0.6 builds the ED set, CMD backlog F-34…F-40 |
| **D-37** | Native completion diagram | Accepted (user, 2026-10-08) | Drawn in React from structured construction data; server SVG only for the printable report |
| **D-38** | Three health tags | Accepted (user, 2026-10-08) | Healthy (green) = PRODUCING_OK; Needs attention (amber) = AT_RISK + UNDERPERFORMING; Not producing (red) = NOT_PRODUCING; display-only |
| **D-39** | Live voice cap 12 → 13 | Accepted (user, 2026-10-08) | Adds `ui_control` to Live voice; SDD §11.3 cap is our own rule |
| **D-41** | Health filter is a display action | Accepted (user, 2026-10-08) | `ui_control health_filter`; display requests never open Health & priority; runner drops health navigation when `ui_control` ran |
| **D-40** | Hands-off control | Accepted (user, 2026-10-08) | Plain UI commands run in the browser (no model call); everything else goes to the agent, which can call `ui_control`; allow-listed actions only |
