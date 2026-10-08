# Business Requirements Document (BRD)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 0.5.0-draft (v0.5 canonical expansion)  
**Date:** 2026-10-08  
**Status:** In progress (v0.5 expansion; canonical brief: [v05_change_brief.md](./v05_change_brief.md))  
**Author:** Energy Operations & AI Engineering Team  
**Source of truth:** [`docs/v05_change_brief.md`](./v05_change_brief.md) (canonical for v0.5); [`verbatim.md`](../verbatim.md) (repo root for v0.4 baseline). Feedback U-1..U-7 from brief §1 governs v0.5.  
**Companion docs:** [features.md](./features.md) · [BDD.md](./BDD.md) · [SDD.md](./SDD.md) · [build.md](./build.md) · [checklist.md](./checklist.md) · [DELEGATION.md](./DELEGATION.md) · [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) · [v05_change_brief.md](./v05_change_brief.md). Routes: [SDD.md](./SDD.md) §13 and brief §9 are authoritative.  

---

## 1. Executive Summary
WellPulse provides real-time well health triage, automated decline attribution, and conversational AI diagnostics for upstream oil and gas production and workover operations. Operating across hundreds of active wellheads requires balancing immediate flow assurance and mechanical integrity against long-term reservoir depletion. WellPulse delivers a high-density, map-based operational interface prioritizing well assets into computed health buckets (TC-020), provides immediate drilldown into 24-to-60-month historical production and maintenance curves, and empowers engineers with a voice-enabled conversational AI agent for hands-free diagnostics, next-best-action recommendations, and counterfactual justifications.

### 1.1 v3.0 Demo Objective
The primary objective of v3.0 is demonstrating holistic production and workover AI capabilities to Ajay Ratan, Executive Director (Head of Workover Operations), ONGC Institute of Drilling and Well Engineering (IDWE), Dehradun.

Verbatim requirement:
> *"So I am meeting the head of the workover operations in ONGC. And for them I need to showcase the capabilities in production and workover operations."*

The operational scope expands from a single field (Geleki) to three ONGC Assam fields: Geleki, Lakwa, and Lakhmani. All underlying data across the platform is synthetic and representative; the application explicitly acknowledges this representative status whenever asked.

