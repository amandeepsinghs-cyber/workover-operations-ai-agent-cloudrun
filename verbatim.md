# Stakeholder Verbatim & Demo Expansion Requirements

**Date Recorded**: 2026-10-07  
**Target Organization**: Oil and Natural Gas Corporation (ONGC) — Institute of Drilling and Well Engineering (IDWE), Dehradun  
**Key Stakeholder**: Ajay Ratan, Executive Director (Head of Workover Operations)  
**Target Application**: Workover & Well Intervention AI Agent System (`workover_well_intervention`)  

---

## 1. Verbatim Audio Transcript

> "This for the context. So consider it as a verbatim. Just create a file called verbatim and I'll be explaining what do I need from this particular demo.
> 
> So I am meeting the head of the workover operations in ONGC. And for them I need to showcase the capabilities in production and workover operations.
> 
> So I am meeting the Institute of Drilling and Well Engineering, IDWE Dehradun. And the person is called Ajay Ratan, he's the Executive Director. Now this is the background in terms of who am I meeting.
> 
> So the demo that I would like to give, so this is one, and I'm also making it holistically of overall workover operations.
> 
> Now there are certain decisions to be made in workover operations. For example, what happened... So workover operations, let's take a step back and understand why do they happen:
> 
> So the production in a particular well declines, due to whatever reason, right?
> 
> First part is that we would like to know, okay, why did the production decline? Was it human factor, controllable factor, what kind of factors, right, that contributed?
> 
> Second is, we would like to know a predictive analysis: which of the wells are doing okay, which of the wells are not doing okay, which of the wells are not producing now. So again, this is I think already built.
> 
> Then we would like to diagnose why something has happened, in terms of, you know, maybe running machine learning algorithms on the production data, and on that data one can potentially run a classification algorithm because let's say we can assume 5 to 10 type of interventions can happen, or let's say 15 type of interventions.
> 
> Now depending on not just the production data, but also of the well history, the construction, one can recommend what is the next best action. So this is another feature that is needed, right, which is currently not there.
> 
> And I believe to enable all this, certain things are to happen:
> 
> One is, okay, every well, there should be multiple wells in an area, and there can be different areas. For example, currently we have Geleki, and I can also showcase that, okay, similarly you can have Lakwa, you can have Lakhmani. So that there are three areas, with their individual cluster.
> 
> Now again, so in this particular demo taking again one step further: so we answered a few questions on a particular cluster, on a well level, right? Why a particular well is not performing, what is a well intervention required...
> 
> We would also like to know the previous history of the well. So basically to showcase that at times when a person is going to the field, the previous history is not there, which becomes a problem, right? So we can aggregate all the history and give it to the person who is going to the field operations.
> 
> So again, enabling that real-time, Gemini Live. So this particular Gemini Live is not working well in the current build. It is working very good in Drilling Intelligence 2.0. So check how it is built in that Drilling Intelligence and we can learn from that.
> 
> Next pass I would say, we would also like to generate more data. So this is one field Geleki, I would also like to generate for, let's say two more clusters. I'm saying that let's say it is Lakwa and Lakhmani. There are two more clusters, build those wells as well.
> 
> Then there'll be another high level question that can be answered: This is for a let's say asset manager level: Which particular field is not performing? Or how, what is the performance at a field level, right? That question is not currently being answered by the current build.
> 
> Now to enable this a few things have to happen: We need to generate the documents of PDF files of you know, well interventions and other documents. I would need your help to define it, what do we need to do.
> 
> Generate a verbatim."

---

## 2. Requirement Breakdown & Strategic Work Streams

### Work Stream 1: Multi-Field Hierarchy & Geospatial Expansion
* **Current State**: Single field (`Geleki`).
* **Required Expansion**: 3 distinct fields / clusters with multiple wells each:
  1. **Geleki Field** (Assam Asset)
  2. **Lakwa Field** (Assam Asset)
  3. **Lakhmani Field** (Assam Asset)
* **High-Level Asset Manager View**:
  - Macro-level field performance comparisons ("Which field is underperforming?").
  - Aggregate field production vs. targets, uptime, water cut, and active intervention counts.

---

### Work Stream 2: Production Decline & Root Cause Factor Attribution
* **Decline Analysis**:
  - Predictive health screening: Categorize wells into *Healthy / Producing Normally*, *Marginal / At-Risk*, and *Shut-In / Zero Production*.
