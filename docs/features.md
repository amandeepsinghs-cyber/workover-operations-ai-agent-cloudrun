# Feature Catalog & Roadmap (`features.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 3.0.0 (v0.4 verbatim expansion)
**Date:** 2026-10-07
**Status:** Approved for build (all decisions resolved, §7; autonomous run authorised 2026-10-07)
**Source of truth:** [`verbatim.md`](../verbatim.md) (repo root), the stakeholder brief for the demo to Ajay Ratan, ED, ONGC IDWE Dehradun. §1 = Transcript 1 (**T1**), §3 = Transcript 2 (**T2**), §2 = work-stream breakdown (**WS-n**). §4–§8 were written afterwards by an agent; their numbers are **illustrative and not in the data**.
**Companion docs:** [`BRD.md`](./BRD.md) · [`BDD.md`](./BDD.md) · [`SDD.md`](./SDD.md) · [`build.md`](./build.md) · [`checklist.md`](./checklist.md) · [`DELEGATION.md`](./DELEGATION.md) · [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md)
**Previous version:** 2.0.0 (FEAT-01…FEAT-16, MoSCoW). Those features are now the **baseline** in §1.

> [!IMPORTANT]
> Every feature below cites a verbatim anchor. Anything without one is labelled **derived**, with the reason. Routes, module paths and component names follow [`SDD.md`](./SDD.md) §4 and §13, which are authoritative.

---

## 0. Scope in one line

**WellPulse becomes the ONGC workover demo product: every verbatim capability (F-01…F-19) is built on top of the existing React/FastAPI app by porting the sibling ADK repo's data generator and deterministic tools into `backend/app/analytics/` and replacing prompt-stuffing, hard-coded health, fabricated USD recommendations and the fake "Live" (D-10, D-11, D-12).**

### Status legend
| Tag | Meaning |
|---|---|
| `EXISTS` | Works today in WellPulse; kept, possibly extended to multi-field |
| `PARTIAL` | Some of it works today; the gap is stated |
| `REPLACE` | Exists today but is wrong (fabricated, hard-coded or fake); superseded |
| `NEW` | Net-new in WellPulse v0.4 |

---

## 1. Baseline: existing WellPulse features (FEAT-01…FEAT-16)

**Six of sixteen baseline features must be replaced, because they fabricate or hard-code what the demo has to prove.** The UI shell (map, charts, split pane, language toggle) survives; the data, health logic, recommendations, chat engine and voice transport do not.

| ID | Baseline feature (v2.0.0) | Status | Why | Superseded / extended by |
|---|---|---|---|---|
| FEAT-01 | Esri satellite GIS map, tagged wellheads, Dark SCADA toggle (`WellMap.tsx`) | `EXISTS` | Works; Esri basemap kept for all fields (D-5) | Extended by **F-17** (multi-field, clusters, field filter), F-05 |
| FEAT-02 | 3-tier health status 🟢/🟡/🔴 | `REPLACE` (logic) | Status is **hard-coded** 32/12/6 by `random.seed(42)` in `data_generator.py`, not computed | **F-02** (TC-020 computed buckets); badges/filters kept |
| FEAT-03 | 24-month telemetry charts (`TelemetryCharts.tsx`) | `EXISTS` | Works on the JSON series | Extended by **F-12** (2–5 yr, intervention markers) and **F-11** (field aggregate); data via repository layer (D-11) |
| FEAT-04 | Workover timeline (`WorkoverTimeline.tsx`) | `PARTIAL` | Shows `cost_usd` and `contractor` point values, which violate D-1 | Cost → band + rig-days (D-1); extended by **F-06**, **F-12** |
| FEAT-05 | Split-pane contextual AI chat | `REPLACE` (engine) | `build_well_context` stuffs well JSON into the prompt; numbers cannot be traced | **F-18** via ADK `Runner` tool calling (D-10, D-12); panel kept |
| FEAT-06 | Voice mic UI and STT | `PARTIAL` | Code uses a MediaRecorder upload to `POST /api/wells/{id}/audio`, not streaming | **F-07** (16 kHz AudioWorklet streaming); visuals kept |
| FEAT-07 | TTS with Indian voices (browser `speechSynthesis`) | `REPLACE` | Not Gemini audio; root cause of "Live not working well" | **F-07** (native 24 kHz Live audio); `speechSynthesis` kept only for the text fallback |
| FEAT-08 | Prescriptive recommendations & payback | `REPLACE` | `generate_structured_recommendation` returns hard-coded actions per status with fabricated `estimated_cost_usd`, uplift and payback | **F-04** (TC-022), **F-13** (TC-027), **F-14** (SOP links) |
| FEAT-09 | 50-well Geleki synthetic engine (`GLK-101…150`) | `REPLACE` | One 7.6 MB JSON; dates relative to `now()` (non-reproducible); Geleki only | **F-08** (ported ADK generator, 3 fields, 60 months, D-2/D-11) |
| FEAT-10 | `run_local.sh` local runner | `PARTIAL` | pip, and `requirements.txt` omits `requests` | uv + `pyproject.toml` (D-14), Stage M — *derived: build hygiene* |
| FEAT-11 | Engineering reports (WCR, DWR, BHP/Sonolog, water chemistry) | `PARTIAL` | 4 inline dicts per well; no documents, no citations | **F-10** (D1–D11 PDF corpus); `WellReportsTab.tsx` reads real documents |
| FEAT-12 | Hinglish / English / Hindi copilot, 2–3 sentence voice cap | `EXISTS` | Toggle works | Kept in **F-07**; integrity rule applies in every language (X-6) |
| FEAT-13 | "Vertex AI Gemini 2.5 Flash ADC" + semantic fallback | `REPLACE` | Doc is wrong: code calls the Generative Language REST API with `GEMINI_API_KEY` and `gemini-3.8-flash`; fallback is keyword-based | Vertex AI + ADC, key removed (D-12); text model stays `gemini-3.8-flash` (D-13); fallback must not emit numbers (X-1) |
| FEAT-14 | Geleki GGS-1/2/3 + CDP and flowlines | `PARTIAL` | Topology drawn for `GLK-` wells only | **F-05** clusters (Lakwa / Lakhmani GGS, Geleki blocks); regenerated for `GK-` wells |
| FEAT-15 | One-click dossier export (JSON / Markdown) | `PARTIAL` | Dumps the 4 report dicts; no aggregation | **F-06** (TC-023 PDF) upgrades `GET /api/wells/{id}/export` |
| FEAT-16 | Cloud Run deployment (`wellpulse-app`, `us-central1`) | `EXISTS` | Public service runs today | Stage W redeploy of `wellpulse-app` in `workover-operations-agentic-ai` (D-4) |