### 1.2 v0.5 Expansion Objectives (Answer Canvas & Multimodal Workover Intelligence)
Following user feedback on 2026-10-08 (U-1..U-7 in [`v05_change_brief.md`](./v05_change_brief.md)), WellPulse v0.5 transforms from a monolithic "everything at once" well dump into a **question-driven answer canvas**. When an engineer asks a question, the middle panel surfaces only the specific matching view (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`), while chat answers stay concise (≤ 3 sentences). In addition, v0.5 introduces a **multimodal success engine** (presented as an art-of-the-possible multimodal neural network, powered by a deterministic demo scorer per Decision D-32) ranking the top 3 interventions with calibrated P(success), look-alike analog wells, top drivers, and an architecture diagram of the production Vertex AI path; an **expandable middle panel** with the conversational agent as command centre; a **printable HTML field report** with wellbore schematics for workover crews; and closes 6 synthetic data gaps across all 412 wells.

---

## 2. Business Objectives & Value Proposition
WellPulse maximizes operational uptime and streamlines workover decisions across the asset lifecycle through ten core business objectives:

1. **Reduce Mean Time to Detect (MTTD) Production Anomalies**: Identify SRP pump wear, gas-lift valve failure, wax, scale and sand problems within minutes rather than days.
2. **Prevent Catastrophic Well Downtime**: Computed health triage (TC-020) ensures the most critical wells receive immediate operational attention.
3. **Preserve Operational Knowledge**: Ingest and surface historical workover interventions, chemical treatments, and mechanical repairs so past lessons inform today's decisions.
4. **Hands-Free Operational Intelligence**: Enable field and control room engineers to interact verbally with well data, accelerating root-cause analysis and operational planning.
5. **Local-First Reliability**: The app runs locally with one command; if Vertex AI is unreachable it degrades to a text fallback that never fabricates numbers.
6. **Explain Production Decline Root Causes** — T1: *"why did the production decline? Was it human factor, controllable factor"*. Attribute lost barrels across human-process, controllable (equipment, operational), and uncontrollable (subsurface, external) factors.
7. **Diagnose and Prescribe with Explainability** — T1: *"classification algorithm… 15 type of interventions"*; *"next best action… currently not there"*; T2: *"why not just wax removal?"*. ML classifier over 15 intervention classes plus a next-best-action engine using production, well history and construction, and a "why this, not that" defence.
8. **Deliver Asset-Manager Visibility** — T1: *"Which particular field is not performing?"*. Identify which field underperforms against target, and why.
9. **Automate Field-Engineer Dossiers** — T1: *"aggregate all the history and give it to the person who is going to the field operations"*. Consolidated pre-visit dossier of mechanical, production and intervention history.
10. **Enable Real Gemini Live Voice** — T1: *"Gemini Live is not working well in the current build"*. True bidirectional streaming audio (WebSocket + AudioWorklet), replacing today's text-chat wrapper and browser TTS. v3.0 is audio-only: camera/image input ("multimodal", WS-5) is out of scope. Push-to-talk plus an open-mic hands-free option; the `FIELD_ENGINEER` persona keeps Live voice.
11. **Question-Driven Answer Canvas (U-1, U-2)**: Eliminate monolithic well-history dumps by displaying only the specific view matching the user's targeted inquiry in the middle panel (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`), keeping conversational responses focused and concise (≤ 3 sentences).
12. **Expandable Operational Command Centre (U-3)**: Allow the middle answer canvas to expand over the map area for deep wellbore schematics and time-series analysis while pinning the AI agent on the right as a persistent operational command centre.
13. **Top-3 Interventions with P(Success) & Multi-modal Explainability (U-4)**: Deliver ranked top 3 candidate interventions (primary + 2 alternatives) plus `NO_JOB_JUSTIFIED`, each with calibrated P(success), expected uplift, rig-days, qualitative cost band (`LOW`/`MED`/`HIGH`), operational risks, look-alike analog wells, and driving features.
14. **Multimodal Success Engine (U-5, D-32)**: Present a multimodal neural network as the intervention ranking engine with an architecture diagram panel showing fusion of 24-month production time series, static mechanical/geology features, and history. Compute believable, deterministic P(success) via the demo scorer (`backend/app/analytics/tools/success_engine.py`) combining `ic-hgb-v1` mechanism probabilities, historical field base rates with Bayesian shrinkage, and k=5 analog well success rates.
15. **Field Workover Crew Readiness via Printable Field Report (U-6)**: Generate an on-demand, printable A4 HTML field report with ONGC branding, wellbore architecture SVG, completion diagrams, and an actionable job program for field execution.

---

## 3. User Personas & Core Journeys
WellPulse supports field, engineering, and executive personas governed by three tool-enforced RBAC roles (`ED`, `ASSET_MANAGER`, `FIELD_ENGINEER`).

> **Note on Baseline KPIs**: The legacy KPI line (`Fleet Total: 50 | Healthy: 32 | Attention: 12 | Critical: 6`) represents the v2 baseline derived from hard-coded synthetic statuses and will be superseded by dynamically computed health classifications (TC-020).

### 3.1 Persona A: Production & Field Engineer ("Sarah")
- **Responsibility**: Daily monitoring of 40–80 wells across the Geleki Tipam and Barail formations (Assam Asset, ONGC).
- **Pain Point**: Sifting through dense tabular SCADA logs to pinpoint which wells are choked by paraffin wax or experiencing water breakthrough.
- **Journey**: Opens WellPulse satellite map view → views tagged wellheads over aerial terrain → filters by "Needs Attention" & "Critical" → clicks a red wellhead → inspects the 24-month oil/gas/pressure decline → speaks to the AI: *"What caused the sharp pressure drop on August 12?"* → receives clear diagnostic answer.

