# Implementation & Verification Checklist (`checklist.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 3.0.0 (v0.4 verbatim expansion)  
**Date:** 2026-10-07  
**Status:** Phases 1-7 done (baseline); Phase 8+ (v0.4) in progress — see ticks below  
**Companion Docs:** [`build.md`](./build.md) · [`verbatim.md`](../verbatim.md) · [`BRD.md`](./BRD.md) · [`features.md`](./features.md) · [`BDD.md`](./BDD.md) · [`SDD.md`](./SDD.md) · [`DELEGATION.md`](./DELEGATION.md) · [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md)  
**Autonomy:** Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources. A gate that fails 3 times is marked **BLOCKED** here and independent stages continue; never fake a gate; never change the model.  
**User rule:** "During the build, do a git commit and push to origin main after every major milestone (each passed stage gate)."  
**Legend:** `[O]` = orchestrator (Opus/Pro), `[F]` = Gemini Flash worker (lands only after its deterministic gate passes and `[O]` reviews it).

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
- [ ] [F] N-F1 Port generator modules and `train.py` boilerplate from `${ADK_REPO}` with import rewrites into `backend/app/analytics/generator/` and `backend/app/analytics/model/train.py`
- [ ] [O] N.1 FieldConfig and field modules: implement `backend/app/analytics/generator/fields/{__init__.py, geleki.py, lakwa.py, lakhmani.py}` with fixtures (LKW-047, LKW-088, LKW-112, LKM-023, LKM-061, LKM-090) and new tables in `{hierarchy.py, construction.py, operations_events.py, targets.py}` (incl. `pressure_surveys`, `formation_tops`, D-19)
- [ ] [O] N.2 Catalogue and labels (K-1, K-2): add `GLV_REPLACE` and `cost_band` to `job_catalogue`; add `catalogue_job_code` and `intervention_class` (IC-01…IC-15) to `workover_history`
- [ ] [O] N.3 Telemetry columns (D-19): add `wht_degc`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2` (GOR = `gor_scf_bbl`; SPM for SRP), plus append-only `pressure_surveys` and `formation_tops`
- [ ] [O] N.4 Repository layer: implement `backend/app/data_access/{repository.py, parquet_repo.py, adapters.py}`, update `backend/app/api/wells.py` to read from repository, and deprecate/delete `backend/app/services/data_generator.py`
- [ ] [F] N-F2 Frontend type and label updates: update `frontend/src/types/well.ts` and `frontend/src/components/timeline/WorkoverTimeline.tsx` (replace `cost_usd` with `cost_band` + `rig_days`)
- [ ] [O] N.5 Generation and validation: generate 60-month dataset (2021-10-01 to 2026-09-30) for all fields, validate V-N1..V-N7 and baseline comparison, verify CoxPH model training
- [ ] [O] N.6 Pin design targets: run `pin_targets.py` to generate `docs/pinned_values.md` and replace `«target ± tol»` placeholders in `BDD.md`

#### Gate N
- [ ] Validator 0 violations for Geleki, Lakwa and Lakhmani; well counts 142 / 160 / 110
- [ ] Geleki's pre-existing columns are hash-identical to `landing_v030`; the Geleki join at the prepend boundary is continuous (±3%)
- [ ] All fields cover 2021-10-01 → 2026-09-30, and two runs produce byte-identical parquet (reproducible; fixes the `now()` defect)
- [ ] CoxPH C-index reproduces 0.7128 with the prepend excluded (Gate E)
- [ ] Every IC-01…IC-15 has ≥ 30 `workover_history` rows; `GLV_REPLACE` exists
- [ ] Lakwa gap vs. target inside −18% ± 3 pp; LKW-047 has 41 `WAIT_ON_RIG` days and 12 `WAIT_ON_MATERIAL` days
- [ ] `wht_degc`, `gor_scf_bbl`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2` present; `pressure_surveys` and `formation_tops` populated (verbatim WS6, D-19)
- [ ] `test_api_shapes.py` green against the repository (React UI unchanged except for the N-F2 cost-band fields); `npm run build` green
- [ ] No `cost_usd` remains in API responses (D-1)
- [ ] `docs/pinned_values.md` written; BDD targets replaced
- [ ] [O] Commit + push after Gate N passes: `git commit -m "v0.4(N): data foundation v2 — Gate N passed" && git push origin main`

