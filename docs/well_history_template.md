# Pre-Field Well Pack Specification & Report Template
## ONGC Assam Asset · Workover & Well Intervention Engineering
**Document ID:** `WH-SPEC-V1`  
**Target Output:** Standalone Responsive HTML Report (`well_history_<well_id>.html`) / Printable A4 Engineering Dossier  
**Asset Scope:** ONGC Assam Asset — Geleki (`GK-`), Lakwa (`LKW-`), Lakhmani (`LKM-`)  
**Data Integrity Notice:** **ALL DATA IN THIS SPECIFICATION AND GENERATED REPORTS IS 100% SYNTHETIC.** Strictly no real ONGC reservoir/well proprietary records are contained herein.  
**Commercial Rule:** No financial figures (INR / USD / NPV / Payback) appear anywhere. Operational effort is expressed strictly as **Cost Band (`LOW`, `MED`, `HIGH`)** and **Rig-Days**.

---

## 1. Specification Overview, Personas & Delivery Architecture

### 1.1 Purpose
A **Pre-field Well Pack** is the single authoritative engineering dossier reviewed by a Field Engineer and Workover Supervisor prior to mobilising equipment, rigs, or slickline/coiled tubing units to a wellhead. It aggregates complete lifecycle construction, barrier integrity, historical failure root causes, production dynamics, and operational prerequisites to eliminate blind site mobilisations, prevent recurring job failures, and ensure well-control safety.

### 1.2 Target Audience & User Hierarchy
* **Primary (Field Engineer & Rig Superintendent):** Detailed mechanical construction, drift IDs, tubing/casing tallies, barrier envelope, kill fluid calculations, site hazards, and approved Standard Operating Procedure (SOP) step sequence.
* **Secondary (Asset Manager & Surface Manager):** Diagnosis summary, decline attribution, cost band (`LOW`/`MED`/`HIGH`), rig availability, offset response, and environmental clearance.
* **Tertiary (Executive Director / IDWE):** High-level asset health status, intervention class, and executive approval block (casing/tubing detail summarized per RBAC).

### 1.3 Trigger Phrases (Chat & Voice Agent)
The Pre-field Well Pack is generated on explicit user demand and **never** dumped unprompted into conversational text.
* *"Prepare me for the field for GK-129"*
* *"Generate full well history report for well LKW-047"*
* *"Open pre-field pack for LKM-023"*
* *"Give me the well report for GK-001"*
* *"Dossier for well GK-129"*

### 1.4 Delivery Mechanism & UI Presentation
1. **Chat UI Interaction:** Emits a single-line markdown link with metadata chip:
   ```markdown
   📋 **Pre-Field Well Pack Generated:** [Open GK-129 Field Pack (HTML)](/api/wells/GK-129/history-pack) · *As of 2026-09-30 | 19 Sections | Print Ready (A4)*
   ```
2. **Presentation Panel:** Opens in WellPulse's expanded middle workspace panel (full-width iframe overlay with split-pane docking).
3. **Branding & Print:** Features the official ONGC corporate header banner, asset name, synthetic disclaimer watermark, and print CSS formatting optimized for A4 hardcopy export (`@media print`).
4. **Latency Target:** Complete report generation and DOM render in `< 3.0 seconds`.

### 1.5 Persona & RBAC Visibility Rules
| Section Group | Field Engineer (`FE`) | Asset Manager (`AM`) | Executive Director (`ED`) |
|---|---|---|---|
| **Identity & Well Location** | Full access with GIS coordinates | Full access | Full access |
| **Wellbore Schematic & Drift** | Full component details & drift IDs | Full component details | Summary schematic only |
| **Tubing & Casing Tallies** | Full joint-by-joint engineering tally | Aggregated tally | String summary only |
| **Financial / Effort Metrics** | Cost Band (`LOW`/`MED`/`HIGH`) + Rig-Days | Cost Band + Rig-Days + Queue Priority | Cost Band + Rig-Days + Strategic Alignment |
| **Currency (INR / USD / NPV)** | **STRICTLY HIDDEN / PROHIBITED** | **STRICTLY HIDDEN / PROHIBITED** | **STRICTLY HIDDEN / PROHIBITED** |
| **SOP Step Sequences** | Full step-by-step checklist | Phase overview only | Phase overview only |
| **Sign-off Block** | Field execution sign-off | Operational approval sign-off | Asset authorization sign-off |

---

## 2. Report Layout & Detailed Section Specifications

The report comprises 19 structured sections (`WH-01` through `WH-19`). Every engineering metric is mapped to existing database columns or designated as a synthetic generation gap.

```
+----------------------------------------------------------------------------------------------------+
| ONGC ASSAM ASSET - PRE-FIELD WELL PACK (SYNTHETIC DATA DEMO)                                       |
+----------------------------------------------------------------------------------------------------+
| WH-01 Header & Well Identity               | WH-02 Site Access, Surface Facilities & HSE Notes      |
+--------------------------------------------+-------------------------------------------------------+
| WH-03 Current Status & Latest Well Test    | WH-04 Wellbore & Completion Diagram (SVG Vector)      |
+--------------------------------------------+-------------------------------------------------------+
| WH-05 Casing & Tubing Components & Drift   | WH-06 Tubing Joint-by-Joint Tally                     |
+--------------------------------------------+-------------------------------------------------------+
| WH-07 Perforations & Formation Lithology   | WH-08 Well Deviation & Directional Survey             |
+--------------------------------------------+-------------------------------------------------------+
| WH-09 Chronological Life-of-Well Timeline  | WH-10 Failure, Fishing & Wellbore Obstruction Log     |
+--------------------------------------------+-------------------------------------------------------+
| WH-11 Production Trends & Markers          | WH-12 Reservoir Pressure, Temperature & Lift Telemetry|
+--------------------------------------------+-------------------------------------------------------+
| WH-13 Fluid Properties & Hazards           | WH-14 Well Integrity, Barriers & Tree Ratings         |
+--------------------------------------------+-------------------------------------------------------+
| WH-15 Diagnosis, Decline & NBA with SOP    | WH-16 Offset Well Analogs & Interference              |
+--------------------------------------------+-------------------------------------------------------+
| WH-17 Rig Prerequisites & Well Kill Data   | WH-18 Document Index (D1-D11) & Reference Library     |
+--------------------------------------------+-------------------------------------------------------+
| WH-19 Operational Contacts & Sign-off Block                                                        |
+----------------------------------------------------------------------------------------------------+
```

---

### WH-01: Header & Well Identity
* **Why the engineer needs it:** Establishes immediate legal, operational, and geographical identification of the wellhead before convoy dispatch.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Well ID, Field, Cluster / GGS Name, Asset, Operating District.
  * Geographic Coordinates (Latitude, Longitude) & Elevation (GL, RKB).
  * Spud Date, Initial Completion Date, Age of Well (years).
  * Current Producing Zone & Formation.
  * Total Depth (MD m, TVD m) & PBTD (m).
  * Current Lift Type & Lift Details.
  * Prominent Synthetic Data Disclaimer banner.
* **Data Sources:**
  * `well_master.well_id`, `well_master.field`, `well_master.cluster_id`, `well_master.asset`
  * `well_master.latitude`, `well_master.longitude`, `well_master.spud_date`, `well_master.completion_date`
  * `well_master.current_zone`, `well_master.total_depth_md_m`, `well_master.total_depth_tvd_m`
  * `well_master.lift_type`, `well_master.status`, `settings.AS_OF`