---

## 2. v0.4 feature summary (F-01…F-19)

**Seventeen of the nineteen features are new or replace baseline behaviour; only F-12 and F-17 build on working WellPulse UI, and F-19 is process.** Build order follows data dependencies (stage letters from [`build.md`](./build.md)): M → N → O → P → Q → R → S → T → X → U → Y → V → W.

| ID | Feature | Verbatim anchor | Status in WellPulse | Tool contract(s) | BDD | Stage | UI surface in WellPulse |
|---|---|---|---|---|---|---|---|
| **F-01** | Decline root-cause attribution (human / controllable / uncontrollable) | T1: *"why did the production decline? Was it human factor, controllable factor…"* | `NEW` | TC-019 | BDD-F01-S01…S06 | P | Chat answer + `AttributionWaterfall` chart (field and well view) |
| **F-02** | Well-health screening (ok / not ok / not producing) | T1: *"which of the wells are doing okay… not producing now… already built"* | `REPLACE` (FEAT-02 hard-coded) | TC-020 | BDD-F02-S01…S05 | P | Header KPIs, map pin colours, status filter chips, `HealthBucketsCard` |
| **F-03** | ML intervention classifier (15 classes) | T1: *"classification algorithm… or let's say 15 type of interventions"* | `NEW` | TC-021 | BDD-F03-S01…S06 | Q | Top-3 class card in well view and chat |
| **F-04** | Next-best-action (production + history + construction) | T1: *"not just the production data, but also of the well history, the construction… next best action… currently not there"* | `REPLACE` (FEAT-08) | TC-022 | BDD-F04-S01…S05 | R | `NbaCard` (replaces `POST /recommendations` output) |
| **F-05** | Multi-field hierarchy Asset → Field → Cluster → Well | T1: *"Geleki… Lakwa… Lakhmani. So that there are three areas, with their individual cluster"* | `NEW` | TC-025, TC-016 v2 | BDD-F05-S01…S04 | N, T, Y | `FieldSelector`, cluster layer on `WellMap` |
| **F-06** | Field-engineer well-history dossier | T1: *"aggregate all the history and give it to the person who is going to the field"* | `PARTIAL` (FEAT-11/15) | TC-023 | BDD-F06-S01…S05 | S | "Dossier PDF" button; `POST /api/wells/{id}/dossier`, `GET /api/wells/{id}/export?format=pdf` |
| **F-07** | Real Gemini Live voice (ported from DI 2.0) | T1: *"Gemini Live is not working well in the current build… check how it is built in that Drilling Intelligence"* | `REPLACE` (fake WS) | Live proxy + voice tool subset | BDD-F07-S01…S08 | U | `VoiceAgentPanel.tsx` (AudioWorklet, `WS /ws/live`), language toggle kept |
| **F-08** | Synthetic data expansion: Lakwa, Lakhmani | T1: *"two more clusters… Lakwa and Lakhmani, build those wells as well"* | `REPLACE` (FEAT-09) | generator v2 (`backend/app/analytics/generator/`) | BDD-F08-S01…S06 | N | All screens (via `backend/app/data_access/`) |
| **F-09** | Asset-manager field performance | T1: *"Which particular field is not performing?… not currently being answered"* | `NEW` | TC-024 | BDD-F09-S01…S05 | T | `FieldComparisonTable` screen |
| **F-10** | Synthetic PDF document corpus | T1: *"generate the documents of PDF files of… well interventions and other documents… help to define it"* | `PARTIAL` (FEAT-11 dicts) | generator `docs_pdf`, TC-026 | BDD-F10-S01…S04 | O | `WellReportsTab.tsx`; `GET /api/docs/{doc_id}.pdf` |
| **F-11** | Field 5-year production history: tell, then plot | T2: *"the past let's say 5 year production data field-wise… Can you give me a plot?"* | `NEW` | TC-028 | BDD-F11-S01…S03 | N, T | `FieldHistoryChart` (Recharts, one line per field + water-cut panel) |
| **F-12** | Well deep-dive with nearby wells and intervention markers | T2: *"tell me more about this well… what are the different interventions happened in the past"*; *"also give information of nearby wells"* | `PARTIAL` (FEAT-03/04) | TC-029, TC-017 v2 | BDD-F12-S01…S05 | T | `WellDeepDive`, `TelemetryCharts.tsx` markers + WHT / GOR / gas-lift series, `NearbyWellsTable` |
| **F-13** | Counterfactual: "why this and not that?" | T2: *"Why are you recommending this against an alternative?… why not just wax removal?… super deep"* | `NEW` | TC-027 | BDD-F13-S01…S05 | R | `CounterfactualTable` in chat and well deep-dive |
| **F-14** | SOP library, cited in recommendations | T2: *"we need to generate a lot of documents… The SOPs"* | `NEW` | D11 docs, TC-026 | BDD-F14-S01…S02 | O, R | SOP link chips on each action |
| **F-15** | Medallion Lakehouse + production-store decision | T2: *"showcase that in the Medallion architecture… Lakehouse… BigQuery or… a better database"* | `NEW` | `lakehouse/`, `DATA_BACKEND` switch | BDD-F15-S01…S03 | X | None (backend); optional "data lineage" note in About |
| **F-16** | Role-based access (optional) | T2: *"Executive Director… versus a field engineer… If it is overcomplicating, we can leave it"* | `NEW` (optional) | `require()` at tool layer | BDD-F16-S01…S03 | Y | `PersonaPicker` in `Header.tsx` |
| **F-17** | Multi-screen interface showing fields and wells | T2: *"different screens opened… they can see different fields… and the wells"* | `PARTIAL` (FEAT-01, single field) | `/api/fields`, `/api/wells?field=` | BDD-F17-S01…S03 | T, Y | `App.tsx` tabs: asset map, field history, field comparison, priority queue, well deep-dive (+ docked voice panel) |
| **F-18** | Hierarchical 5-level demo flow L1–L5 | T2: *"do you see the hierarchy of question and answering?"* | `NEW` (acceptance) | all | BDD-F18-S01…S03 | V | Whole app; `POST /api/chat` |
| **F-19** | Delegation: orchestrator vs. Flash workers | T2: *"what are the tasks that Opus would do… outsourced to the Flash models… document generation"* | Process | — | BDD-F19-S01…S02 | all | — |