---

### Phase 10 · Stage O — PDF corpus + SOPs
**Verbatim anchor:** §1 *"generate the documents of PDF files of… well interventions"*; §3 *"The SOPs"*

#### Tasks
- [ ] [O] O-O1 Fact-slot framework: implement `backend/app/analytics/generator/docs_pdf/{facts.py, render.py, scanify.py, validate.py, index.py}`, fact-slot schemas, and API routes in `backend/app/api/docs.py` (`GET /api/docs/{doc_id}.pdf`, `GET /api/wells/{id}/documents`)
- [ ] [F] O-F1 D1 Well Completion Report (WCR) generator template
- [ ] [F] O-F2 D2 Workover Completion Report generator template
- [ ] [F] O-F3 D3 Daily Workover Shift Log (DWR) generator template
- [ ] [F] O-F4 D4 Well Completion Schematic generator template
- [ ] [F] O-F5 D5 Cement Bond Log (CBL) survey generator template
- [ ] [F] O-F6 D6 Chemical Treatment Log generator template
- [ ] [F] O-F7 D7 Well Test Report generator template
- [ ] [F] O-F8 D8 Root Cause Analysis (RCA) report generator template
- [ ] [F] O-F9 D9 Field Study Report generator template
- [ ] [F] O-F10 D10 Monthly Field Performance Report generator template
- [ ] [F] O-F11 D11 SOP library generator template (IC-01…IC-14)
- [ ] [F] Hero narrative prose drafting for GK-129, LKW-047, LKW-112, LKM-090 (reviewed by [O])
- [ ] [O] UI document integration: update `frontend/src/components/reports/WellReportsTab.tsx` to consume document index while keeping the JSON export
- [ ] [O] Corpus generation and validation: run `render --field all`, `scanify --fraction 0.10 --types D1,D5`, validate 100% facts, and build the TF-IDF index `backend/app/data/index/{doc_chunks.parquet, tfidf.pkl}` (D-17)

#### Gate O
- [ ] D1…D11 present for all 3 fields; every IC-01…IC-14 has an SOP (D11)
- [ ] Fact validation 100%; no digit in template prose outside a fact slot
- [ ] Every `document_index` row resolves; `GET /api/docs/{id}.pdf` returns `application/pdf`
- [ ] The scanned subset is flagged `has_text_layer=false` and is still retrievable
- [ ] GK-129 has the 1998 CBL (D5) and the 2019 failed water-shut-off report (D2)
- [ ] WellReportsTab shows real documents for the selected well; `npm run build` green
- [ ] Corpus size logged (target ≤ 200 MB, so it fits in the image)
- [ ] [O] Commit + push after Gate O passes: `git commit -m "v0.4(O): PDF corpus + SOPs — Gate O passed" && git push origin main`

---

### Phase 11 · Stage P — Analytics port + attribution + health
**Verbatim anchor:** §1 *"why did the production decline? Was it human factor, controllable factor"*; §1 *"which of the wells are doing okay… not producing now"*

#### Tasks
- [ ] [O] Deterministic tools port: port 18 deterministic tools (TC-001…TC-018) from `${ADK_REPO}/tools/` into `backend/app/analytics/tools/{common,arps_decline,chan_diagnostic,candidate_ranking,render_well_map}.py`, removing Geleki defaults (K-6)
- [ ] [O] Hierarchy helper: implement `field_of()` in `backend/app/analytics/tools/hierarchy.py`
- [ ] [O] TC-019 decline attribution: implement `backend/app/analytics/tools/attribution.py` and `backend/app/analytics/config/factor_map.yaml`
- [ ] [O] TC-020 data-driven health engine: implement `backend/app/analytics/tools/health.py` and wire into `backend/app/api/wells.py` (`/api/wells/kpis` and well status)
- [ ] [F] P-F1 Unit-test scaffolds from TC signatures for tools port, TC-019 attribution, and TC-020 health