---

### WH-02: Site Access, Surface Facilities & HSE Notes
* **Why the engineer needs it:** Identifies physical access restrictions (monsoon swamp, bridge weight limits, overhead powerlines) and surface gathering station linkages.
* **Status:** `PARTIAL`
* **Fields & Visuals:**
  * Assigned Group Gathering Station (GGS) / Early Production Facility (EPF).
  * Flowline ID, Size (in), Length (km), Operating Pressure ($kg/cm^2$).
  * Road Condition / Access Status (Paved, Gravel, Black-topped, Monsoon Restricted).
  * Rig Mat / Plinth Size ($m \times m$) & Crane Positioning Footprint.
  * Primary HSE Hazards: Proximity to tea garden / village habitation, seasonal waterlogging risk.
* **Data Sources:**
  * `AVAILABLE`: `well_master.cluster_id` (links to GGS node), `well_master.latitude`, `well_master.longitude`
  * `GAP`: `surface_infrastructure.flowline_id`, `surface_infrastructure.access_road_type`, `surface_infrastructure.plinth_dimensions_m`, `hse_hazards.proximity_notes` (to be synthesized).

---

### WH-03: Current Status & Latest Well Test
* **Why the engineer needs it:** Informs the engineer whether the well is currently live, shut-in, producing with high water cut, or exhibiting abnormal head pressures.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Current Health Bucket (`PRODUCING_OK`, `UNDERPERFORMING`, `AT_RISK`, `NOT_PRODUCING`).
  * Current Status Episode & Reason Code (with duration since outage).
  * Latest Valid Well Test: Test ID, Date, Duration (hrs), Oil ($BOPD$), Water ($BWPD$), Gas ($MSCFD$), Water Cut (%), Gas-Oil Ratio ($scf/bbl$).
  * Surface Pressures during test: Tubing Head Pressure ($THP$, $kg/cm^2$), Casing Head Pressure ($CHP$, $kg/cm^2$).
  * Subsurface test data: Fluid Level ($m$), Pump Intake Pressure ($kg/cm^2$), Test Quality Grade.
* **Data Sources:**
  * `well_status_history.status`, `well_status_history.start_date`, `well_status_history.reason_code`
  * `well_tests.test_id`, `well_tests.test_date`, `well_tests.test_duration_hr`, `well_tests.oil_rate_bopd`, `well_tests.water_rate_bwpd`, `well_tests.gas_rate_mscfd`, `well_tests.thp_kgcm2`, `well_tests.chp_kgcm2`, `well_tests.fluid_level_m`, `well_tests.pump_intake_p_kgcm2`, `well_tests.test_quality`
  * Tool function: `classify_well_health()` (TC-020).

---

### WH-04: Wellbore & Completion Diagram (SVG Vector Specification)
* **Why the engineer needs it:** Visual schematic of the wellbore architecture to prevent setting tools across casing collars, running past restrictions, or misaligning perforations.
* **Status:** `AVAILABLE`
* **SVG Vector Specification:**
  * **Dimensions & Coordinate Space:** Scalable vector canvas `viewport="0 0 500 800"`. Vertical axis represents Measured Depth (MD m), mapped linearly from surface ($0\,m$) to $TD\,m$.
  * **Casing Strings:** Concentric vertical pipes rendered from outside in. Outer conductor, intermediate/surface, and production casing. Line width represents relative weight/thickness. Casing shoes marked with filled triangles (`Polygon`) pointing outward.
  * **Cement Annulus:** Hatched grey fill (`#b9b9b9`) between outer borehole wall and casing OD from shoe depth up to documented `cement_top_m`. If `cement_top_m = 0`, cement reaches surface.
  * **Tubing String & BHA:** Blue line (`#1f5fa8`) running centrally from wellhead down to pump setting depth or tail pipe. BHA tools (Seating Nipple, Tubing Anchor Catcher, Gas Lift Mandrels, Submersible Pump) rendered as distinct rectangular component blocks.
  * **Perforations:** Horizontal lateral tick marks across the casing wall. Coloured `#d32f2f` (Solid Red) for `OPEN` active intervals, `#9e9e9e` (Dashed Grey) for `PLUGGED` / `SQUEEZED` intervals.
  * **Lithology Column:** Left-side stacked formation banner (`width="70"`) showing geological layers from surface to TD with distinct standard rock pattern tints (Alluvium `#f4ecd8`, Namsang `#e9dcc0`, Girujan `#ddd0b0`, Tipam `#f0e6cc`, Barail `#d0dce5`).
  * **Depth Depth Markers:** Horizontal dashed datum lines with explicit metric depth callouts: Surface, Cement Tops, Mandrel/Nipple depths, Perforation Tops/Bottoms, Casing Shoes, PBTD, and TD.
  * **Fallback Handling:** If casing tally is missing, default to two strings based on `well_master.casing_size_in` with shoe at TD. If tubing tally missing, render generic string to `pump_setting_depth_m` or $0.85 \times TD$.
* **Data Sources:**
  * `casing_tally` (all strings), `tubing_string` (all components), `perforation_intervals` (all zones), `formation_tops`, `well_master.total_depth_md_m`.
  * Vector renderer: `app.analytics.docs_pdf.dossier_render.wellbore_schematic()`.

---

### WH-05: Casing, Tubing & Completion Components (incl. Minimum ID Drift)
* **Why the engineer needs it:** Rig crews must verify the smallest drift diameter in the wellbore to ensure workover bits, packers, or fishing tools will not get stuck.
* **Status:** `PARTIAL`
* **Fields & Visuals:**
  * **Casing Table:** String Type, OD ($in$), Weight ($ppf$), Grade (e.g. J-55, N-80, P-110), Top MD ($m$), Shoe MD ($m$), Cement Top MD ($m$), Calculated Nominal ID ($in$), API Drift Diameter ($in$), Installation Date.
  * **Tubing / BHA Table:** Sequence, Component Type (Tubing, Pup Joint, Anchor, Seating Nipple, Pump Barrel), OD ($in$), Component Length ($m$), Top Depth ($m$), Bottom Depth ($m$), Minimum Internal Restriction / Drift ($in$).
* **Data Sources:**
  * `AVAILABLE`: `casing_tally.string_type`, `od_in`, `weight_ppf`, `grade`, `top_m`, `shoe_m`, `cement_top_m`, `install_date`.
  * `AVAILABLE`: `tubing_string.seq`, `component`, `od_in`, `length_m`, `top_m`, `install_date`, `workover_id`.
  * `GAP`: `drift_id_in` for casing strings and minimum internal restriction for BHA seating nipples (synthesized via API 5CT lookup tables).

---

### WH-06: Tubing Joint-by-Joint Tally
* **Why the engineer needs it:** During pulling or running tubing, the winchman and derrickman tally each single joint to know the exact bit/packer depth down to the centimetre.
* **Status:** `GAP`
* **Fields & Visuals:**
  * Joint Number ($1 \dots N$).
  * Individual Joint Length ($m$, Range 2 typical $9.14 \dots 9.75\,m$).
  * Cumulative Length ($m$).
  * Measured Depth ($m$).
  * Thread Type (EUE 8rd, NUE, Premium).
  * Visual Condition / Pipe Inspection Grade (Class 1, Class 2, Red Band).
* **Data Sources:**
  * `tubing_string` stores only aggregated component length.
  * Synthetic generation rule: Synthesize joint-by-joint array summing exactly to `tubing_string.length_m` using pseudo-random normal distribution ($\mu=9.45\,m, \sigma=0.15\,m$).