* **Causal Factor Disaggregation**:
  - Quantify root cause drivers: Controllable operational factors (choke setting, gas-lift rate, artificial lift pump failure), subsurface/reservoir factors (water breakthrough, sand influx, pressure depletion, scale), and human/operational factors (delayed maintenance, logistical bottlenecks).

---

### Work Stream 3: ML Diagnostic & Intervention Recommendation Engine (NBA)
* **Multi-Class Intervention Classification**:
  - 10 to 15 standardized well intervention archetypes (e.g., Gas Lift Valve Replacement, Squeeze Cementing / Water Shut-off, Acid Stimulation / Matrix Acidizing, Sand Cleanout / Bailing, ESP Replacement / Workover, Re-perforation, Tubing Leak Repair).
* **Next Best Action (NBA) Recommender**:
  - Evaluates real-time telemetry + historical well intervention track record + mechanical well construction/schematics.
  - Generates scored, actionable intervention recommendations with expected uplift (bopd), estimated cost, and risk profile.

---

### Work Stream 4: Field Engineer Workover Dossier & Historical Aggregation
* **Problem**: Field engineers dispatching to well pads often lack historical well records, prior workover logs, and completion schematics.
* **Solution**:
  - Automated "Field Operations Dossier" aggregating past intervention histories, well architecture, casing/tubing tallies, and lithology.
  - Generation of historical intervention PDF reports and completion dossiers.

---

### Work Stream 5: Gemini Live Voice/Multimodal Real-Time Assistant
* **Problem**: Gemini Live in the current `workover_well_intervention` build is underperforming / unstable.
* **Benchmark Reference**: **Drilling Intelligence 2.0** (`cloud_run_apps/Drilling-Intelligence-2.0`), which has a tested, production-grade implementation:
  - Architecture: `backend/app/agent/live_session.py`, `backend/app/api/ws_live.py`, `docs/adr/ADR-003-gemini-live-adk-proxy.md`.
  - Frontend: `frontend/src/live/liveClient.ts`.
* **Goal**: Align the Workover Gemini Live architecture with Drilling Intelligence 2.0 WebSocket proxy pattern for hands-free field technician operation.

---

### Work Stream 6: Synthetic Document & Telemetry Generation
* **Telemetry Data**: Production time series for Lakwa and Lakhmani fields (rate, pressure, temperature, water cut, GOR, artificial lift metrics).
* **Document Assets**: Synthetic historical PDF documentation (Well Intervention Reports, Daily Workover Logs, Well Completion Schematics, Chemical Treatment Logs) to ground the RAG and Gemini Live tools.

---

## 3. Verbatim Audio Transcript 2: Demo Flow & Architecture

> "So the demo flow would be something like this:
> 
> A person would open, so there will be different screens opened, like what we currently have the interface.
> 
> Then on the interface they can see different fields, right, clearly, and the wells where they are currently represented already.
> 
> Then if I ask a very first question: 'Can you give me the production history, the past let's say 5 year production data field-wise?' Right? So they have different fields, it should be able to give me that data, or at least tell me that data.
> 
> First it will tell, then I'll say: 'Can you give me a plot?' It should be able to plot it as well. You know what I mean? On a field level, so it is an aggregated of all the wells.
> 
> Then I will say, I will drill down to a particular field.
> 
> Then I will say: 'Can you tell me how many wells in Geleki are not... are either sick or they have lost production?' Then they will say this.
> 
> Then I will ask: 'Can you give me a priority list of all the wells that needs intervention?'
> 
> Then it should be able to give me a list.
> 
> Then I will ask, drill down to one particular well: 'Can you tell me more about this well and show me the production data, the production history?' It should be able to show me either 2-3 year history or 5 year history, whatever, let's say 2-3 years.
> 
> And on that particular log or plot, it should also tell me what are the different interventions happened in the past.
> 
> Then I should be able to ask: 'Okay, what are the next best recommended interventions?'
> 
> Then I should be able to ask: 'Why are you recommending this against an alternative?' Let's say perforation, I can say 'Okay why not just wax removal?' and something that is super deep.
> 
> Now to enable this, we need to generate a lot of documents, I see. The SOPs, and I should be able to showcase that in the Medallion architecture, and then we can that we can create a let's say Lakehouse, so to say.
> 
> And production data we can discuss whether it should go ultimately into BigQuery or if there is a better database to store production data or how it can be stored.
> 
> And yeah I think so far it is it is this, I will say.
> 
> And see if we can also build access based... we would like to also show access, role-based access in this. And also consider how it can be made role-based access. And what that demo flow can look like.
> 
> Let's say if an Executive Director is asking for a particular data versus a field engineer is asking for a data, what that data can be? Right, in case of field. If it is overcomplicating, we can leave it.
> 
> And do you see the the hierarchy of question and answering? So it should be able to generate some documents, give some aggregated data if needed, also drill down to a particular well, also give information of nearby wells.
> 
> And everything needs to be generated, right?
> 
> What I additionally want is that after the checklist and everything is created, first add this, the entire script to verbatim.md file.
> 
> And then once everything is created, I would like to give a delegation of what are the tasks that Opus would do and what are the tasks that can be outsourced to the Flash models. For example, the document generation can be given to the Flash models.
> 
> So this is how I would like to proceed and give me the verbatim of this and add the verbatim to verbatim.md file."