### 3.2 Persona B: Workover & Interventions Specialist ("Carlos")
- **Responsibility**: Planning mechanical interventions, hot oil wax circulation, water shut-off (WSO) polymer squeezes, and gas lift valve maintenance.
- **Pain Point**: Historical workover reports are buried in siloed archives; difficult to evaluate whether a previous hot oil wash or polymer plug was effective.
- **Journey**: Selects an amber well → reviews the Workover History timeline → queries voice agent: *"What was the flow delta from the last hot oil wax treatment?"* → asks: *"Recommend an intervention plan for current water cut surge"*.

### 3.3 Persona C: Asset Operations Director ("Marcus")
- **Responsibility**: Fleet-wide production volume, operational uptime, and safety compliance across monitored assets.
- **Pain Point**: Needs high-level executive visibility into fleet health distribution without navigating complex SCADA software.
- **Journey**: Reviews top KPI bar → observes geographic clusters of failing wells over satellite imagery → exports prioritized triage list.

### 3.4 Executive Director (ED)
- **Role & Access**: RBAC role `ED` (gated at tool layer per D-8).
- **Responsibility**: Strategic asset governance, high-level fleet uptime, and cross-field capital and operational allocation.
- **Key Question**: Asks high-level L1/L2 questions: *"Can you give me the 5-year production history field-wise?"* and *"How many wells in Geleki are sick or have lost production?"*
- **What They May See**: Field-level aggregates, macro trend plots, and health roll-ups; raw operational tallies and granular mechanical logs hidden by default.

### 3.5 Asset Manager
- **Role & Access**: RBAC role `ASSET_MANAGER` (gated at tool layer per D-8).
- **Responsibility**: Field performance management, target achievement, and operational prioritization across Geleki, Lakwa, and Lakhmani.
- **Key Question**: *"Which particular field is not performing vs target and why?"*
- **What They May See**: Cross-field comparisons, deferred barrels broken down by factor (human-process, controllable, uncontrollable), and prioritized candidate lists for intervention.

### 3.6 Production Engineer
- **Role & Access**: Maps to RBAC role `ASSET_MANAGER` for access permissions (not a separate RBAC role).
- **Responsibility**: Granular well performance monitoring, decline curve analysis, and intervention candidate selection.
- **Key Question**: Uses L3–L5 workflows: *"Can you give me a priority list of all wells needing intervention?"*, *"Show me production history and offset wells"*, and *"Why recommend this intervention over an alternative?"*
- **What They May See**: Ranked intervention priority queues, 2–3 year multi-curve telemetry with offset wells, next-best-action (NBA) recommendations, and counterfactual trade-off tables.

### 3.7 Field Engineer
- **Role & Access**: RBAC role `FIELD_ENGINEER` (gated at tool layer per D-8).
- **Responsibility**: On-site execution, wellhead servicing, rig operations, and adherence to standard operating procedures (SOPs).
- **Key Question**: *"What is the mechanical history and SOP checklist for this well before my site visit?"*
- **What They May See**: Single-well mechanical schematics, past intervention summaries, SOP guidelines, and generated well dossier PDFs; restricted from viewing field-level financial roll-ups.

---

## 4. Detailed Functional Requirements

### 4.1 Geospatial Satellite Map & Well Prioritization (BRD-F01)
- **F01.1**: The platform must display an interactive **Satellite Map** plotting monitored wellheads with representative coordinates across the Geleki, Lakwa, and Lakhmani fields in Sivasagar, Assam (`26.77° N, 94.69° E`).
- **F01.2**: Every wellhead marker on the satellite map must display a **permanent tagged badge showing the well name/ID** (e.g., `GK-129`, `LKW-047`, `LKM-061`) and an authentic oil derrick icon, eliminating confusing currency signs or cryptic symbols.
- **F01.3**: Each well must be visually categorized by its **computed** TC-020 health bucket (the v2 hard-coded thresholds and seeded statuses are superseded):
  - 🟢 **Healthy / Optimal** = `PRODUCING_OK`.
  - 🟡 **Needs Attention / Warning** = `AT_RISK` or `UNDERPERFORMING`.
  - 🔴 **Critical / Failed** = `NOT_PRODUCING`, with an active visual pulsing radar ring.