---

## 3. Feature detail

Module paths are relative to `wellpulse/`. Analytics code is ported from `../workover_well_intervention/tools/` and `generator/` (D-10).

### F-01 · Decline root-cause attribution — `NEW`
> T1: *"why did the production decline? Was it human factor, controllable factor, what kind of factors, right, that contributed?"* · WS-2: *"Controllable operational factors… subsurface/reservoir factors… human/operational factors (delayed maintenance, logistical bottlenecks)"*

**What it does:** For a well, cluster or field over a window, TC-019 splits lost oil (actual vs. Arps-expected) into a barrel-loss waterfall that sums to 100%, each part tagged with a factor class.

| Factor class | Controllable? | Examples |
|---|---|---|
| `SUBSURFACE` | No | Natural decline, water coning/channelling, depletion confirmed by offsets, sand influx |
| `EQUIPMENT` | Yes (maintenance) | Pump wear, rod part, tubing leak, gas-lift valve failure |
| `OPERATIONAL` | Yes (setpoints) | Choke/SPM changes, off-optimum gas-lift rate, wax/scale without a treatment programme |
| `HUMAN_PROCESS` | Yes (organisation) | Waiting on rig, waiting on material, deferred maintenance, missed tests |
| `EXTERNAL` | No | GGS power outage, bandh/strike, monsoon access loss |

**Rules:** "Human factor" = process delay, never individual blame (*derived: no operator names in data*). Unexplained residual is always shown; > 15% ⇒ `LOW_CONFIDENCE`. Every barrel traces to `daily_production`, `operations_events` or the TC-001 Arps fit.
**WellPulse build:** `backend/app/analytics/tools/attribution.py`; API `GET /api/fields/{field}/attribution`, `GET /api/wells/{id}/attribution`; React `components/field/AttributionWaterfall.tsx`.
**Gap today:** none of this exists; `wells_data.json` has no event or downtime-reason data.
**Acceptance:** BDD-F01-S01…S06; components sum to total loss within ±0.5%.

### F-02 · Well-health screening — `REPLACE` (FEAT-02)
> T1: *"which of the wells are doing okay, which of the wells are not doing okay, which of the wells are not producing now. So again, this is I think already built."*

**Finding:** It is *not* really built in WellPulse: the 32/12/6 split is seeded, not computed. The UI is.
**What it does:** TC-020 `classify_well_health(field, as_of, cluster_id=None)` returns four buckets, reusing the ported triggers A–D (TC-007). Rules are those of [`SDD.md`](./SDD.md) §6.3 (authoritative), evaluated at `AS_OF`:

| Bucket | Rule | REST `status` | WellPulse colour |
|---|---|---|---|
| `NOT_PRODUCING` | Open `well_status_history` episode ≠ `PRODUCING`; carries `reason`, `recoverable` | `failed` | 🔴 |
| `UNDERPERFORMING` | TC-001 `residual_pct ≤ −20` over 7 consecutive producing days (Trigger A) | `warning` | 🟡 (sub-label) |
| `AT_RISK` | Not above, and any of Trigger B/C/D fired (TC-007) | `warning` | 🟡 |
| `PRODUCING_OK` | Otherwise | `healthy` | 🟢 |

L2 wording *"sick or lost production"* = `AT_RISK` + `UNDERPERFORMING`; `NOT_PRODUCING` reported separately. `recoverable = false` when TC-004 says `RESERVOIR_DECLINE`.
**WellPulse build:** `analytics/tools/health.py`; `GET /api/wells/kpis?field=`, `GET /api/wells?status=` keep their shapes but read TC-020 (D-11); `GET /api/fields/{field}/health?cluster_id=` returns the buckets.
**Acceptance:** BDD-F02-S01…S05; KPI header, map and agent show identical counts.