#### Gate P
- [ ] All 18 ported tools pass the ADK contract tests (ported to `tests/unit/test_tools_port.py`); no `GK-129` / `Geleki` defaults remain (K-6)
- [ ] The attribution waterfall sums to the total loss within 0.5% for every well in all 3 fields
- [ ] LKW-047's largest class is `HUMAN_PROCESS`; LKM-090 is ≥ 80% `SUBSURFACE`; LKW-088 shows `EXTERNAL` (`GRID_POWER_OUTAGE`)
- [ ] TC-020 buckets come from data; `random.seed(42)` status removed; `/api/wells/kpis` = TC-020 counts
- [ ] Geleki trigger results are unchanged from the ADK baseline
- [ ] [O] Commit + push after Gate P passes: `git commit -m "v0.4(P): analytics port + attribution + health — Gate P passed" && git push origin main`

---

### Phase 12 · Stage Q — ML intervention classifier
**Verbatim anchor:** §1 *"run a classification algorithm… 5 to 10… or 15 type of interventions"*

#### Tasks
- [ ] [O] Feature engineering: implement `backend/app/analytics/model/features.py` incorporating production telemetry, well history, and construction tables (casing, tubing, perforations) without data leakage
- [ ] [O] Classifier training pipeline: implement `backend/app/analytics/model/train_classifier.py` (multi-class IC-01…IC-15 with SHAP explainability), producing `backend/app/analytics/model/intervention_classifier_v1.pkl` and `intervention_classifier_metrics.json`
- [ ] [O] TC-021 classifier tool: implement `backend/app/analytics/tools/intervention_classifier.py`
- [ ] [O] Unit and leakage tests: implement `backend/tests/unit/{test_features_no_leakage.py, test_tc021_classifier.py}`

#### Gate Q
- [ ] Holdout **macro-F1 0.70–0.92**
- [ ] Top-3 accuracy ≥ 0.90
- [ ] Beats the TC-008 rule baseline by ≥ 0.05 macro-F1
- [ ] ECE ≤ 0.08
- [ ] Leakage test green (no post-event features); LKM-023 → IC-06, LKM-061 → IC-07
- [ ] Features include construction tables (casing, tubing, perforations) and prior-job history (verbatim §1)
- [ ] [O] Commit + push after Gate Q passes: `git commit -m "v0.4(Q): ML classifier — Gate Q passed" && git push origin main`

---

### Phase 13 · Stage R — Next best action + counterfactual
**Verbatim anchor:** §1 *"recommend what is the next best action"*; §3 *"Why are you recommending this against an alternative?"*

#### Tasks
- [ ] [O] TC-022 Next Best Action: implement `backend/app/analytics/tools/nba.py` with expected uplift, cost band, rig-days, risk profile, and SOP link (D11)
- [ ] [O] TC-027 Counterfactual defense: implement `backend/app/analytics/tools/counterfactual.py` evaluating reservoir pressure/IPR (row 1 uses `pressure_surveys`), historical efficacy, and cost-band/downtime delta; served by `GET /api/wells/{id}/compare?recommended=&alternative=`
- [ ] [O] Recommendations API refactoring: update `backend/app/services/ai_agent.py` (`generate_structured_recommendation` delegates to TC-022) and `POST /api/wells/{id}/recommendations`, replacing `estimated_cost_usd` with `cost_band` + `rig_days`
- [ ] [O] Unit tests: implement `backend/tests/unit/{test_tc022_nba.py, test_tc027_counterfactual.py}`