- **F01.4**: Operators must be able to toggle between **Satellite Field Imagery** and **Dark SCADA GIS** layers with one click.
- **F01.5**: Operators must be able to filter wells by status (All, Healthy, Attention, Failed) and search by Well Name, ID, or Formation.
- **F01.6**: Critical wells must feature an animated visual cue (pulsing radar ring) on the map to draw immediate focus.
- **F01.7**: Operators must be able to filter by field (Geleki, Lakwa, Lakhmani) and cluster, with field boundaries drawn (T2: *"they can see different fields, right, clearly, and the wells"*).

### 4.2 Historical Telemetry & Analytics (BRD-F02)
- **F02.1**: Clicking a wellhead must display comprehensive historical telemetry charts covering 24 to 60 months.
- **F02.2**: The telemetry must track:
  - Oil Production (BOPD - Barrels of Oil Per Day)
  - Gas Production (MCFD - Thousand Cubic Feet Per Day)
  - Water Cut (% - percentage of produced water)
  - Tubing Pressure vs. Casing Pressure (psi)
  - **New in v3.0** (WS-6: *"rate, pressure, temperature, water cut, GOR, artificial lift metrics"*; Turn 4 shows gas-lift injection pressure): wellhead temperature (`wht_degc`), GOR (`gor_scf_bbl`), SPM / runtime for SRP wells, gas-lift injection rate (`gl_inj_rate_mscfd`) and pressure (`gl_inj_pressure_kgcm2`) for gas-lift wells (D-19).
- **F02.3**: Users must have time-range toggles (Last 30 Days, 6 Months, 1 Year, 2 Years, 5 Years).
- **F02.4**: Past interventions must be marked on the production chart (T2: *"on that particular log or plot, it should also tell me what are the different interventions happened in the past"*).

### 4.3 Workover & Intervention History (BRD-F03)
- **F03.1**: The platform must present a chronological timeline of all prior workovers and well interventions.
- **F03.2**: Each workover record must capture: Date, Intervention Type (catalogue job code and one of the 15 intervention classes, e.g. pump change, gas-lift valve change, wax removal, water shut-off squeeze, sand cleanout, re-perforation), Cost Band (LOW/MED/HIGH) + Rig-Days (D-1), Equipment (rig / rigless unit; no vendor name), Description, and Post-Intervention Flow Delta (+/- BOPD).

### 4.4 Voice-Enabled AI Conversational Agent (BRD-F04)
- **F04.1**: The right-side pane must feature an interactive voice-enabled conversational AI agent.
- **F04.2**: The agent must answer by **calling deterministic tools** for the selected well, field or persona (D-10, D-12); it must not rely on well JSON stuffed into its prompt, so every number traces to a tool return.
- **F04.3**: Operators must be able to ask questions via natural voice input (Speech-to-Text) using an intuitive push-to-talk or streaming voice session.
- **F04.4**: The agent must respond both in formatted textual chat and audible spoken voice (Text-to-Speech / Streaming Audio).
- **F04.5**: Audio input/output must be complemented with a dynamic waveform or speaking animation.

### 4.5 Prescriptive Recommendations Engine (BRD-F05)
- **F05.1**: The agent must generate structured, engineering-sound recommendations for selected wells.
- **F05.2**: Recommendations must outline: Proposed Action, Urgency Level (Immediate / High / Routine), Cost Band (LOW/MED/HIGH) + Rig-Days (D-1), Expected Flow Uplift (+BOPD), and Risk Mitigation factor.

### 4.6 Business Acceptance: 5-Level Question Hierarchy (L1–L5)
The platform must successfully resolve executive and operational inquiries structured across five progressive levels of detail:

| Level | Question (Verbatim Transcript 2) | Accepted When |
|---|---|---|
| **L1** | *"Can you give me the production history, the past let's say 5 year production data field-wise?"* then *"Can you give me a plot?"* | Agent answers with summary findings first, then plots monthly per-field aggregate for 60 months (2021-10-01…2026-09-30), drawing verified numbers from tool `TC-028`. |
| **L2** | *"Can you tell me how many wells in Geleki are … either sick or they have lost production?"* | Agent reports well counts grouped by computed health bucket (not hard-coded) derived from tool `TC-020`. |
| **L3** | *"Can you give me a priority list of all the wells that needs intervention?"* | Agent presents a ranked priority list from `TC-022` batch execution (rank = deferred bbl × p_success ÷ rig-days, shown with cost band; replaces verbatim NPV ranking), detailing root cause and justification for each candidate well. |
| **L4** | *"Can you tell me more about this well and show me the production data, the production history?"* | Agent displays a 2–3 year multi-curve production plot with historical interventions marked, alongside offset/nearby well comparisons from `TC-029`. |
| **L5** | *"Okay, what are the next best recommended interventions?"* then *"Why are you recommending this against an alternative? … why not just wax removal?"* | Agent outputs Top-3 ranked actions from `TC-022` and presents a side-by-side counterfactual evidence table from `TC-027`; demonstrated on hero well `GK-129` ("why squeeze, not wax removal") with backup well `LKM-061`. |

### 4.7 New Functional Requirements (BRD-F06–F13)
Detailed specifications for these requirements are provided in [features.md](./features.md):

- **BRD-F06 (F-01)**: **Decline Attribution** — T1: *"Was it human factor, controllable factor, what kind of factors"*. Decompose and attribute lost production barrels across human-process, controllable (equipment, operational), and uncontrollable (subsurface, external) factors.
- **BRD-F07 (F-03, F-04, F-13)**: **ML Classifier, Next-Best-Action (NBA) & Counterfactual Justification** — T1: *"15 type of interventions"*, *"next best action"*; T2: *"Why are you recommending this against an alternative?"*. Machine learning classifier covering 15 intervention classes; ranked candidate actions and side-by-side evidence tables justifying why a recommended job is chosen over alternatives.
- **BRD-F08 (F-05, F-08, F-09, F-11)**: **Multi-Field Hierarchy & Field Performance** — T1: *"Geleki… Lakwa… Lakhmani… three areas, with their individual cluster"*, *"Which particular field is not performing?"*; T2: *"5 year production data field-wise"*. Asset hierarchy across the three fields; identify underperforming fields against target.
- **BRD-F09 (F-06, F-10, F-14)**: **Well Dossier, PDF Corpus & SOP Retrieval** — T1: *"aggregate all the history"*, *"generate the documents of PDF files"*; T2: *"The SOPs"*. Pre-visit PDF dossiers (English-only, Q-2; lithology from `formation_tops`); recommendations grounded in cited PDFs and SOPs (TF-IDF search in v3.0, D-17).
- **BRD-F10 (F-07)**: **Real Gemini Live Streaming Voice** — T1: *"check how it is built in that Drilling Intelligence"*. Bidirectional low-latency streaming voice over WebSockets with AudioWorklet (16 kHz uplink / 24 kHz downlink), replacing browser-only TTS.
- **BRD-F11 (F-16, optional)**: **Role-Based Access Control (RBAC)** — T2: *"Executive Director… versus a field engineer… If it is overcomplicating, we can leave it"*. Three roles (`ED`, `ASSET_MANAGER`, `FIELD_ENGINEER`) gated at the tool layer (D-8).
- **BRD-F12 (F-15)**: **Medallion Lakehouse in BigQuery** — T2: *"showcase that in the Medallion architecture… Lakehouse"*. Bronze / Silver / Gold in BigQuery `asia-south1` (D-9); Bronze files in existing `gs://workover-operations-agentic-ai-datalake`. Vertex AI Search is optional later (D-17).
- **BRD-F13 (F-17, F-18)**: **Multi-screen demo and 5-level flow** — T2: *"different screens opened"*, *"do you see the hierarchy of question and answering?"*. Acceptance per §4.6.

### 4.8 v0.5 Functional Requirements (BRD-F14–BRD-F19)
Detailed technical specifications and BDD mappings are provided in [features.md](./features.md) and [`v05_change_brief.md`](./v05_change_brief.md):