---

## 4. End-to-End Hierarchical Demo Script & Conversation Flow

The demo is structured as an interactive top-down drill-down journey reflecting real executive decision-making:

```
[Level 1: Multi-Field Macro Performance]
     │
     ▼
[Level 2: Sick Wells & Field Screening (Geleki)]
     │
     ▼
[Level 3: Prioritized Intervention Queue]
     │
     ▼
[Level 4: Well Deep Dive & Historical Overlay]
     │
     ▼
[Level 5: Next Best Action (NBA) & Counterfactual Defense]
```

### Turn 1: Macro Field-Level Aggregation & Plot
* **User Prompt**: *"Can you give me the past 5-year production data across all fields (Geleki, Lakwa, Lakhmani)?"*
* **Agent Response**: Summarizes oil/gas production trends, field-by-field water cut trends, and declining trajectories.
* **Follow-up Prompt**: *"Can you give me a plot of this field-level aggregated production?"*
* **Agent Response**: Renders interactive time-series plot comparing oil (bopd), water cut (%), and gas production aggregated across all wells per field.

### Turn 2: Field Drill-Down & Sick Well Screening
* **User Prompt**: *"How many wells in Geleki are currently sick or have lost production?"*
* **Agent Response**: Reports total well count in Geleki (e.g., 42 wells), categorized into:
  - *Healthy*: 26 wells
  - *Sick / Sub-optimal*: 11 wells (significant decline vs. baseline)
  - *Shut-In / Zero Production*: 5 wells
  - Summarizes primary contributing factor breakdown (e.g., 45% water breakthrough, 30% mechanical/lift failure, 25% sand influx/tubing scaling).

### Turn 3: Prioritized Intervention Ranking
* **User Prompt**: *"Give me a priority list of all wells in Geleki that need intervention."*
* **Agent Response**: Displays a ranked prioritization table based on estimated Net Present Value (NPV), uplift potential (bopd), risk index, and operational readiness:
  | Rank | Well ID | Current Status | Primary Symptom | Recommended Intervention | Est. Uplift | Est. Cost | Payback |
  |:---:|:---|:---|:---|:---|:---:|:---:|:---:|
  | 1 | GK-104 | Sick (80% drop) | Gas lift valve failure & wax | Gas Lift Valve changeout & hot oiling | +180 bopd | ₹18 Lakhs | 12 days |
  | 2 | GK-078 | Shut-in | Severe water cone | Water Shut-Off (Polymer gel / squeeze) | +220 bopd | ₹45 Lakhs | 28 days |
  | 3 | GK-112 | Sick | Sand bridging in perforations | Coiled Tubing Sand Cleanout | +140 bopd | ₹22 Lakhs | 19 days |
  | 4 | GK-045 | Sick | Mechanical tubing leak | Workover Rig Work (Tubing string replace) | +110 bopd | ₹65 Lakhs | 55 days |

### Turn 4: Single Well Deep-Dive & Historical Workover Overlay
* **User Prompt**: *"Tell me more about GK-104 and show me its 3-year production history with past interventions."*
* **Agent Response**:
  - Detailed well profile: Completion depth, reservoir formation (Barail/Tipam sand), current artificial lift setup (continuous gas lift), casing/tubing sizes.
  - Interactive 3-year production chart showing oil rate, gas-lift injection pressure, and water cut, **overlaid with event markers** for past workovers (e.g., *"June 2024: Acid wash"*, *"Nov 2025: Wireline wax scraping"*).
  - Nearby offset well context: Status and performance of neighboring wells on the same cluster pad (GK-102, GK-105).