#### Gate R
- [ ] LKW-047 action 1 = `PUMP_OVERHAUL`; LKM-090 action 1 = `NO_JOB_JUSTIFIED`
- [ ] Hero GK-129: `compare_interventions(squeeze vs. wax removal)` returns the verdict, the deciding dimension and a cited prior-job document (D5 1998 CBL / D2 2019 WSO)
- [ ] The counterfactual covers the reservoir/IPR, historical-efficacy and cost-band + rig-days dimensions (verbatim §4 T5)
- [ ] A Chan-negative fixture yields `CHOKE_BACK` with `MODEL_PHYSICS_DISAGREEMENT`
- [ ] Priority ranking (`GET /api/fields/{field}/priority`) = deferred bbl × p_success ÷ rig-days, shown with the cost band (K-7)
- [ ] **No ₹, USD or payback point value** in any response (D-1); `grep -rn "estimated_cost_usd\|payback" backend/app` returns nothing
- [ ] Every action has a resolving `sop_doc_id` (D11) and SOP steps, unit type and duration band (verbatim §4 T5)
- [ ] [O] Commit + push after Gate R passes: `git commit -m "v0.4(R): NBA + counterfactual — Gate R passed" && git push origin main`

---

### Phase 14 · Stage S — Field-engineer dossier
**Verbatim anchor:** §1 *"aggregate all the history and give it to the person who is going to the field"*

#### Tasks
- [ ] [F] S-F1 Layout, styling, and 9 section templates (no digits) for the pre-job dossier PDF in `backend/app/analytics/tools/dossier.py`
- [ ] [O] TC-023 Dossier assembly: implement data assembly, fact tracing, and UNAVAILABLE fallbacks in `backend/app/analytics/tools/dossier.py`
- [ ] [O] Export route & UI integration: update `GET /api/wells/{id}/export` in `backend/app/api/wells.py` (JSON adds `pdf_url`; `?format=pdf` returns the PDF), add `POST /api/wells/{id}/dossier` (English-only, Q-2; lithology from `formation_tops`), and wire into `frontend/src/components/reports/WellReportsTab.tsx`
- [ ] [O] Unit tests: implement `backend/tests/unit/test_tc023_dossier.py`

#### Gate S
- [ ] 2–4 pages, ≤ 10 s, all 9 sections, including lithology and casing/tubing tallies (verbatim WS4)
- [ ] Every number traces to a table or tool return; missing sections render `UNAVAILABLE — <table>`
- [ ] GK-129 cites the 1998 CBL and the 2019 WSO
- [ ] The JSON export still works (baseline FEAT kept)
- [ ] [O] Commit + push after Gate S passes: `git commit -m "v0.4(S): dossier — Gate S passed" && git push origin main`

---

### Phase 15 · Stage T — Asset view & drill-down
**Verbatim anchor:** §1 *"Which particular field is not performing?"*; §3 *"Can you give me a plot?"*, *"drill down to one particular well"*, *"information of nearby wells"*

#### Tasks
- [ ] [O] Field analytics tools: implement `backend/app/analytics/tools/{field_performance.py (TC-024, TC-028), hierarchy.py (TC-025), well_profile.py (TC-029)}` and TC-017 v2 job markers
- [ ] [O] Fields REST API: implement `backend/app/api/fields.py` (`GET /api/fields`, `/api/fields/history?fields=`, `/api/fields/{field}/history`, `/api/fields/compare?period=`, `/api/fields/{field}/health?cluster_id=`, `/api/fields/{field}/attribution?window_days=`, `/api/fields/{field}/priority`) and in `wells.py` `/api/wells/{id}/profile`, `/api/wells/{id}/production` (markers + WHT / GOR / gas-lift series)
- [ ] [F] T-F1 Boundary geodata: create synthetic GeoJSON boundaries for Geleki, Lakwa, Lakhmani and GGS clusters in `backend/app/data/geodata/` (D-3)
- [ ] [F] T-F2 Recharts visualization components: implement `frontend/src/components/field/{FieldHistoryChart.tsx, FieldComparisonTable.tsx, AttributionWaterfall.tsx, HealthBucketsCard.tsx, PriorityQueueTable.tsx}` and `components/well/NbaCard.tsx`
- [ ] [F] T-F3 Screen scaffolding & integration: implement `frontend/src/components/common/FieldSelector.tsx`, `components/well/{WellDeepDive.tsx, NearbyWellsTable.tsx, CounterfactualTable.tsx}`, and update `TelemetryCharts.tsx` with job markers, WHT, GOR and gas-lift injection rate + pressure
- [ ] [O] Unit and contract tests: implement `backend/tests/unit/{test_tc024_fields.py, test_tc025_hierarchy.py, test_tc028_field_history.py, test_tc029_well_profile.py}`

