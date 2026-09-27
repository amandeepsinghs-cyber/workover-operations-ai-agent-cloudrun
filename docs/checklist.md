# Implementation & Verification Checklist (`checklist.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 1.0.0  
**Status:** In Progress  

---

## Phase 1: Archiving & Repository Scaffolding
- [x] Create `archive/` directory to preserve previous prototypes for learning.
- [x] Relocate legacy `drilling-dashboard/` and `drilling-intelligence/` into `archive/`.
- [x] Synthesize `archive/LEARNINGS.md` with lessons learned.
- [x] Scaffold top-level project folders: `docs/`, `backend/`, `frontend/`, `scripts/`.
- [x] Create repository README and symlinks.

---

## Phase 2: Specification Documentation Suite
- [x] Generate **BRD.md** (Business Requirements Document: Executive Summary, Personas, Objectives, Functional & Non-functional requirements).
- [x] Generate **BDD.md** (Behavior-Driven Development: Gherkin scenarios for Map Triage, Telemetry, Timeline, Voice AI, and Recommendations).
- [x] Generate **SDD.md** (Software Design Document: System Architecture, Tech Stack, Data Models, API Specs, Voice Pipeline).
- [x] Generate **features.md** (Detailed Feature Catalog with MoSCoW prioritization).
- [x] Generate **build.md** (Step-by-step local prerequisites, environment setup, and execution commands).
- [x] Generate **checklist.md** (This phased verification tracker).

---

## Phase 3: Backend & Synthetic Data Engine
- [x] Create `backend/requirements.txt` (fastapi, uvicorn, pydantic, google-genai).
- [x] Implement `backend/app/services/data_generator.py` simulating 50 Geleki Brownfield wells (Assam Asset, ONGC) with:
  - [x] 730 days of realistic daily telemetry (BOPD, MCFD, Water Cut %, Tubing/Casing Pressure psi).
  - [x] Realistic failure events (Gas lift cuts, severe paraffin wax choking, Tipam sand bridging).
  - [x] Comprehensive historical workover logs (Hot oil wax cleanouts, WSO polymer squeezes, gravel packs, GLV replacements with costs and flow deltas).
- [x] Implement `backend/app/api/wells.py` endpoints:
  - [x] `GET /api/health`
  - [x] `GET /api/wells` (with status and formation filters)
  - [x] `GET /api/wells/kpis` (fleet metrics)
  - [x] `GET /api/wells/{id}`
  - [x] `GET /api/wells/{id}/history`
  - [x] `GET /api/wells/{id}/workovers`
  - [x] `POST /api/wells/{id}/chat`
  - [x] `POST /api/wells/{id}/recommendations`
- [x] Implement `backend/app/services/ai_agent.py`:
  - [x] Context builder assembling well profile, 24-month high/lows, and workover history.
  - [x] Live Gemini 2.5 Flash query integration when `GEMINI_API_KEY` is present.
  - [x] Deterministic local Petroleum Diagnostic fallback engine when API key is omitted.
  - [x] Structured prescriptive workover recommendation generation.
- [x] Implement `backend/run.py` server launcher.

---

## Phase 4: Frontend Map, Telemetry & Voice UI
- [x] Initialize `frontend/package.json` with React 18, Vite, Tailwind CSS, Leaflet, Recharts, and Lucide-react.
- [x] Configure `tailwind.config.js` with industrial dark SCADA theme palette:
  - `#0d1117` main background
  - `#161b22` card containers
  - `#2ea043` green (healthy)
  - `#d29922` amber (needs attention)
  - `#f85149` red (critical/failed)
- [x] Implement `frontend/src/components/map/WellMap.tsx`:
  - [x] Interactive Leaflet map centered on Geleki Field, Assam (lat ~26.77, lng ~94.69).
  - [x] Custom SVG markers colored Green, Amber, Red.
  - [x] Pulsing CSS radar effect on Critical/Failed wells.
  - [x] Click-to-select and focus handlers.
