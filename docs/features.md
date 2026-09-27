# Feature Catalog & Roadmap (`features.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 2.0.0  
**Methodology:** MoSCoW Prioritization (Must have, Should have, Could have, Won't have)

---

## 1. Feature Matrix Overview

| ID | Feature Name | Category | Priority | Status |
|---|---|---|---|---|
| **FEAT-01** | Interactive GIS Wellhead Map & Satellite Imagery | Geospatial | **Must-Have** | Complete |
| **FEAT-02** | 3-Tier Health Status Prioritization (🟢/🟡/🔴) | Operational Triage | **Must-Have** | Complete |
| **FEAT-03** | 24-Month Telemetry Time-Series Charts | Analytics | **Must-Have** | Complete |
| **FEAT-04** | Chronological Workover & Intervention Log | Maintenance | **Must-Have** | Complete |
| **FEAT-05** | Split-Pane Contextual AI Chat Agent | Conversational AI | **Must-Have** | Complete |
| **FEAT-06** | Active Voice Microphone UI & Live Interim STT | Voice Experience | **Must-Have** | Complete |
| **FEAT-07** | Voice Playback (TTS) Synthesis with Indian Voices | Voice Experience | **Must-Have** | Complete |
| **FEAT-08** | Prescriptive Engineering Recommendations & Payback | Decision Support | **Must-Have** | Complete |
| **FEAT-09** | 50-Well Physics Synthetic Data Engine (Geleki Field) | Simulation | **Must-Have** | Complete |
| **FEAT-10** | Single-Script Local Runner (`run_local.sh`) | Dev Experience | **Must-Have** | Complete |
| **FEAT-11** | Engineering Reports Dossier (WCR, DWR, BHP, Lab) | Grounding | **Must-Have** | Complete |
| **FEAT-12** | Bilingual Hinglish, English & Pure Hindi Copilot | Natural Language | **Must-Have** | Complete |
| **FEAT-13** | Vertex AI Gemini 2.5 Flash ADC & Semantic Fallback | Cloud AI | **Must-Have** | Complete |
| **FEAT-14** | Geleki Gas Gathering Stations (GGS) & Flowline Network | Geospatial GIS | **Should-Have**| Complete |
| **FEAT-15** | One-Click Engineering Dossier Export (JSON/Markdown) | Field Reporting | **Should-Have**| Complete |
| **FEAT-16** | Cloud Run Serverless Production Deployment | Cloud Operations | **Must-Have** | Complete |

---

## 2. Detailed Feature Specifications

### FEAT-01: Interactive Satellite Field Map & Tagged Wellheads
- **User Value**: Delivers realistic geospatial aerial context of the mature Geleki brownfield asset in Sivasagar, Assam.
- **Capabilities**:
  - High-resolution aerial satellite imagery powered by Esri World Imagery (Maxar/Earthstar Geographics).
  - Permanent **tagged wellhead name badges** (`GLK-101`, `GLK-104`) floating above each well pin for instant visual identification.
  - Authentic oil derrick wellhead iconography replacing generic or confusing symbols.
  - One-click style switcher between **🛰️ Satellite Field** and **🗺️ Dark SCADA** modes.
  - Interactive panning, zooming, click-to-focus with smooth `flyTo` transitions.

### FEAT-02: 3-Tier Health Status Prioritization
- **User Value**: Eliminates information overload by sorting wells into distinct triage buckets.
- **Capabilities**:
  - 🟢 **Healthy / Optimal**: Flow rate within target tolerance ($\pm 5\%$), stable pressures, zero unresolved alarms.
  - 🟡 **Needs Attention / Warning**: Flow rate decline between 15% and 30%, rising water cut, or minor casing pressure build-up.
  - 🔴 **Critical / Failed**: ESP pump failure, zero production flow, gas lock, or emergency shut-in.
  - Pulsing radar visual badge on all Critical/Failed wells.
  - Filter chips on the top navigation to isolate any status group in 1 click.

### FEAT-03: 24-Month Telemetry Time-Series Charts
- **User Value**: Allows petroleum engineers to evaluate reservoir depletion trends and anomalous drops over 1 to 2 years.
- **Capabilities**:
  - High-performance Recharts line and area graphs.
  - Metrics tracked: Oil (BOPD), Gas (MCFD), Water Cut (%), Tubing Pressure (psi), and Casing Pressure (psi).
  - Time-range toggles: 30 Days, 6 Months, 1 Year, 2 Years.
  - Synchronized tooltips displaying date, exact production numbers, and deviation from 30-day moving average.

### FEAT-04: Chronological Workover & Intervention Log
- **User Value**: Surfaces maintenance history directly alongside current telemetry to avoid repeating ineffective treatments.
- **Capabilities**:
  - Card-based timeline showing date, operation type, contractor, and cost.
  - Quantitative outcome tracking: Net post-workover production change ($\Delta$ BOPD).
  - Categorization badges: Acid Wash, Scale Squeeze, ESP Overhaul, Re-perforation, Sand Cleanout.

### FEAT-05: Split-Pane Contextual AI Chat Agent
- **User Value**: An intelligent conversational copilot directly embedded in the operations view.
- **Capabilities**:
  - Auto-binds context of whichever well is actively selected on the map.
  - Capable of answering complex domain questions:
    - *"What was the total intervention expenditure on this well over the last 18 months?"*
    - *"When did we last change the ESP pump and what was the warranty period?"*
    - *"Why did oil flow decline while water cut rose after the November workover?"*
  - Context window includes 24-month high/lows, recent pressure trends, complete workover logs, and all 4 engineering reports.

### FEAT-06: Active Voice Microphone UI & Live Interim STT
- **User Value**: Natural, responsive hands-free speech input without confusing "mute" visuals.
- **Capabilities**:
  - Distinct emerald active recording state with glowing ripple animation.
  - Replaces confusing slashed microphone (`<MicOff>`) with an active, pulsing `<Mic>` icon.
  - Real-time speech streaming with `interimResults = true`, displaying spoken words live in the input box as the engineer speaks.
  - Dynamic audio frequency wave animation during listening and response playback.

### FEAT-07: Voice Playback (TTS) Synthesis with Authentic Indian Accents
- **User Value**: Clear, intelligible operational readouts in control rooms.
- **Capabilities**:
  - Automatic voice selection preferring Indian English and Hindi synthesizers (`hi-IN`, `en-IN`, Google हिन्दी).
  - Markdown stripping prior to speech to avoid reading formatting characters aloud.
  - Audio mute/unmute control with state persistence.

### FEAT-08: Prescriptive Engineering Recommendations
- **User Value**: Turns raw historical data into prioritized, actionable field operations.
- **Capabilities**:
  - Automatically recommends specific technical workovers (e.g. Chemical Scale Squeeze, ESP frequency adjustment, solvent soak).
  - Includes estimated job cost, projected flow recovery (+BOPD), and payback timeframe in days.
  - Safety hazard and operational risk warnings.

### FEAT-09: 50-Well Physics Synthetic Data Engine (Geleki Field)
- **User Value**: Complete, realistic, zero-setup testing data.
- **Capabilities**:
  - Generates 50 realistic brownfield wells distributed across the Geleki Field in Assam (Tipam Sands, Barail Main Sand, Kopili).
  - Simulates 2 years of daily data incorporating hyperbolic decline curve physics, water cut growth, seasonal temperature swings, and synthetic equipment failures.
  - Generates realistic workover histories with realistic contractor names, dates, and outcomes.

### FEAT-11: Engineering Reports Dossier & Deep AI Grounding
- **User Value**: Grounded, verifiable engineering documentation accessible directly in the telemetry workspace.
- **Capabilities**:
  - **Well Completion Report (WCR)**: Spud date, total depth, casing policy, perforation depths, crude assay (pour point, paraffin wax %).
  - **Daily Workover Report (DWR)**: Shift execution logs with timestamps, supervising engineer name (`Er. R. K. Gogoi`), rig identification, tagged wax/sand bridge depth, and pressure testing certifications.
  - **Bottomhole Pressure & Sonolog Survey (BHP)**: Static BHP, Flowing BHP, Drawdown (ΔP), Productivity Index (PI), and acoustic sonolog liquid level sounding.
  - **Produced Water Chemistry & Scale Assay**: Total Dissolved Solids (TDS), pH, ionic distribution (Cl⁻, Na⁺, Ca²⁺, Mg²⁺, Ba²⁺, SO₄²⁻), Stiff-Davis index, and chemist recommendations.

### FEAT-12: Natural Conversational Voice & Bilingual Hinglish
- **User Value**: Snappy 2–3 sentence operational dialogue in natural Hindi + English.
- **Capabilities**:
  - **2–3 Sentence Voice Hard Cap**: Spoken answers are strictly limited to 35–45 words.
  - **Bilingual Hinglish Mode**: Natural conversational code-switching tailored for ONGC petroleum operations in Assam.
  - **3-Way Language Toggle**: 🇮🇳 Hinglish *(Default)*, 🇬🇧 English, 🇮🇳 Pure Hindi.

### FEAT-13: Vertex AI Gemini 2.5 Flash ADC & Semantic Fallback
- **User Value**: Real generative intelligence running in Google Cloud with robust fallback.
- **Capabilities**:
  - Native Vertex AI integration in `us-central1` using Application Default Credentials (ADC).
  - Smart semantic fallback engine that parses user questions dynamically across all 4 dossiers, never repeating canned text.

### FEAT-14: Geleki Gas Gathering Stations & Pipeline Network
- **User Value**: True oilfield GIS operational topology.
- **Capabilities**:
  - Geographic markers for Geleki Gas Gathering Stations (GGS-1, GGS-2, GGS-3) and Central Desalting Plant (CDP).
  - Visual flowline routes connecting wells to their respective gathering nodes.

### FEAT-15: One-Click Engineering Dossier Export
- **User Value**: Portability of operational dossiers for field engineers and rig supervisors.
- **Capabilities**:
  - Download full well reports dossier in formatted Markdown / JSON with 1 click.