#### Gate T
- [ ] `compare_fields` ranks Lakwa worst, inside the pinned band, with a controllable top driver; the rows include target, uptime, water cut and `active_interventions` counts (TC-024, verbatim WS1)
- [ ] TC-028 returns 60 monthly points per field for oil, water cut and gas; aggregation reconciles with well sums within 0.1%
- [ ] TC-029 returns formation, casing/tubing, lift type and ≥ 3 neighbours on the same cluster; TC-017 v2 shows all in-window job markers
- [ ] `TelemetryCharts` shows WHT, GOR and gas-lift injection rate + pressure from `GET /api/wells/{id}/production`
- [ ] UI: field selector, 5-year field chart, comparison, well deep-dive with markers and nearby wells all render from the APIs (no hard-coded values)
- [ ] `npm run build` green; Part I screens are not regressed
- [ ] [O] Commit + push after Gate T passes: `git commit -m "v0.4(T): asset view & drill-down — Gate T passed" && git push origin main`

---

### Phase 16 · Stage X — Medallion Lakehouse
**Verbatim anchor:** §3 *"showcase that in the Medallion architecture… Lakehouse"*; *"whether it should go ultimately into BigQuery or… a better database"*

#### Tasks
- [ ] [F] X-F1 Medallion DDL scripts: write BigQuery DDL schemas for Bronze, Silver, and Gold in `lakehouse/ddl/*.sql` (Silver partitioned by `production_date`, clustered by `field, well_id`; Silver `doc_chunks` mirror of the TF-IDF index, D-17)
- [ ] [F] X-F2 Bronze-to-Silver ETL loader: implement `lakehouse/load/bronze_to_silver.py` loading `gs://workover-operations-agentic-ai-datalake/bronze/` and `documents/` into BigQuery; exports to `silver_exports/`
- [ ] [F] X-F3 Dataform pipeline: create `lakehouse/dataform/` compiling and executing Silver-to-Gold aggregations (`field_kpi_monthly`, NBA features)
- [ ] [O] DDL apply — Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources: `bq query --dry_run` every DDL file, then apply; bucket = existing `gs://workover-operations-agentic-ai-datalake`
- [ ] [O] X-O4 Repository & parity: implement `backend/app/data_access/bigquery_repo.py`, integration parity test `backend/tests/integration/test_backend_parity.py` (`DATA_BACKEND=parquet|bigquery`), and production-store decision record in `SDD.md`

#### Gate X
- [ ] `wellpulse_bronze`, `wellpulse_silver` and `wellpulse_gold` exist in `asia-south1`; Silver `daily_production` is partitioned by `production_date` and clustered by `field, well_id`
- [ ] Silver row counts = Bronze; Gold `field_kpi_monthly` = TC-028 output
- [ ] Parquet vs. BigQuery parity test green; the app runs with `DATA_BACKEND=bigquery`
- [ ] Silver `doc_chunks` mirrors the TF-IDF index from D1–D11 (D-17; Vertex AI Search optional later, verbatim §5)
- [ ] Production-store decision record (BigQuery vs. alternatives) recorded in [`SDD.md`](./SDD.md) §15.2 (verbatim §3)
- [ ] [O] Commit + push after Gate X passes: `git commit -m "v0.4(X): medallion lakehouse — Gate X passed" && git push origin main`

---

### Phase 17 · Stage U — Real Gemini Live
**Verbatim anchor:** §1 *"Gemini Live is not working well… working very good in Drilling Intelligence 2.0"*

