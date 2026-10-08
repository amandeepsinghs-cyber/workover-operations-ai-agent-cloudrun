# Build & Local Run Guide (`build.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 3.1.0 (v0.5 answer canvas & multimodal model) · **Date:** 2026-10-08
**Target Environment:** Local workstation (Linux, macOS, Windows WSL) and Cloud Run
**Requirements source:** [`verbatim.md`](../verbatim.md) and [`v05_change_brief.md`](./v05_change_brief.md). Companion docs: [`BRD.md`](./BRD.md) · [`features.md`](./features.md) · [`BDD.md`](./BDD.md) · [`SDD.md`](./SDD.md) · [`checklist.md`](./checklist.md)

> [!IMPORTANT]
> **This file has two parts.**
> - **[Part I](#part-i--run-wellpulse-today-baseline)** explains how to run the WellPulse that exists today (the v2 baseline). It has been corrected against the code as of 2026-10-07. The earlier ports 8000/8001/5173/5175 were wrong.
> - **[Part II](#part-ii--v04-verbatim-expansion-build)** is the build for v0.4 (Stages M…W) and v0.5 (Stages AC, DF, DG, NN, FR, W2), each with commands, owner and a gate, delivering every requirement in `verbatim.md` and `v05_change_brief.md`.
>
> **Citation rule.** Every Part II stage cites its verbatim anchor or v0.5 change brief: §, then a short quote. Anything without an anchor is marked **derived**, with the reason. The numbers in verbatim §4–§8 (GK-104, "+180 bopd", "₹18 Lakhs", "142 bar", "25 wells"…) are **illustrative only, not data**. Design targets look like «target ± tol» and are pinned after Stage N.

---

# Part I · Run WellPulse today (baseline)

## 1. Prerequisites

| Tool | Version | Check | Notes |
|---|---|---|---|
| Python | 3.11 (Docker uses `python:3.11-slim`) | `python3 --version` | 3.10+ works locally |
| Node.js / npm | 20.x LTS / 10.x | `node --version && npm --version` | Vite 5 needs Node 18 or later |
| `uv` | latest | `uv --version` | Not needed for Part I. **Required from Stage M onward** (D-14) |
| `gcloud` | latest | `gcloud --version` | Only for deploy or Vertex AI |
| Browser | Chrome or Edge, latest | — | MediaRecorder and Web Speech API |

## 2. Repository structure (as-is)

```
wellpulse/
├── archive/                 # legacy prototypes + LEARNINGS.md (excluded from Docker)
├── docs/                    # BRD, BDD, SDD, features, build (this), checklist, verbatim
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app; serves frontend/dist + router
│   │   ├── api/wells.py     # all REST + WS routes
│   │   ├── services/
│   │   │   ├── data_generator.py   # writes data/wells_data.json (50 GLK wells, 730 days)
│   │   │   └── ai_agent.py         # prompt-stuffing chat, keyword fallback, recommendations
│   │   └── data/wells_data.json    # 7.6 MB, generated
│   ├── requirements.txt     # pip (incomplete: missing `requests`, see §7)
│   └── run.py               # uvicorn launcher, default port 8002
├── frontend/                # React 18 + Vite 5 + Tailwind + Leaflet + Recharts
│   ├── src/{App.tsx, main.tsx, components/{agent,common,map,reports,telemetry,timeline}, types/well.ts}
│   ├── vite.config.ts       # dev port 5180, proxies /api → localhost:8002
│   └── dist/                # committed build, copied by the Dockerfile
├── Dockerfile               # single stage, python:3.11-slim (NOT multi-stage)
├── run_local.sh             # one-command launcher
└── README.md
```

> [!NOTE]
> The earlier version of this file listed `backend/app/core/`, `frontend/src/context/`, `frontend/public/` and `scripts/`. **None of these exist.**

## 3. Environment (`backend/.env`, optional)

```bash
GEMINI_API_KEY="..."        # optional today; if unset, the keyword fallback engine answers
BACKEND_HOST="0.0.0.0"
BACKEND_PORT=8002           # run.py default; PORT wins if set (Cloud Run sets PORT=8080)
```

> [!WARNING]
> Today `ai_agent.py` calls the **Generative Language REST API with an API key**, using model `gemini-3.8-flash`. Stage V moves the calls to **Vertex AI with ADC**, keeps the model name (decision D-13), and **removes `GEMINI_API_KEY`**.

## 4. Manual setup

```bash
# Terminal 1: backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt requests    # requests is imported by ai_agent.py but not listed
python app/services/data_generator.py       # only if app/data/wells_data.json is missing
python run.py                               # http://localhost:8002  (docs: /docs)

# Terminal 2: frontend
cd frontend
npm install
npm run dev                                 # http://localhost:5180  (proxies /api → :8002)
```

## 5. One command: `./run_local.sh`

```bash
chmod +x run_local.sh && ./run_local.sh
```

The script:
1. Checks for python3, node and npm.
2. Creates `backend/.venv` with pip.
3. Generates `wells_data.json` if it is missing.
4. Runs `npm install` if needed.
5. Starts the backend on **:8002** and waits for `/api/health`.
6. Starts Vite on **:5180**.
7. Cleans up on Ctrl+C.

## 6. Verify

| Check | URL |
|---|---|
| Dashboard | http://localhost:5180 |
| Health | http://localhost:8002/api/health |
| Wells | http://localhost:8002/api/wells |
| Swagger | http://localhost:8002/docs |
| Production (public) | https://wellpulse-app-bowxi5445q-uc.a.run.app |

## 7. Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| Port 8002 or 5180 busy | Another process is using it | Run `lsof -i :8002` (or `:5180`) and kill it, or set `BACKEND_PORT` (and update `vite.config.ts` proxy) |
| `ModuleNotFoundError: requests` on chat | Missing from `requirements.txt` | `pip install requests` (fixed for good in Stage M via `pyproject.toml`) |
| Chat gives canned answers | No `GEMINI_API_KEY`, so the keyword fallback answers | Expected today; replaced by tool calling in Stage V |
| "Gemini Live" sounds robotic or doesn't stream | The WS is a text-chat wrapper and voice is browser `speechSynthesis` | Known defect; rebuilt in Stage U |
| Dates shift between runs | Generator dates are relative to `datetime.now()` | Fixed in Stage N (fixed window 2021-10-01…2026-09-30) |
| Mic not capturing | Permission blocked or page is not on localhost/HTTPS | Use `http://localhost:5180` and allow the mic |

---
---

# Part II · v0.4 verbatim expansion build

**Drives:** [`features.md`](./features.md) · [`BDD.md`](./BDD.md) · [`SDD.md`](./SDD.md) (authoritative for routes, §13, and layout, §4) · execution policy in [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md) · source [`verbatim.md`](../verbatim.md). **Working dir:** `cloud_run_apps/wellpulse/`. **Branch:** `main`.

> [!IMPORTANT]
> **Answer first: WellPulse stays the product and the UI.** The proven analytics from `../workover_well_intervention/` are ported into `backend/app/analytics/` (decision D-10). A repository layer replaces `wells_data.json` without breaking the React UI (D-11). The prompt-stuffing chat is replaced by tool calling through an in-process ADK `Runner` (D-12). A real Gemini Live proxy is ported from `../Drilling-Intelligence-2.0`. The stages are ordered **by data dependency, not priority**: every verbatim requirement is in scope.

### Rules that override convenience

> [!CAUTION]
> 1. **`uv` only for Python** (D-14): no global `pip install`. **`npm` only for the frontend.**
> 2. **Never fabricate a number** (derived: integrity rule; verbatim §1 *"why did the production decline?"* needs traceable answers). Every number on screen or in speech comes from a tool return, a table row or a cited PDF. Costs are **band + rig-days**, never ₹ or USD point values (D-1).
> 3. **BigQuery DDL apply and Cloud Run deploy of `wellpulse-app`: Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources.** If a gate fails 3 times, mark the stage BLOCKED in [`checklist.md`](./checklist.md) and continue with independent stages; never fake a gate; never change the model.
> 4. **USER RULE: "During the build, do a git commit and push to origin main after every major milestone (each passed stage gate)."** Every stage ends with the commit step below its gate. The message prefix is `v0.4(<stage>): `. Never commit with a red gate, and never commit secrets (`.env`) or git-ignored baselines.
> 5. **Flash never types digits** (derived: F-19 delegation). Flash output that contains numbers uses fact slots filled from data, and lands only after its deterministic gate passes and the orchestrator has reviewed it.

### Fixed parameters (resolved decisions)

| Key | Value | Source |
|---|---|---|
| `PROJECT_ID` | `workover-operations-agentic-ai` | D-4 (resolved 2026-10-07) |
| Cloud Run region | `us-central1` | D-4 |
| BigQuery location | `asia-south1` | D-9 |
| Text model | `gemini-3.8-flash` on **Vertex AI + ADC** (no API key) | D-13 (resolved) |
| Live model | **from the listing in U.2**, never guessed | D-12 |
| Fields | Geleki 142 `GK-` · Lakwa 160 `LKW-` / 3 GGS · Lakhmani 110 `LKM-` / 2 GGS | D-2, D-11 (verbatim §7's "25 / 20 wells" is illustrative) |
| Window | 2021-10-01 … 2026-09-30 (60 months, all fields) | D-2; verbatim §3 *"past let's say 5 year production data field-wise"* |
| Hero wells | GK-129 (squeeze vs. wax removal); LKM-061 as back-up (GLV) | D-7; verbatim §3 *"why not just wax removal?"* |
| `AS_OF` | 2026-09-23 (data runs to 2026-09-30) | D-15 |
| Lakehouse bucket | existing `gs://workover-operations-agentic-ai-datalake` (prefixes `bronze/`, `documents/`, `silver_exports/`) | Resolved 2026-10-07 |
| Doc search | TF-IDF index in v0.4; Vertex AI Search optional later | D-17 |
| Sessions | In-memory; Cloud Run max-instances=1 + session affinity (Vertex AI sessions later) | D-16 |

```bash
export PROJECT_ID=workover-operations-agentic-ai
export REGION=us-central1
export BQ_LOCATION=asia-south1
export AS_OF=2026-09-23
export LAKEHOUSE_BUCKET=gs://workover-operations-agentic-ai-datalake
export ADK_REPO="../workover_well_intervention"     # port source (read-only)
export DI2_REPO="../Drilling-Intelligence-2.0"      # Live reference (read-only)
```

### Stage map (Part II)

| Stage | Name | Verbatim anchor | Est. | Owner [O]=orchestrator [A]=Argon [F]=Flash |
|---|---|---|---|---|
| **M** | Preflight & baseline | derived: safe migration (D-14), no tests exist today | 0.5 d | O |
| **N** | Data foundation v2 | §1 *"Lakwa… Lakhmani… three areas, with their individual cluster"*; §1 *"generate more data"* | 3 d | O + F×2 |
| **O** | PDF corpus + SOPs | §1 *"generate the documents of PDF files of… well interventions"*; §3 *"The SOPs"* | 2 d | O + F×11 |
| **P** | Analytics port + attribution + health | §1 *"why did the production decline? Was it human factor, controllable factor"*; §1 *"which of the wells are doing okay… not producing now"* | 2.5 d | O + F×1 |
| **Q** | ML classifier | §1 *"run a classification algorithm… 5 to 10… or 15 type of interventions"* | 2 d | O |
| **R** | NBA + counterfactual | §1 *"recommend what is the next best action"*; §3 *"Why are you recommending this against an alternative?"* | 1.5 d | O |
| **S** | Dossier | §1 *"aggregate all the history and give it to the person who is going to the field"* | 1 d | O + F×1 |
| **T** | Asset view & drill-down | §1 *"Which particular field is not performing?"*; §3 *"Can you give me a plot?"*, *"drill down to one particular well"*, *"information of nearby wells"* | 2.5 d | O + F×3 |
| **X** | Medallion Lakehouse | §3 *"showcase that in the Medallion architecture… Lakehouse"*; *"whether it should go ultimately into BigQuery or… a better database"* | 1.5 d | F×3 + O |
| **U** | Real Gemini Live | §1 *"Gemini Live is not working well… working very good in Drilling Intelligence 2.0"* | 2.5 d | O + F×2 |
| **Y** | RBAC + multi-field GIS | §3 *"role-based access… Executive Director… versus a field engineer"*; §3 *"they can see different fields… and the wells"* | 1.5 d | O + F×1 |
| **V** | Agent wiring & eval | §3 *"do you see the hierarchy of question and answering?"* (5-level flow, §4 L1–L5) | 2 d | O + F×3 |
| **W** | Deploy | derived: demo must run on the existing public URL | 0.5 d | O (authorised 2026-10-07; local test first) |
| **AC** | Answer canvas | brief §1 U-1, U-2, U-3; §3 (views, router, expandable middle panel) | 1 d | O + F |
| **DF** | Demo flow & eval | brief §6 (11-step demo script Lakwa → LKW-019, +12 eval cases) | 1 d | F + O |
| **DG** | Data gaps (synthetic) | brief §4 (6 tables for 100% of wells, WH-06, WH-08, WH-10, WH-13, WH-14) — **DONE** | 1.5 d | A×3 + O |
| **NN** | Multimodal success engine (demo scorer) | brief §1 U-4, U-5; §5 (D-32 demo scorer, P(success), analogs, drivers, architecture panel) | 1 d | O + F |
| **FR** | Field report HTML | brief §1 U-6; §7 (Jinja2, wellbore SVG, job program, A4 print) | 1.5 d | F + O |
| **W2** | Redeploy | brief §2; §8 (Cloud Run v0.5, smoke 7/7) | 0.5 d | O |

**Parallelism (derived from data dependencies):**
- **N** gates everything in v0.4.
- **O** can start once N's `workover_history` and construction tables exist.
- **U** (transport and audio client) can run in parallel with P–T, using TC-025 as its first voice tool.
- **Q** needs N; **R** needs P and Q; **S** needs O and R; **T** needs P.
- **X** can run any time after N.
- **V** comes after T, U and Y. **W** comes last in v0.4.
- **v0.5 Order & Parallelism (brief §2, §8):**
  - **AC** builds the answer canvas and expandable panel.
  - **DF** follows AC (validates the 11-step flow on canvas).
  - **DG** (DONE): Argon workers generated 6 synthetic gap tables (412 wells); tests and API routes green.
  - **NN** follows DG and Q (implements `success_engine.py` demo scorer and recommendation contracts TC-030/031 with architecture diagram panel showing production Vertex AI path; D-32).
  - **FR** follows DG and NN (HTML field report with SVG wellbore, DG tables, and NN recommendations; layout scaffold may start after DG).
  - **W2** redeploys all v0.5 features to Cloud Run and verifies smoke checks (adds `/api/wells/GK-129/report`).

**Target layout after v0.4:** authoritative tree in [`SDD.md`](./SDD.md) §4. Key paths: `backend/app/analytics/generator/docs_pdf/` (O), `analytics/tools/{attribution,health,intervention_classifier,nba,counterfactual,dossier,field_performance,hierarchy,well_profile,document_search}.py` (P–T), `analytics/model/{features,train,train_classifier}.py` + `intervention_classifier_v1.pkl` / `intervention_classifier_metrics.json` (N, Q), `analytics/config/{factor_map,ic_map,sla}.yaml`, `agent/{runner,adk_tools,prompt,callbacks,rbac}.py` (V, Y), `live/{session,voice_tools,fallback}.py` + `live_prompt.md` (U), `data/index/{doc_chunks.parquet,tfidf.pkl}` (O), `data/geodata/<field>.geojson` (T), `lakehouse/` (X); frontend `components/{common,field,well,map,telemetry,agent}/` and `live/{liveClient,micCapture,audioPlayer}.ts` + `pcm-worklet.js` (T, U, Y).

---

## Stage M · Preflight & baseline

**Goal:** move to `uv`, freeze today's API shapes and UI build as a regression baseline, and add pytest. *Anchor: derived (D-14; there are no tests today, so nothing else can be gated without them).*
**Owner:** [O] all.
**Files:** `backend/pyproject.toml`, `backend/uv.lock` (new); `backend/requirements.txt` (deleted at the end of M); `run_local.sh` (uv); `backend/tests/{conftest.py, golden/capture.py, golden/*.schema.json, test_api_shapes.py}` (new); `.gitignore` (+ `backend/tests/baseline/`).

```bash
# 0. Auth: mandatory Step 0
gcloud auth list
gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"
gcloud config set project ${PROJECT_ID}

# 1. uv project for the backend
cd backend
uv init --app --no-readme --python 3.11 .           # creates pyproject.toml; delete the generated hello.py/main.py stub if any
uv add "fastapi>=0.110" "uvicorn[standard]>=0.28" "pydantic>=2.6" python-dotenv google-genai requests
uv add --dev pytest httpx pytest-asyncio ruff
uv lock && uv sync

# 2. Golden snapshots of today's API (SHAPES, not values: today's data is relative to now())
uv run python -m tests.golden.capture --wells GLK-101,GLK-120,GLK-150   # writes tests/golden/*.schema.json
uv run pytest -q                                                          # test_api_shapes.py green on baseline

# 3. UI build baseline
cd ../frontend && npm ci && npm run build && du -sh dist

# 4. Port-source baseline (read-only copy, git-ignored)
cd .. && mkdir -p backend/tests/baseline
cp -r "${ADK_REPO}/data/landing" backend/tests/baseline/landing_v030      # Geleki hash reference for Gate N
(cd "${ADK_REPO}" && uv run pytest tests/test_contracts.py -q && uv run python -m generator.validate)
```

### ✅ Gate M
- [ ] ADC valid; `gcloud config get-value project` = `workover-operations-agentic-ai`
- [ ] `backend/pyproject.toml` and `uv.lock` committed; `uv sync --frozen` works from clean; `requests` resolved
- [ ] `./run_local.sh` uses `uv run` and still serves :8002 / :5180
- [ ] Golden schema files exist for every existing `/api` route, and `test_api_shapes.py` is green
- [ ] `npm run build` succeeds; bundle size logged
- [ ] ADK repo baseline: contract tests green, validator 0 violations; `landing_v030/` copied (git-ignored)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(M): preflight & baseline — Gate M passed" && git push origin main
```

---

## Stage N · Data foundation v2

**Goal:** 3 fields × 60 months of reproducible data, behind a repository layer that keeps today's REST shapes. *Anchors:*
- §1 *"currently we have Geleki… similarly you can have Lakwa, you can have Lakhmani. So that there are three areas, with their individual cluster"*
- §1 *"generate more data… build those wells as well"*
- §2 WS6 *"rate, pressure, temperature, water cut, GOR, artificial lift metrics"*
- §1 *"well history, the construction"*

**Owners:**
- [O] `FieldConfig` numbers, fixtures, labels (K-1, K-2), validators, repository and adapters.
- [F] N-F1 port boilerplate (moving modules, import rewrites).
- [F] N-F2 frontend type and label updates (`types/well.ts`, `WorkoverTimeline.tsx`: `cost_usd` → `cost_band` + `rig_days`).

**Files:**
- `backend/app/analytics/generator/**` (ported from `${ADK_REPO}/generator/`)
- `backend/app/analytics/model/train.py` (CoxPH, ported)
- `backend/app/data_access/{repository.py, parquet_repo.py, adapters.py}`
- `backend/app/api/wells.py` reads from the repository
- `backend/app/services/data_generator.py` → deprecated, kept until Gate N, then deleted
- `backend/app/data/landing/**`

### N.1 Port and refactor to `FieldConfig`
```
analytics/generator/fields/__init__.py   # FIELD_CONFIGS = {"Geleki", "Lakwa", "Lakhmani"}
analytics/generator/fields/geleki.py     # ADK v0.3.0 params, seed 42: DO NOT change draws; + 24-month prepend (seed 4242)
analytics/generator/fields/lakwa.py      # 160 wells, 3 GGS; fixtures LKW-047 (41 d wait-on-rig + 12 d wait-on-material → pump change), LKW-088 (GGS-II power), LKW-112 (channelling)
analytics/generator/fields/lakhmani.py   # 110 wells, 2 GGS; fixtures LKM-023 (sand), LKM-061 (GLV + wax), LKM-090 (reservoir decline → no job)
analytics/generator/{hierarchy.py, construction.py, operations_events.py, targets.py}   # new tables: field_master, cluster_master, casing_tally, tubing_string, perforation_intervals, operations_events, field_targets, pressure_surveys, formation_tops (D-19, append-only)
```

### N.2 Labels and catalogue (K-1, K-2)
- Add `GLV_REPLACE` and a `cost_band` column to `job_catalogue`. *Anchor: §2 WS3 "Gas Lift Valve Replacement".*
- In `workover_history`, add `catalogue_job_code` and `intervention_class` (IC-01…IC-15). `job_code` is kept.

### N.3 Telemetry columns
**Verbatim gap:** WS6 asks for **temperature**, and the ADK `daily_production` has none. Add `wht_degc` (wellhead temperature), `gl_inj_rate_mscfd` and `gl_inj_pressure_kgcm2` (D-19), with «target ± tol» ranges pinned in N.5; GOR is `gor_scf_bbl`; SPM stays for SRP wells. Add `pressure_surveys` (counterfactual row 1, D7) and `formation_tops` (dossier lithology). *Anchor: §4 T4 "gas-lift injection pressure" on the chart.*

### N.4 Generate, validate, repository
```bash
cd backend
uv add pandas pyarrow numpy scipy lifelines scikit-learn
uv run python -m app.analytics.generator.generate --field all --start 2021-10-01 --end 2026-09-30
uv run python -m app.analytics.generator.validate --field all                     # V-N1..V-N7
uv run python -m app.analytics.generator.validate --compare-baseline tests/baseline/landing_v030
uv run python -m app.analytics.model.train --exclude-prepend                      # Gate E reproduces
DATA_BACKEND=parquet uv run pytest tests/test_api_shapes.py tests/unit/test_repository.py -q
cd ../frontend && npm run build                                                   # types still compile
```

### N.5 Pin design targets
```bash
cd backend && uv run python -m app.analytics.generator.pin_targets > ../docs/pinned_values.md
```
Then replace every «target ± tol» in [`BDD.md`](./BDD.md) with the pinned value.

### ✅ Gate N
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

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(N): data foundation v2 — Gate N passed" && git push origin main
```

---

## Stage O · PDF corpus + SOPs

**Goal:** a synthetic document corpus, D1–D11, whose every number is a data-filled fact slot, served to the UI and to tools. *Anchors:*
- §1 *"generate the documents of PDF files of… well interventions and other documents"*
- §2 WS6 *"Well Intervention Reports, Daily Workover Logs, Well Completion Schematics, Chemical Treatment Logs"*
- §3 *"we need to generate a lot of documents… The SOPs"*

**Owners:**
- [O] O-O1: fact-slot framework, `facts.json`, validator, index, API route. This must exist **before** any worker starts.
- [F] O-F1…O-F11: one Flash worker per document type:
  - D1 WCR
  - D2 Workover Completion
  - D3 DWR
  - D4 Schematic
  - D5 CBL
  - D6 Chemical Treatment Log
  - D7 Well Test
  - D8 RCA
  - D9 Field Studies
  - D10 Monthly Field Performance
  - D11 SOP library (IC-01…IC-14)
- [F] Hero narrative prose (GK-129, LKW-047, LKW-112, LKM-090): drafted by Flash and **reviewed by [O]**.

**Files:**
- `backend/app/analytics/generator/docs_pdf/**`
- `backend/app/data/docs_pdf/<field>/<Dxx>/*.pdf`
- `backend/app/data/index/doc_chunks.parquet`, `backend/app/data/index/tfidf.pkl` (TF-IDF, D-17)
- `backend/app/api/docs.py` (`GET /api/docs/{doc_id}.pdf`, `GET /api/wells/{id}/documents`)
- `frontend/src/components/reports/WellReportsTab.tsx`: the 4 hard-coded tabs become document-index-driven, and the JSON export is kept

```bash
cd backend
uv add reportlab pypdf matplotlib
uv run python -m app.analytics.generator.docs_pdf.render --field all
uv run python -m app.analytics.generator.docs_pdf.scanify --fraction 0.10 --types D1,D5
uv run python -m app.analytics.generator.docs_pdf.validate                 # 100% facts found; zero stray digits in prose
uv run python -m app.analytics.generator.docs_pdf.index
uv run pytest tests/unit/test_docs_route.py -q
# Flash worker gate (one per type): uv run python -m app.analytics.generator.docs_pdf.validate --type D06
```

### ✅ Gate O
- [ ] D1…D11 present for all 3 fields; every IC-01…IC-14 has an SOP (D11)
- [ ] Fact validation 100%; no digit in template prose outside a fact slot
- [ ] Every `document_index` row resolves; `GET /api/docs/{id}.pdf` returns `application/pdf`
- [ ] The scanned subset is flagged `has_text_layer=false` and is still retrievable
- [ ] GK-129 has the 1998 CBL (D5) and the 2019 failed water-shut-off report (D2)
- [ ] WellReportsTab shows real documents for the selected well; `npm run build` green
- [ ] Corpus size logged (target ≤ 200 MB, so it fits in the image)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(O): PDF corpus + SOPs — Gate O passed" && git push origin main
```

---

## Stage P · Analytics port + attribution + health

**Goal:**
- Port the 18 deterministic tools (TC-001…TC-018), making them field-aware.
- Add decline attribution (TC-019).
- Add data-driven health (TC-020), replacing the hard-coded 32 / 12 / 6 status.

*Anchors:*
- §1 *"why did the production decline? Was it human factor, controllable factor, what kind of factors"*
- §2 WS2 *"Controllable… subsurface/reservoir… human/operational"*
- §1 *"which of the wells are doing okay, which… not doing okay, which… not producing now"*
- §3 *"how many wells in Geleki are… either sick or they have lost production?"*

**Owners:**
- [O] tool port, `field_of()`, the TC-019 algorithm, TC-020 thresholds, `factor_map.yaml`.
- [F] P-F1: unit-test scaffolds from the TC signatures.

**Files:**
- `backend/app/analytics/tools/{common,arps_decline,chan_diagnostic,candidate_ranking,render_well_map}.py` (port of `${ADK_REPO}/tools/`, 18 functions exported by `__init__.py`)
- `tools/{hierarchy.py (field_of), attribution.py, health.py}`
- `backend/app/analytics/config/factor_map.yaml`
- `backend/app/api/wells.py`: `/api/wells/kpis` and `status` come from TC-020

```bash
cd backend
uv run pytest tests/unit/test_tools_port.py tests/unit/test_tc019_attribution.py tests/unit/test_tc020_health.py tests/test_api_shapes.py -q
```

### ✅ Gate P
- [ ] All 18 ported tools pass the ADK contract tests (ported to `tests/unit/test_tools_port.py`); no `GK-129` / `Geleki` defaults remain (K-6)
- [ ] The attribution waterfall sums to the total loss within 0.5% for every well in all 3 fields
- [ ] LKW-047's largest class is `HUMAN_PROCESS`; LKM-090 is ≥ 80% `SUBSURFACE`; LKW-088 shows `EXTERNAL` (`GRID_POWER_OUTAGE`)
- [ ] TC-020 buckets come from data; `random.seed(42)` status removed; `/api/wells/kpis` = TC-020 counts
- [ ] Geleki trigger results are unchanged from the ADK baseline

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(P): analytics port + attribution + health — Gate P passed" && git push origin main
```

---

## Stage Q · ML intervention classifier

**Goal:** a multi-class IC classifier (TC-021) with an honest metric band and SHAP contributions. *Anchors:*
- §1 *"run a classification algorithm… 5 to 10 type of interventions… or 15"*
- §1 *"not just the production data, but also of the well history, the construction"*

**Owner:** [O] only: features, training, gate.
**Files:** `backend/app/analytics/model/{features.py, train_classifier.py, intervention_classifier_v1.pkl, intervention_classifier_metrics.json}`, `analytics/tools/intervention_classifier.py`.

```bash
cd backend
uv add shap
uv run python -m app.analytics.model.train_classifier --as-of 2026-09-23   # asserts Gate Q, writes pkl + metrics
uv run pytest tests/unit/test_features_no_leakage.py tests/unit/test_tc021_classifier.py -q
```

### ✅ Gate Q
- [ ] Holdout **macro-F1 0.70–0.92**
- [ ] Top-3 accuracy ≥ 0.90
- [ ] Beats the TC-008 rule baseline by ≥ 0.05 macro-F1
- [ ] ECE ≤ 0.08
- [ ] Leakage test green (no post-event features); LKM-023 → IC-06, LKM-061 → IC-07
- [ ] Features include construction tables (casing, tubing, perforations) and prior-job history (verbatim §1)

> [!WARNING]
> **Macro-F1 > 0.92 is a failure, not a win.** It means leakage or generator signatures that are too clean. Fix them in the generator and retrain. The discipline is the same as Gate E's honest band.

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(Q): ML classifier — Gate Q passed" && git push origin main
```

---

## Stage R · Next best action + counterfactual

**Goal:**
- A ranked NBA (TC-022) with uplift, cost band, rig-days, risk and an SOP link.
- A counterfactual comparison (TC-027) that defends a pick against an alternative.
- Replace `generate_structured_recommendation`'s fabricated USD, uplift and payback.

*Anchors:*
- §1 *"recommend what is the next best action"*
- §2 WS3 *"expected uplift (bopd), estimated cost, and risk profile"*
- §3 *"'Why are you recommending this against an alternative?'… 'why not just wax removal?'… something that is super deep"*
- §4 T5's three dimensions: reservoir pressure / IPR, historical efficacy, cost & downtime delta

**Owner:** [O] only (numeric logic and guardrails).
**Files:** `analytics/tools/{nba.py, counterfactual.py}`; `backend/app/services/ai_agent.py::generate_structured_recommendation` → delegates to TC-022 (fabricated fields deleted); `POST /api/wells/{id}/recommendations` keeps its shape, with `estimated_cost_usd` → `cost_band` + `rig_days`.

```bash
cd backend
uv run pytest tests/unit/test_tc022_nba.py tests/unit/test_tc027_counterfactual.py tests/test_api_shapes.py -q
```

### ✅ Gate R
- [ ] LKW-047 action 1 = `PUMP_OVERHAUL`; LKM-090 action 1 = `NO_JOB_JUSTIFIED`
- [ ] Hero GK-129: `compare_interventions(squeeze vs. wax removal)` returns the verdict, the deciding dimension and a cited prior-job document (D5 1998 CBL / D2 2019 WSO)
- [ ] The counterfactual covers the reservoir/IPR, historical-efficacy and cost-band + rig-days dimensions (verbatim §4 T5)
- [ ] A Chan-negative fixture yields `CHOKE_BACK` with `MODEL_PHYSICS_DISAGREEMENT`
- [ ] Priority ranking = deferred bbl × p_success ÷ rig-days, shown with the cost band (K-7); `GET /api/fields/{field}/priority` and `GET /api/wells/{id}/compare?recommended=&alternative=` serve it
- [ ] Counterfactual row 1 (diagnostic fit) uses `pressure_surveys`
- [ ] **No ₹, USD or payback point value** in any response (D-1); `grep -rn "estimated_cost_usd\|payback" backend/app` returns nothing
- [ ] Every action has a resolving `sop_doc_id` (D11) and SOP steps, unit type and duration band (verbatim §4 T5)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(R): NBA + counterfactual — Gate R passed" && git push origin main
```

---

## Stage S · Field-engineer dossier

**Goal:** a 2–4 page pre-job PDF built only from tables and tool returns. It upgrades `/api/wells/{id}/export`. *Anchors:*
- §1 *"when a person is going to the field, the previous history is not there… aggregate all the history and give it to the person"*
- §2 WS4 *"past intervention histories, well architecture, casing/tubing tallies, and lithology"*

**Owners:**
- [O] TC-023 assembly and trace rules.
- [F] S-F1: layout, styles and section templates (no digits).

**Files:** `analytics/tools/dossier.py`; `backend/app/api/wells.py` export route (JSON adds `pdf_url`; `?format=pdf` returns the PDF) and `POST /api/wells/{id}/dossier`; English-only (Q-2); lithology from `formation_tops`; the export button in `WellReportsTab.tsx`.

```bash
cd backend
uv run python -c "from app.analytics.tools.dossier import build_well_dossier; print(build_well_dossier('LKW-047'))"
uv run pytest tests/unit/test_tc023_dossier.py -q
curl -sf -o /tmp/gk129.pdf "http://localhost:8002/api/wells/GK-129/export?format=pdf"
```

### ✅ Gate S
- [ ] 2–4 pages, ≤ 10 s, all 9 sections, including lithology and casing/tubing tallies (verbatim WS4)
- [ ] Every number traces to a table or tool return; missing sections render `UNAVAILABLE — <table>`
- [ ] GK-129 cites the 1998 CBL and the 2019 WSO
- [ ] The JSON export still works (baseline FEAT kept)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(S): dossier — Gate S passed" && git push origin main
```

---

## Stage T · Asset view & drill-down

**Goal:** field-level APIs and React screens for the L1→L4 drill-down. *Anchors:*
- §1 *"Which particular field is not performing?… performance at a field level"*
- §2 WS1 *"production vs. targets, uptime, water cut, and active intervention counts"*
- §3 *"past… 5 year production data field-wise… Can you give me a plot?"*
- §3 *"drill down to one particular well… production history… what are the different interventions happened in the past"*
- §3 *"also give information of nearby wells"*
- §4 T4 *"reservoir formation… casing/tubing sizes"*

**Owners:**
- [O] TC-024 `compare_fields`, TC-025 `query_hierarchy`, TC-028 `field_history`, TC-029 `well_profile` (with neighbours), TC-017 v2 markers, `/api/fields*` routes.
- [F] T-F1: field + GGS boundary GeoJSON (approximate synthetic, D-3).
- [F] T-F2: Recharts components (field 5-year history: oil, water cut, gas; field comparison; attribution waterfall; health donut; NBA table).
- [F] T-F3: React screen scaffolds (field selector, field view, well deep-dive with nearby wells, intervention markers on `TelemetryCharts`).

**Files:**
- `analytics/tools/{field_performance,hierarchy,well_profile}.py` (TC-028 lives in `field_performance.py`)
- `backend/app/api/fields.py`: `GET /api/fields`, `/api/fields/history?fields=`, `/api/fields/{field}/history`, `/api/fields/compare?period=`, `/api/fields/{field}/health?cluster_id=`, `/api/fields/{field}/attribution?window_days=`, `/api/fields/{field}/priority`
- `backend/app/api/wells.py`: `/api/wells/{id}/profile`, `/api/wells/{id}/production` (job markers + `wht_degc`, `gor_scf_bbl`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2`)
- `backend/app/data/geodata/{geleki,lakwa,lakhmani}.geojson`
- `frontend/src/components/common/FieldSelector.tsx`, `components/field/{FieldHistoryChart,FieldComparisonTable,HealthBucketsCard,AttributionWaterfall,PriorityQueueTable}.tsx`, `components/well/{WellDeepDive,NearbyWellsTable,NbaCard,CounterfactualTable}.tsx`
- `TelemetryCharts.tsx` (markers, WHT, GOR, gas-lift injection rate + pressure), `App.tsx`, `types/well.ts`

```bash
cd backend
uv run pytest tests/unit/test_tc024_fields.py tests/unit/test_tc025_hierarchy.py tests/unit/test_tc028_field_history.py tests/unit/test_tc029_well_profile.py -q
cd ../frontend && npm run build && npm run dev    # walk L1→L4 manually at http://localhost:5180
```

### ✅ Gate T
- [ ] `compare_fields` ranks Lakwa worst, inside the pinned band, with a controllable top driver; the rows include target, uptime, water cut and `active_interventions` counts (TC-024, verbatim WS1)
- [ ] TC-028 returns 60 monthly points per field for oil, water cut and gas; aggregation reconciles with well sums within 0.1%
- [ ] TC-029 returns formation, casing/tubing, lift type and ≥ 3 neighbours on the same cluster; TC-017 v2 shows all in-window job markers
- [ ] `TelemetryCharts` shows WHT, GOR and gas-lift injection rate + pressure from `GET /api/wells/{id}/production` (verbatim WS6, T4)
- [ ] UI: field selector, 5-year field chart, comparison, well deep-dive with markers and nearby wells all render from the APIs (no hard-coded values)
- [ ] `npm run build` green; Part I screens are not regressed

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(T): asset view & drill-down — Gate T passed" && git push origin main
```

---

## Stage X · Medallion Lakehouse

**Goal:** Bronze/Silver/Gold in BigQuery (`asia-south1`), plus a `DATA_BACKEND=parquet|bigquery` switch with a parity test. *Anchors:*
- §3 *"showcase that in the Medallion architecture… a Lakehouse"*
- §3 *"whether it should go ultimately into BigQuery or if there is a better database"*
- §5 topology: Silver *"partitioned… clustered by `field_id, well_id`"*; Silver vector store; Gold KPIs / NBA features / grounding cache

**Owners:**
- [F] X-F1 DDL; X-F2 loaders; X-F3 Dataform.
- [O] X-O4: review, `bigquery_repo.py`, parity test, production-store decision record.

**Files:** `lakehouse/ddl/*.sql`, `lakehouse/load/*.py`, `lakehouse/dataform/**` (repo root), `backend/app/data_access/bigquery_repo.py`, `backend/tests/integration/test_backend_parity.py`.

```bash
export LAKEHOUSE_BUCKET=gs://workover-operations-agentic-ai-datalake   # existing bucket (resolved 2026-10-07); prefixes bronze/, documents/, silver_exports/
cd backend && uv add google-cloud-bigquery google-cloud-storage
gcloud storage buckets describe ${LAKEHOUSE_BUCKET} >/dev/null   # must exist; never delete or recreate it
gcloud storage cp -r app/data/landing  ${LAKEHOUSE_BUCKET}/bronze/
gcloud storage cp -r app/data/docs_pdf ${LAKEHOUSE_BUCKET}/documents/
for f in ../lakehouse/ddl/*.sql; do bq query --project_id=${PROJECT_ID} --location=${BQ_LOCATION} --use_legacy_sql=false --dry_run < "$f"; done
# Authorised by user (2026-10-07): apply only after every dry-run above is clean; never drop existing tables
for f in ../lakehouse/ddl/*.sql; do bq query --project_id=${PROJECT_ID} --location=${BQ_LOCATION} --use_legacy_sql=false --label=app:wellpulse < "$f"; done
uv run python -m lakehouse.load.bronze_to_silver
(cd ../lakehouse/dataform && npx @dataform/cli compile && npx @dataform/cli run)
DATA_BACKEND=bigquery uv run pytest tests/integration/test_backend_parity.py -q
```

### ✅ Gate X
- [ ] `wellpulse_bronze`, `wellpulse_silver` and `wellpulse_gold` exist in `asia-south1`; Silver `daily_production` is partitioned by `production_date` and clustered by `field, well_id`
- [ ] Silver row counts = Bronze; Gold `field_kpi_monthly` = TC-028 output
- [ ] Parquet vs. BigQuery parity test green; the app runs with `DATA_BACKEND=bigquery`
- [ ] Silver `doc_chunks` table mirrors the TF-IDF index from D1–D11 (D-17; Vertex AI Search optional later, verbatim §5)
- [ ] Exports written to `${LAKEHOUSE_BUCKET}/silver_exports/`
- [ ] Production-store decision record (BigQuery vs. alternatives) recorded in [`SDD.md`](./SDD.md) §15.2 (verbatim §3)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(X): medallion lakehouse — Gate X passed" && git push origin main
```

---

## Stage U · Real Gemini Live

**Goal:** replace the fake `WS /api/wells/{id}/live` with a google-genai Live proxy ported from Drilling Intelligence 2.0, calling the **same** tool functions. *Anchors:*
- §1 *"Gemini Live is not working well in the current build. It is working very good in Drilling Intelligence 2.0. So check how it is built"*
- §2 WS5 *"live_session.py, ws_live.py, ADR-003… liveClient.ts"*

**Owners:**
- [O] `session.py` (resumption, context compression, recap, 3-failure fallback to text), voice tool declarations, model verification.
- [F] U-F1: AudioWorklet client (16 kHz up / 24 kHz down) and the player.
- [F] U-F2: VoiceAgentPanel UI states (connecting, listening, speaking, fallback), keeping the Hinglish / English / Hindi toggle; push-to-talk plus an open-mic hands-free option. Audio-only (no camera/image).

**Files:**
- `backend/app/live/{session.py, voice_tools.py, live_prompt.md, fallback.py}`
- `backend/app/api/live.py`: `WS /ws/live` (field/well context message) plus the legacy `WS /api/wells/{id}/live` shim, kept until Gate V (D-20)
- `frontend/src/live/{liveClient.ts, micCapture.ts, pcm-worklet.js, audioPlayer.ts}`
- `components/agent/VoiceAgentPanel.tsx`: `speechSynthesis` removed from the Live path

### U.1 Study the reference (read before writing)
```
${DI2_REPO}/backend/app/agent/live_session.py     # lifecycle, resumption, fallback
${DI2_REPO}/backend/app/api/ws_live.py            # WS proxy
${DI2_REPO}/frontend/src/live/{liveClient,micCapture,audioPlayer}.ts
${DI2_REPO}/docs/adr/ADR-003-gemini-live-adk-proxy.md
```

### U.2 Live model verification: list, never guess
```bash
cd backend
uv run python - <<'EOF'
from google import genai
c = genai.Client(vertexai=True, project="workover-operations-agentic-ai", location="us-central1")
names = [m.name for m in c.models.list()]
print("LIVE:", [n for n in names if "live" in n.lower() or "native-audio" in n.lower()])
print("TEXT:", [n for n in names if "gemini-3.8-flash" in n])   # D-13: confirm the text model exists on Vertex
EOF
```
Write the exact names from that output into `backend/.env`: `LIVE_MODEL=…`, `LIVE_LOCATION=…`, `TEXT_MODEL=gemini-3.8-flash`. If a model is missing in `us-central1`, try the other listed locations; if none has it after 3 attempts, mark Stage U **BLOCKED** in [`checklist.md`](./checklist.md) and continue with independent stages. Never substitute or change the model.

### U.3 Test locally
```bash
cd backend
uv add websockets
uv run pytest tests/integration/test_ws_live.py -q     # fake session: reconnect, recap, 3-failure fallback
./run_local.sh                                        # push-to-talk at http://localhost:5180: "Which field is underperforming?"
```

### ✅ Gate U
- [ ] The model names in `.env` come from the U.2 listing (output pasted into the commit message or PR)
- [ ] Spoken answer to *"Which field is underperforming?"*; first audio ≤ 2.5 s warm
- [ ] Barge-in ≤ 300 ms; a forced reconnect keeps context (resumption + recap); 3 failures → text fallback with a visible notice
- [ ] Spoken numbers equal tool returns (same functions as the text path)
- [ ] The language toggle still works; `speechSynthesis` is no longer used for Live replies
- [ ] Open-mic hands-free mode works; `FIELD_ENGINEER` persona can use Live voice
- [ ] Runs on Vertex ADC; `GEMINI_API_KEY` is not read anywhere (`grep -rn GEMINI_API_KEY backend/app` is empty)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(U): real Gemini Live — Gate U passed" && git push origin main
```

---

## Stage Y · RBAC + multi-field GIS

**Goal:** a minimal three-persona RBAC (ED, ASSET_MANAGER, FIELD_ENGINEER), gated at the tool layer, and a multi-field WellMap. *Anchors:*
- §3 *"if an Executive Director is asking for a particular data versus a field engineer… If it is overcomplicating, we can leave it"*
- §6 matrix (allowed and restricted views)
- §3 *"on the interface they can see different fields, right, clearly, and the wells"*

**Owners:**
- [O] Y-O1: `agent/rbac.py` capability matrix and `require()` in each tool wrapper; persona in session state. Built last (D-8).
- [F] Y-F2: persona picker, WellMap multi-field (boundaries, GGS clusters, health colours, field filter) against the T APIs, keeping the Esri basemap (D-5).

**Files:** `backend/app/agent/rbac.py` (capability matrix in code, no YAML), `backend/app/agent/adk_tools.py` (`require()`); `frontend/src/components/common/PersonaPicker.tsx`, `components/map/WellMap.tsx`, `components/common/Header.tsx`.

```bash
cd backend && uv run pytest tests/unit/test_rbac.py tests/bdd -k "rbac or gis" -q
cd ../frontend && npm run build
```

### ✅ Gate Y
- [ ] The same question as ED vs. FIELD_ENGINEER gives correctly scoped answers per verbatim §6; a direct denied tool call returns `UNAVAILABLE` (no data leak in the error)
- [ ] The map shows 3 fields with boundaries, GGS markers and a field filter; header counts = TC-020; the well drawer = TC-029
- [ ] Synthetic coordinates are labelled as synthetic on the map (D-3)
- [ ] Persona switch works in both text and Live

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(Y): RBAC + multi-field GIS — Gate Y passed" && git push origin main
```

---

## Stage V · Agent wiring & eval

**Goal:** an in-process ADK `Runner` with about 30 tool wrappers behind `POST /api/chat` and the existing per-well chat route; BDD tests for the 5-level flow; an eval dataset. *Anchors:*
- §3 *"do you see the hierarchy of question and answering? … generate some documents, give some aggregated data… drill down to a particular well… nearby wells"*
- §4 L1–L5
- §8 Milestone 6 *"Automated pytest execution covering all 5 demo turns"*

**Owners:**
- [O] `runner.py`, wrapper contracts, prompt guardrails (numbers only from tool returns; no ₹/USD; ML disclosure), eval iteration.
- [F] V-F1: Gherkin → `tests/bdd/features/*.feature` and step glue.
- [F] V-F2: eval JSON (≥ 30 cases: every L1–L5 turn × 3 personas + refusals, every 🎤 scenario).
- [F] V-F3: Playwright UI specs.

**Files:**
- `backend/app/agent/{runner.py, adk_tools.py, prompt.py, callbacks.py}`
- `backend/app/api/chat.py` (`POST /api/chat {persona, field, well_id?, message}`)
- `api/wells.py` `/chat` and `/audio` → Runner; legacy `WS /api/wells/{id}/live` and `/audio` shims removed at the end of V (D-20)
- `services/ai_agent.py`: `build_well_context`, `call_gemini_api` and `query_local_petroleum_expert` deleted
- `backend/tests/{bdd/, eval/wellpulse-eval.json}`, `frontend/tests/e2e/*.spec.ts`

```bash
cd backend
uv add google-adk
uv add --dev pytest-bdd
uv run pytest tests/ -q                                   # golden + unit + integration + bdd
uvx google-agents-cli eval run                            # or `agents-cli eval run` if installed; iterate 5–10×
cd ../frontend && npm i -D @playwright/test && npx playwright install chromium && npx playwright test
```

### ✅ Gate V
- [ ] All BDD scenarios green, including one automated test per demo turn L1–L5 (verbatim §8 M6)
- [ ] Eval tool-selection accuracy ≥ 90% on `tests/eval/wellpulse-eval.json` (≥ 30 cases); if it is lower, apply the SDD sub-agent split and re-run
- [ ] No answer contains a number missing from that turn's tool returns (number-trace test)
- [ ] The agent refuses at least once per new field (LKM-090 → no job justified) and explains why
- [ ] The prompt-stuffing code and the keyword fallback are removed; text runs on Vertex ADC with `gemini-3.8-flash` (D-13)
- [ ] Playwright: L1→L5 click-through passes against `npm run build` served by FastAPI
- [ ] Legacy `/api/wells/{id}/live` and `/audio` shims removed; `WS /ws/live` is the only Live route (D-20)

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(V): agent wiring & eval — Gate V passed" && git push origin main
```

---

## Stage W · Deploy (authorised by user, 2026-10-07)

**Goal:** update Cloud Run service `wellpulse-app` in `workover-operations-agentic-ai` with the multi-stage image, then smoke test. *Anchor: derived (the demo runs on the existing public URL).*
**Owner:** [O] only. Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources. Smoke test after deploy.

### W.1 Multi-stage Dockerfile plan (D-14; authoritative version in [`SDD.md`](./SDD.md) §17.1)
```dockerfile
# Stage 1: frontend
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build                      # → /web/dist

# Stage 2: Python deps with uv
FROM python:3.11-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Stage 3: runtime
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PORT=8080 PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend
COPY --from=deps /app/backend/.venv ./.venv
COPY backend/ ./                        # app/, incl. data/landing, data/docs_pdf, data/index, data/geodata, analytics/model/*.pkl, analytics/config/ (D-18: regenerated here if git-ignored)
RUN python -m app.analytics.tools.selfcheck   # fails the build if data/model artifacts are missing
COPY --from=web /web/dist /app/frontend/dist
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--ws-ping-interval", "20"]
```
- Keep `.dockerignore` excluding `archive`, `node_modules` and `.venv`. Add `backend/tests`.
- **Resolved:** untrack `frontend/dist` (`git rm -r --cached frontend/dist`, add to `.gitignore`) in the same commit that lands this Dockerfile.

### W.2 Local first
```bash
docker build -t wellpulse:v04 . && docker run --rm -p 8080:8080 \
  -e GOOGLE_GENAI_USE_VERTEXAI=true -e GOOGLE_CLOUD_PROJECT=${PROJECT_ID} -e GOOGLE_CLOUD_LOCATION=${REGION} \
  -v ~/.config/gcloud:/root/.config/gcloud:ro wellpulse:v04
curl -sf localhost:8080/api/healthz && curl -sf localhost:8080/api/fields
```

### W.3 Authorised (user, 2026-10-07)
Proceed only if W.2 passed locally. Never delete the existing service or revisions.

### W.4 Cloud Run
```bash
gcloud run deploy wellpulse-app --source . \
  --project workover-operations-agentic-ai --region us-central1 \
  --memory 4Gi --cpu 2 --min-instances 1 --max-instances 1 \
  --timeout 3600 --session-affinity --no-cpu-throttling \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=workover-operations-agentic-ai,GOOGLE_CLOUD_LOCATION=us-central1,TEXT_MODEL=gemini-3.8-flash,LIVE_MODEL=<from U.2>,LIVE_LOCATION=<from U.2>,DATA_BACKEND=parquet,AS_OF=2026-09-23,BQ_LOCATION=asia-south1 \
  --labels app=wellpulse,stage=v04
# The runtime SA needs roles/aiplatform.user (Phase 6) and, if DATA_BACKEND=bigquery, roles/bigquery.dataViewer + jobUser.
# Remove any GEMINI_API_KEY env/secret from the service:
gcloud run services update wellpulse-app --project workover-operations-agentic-ai --region us-central1 --remove-env-vars GEMINI_API_KEY
scripts/smoke.sh https://wellpulse-app-bowxi5445q-uc.a.run.app   # /api/healthz, one route per screen, one chat turn, WS connect
```
- `--max-instances 1` is **D-16**: ADK sessions and Live sessions are held in memory, so a single instance plus session affinity avoids split sessions during the demo.
- `--no-traffic` plus a tagged revision is the safer alternative if the user wants to keep the current revision live until the smoke test passes.

### ✅ Gate W
- [ ] https://wellpulse-app-bowxi5445q-uc.a.run.app serves v0.4: `/api/healthz`, `/api/fields`, a dossier PDF, `/api/docs/{id}.pdf`
- [ ] Text L1–L5 and Live (*"Which field is underperforming?"*) work end to end on the URL; forced reconnect and fallback both work
- [ ] No `GEMINI_API_KEY` on the service; the revision runs on Vertex ADC
- [ ] Pre-warm checklist for demo day: min-instance up, Live connect test, fallback test, persona switch

**Commit (gate passed):**
```bash
git add -A && git commit -m "v0.4(W): deploy — Gate W passed" && git push origin main
```

---

## Stage AC · Answer canvas

**Goal:** Turn WellPulse from an all-in-one well history dump into a question-driven answer canvas. The middle panel shows only the specific view matching the user's question; the chat provides concise replies (≤ 3 sentences plus an optional collapsed card); the middle panel can expand to full width hiding the map (ESC or restore button restores map); the agent remains as the command center on the right. *Anchor: brief §1 U-1, U-2, U-3; §3 (D-25).*
**Owner:** [O] Orchestrator (routing architecture, action contracts, review), [F] Flash (view components in `WellDeepDiveDrawer.tsx`, expandable middle panel, hotkeys, brevity guardrails).
**Files:** `frontend/src/api/chat.ts`, `frontend/src/components/well/WellDeepDiveDrawer.tsx`, `frontend/src/App.tsx`, `frontend/src/components/agent/VoiceAgentPanel.tsx`.

```bash
# Frontend build & typecheck
cd frontend && npm run build
```

### ✅ Gate AC
- [ ] 10 demo phrases route to the correct canvas view via `pickCanvasView` (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`)
- [ ] Chat replies are strictly concise (≤ 3 sentences plus optional collapsed card); no full-history dump in chat
- [ ] Expandable middle panel hides the map; ESC key and restore button return to standard split layout
- [ ] Interventions table and compare view auto-open on counterfactual questions
- [ ] `cd frontend && npm run build` and `tsc` green; user UI sign-off

**Commit (gate passed and user approved, orchestrator only):**
```bash
git add -A && git commit -m "v0.5(AC): answer canvas — Gate AC passed" && git push origin main
```

---

## Stage DF · Demo flow & eval

**Goal:** Standardize and automate the 11-step Lakwa → LKW-019 demo sequence in chat and voice, and expand the evaluation dataset with canvas-routing assertions. *Anchor: brief §1 U-1..U-4; §6.*
**Owner:** [F] Flash (demo script documentation, eval dataset additions), [O] Orchestrator (rehearsal runner, evaluation verification).
**Files:** `docs/demo_flow.md`, `backend/tests/eval/wellpulse-eval.json`, `backend/tests/integration/test_demo_flow.py`.

```bash
# Run backend tests and eval suite
cd backend && uv run pytest -q
uv run python -m tests.eval.run_eval
```

### ✅ Gate DF
- [ ] 11-step demo script (`docs/demo_flow.md`: Lakwa → LKW-019) passes end-to-end in chat and voice
- [ ] Eval dataset includes +12 canvas-routing test cases with ≥ 90% routing and tool selection accuracy
- [ ] Every turn asserts correct canvas view, chat response ≤ 3 sentences, and 0 history dumps

**Commit (gate passed and user approved, orchestrator only):**
```bash
git add -A && git commit -m "v0.5(DF): demo flow & eval — Gate DF passed" && git push origin main
```

---

## Stage DG · Synthetic data gaps — **DONE**

**Goal:** Generate 6 new synthetic tables for 100% of wells (412 wells across 3 fields) to fill critical well integrity, survey, hazard, and completion data gaps, with deterministic seed `20261008`, `is_synthetic=true` flag on every row, and full lakehouse parity. *Anchor: brief §4; WH-06, WH-08, WH-10, WH-13, WH-14 (D-29, D-31).*
**Status:** **DONE**. Argon workers completed 6 tables for 412 wells; tests green (`backend/tests/unit/test_dg_*.py` and `backend/tests/unit/test_tc033_dg_tables.py`). DG integration (routes `/tubing-tally`, `/deviation`, `/integrity`, lakehouse DDL regenerated, not applied) is done.
**Owner:** [A] Argon (`gemini-3.8-flash-high` via `swarm add`) for table generators and consistency tests:
- Worker 1: `tubing_tally` (WH-06), `deviation_survey` (WH-08)
- Worker 2: `barrier_tests` (WH-14), `wellhead_rating` (WH-14)
- Worker 3: `fluid_hazards` (WH-13), `fishing_records` (WH-10)
[O] Orchestrator (landing integration, Lakehouse Bronze/Silver ingestion, gap register updates).
**Files:** `backend/app/analytics/generator/dg.py`, `backend/app/analytics/generator/fields/{tubing,deviation,integrity,hazards}.py`, `backend/tests/unit/test_dg_consistency.py`, `lakehouse/ddl/dg_tables.sql`, `lakehouse/load/bronze_to_silver.py`.

```bash
# Generate all 6 DG tables across all fields and run consistency validation
cd backend && uv run python -m app.analytics.generator.dg --field all
uv run pytest tests/unit/test_dg_*.py tests/unit/test_tc033_dg_tables.py -q
uv run pytest -q
```

### ✅ Gate DG
- [x] 6 new tables generated for 100% of wells (412 wells), written to `backend/app/data/landing/<field>/<table>.parquet`
- [x] Every row tagged with `is_synthetic=true`, `_source_system='wellpulse_dg_v1'`, deterministic seed `20261008`
- [x] Consistency tests green: `tests/unit/test_dg_*.py` and `tests/unit/test_tc033_dg_tables.py` (tally length within ±1 joint of tubing depth, TVD monotonic and ≤ MD, barrier dates in valid range with FAIL ≤ 5%, wellhead class ≥ 1.5 × max THP, fishing records only where failure codes allow)
- [x] DG integration complete: routes `/tubing-tally`, `/deviation`, `/integrity` implemented; lakehouse DDL regenerated (not applied); `well_history_template.md` data gap register updated from GAP to AVAILABLE (synthetic)

**Commit (gate passed and user approved, orchestrator only):**
```bash
git add -A && git commit -m "v0.5(DG): synthetic data gaps — Gate DG passed" && git push origin main
```

---

## Stage NN · Multimodal success engine (demo scorer)

**Goal:** Present a multimodal neural network as the intervention ranking engine with an architecture diagram panel showing the production path (Vertex AI custom job + Model Registry). Per Decision D-32, no model is trained in v0.5; compute stable, believable P(success) numbers using the deterministic demo scorer in `backend/app/analytics/tools/success_engine.py` (formula in brief §5); rank top 3 interventions + `NO_JOB_JUSTIFIED` with expected uplift, analogs, and top drivers; provide "How did you decide?" explanation panel with architecture diagram. *Anchor: brief §1 U-4, U-5; §5 (D-32).*
**Owner:** [O] Orchestrator (demo scorer formula in `success_engine.py`, recommendation contract TC-030, analog search TC-031, architecture panel, plausibility reviews), [F] Flash (explanation card UI, architecture SVG/diagram, documentation).
**Files:** `backend/app/analytics/tools/success_engine.py`, `backend/app/analytics/tools/recommendations.py`, `backend/app/analytics/tools/similar_wells.py`, `backend/tests/unit/test_tc030_recommend.py`, `backend/tests/unit/test_success_engine.py`.

```bash
# Run success engine and recommendation unit tests
cd backend && uv run pytest tests/unit/test_success_engine.py tests/unit/test_tc030_recommend.py -q
uv run pytest -q
```

### ✅ Gate NN (demo)
- [ ] Top 3 render for all producing wells via TC-030 `recommend_interventions`
- [ ] p_success is strictly in [0.05, 0.95] and stable across calls
- [ ] Analog counts recompute exactly from data (TC-031 `similar_wells`, k=5)
- [ ] The explanation panel shows all four elements: evidence chain, look-alike analogs, top drivers (SHAP), and multimodal NN architecture diagram (with Vertex AI custom job + Model Registry described as production path)
- [ ] Plausibility review of GK-129, LKW-019, and LKM-061 outputs passes orchestrator inspection

**Commit (gate passed and user approved, orchestrator only):**
```bash
git add -A && git commit -m "v0.5(NN): multimodal success engine — Gate NN passed" && git push origin main
```

---

## Stage FR · Field report (HTML)

**Goal:** Server-side rendered A4-printable HTML field report (`GET /api/wells/{id}/report?intervention=<class>`) with ONGC branding, wellbore schematic SVG, complete job program, top-3 rationale, and 100% fact-checked tool provenance. *Anchor: brief §1 U-6; §7 (D-30).*
**Owner:** [F] Flash (Jinja2 HTML template prose, wellbore SVG drawing component, A4 print CSS, canvas iframe viewer), [O] Orchestrator (TC-032 report data assembly engine, job program synthesis, fact validator, route registration).
**Files:** `backend/app/analytics/tools/field_report.py`, `backend/app/analytics/templates/field_report.html`, `backend/app/api/wells.py`, `frontend/src/components/well/FieldReportView.tsx`, `backend/tests/unit/test_tc032_field_report.py`.

```bash
# Run field report unit tests and fact validator
cd backend && uv run pytest tests/unit/test_tc032_field_report.py -q
uv run pytest -q
```

### ✅ Gate FR
- [ ] `GET /api/wells/{id}/report` renders for all 412 wells in < 3 s locally (p95)
- [ ] Clean A4 print layout verified with repeating headers, print-friendly styling, and "SYNTHETIC DATA — DEMO" banner
- [ ] ONGC logo (`frontend/public/brand/ongc_logo.svg`) displayed at top left and print footer, with text wordmark fallback if missing
- [ ] Wellbore SVG renders dynamically from casing/tubing/perf/formation data (with placeholders for missing data per WH-05)
- [ ] 100% of digits validated against `facts.json` sidecar; Flash writes template prose only with no hard-coded numerals
- [ ] Chat and voice provide a concise one-line link to open the field report

**Commit (gate passed and user approved, orchestrator only):**
```bash
git add -A && git commit -m "v0.5(FR): field report HTML — Gate FR passed" && git push origin main
```

---

## Stage ED · ED meeting pack (v0.6, Ajay Ratan) — in progress 2026-10-08

**Goal:** Everything an ED (one asset, technical) asks about production, shown to everyone (showcase mode), on an India map that drills down to the Assam Asset. *Anchor: [`features.md`](./features.md) §3b F-27…F-33; D-33…D-36.*
**Owner:** [O] Orchestrator, step by step. Each step is shown to the user, then committed and pushed after approval (X-7).

| Step | Feature | Files | Done when |
|---|---|---|---|
| ED-1 | F-27 Showcase mode | `backend/app/agent/rbac.py`, `backend/tests/conftest.py`, `frontend/src/components/persona/PersonaPicker.tsx` | Switch off → every persona FULL; tests run with the switch on and stay green |
| ED-2 | F-28 Completion diagram | `backend/app/analytics/tools/field_report.py` (shared SVG), `backend/app/api/analytics_wells.py` (`/schematic.svg`), `WellDeepDiveDrawer.tsx` (Wellbore view) | Diagram with casing, cement, tubing, packer/pump, perforations, formation tops, TD for hero + random wells |
| ED-3 | F-29 Offset decline verdict | `backend/app/analytics/tools/offset_decline.py` (TC-033), route `/offset-decline`, `OffsetDeclineView.tsx`, `docs/pinned_values.md` | Verdict + curves for GK-129, LKW-019, LKM-061; unit tests |
| ED-4 | F-30 Anomaly scan | `backend/app/analytics/tools/anomalies.py` (TC-034), route `/anomalies`, `WellHistoryView.tsx` ("History & Wax/Sand" view: dated timeline) | ≤ 12 dated events, deterministic; unit tests |
| ED-5 | F-31 Wax & sand behaviour | `backend/app/analytics/tools/wax_sand.py` (TC-035), route `/wax-sand`, `WellHistoryView.tsx` (wax / sand panels) | Counts, own cycle vs. field norm, next-due only from own cycle, downtime; "no sand-rate data" stated; unit tests |
| ED-6 | F-32 India map | `backend/app/analytics/tools/ongc_assets.py` (seeded), `/api/geo/ongc-assets` (`api/asset.py`), `WellMap.tsx` (India / Assam toggle) | India view on login with non-interactive tags for 13 assets; Assam drill-down unchanged |
| ED-7 | F-33 Agent + script | `backend/app/agent/adk_tools_ext.py` (+3 tools → 33), `runner.py` (artifacts → well view), `rbac.py`, `prompt.py`, `live/voice_tools.py` (`well_profile.data.checks`, 12-tool cap kept), `frontend/src/api/chat.ts` + `VoiceAgentPanel.tsx` (offsets / history views), `docs/demo_flow.md` | "What's wrong with GK-129?" uses TC-033…035 and opens Offsets; ED script rehearsed |

```bash
# per step
cd backend && uv run pytest -q tests/unit -p no:warnings
cd ../frontend && npx tsc --noEmit -p . && npx vite build
```

### ✅ Gate ED
- [ ] ED-1 … ED-7 done and each approved by the user
- [ ] Unit tests green (current baseline 527 + new TC-033…035 / schematic tests)
- [ ] `tsc` + `vite build` green
- [ ] Every new number traces to a tool return (X-1/X-2); no currency (X-3)
- [ ] ED rehearsal script passes on the local app

**Commit (per step, user approved):**
```bash
git commit -m "v0.6(ED-n): <name>" && git push origin main
```

---

## Stage W2 · Redeploy

**Goal:** Redeploy WellPulse v0.5 container to Cloud Run with zero-downtime revision rollout, verifying answer canvas, multimodal success scoring, data gap tables, and field report via 7/7 smoke tests. *Anchor: brief §2; §8.*
**Owner:** [O] Orchestrator all (container configuration, deployment, smoke verification).
**Files:** `Dockerfile`, `deploy/deploy.sh`, `deploy/smoke_test.py`, `deploy/selfcheck.py`.

```bash
# Build, deploy, and smoke test Cloud Run deployment
deploy/deploy.sh build
deploy/deploy.sh deploy
deploy/deploy.sh smoke
```

### ✅ Gate W2
- [ ] Local container validation passes via `deploy/deploy.sh build`
- [ ] Cloud Run deployment completes successfully via `deploy/deploy.sh deploy` with min-instances=1 and session affinity
- [ ] `deploy/deploy.sh smoke` passes 7/7 checks (including new endpoint `/api/wells/GK-129/report`)
- [ ] End-to-end 11-step demo script verified on public Cloud Run URL

**Commit (gate passed and user approved, orchestrator only):**
```bash
git add -A && git commit -m "v0.5(W2): redeploy — Gate W2 passed" && git push origin main
```

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

## Definition of done (v0.5)
- [ ] Answer canvas active: chat replies ≤ 3 sentences, no full-history dumps, 10 key phrases route correctly via `pickCanvasView` (F-20, F-21)
- [ ] Middle panel expandable with map hiding, ESC hotkey and restore button (F-21)
- [x] 6 synthetic data gap tables generated for 100% of wells (412 wells), `is_synthetic=true`, consistency tests 100% green (F-22)
- [ ] Multimodal success engine implemented (demo scorer in `success_engine.py`, D-32), top 3 recommendations + `NO_JOB_JUSTIFIED` served with P(success), analogs, drivers, and architecture diagram panel (F-23, F-24)
- [ ] Printable HTML field report (`GET /api/wells/{id}/report`) renders for all 412 wells < 3 s with ONGC branding, wellbore SVG, job program, and 100% fact validation (F-25)
- [ ] 11-step demo script (Lakwa → LKW-019) passes in chat and voice with canvas routing and brevity (F-26)
- [ ] Deployed to Cloud Run with `deploy/deploy.sh deploy` and smoke test 7/7 green
- [ ] One commit + push to `origin main` per passed stage gate with user sign-off (orchestrator only)

---

## Definition of done (v0.6, ED meeting)
- [ ] Showcase mode: nothing hidden for any persona; RBAC presented as a switchable capability (D-33)
- [ ] Completion diagram with perforations in the dashboard (F-28)
- [ ] "What is wrong" answered by the offset decline verdict, anomaly scan and wax/sand behaviour (F-29…F-31)
- [ ] India map with 13 ONGC asset tags; Assam drill-down (F-32)
- [ ] ED rehearsal script passes; CMD features logged as backlog F-34…F-40
- [ ] One commit + push per approved step

---

## Former open items (all resolved 2026-10-07)

| # | Item | Owner | Blocks | Status |
|---|---|---|---|---|
| 1 | Meeting date with Ajay Ratan (Q-1) | Orchestrator | Unknown: build all stages; if time-boxed, cut Y first, then X | Resolved |
| 2 | Lakehouse bucket | Orchestrator | Stage X | Resolved: existing `gs://workover-operations-agentic-ai-datalake` (`bronze/`, `documents/`, `silver_exports/`) |
| 3 | Verbatim §4 T3 ranks by NPV / payback (conflicts with D-1) | Orchestrator | Stages R, T | Resolved: deferred bbl × p_success ÷ rig-days, shown with cost band (K-7) |
| 4 | Untrack the committed `frontend/dist` | Orchestrator | Stage W | Resolved: untracked in Stage W |
| — | D-15…D-20, Q-2 (AS_OF, sessions, TF-IDF, artefacts, telemetry columns, WS shims, English-only dossier) | — | — | Resolved 2026-10-07 ([`SDD.md`](./SDD.md) §19.2) |
| — | Autonomy: DDL apply, Cloud Run deploy, commit + push per gate | — | — | Authorised by user 2026-10-07 19:52 |
| — | D-4 project = `workover-operations-agentic-ai` | — | — | Resolved 2026-10-07 |
| — | D-13 text model = `gemini-3.8-flash` on Vertex ADC | — | — | Resolved 2026-10-07 |
| — | Stray `v0.4-build` branch on GitHub | — | — | Deleted 2026-10-07 |