- **BRD-F14 (F-20, F-21)**: **Question-Driven Answer Canvas & Command Centre (Stage AC)**
  - Replaces the monolithic all-in-one Deep Dive with an answer canvas: middle panel surfaces only the view matching the user's specific inquiry (`overview`, `production`, `interventions`, `wellbore`, `pressures`, `diagnosis`, `recommendation`, `compare`, `nearby`, `report`) via deterministic routing `pickCanvasView` (D-25).
  - Chat responses are strictly capped at ≤ 3 sentences plus an optional collapsed card; full-history data dumps in chat are prohibited.
  - Middle panel can expand over the map area to give maximum room for logs and diagrams, keeping the voice/chat agent docked on the right as the command centre; pressing ESC or clicking restore restores the split map view.
- **BRD-F15 (F-22)**: **Synthetic Data Gap Closure (Stage DG)**
  - Closes 6 structural data gaps across all 412 wells in `well_master`: `tubing_tally` (WH-06), `deviation_survey` (WH-08), `barrier_tests` (WH-14), `wellhead_rating` (WH-14), `fluid_hazards` (WH-13), and `fishing_records` (WH-10).
  - Deterministic generation (seed `20261008`), written to parquet landing and bronze → silver in BigQuery (D-19).
  - Every row carries `is_synthetic=true`, `_source_system='wellpulse_dg_v1'`, and `_batch_id` (D-29); read access via `TC-033` and endpoints (`/tubing-tally`, `/deviation`, `/integrity`).
- **BRD-F16 (F-23)**: **Multimodal Success Engine (Stage NN, D-32)**
  - Presented to users as an art-of-the-possible multimodal neural network combining 4 modalities: 24-month production time series (1D-CNN/GRU), static geology and mechanical casing/tubing features, decline attribution and health context, and candidate intervention embeddings.
  - Per Decision D-32, **no model training, no Vertex AI training job, and no synthetic data regeneration are executed in v0.5**.
  - All numbers are computed by a deterministic demo scorer (`backend/app/analytics/tools/success_engine.py`): `P(success | c) = clip(p_mechanism(c)^0.5 × (0.5·base_rate + 0.5·analog_rate), 0.05, 0.95)`, combining real `ic-hgb-v1` mechanism probabilities with historical field base rates (Bayesian shrink to asset) and k=5 analog well success rates.
  - Full training on Vertex AI (custom job in `us-central1` + Model Registry) is presented in the "How did you decide?" panel as an architecture diagram showing the production path.
- **BRD-F17 (F-24)**: **Top-3 Recommendations with Analogs & Attributions (Stage NN, AC)**
  - Tool `TC-030` (`recommend_interventions(well_id, k=3)`) returns top 3 interventions (primary + 2 alternatives) plus `NO_JOB_JUSTIFIED`, ranked by deferred bbl × p_success ÷ rig-days with qualitative cost band (`LOW`/`MED`/`HIGH`).
  - Explainability ("How did you decide?"): evidence chain (signals → mechanism → candidate), look-alike analog wells (`TC-031`, k=5; cosine similarity on standardised `build_features` vectors that ran candidate c), top 3 feature drivers from SHAP on `ic-hgb-v1`, and the neural network architecture diagram.
  - Endpoints: `GET /api/wells/{id}/recommendations?k=3` and `GET /api/wells/{id}/similar?class=`. Strictly no point currency estimates (D-1).
- **BRD-F18 (F-25)**: **Printable HTML Field Report & Job Program (Stage FR)**
  - Tool `TC-032` generates an on-demand, printable A4 HTML field report for workover crews via `GET /api/wells/{id}/report?intervention=<class>`, opening in the expanded middle panel iframe.
  - Contains sections WH-01…WH-19 of `well_history_template.md`: ONGC branding (logo or fallback text wordmark "ONGC", D-30), wellbore architecture SVG, candidate job program (steps, rig class, kill fluid weight from reservoir pressure, barriers, risks, contingencies, SOP citation), and top-3 recommendation rationale.
  - Rendered server-side with Jinja2 from deterministic tool returns; 100% fact-validated through `facts.json` sidecar. Chat shows a single-line link to open the report.
