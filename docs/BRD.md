# Business Requirements Document (BRD)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 3.0.0 (v0.4 verbatim expansion)  
**Date:** 2026-10-07  
**Status:** Approved for build (all decisions resolved; autonomous run authorised by user 2026-10-07)  
**Author:** Energy Operations & AI Engineering Team  
**Source of truth:** [verbatim.md](../verbatim.md) (repo root)  
**Companion docs:** [features.md](./features.md) · [BDD.md](./BDD.md) · [SDD.md](./SDD.md) · [build.md](./build.md) · [checklist.md](./checklist.md) · [DELEGATION.md](./DELEGATION.md) · [EXECUTION_PLAN.md](./EXECUTION_PLAN.md). Routes: [SDD.md](./SDD.md) §13 is authoritative.  

---

## 1. Executive Summary
WellPulse provides real-time well health triage, automated decline attribution, and conversational AI diagnostics for upstream oil and gas production and workover operations. Operating across hundreds of active wellheads requires balancing immediate flow assurance and mechanical integrity against long-term reservoir depletion. WellPulse delivers a high-density, map-based operational interface prioritizing well assets into computed health buckets (TC-020), provides immediate drilldown into 24-to-60-month historical production and maintenance curves, and empowers engineers with a voice-enabled conversational AI agent for hands-free diagnostics, next-best-action recommendations, and counterfactual justifications.

### 1.1 v3.0 Demo Objective
The primary objective of v3.0 is demonstrating holistic production and workover AI capabilities to Ajay Ratan, Executive Director (Head of Workover Operations), ONGC Institute of Drilling and Well Engineering (IDWE), Dehradun.

Verbatim requirement:
> *"So I am meeting the head of the workover operations in ONGC. And for them I need to showcase the capabilities in production and workover operations."*

The operational scope expands from a single field (Geleki) to three ONGC Assam fields: Geleki, Lakwa, and Lakhmani. All underlying data across the platform is synthetic and representative; the application explicitly acknowledges this representative status whenever asked.

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
System performance, data fidelity, and operational efficacy are validated against six quantifiable criteria:

| ID | Metric | Target | How Verified |
|---|---|---|---|
| **SM-01** | Traceable Numbers | 100% of on-screen and spoken numbers trace directly to a verified tool return, database table row, or cited technical document | BDD integrity scenarios and automated evaluation |
| **SM-02** | Refusal When No Job Justified | Agent returns `NO_JOB_JUSTIFIED` for well `LKM-090` (reservoir decline confirmed by offset wells) and refuses to recommend an unneeded job | BDD test scenario |
| **SM-03** | Voice Session Resilience | Gemini Live session survives a forced network reconnection with conversational context intact; gracefully falls back to text chat after 3 failed reconnect attempts | BDD F-07 test scenarios |
| **SM-04** | Field Performance Attribution | Agent correctly identifies the underperforming field along with the primary driver; Lakwa designed at about −18% vs target (design target, pinned after Stage N) | BDD F-09 test scenarios |
| **SM-05** | 5-Level Question Flow | Complete L1–L5 question hierarchy executes smoothly end-to-end without manual user intervention | Automated Playwright test and evaluation suite |
| **SM-06** | ML Classifier Quality (Gate Q) | Holdout macro-F1 0.70–0.92 (upper bound = leakage ceiling), top-3 accuracy ≥ 0.90, and Expected Calibration Error (ECE) ≤ 0.08 | Offline model evaluation report |

---

## 7. Constraints
Implementation and operational execution must adhere strictly to six non-negotiable constraints:

- **C-01: No Fabricated Numbers**: Tools must return `UNAVAILABLE` or `LOW_CONFIDENCE` rather than guess or extrapolate. Hard-coded recommendations containing fabricated cost estimates, uplifts, or payback periods are prohibited and must be replaced.
- **C-02: Cost Banding Only**: Operational costs must be expressed strictly as a qualitative cost band (`LOW` / `MED` / `HIGH`) plus rig-days (Decision D-1). Point estimates in currency (such as INR, USD, or lakhs) are strictly prohibited.
- **C-03: Synthetic Representative Data**: All operational telemetry, well logs, and geographic coordinates near Sivasagar, Assam are synthetic and representative (Decision D-3); the platform must clearly declare data as synthetic if queried.
- **C-04: Trilingual Data Integrity**: The data integrity rules and zero-hallucination standards must hold equally across all three supported voice and chat interaction languages (Hinglish default, English, Hindi).
- **C-05: Cloud Infrastructure & Model Controls**: GCP project `workover-operations-agentic-ai` (D-4, resolved): Cloud Run service `wellpulse-app` in `us-central1`, BigQuery in `asia-south1`. Calls go through Vertex AI with Application Default Credentials; the API key is removed. Text model stays `gemini-3.8-flash` (D-13, resolved); the Live model is verified by listing models.
- **C-06: Deployment Gate**: Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources. This covers BigQuery DDL apply and the Cloud Run deploy of `wellpulse-app` (smoke test after); see [EXECUTION_PLAN.md](./EXECUTION_PLAN.md).
