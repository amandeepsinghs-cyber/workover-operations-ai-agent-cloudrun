# Business Requirements Document (BRD)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 1.0.0  
**Status:** Approved  
**Author:** Energy Operations & AI Engineering Team  

---

## 1. Executive Summary
WellPulse is an operational asset intelligence and triage platform engineered for upstream and production operations in oil and gas. Operating on hundreds of active wellheads requires balancing immediate safety and flow integrity with long-term reservoir recovery. WellPulse delivers a high-density, map-based operational interface prioritizing well assets into 3 distinct health states, providing immediate drilldown into 24-month historical production and maintenance curves, and empowering engineers with a voice-enabled conversational AI agent for hands-free diagnostics and intervention recommendations.

---

## 2. Business Objectives & Value Proposition
1. **Reduce Mean Time to Detect (MTTD) Production Anomalies**: Identify failing electric submersible pumps (ESPs), gas locking, and tubing scale choke within minutes rather than days.
2. **Prevent Catastrophic Well Downtime**: Automated 3-tier health triage (Green, Amber, Red) ensures the most critical wells receive immediate operational attention.
3. **Preserve Operational Knowledge**: Ingest and surface historical workover interventions, chemical treatments, and mechanical repairs so past lessons inform today's decisions.
4. **Hands-Free Operational Intelligence**: Enable field and control room engineers to interact verbally with well data, accelerating root-cause analysis and operational planning.
5. **Local-First Reliability**: Guarantee 100% operational readiness in offline or local field environments without mandatory cloud connectivity.

---

## 3. User Personas & Core Journeys

### 3.1 Persona A: Production & Field Engineer ("Sarah")
- **Responsibility**: Daily monitoring of 40–80 wells across the Geleki Tipam and Barail formations (Assam Asset, ONGC).
- **Pain Point**: Sifting through dense tabular SCADA logs to pinpoint which wells are choked by paraffin wax or experiencing water breakthrough.
- **Journey**: Opens WellPulse satellite map view $\rightarrow$ views tagged wellheads (`GLK-101`, `GLK-104`) over aerial terrain $\rightarrow$ filters by "Needs Attention" & "Critical" $\rightarrow$ clicks a red wellhead $\rightarrow$ inspects the 24-month oil/gas/pressure decline $\rightarrow$ speaks to the AI: *"What caused the sharp pressure drop on August 12?"* $\rightarrow$ receives clear diagnostic answer.

### 3.2 Persona B: Workover & Interventions Specialist ("Carlos")
- **Responsibility**: Planning mechanical interventions, hot oil wax circulation, water shut-off (WSO) polymer squeezes, and gas lift valve maintenance.
- **Pain Point**: Historical workover reports are buried in siloed archives; difficult to evaluate whether a previous hot oil wash or polymer plug was cost-effective.
- **Journey**: Selects an amber well $\rightarrow$ reviews the Workover History timeline $\rightarrow$ queries voice agent: *"What was the flow delta and ROI from the last hot oil wax treatment?"* $\rightarrow$ asks: *"Recommend an intervention plan for current water cut surge"*.

### 3.3 Persona C: Asset Operations Director ("Marcus")
- **Responsibility**: Fleet-wide production volume, operational uptime, and safety compliance across the Geleki field.
- **Pain Point**: Needs high-level executive visibility into fleet health distribution without navigating complex SCADA software.
- **Journey**: Reviews top KPI bar (Fleet Total: 50 | Healthy: 32 | Attention: 12 | Critical: 6) $\rightarrow$ observes geographic clusters of failing wells over satellite imagery $\rightarrow$ exports prioritized triage list.

---

## 4. Detailed Functional Requirements