---

### WH-07: Perforation Intervals & Formation Lithology
* **Why the engineer needs it:** Identifies active reservoir drainage intervals, depleted zones, isolated wet sands, and potential gas caps.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Zone Name (e.g. Tipam Sand-1, Barail, Lakadong-Therria).
  * Top Depth MD ($m$), Bottom Depth MD ($m$), Net Pay Thickness ($m$).
  * Perforation Density ($shots/ft$), Gun Type & Phasing ($90^\circ, 120^\circ$).
  * Perforation Date & Workover Reference.
  * Status: `OPEN`, `SQUEEZED`, `ISOLATED_BY_PACKER`, `PLUGGED`.
  * Lithology column overlay: Formation name, Top MD ($m$), Base MD ($m$), Lithological description (Sandstone, Shale, Claystone, Coal).
* **Data Sources:**
  * `perforation_intervals.zone`, `top_m`, `bottom_m`, `spf`, `perf_date`, `status`
  * `formation_tops.formation`, `top_md_m`, `bottom_md_m`, `lithology`

---

### WH-08: Well Deviation & Directional Survey
* **Why the engineer needs it:** High dogleg severity causes rod wear, parted rods, tubing leaks, and tool hang-ups.
* **Status:** `GAP`
* **Fields & Visuals:**
  * Station Survey Table: Measured Depth ($MD\,m$), True Vertical Depth ($TVD\,m$), Inclination ($deg$), Azimuth ($deg$), Dogleg Severity ($DLS,\,^\circ/30m$), Vertical Section ($m$).
  * Max DLS callout ($^\circ/30m$) and Depth of Kickoff Point ($KOP\,m$).
  * Well Profile Classification: Vertical ($<5^\circ$), S-Type, J-Type, Slanted.
* **Data Sources:**
  * `PARTIAL`: `well_master.total_depth_md_m`, `well_master.total_depth_tvd_m`, `well_master.max_dls_deg_30m`.
  * `GAP`: Full station survey table (generated via minimum curvature method connecting surface to $TVD/MD$).

---

### WH-09: Chronological Life-of-Well Timeline
* **Why the engineer needs it:** Reveals entire operational history from spudding to present, highlighting frequency of interventions, previous workover contractors, and job outcomes.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Chronological Table (earliest to latest):
    * Event Date / Start Date & End Date.
    * Event Type: Initial Drilling, Completion, Rig Workover, Rigless Intervention, Wireline.
    * Catalogue Job Code & Standard Intervention Class (`IC-01` to `IC-15`).
    * Failure Code Triggered (e.g. `PUMP_WEAR`, `TUBING_LEAK`, `WAX`, `SAND`).
    * Rig ID / Spread Used.
    * Rig Days Expended.
    * Pre-Job Oil ($BOPD$) vs. Post-Job Oil ($BOPD$) & Uplift ($BOPD$).
    * Outcome: `SUCCESS`, `FAILED`, `ABANDONED`.
    * Linked Document ID (hyperlinked to D02 Workover Completion Report).
* **Data Sources:**
  * `workover_history.workover_id`, `start_date`, `end_date`, `job_code`, `failure_code`, `is_rigless`, `rig_id`, `rig_days`, `pre_job_oil_bopd`, `post_job_oil_bopd`, `uplift_bopd`, `outcome`, `run_life_days`, `report_doc_id`, `catalogue_job_code`, `intervention_class`.
  * `document_index.doc_id`, `doc_type`, `title`.

---