- **BRD-F19 (F-26)**: **11-Step Demo Flow & Verification (Stage DF)**
  - End-to-end 11-step demo script (Lakwa → `LKW-019`: Field compare → Sick wells → Priority list → Overview → Production → Interventions → Wellbore → Diagnosis → Recommendation top 3 → Compare why not sand cleanout → Prepare me for field).
  - Evaluated in chat and voice with +12 canvas routing test cases in `backend/eval/` (≥ 90% accuracy).

---

## 5. Non-Functional Requirements

| ID | Category | Requirement Description |
|---|---|---|
| **NFR-01** | Performance | Map pin rendering and initial data load < 1.0 second for all three fields (142 + 160 + 110 = 412 wells; D-2, D-11). |
| **NFR-02** | Local-First | Application must run completely locally on `localhost` via a single startup command. |
| **NFR-03** | Resilience & Integrity | If external LLM APIs are unreachable or unconfigured, the system must fall back to an intelligent local rule-based simulation engine without failing; fallback must return `UNAVAILABLE` or `LOW_CONFIDENCE` rather than fabricate numbers. |
| **NFR-04** | Usability | Dark-mode SCADA/Energy Operations interface compliant with contrast standards. |
| **NFR-05** | Browser Compatibility | Chrome and Edge supporting Web Speech API and AudioWorklet (16 kHz uplink / 24 kHz downlink) for real Gemini Live streaming voice. |
| **NFR-06** | Reproducibility | Synthetic data generation must be seed-locked with fixed historical dates (2021-10-01…2026-09-30) rather than dynamic dates relative to execution time (`now()`). |
| **NFR-07** | Voice Latency | Gemini Live first audio response latency must be ≤ 2.5 seconds on a warm Cloud Run container instance. |

---

## 6. Success Metrics
System performance, data fidelity, and operational efficacy are validated against twelve quantifiable criteria:

| ID | Metric | Target | How Verified |
|---|---|---|---|
| **SM-01** | Traceable Numbers | 100% of on-screen and spoken numbers trace directly to a verified tool return, database table row, or cited technical document | BDD integrity scenarios and automated evaluation |
| **SM-02** | Refusal When No Job Justified | Agent returns `NO_JOB_JUSTIFIED` for well `LKM-090` (reservoir decline confirmed by offset wells) and refuses to recommend an unneeded job | BDD test scenario |
| **SM-03** | Voice Session Resilience | Gemini Live session survives a forced network reconnection with conversational context intact; gracefully falls back to text chat after 3 failed reconnect attempts | BDD F-07 test scenarios |
| **SM-04** | Field Performance Attribution | Agent correctly identifies the underperforming field along with the primary driver; Lakwa designed at about −18% vs target (design target, pinned after Stage N) | BDD F-09 test scenarios |
| **SM-05** | 5-Level Question Flow | Complete L1–L5 question hierarchy executes smoothly end-to-end without manual user intervention | Automated Playwright test and evaluation suite |
| **SM-06** | ML Classifier Quality (Gate Q) | Holdout macro-F1 0.70–0.92 (upper bound = leakage ceiling), top-3 accuracy ≥ 0.90, and Expected Calibration Error (ECE) ≤ 0.08 | Offline model evaluation report |
| **SM-07** | Canvas Routing Accuracy (Gate AC, DF) | ≥ 90% routing accuracy across 12 eval cases; 10 demo phrases route to the correct canvas view; zero full-history dumps in chat | Automated eval suite in `backend/eval/` |
| **SM-08** | Chat Answer Conciseness | ≤ 3 sentences per chat response, accompanied by an optional collapsed card; no monolithic history dumps | Chat length verification and demo assertions |
| **SM-09** | Field Report Performance & Fidelity (Gate FR) | p95 < 3.0 s local render across all 412 wells; 100% fact verification via `facts.json` sidecar; A4 print layout verified | `test_field_report.py` and print layout validation |
| **SM-10** | Multimodal Demo Gate (Gate NN) | Top 3 render for all producing wells; deterministic P(success) in [0.05, 0.95] stable across calls; analog counts recomputed from data; explanation panel shows all 4 elements; plausibility review GK-129, LKW-019, LKM-061 passes (D-32) | Demo verification tests and orchestrator review |
| **SM-11** | Synthetic Data Gap Parity (Gate DG) | 100% well coverage across all 6 DG tables with `is_synthetic=true` and 0 consistency violations | Unit tests in `backend/tests/unit/test_dg_consistency.py` |
| **SM-12** | End-to-End Demo Script (Gate DF) | 11/11 steps of Lakwa → `LKW-019` demo flow pass smoothly in chat and voice without manual intervention | Automated demo runner (`docs/demo_flow.md`) |

