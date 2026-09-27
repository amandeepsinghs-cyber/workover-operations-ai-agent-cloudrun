# Learnings from Archived Drilling Prototypes

This document synthesizes key architectural patterns, domain lessons, and technical limitations discovered during the review of the archived `drilling-dashboard` and `drilling-intelligence` prototypes.

---

## 1. Domain Modeling & Visual Standards
- **Three-Tier Status Prioritization**: The prior prototypes successfully used clear status categories with industrial colors:
  - Optimal / Healthy: `#2ea043` (Green)
  - Caution / Needs Attention: `#d29922` (Amber/Yellow)
  - Critical / Failed: `#f85149` (Red)
- **High-Density Energy Ops Palette**: The dark theme (`#0e1117` background, `#161b22` cards, `#30363d` borders) provided excellent contrast for engineers viewing continuous telemetry charts.

---

## 2. Limitations of Previous Implementation
- **Lack of Geospatial Visual Context**: The previous Streamlit apps used dropdown selection menus (`WELL-KG-01`, `WELL-KG-02`, etc.) without spatial awareness. Operators could not see field-level clustering, regional formation context, or geographic proximity of failing wells.
- **Synchronous / Blocking UI**: Streamlit's full-page rerun paradigm caused chart re-rendering delays whenever filters changed or AI queries were dispatched.
- **Voice Interactivity Missing**: Previous tools were purely text-input or script-driven with no voice capabilities (Speech-to-Text or Text-to-Speech) for hands-free field operations.
- **Cloud Dependency on Startup**: The prototypes crashed if BigQuery or Vertex AI credentials were not present, preventing instant local testing and offline capability.

---

## 3. Architectural Enhancements in WellPulse
1. **Interactive Leaflet GIS Mapping**: Real geospatial coordinates in the Permian Basin with custom status pins, pulsing alerts on critical wells, and instant click-to-focus.
2. **Decoupled Client-Server (React + FastAPI)**: FastAPI backend provides fast JSON APIs and asynchronous Gemini AI calls. React + Tailwind frontend provides instant 60fps UI responsiveness without page reloads.
3. **Voice AI Pipeline**: Native browser Web Speech API for low-latency Speech-to-Text (STT) and speech synthesis (TTS) paired with contextual prompt injection.
4. **Resilient Local Execution**: Includes a synthetic data generator producing 24 months of physics-consistent telemetry (BOPD, MCFD, Water Cut, Tubing/Casing Pressure, and Workover logs). The system functions 100% locally with an intelligent local reasoning engine, and seamlessly elevates to Gemini 2.5 when an API key is provided.