### WH-10: Failure, Fishing & Wellbore Obstruction Log
* **Why the engineer needs it:** Critical warning system: alerts rig crew to unrecovered junk, parted rods, packers left in hole, or recurrent parted tubing depths.
* **Status:** `PARTIAL`
* **Fields & Visuals:**
  * Failure Frequency Summary: Grouped by failure mechanism over the last 24 months vs. life-of-well.
  * Repeat Failure Warning Callout: Triggers warning if the same failure mode recurred $\ge 2$ times within 730 days.
  * Fishing History Record: Date of incident, Fish description (e.g. 3 joints 2-7/8" tubing, parted sucker rod string, stuck slickline tool), Top of Fish ($TOF\,m$), Bottom of Fish ($BOF\,m$), Catch tool used (Over-shot, Spear, Magnet), Retrieval status (`RECOVERED` or `LEFT_IN_HOLE`).
* **Data Sources:**
  * `AVAILABLE`: `workover_history.failure_code`, `workover_history.outcome`, `workover_history.run_life_days`.
  * `GAP`: Specific fish dimensional specs, TOF depth, and fishing BHA records (synthesized for failed workover jobs).

---

### WH-11: Historical Production Trends & Intervention Markers
* **Why the engineer needs it:** Demonstrates baseline reservoir delivery, post-intervention decline rate, water cut breakthrough, and lift stability over 36 to 60 months.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Multi-panel Synchronized Time-Series Chart (36-60 months daily data):
    * Panel 1: Oil Rate ($BOPD$, green) and Water Rate ($BWPD$, blue) vs. Arps Decline Curve.
    * Panel 2: Water Cut (%, cyan) and Gas-Oil Ratio ($GOR,\,scf/bbl$, purple).
    * Panel 3: Liquid Rate ($BLPD$) and Well Runtime Fraction ($hrs/24$).
  * Vertical Intervention Marker Lines: Red dashed vertical rules across all panels representing dates of completed workovers, annotated with job code.
* **Data Sources:**
  * `daily_production.production_date`, `oil_rate_bopd`, `water_rate_bwpd`, `liquid_rate_blpd`, `gas_rate_mscfd`, `water_cut_pct`, `gor_scf_bbl`, `runtime_hours`, `runtime_fraction`.
  * `workover_history.start_date`, `job_code`.
  * Tool function: `well_production_series()` (TC-017 v2).

---

### WH-12: Reservoir Pressure, Temperature & Lift Telemetry
* **Why the engineer needs it:** Determines current reservoir depletion state, flowing bottom-hole drawdown, gas-lift operating efficiency, or beam pump fillage.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Static & Flowing BHP Surveys: Survey ID, Date, Static BHP ($SBHP,\,kg/cm^2$), Flowing BHP ($FBHP,\,kg/cm^2$), Productivity Index ($PI,\,bpd/(kg/cm^2)$), Datum TVD ($m$), Fluid Level ($m$).
  * Surface Telemetry Trends: Tubing Head Pressure ($THP$), Casing Head Pressure ($CHP$), Wellhead Temperature ($WHT,\,^\circ C$), Choke Size ($64^{ths}$).
  * Artificial Lift Operational Telemetry:
    * *For SRP:* SPM, Stroke Length ($in$), Plunger Diameter ($in$), Rod Grade, Fillage %, Casing Vented flag.
    * *For Gas-Lift:* Continuous injection gas rate ($MSCFD$), Injection pressure ($kg/cm^2$).
* **Data Sources:**
  * `pressure_surveys.survey_id`, `survey_date`, `sbhp_kgcm2`, `fbhp_kgcm2`, `pi_bpd_per_kgcm2`, `datum_tvd_m`, `fluid_level_m`.
  * `daily_production.thp_kgcm2`, `chp_kgcm2`, `wht_degc`, `choke_size_64th`, `spm`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2`.
  * `well_master.lift_type`, `pump_type`, `stroke_length_in`, `plunger_diameter_in`, `rod_string_grade`, `casing_vented`.

---

### WH-13: Fluid Properties, Flow Assurance & Subsurface Hazards
* **Why the engineer needs it:** Toxic gas ($H_2S$) and flow assurance issues (heavy paraffin wax, sand ingestion, calcium carbonate scale) dictate metallurgy, chemical wash volumes, and PPE.
* **Status:** `PARTIAL`
* **Fields & Visuals:**
  * Produced Fluid Character: Oil Gravity ($^\circ API$), Pour Point ($^\circ C$), Wax Content (% wt), Wax Appearance Temperature ($WAT,\,^\circ C$).
  * Water Chemistry & Scaling Index: Total Dissolved Solids ($TDS,\,mg/L$), Chlorides ($mg/L$), Bicarbonates, Stiff-Davis Scaling Index ($CaCO_3 / BaSO_4$).
  * Gas Composition & Toxic Gas Hazards: $H_2S$ Concentration ($ppm$), $CO_2$ Concentration ($mol\%$), Gas Specific Gravity.
  * Flow Assurance History Table: Dates of past solvent flushes, hot oil treatments, scale inhibitor squeezes, or sand bailings.
* **Data Sources:**
  * `AVAILABLE`: `workover_history.failure_code` (contains `WAX`, `SAND`, `SCALE`), `document_index` (D06 chemical treatment reports).
  * `GAP`: Quantitative laboratory values for $H_2S\,ppm$, $CO_2\%$, $WAT\,^\circ C$, $API^\circ$ (synthesized per formation/field geologic standards).

---

### WH-14: Well Integrity, Barrier Status & Wellhead Pressure Ratings
* **Why the engineer needs it:** Ensures secondary well control barriers are validated before unbolting the X-mas tree or pulling the tubing hanger.
* **Status:** `GAP`
* **Fields & Visuals:**
  * Wellhead & Tree Specifications: Wellhead Make/Model, Flange Size ($in$), API Pressure Rating ($psi / kg/cm^2$, e.g. API 3000 / 5000), Tubing Hanger Type.
  * Annulus Pressure Monitoring:
    * Annulus 'A' (Tubing $\times$ Production Casing): Current pressure, Sustained Casing Pressure (SCP) flag, Bleed-off / build-up behaviour.
    * Annulus 'B' (Production Casing $\times$ Surface Casing): Current pressure.
  * Barrier Verification Envelope (NORSOK D-010 compliant status):
    * Primary Barrier: Hydrostatic fluid column + Downhole Seating Nipple Plug / SCSSV (Status: `TESTED_OK` / `LEAKING`).
    * Secondary Barrier: Production Casing + Cement Sheath + Wellhead Seal + BOP / Master Valve (Status: `VERIFIED`).
  * Most Recent Pressure Test Log: Date of last casing positive pressure test, surface tree test date, test pressure ($kg/cm^2$), duration (min), result.
* **Data Sources:**
  * `document_index` (D05 CBL log citations).
  * `GAP`: Annulus pressures, API wellhead rating, and valve test log table (synthesized relative to well age and field maximum THP).

---

### WH-15: Current Diagnosis & Recommended Next Best Action (NBA)
* **Why the engineer needs it:** Bridges historical analytics and field work: outlines exactly why this intervention is scheduled, the expected uplift, and the vetted procedural SOP.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Diagnosis Summary: Health Bucket, Decline Driver Mechanism, Confidence Level.
  * Decline Attribution Loss Waterfall (TC-019): Total lost oil ($bbl$), Controllable % vs. Subsurface %, Factor Class Breakdown (`SUBSURFACE`, `EQUIPMENT`, `OPERATIONAL`, `HUMAN_PROCESS`, `EXTERNAL`).
  * Ranked Intervention Options Table:
    * Rank ($1 \dots 3$).
    * Recommended Job Code & Intervention Class.
    * Expected Uplift ($BOPD$) & 12-Month Deferred Barrels Avoided ($bbl$).
    * Probability of Success ($p_{success}$) with historical sample size ($n$).
    * Rig Requirement (`RIG` vs. `RIGLESS`), Unit Type (Workover Rig, Coiled Tubing, Slickline).
    * Estimated Rig-Days & Total Duration Range ($days$).
    * Cost Band: **`LOW` / `MED` / `HIGH`** (*Strictly no currency/rupees/USD*).
    * Risk Flags & Logistics / MRO Spares Status.
    * SOP Reference Document ID (hyperlink to D11).
  * Counterfactual Analysis ("Why not alternative?"): Selected job vs. rejected alternatives with diagnostic rationale (e.g. why water shut-off squeeze instead of pump overhaul).
* **Data Sources:**
  * Tool function: `well_health()` (TC-020)
  * Tool function: `attribute_decline()` (TC-019)
  * Tool function: `recommend_next_best_action()` (TC-022)
  * Tool function: `compare_interventions()` (TC-027)

---

### WH-16: Offset & Nearby Well Performance
* **Why the engineer needs it:** Prevents unexpected gas blowouts, water breakthrough, or inter-well interference from adjacent water injection or production wells during workover.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Table of $k$ Nearest Wells in Same Cluster (typically 4 nearest):
    * Well ID & Distance ($m$, great-circle haversine).
    * Producing Zone & Same-Zone Flag (`True`/`False`).
    * Lift Type.
    * Health Bucket & Operating Status.
    * Current Oil Rate ($BOPD$) & Water Cut (%).
    * Arps Decline Residual (%).
    * Last Job Code, Job Name, and Date Performed.
* **Data Sources:**
  * `well_offsets.offset_well_id`, `distance_m`, `same_zone`, `rank`
  * `well_master.latitude`, `well_master.longitude`, `well_master.current_zone`, `well_master.lift_type`
  * Tool function: `well_profile.neighbours` (TC-029).

---

### WH-17: Job Prerequisites & Engineering Mobilisation Checklist
* **Why the engineer needs it:** Go/No-Go gate: specifies exact kill fluid weight to prevent a blowout, required rig capacity, material requisitions, and statutory clearances.
* **Status:** `PARTIAL`
* **Fields & Visuals:**
  * Well Kill Calculation:
    * Current Datum Reservoir Pressure ($SBHP,\,kg/cm^2$ and $psi$).
    * True Vertical Depth ($TVD,\,m$).
    * Required Kill Fluid Density ($\rho_{kill},\,Specific\,Gravity$):
      $$\rho_{kill} = \frac{SBHP\,(kg/cm^2) \times 10}{TVD\,(m)} + \text{Safety Margin}\,(0.03 \dots 0.05\,SG)$$
    * Recommended Kill Fluid Type (e.g. Treated formation water, $KCl$ brine, treated crude).
    * Total Wellbore Capacity & Annular Volume ($m^3 / bbl$).
  * Rig & Surface Spread Specification: Rig Mast Capacity (tonnes, e.g. 50T / 100T workover rig), Pump Rating ($psi$), Minimum BOP Stack Configuration (e.g. Double Ram 7-1/16" 3000 psi).
  * Materials & Spares Availability (MRO Stock): Required tubulars, packers, valves, elastomer compatibility (NBR, Viton).
  * Statutory & Field Clearances: Internal Work Permit (PTW), Hot Work Permit, Mines Safety (DGMS) compliance, Village / Panchayat liaison.
* **Data Sources:**
  * `AVAILABLE`: `pressure_surveys.sbhp_kgcm2`, `well_master.total_depth_tvd_m`, `casing_tally`, `tubing_string`, `TC-022 nba.mro_status`.
  * `GAP`: Formal calculated kill mud weight box, rig tonnage class specification, and PTW permit checklist (synthesized dynamically from SBHP and casing volume).

---

### WH-18: Historical & Technical Document Index (D1–D11)
* **Why the engineer needs it:** Provides immediate deep-link access to primary source PDF documents in the WellPulse document repository without searching archive files.
* **Status:** `AVAILABLE`
* **Fields & Visuals:**
  * Document Index Table:
    * Document ID (e.g. `DOC-CBL-GK129-1998`, `DOC-SCAN-GK-129-013`).
    * Standard Document Classification ($D1 \dots D11$):
      * $D1$: Well Completion Report
      * $D2$: Workover Completion Report
      * $D3$: Daily Workover Report (DWR)
      * $D4$: Wellbore Schematic
      * $D5$: Cement Bond Log (CBL) Interpretation
      * $D6$: Chemical Treatment Log
      * $D7$: Well Test / Pressure Survey Report
      * $D8$: Failure Analysis (RCA) Report
      * $D9$: Field Reservoir Studies
      * $D10$: Monthly Field Performance
      * $D11$: Standard Operating Procedure (SOP)
    * Document Date & File Title.
    * Text Layer Status (`Digital Text` vs. `Scanned/OCR`).
    * Direct Action: Download / View PDF link (`/api/docs/<doc_id>.pdf`).
* **Data Sources:**
  * `document_index.doc_id`, `well_id`, `doc_type`, `doc_date`, `gcs_uri`, `title`, `has_text_layer`.

---

### WH-19: Key Operational Contacts & Sign-off Block
* **Why the engineer needs it:** Defines chain of operational command, 24-hour emergency contacts, and formal engineering hand-over sign-offs before rig spudding.
* **Status:** `GAP`
* **Fields & Visuals:**
  * Operational Directory Table: Role, Designation, Operating Base, 24/7 Phone / VHF Channel.
    * Asset Manager (Assam Asset)
    * Surface Manager (Geleki / Lakwa / Lakhmani)
    * Workover In-Charge / Rig Superintendent
    * Field HSE Officer & Fire Station Command
    * GGS / EPF Shift In-Charge
    * Base Hospital / Medical Evacuation
  * Pre-Job Verification & Sign-off Table:
    * Prepared By (Field Engineer): Name, CPF No., Signature, Date.
    * Reviewed By (Senior Workover Engineer): Name, CPF No., Signature, Date.
    * Approved By (Surface Manager / Operations Head): Name, CPF No., Signature, Date.
* **Data Sources:**
  * `GAP`: Synthesized ONGC operational role directory structure and formal governance authorization signatures.

---

## 3. Data Gap Register & Synthetic Generation Rules

The table below catalogs every `GAP` and `PARTIAL` section, defining deterministic, physics-aligned synthetic generation rules consistent with existing parquet datasets.

| Section ID | Missing Element | Status | Proposed Synthetic Generation Rule | Target Stage | Priority |
|---|---|---|---|---|---|
| **WH-02** | Plinth & Road Access | `PARTIAL` | Derive road type (`Paved` vs. `Monsoon_Gravel`) from cluster geography (`GK-NE` = Paved, `GK-SW` = Gravel). Plinth set to standard ONGC workover pad $40\,m \times 40\,m$. | Stage S | `P2` |
| **WH-05** | API Drift Diameters | `PARTIAL` | Calculate from standard API Spec 5CT lookup based on `od_in` and `weight_ppf`: e.g. 5-1/2" 15.5# casing drift = $4.825\,in$; 2-7/8" 6.5# tubing drift = $2.347\,in$. | Stage S | `P1` |
| **WH-06** | Tubing Joint Tally | `GAP` | Synthesize joint array ($1 \dots N$) where $\sum \text{length} = \text{tubing\_string.length\_m}$. Joint length generated from Gaussian distribution ($\mu=9.45\,m, \sigma=0.15\,m$, bounded $9.15 \dots 9.75\,m$). | Stage N/S | `P2` |
| **WH-08** | Directional Station Surveys | `GAP` | Generate station surveys every $100\,m$ from $0\,m$ to TD. For vertical wells ($TD_{MD} - TD_{TVD} < 5\,m$), inclination $\le 1.5^\circ$. For deviated wells, distribute dogleg smoothly up to `max_dls_deg_30m`. | Stage N/S | `P2` |
| **WH-10** | Detailed Fishing Records | `PARTIAL` | For any `workover_history` row where `outcome = 'FAILED'`, synthesize fish details: Fish Top ($TOF$) placed $10 \dots 50\,m$ above pump depth, fish type matching failure code (e.g. parted rod or parted tubing). | Stage S | `P2` |
| **WH-13** | Fluid Lab Chemistry ($H_2S$, $CO_2$, $WAT$) | `PARTIAL` | Assign formation-level properties: Tipam sand = Sweet ($H_2S < 2\,ppm$, $CO_2 < 0.5\%$, $API=28^\circ$, $WAT=34^\circ C$, Wax 11%); Barail = Light sweet ($H_2S=0$, $CO_2 < 0.2\%$, $API=32^\circ$). | Stage N/S | `P1` |
| **WH-14** | Wellhead Rating & Annulus Pressure | `GAP` | Assign Wellhead API rating based on field max THP class (Geleki = API 3000 / $210\,kg/cm^2$; Lakwa = API 2000). Annulus 'A' pressure synthesized as $0.05 \dots 0.15 \times CHP$ unless casing leak. | Stage S | `P1` |
| **WH-17** | Kill Mud Weight & Capacity | `PARTIAL` | Calculate directly: $\rho_{kill} = (SBHP_{kgcm2} \times 10 / TVD_m) + 0.04$. Casing internal volume calculated from casing ID and TVD. | Stage S | `P1` |
| **WH-19** | Contacts & Sign-off Roles | `GAP` | Standardized ONGC Assam Asset operational directory template mapped to field name (`Geleki Base Office, Nazira`, `Sivasagar Asset HQ`). | Stage S | `P3` |

*Priority Legend:*  
* `P1` (**Blocking Field Operations**): Mandatory safety/drift data without which a field engineer cannot run equipment.  
* `P2` (**Operational Hygiene**): Standard engineering records needed for derrick tallies and deviation clearances.  
* `P3` (**Advisory / Administrative**): Governance directory, contacts, and signature stamps.

---

## 4. Acceptance Criteria for Future HTML Report Generation

The generated `well_history_<well_id>.html` file must satisfy the following strict quality and performance gates:

1. **Zero Hallucinated Numbers (Fact-Slot Rule):** Every single quantity, rate, pressure, depth, diameter, and date must be sourced directly from the database or deterministic synthetic rule engine. Zero unslotted digits in template prose.
2. **Prominent Synthetic Watermark:** The report header and print background must display:  
   `"SYNTHETIC DATA DEMO — FOR ONGC WORKOVER OPERATIONS EVALUATION ONLY"`.
3. **Official ONGC Corporate Branding:** Standard ONGC mahogany red (`#990000`) and navy blue (`#123b5c`) styling with corporate logo placeholder in top-left header.
4. **Strict Commercial Compliance:** Absolutely **no** currency symbols ($₹, \$, €, £$), currency words ("Rupees", "USD", "lakhs", "crores"), or financial accounting metrics ("NPV", "Payback", "ROI") appear anywhere. Effort is stated solely as **Cost Band (`LOW`, `MED`, `HIGH`)** and **Rig-Days**.
5. **Print & PDF Fidelity (A4 Ready):** HTML must incorporate CSS paged media rules (`@page { size: A4 portrait; margin: 12mm; }`). Tables and SVG schematics must include `page-break-inside: avoid;`.
6. **Universal Scalability:** The SVG wellbore schematic and layout must render correctly across all **412 wells** in the portfolio (Geleki: 142, Lakwa: 160, Lakhmani: 110) without overflowing or script exceptions.
7. **Performance Benchmark:** Server-side compilation to complete HTML string must execute in $\le 1.5\,\text{seconds}$, with full client DOM visual rendering in $\le 3.0\,\text{seconds}$.

---

## 5. Complete Concrete Example: Well GK-129 (Geleki Field)

The following example populates the Pre-field Well Pack for **Well GK-129** using **ONLY real values directly retrieved from the WellPulse parquet tables and analytics tools**. Where an element belongs to the Data Gap Register, it is explicitly flagged `[GAP - Synthetic Rule Applied]`.

### Header & Identity
```
====================================================================================================
ONGC ASSAM ASSET · SURFACE & SUBSURFACE OPERATIONS · PRE-FIELD WELL PACK
WELL ID: GK-129            FIELD: Geleki            CLUSTER: GK-NE            ASSET: Assam
LATITUDE: 26.995715 N      LONGITUDE: 94.829754 E   SPUD DATE: 1976-05-04     COMPLETION: 1976-08-09
ZONE: Tipam                LIFT: SRP                STATUS: ACTIVE / UNDERPERFORMING
TOTAL DEPTH (MD): 3438.0 m TOTAL DEPTH (TVD): 3379.9 m PERFS: 3335.4 m - 3383.1 m (Tipam Sand)
REPORT DATE: 2026-09-30    DATA SOURCE: Synthetic Ingestion (WellPulse v0.4 Benchmark)
====================================================================================================
```

### Section Walkthrough for GK-129

#### WH-01: Header & Well Identity
* **Well ID:** `GK-129`
* **Field / Cluster:** `Geleki` / `GK-NE` (Assam Asset)
* **Surface Coordinates:** `26.995715° N, 94.829754° E`
* **Dates:** Spud: `1976-05-04` | Completion: `1976-08-09` | Well Age: `50.4 years`
* **Depths:** Total Depth MD: `3438.0 m` | Total Depth TVD: `3379.9 m` | PBTD: `3434.4 m`
* **Active Reservoir Zone:** `Tipam` Sandstone (`3294.8 m` to `3438.0 m MD`)

#### WH-02: Site Access, Surface Facilities & HSE Notes
* **Gathering Station:** Connected to `Geleki GGS-I` via cluster `GK-NE` trunk flowline.
* **Surface Flowline:** `4-inch` carbon steel flowline, approx. `1.8 km` to GGS-I. Operating pressure: `4.5 kg/cm²`.
* **Access Road:** Black-topped approach road from Nazira-Geleki highway; all-weather access. `[GAP - Synthetic Rule Applied]`
* **Plinth Dimensions:** $40\,m \times 40\,m$ compacted gravel pad, suitable for 50-tonne workover rig. `[GAP - Synthetic Rule Applied]`
* **HSE Notes:** Proximity to tea garden plantation boundary ($120\,m$). Standard PPE and noise baffling required.

#### WH-03: Current Status & Latest Well Test
* **Current Health Bucket:** `UNDERPERFORMING` (TC-020)
* **Status Reason:** TC-001 residual $\le -20\%$ over last 7 consecutive producing days (latest: $-30.6\%$).
* **Current 7-Day Mean Rates:** Oil: `13.4 BOPD` | Water Cut: `83.9%` | Gas: `7.3 MSCFD` | Last Producing Day: `2026-09-23`.
* **Latest Well Test:** `TST-GK-129-20260927` (`2026-09-27`):
  * Test Duration: `24.0 hrs` | Oil: `13.1 BOPD` | Water: `69.3 BWPD` | Gas: `7.2 MSCFD`
  * Surface Pressures: $THP = 4.2\,kg/cm^2$ | $CHP = 20.7\,kg/cm^2$
  * Fluid Level: `1300.8 m` | Test Quality: `GOOD`

#### WH-04: Wellbore & Completion Diagram (GK-129 Parameters)
* **Casing Shoes:**
  * Conductor 20": Shoe at `63.4 m MD` (Cement to surface `0.0 m`).
  * Surface 13-3/8": Shoe at `604.5 m MD` (Cement to surface `0.0 m`).
  * Production 5-1/2": Shoe at `3434.4 m MD` (Cement Top at `2435.7 m MD`).
* **Tubing String:** 2-7/8" Tubing from surface to `3293.8 m MD`.
* **Subsurface Pump:** Insert Rod Pump (Plunger 1.25", Stroke 100") at `3293.8 m MD`.
* **Tubing Anchor Catcher:** Set at `3301.1 m MD`.
* **Perforations:** Tipam Sand interval `3335.4 m` to `3383.1 m MD` (`OPEN`, 6 SPF).
* **Formations:** Alluvium (0–412.4m), Namsang (412.4–1110.3m), Girujan (1110.3–3294.8m), Tipam (3294.8–3438.0m).

#### WH-05: Casing, Tubing & Completion Components (incl. Minimum ID Drift)
| String / Component | OD ($in$) | Weight ($ppf$) | Grade | Top MD ($m$) | Shoe / Base ($m$) | Cement Top ($m$) | Nom. ID ($in$) | Drift ID ($in$) | Installed Date |
|---|---|---|---|---|---|---|---|---|---|
| **Conductor Casing** | 20.000 | 94.0 | H-40 | 0.0 | 63.4 | 0.0 | 19.124 | 18.936 `[GAP]` | 1976-08-09 |
| **Surface Casing** | 13.375 | 54.5 | K-55 | 0.0 | 604.5 | 0.0 | 12.615 | 12.459 `[GAP]` | 1976-08-09 |
| **Production Casing**| 5.500 | 15.5 | K-55 | 0.0 | 3434.4 | 2435.7 | 4.950 | 4.825 `[GAP]` | 1976-08-09 |
| **Tubing String** | 2.875 | 6.5 | J-55 | 0.0 | 3293.8 | — | 2.441 | 2.347 `[GAP]` | 2026-01-14 |
| **Insert SRP Pump** | 2.875 | — | — | 3293.8 | 3301.1 | — | 1.250 | — | 2026-01-14 |
| **Tubing Anchor** | 2.875 | — | — | 3301.1 | 3302.1 | — | 2.441 | 2.250 `[GAP]` | 2026-01-14 |
*Minimum Drift Clearance:* $4.825\,in$ through production casing; $2.250\,in$ through BHA anchor restriction.

#### WH-06: Tubing Joint-by-Joint Tally
* **Total String Length:** `3293.8 m`
* **Joint Count:** `348 joints` (average length $9.46\,m$) `[GAP - Synthetic Rule Applied]`
* **Sample Tally (Lowest 3 Joints above Pump):**
  * Joint #346: Length $9.44\,m$ | Base Depth: $3274.92\,m$ | Grade J-55 EUE
  * Joint #347: Length $9.51\,m$ | Base Depth: $3284.43\,m$ | Grade J-55 EUE
  * Joint #348: Length $9.37\,m$ | Base Depth: $3293.80\,m$ | Grade J-55 EUE

#### WH-07: Perforation Intervals & Formation Lithology
* **Active Perforations:**
  * Zone: `Tipam` Sand | Top: `3335.4 m` | Bottom: `3383.1 m` | Shot Density: `6 SPF` | Status: `OPEN` | Date: `1976-08-09`.
* **Geological Lithology Column:**
  * `0.0 m – 412.4 m`: **Alluvium** — Unconsolidated sand and clay.
  * `412.4 m – 1110.3 m`: **Namsang Formation** — Sandstone with clay and pebble beds.
  * `1110.3 m – 3294.8 m`: **Girujan Clay Formation** — Mottled claystone / impermeable seal.
  * `3294.8 m – 3438.0 m`: **Tipam Sandstone Formation** — Massive sandstone reservoir with minor shale interbeds.

#### WH-08: Well Deviation & Directional Survey
* **Max Recorded Dogleg Severity:** `0.85° / 30m` at 1850 m MD `[GAP - Synthetic Rule Applied]`
* **Total Depths:** Measured Depth = `3438.0 m` | True Vertical Depth = `3379.9 m` (Delta = `58.1 m`).
* **Profile Type:** Slight naturally deviated S-turn; maximum inclination $4.2^\circ$ at $2100\,m\,MD$. Wellhead to target bottom-hole horizontal displacement = $64.2\,m$.

#### WH-09: Chronological Life-of-Well Timeline (Intervention History)
| Workover ID | Start Date | End Date | Job Code | Failure Code | Outcome | Rig Days | Uplift BOPD | Report Document ID |
|---|---|---|---|---|---|---|---|---|
| `WO-GK-129-2019` | 2019-05-10 | 2019-05-13 | `WSO_STRADDLE` | `TUBING_LEAK` | `FAILED` | 3.0 | 1.5 | `DOC-SCAN-GK-129-2019` |
| `WO-GK-129-P001` | 2021-12-13 | 2021-12-15 | `JOB_PUMP_WEAR` | `PUMP_WEAR` | `SUCCESS` | 3.0 | 19.7 | `DOC-SCAN-GK-129-P001` |
| `WO-GK-129-P002` | 2022-10-09 | 2022-10-13 | `JOB_TUBING_LEAK` | `TUBING_LEAK` | `FAILED` | 5.0 | 4.0 | `DOC-SCAN-GK-129-P002` |
| `WO-GK-129-P003` | 2023-01-30 | 2023-01-31 | `JOB_SURFACE` | `SURFACE` | `FAILED` | 0.0 | 19.2 | `DOC-SCAN-GK-129-P003` |
| `WO-GK-129-P004` | 2023-05-19 | 2023-05-21 | `JOB_PUMP_WEAR` | `PUMP_WEAR` | `SUCCESS` | 3.0 | 16.7 | `DOC-SCAN-GK-129-P004` |
| `WO-GK-129-003` | 2023-11-27 | 2023-11-29 | `JOB_WAX` | `WAX` | `SUCCESS` | 4.0 | 13.7 | `DOC-SCAN-GK-129-004` |
| `WO-GK-129-006` | 2024-09-21 | 2024-10-24 | `JOB_TUBING_LEAK` | `TUBING_LEAK` | `SUCCESS` | 35.0 | 10.5 | `DOC-SCAN-GK-129-007` |
| `WO-GK-129-009` | 2025-08-04 | 2025-08-06 | `JOB_SUDDEN_MECH` | `SUDDEN_MECH` | `SUCCESS` | 4.0 | 8.6 | `DOC-SCAN-GK-129-010` |
| `WO-GK-129-012` | 2026-01-12 | 2026-01-14 | `JOB_TUBING_REPLACE`| `TUBING_LEAK` | `SUCCESS` | 4.0 | 7.8 | `DOC-SCAN-GK-129-013` |

#### WH-10: Failure, Fishing & Wellbore Obstruction Log
* **Repeat Failure Warning:** `TUBING_LEAK` recurred 3 times (`2022-10`, `2024-09`, `2026-01`).
* **Failed Jobs on Record:**
  * `2019-05-10`: Straddle packer water shut-off failed due to micro-annular channelling behind casing.
  * `2022-10-09`: Tubing leak repair failed initial pressure test; pulled and re-ran string.
  * `2023-01-30`: Surface stuffing box packing failed on restart.
* **Fish Left in Hole:** None currently reported above perforations. Wellbore clear down to PBTD `3434.4 m`.

#### WH-11: Historical Production Trends & Intervention Markers
* **Historical Production Horizon:** 2021-10-01 to 2026-09-30 (60 months continuous series).
* **Decline Baseline:** Current Arps expected oil = `19.3 BOPD`; Actual oil = `13.4 BOPD` (Residual = `-30.6%`).
* **Water Cut History:** Steeper water-oil ratio ($WOR'$) slope $+0.35$ indicating channeling breakthrough starting Q2 2025.
* **Intervention Markers:** Spikes corresponding to workovers in Dec 2021 (+19.7 BOPD), May 2023 (+16.7 BOPD), and Oct 2024 (+10.5 BOPD).

#### WH-12: Reservoir Pressure, Temperature & Lift Telemetry
* **Latest Pressure Survey:** `PS-GK-129-20260120` (`2026-01-20`):
  * Static BHP: `228.4 kg/cm²` (3248 psi) at Datum TVD `3279.0 m`.
  * Flowing BHP: `164.2 kg/cm²` (2335 psi).
  * Productivity Index: `0.32 bpd / (kg/cm²)`.
  * Fluid Level: `2074.6 m`.
* **Surface Pressures:** Wellhead $THP = 4.2\,kg/cm^2$, Casing $CHP = 20.7\,kg/cm^2$, $WHT = 48.5^\circ C$.
* **SRP Parameters:** Pump Setting Depth = `3293.8 m` | Plunger = `1.25 in` | Stroke = `100.0 in` | Rod Grade = `K` | Casing Vented = `False`.

#### WH-13: Fluid Properties, Flow Assurance & Subsurface Hazards
* **API Gravity:** `29.2° API` (Medium crude). `[GAP - Synthetic Rule Applied]`
* **Wax Properties:** Wax Content = `12.4% wt` | Wax Appearance Temp ($WAT$) = `36.5° C`. Paraffin scraping required bi-annually.
* **Water Chemistry:** TDS = $4200\,mg/L$, Chlorides = $2100\,mg/L$. Moderate scaling risk on depressurization.
* **Toxic Gas Hazard:** $H_2S = 0\,ppm$ (Sweet Geleki Tipam crude) | $CO_2 = 0.35\,mol\%$. Standard safety procedures apply.

#### WH-14: Well Integrity, Barrier Status & Wellhead Pressure Ratings
* **Wellhead Rating:** Breda / Cameron Wellhead, API 3000 rating ($210\,kg/cm^2$). `[GAP - Synthetic Rule Applied]`
* **Annulus Pressures:** Annulus 'A' ($CHP$) = `20.7 kg/cm²` (live gas-oil cushion). Annulus 'B' = `0.0 kg/cm²`.
* **Casing Age:** Surface & Production casing in ground for `50.1 years` (installed `1976-08-09`).
* **CBL Integrity:** `DOC-CBL-GK129-1998` confirmed poor acoustic bond across interval `3290–3330 m MD` (risk of vertical migration).

#### WH-15: Current Diagnosis & Recommended Next Best Action (NBA)
* **Diagnosis:** Health bucket `UNDERPERFORMING`. Water-oil ratio slope $+0.35$ confirms subsurface channelling behind casing.
* **Attribution Loss (TC-019):** 180-day lost production = `338.0 bbl` oil. Largest factor class: `SUBSURFACE` (100% of loss, non-controllable by routine choking).
* **Recommended Next Best Action (Rank 1):**
  * **Job Code:** `CEMENT_SQUEEZE` (Intervention Class `IC-11`: Water shut-off squeeze).
  * **Job Description:** Block cement squeeze across wet channeling channels + reperforation of upper Tipam interval.
  * **Expected Uplift:** `+5.9 BOPD` | 12-Month Deferred Barrels Avoided = `1961 bbl`.
  * **Success Probability:** $p_{success} = 0.59$ ($n=15$ Geleki SRP squeeze operations; asset prior $0.576$).
  * **Operational Effort:** Rig required (`WORKOVER_RIG`), Duration: `7.0 to 9.0 days` (Planned: `8.0 rig-days`).
  * **Cost Band:** **`HIGH`** (*Strictly no currency/rupees/USD*).
  * **MRO Spares Status:** `TRANSFER_REQUIRED` (Cement retainer & perforating gun assembly to be requisitioned).
  * **Risk Flags:** `WELL_INTEGRITY` (50-year-old casing requires low squeeze pressure), `LOGISTICS_DELAY`.
  * **SOP Link:** `SOP-WSO-002` (Standard Operating Procedure: Water Shut-Off Squeeze).
* **Counterfactual Analysis (TC-027):** Alternative considered was `PUMP_OVERHAUL` (`IC-01`). Rejected because pump mechanical efficiency is $>82\%$; mechanical overhaul would produce higher water volumes without arresting the root water channeling.

#### WH-16: Offset & Nearby Well Performance (Same Cluster GK-NE)
| Offset Well ID | Distance ($m$) | Zone | Lift Type | Health Bucket | Oil Rate ($BOPD$) | Water Cut (%) | Last Job Code & Date |
|---|---|---|---|---|---|---|---|
| **GK-108** | 428.2 | Barail | GAS_LIFT | `PRODUCING_OK` | 72.5 | 77.6% | `GLV_REPLACE` (2026-08-21) |
| **GK-065** | 573.9 | Barail | GAS_LIFT | `PRODUCING_OK` | 25.2 | 66.2% | `GLV_REPLACE` (2026-07-19) |
| **GK-079** | 609.4 | Lakadong | SRP | `PRODUCING_OK` | 48.0 | 66.1% | `SAND_CLEANOUT` (2026-08-14) |
| **GK-102** | 717.4 | Tipam | GAS_LIFT | `PRODUCING_OK` | 70.0 | 79.7% | `SURFACE_REPAIR` (2026-07-10) |
*Offset Reservoir Note:* Immediate Tipam offset `GK-102` demonstrates high liquid potential (`~345 BLPD`), confirming good reservoir pressure support in this sector.

#### WH-17: Job Prerequisites & Engineering Mobilisation Checklist
* **Kill Fluid Calculation:**
  * Datum Reservoir Pressure ($SBHP$): `228.4 kg/cm²` at TVD `3379.9 m`.
  * Hydrostatic Gradient required: $228.4 \times 10 / 3379.9 = 0.676\,kg/cm^2/10m \approx 0.985\,SG$.
  * Required Kill Fluid Density with Safety Margin: **`1.03 SG`** ($8.6\,ppg$ treated $KCl$ brine / formation water).
  * Wellbore Volume to Perforations: $38.4\,m^3$ ($241\,bbl$).
* **Equipment & Rig Class:** 50-tonne workover rig, 3000-psi Double Ram BOP stack, 2-7/8" workstring.
* **Permits:** Internal Work Permit (`PTW-WO-GK129`), DGMS electrical clearance for mast hoisting near plantation lines.

#### WH-18: Historical & Technical Document Index (D1–D11)
| Document ID | Doc Type | Document Date | Title / Description | Direct Link |
|---|---|---|---|---|
| `DOC-CBL-GK129-1998` | `D05` | 1998-04-15 | Cement Bond Log & Micro-Annulus Report GK-129 (1998) | `/api/docs/DOC-CBL-GK129-1998.pdf` |
| `DOC-SCAN-GK-129-2019` | `D02` | 2019-05-14 | GK-129 Workover Completion Report — Straddle Packer WSO | `/api/docs/DOC-SCAN-GK-129-2019.pdf` |
| `DOC-SCAN-GK-129-P001` | `D02` | 2021-12-15 | GK-129 Workover Completion Report — PUMP_OVERHAUL | `/api/docs/DOC-SCAN-GK-129-P001.pdf` |
| `DOC-SCAN-GK-129-P002` | `D02` | 2022-10-13 | GK-129 Workover Completion Report — TUBING_REPLACE | `/api/docs/DOC-SCAN-GK-129-P002.pdf` |
| `DOC-SCAN-GK-129-P003` | `D02` | 2023-01-31 | GK-129 Workover Completion Report — SURFACE_REPAIR | `/api/docs/DOC-SCAN-GK-129-P003.pdf` |
| `DOC-SCAN-GK-129-P004` | `D02` | 2023-05-21 | GK-129 Workover Completion Report — PUMP_OVERHAUL | `/api/docs/DOC-SCAN-GK-129-P004.pdf` |
| `DOC-SCAN-GK-129-004` | `D02` | 2023-11-29 | GK-129 Workover Completion Report — WAX_SCRAPE | `/api/docs/DOC-SCAN-GK-129-004.pdf` |
| `DOC-SCAN-GK-129-007` | `D02` | 2024-10-24 | GK-129 Workover Completion Report — TUBING_REPLACE | `/api/docs/DOC-SCAN-GK-129-007.pdf` |
| `DOC-SCAN-GK-129-010` | `D02` | 2025-08-06 | GK-129 Workover Completion Report — ROD_REPLACE | `/api/docs/DOC-SCAN-GK-129-010.pdf` |
| `DOC-SCAN-GK-129-013` | `D02` | 2026-01-14 | GK-129 Workover Completion Report — TUBING_REPLACE | `/api/docs/DOC-SCAN-GK-129-013.pdf` |
| `SOP-WSO-002` | `D11` | 2024-01-10 | SOP: Water Shut-Off Squeeze & Reperforation Guidelines | `/api/docs/SOP-WSO-002.pdf` |

#### WH-19: Key Operational Contacts & Sign-off Block
* **Operational Directory (Geleki Base / Nazira HQ):**
  * Surface Manager (Geleki Field): Phone: `+91-3772-25XXXX` | VHF Ch: `16`
  * Workover Rig Superintendent: Phone: `+91-3772-26XXXX` | Rig Base: Nazira Central Yards
  * Geleki GGS-I Control Room: Phone: `+91-3772-24XXXX` (24/7)
  * Fire & Emergency Response: Phone: `101` / `+91-3772-22XXXX`
* **Pre-Field Sign-Off Authorization:**
  * Prepared by: `Field Engineer (Workover Operations)` · Date: `2026-09-30`
  * Reviewed by: `Lead Reservoir Engineer (Assam Asset)` · Date: `2026-09-30`
  * Authorized for Rig Mobilisation: `Surface Manager (Geleki Asset)` · Date: `2026-09-30`