### Turn 5: Next Best Action (NBA) Recommendation & Counterfactual Defense
* **User Prompt**: *"What is the next best recommended intervention for GK-104?"*
* **Agent Response**: Recommends: **Gas Lift Valve (GLV) replacement via slickline combined with chemical solvent soak for asphaltic wax deposition**. Outlines step-by-step SOP, required slickline unit, estimated duration (36 hrs), and expected post-job stabilization at 210 bopd.
* **Counterfactual Defense Prompt**: *"Why are you recommending GLV replacement and chemical soak instead of re-perforation or mechanical wax scraping?"*
* **Agent Response**: **Deep technical justification**:
  1. *Reservoir pressure check*: Wellhead flowing pressure indicates the reservoir zone still maintains 142 bar; inflow performance relationship (IPR) confirms the sand face is open, eliminating perforation skin as the root constraint.
  2. *Historical efficacy comparison*: Mechanical scraping was attempted 11 months ago and wax reformed within 45 days because the cold injection gas caused thermodynamic wax crystallization; chemical inhibition will address the precipitation temperature boundary.
  3. *Cost & Downtime delta*: Re-perforation requires a workover rig (₹65L, 14 days), whereas wireline GLV + solvent requires a slickline unit (₹18L, 2 days), delivering a 4.2x higher return on capital.

---

## 5. Medallion Lakehouse Architecture & Production Data Strategy

### Storage & Lakehouse Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                          BRONZE (Raw Layer)                            │
│  - Raw SCADA / Telemetry CSVs & Historian dumps (GCS)                  │
│  - Raw Well Intervention PDFs & Daily Workover Reports (DWRs) (GCS)    │
│  - Raw SOPs & Equipment Manuals (GCS)                                  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         SILVER (Curated Layer)                         │
│  - BigQuery: Cleaned, partitioned daily production time series         │
│  - BigQuery: Standardized Well Master (casing, perforation, lift type) │
│  - Vector Store / Vertex Search: Parsed & chunked PDFs (SOPs, DWRs)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          GOLD (Feature / NBA)                          │
│  - BigQuery / Dataform: Aggregated KPIs (5-yr field rollup, decline %) │
│  - ML Intervention Features & Next Best Action Lookup Tables           │
│  - Gemini Grounding Cache for Field Dossiers                           │
└────────────────────────────────────────────────────────────────────────┘
```

* **Recommended Production Telemetry Engine**: **BigQuery**
  * *Why BigQuery over Cloud SQL/Spanner*: Cost-effective columnar storage for multi-year high-frequency telemetry, native time-series partitioning by `date` and clustering by `field_id, well_id`, with sub-second SQL execution for macro-aggregations.

---

## 6. Role-Based Access Control (RBAC) Matrix

| Persona | Primary Focus & Needs | Allowed Data & Views | Restricted Views |
|:---|:---|:---|:---|
| **Executive Director (e.g., Ajay Ratan)** | Macro ROI, multi-field benchmarking, fleet uptime, Capex/Opex allocation, strategic intervention approvals. | Field-level aggregates (Geleki, Lakwa, Lakhmani), 5-year macro plots, Capex priority queues, field-to-field decline trends. | Sensor calibration curves, raw wireline tension logs, micro-tool telemetry. |
| **Asset / Production Manager** | Cluster-level optimization, sick well diagnosis, rig scheduling, production target deficits. | Full cluster drill-down, priority intervention matrix, root cause factor breakdowns, rig allocation calendar. | Corporate financial hedges, cross-basin executive reports. |
| **Field Engineer / Workover Operator** | On-site execution, wellbore mechanical history, safety SOPs, specific tool tallies, pre-job dossier. | Single-well mechanical schema, past intervention logs, casing/tubing tallies, step-by-step SOPs, Gemini Live voice guidance. | Macro asset financial models, executive Capex budget approvals. |

---

## 7. Model Delegation Matrix: Opus (Orchestrator) vs. Flash (Workers)

To maximize generation speed, quality, and cost efficiency, tasks are strictly partitioned between **Pro/Opus (Complex Reasoning & Orchestration)** and **Flash (High-Throughput Parallel Generation)**:

```
                  ┌───────────────────────────────┐
                  │    OPUS / PRO (Orchestrator)  │
                  │ - System Architecture & Plan  │
                  │ - Tool Orchestration & Agent  │
                  │ - Diagnostic Decision Logic   │
                  │ - Verification & Synthesis    │
                  └───────────────┬───────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│ FLASH SUBAGENT│         │ FLASH SUBAGENT│         │ FLASH SUBAGENT│