---

## 7. Constraints & Scope Boundaries
Implementation and operational execution must adhere strictly to six non-negotiable constraints, along with defined v0.5 scope boundaries:

- **C-01: No Fabricated Numbers**: Tools must return `UNAVAILABLE` or `LOW_CONFIDENCE` rather than guess or extrapolate. Hard-coded recommendations containing fabricated cost estimates, uplifts, or payback periods are prohibited and must be replaced.
- **C-02: Cost Banding Only**: Operational costs must be expressed strictly as a qualitative cost band (`LOW` / `MED` / `HIGH`) plus rig-days (Decision D-1). Point estimates in currency (such as INR, USD, or lakhs) are strictly prohibited.
- **C-03: Synthetic Representative Data**: All operational telemetry, well logs, and geographic coordinates near Sivasagar, Assam are synthetic and representative (Decision D-3); the platform must clearly declare data as synthetic if queried.
- **C-04: Trilingual Data Integrity**: The data integrity rules and zero-hallucination standards must hold equally across all three supported voice and chat interaction languages (Hinglish default, English, Hindi).
- **C-05: Cloud Infrastructure & Model Controls**: GCP project `workover-operations-agentic-ai` (D-4, resolved): Cloud Run service `wellpulse-app` in `us-central1`, BigQuery in `asia-south1`. Calls go through Vertex AI with Application Default Credentials; the API key is removed. Text model stays `gemini-3.8-flash` (D-13, resolved); the Live model is verified by listing models.
- **C-06: Deployment Gate**: Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources. This covers BigQuery DDL apply and the Cloud Run deploy of `wellpulse-app` (smoke test after); see [EXECUTION_PLAN.md](./EXECUTION_PLAN.md).

### 7.1 Scope & Out-of-Scope (v0.5 Boundaries)

| Dimension | In-Scope (v0.5) | Out-of-Scope (v0.5) | Rationale / Decision |
|---|---|---|---|
| **Model Training & Serving** | Multimodal NN presented as engine; deterministic demo scorer in `backend/app/analytics/tools/success_engine.py` | **No model training, no Vertex AI training job, no data regeneration in v0.5**; no online endpoint | Art-of-the-possible demo engine; production path (Vertex custom training + Model Registry) described in architecture panel (D-32) |
| **Financial / Economics** | Qualitative cost bands (`LOW` / `MED` / `HIGH`) and rig-days | **No point currency estimates (₹ / USD / Lakhs)**; no NPV, ROI, or payback calculations | Adheres strictly to core integrity rule C-02 and Decision D-1 |
| **Operational Telemetry** | 60 months synthetic telemetry and 6 synthetic gap tables for 412 wells | **No live SCADA feeds or real ONGC corporate database connections** | Demonstrates complete platform capabilities using representative synthetic data (D-3, C-03) |
| **Interface / Interaction** | Question-driven answer canvas (10 views), expandable panel, streaming voice (AudioWorklet) | **No camera / video streaming input** to Live voice | Audio-only bidirectional streaming satisfies field operations without video overhead |
| **Field Artefact Delivery** | Printable A4 HTML field report (`GET /api/wells/{id}/report`) and dossier PDF | **No offline-first native mobile application** | Printable, self-contained HTML/PDF reports provide immediate field-readiness on any device |