#### Tasks
- [ ] [O] Reference study: inspect `${DI2_REPO}/backend/app/agent/live_session.py`, `backend/app/api/ws_live.py`, `frontend/src/live/{liveClient,micCapture,audioPlayer}.ts`, and `docs/adr/ADR-003-gemini-live-adk-proxy.md`
- [ ] [O] Model verification (U.2): run live model verification script against Vertex AI in `us-central1` and write exact returned names into `backend/.env` (`TEXT_MODEL`, `LIVE_MODEL`, `LIVE_LOCATION`); if missing after 3 attempts, mark Stage U BLOCKED — never substitute
- [ ] [O] Live session engine: implement `backend/app/live/{session.py, voice_tools.py, live_prompt.md, fallback.py}` supporting resumption, context compression, session recap, and 3-failure fallback to text
- [ ] [O] Live WebSocket route: implement `backend/app/api/live.py` serving `WS /ws/live` (field/well context message); legacy `WS /api/wells/{id}/live` shim kept until Gate V (D-20)
- [ ] [F] U-F1 AudioWorklet client: implement `frontend/src/live/{liveClient.ts, micCapture.ts, pcm-worklet.js, audioPlayer.ts}` (16 kHz upload / 24 kHz playback)
- [ ] [F] U-F2 Voice UI state machine: update `frontend/src/components/agent/VoiceAgentPanel.tsx` with connection states (connecting, listening, speaking, fallback), remove browser `speechSynthesis`, retain language toggle, add open-mic hands-free option (audio-only)
- [ ] [O] Integration testing: implement `backend/tests/integration/test_ws_live.py` verifying reconnect, recap, and 3-failure fallback

#### Gate U
- [ ] The model names in `.env` come from the U.2 listing (output pasted into the commit message or PR)
- [ ] Spoken answer to *"Which field is underperforming?"*; first audio ≤ 2.5 s warm
- [ ] Barge-in ≤ 300 ms; a forced reconnect keeps context (resumption + recap); 3 failures → text fallback with a visible notice
- [ ] Spoken numbers equal tool returns (same functions as the text path)
- [ ] The language toggle still works; `speechSynthesis` is no longer used for Live replies
- [ ] Open-mic hands-free mode works; `FIELD_ENGINEER` persona can use Live voice
- [ ] Runs on Vertex ADC; `GEMINI_API_KEY` is not read anywhere (`grep -rn GEMINI_API_KEY backend/app` is empty)
- [ ] [O] Commit + push after Gate U passes: `git commit -m "v0.4(U): real Gemini Live — Gate U passed" && git push origin main`

---

### Phase 18 · Stage Y — RBAC + multi-field GIS
**Verbatim anchor:** §3 *"role-based access… Executive Director… versus a field engineer"*; §3 *"they can see different fields… and the wells"*

#### Tasks
- [ ] [O] Y-O1 RBAC policy engine: implement `backend/app/agent/rbac.py` (matrix in code) and `require()` checks in `backend/app/agent/adk_tools.py` in tool wrappers across `ED`, `ASSET_MANAGER`, and `FIELD_ENGINEER` personas
- [ ] [F] Y-F2 Persona UI & Multi-field Map: implement `frontend/src/components/common/PersonaPicker.tsx`, update `components/map/WellMap.tsx` (multi-field boundaries, GGS clusters, health colours, field filter, synthetic label per D-3, Esri basemap per D-5), and update `Header.tsx`
- [ ] [O] Unit and BDD tests: implement `backend/tests/unit/test_rbac.py` and BDD tests in `backend/tests/bdd`

#### Gate Y
- [ ] The same question as ED vs. FIELD_ENGINEER gives correctly scoped answers per verbatim §6; a direct denied tool call returns `UNAVAILABLE` (no data leak in the error)
- [ ] The map shows 3 fields with boundaries, GGS markers and a field filter; header counts = TC-020; the well drawer = TC-029
- [ ] Synthetic coordinates are labelled as synthetic on the map (D-3)
- [ ] Persona switch works in both text and Live
- [ ] [O] Commit + push after Gate Y passes: `git commit -m "v0.4(Y): RBAC + multi-field GIS — Gate Y passed" && git push origin main`

---

### Phase 19 · Stage V — Agent wiring & eval
**Verbatim anchor:** §3 *"do you see the hierarchy of question and answering?"* (5-level flow, §4 L1–L5)