### F-03 · ML intervention classifier — `NEW`
> T1: *"running machine learning algorithms on the production data… a classification algorithm… let's say 15 type of interventions"* · WS-3: *"10 to 15 standardized well intervention archetypes"*

**What it does:** TC-021 predicts top-3 of 15 intervention classes with probabilities and driving features (production signatures, construction, history).

| IC | Class | IC | Class |
|---|---|---|---|
| IC-01 | SRP pump change | IC-09 | Matrix stimulation (acid / frac) |
| IC-02 | Rod string repair | IC-10 | Perforation work |
| IC-03 | Tubing leak repair | IC-11 | Water shut-off squeeze |
| IC-04 | Wax removal / control | IC-12 | Zonal isolation |
| IC-05 | Scale removal / inhibition | IC-13 | Coning control (choke back) |
| IC-06 | Sand cleanout / control | IC-14 | Surface and integrity repair |
| IC-07 | Gas-lift valve change (`GLV_REPLACE`, new code; K-2) | IC-15 | No job justified / terminal |
| IC-08 | Lift optimisation / conversion — includes ESP replacement (verbatim WS-3; explicit mapping, no ESP wells in the data) | | |

**Labels:** `workover_history.catalogue_job_code` + `intervention_class` added (fixes K-1: `job_code` copies the failure code).
**WellPulse build:** `analytics/model/` (train, features, calibrate); artefact loaded at startup; result card in `WellDetails.tsx`.
**Acceptance (Gate Q):** holdout macro-F1 0.70–0.92 (≥ 0.70 floor, ≤ 0.92 leakage ceiling); top-3 ≥ 0.90; beats TC-008 rules by ≥ 0.05; ECE ≤ 0.08; ≥ 30 examples per class.

### F-04 · Next-best-action — `REPLACE` (FEAT-08)
> T1: *"depending on not just the production data, but also of the well history, the construction, one can recommend what is the next best action… currently not there"* · WS-3: *"expected uplift (bopd), estimated cost, and risk profile"*

**What it does:** TC-022 combines F-03 ML + physics guardrails + economics + logistics into a ranked top-3 per well (and a batch priority list for L3). Each action: job code + IC, uplift (BOPD) and 12-month deferred barrels (TC-009), p(success) with n, rig-days and rig/rigless, **cost band `LOW`/`MED`/`HIGH`**, risk (integrity, repeat failures, HSE), MRO (TC-011) and rig slot (TC-015), `sop_doc_id` (F-14), narrative + rejected alternatives.
**Guardrails (non-overridable):** (1) Chan negative slope = coning ⇒ choke back; ML cannot invert. (2) `offset_verdict = RESERVOIR_DECLINE` ⇒ `NO_JOB_JUSTIFIED` (fixture LKM-090). (3) ML vs. physics disagreement ⇒ flag `MODEL_PHYSICS_DISAGREEMENT`, both shown (SDD §9.1 G-3). (4) No ₹/USD point estimates (D-1).
**WellPulse build:** `analytics/tools/nba.py`; `POST /api/wells/{id}/recommendations` keeps its route but returns TC-022; `GET /api/wells/{id}/nba`; `GET /api/fields/{field}/priority` for L3. **Ranking:** deferred bbl (12 mo) × p(success) ÷ rig-days, shown with the cost band (K-7; resolves verbatim NPV ranking). `generate_structured_recommendation` is deleted.
**Acceptance:** BDD-F04-S01…S05; no field named `*_usd`, `payback` or `roi` in any response.

### F-05 · Multi-field hierarchy — `NEW`
> T1: *"every well, there should be multiple wells in an area, and there can be different areas… Geleki… Lakwa… Lakhmani… three areas, with their individual cluster"*

| Field | IDs | Wells | Clusters | Designed story |
|---|---|---|---|---|
| Geleki | `GK-001…GK-142` | 142 | `GK-NE`, `GK-CENTRAL`, `GK-SW` | Baseline; hero GK-129 (channelling) |
| Lakwa | `LKW-001…LKW-160` | 160 | `LKW-GGS-I/II/III` | Underperformer, about −18% vs. target «pinned after Stage N»; mostly controllable |
| Lakhmani | `LKM-001…LKM-110` | 110 | `LKM-GGS-I/II` | Sand + gas-lift; refusal well |

**Fixtures (D-11):** LKW-047 (41 d waiting on rig + 12 d on material → pump change), LKW-112 (channelling), LKW-088 (GGS-II outages), LKM-023 (sand), LKM-061 (GLV + wax; D-7 backup), LKM-090 (reservoir decline ⇒ no job).
**WellPulse build:** TC-025 `analytics/tools/hierarchy.py`; `GET /api/fields` (hierarchy incl. clusters); `WellMap.tsx` cluster polygons; coordinates synthetic near Sivasagar, labelled synthetic (D-3).
**Acceptance:** BDD-F05-S01…S04.

### F-06 · Field-engineer dossier — `PARTIAL` (FEAT-11, FEAT-15)
> T1: *"when a person is going to the field, the previous history is not there… aggregate all the history and give it to the person who is going to the field operations"* · WS-4: *"past intervention histories, well architecture, casing/tubing tallies, and lithology"*