- [x] Implement `frontend/src/components/common/Header.tsx` & Fleet KPI ribbon (Total, Healthy, Attention, Failed).
- [x] Implement `frontend/src/components/telemetry/TelemetryCharts.tsx`:
  - [x] Time-series charts for Oil (BOPD) and Gas (MCFD).
  - [x] Water Cut (%) area chart.
  - [x] Dual-axis Tubing vs Casing pressure line chart.
  - [x] Time range selectors (30D, 6M, 1Y, 2Y).
- [x] Implement `frontend/src/components/timeline/WorkoverTimeline.tsx`:
  - [x] Chronological intervention cards showing date, operation type, cost, contractor, and flow delta.
- [x] Implement `frontend/src/components/agent/VoiceAgentPanel.tsx`:
  - [x] Web Speech API Speech-to-Text with push-to-talk microphone button.
  - [x] Animated audio sound-wave visualizer.
  - [x] Web Speech API Text-to-Speech audio response playback.
  - [x] Contextual chat message stream with pre-canned prompt suggestions.
  - [x] Prescriptive recommendation card with ROI, cost, and flow recovery estimates.
- [x] Implement `frontend/src/components/telemetry/WellDetails.tsx`.
- [x] Implement `frontend/src/App.tsx` master operations dashboard.

---

## Phase 5: Local Integration & Verification
- [x] Implement root `run_local.sh` single-command startup script with automated port management (8001 & 5175).
- [x] Create root `README.md` with complete architectural guide and navigation links.
- [x] Test backend APIs with python test runner to ensure 200 OK responses and proper context injection.
- [x] Test frontend production build (`npm run build`) with zero TypeScript and bundling errors.
- [x] Verify full end-to-end user workflow:
  - [x] Map renders with 3 distinct color tiers (Green = Healthy, Amber = Attention, Red = Critical with radar pulse).
  - [x] Status filtering and search work smoothly.
  - [x] Clicking a well updates the 24-month charts and workover timeline.
  - [x] Voice query receives a grounded response with historical intervention data and audio playback.
  - [x] Recommendation engine produces actionable workover suggestions with costs, ROI, and risk factors.

---

## Phase 6: Engineering Reports Dossier & Deep AI Grounding
- [x] Implement multi-page Engineering Reports generator in `backend/app/services/data_generator.py`:
  - [x] Well Completion Report (WCR) with casing policy, perforations, crude assay (wax %, pour point).
  - [x] Daily Workover Report (DWR) with supervising engineer, rig, contractor, and hourly execution logs.
  - [x] Subsurface BHP & Acoustic Sonolog Survey with SBHP, FBHP, Drawdown, and acoustic fluid level.
  - [x] Produced Water Chemistry & Scale Deposition Assay with TDS, pH, ions, and Stiff-Davis index.
- [x] Expose reports in backend API (`GET /api/wells/{id}`, `GET /api/wells/{id}/reports`, `GET /api/wells/{id}/reports/{type}`).
- [x] Inject full reports dossier into AI Copilot prompt context and local deterministic petroleum expert.
- [x] Add `WellReportsTab.tsx` component with 4 interactive sub-tabs styled as official ONGC engineering documents.
- [x] Embed `Engineering Reports Dossier (4 Docs)` tab into `WellDetails.tsx`.
- [x] Add report-grounded prompt chips to `VoiceAgentPanel.tsx`.
- [x] Verify frontend builds cleanly (`npm run build`) and backend tests succeed.

---

## Phase 7: Natural Conversational Voice, Bilingual Hinglish & Gemini Live API
- [x] Cap spoken AI responses to strictly 2–3 punchy sentences (30–45 words max) for natural human speech cadence.
- [x] Implement natural bilingual Hindi + English (Hinglish) code-switching for ONGC Geleki field operations.
- [x] Add 3-way language toggle in UI header: 🇮🇳 Hinglish *(Default)*, 🇬🇧 English, 🇮🇳 Pure Hindi.
- [x] Integrate Gemini Live bidirectional WebSocket endpoint at `/api/wells/{id}/live`.
- [x] Upgrade Web Speech API TTS to select authentic Indian/Hindi voices (`hi-IN`, `en-IN`, Google हिन्दी) and sanitize markdown before playback.
- [x] Verify concise responses and WebSocket streaming with automated test suite.
