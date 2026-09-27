# Feature Catalog & Roadmap (`features.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 1.0.0  
**Methodology:** MoSCoW Prioritization (Must have, Should have, Could have, Won't have)

---

## 1. Feature Matrix Overview

| ID | Feature Name | Category | Priority | Target Release |
|---|---|---|---|---|
| **FEAT-01** | Interactive GIS Wellhead Map | Geospatial | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-02** | 3-Tier Health Status Prioritization | Operational Triage | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-03** | 24-Month Telemetry Time-Series Charts | Analytics | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-04** | Chronological Workover & Intervention Log | Maintenance | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-05** | Split-Pane Contextual AI Chat Agent | Conversational AI | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-06** | Voice Input (STT) & Audio Waveform | Voice Experience | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-07** | Voice Playback (TTS) Synthesis | Voice Experience | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-08** | Prescriptive Engineering Recommendations | Decision Support | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-09** | 50-Well Physics Synthetic Data Engine | Simulation | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-10** | Single-Script Local Runner (`run_local.sh`)| Developer Experience | **Must-Have** | v1.0 (Local MVP) |
| **FEAT-11** | Quick Prompt Suggestion Chips | Usability | **Should-Have** | v1.1 |
| **FEAT-12** | PDF/Markdown Diagnostic Report Export | Reporting | **Should-Have** | v1.1 |
| **FEAT-13** | Multi-Well Comparative Analytics | Advanced Analytics | **Could-Have** | v1.2 |
| **FEAT-14** | Live SCADA MQTT/Modbus Ingestion Hook | Enterprise Integration | **Won't-Have (v1)**| Future |

---

## 2. Detailed Feature Specifications

### FEAT-01: Interactive Satellite Field Map & Tagged Wellheads
- **User Value**: Delivers realistic geospatial aerial context of the mature Geleki brownfield asset in Sivasagar, Assam, allowing engineers to visualize real terrain and surface pad locations.
- **Capabilities**:
  - High-resolution aerial satellite imagery powered by Esri World Imagery (Maxar/Earthstar Geographics).
  - Permanent **tagged wellhead name badges** (`GLK-101`, `GLK-104`) floating above each well pin for instant visual identification.
  - Authentic oil derrick wellhead iconography replacing generic or confusing symbols.
  - One-click style switcher between **🛰️ Satellite Field** and **🗺️ Dark SCADA** modes.
  - Interactive panning, zooming, click-to-focus, and rich telemetry popups on hover.

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
  - Context window includes 24-month high/lows, recent pressure trends, and complete workover logs.

### FEAT-06 & FEAT-07: Voice Input (STT) & Voice Playback (TTS)
- **User Value**: Hands-free operation for engineers in control rooms or on mobile field tablets.
- **Capabilities**:
  - Browser-native Web Speech API Speech-to-Text with push-to-talk microphone button.
  - Animated sound-wave visualizer indicating listening and processing states.
  - Text-to-Speech synthesis with mute/pause controls and natural pacing.

### FEAT-08: Prescriptive Engineering Recommendations
- **User Value**: Turns raw historical data into prioritized, actionable field operations.
- **Capabilities**:
  - Automatically recommends specific technical workovers (e.g. Chemical Scale Squeeze, ESP frequency adjustment, solvent soak).
  - Includes estimated job cost, projected flow recovery (+BOPD), and payback timeframe in days.
  - Safety hazard and operational risk warnings.

### FEAT-09: Synthetic Data Engine (50 Wells, 730 Days)
- **User Value**: Complete, realistic, zero-setup testing data.
- **Capabilities**:
  - Generates 50 realistic brownfield wells distributed across the Geleki Field in Assam (Tipam Sands, Barail Main Sand, Kopili).
  - Simulates 2 years of daily data incorporating hyperbolic decline curve physics, water cut growth, seasonal temperature swings, and synthetic equipment failures.
  - Generates realistic workover histories with realistic contractor names, dates, and outcomes.

### FEAT-10: Single-Script Local Runner (`run_local.sh`)
- **User Value**: Seamless local deployment with zero complex configuration.
- **Capabilities**:
  - Checks Python and Node prerequisites.
  - Installs requirements and npm packages.
  - Launches backend and frontend with automated port management.
  - Handles graceful shutdown on `Ctrl+C`.

### FEAT-11: Engineering Reports Dossier & Deep AI Grounding
- **User Value**: Grounded, verifiable engineering documentation accessible directly in the telemetry workspace and queryable via the voice agent.
- **Capabilities**:
  - **Well Completion Report (WCR)**: Spud date, total depth, casing policy, perforation depths, crude assay (pour point, paraffin wax %).
  - **Daily Workover Report (DWR)**: Shift execution logs with timestamps, supervising engineer name (`Er. R. K. Gogoi`), rig identification, tagged wax/sand bridge depth, and pressure testing certifications.
  - **Bottomhole Pressure & Sonolog Survey (BHP)**: Static BHP, Flowing BHP, Drawdown (ΔP), Productivity Index (PI), and acoustic sonolog liquid level sounding.
  - **Produced Water Chemistry & Scale Assay**: Total Dissolved Solids (TDS), pH, ionic distribution (Cl⁻, Na⁺, Ca²⁺, Mg²⁺, Ba²⁺, SO₄²⁻), Stiff-Davis index, and chemist recommendations.
  - **Voice AI Context Injection**: The voice agent directly cites report IDs, named supervising engineers, tagged depths, and exact laboratory values.

### FEAT-12: Natural Conversational Voice, Bilingual Hinglish & Gemini Live API
- **User Value**: Eliminates robotic, long-winded report recitation; enables snappy 2–3 sentence operational dialogue in natural Hindi + English.
- **Capabilities**:
  - **2–3 Sentence Voice Hard Cap**: Spoken answers are strictly limited to 35–45 words so engineers get the immediate takeaway without waiting.
  - **Bilingual Hinglish Mode**: Natural conversational code-switching tailored for ONGC petroleum operations in Assam.
  - **3-Way Language Toggle**: 🇮🇳 Hinglish *(Default)*, 🇬🇧 English, 🇮🇳 Pure Hindi.
  - **Gemini Live WebSocket Endpoint**: Low-latency bidirectional live streaming via `/api/wells/{id}/live`.
  - **Authentic TTS Synthesis**: Automatic selection of Indian English / Hindi voices (`hi-IN`, `en-IN`, Google हिन्दी) with markdown sanitization.