**What it does:** TC-023 `build_well_dossier(well_id)` → 2–4 page PDF + chat summary card: identity/map link; construction (casing tally, tubing/BHA, perforations, schematic); **lithology / zone column** from `formation_tops` (*verbatim gap, added; D-19*); last 90 days + last test; full intervention timeline; repeat-failure patterns; diagnosis + NBA (F-04); hazards and lessons cited from documents (e.g. GK-129's 2019 failed WSO); MRO and rig slot; source document list.
**WellPulse build:** `analytics/tools/dossier.py` (ReportLab); `POST /api/wells/{id}/dossier`; `GET /api/wells/{id}/export` (JSON, adds `pdf_url`) and `?format=pdf`. English-only dossier (Q-2).
**Acceptance:** BDD-F06-S01…S05; ≤ 10 s; every number traces to a row or a cited document; no LLM prose inside the PDF.

### F-07 · Real Gemini Live voice — `REPLACE` (fake Live)
> T1: *"this particular Gemini Live is not working well in the current build. It is working very good in Drilling Intelligence 2.0. So check how it is built"* · WS-5: *"Voice/Multimodal Real-Time Assistant… hands-free field technician operation"*

**Finding:** `WS /api/wells/{id}/live` advertises `gemini-live-bi-directional` but wraps the text chat; audio out is browser `speechSynthesis`. That answers prior SDD Q-3.
**Port from `../Drilling-Intelligence-2.0`:**

| DI 2.0 source | Pattern | WellPulse target |
|---|---|---|
| `backend/app/agent/live_session.py` | `genai` `client.aio.live.connect`, session-resumption handle, sliding-window compression, recap on reconnect, 3-failure fallback to text | `backend/app/live/session.py` |
| `backend/app/api/ws_live.py` | WS endpoint | `WS /ws/live` in `backend/app/api/live.py` (legacy `WS /api/wells/{id}/live` text shim until Gate V, D-20) |
| `frontend/src/live/micCapture.ts`, `audioPlayer.ts`, `liveClient.ts` | 16 kHz PCM up, 24 kHz jitter buffer + barge-in, message protocol | `frontend/src/live/*`, used by `VoiceAgentPanel.tsx` |

**Voice tool subset:** the 12 tools in [`SDD.md`](./SDD.md) §11.3 (incl. TC-025, TC-024, TC-020, TC-019, TC-022, TC-023 speaks summary + pushes PDF link, TC-026, TC-017) — the **same** functions as text chat (D-12). Push-to-talk plus an **open-mic hands-free** option (WS-5). The `FIELD_ENGINEER` persona keeps Live voice. Live model is verified by listing models, never guessed. Hinglish (default) / English / Hindi toggle kept; ≤ 3 sentences unless asked.
**Acceptance:** BDD-F07-S01…S08; first audio ≤ 2.5 s warm; survives a forced reconnect with context; text fallback after 3 failures.
**Verbatim gap (resolved):** WS-5 says *"Multimodal"*; v0.4 is audio-only (camera/image out of scope, SDD §1.2).

### F-08 · Synthetic data expansion — `REPLACE` (FEAT-09)
> T1: *"generate for, let's say two more clusters… Lakwa and Lakhmani… build those wells as well"* · WS-6: *"rate, pressure, temperature, water cut, GOR, artificial lift metrics"*

**What it does:** Port the ADK generator to `backend/app/analytics/generator/` with `FieldConfig`; Geleki reproduces the frozen v0.3.0 baseline plus a 24-month prepend; 60 months for all fields, 2021-10-01…2026-09-30, fixed dates and seed (fixes FEAT-09 `now()` drift). New tables: `field_master`, `cluster_master`, `field_targets`, `operations_events`, `casing_tally`, `tubing_string`, `perforation_intervals`, `pressure_surveys`, `formation_tops` (D-19, append-only); `daily_production` adds `wht_degc`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2` (GOR = `gor_scf_bbl`); extended `workover_history`, `job_catalogue` (+`GLV_REPLACE`). The repository layer `backend/app/data_access/` replaces `wells_data.json` and keeps current REST shapes.
**Verbatim gap:** WellPulse charts show oil, gas, water cut, THP, CHP. WS-6 also asks for **temperature, GOR and lift metrics**, and verbatim Turn 4 shows **gas-lift injection pressure**. These series (`wht_degc`, `gor_scf_bbl`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2`) are added to the data model, `GET /api/wells/{id}/production` and `TelemetryCharts.tsx`, and checked at Gates N and T.
**Acceptance:** BDD-F08-S01…S06; validator 0 violations per field; ≥ 30 events per class; ported ADK contract tests pass on Geleki.

### F-09 · Asset-manager field performance — `NEW`
> T1: *"for a let's say asset manager level: Which particular field is not performing?… That question is not currently being answered"* · WS-1: *"field production vs. targets, uptime, water cut, and active intervention counts"*

**What it does:** TC-024 `compare_fields(asset, as_of, period)`: actual vs. target vs. decline-expected, gap %, uptime %, water cut %, health buckets, deferred barrels by factor class (F-01), rig/rigless candidate counts, `active_interventions`, month-on-month trend; ranked by gap with the top driver named.
**WellPulse build:** `GET /api/fields/compare?period=`; `components/field/FieldComparisonTable.tsx` (gap bars + stacked deferment by factor).
**Acceptance:** BDD-F09-S01…S05; designed answer names Lakwa and its top controllable driver; values come from the tool.

### F-10 · Synthetic PDF corpus — `PARTIAL` (FEAT-11)
> T1: *"generate the documents of PDF files of you know, well interventions and other documents. I would need your help to define it"*