│  Worker #1    │         │  Worker #2    │         │  Worker #3    │
│  Synthetic    │         │  Synthetic    │         │  Well Dossier │
│ Telemetry Gen │         │   PDF Docs    │         │ & SOP Chunking│
│(Lakwa/Lakhmani)│        │(Interventions)│         │  for RAG      │
└───────────────┘         └───────────────┘         └───────────────┘
```

### 1. Opus / Pro Responsibilities
* **Decision Engine & Counterfactual Reasoning**: Writing the multi-class ML diagnostic classifier and prompt logic for defending recommendations against alternatives.
* **Agent Architecture & WebSocket Proxy**: Porting the Gemini Live architecture from `Drilling-Intelligence-2.0` (`live_session.py` and `ws_live.py`).
* **Tool Schemas & Routing**: Building the high-level tools that support field-level aggregation, well drill-downs, and RBAC persona gating.
* **Final Verification & Test Suite Execution**: Validating the end-to-end conversation flow and data accuracy.

### 2. Flash Responsibilities (Parallelized Subagents)
* **Subagent 1: Telemetry Data Synthesizer**:
  - Generate 5 years of daily synthetic production time series for `Lakwa` (25 wells) and `Lakhmani` (20 wells) conforming to the existing Geleki schema.
* **Subagent 2: Workover PDF & Document Generator**:
  - Generate realistic PDF documents using ReportLab / WeasyPrint:
    - 15x Daily Workover Reports (DWRs) with historical timestamps.
    - 5x Well Completion Schematics & Casing Tallies.
    - 5x Standard Operating Procedures (SOPs) for GLV changeouts, Water Shut-Off, and Sand Bailing.
* **Subagent 3: BigQuery & Lakehouse Schema Ingestion**:
  - Script the Medallion table definitions and ingestion pipelines into BigQuery for Bronze/Silver/Gold layers.

---

## 8. Executive Implementation Checklist & Milestone Gates

```
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0% Complete (Phase 2 Expansion)
- Gate 1: Specification & Transcript Alignment (100% COMPLETE)
- Gate 2: Multi-Field Telemetry & Cluster Generation (Lakwa + Lakhmani)
- Gate 3: Medallion Lakehouse & BigQuery Schema Ingestion
- Gate 4: Synthetic PDF Dossiers & SOP RAG Knowledge Base
- Gate 5: Multi-Class ML Diagnostic & Counterfactual NBA Engine
- Gate 6: Gemini Live Stabilization (Ported from Drilling Intelligence 2.0)
- Gate 7: End-to-End Hierarchical Demo Script Validation
```

### Milestone Breakdown
- [x] **Milestone 0: Requirements Capture**
  - [x] Exact verbatim audio captured in `verbatim.md`.
  - [x] Hierarchical 5-turn demo script defined.
  - [x] Medallion Lakehouse, RBAC, and Opus/Flash delegation models specified.
- [ ] **Milestone 1: Multi-Cluster Synthetic Telemetry (Flash Subagent 1)**
  - [ ] Generate 5-year daily production histories for `Lakwa` (25 wells) and `Lakhmani` (20 wells).
  - [ ] Implement field-level aggregation tables and comparative decline metrics.
- [ ] **Milestone 2: Unstructured PDF Generation (Flash Subagent 2)**
  - [ ] Generate realistic Daily Workover Reports (DWRs), wellbore schematics, and SOPs in PDF format.
  - [ ] Establish GCS Bronze storage layout (`gs://well-workover-intervention-data/documents/`).
- [ ] **Milestone 3: Medallion Lakehouse in BigQuery (Flash Subagent 3)**
  - [ ] Bronze: Raw staging tables and Cloud Storage object catalog.
  - [ ] Silver: Cleaned daily production tables partitioned by `date` and clustered by `field_id, well_id`.
  - [ ] Gold: Pre-aggregated field KPIs, sick well screening views, and intervention feature store.
- [ ] **Milestone 4: Diagnostic Classifier & Counterfactual NBA (Opus / Orchestrator)**
  - [ ] Train/calibrate multi-class classifier across 10–15 intervention types.
  - [ ] Build deterministic counterfactual reasoning tool (justifying GLV vs. perforation vs. wax solvent).
- [ ] **Milestone 5: Gemini Live Audio/Multimodal Port (Opus / Orchestrator)**
  - [ ] Benchmark against `Drilling-Intelligence-2.0` (`live_session.py`, `ws_live.py`).
  - [ ] Upgrade WebSocket bidirectional proxy for low-latency field technician voice interaction.
- [ ] **Milestone 6: Verification & Dry-Run**
  - [ ] Automated pytest execution covering all 5 demo turns.
  - [ ] RBAC view gating validation (Executive Director vs. Field Engineer).


