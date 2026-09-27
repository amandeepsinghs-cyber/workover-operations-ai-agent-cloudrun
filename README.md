# WellPulse: Energy Well Operations & Voice AI Platform
## Geleki Brownfield Asset (Assam, India • ONGC)

WellPulse is an industrial operations intelligence platform designed for mature brownfield production and integrity management in the **Geleki Oil Field (Sivasagar, Assam)**. It combines high-resolution **Aerial Satellite Mapping** with tagged wellhead markers (`GLK-101` to `GLK-150`), 3-tier operational health prioritization (Healthy, Needs Attention, Failed), 24-month deep telemetry drilldown (BOPD, MCFD, Water Cut %, Pressures), chronological workover and intervention histories, and a voice-enabled conversational AI agent with real-time well context injection.

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
5. **100% Offline / Local Resilience**:
   - Automatically utilizes Google Gemini 2.5 Flash when `GEMINI_API_KEY` is provided.
   - Seamlessly falls back to the deterministic **Local Petroleum Expert Engine** when running completely offline.