**Definition:** D1 Well Completion Report · D2 Workover Completion Report · D3 Daily Workover Report · D4 Well Schematic · D5 CBL interpretation · D6 Chemical Treatment Log · D7 Well Test Report · D8 Failure Analysis (RCA) · D9 Field Studies · D10 Monthly Field Performance · D11 SOP (F-14). Counts are «target ± tol», pinned after Stage N.
**Integrity rule (fact slots):** every printed number is rendered from a table row; sidecar `facts.json`; validator re-extracts text and checks every fact; ~10% of D1/D5 image-only ("scanned"). Flash writes prose only; Flash never types digits (F-19).
**WellPulse build:** `analytics/generator/docs_pdf/`; `GET /api/docs/{doc_id}.pdf`; TC-026 `search_documents`; `WellReportsTab.tsx` lists real documents for the well and keeps WCR/DWR/BHP/Chemistry tabs mapped to D1/D3/D7/D6.
**Acceptance:** BDD-F10-S01…S04; 100% facts validate; citations are page-anchored.

### F-11 · Field 5-year history: tell, then plot — `NEW`
> T2: *"Can you give me the production history, the past let's say 5 year production data field-wise?… First it will tell, then I'll say: 'Can you give me a plot?'… aggregated of all the wells"*

TC-028 `field_production_history(fields, start, end, freq="M")`: monthly oil/water/gas/liquid, water cut, producing-well count, uptime. The agent summarises first, then pushes a chart on request. **WellPulse build:** `GET /api/fields/history`; `components/field/FieldHistoryChart.tsx`. **Acceptance:** BDD-F11-S01…S03.

### F-12 · Well deep-dive with nearby wells — `PARTIAL` (FEAT-03, FEAT-04)
> T2: *"Can you tell me more about this well and show me the production data… 2-3 year history or 5 year… on that particular log or plot, it should also tell me what are the different interventions happened in the past"*; *"also give information of nearby wells"*

TC-029 `well_profile(well_id)`: depth, zone, lift type, casing/tubing, status, last test, k nearest wells (status, rate, decline residual). TC-017 v2: 2–5 yr plot with markers for all jobs in window. **WellPulse build:** `GET /api/wells/{id}/profile`; `GET /api/wells/{id}/production` (job markers + WHT / GOR / gas-lift series) drawn as Recharts `ReferenceLine`s in `TelemetryCharts.tsx`; `components/well/WellDeepDive.tsx`, `components/well/NearbyWellsTable.tsx`; nearby wells highlighted on `WellMap.tsx`. **Acceptance:** BDD-F12-S01…S05.

### F-13 · Counterfactual defence — `NEW`
> T2: *"Why are you recommending this against an alternative? Let's say perforation, I can say 'Okay why not just wax removal?' and something that is super deep"*

TC-027 `compare_interventions(well_id, recommended_job, alternative_job)` → evidence table: (1) diagnostic fit (TC-002 Chan, TC-005 signature, TC-003 fillage, TC-004 offsets, `pressure_surveys`); (2) this well's history with each job; (3) field efficacy p(success), n; (4) execution: rig/rigless, rig-days, cost band, MRO, earliest start; (5) value: deferred bbl avoided per rig-day; (6) verdict + deciding row. The agent narrates the table and adds nothing outside it (X-1). Demo: GK-129 *"why squeeze, not wax removal"* (D-7). **WellPulse build:** `GET /api/wells/{id}/compare?recommended=&alternative=`; `components/well/CounterfactualTable.tsx`. **Acceptance:** BDD-F13-S01…S05.

### F-14 · SOP library — `NEW`
> T2: *"we need to generate a lot of documents, I see. The SOPs"* · verbatim Turn 5 (illustrative): *"Outlines step-by-step SOP, required slickline unit"*

D11 SOP per intervention-class family (≈11): purpose, prerequisites, equipment, steps, hold points, HSE, handover. TC-022 actions carry `sop_doc_id`; the agent cites "SOP-xx steps n–m" with the page. **Acceptance:** BDD-F14-S01…S02.

### F-15 · Medallion Lakehouse — `NEW`
> T2: *"showcase that in the Medallion architecture… Lakehouse… whether it should go ultimately into BigQuery or if there is a better database"*

Bronze (bucket `gs://workover-operations-agentic-ai-datalake`, prefixes `bronze/`, `documents/`, `silver_exports/`; external tables: generator drops, PDFs, SOPs), Silver (BigQuery, `daily_production` partitioned by date, clustered by `field, well_id`; parsed document chunks), Gold (Dataform: 5-yr field KPIs, health view, feature store, NBA lookup). Location `asia-south1` in project `workover-operations-agentic-ai` (D-9, D-4). Decision record: BigQuery, compared with Bigtable / AlloyDB / Cloud SQL in [`SDD.md`](./SDD.md). Runtime switch `DATA_BACKEND=parquet|bigquery` with a parity test. Verbatim §5 also mentions Vertex AI Search for chunks and a Gemini grounding cache; v0.4 uses a TF-IDF index (`data/index/`) with a Silver `doc_chunks` mirror (D-17); Vertex AI Search is optional later. **Acceptance:** BDD-F15-S01…S03.

### F-16 · Role-based access (optional) — `NEW`
> T2: *"if an Executive Director is asking for a particular data versus a field engineer is asking for a data, what that data can be?… If it is overcomplicating, we can leave it"*

Three personas `ED`, `ASSET_MANAGER`, `FIELD_ENGINEER` (D-8); Production Engineer maps to `ASSET_MANAGER`. Gating in the tool layer via `require()`, not the prompt. Field engineer: single-well mechanical view, SOPs, dossier; no field financial roll-ups. ED: field aggregates; no raw tallies by default. Demo: same question, two correctly scoped answers. Built last (Stage Y); cut if it slips. Field engineer keeps Live voice. **WellPulse build:** `components/common/PersonaPicker.tsx` in `Header.tsx`; header `X-Persona` sent with every `/api/*` call. **Acceptance:** BDD-F16-S01…S03.

