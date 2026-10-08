# WellPulse: Energy Well Operations & Voice AI Platform
## Geleki Brownfield Asset (Assam, India • ONGC)

WellPulse is an industrial operations intelligence platform designed for mature brownfield production and integrity management in the **Geleki Oil Field (Sivasagar, Assam)**. It combines high-resolution **Aerial Satellite Mapping** with tagged wellhead markers (`GLK-101` to `GLK-150`), 3-tier operational health prioritization (Healthy, Needs Attention, Failed), 24-month deep telemetry drilldown (BOPD, MCFD, Water Cut %, Pressures), chronological workover and intervention histories, and a voice-enabled conversational AI agent with real-time well context injection.

---

## Documentation (v0.5 doc set, 0.5.0-draft)

> The README below describes the platform architecture and capabilities. The v0.5 expansion is canonically defined in [`docs/v05_change_brief.md`](./docs/v05_change_brief.md):

| Doc | Purpose |
|---|---|
| [`docs/v05_change_brief.md`](./docs/v05_change_brief.md) | **Canonical source of truth for v0.5**: user feedback U-1..U-7, stages AC..W2, decisions D-25..D-32 |
| [`verbatim.md`](./verbatim.md) | Source of truth: the user's verbatim requirements (v0.4 baseline) |
| [`docs/BRD.md`](./docs/BRD.md) | Business requirements, personas, success metrics (v0.5 updated) |
| [`docs/features.md`](./docs/features.md) | Feature catalogue F-01…F-26 with verbatim anchors (v0.5 updated) |
| [`docs/BDD.md`](./docs/BDD.md) | Gherkin acceptance scenarios (104) |
| [`docs/SDD.md`](./docs/SDD.md) | Design; authoritative route table (§13) and layout (§4) |
| [`docs/build.md`](./docs/build.md) | Stage-by-stage build commands and gates (M…W, AC…W2) |
| [`docs/checklist.md`](./docs/checklist.md) | Live progress tracker |
| [`docs/DELEGATION.md`](./docs/DELEGATION.md) | Orchestrator vs. Flash vs. Argon task split |
| [`docs/EXECUTION_PLAN.md`](./docs/EXECUTION_PLAN.md) | Autonomous run policy, milestones MS-0…MS-19, git and failure rules |
| [`docs/CONSISTENCY_REPORT.md`](./docs/CONSISTENCY_REPORT.md) | Doc-set alignment record and residual issues |

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │    WellPulse Web Application (Vite)     │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
        │ Satellite GIS Map │   │  24-Month Curves  │   │  Voice AI Copilot │
        │ (Tagged GLK Pins) │   │(Recharts BOPD/psi)│   │ (STT / Wave / TTS)│
        │ 🟢 🟡 🔴 Triage   │   │  Workover Log     │   │ Context Injection │
        └───────────────────┘   └───────────────────┘   └───────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    FastAPI Backend Server (:8002)      │
                      │  • 50 Geleki Wells Synthetic Engine    │
                      │  • Hybrid Gemini 2.5 + Local Engine    │
                      └────────────────────────────────────────┘
```

---

## Quickstart (Local Run)

Launch both the backend API server and frontend client with a single command:

```bash
chmod +x run_local.sh
./run_local.sh
```

- **Dashboard UI**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## Project Structure

```
wellpulse/
├── archive/                     # Preserved prototypes for learning & reference
│   ├── LEARNINGS.md             # Review of previous Streamlit & Vertex approaches
│   ├── drilling-dashboard/      # Archived prototype
│   └── drilling-intelligence/   # Archived prototype
├── docs/                        # Complete Engineering Specifications
│   ├── BRD.md                   # Business Requirements Document
│   ├── BDD.md                   # Behavior-Driven Development (Gherkin Scenarios)
│   ├── SDD.md                   # Software Design Document & System Architecture
│   ├── features.md              # Feature Catalog (MoSCoW Prioritized)
│   ├── build.md                 # Local Build, Prerequisites & Run Guide
│   └── checklist.md             # Phased Delivery & Verification Tracker
├── backend/                     # Python FastAPI Service
│   ├── app/
│   │   ├── api/                 # Endpoints (/wells, /wells/{id}/history, /chat)
│   │   ├── services/            # Telemetry generator & contextual AI copilot
│   │   └── data/                # Generated 24-month well dataset (730 days)
│   ├── requirements.txt         # FastAPI, Uvicorn, Pydantic, google-genai
│   └── run.py                   # Server launcher
├── frontend/                    # Modern React 18 + Vite + Tailwind Client
│   ├── src/
│   │   ├── components/
│   │   │   ├── map/             # Leaflet GIS Map with custom radar pins
│   │   │   ├── telemetry/       # 24-Month Recharts (BOPD, MCFD, Pressures)
│   │   │   ├── timeline/        # Chronological workover & intervention log
│   │   │   ├── agent/           # Voice AI assistant with STT, Waveform & TTS
│   │   │   └── common/          # Header, fleet KPI ribbon & search
│   │   ├── types/               # TypeScript interfaces
│   │   └── App.tsx              # Multi-pane industrial operations dashboard
│   ├── package.json
│   └── vite.config.ts
├── run_local.sh                 # Unified local startup script
└── README.md                    # Landing documentation
```

---

## Core Capabilities

1. **Geospatial Health Prioritization (3 Tiers)**:
   - 🟢 **Healthy / Optimal**: Telemetry within target decline envelope.
   - 🟡 **Needs Attention / Warning**: Flow decline >15%, water cut spikes, pressure anomalies.
   - 🔴 **Critical / Failed**: ESP pump motor failure, zero flow, or emergency shut-in with pulsing radar pins.
2. **24-Month Historical Telemetry**:
   - High-resolution daily time series for 50 wells across Wolfcamp and Bone Spring formations.
   - Tracks Oil (BOPD), Gas (MCFD), Water Cut (%), Tubing Pressure (psi), and Casing Pressure (psi).
3. **Chronological Workover Log**:
   - Detailed history of past interventions (Acid stimulations, ESP replacements, scale squeezes) with contractor, date, cost in USD, and post-intervention flow delta (+BOPD).
4. **Voice-Enabled Contextual AI Copilot**:
   - In-browser Speech-to-Text (STT) and dynamic audio waveform animations.
   - Audible Text-to-Speech (TTS) response playback.
   - Ingests selected well telemetry and workover history to answer diagnostic questions and formulate prescriptive workover recommendations.
5. **Tool-grounded agent (v0.4)**:
   - Text chat (`POST /api/chat`) runs an in-process ADK agent on `gemini-3.8-flash` via Vertex AI with ADC (no API key).
   - Every number in an answer must come from that turn's tool results; a guardrail masks anything else.
   - If the model is unreachable the reply is marked `degraded`; `WELLPULSE_AGENT_LLM=fake` runs a deterministic scripted model for CI/offline demos.

---

## What's New in v0.5 (2026-10-08)

> **Canonical Source**: [`docs/v05_change_brief.md`](./docs/v05_change_brief.md) (user feedback U-1..U-7; build order AC → DF → DG → NN → FR → W2).

WellPulse v0.5 transforms the application from an all-in-one well dump into an interactive, question-driven operations intelligence platform:

1. **Question-Driven Answer Canvas (F-20, F-21; Stage AC)**:
   - Middle panel dynamically displays the specific view matching the user's question (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`), replacing the monolithic Deep Dive (D-25).
   - Conversational responses are strictly capped at ≤ 3 sentences plus an optional collapsed card; full-history data dumps in chat are eliminated.
   - Middle panel expands over the map area for deep technical views, while the conversational AI agent remains pinned on the right as the operational command centre (ESC or restore button restores map).