#### Tasks
- [ ] [O] In-process ADK Runner: implement `backend/app/agent/{runner.py, adk_tools.py, prompt.py, callbacks.py}` wiring ~30 tool wrappers with strict numeric trace and anti-fabrication guardrails
- [ ] [O] Chat API refactoring: implement `backend/app/api/chat.py` (`POST /api/chat`), route per-well `/chat` and `/audio` to Runner, remove legacy `/api/wells/{id}/live` and `/audio` shims at the end of V (D-20), and delete prompt-stuffing and keyword fallback in `services/ai_agent.py`
- [ ] [F] V-F1 BDD Gherkin test suite: generate `backend/tests/bdd/features/*.feature` and step implementations for L1–L5 hierarchical conversation flow
- [ ] [F] V-F2 Agent evaluation dataset: build `backend/tests/eval/wellpulse-eval.json` (≥ 30 cases: every L1–L5 turn × 3 personas + refusals, all voice and text scenarios)
- [ ] [F] V-F3 Playwright E2E specs: implement `frontend/tests/e2e/*.spec.ts` for full UI click-through
- [ ] [O] Eval iteration & test execution: run pytest suite, run `agents-cli eval run` (tool selection ≥ 90%), and execute Playwright tests

#### Gate V
- [ ] All BDD scenarios green, including one automated test per demo turn L1–L5 (verbatim §8 M6)
- [ ] Eval tool-selection accuracy ≥ 90% on `tests/eval/wellpulse-eval.json` (≥ 30 cases); if it is lower, apply the SDD sub-agent split and re-run
- [ ] No answer contains a number missing from that turn's tool returns (number-trace test)
- [ ] The agent refuses at least once per new field (LKM-090 → no job justified) and explains why
- [ ] The prompt-stuffing code and the keyword fallback are removed; text runs on Vertex ADC with `gemini-3.8-flash` (D-13)
- [ ] Playwright: L1→L5 click-through passes against `npm run build` served by FastAPI
- [ ] Legacy `/api/wells/{id}/live` and `/audio` shims removed; `WS /ws/live` is the only Live route (D-20)
- [ ] [O] Commit + push after Gate V passes: `git commit -m "v0.4(V): agent wiring & eval — Gate V passed" && git push origin main`

---

### Phase 20 · Stage W — Deploy (authorised by user, 2026-10-07)
**Verbatim anchor:** derived: demo must run on the existing public URL

#### Tasks
- [ ] [O] W.1 Multi-stage Dockerfile: implement 3-stage Dockerfile (Node web build, uv deps sync, python:3.11-slim runtime), `selfcheck` + uvicorn per SDD §17.1, update `.dockerignore` to exclude tests, and untrack `frontend/dist` in the same commit (resolved)
- [ ] [O] W.2 Local container validation: build `wellpulse:v04` image and verify `/api/healthz` and `/api/fields` locally with Vertex credentials
- [ ] [O] W.3 Deploy gate — Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources: proceed only if W.2 passed locally
- [ ] [O] W.4 Cloud Run deployment: deploy to `wellpulse-app` in `us-central1` (project `workover-operations-agentic-ai`, memory 4Gi, cpu 2, min/max instances 1, session affinity, no CPU throttling, env `TEXT_MODEL`, `LIVE_MODEL`, `LIVE_LOCATION`, `AS_OF=2026-09-23`, `BQ_LOCATION`, remove `GEMINI_API_KEY`)
- [ ] [O] Post-deployment smoke test & pre-warm: run `scripts/smoke.sh` against the public URL, run L1–L5 text and voice queries, test reconnect and fallback

#### Gate W
- [ ] https://wellpulse-app-bowxi5445q-uc.a.run.app serves v0.4: `/api/healthz`, `/api/fields`, a dossier PDF, `/api/docs/{id}.pdf`
- [ ] Text L1–L5 and Live (*"Which field is underperforming?"*) work end to end on the URL; forced reconnect and fallback both work
- [ ] No `GEMINI_API_KEY` on the service; the revision runs on Vertex ADC
- [ ] Pre-warm checklist for demo day: min-instance up, Live connect test, fallback test, persona switch
- [ ] [O] Commit + push after Gate W passes: `git commit -m "v0.4(W): deploy — Gate W passed" && git push origin main`

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