### F-17 · Multi-screen interface — `PARTIAL` (FEAT-01)
> T2: *"there will be different screens opened, like what we currently have the interface. Then on the interface they can see different fields, right, clearly, and the wells"*

Keep the split pane; add views: multi-field map (boundaries, clusters, health colours, field filter), field view (F-09/F-11), well view (F-12), voice (F-07). APIs `GET /api/fields`, `GET /api/wells?field=&status=` wrap TC-020/025/029 so screen numbers match the agent. **Acceptance:** BDD-F17-S01…S03.

### F-18 · 5-level demo flow — acceptance
> T2: *"do you see the hierarchy of question and answering? So it should be able to generate some documents, give some aggregated data if needed, also drill down to a particular well, also give information of nearby wells"*

| Level | Question (T2) | Tools | WellPulse surface |
|---|---|---|---|
| L1 | *"past let's say 5 year production data field-wise"* → *"give me a plot"* | TC-028 | Chat + `FieldHistoryChart` |
| L2 | *"how many wells in Geleki are… sick or they have lost production?"* | TC-020 (+ TC-019 field) | Chat + KPIs + map |
| L3 | *"priority list of all the wells that needs intervention"* | TC-022 batch (TC-010 v2), `GET /api/fields/{field}/priority`; rank = deferred bbl × p(success) ÷ rig-days + cost band | Chat table + priority list |
| L4 | *"tell me more about this well… production history"* + past interventions + nearby wells | TC-029 + TC-017 v2 | Well view |
| L5 | *"next best recommended interventions?"* → *"why not just wax removal?"* | TC-022 → TC-027 (+ TC-026 SOP) | Recommendations + evidence table |

Runs through `POST /api/chat` (ADK `Runner`, persona- and field-aware, D-12) and by voice. **Acceptance:** BDD-F18-S01…S03; Playwright run of L1–L5; `agents-cli eval` dataset.

### F-19 · Delegation — process
> T2: *"a delegation of what are the tasks that Opus would do and what are the tasks that can be outsourced to the Flash models. For example, the document generation can be given to the Flash models."*

Orchestrator (Opus/Pro-class): contracts, numeric logic, guardrails, ML gates, counterfactual, RBAC policy, reviews, commits, deploys. Gemini Flash workers: document templates and prose (fact slots only; never digits), DDL/loaders/Dataform, Recharts components, React screen scaffolds, Gherkin/step glue, eval JSON, README/checklist ticks — always behind a deterministic gate.

---

## 4. Cross-cutting rules (apply to every feature)

**Rule X-1 overrides everything: if a number did not come from a tool return, it is not shown or spoken.**

| ID | Rule | Origin |
|---|---|---|
| X-1 | **Never fabricate a number.** Tools return `UNAVAILABLE` / `LOW_CONFIDENCE` rather than guess; the LLM and the keyword fallback never emit digits of their own | *Derived:* ADK prompt guardrail; WellPulse defect (FEAT-08) |
| X-2 | **Numbers only from tool returns.** Every on-screen or spoken number traces to a tool call, a table row or a cited document | *Derived:* ADK definition of done |
| X-3 | **No ₹ or USD point estimates.** Cost = band `LOW`/`MED`/`HIGH` + rig-days. No NPV, payback or ROI. `cost_usd` / `estimated_cost_usd` become bands | D-1 (resolves C-3, C-7) |
| X-4 | Synthetic data is acknowledged as synthetic and representative for all 3 fields, including coordinates | T2: *"everything needs to be generated"*; D-3 |
| X-5 | Existing REST shapes keep working until the React UI is migrated (golden snapshots, Stage M) | *Derived:* D-11 non-regression |
| X-6 | **Voice keeps integrity in every language.** Hinglish (default), English and Hindi answers obey X-1…X-3; numbers are spoken as returned | FEAT-12 + T1 Live anchor |
| X-7 | **Git: commit and push to `origin main` after every major milestone (each passed stage gate)**, with message `v0.4(<stage>): <name> — Gate <stage> passed`. Run tests before every commit; never commit with a red gate, never commit `.env` or secrets. Python via `uv` only | User rule (2026-10-07); D-14 |
| X-8 | Cloud resources: authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources. Covers BigQuery DDL apply and Cloud Run deploy of `wellpulse-app` in `workover-operations-agentic-ai` (smoke test after); see [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md) | User rule; D-4 |

---

## 5. Conflicts and resolutions

**The verbatim §4–§8 example numbers are not data; every conflict resolves to "tool returns at run time" or a decision.** C-1…C-8 come from the prior feature.md §5.1; C-9…C-11 are WellPulse-specific.