2. **Multimodal Success Engine (F-23; Stage NN)**:
   - Presented in UI as an advanced multimodal neural network combining 24-month production time series, static geology and completion data, decline context, and candidate intervention embeddings (art-of-the-possible demo, Decision D-32).
   - Powered by a deterministic demo scorer (`backend/app/analytics/tools/success_engine.py`) calculating $P(\text{success} \mid c) = \text{clip}(p_{\text{mechanism}}(c)^{0.5} \times (0.5 \cdot \text{base\_rate} + 0.5 \cdot \text{analog\_rate}), 0.05, 0.95)$ using existing `ic-hgb-v1` probabilities, Bayesian-shrunk field historical base rates, and $k=5$ look-alike analog well success rates.
   - Production path (Vertex AI custom training job, Model Registry `wellpulse-success-nn`, and batch scoring into `gold.intervention_success_scores`) is presented to the user in the "How did you decide?" architecture diagram panel (no training job in v0.5, D-27, D-32).
3. **Top-3 Recommendations with Analogs & Attributions (F-24; Stage NN, AC)**:
   - Ranks top 3 candidate interventions (primary + 2 alternatives) plus `NO_JOB_JUSTIFIED` by deferred bbl × p_success ÷ rig-days with qualitative cost band (`LOW`/`MED`/`HIGH`; no currency point estimates, D-1).
   - Full explainability: evidence chain, k-NN look-alike analog wells (`similar_wells`, k=5 on standardised `build_features` vectors), and top 3 feature drivers from SHAP.
4. **Printable HTML Field Report & Job Program (F-25; Stage FR)**:
   - Server-rendered A4-printable HTML report (`GET /api/wells/{id}/report`) for workover crews featuring ONGC branding, wellbore architecture SVG, completion diagrams, and an actionable job program.
   - 100% fact-validated through `facts.json` sidecar.
5. **Synthetic Data Gap Closure (F-22; Stage DG)**:
   - Closes 6 structural data gaps across all 412 wells in `well_master`: `tubing_tally`, `deviation_survey`, `barrier_tests`, `wellhead_rating`, `fluid_hazards`, and `fishing_records` (`is_synthetic=true`, D-29). Fully generated and verified with unit tests.
6. **11-Step Demo Flow & Verification (F-26; Stage DF)**:
   - End-to-end verified sequence from field comparison to field report link on Lakwa → `LKW-019` across chat and voice.

### New v0.5 API Routes

| Method | Route | Description | Stage / Tool Contract |
|---|---|---|---|
| `GET` | `/api/wells/{id}/recommendations?k=3` | Top-3 ranked candidate interventions with calibrated P(success), analogs, and drivers | Stage NN, AC (`TC-030`) |
| `GET` | `/api/wells/{id}/similar?class=` | Look-alike analog wells (k=5) based on feature space | Stage NN (`TC-031`) |
| `GET` | `/api/wells/{id}/report` | Printable A4 HTML field report with wellbore SVG and job program | Stage FR (`TC-032`) |
| `GET` | `/api/wells/{id}/tubing-tally` | Detailed joint-by-joint tubing tally for completion architecture | Stage DG (`TC-033`, DONE) |
| `GET` | `/api/wells/{id}/deviation` | Directional deviation survey stations (MD, Inc, Azi, TVD) | Stage DG (`TC-033`, DONE) |
| `GET` | `/api/wells/{id}/integrity` | Barrier tests and wellhead ratings for well integrity review | Stage DG (`TC-033`, DONE) |