### 4.1 Geospatial Satellite Map & Well Prioritization (BRD-F01)
- **F01.1**: The platform must display an interactive **Satellite Map** plotting all monitored wellheads with accurate coordinates over the Geleki Oil Field in Sivasagar, Assam (`26.77° N, 94.69° E`).
- **F01.2**: Every wellhead marker on the satellite map must display a **permanent tagged badge showing the well name/ID** (e.g., `GLK-101`) and an authentic oil derrick icon, eliminating confusing dollar signs or cryptic symbols.
- **F01.3**: Each well must be visually categorized using 3 distinct status colors:
  - 🟢 **Healthy / Optimal**: Telemetry within expected brownfield decline envelope ($\pm 5\%$), stable gas lift pressures.
  - 🟡 **Needs Attention / Warning**: Flow decline >15%, water cut increase >12%, or paraffin wax deposition.
  - 🔴 **Critical / Failed**: Gas lift cutoff, severe wax lock, or sand bridging with an active visual pulsing radar ring.
- **F01.4**: Operators must be able to toggle between **Satellite Field Imagery** and **Dark SCADA GIS** layers with one click.
- **F01.5**: Operators must be able to filter wells by status (All, Healthy, Attention, Failed) and search by Well Name, ID, or Formation.
- **F01.3**: Critical wells must feature an animated visual cue (pulsing radar ring) on the map to draw immediate focus.
- **F01.4**: Operators must be able to filter wells by status (All, Healthy, Attention, Failed) and search by Well Name, ID, or Basin.

### 4.2 Historical Telemetry & Analytics (BRD-F02)
- **F02.1**: Clicking a wellhead must display comprehensive 24-month historical telemetry charts.
- **F02.2**: The telemetry must track:
  - Oil Production (BOPD - Barrels of Oil Per Day)
  - Gas Production (MCFD - Thousand Cubic Feet Per Day)
  - Water Cut (% - percentage of produced water)
  - Tubing Pressure vs. Casing Pressure (psi)
- **F02.3**: Users must have time-range toggles (Last 30 Days, 6 Months, 1 Year, 2 Years).

### 4.3 Workover & Intervention History (BRD-F03)
- **F03.1**: The platform must present a chronological timeline of all prior workovers and well interventions.
- **F03.2**: Each workover record must capture: Date, Intervention Type (Acid Stimulation, ESP Replacement, Scale Squeeze, Perforation Re-shoot), Total Cost ($ USD), Contractor, Description, and Post-Intervention Flow Delta (+/- BOPD).

### 4.4 Voice-Enabled AI Conversational Agent (BRD-F04)
- **F04.1**: The right-side pane must feature an interactive voice-enabled conversational AI agent.
- **F04.2**: The agent must automatically receive the selected well's complete profile, 24-month telemetry aggregates, and workover log into its prompt context.
- **F04.3**: Operators must be able to ask questions via natural voice input (Speech-to-Text) using an intuitive push-to-talk or voice-toggle button.
- **F04.4**: The agent must respond both in formatted textual chat and audible spoken voice (Text-to-Speech).
- **F04.5**: Audio input/output must be complemented with a dynamic waveform or speaking animation.

### 4.5 Prescriptive Recommendations Engine (BRD-F05)
- **F05.1**: The agent must generate structured, engineering-sound recommendations for selected wells.
- **F05.2**: Recommendations must outline: Proposed Action, Urgency Level (Immediate / High / Routine), Estimated Cost ($), Expected Flow Uplift (+BOPD), and Risk Mitigation factor.

---

## 5. Non-Functional Requirements

| ID | Category | Requirement Description |
|---|---|---|
| **NFR-01** | Performance | Map pin rendering and initial data load < 1.0 second for 50+ wells. |
| **NFR-02** | Local-First | Application must run completely locally on `localhost` via a single startup command. |
| **NFR-03** | Resilience | If external LLM APIs are unreachable or unconfigured, the system must fall back to an intelligent local rule-based simulation engine without failing. |
| **NFR-04** | Usability | Dark-mode SCADA/Energy Operations interface compliant with contrast standards. |
| **NFR-05** | Browser Compatibility | Chrome, Edge, and Firefox supporting Web Speech API. |