| # | Verbatim / baseline says | Reality | Resolution |
|---|---|---|---|
| C-1 | Turn 2: Geleki *"e.g., 42 wells… 26 healthy, 11 sick, 5 shut-in"* | Geleki has 142 wells in the adopted data | Counts come from TC-020 at run time (illustrative) |
| C-2 | Turns 3–5 hero **GK-104** "gas lift valve failure & wax" | GK-104 is an SRP, healthy well; GLV impossible on SRP | **D-7:** hero GK-129 ("why squeeze, not wax removal"); LKM-061 GLV backup |
| C-3 | Turn 3 table: **₹ Lakhs, NPV, payback** | Integrity rule forbids point costs | **D-1:** cost band + rig-days |
| C-4 | §7: Lakwa **25**, Lakhmani **20** wells | Plan scale 160 / 110 | **D-2:** 160 / 110 |
| C-5 | §7: 15 DWRs, 5 schematics, 5 SOPs | Templated, fact-validated corpus at scale | Both: templated corpus + Flash-authored SOP/narrative set (F-10, F-14, F-19) |
| C-6 | §7/§8: "5 years daily production" | ADK data: 36 months from 2023-10-01 | **D-2:** 60 months for all fields; Geleki 24-month prepend |
| C-7 | Turn 5: "142 bar", "36 hrs", "₹18L", "4.2x return" | Invented figures | From TC-022 / TC-027 returns or dropped |
| C-8 | §8 Gates 1–7 | Stages M–W | Mapped in [`checklist.md`](./checklist.md) |
| **C-9** | WellPulse: **50 `GLK-` wells**, 730 days, JSON | ADK: **142 `GK-` wells**, parquet, validators, CoxPH | **D-11:** adopt ADK foundation behind `backend/app/data_access/`; REST shapes kept |
| **C-10** | WellPulse "Gemini Live" (`WS /api/wells/{id}/live`) | Text-chat wrapper + browser TTS | **F-07:** real google-genai Live proxy ported from DI 2.0 |
| **C-11** | Verbatim header: *Target Application `workover_well_intervention`*; WS-3 lists *"ESP Replacement"*; Turn 3 ranks by *NPV* | WellPulse is the product (D-10); Assam fixtures are SRP / gas lift; NPV conflicts with D-1 | WellPulse hosts the build; ESP replacement maps to IC-08; ranking = deferred bbl × p(success) ÷ rig-days with cost band |

---

## 6. Out of scope for v0.4

- Live SCADA or real ONGC data (synthetic only)
- Absolute cost, NPV, payback or ROI in ₹ or USD (X-3)
- Assets beyond the Assam Asset
- Camera / image input to Live (WS-5 "multimodal" → audio-only, resolved)
- Mobile / offline-first field app (the dossier PDF is the field artefact)
- Gemini Enterprise republish (D-6: not applicable to WellPulse; future)
- Vertex AI Search vector store and grounding cache (verbatim §5; optional later, D-17)
- Non-English dossier (Q-2: English-only)

---

## 7. Decisions referenced

**All decisions D-1…D-20, Q-1 and Q-2 are resolved (user / orchestrator, 2026-10-07); no decision is open.**

| ID | Decision | State |
|---|---|---|
| D-1 | Cost band + rig-days; no ₹/USD point estimates | Accepted |
| D-2 | Lakwa 160 wells / 3 GGS; Lakhmani 110 / 2 GGS; 60 months (2021-10-01…2026-09-30) | Accepted |
| D-3 | Synthetic coordinates near Sivasagar, labelled synthetic | Accepted |
| D-4 | GCP project `workover-operations-agentic-ai` (Cloud Run `us-central1`; BigQuery `asia-south1`) | Resolved (user, 19:44) |
| D-5 | Keep Esri basemap for all fields | Accepted |
| D-6 | Gemini Enterprise republish not applicable; future | Accepted |
| D-7 | Hero GK-129; backup LKM-061 | Accepted |
| D-8 | Minimal RBAC (ED, ASSET_MANAGER, FIELD_ENGINEER) at tool layer, built last | Accepted |
| D-9 | BigQuery Medallion Lakehouse, `asia-south1`, in the D-4 project | Accepted |
| D-10 | WellPulse is the product; port ADK generator + tools into `backend/app/analytics/`; tool calling replaces prompt-stuffing | Accepted (recommended) |
| D-11 | Adopt ADK data foundation (GK 142 + LKW + LKM) behind `backend/app/data_access/`; keep REST shapes | Accepted (recommended) |
| D-12 | ADK `Runner` in-process in FastAPI; google-genai Live with same tools; Vertex AI + ADC | Accepted (recommended) |
| D-13 | Keep text model `gemini-3.8-flash`; calls move to Vertex AI with ADC (no API key) | Resolved (user, 19:44) |
| D-14 | `uv` + `pyproject.toml`; multi-stage Dockerfile | Accepted |
| D-15 | AS_OF = 2026-09-23; data runs to 2026-09-30 | Resolved |
| D-16 | Demo: in-memory sessions, Cloud Run max-instances=1 + session affinity; Vertex AI sessions in production later | Resolved |
| D-17 | TF-IDF document search in v0.4; Vertex AI Search optional later | Resolved |
| D-18 | Commit parquet + model artefacts if every file < 50 MB, else git-ignore and regenerate in the Docker build; PDFs + index built in a Docker stage, uploaded to GCS in Stage X | Resolved |
| D-19 | Add `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2`, `wht_degc`, `pressure_surveys`, `formation_tops` (append-only) | Resolved |
| D-20 | Legacy WS `/api/wells/{id}/live` and `/audio` shims kept until Gate V; removed at Stage V | Resolved |
| Q-1 | Meeting date unknown: build all stages; if time-boxed, cut Y first, then X | Resolved |
| Q-2 | English-only dossier | Resolved |
| Bucket | Existing `gs://workover-operations-agentic-ai-datalake` (`bronze/`, `documents/`, `silver_exports/`) | Resolved |
| Ranking | Deferred bbl × p(success) ÷ rig-days, shown with cost band (K-7) | Resolved |
| frontend/dist | Untracked in Stage W | Resolved |
| Autonomy | Overnight autonomous build incl. BigQuery DDL apply (dry-run first), Cloud Run deploy of `wellpulse-app` (smoke after), commit + push after each passed gate | Authorised by user (2026-10-07 19:52) |
| Git | Stray GitHub branch `v0.4-build` (ADK code pushed by mistake) | Done: deleted by user |
