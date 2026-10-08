# Behavior-Driven Development (BDD) Specifications
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 4.0.0 (v0.5 answer canvas & multimodal expansion) · **Date:** 2026-10-08
**Test frameworks:** pytest-bdd (REST + WS) · Playwright (React UI) · FakeLiveSession (WS without Vertex)
**Primary source:** [`verbatim.md`](../verbatim.md) · **v0.5 Canonical Brief:** [`v05_change_brief.md`](./v05_change_brief.md) · **Features:** [`features.md`](./features.md) · **Design:** [`SDD.md`](./SDD.md) · **Build:** [`build.md`](./build.md) · **Checklist:** [`checklist.md`](./checklist.md) · **Delegation:** [`DELEGATION.md`](./DELEGATION.md)

**Bottom line:** WellPulse behaviour is specified by 8 corrected baseline features (B-01…B-08), 19 v0.4 verbatim features (F-01…F-19), cross-cutting guardrails (X), and 7 v0.5 features (F-20…F-26). Every scenario has an ID `@BDD-<feature>-Sxx`, an anchor to verbatim or change brief, a Stage (M…W2), and runs as pytest-bdd, Playwright, or a fake-Live WS test.

> [!IMPORTANT]
> Numbers written **«target ± tol»** are design targets the synthetic generator must hit; they are **pinned to exact values at Gate N** and then asserted exactly. Plain numbers are already true (e.g. Geleki 142 wells from the ADK v0.3.0 baseline) or are fixed contract thresholds. Numbers in verbatim §4–§8 (e.g. "42 wells", "₹18 Lakhs", "+180 bopd", "25 / 20 wells") are **illustrative** and are never asserted.

> [!WARNING]
> v1.0.0 of this file asserted hard-coded values (32/12/6 health split, 50 `GLK-` wells, USD cost, payback, browser-TTS "Live"). All are removed: health counts now come from TC-020, cost is a band (D-1), and Live is real (Stage U).

---

## 0. Personas, surfaces and conventions

| Persona | Who | What they ask | RBAC role (D-8) |
|---|---|---|---|
| **ED** | Ajay Ratan, Executive Director, ONGC IDWE | "Why did it decline? What should we do? Can I trust the model?" | `ED` |
| **AM** | Assam Asset Manager | "Which field is not performing, and why?" | `ASSET_MANAGER` |
| **PE** | Field production engineer | "Which wells are at risk? What's the next best action?" | `ASSET_MANAGER` (derived: §6 groups asset/production manager) |
| **FE** | Field / workover engineer on a well pad | "Give me the full history of this well before I go." | `FIELD_ENGINEER` |

| Surface | Used by steps like | Stage |
|---|---|---|
| Map (`WellMap.tsx`), field selector, KPI ribbon | "When I select field "Lakwa" in the field selector" | T, Y |
| Well drawer (`WellDetails`, `TelemetryCharts`, `WorkoverTimeline`) / Answer Canvas (`WellDeepDiveDrawer.tsx`) | "Then the well drawer shows …" / "Then the answer canvas opens …" | T, AC |
| `VoiceAgentPanel.tsx` (Hinglish / English / Hindi) | "When I say "…"" | U, AC |
| `WellReportsTab.tsx` | "Then WellReportsTab opens that PDF at the cited page" | O |
| REST `/api/...` | "When I GET /api/wells/kpis?field=Geleki" | per feature |
| WS `/ws/live` (field/well context sent as a `context` message; legacy `WS /api/wells/{id}/live` is a deprecated text shim until Stage V, D-20) | "Then a tool_call event for "…" is emitted" | U |

**v0.4 & v0.5 routes used below** are the final route table in [`SDD.md`](./SDD.md) §13 and [`v05_change_brief.md`](./v05_change_brief.md) §9: kept `GET /api/health`, `/api/wells/kpis?field=`, `/api/wells?field=&status=&search=`, `/api/wells/{id}`, `/api/wells/{id}/reports`, `/api/wells/{id}/reports/{type}`, `/api/wells/{id}/history?range=30d|6m|1y|2y|3y|5y`, `/api/wells/{id}/workovers`, `/api/field/infrastructure?field=`, `/api/wells/{id}/export` (JSON; `?format=pdf` → dossier PDF); `POST /api/wells/{id}/chat`, `/api/wells/{id}/audio`, `/api/wells/{id}/recommendations`; new `GET /api/healthz`, `/api/me/capabilities`, `/api/fields`, `/api/fields/history?fields=`, `/api/fields/{field}/history`, `/api/fields/compare?period=`, `/api/fields/{field}/health?cluster_id=`, `/api/fields/{field}/attribution?window_days=`, `/api/fields/{field}/priority`, `/api/wells/{id}/profile`, `/api/wells/{id}/production`, `/api/wells/{id}/attribution?window_days=`, `/api/wells/{id}/classification`, `/api/wells/{id}/nba`, `/api/wells/{id}/compare?recommended=&alternative=`, `/api/wells/{id}/documents`, `/api/docs/search`, `/api/docs/{doc_id}.pdf`; `POST /api/wells/{id}/dossier`, `POST /api/chat`; `WS /ws/live`; new in v0.5: `GET /api/wells/{id}/recommendations?k=3`, `GET /api/wells/{id}/similar?class=`, `GET /api/wells/{id}/report`, `GET /api/wells/{id}/tubing-tally`, `GET /api/wells/{id}/deviation`, `GET /api/wells/{id}/integrity`. Header `X-Persona`; analytics responses use the envelope `{status, data, message, missing_fields, provenance}`.

**Tags:** `@api` pytest-bdd over HTTP · `@ws` pytest-bdd over WebSocket with FakeLiveSession · `@ui` Playwright · `@voice` spoken prompt (WS audio or transcript injection) · `@data` generator/validator tests · `@gate` stage gate · `@demo` used in the ED demo · `@L1`…`@L5` five-level flow · `@regression` must stay green once its stage gate has passed.

## 1. Shared background

```gherkin
Background:
  Given WellPulse runs locally or on Cloud Run service "wellpulse-app" (project workover-operations-agentic-ai)
  And the data was generated by the Stage N generator with seed 42
  And asset "ASSAM_ASSET" contains fields "Geleki", "Lakwa", "Lakhmani"
  And data covers 2021-10-01 to 2026-09-30 and as_of is "2026-09-23"  # D-15
  And all data and coordinates are synthetic and representative
```

---

## Part A · Baseline WellPulse features, corrected (B-01 … B-08)

*Anchor for Part A: T2 — "there will be different screens opened, like what we currently have the interface"; T1 — "which of the wells are … not producing now. So again, this is I think already built." These keep today's UI working on the new data (D-11).*

## B-01 · Geospatial well triage map
*Baseline: FEAT-01, FEAT-02, FEAT-14 · Status: PARTIAL · Corrected at Stage P/Y*

```gherkin
Feature: Geospatial Well Health Prioritization and Triage
  As a Production Engineer
  I want to view all operational wells on an interactive map categorized by health status
  So that I can immediately triage critical assets requiring urgent intervention

  @BDD-B01-S01 @ui @regression
  Scenario Outline: Initial fleet overview and KPI summary ribbon across fields
    Given the WellPulse dashboard is open
    When I select field "<field>" in the field selector
    Then the map displays <total> wellhead markers
    And each marker displays an authentic oil derrick glyph with a permanent tag badge
    And markers with status NOT_PRODUCING display an active visual pulse animation
    And the fleet KPI summary ribbon displays counts for PRODUCING_OK, AT_RISK, UNDERPERFORMING, and NOT_PRODUCING matching TC-020 classify_well_health via GET /api/wells/kpis?field=<field>
    And the sum of bucket counts equals <total>

    Examples:
      | field    | total   |
      | Geleki   | 142     |
      | Lakwa    | 160     |
      | Lakhmani | 110     |

  @BDD-B01-S02 @ui @regression
  Scenario Outline: Filter wellheads by operational health status
    Given the WellPulse dashboard is open for field "Geleki"
    When I click the status filter chip "<status_filter>"
    Then the map renders only markers with status "<status_filter>"
    And the visible well count equals the TC-020 count for "<status_filter>"

    Examples:
      | status_filter   |
      | PRODUCING_OK    |
      | AT_RISK         |
      | UNDERPERFORMING |
      | NOT_PRODUCING   |

  @BDD-B01-S03 @ui
  Scenario: Toggle between Satellite Imagery and Dark SCADA layers
    Given the WellPulse dashboard is open
    When I click "Dark SCADA" on the map layer control
    Then the map tile layer switches from Esri World Imagery to Esri Dark Gray Canvas
    And all tagged wellhead markers and pulsing indicators remain visible

  @BDD-B01-S04 @ui
  Scenario: Search and pan to well by name
    Given the WellPulse dashboard is open
    When I enter "GK-129" into the search bar
    Then the map highlights and pans to marker "GK-129"
    And non-matching wellhead markers are dimmed or hidden
```

## B-02 · Well telemetry drill-down
*Baseline: FEAT-03 · Status: PARTIAL · Corrected at Stage N*

```gherkin
Feature: Well Selection and Telemetry Drill-Down
  As a Reservoir Engineer
  I want to select a specific well from the map or list
  So that I can inspect its complete 60-month production history and pressure dynamics

  @BDD-B02-S01 @ui @regression
  Scenario: Select well GK-129 and inspect telemetry metrics and 60-month history
    Given the WellPulse dashboard is open for field "Geleki"
    When I click the GK-129 marker on the map
    Then the well drawer shows telemetry for "GK-129"
    And the wellhead KPI cards display:
      | Metric                 | Unit       |
      | Current Oil Production | bopd       |
      | Current Gas Production | mscf/d     |
      | Water Cut              | %          |
      | Tubing Pressure        | THP in ksc |
      | Casing Pressure        | CHP in ksc |
      | Artificial Lift Type   | text       |
    And the production timeseries chart renders 1819 historical daily points covering 2021-10-01 to as_of 2026-09-23
    And the user can toggle the time range between "1 Month", "6 Months", "1 Year", and "5 Years"

  @BDD-B02-S02 @ui @api @regression
  Scenario: Verify water-cut channelling signature against diagnostic and telemetry history
    Given marker "GK-129" is selected in the well drawer
    When I inspect the historical production and water-cut chart
    Then the water-cut chart for GK-129 shows the channelling signature returned by TC-003 Chan diagnostic
    And the plotted values equal GET /api/wells/GK-129/history?range=5y
```

## B-03 · Workover history timeline
*Baseline: FEAT-04 · Status: PARTIAL · Corrected at Stage N*

```gherkin
Feature: Workover and Intervention History Timeline
  As a Workover Specialist
  I want to review past operations performed on the selected well
  So that I can assess intervention frequency, cost band, and effectiveness

  @BDD-B03-S01 @ui @api @regression
  Scenario: View historical workovers chronologically for GK-129
    Given well "GK-129" is selected
    When I open the "Workover History" tab in the well drawer
    Then a chronological list of workover events is rendered from GET /api/wells/GK-129/workovers
    And each event card displays:
      | Field          | Description                       |
      | Date           | ISO Date of intervention          |
      | Operation Type | Intervention type description     |
      | Cost Band      | Cost band (LOW/MED/HIGH)          |
      | Rig Days       | Number of rig days                |
      | Equipment      | Rig / rigless unit (no vendor name) |
      | Scope Summary  | Narrative of work performed       |
      | Delta Flow     | uplift_bopd from workover_history |
    And no USD, ₹ or INR amount is displayed
```

## B-04 · Voice-enabled contextual agent
*Baseline: FEAT-05, FEAT-06, FEAT-07, FEAT-12 · Status: REPLACE · Corrected at Stage U/V*

```gherkin
Feature: Voice-Enabled Contextual AI Agent
  As a Field Operations Engineer
  I want to verbally interact with an AI agent that possesses the active well's full context
  So that I can diagnose issues and evaluate history hands-free

  @BDD-B04-S01 @ui @ws
  Scenario: Voice query about historical interventions and cost
    Given well "GK-129" is selected
    And VoiceAgentPanel connects to websocket "/ws/live" with context well_id "GK-129" proxying Gemini Live
    When I stream microphone audio at 16 kHz PCM asking "What was the last workover done on this well and how much did it cost?"
    Then the websocket server sends an "input_transcript" event
    And the server invokes the workover_history tool via a "tool_call" event
    And the server streams 24 kHz PCM audio and "caption_delta" events
    And the response answers cost as cost band and rig_days with numbers from the tool return
    And the response includes the post-workover uplift_bopd from the tool return
    And no USD, ₹ or INR amount is displayed or spoken

  @BDD-B04-S02 @ui @ws
  Scenario: Hinglish voice query for workover history and outcome
    Given well "GK-129" is selected
    And the language toggle in VoiceAgentPanel is set to "Hinglish"
    And VoiceAgentPanel connects to websocket "/ws/live" with context well_id "GK-129" proxying Gemini Live
    When I stream microphone audio at 16 kHz PCM speaking "GK-129 pe last workover kab hua tha aur kya result tha?"
    Then the websocket server sends an "input_transcript" event
    And the server invokes the workover_history tool via a "tool_call" event
    And the server streams 24 kHz PCM audio and "caption_delta" events in Hinglish
    And the answer cites the intervention date, operation type, and uplift_bopd from the tool return

  @BDD-B04-S03 @ui @ws
  Scenario: Diagnostic inquiry regarding production decline
    Given well "GK-129" is selected with status "UNDERPERFORMING"
    And VoiceAgentPanel connects to websocket "/ws/live" with context well_id "GK-129" proxying Gemini Live
    When I stream microphone audio at 16 kHz PCM asking "Why has production declined over the last 90 days?"
    Then the agent invokes TC-003 Chan diagnostic and TC-019 attribute_decline tools via "tool_call" events
    And the server streams 24 kHz PCM audio and "caption_delta" events citing the tool returns
    And the response attributes the decline to water channelling without asserting scale deposition
```

## B-05 · Prescriptive recommendation card
*Baseline: FEAT-08 · Status: REPLACE · Corrected at Stage R*

```gherkin
Feature: Prescriptive Workover Recommendations
  As an Operations Manager
  I want the AI agent to provide actionable engineering recommendations
  So that I can expedite workover scheduling with operational cost bands and production uplift estimates

  @BDD-B05-S01 @ui @api @regression
  Scenario: Generate prescriptive recommendation card for well GK-129
    Given well "GK-129" is selected in the well drawer
    When I click "Generate Recommendation" or POST to "/api/wells/GK-129/recommendations"
    Then the response status is 200
    And the Recommendation Card renders:
      | Attribute           | Expectation                                        |
      | Recommended Action  | Specific engineering job from TC-022               |
      | Urgency Level       | Immediate, High, or Routine                        |
      | Cost Band           | cost_band from TC-022                              |
      | Rig Days            | rig_days from TC-022                               |
      | Expected Uplift     | uplift_bopd from TC-022 recommend_next_best_action |
      | Safety & Risk Notes | Containment and environmental protocols            |
    And no payback period, USD or ₹ figure appears
    And every number in the card appears in the TC-022 recommend_next_best_action return
```

## B-06 · Offline / degraded resilience
*Baseline: FEAT-13 · Status: PARTIAL · Corrected at Stage U/V*

```gherkin
Feature: Offline and Local Fallback Resilience
  As an Engineer running WellPulse
  I want the platform to operate deterministically even when cloud AI services are degraded or unreachable
  So that operations and monitoring remain uninterrupted

  @BDD-B06-S01 @api @regression
  Scenario: Degraded chat response when Vertex AI is unreachable
    Given Vertex AI is unreachable or Application Default Credentials are missing
    When I POST to "/api/wells/GK-129/chat" with prompt "What is the status of GK-129?"
    Then the response status is 200
    And the response payload has status "degraded"
    And the answer is generated using deterministic tool returns only
    And the response states it is operating in degraded mode

  @BDD-B06-S02 @ui @ws  # shares step definitions with BDD-F07-S04
  Scenario: Fallback from Gemini Live to text chat after repeated connection failures
    Given well "GK-129" is selected in the well drawer
    And the Gemini Live websocket connection fails 3 consecutive times
    When VoiceAgentPanel receives websocket status "fallback"
    Then VoiceAgentPanel switches from voice mode to text chat
    And the UI displays a notification indicating degraded connectivity
```

## B-07 · Engineering reports tab
*Baseline: FEAT-11 · Status: PARTIAL · Corrected at Stage O*

```gherkin
Feature: Engineering Reports Tab
  As a Production Engineer
  I want to access category-specific engineering reports and verified document sidecars
  So that I can review historical well tests, completion reports, and chemistry analyses

  @BDD-B07-S01 @ui @api @regression
  Scenario: Display engineering report sub-tabs and PDF links for GK-129
    Given well "GK-129" is selected
    When I open the "Engineering Reports" tab in the well drawer
    Then the WellReportsTab for GK-129 shows tabs:
      | Tab Name        |
      | WCR             |
      | DWR             |
      | BHP/Sonolog     |
      | Water chemistry |
    And after Stage O each tab links to a real PDF served by GET /api/docs/{doc_id}.pdf
    And each report link displays the document title, date, and page

  @BDD-B07-S02 @ui @api @regression
  Scenario: Verify report value matches facts sidecar
    Given well "GK-129" is selected and the "Engineering Reports" tab is open
    When I inspect an engineering report value displayed in the tab
    Then the report value shown in the tab equals the matching fact in the document's facts.json sidecar
```

## B-08 · Well export
*Baseline: FEAT-15 · Status: PARTIAL · Corrected at Stage S*

```gherkin
Feature: Well Export
  As an Operations Engineer
  I want to export comprehensive well dossiers in structured formats
  So that I can share well summaries with field and reservoir teams

  @BDD-B08-S01 @api @regression
  Scenario: Export well summary as JSON, then PDF
    Given well "GK-129" exists with complete history
    When I GET "/api/wells/GK-129/export"
    Then the response status is 200
    And the export JSON contains sections:
      | Section    |
      | Identity   |
      | Workovers  |
      | Reports    |
    And no USD amounts appear in the export
    And after Stage S the JSON adds pdf_url and GET "/api/wells/GK-129/export?format=pdf" returns the F-06 dossier PDF
```

---

## Part B · v0.4 verbatim features (F-01 … F-19)

> [!NOTE]
> Adapted from `../workover_well_intervention/BDD.md` (same IDs) but re-targeted to WellPulse surfaces: React UI (map, field selector, well drawer, VoiceAgentPanel, reports tab) and FastAPI REST/WS. Every feature carries its verbatim anchor; steps with no anchor are tagged *derived* with the reason.

### F-01 · Decline root-cause factor attribution

*Anchor: T1 — "why did the production decline? Was it human factor, controllable factor, what kind of factors". WS2 factor list. Tool TC-019 · Stage P.*

```gherkin
Feature: Decline root-cause factor attribution
  As the ED
  I want a well's lost oil split into human, controllable and uncontrollable factors
  So that I can tell which losses my organisation could have prevented

  @BDD-F01-S01 @api @demo
  Scenario: Human-process delay dominates a well's decline
    When I GET /api/wells/LKW-047/attribution?window_days=180
    Then the response status is 200
    And the waterfall components sum to total lost oil within 0.5%
    And the largest factor class is "HUMAN_PROCESS"
    And HUMAN_PROCESS includes "WAIT_ON_RIG" of 41 days and "WAIT_ON_MATERIAL" of 12 days
    And "EQUIPMENT" contains sub-factor "PUMP_WEAR"

  @BDD-F01-S02 @ws @voice @demo
  Scenario: Same question by voice in English
    Given VoiceAgentPanel is connected with language "English"
    When I say "Why did LKW-047's production decline over the last 6 months?"
    Then a tool_call event for "attribute_decline" with well_id "LKW-047" and window_days 180 is emitted
    And the spoken answer calls the loss "controllable" and never names an individual
    And every number in the caption appears in that tool return

  @BDD-F01-S03 @api
  Scenario: Pure reservoir decline is uncontrollable
    When I GET /api/wells/LKM-090/attribution?window_days=180
    Then "SUBSURFACE" accounts for ≥ 80% of lost oil  # pinned at Gate P: measured 100.0% (TC-019, AS_OF 2026-09-23; pinned_values.md §8)
    And the controllable share is ≤ 15%  # pinned at Gate P: measured 0.0%
    And the response flags "NO_OPERATIONAL_ACTION_WOULD_HAVE_PREVENTED"

  @BDD-F01-S04 @api
  Scenario: Grid power outages are external, not operational
    When I GET /api/wells/LKW-088/attribution?window_days=180
    Then sub-factor "GRID_POWER_OUTAGE" is classed "EXTERNAL"
    And it is excluded from the controllable share

  @BDD-F01-S05 @api
  Scenario: Unexplained residual is surfaced
    Given a well whose explained components cover less than 85% of lost oil
    When its attribution is requested
    Then status is "LOW_CONFIDENCE"
    And the "UNEXPLAINED" component is returned with barrels and percentage

  @BDD-F01-S06 @api @ui
  Scenario: Field-level attribution rolls up from wells
    When I GET /api/fields/Lakwa/attribution?window_days=90
    Then the field total equals the sum of its wells' totals within 0.5%
    And the controllable share (EQUIPMENT + OPERATIONAL + HUMAN_PROCESS) is ≥ 40%  # pinned at Gate P: measured 68.8% (TC-019)
    When I open the well drawer for LKW-047 and the "Decline causes" tab
    Then the waterfall bars equal the API components
```

### F-02 · Well-health screening (replaces hard-coded status)

*Anchor: T1 — "which of the wells are doing okay, which … not doing okay, which … not producing now. So again, this is I think already built." Built = baseline FEAT-02 (REPLACE: status hard-coded 32/12/6). WS2 three categories → four buckets (derived: UNDERPERFORMING separates sustained gap from early risk). Tool TC-020 · Stage P.*

```gherkin
Feature: Well-health screening across fields
  As a PE
  I want to know which wells are okay, at risk, underperforming or not producing
  So that I can focus my attention

  @BDD-F02-S01 @api @demo
  Scenario Outline: Four-bucket health per field
    When I GET /api/wells/kpis?field=<field>
    Then every <field> well appears in exactly one of PRODUCING_OK, AT_RISK, UNDERPERFORMING, NOT_PRODUCING
    And bucket counts sum to <total>
    And every NOT_PRODUCING well has a reason_code and a recoverable flag
    Examples:
      | field    | total |
      | Geleki   | 142   |
      | Lakwa    | 160   |
      | Lakhmani | 110   |

  @BDD-F02-S02 @api @regression
  Scenario: Geleki regression against ADK v0.3.0 trigger states
    When health is classified for "Geleki"
    Then GK-129, GK-141, GK-055, GK-087, GK-103, GK-112, GK-147 keep their v0.3.0 trigger states
    And each bucket follows the TC-020 rules in SDD.md

  @BDD-F02-S03 @api
  Scenario: Cluster rollup
    When I GET /api/fields/Lakwa/health?cluster_id=LKW-GGS-II
    Then only wells with cluster_id "LKW-GGS-II" are counted

  @BDD-F02-S04 @ws @voice @demo
  Scenario: Hinglish health question
    Given VoiceAgentPanel language is "Hinglish"
    When I say "Lakhmani mein kitne wells theek chal rahe hain aur kitne band hain?"
    Then a tool_call for "classify_well_health" with field "Lakhmani" is emitted
    And the spoken counts equal the tool's bucket counts

  @BDD-F02-S05 @ui
  Scenario: UI status never disagrees with TC-020
    When I select field "Geleki" in the field selector
    Then each map pin colour equals the TC-020 bucket of that well
    And no well status is read from a stored "status" field  # derived: defect fix for hard-coded status
```

### F-03 · ML intervention classifier

*Anchor: T1 — "running machine learning algorithms on the production data … classification algorithm … 5 to 10 type of interventions … or let's say 15". WS3 archetypes. Tool TC-021 · Stage Q.*

```gherkin
Feature: ML intervention classifier
  As the ED
  I want a trained model to say which of 15 intervention types a well needs, and why
  So that diagnosis is consistent and explainable

  @BDD-F03-S01 @api @demo
  Scenario: Sand cleanout identified with explanation
    When I GET /api/wells/LKM-023/classification
    Then top-1 class is "IC-06 SAND_CLEANOUT"
    And 3 classes are returned with probabilities summing to at most 1.0
    And at least 3 top features are listed with direction ↑ or ↓
    And model_version and holdout macro-F1 are present

  @BDD-F03-S02 @api
  Scenario: Gas-lift valve failure recognised
    When I GET /api/wells/LKM-061/classification
    Then top-1 class is "IC-07 GAS_LIFT_VALVE_CHANGE"

  @BDD-F03-S03 @ws @voice @demo
  Scenario: Model quality disclosed on request
    When I say "How good is this model? Can I trust it?"
    Then the answer reports holdout macro-F1, top-3 accuracy and the rule-based baseline macro-F1
    And the values equal backend/app/analytics/model/intervention_classifier_metrics.json exactly
    And the agent says the model was trained on synthetic data

  @BDD-F03-S04 @gate
  Scenario: Gate Q quality bars
    Given the classifier was trained by the Stage Q training script
    Then holdout macro-F1 is between 0.70 and 0.92
    And holdout top-3 accuracy is at least 0.90
    And macro-F1 beats the TC-008 rule baseline by at least 0.05
    And expected calibration error is at most 0.08

  @BDD-F03-S05 @api
  Scenario: Insufficient history returns a status
    Given a well with fewer than 90 days of production
    When its classification is requested
    Then status is "INSUFFICIENT_HISTORY" and no class is returned

  @BDD-F03-S06 @data
  Scenario: ESP replacement maps to IC-08  # V§2 WS-3 "ESP Replacement"; SDD §8.1
    Then config/ic_map.yaml maps the archetype "ESP Replacement" to "IC-08 Lift optimisation / conversion"
    And asked about ESP replacement, the agent answers with IC-08 and discloses that the dataset has no ESP wells
```

### F-04 · Next-best-action recommender (replaces fabricated recommendations)

*Anchor: T1 — "depending on not just the production data, but also of the well history, the construction, one can recommend what is the next best action … currently not there". WS3. T2 L5 "next best recommended interventions". Replaces baseline FEAT-08 (fabricated `estimated_cost_usd`, payback). Tool TC-022 · Stage R.*

```gherkin
Feature: Next best action
  As a PE
  I want ranked actions that combine production, history and construction
  So that I pick the intervention with the best value per rig-day

  @BDD-F04-S01 @api @demo
  Scenario: Ranked top-3 actions with evidence
    When I POST /api/wells/LKW-047/recommendations
    Then 3 ranked actions are returned
    And each has job_code, intervention_class, uplift_bopd, deferred_bbl_12mo, p_success,
        rig_days, requires_rig, cost_band, risk_flags, mro_status, earliest_start_date, sop_doc_id
    And action 1 is "PUMP_OVERHAUL"
    And at least one rejected alternative is listed with its reason

  @BDD-F04-S02 @api
  Scenario: Physics veto on Chan sign
    Given the classifier's top class is "IC-11 WATER_SHUTOFF_SQUEEZE"
    And the Chan WOR′ slope is negative (CONING)
    When recommendations are requested
    Then action 1 is "CHOKE_BACK" with flag "MODEL_PHYSICS_DISAGREEMENT"
    And both the ML suggestion and the physics route are shown

  @BDD-F04-S03 @ws @voice @demo
  Scenario: Engineering refusal
    When I say "What should we do with LKM-090?"
    Then action 1 is "NO_JOB_JUSTIFIED"
    And the reason cites offset_verdict "RESERVOIR_DECLINE" with the offset wells named

  @BDD-F04-S04 @api
  Scenario: Construction changes the recommendation
    Given two wells with the same production signature
    And one has casing older than 35 years and a failed squeeze in its history
    Then the old-casing well carries risk flag "WELL_INTEGRITY"
    And its squeeze p_success is lower than the other's

  @BDD-F04-S05 @api @ui @regression
  Scenario: Cost is a band, never money  # derived: D-1
    When any recommendation is rendered in the Recommendation Card
    Then cost shows only LOW, MED or HIGH plus rig_days
    And no ₹, INR, USD, "$" or payback figure appears in the API body or the card
```

### F-05 · Multi-field hierarchy

*Anchor: T1 — "currently we have Geleki … similarly you can have Lakwa, you can have Lakhmani … three areas, with their individual cluster". WS1. Tools TC-025, TC-016 v2 · Stages N, T.*

```gherkin
Feature: Asset → field → cluster → well hierarchy
  As the AM
  I want to navigate fields and their clusters
  So that I can drill from asset to a single well

  @BDD-F05-S01 @api @demo
  Scenario: List fields and clusters
    When I GET /api/fields
    Then the response lists Geleki (3 clusters, 142 wells), Lakwa (3 clusters, 160 wells), Lakhmani (2 clusters, 110 wells)

  @BDD-F05-S02 @ui @demo
  Scenario: Field selector drives the map
    When I select field "Lakwa" in the field selector
    Then the map shows every Lakwa well and the 3 GGS cluster polygons
    And no Geleki or Lakhmani well is shown
    And the KPI ribbon equals GET /api/wells/kpis?field=Lakwa

  @BDD-F05-S03 @api
  Scenario: Well IDs resolve to their field
    When I POST /api/chat with message "Tell me about LKM-061" and no field
    Then every tool call in the trace uses field "Lakhmani"

  @BDD-F05-S04 @api
  Scenario: Unknown field refused, not guessed
    When I POST /api/chat with message "Show me Rudrasagar"
    Then the answer says Rudrasagar is not in the dataset and lists the 3 fields
    And GET /api/fields/Rudrasagar/health returns 404
```

### F-06 · Field-engineer well-history dossier

*Anchor: T1 — "when a person is going to the field, the previous history is not there … aggregate all the history and give it to the person". WS4 (incl. "lithology"). Tool TC-023 · Stage S (upgrades baseline FEAT-15 export).*

```gherkin
Feature: Well history dossier for field dispatch
  As an FE going to a well pad
  I want the complete well history in one document
  So that I am not working blind

  @BDD-F06-S01 @api @demo
  Scenario: Generate a dossier PDF
    When I GET /api/wells/LKW-047/export?format=pdf
    Then a PDF of 2 to 4 pages is returned within 10 seconds
    And it contains sections Identity, Construction & Lithology, Production Snapshot,
        Intervention Timeline, Repeat Failures, Current Diagnosis & NBA, Hazards & Lessons,
        Logistics, Source Documents
    And Construction & Lithology shows the casing/tubing tally and a lithology column from formation_tops  # V§2 WS-4; D-19

  @BDD-F06-S02 @ws @voice @demo
  Scenario: Hinglish dispatch request from the field
    Given persona "FIELD_ENGINEER" and VoiceAgentPanel language "Hinglish"
    When I say "Main kal LKW-047 ja raha hoon, iski poori history de do"
    Then a tool_call for "build_well_dossier" with well_id "LKW-047" is emitted
    And the panel shows the 3 key points and a download link to the dossier PDF

  @BDD-F06-S03 @api
  Scenario: Every dossier number is traceable
    Given a generated dossier for any well
    Then every numeric value matches a source table row or a cited document fact

  @BDD-F06-S04 @api
  Scenario: Lessons come from documents with citations
    When the GK-129 dossier is generated
    Then Hazards & Lessons cites the 1998 CBL report and the 2019 failed water shut-off report by title and date

  @BDD-F06-S05 @api
  Scenario: Missing construction data is declared
    Given a well with no casing_tally rows
    Then the Construction section reads "UNAVAILABLE — casing_tally" and nothing is invented
```

### F-07 · Real Gemini Live voice (replaces fake Live)

*Anchor: T1 — "Gemini Live is not working well in the current build. It is working very good in Drilling Intelligence 2.0 … learn from that". WS5 "hands-free field technician operation". Root cause: baseline WS only wraps text chat + browser TTS. Stage U.*

```gherkin
Feature: Real-time voice with Gemini Live
  As the ED in a live demo, or an FE hands-free on a well pad
  I want to speak to the agent and hear it answer
  So that it feels like talking to a senior engineer

  @BDD-F07-S01 @ws @voice @demo
  Scenario: Voice question to spoken answer
    Given VoiceAgentPanel opens WS /ws/live and receives status "connected"
    When I say "Which field is underperforming?"
    Then the server streams an input_transcript of my question
    And a tool_call event for "compare_fields" is emitted
    And 24 kHz PCM audio starts within 2.5 s of end of speech on a warm instance
    And caption_delta events carry the spoken text
    And the browser speechSynthesis API is not used  # derived: defect fix

  @BDD-F07-S02 @ws @ui
  Scenario: Barge-in stops playback
    Given the agent is speaking
    When I start speaking
    Then playback stops within 300 ms and the new question is processed

  @BDD-F07-S03 @ws
  Scenario: Transparent reconnect keeps memory
    Given a Live session with at least 2 completed turns
    When the upstream session sends GoAway or drops
    Then the server reconnects with the latest resumption handle
    And emits status "resumed" with memory true
    And "and what about the second one?" is answered in context

  @BDD-F07-S04 @ws @ui
  Scenario: Fallback after 3 consecutive failures
    Given Gemini Live fails 3 consecutive times
    Then status "fallback" is sent
    And VoiceAgentPanel switches to text chat via POST /api/chat with a visible "text mode" badge

  @BDD-F07-S05 @ws @regression
  Scenario: Voice obeys the integrity rule
    When I ask by voice for any number
    Then the spoken number equals a value returned by a tool_call in the same turn

  @BDD-F07-S06 @ws @voice
  Scenario Outline: Language toggle is kept
    Given VoiceAgentPanel language is "<lang>"
    When I say "<utterance>"
    Then the answer is about Lakwa's worst well using tool output
    And the reply language matches "<lang>"
    Examples:
      | lang     | utterance                                   |
      | Hinglish | Lakwa mein sabse kharab well kaun sa hai?   |
      | English  | Which is the worst well in Lakwa?           |
      | Hindi    | लकवा में सबसे खराब कुआँ कौन सा है?             |

  @BDD-F07-S07 @ws
  Scenario: Live model is verified, not guessed  # derived: D-12
    When the Live proxy starts
    Then the configured Live model is present in the Vertex AI model list
    And otherwise the server logs the error and serves status "fallback"

  @BDD-F07-S08 @ui @ws
  Scenario: Hands-free open-mic, audio-only  # V§2 WS-5 "hands-free field technician operation"; "Multimodal" = audio-only in v0.4
    Given persona "FIELD_ENGINEER" and VoiceAgentPanel in Live mode
    When I switch on the open-mic toggle (off by default) and speak without holding the talk button
    Then server VAD ends my turn and a spoken answer streams back
    And the panel offers no camera or image input
```

### F-08 · Synthetic data expansion (replaces 50-well JSON)

*Anchor: T1 — "generate more data … two more clusters … Lakwa and Lakhmani … build those wells as well". WS6 telemetry list. T2 "everything needs to be generated". §8 "25 / 20 wells" is illustrative; D-2 sets 160 / 110 (pinned at Gate N, `docs/pinned_values.md`). Stage N.*

```gherkin
Feature: Synthetic data for three fields
  As the builder
  I want realistic, validated data for Geleki, Lakwa and Lakhmani
  So that every multi-field feature has something true to say

  @BDD-F08-S01 @data @regression
  Scenario: Geleki baseline reproduced
    When the Stage N generator runs for Geleki with seed 42
    Then every ADK v0.3.0 Geleki row in the overlapping 36 months is identical apart from added columns
    And the ported contract tests pass

  @BDD-F08-S02 @data
  Scenario: Per-field validator gate
    When the generator validator runs for all fields
    Then it reports 0 violations for Geleki, Lakwa and Lakhmani

  @BDD-F08-S03 @data
  Scenario: Classifier-ready labels  # derived: K-1, K-2 fixes
    Then every non-censored workover_history row has a catalogue_job_code in job_catalogue
    And an intervention_class in IC-01..IC-15, each with at least 30 rows

  @BDD-F08-S04 @data
  Scenario: Fixture wells hit their stories
    Then LKW-047 has WAIT_ON_RIG 41 days and WAIT_ON_MATERIAL 12 days in its 180-day window
    And LKM-090's offsets have decline residuals within ± 5 pp of LKM-090's (pinned max 0.6 pp)

  @BDD-F08-S05 @data
  Scenario: Telemetry columns and window
    Then daily_production for every field spans 2021-10-01 to 2026-09-30
    And carries oil, gas, water rate, THP, CHP, temperature, water cut, GOR and lift metrics

  @BDD-F08-S06 @api @regression
  Scenario: REST shapes survive the repository swap  # derived: D-11
    When I GET /api/wells, /api/wells/GK-129 and /api/wells/GK-129/history
    Then each response validates against the Stage M golden schema snapshot
    And backend/app/data/wells_data.json is no longer read
    And the data is identical across two runs on different days  # defect fix: datetime.now()
```

### F-09 · Asset-manager field performance

*Anchor: T1 — "asset manager level: Which particular field is not performing? … what is the performance at a field level". WS1 "production vs. targets, uptime, water cut, and active intervention counts". Tool TC-024 · Stage T.*

```gherkin
Feature: Field performance for the asset manager
  As the AM
  I want to compare fields against target and see why one underperforms
  So that I can allocate rigs and attention

  @BDD-F09-S01 @ws @voice @demo
  Scenario: Which field is not performing
    When I say "Which field is not performing, and why?"
    Then a tool_call for "compare_fields" with asset "ASSAM_ASSET" is emitted
    And fields are ranked by gap to target with Lakwa worst at −17.6% (QTD 2026-07-01..AS_OF; pinned at Gate N)
    And the top driver named is a controllable factor class

  @BDD-F09-S02 @ui
  Scenario: Field comparison screen
    When I open the "Field comparison" view
    Then I see gap bars per field and deferred-oil-by-factor stacks
    And the bar values equal GET /api/fields/compare

  @BDD-F09-S03 @api
  Scenario: KPI completeness
    When I GET /api/fields/compare
    Then each field row has actual_bopd, target_bopd, gap_pct, expected_bopd, uptime_pct, water_cut_pct,
        health bucket counts, deferred_bbl by factor class, active_interventions, rig and rigless candidate counts

  @BDD-F09-S04 @ws
  Scenario: Drill-down from field to wells
    Given I asked which field is underperforming
    When I say "Show me the worst wells in it"
    Then Lakwa wells are listed ranked by deferred barrels with their main factor class
    And the map selects field "Lakwa"

  @BDD-F09-S05 @api
  Scenario: Missing target is declared
    Given field_targets has no row for a field and month
    Then gap_pct is "UNAVAILABLE" and the field is excluded from the ranking with a note
```

### F-10 · Synthetic PDF document corpus

*Anchor: T1 — "generate the documents of PDF files of … well interventions and other documents. I would need your help to define it". WS6 document list (intervention reports, DWRs, completion schematics, chemical treatment logs). Stage O; tool TC-026.*

```gherkin
Feature: Fact-validated synthetic PDF corpus
  As the agent
  I want PDF documents grounded in the data
  So that citations open real files and every number in them is true

  @BDD-F10-S01 @data
  Scenario: Every printed fact validates
    When the PDF validator runs
    Then 100% of facts in every facts.json sidecar are found in the extracted PDF text
    And every document_index row points to an existing PDF

  @BDD-F10-S02 @api @ui @demo
  Scenario: Page-anchored citation opens in the reports tab
    When I POST /api/chat "Has LKW-112 had a water shut-off before? Show me the report."
    Then the answer cites title, date, page and a URI under /api/docs/
    When I click the citation
    Then WellReportsTab opens that PDF at the cited page

  @BDD-F10-S03 @api
  Scenario: Scanned document is retrievable
    Given a D1 report with has_text_layer false
    When documents are searched by well_id and topic
    Then it is returned with flag "SCANNED" and the citation resolves

  @BDD-F10-S04 @data
  Scenario: Document type coverage
    Then the corpus contains every type D1..D11 for all three fields
    And it includes daily workover reports, completion schematics with casing tallies and chemical treatment logs
```

### F-11 · Field-level 5-year production history (L1)

*Anchor: T2 — "the past let's say 5 year production data field-wise … First it will tell, then I'll say: 'Can you give me a plot?' … aggregated of all the wells." §4 Turn 1 adds gas (illustrative). Tool TC-028 · Stage T.*

```gherkin
Feature: Field-wise production history
  As the ED
  I want 5 years of production per field, told first and then plotted
  So that I see the macro trend before drilling down

  @BDD-F11-S01 @ws @voice @demo @L1
  Scenario: Tell first
    When I say "Can you give me the production history for the past 5 years, field-wise?"
    Then a tool_call for "field_production_history" for Geleki, Lakwa, Lakhmani over 60 months is emitted
    And the answer gives per field start vs end oil rate, gas trend, water-cut change and producing-well count
    And no chart is shown yet

  @BDD-F11-S02 @ui @demo @L1
  Scenario: Then plot
    Given the previous answer
    When I say "Can you give me a plot?"
    Then the field 5-year history chart opens with one monthly oil series per field, a gas series and a water-cut panel
    And plotted values equal GET /api/fields/history?fields=Geleki,Lakwa,Lakhmani&freq=M

  @BDD-F11-S03 @api
  Scenario: Aggregation integrity
    Then each field's monthly oil equals the sum of its wells' daily oil divided by days in month within 0.1%
```

### F-12 · Well deep-dive with interventions and nearby wells (L4)

*Anchor: T2 — "drill down to one particular well … show me … 2-3 year history or 5 year history … on that particular log or plot … what are the different interventions happened"; "also give information of nearby wells". Tools TC-029, TC-017 v2 · Stage T.*

```gherkin
Feature: Well profile, history overlay and neighbours

  @BDD-F12-S01 @ws @ui @demo @L4
  Scenario: Profile, history with interventions, neighbours
    When I say "Tell me more about GK-129 and show me its 3-year production history"
    Then tool_calls for "well_profile" and "plot_production" with months 36 are emitted
    And the well drawer opens on GK-129 showing zone, lift type, completion depth, casing and tubing sizes, current bucket
    And the chart has a marker for every intervention in the window with job and outcome
    And at least 3 nearby wells are listed with bucket, oil rate and decline residual

  @BDD-F12-S02 @ui
  Scenario Outline: History window is selectable
    When I choose "<window>" in the well drawer
    Then the chart shows <months> months and markers only for interventions inside it
    Examples:
      | window  | months |
      | 2 years | 24     |
      | 3 years | 36     |
      | 5 years | 60     |

  @BDD-F12-S03 @api
  Scenario: Older interventions are still disclosed
    Given a well with interventions older than the plotted window
    Then the caption lists them as "Historical" with year and outcome

  @BDD-F12-S04 @ui
  Scenario: Nearby wells are clickable on the map
    When I click a nearby well in the drawer
    Then the map pans to it and the drawer switches to that well

  @BDD-F12-S05 @api @ui
  Scenario: Temperature, GOR and gas-lift injection are charted  # V§2 WS-6; V§4 T4 "gas-lift injection pressure" (illustrative); D-19
    When I GET /api/wells/LKM-061/production?months=36&metrics=oil,gor,wht,gl_inj_rate,gl_inj_pressure
    Then the series include gor_scf_bbl, wht_degc, gl_inj_rate_mscfd and gl_inj_pressure for gas-lift well LKM-061
    And TelemetryCharts shows WHT, GOR and gas-lift injection rate and pressure panels whose values equal the API
    And for an SRP well the gas-lift series are null and their panels are hidden
```

### F-13 · Counterfactual defence (L5)

*Anchor: T2 — "'Why are you recommending this against an alternative?' Let's say perforation, I can say 'Okay why not just wax removal?' and something that is super deep." Hero GK-129 (D-7). Tool TC-027 · Stage R.*

```gherkin
Feature: Why this and not that

  @BDD-F13-S01 @ws @voice @demo @L5
  Scenario Outline: Defend the recommendation against an alternative
    Given the next best action for <well> is <recommended>
    When I say "Why are you recommending this instead of <alternative>?"
    Then a tool_call for "compare_interventions" with recommended <recommended> and alternative <alternative> is emitted
    And the answer covers diagnostic fit, this well's history, field efficacy (p_success with n),
        execution (rig or rigless, rig_days, cost band, MRO), value per rig-day and a verdict
    And every number in the answer appears in the compare_interventions return
    Examples:
      | well    | recommended            | alternative    |
      | GK-129  | WATER_SHUTOFF_SQUEEZE  | WAX_REMOVAL    |
      | GK-129  | WATER_SHUTOFF_SQUEEZE  | REPERFORATION  |
      | LKM-061 | GAS_LIFT_VALVE_CHANGE  | REPERFORATION  |

  @BDD-F13-S02 @api
  Scenario: Prior failed attempt is cited
    Given the alternative was attempted on this well before and failed
    Then the answer cites that workover's date, outcome, run life and source document

  @BDD-F13-S03 @api
  Scenario: Honest concession
    Given the alternative scores within 10% of the recommendation
    Then the verdict says the options are close and names the deciding factor

  @BDD-F13-S04 @ws @voice
  Scenario: Hinglish counterfactual
    When I say "GK-129 pe wax removal kyun nahi? Squeeze hi kyun?"
    Then the same compare_interventions tool_call is emitted and the answer is in Hinglish

  @BDD-F13-S05 @api
  Scenario: Diagnostic fit cites reservoir pressure evidence  # V§4 T5 "reservoir pressure check … IPR" (illustrative values); D-19
    When I GET /api/wells/GK-129/compare?recommended=WATER_SHUTOFF_SQUEEZE&alternative=WAX_REMOVAL
    Then the diagnostic-fit row cites the latest pressure_surveys row (survey_date, sbhp_kgcm2, pi_bpd_per_kgcm2) for GK-129
    And every pressure value equals that pressure_surveys row; no "142 bar" literal is used
```

*Job codes are pinned to `job_catalogue` at Stage N.*

### F-14 · SOP library

*Anchor: T2 — "we need to generate a lot of documents, I see. The SOPs". §4 Turn 5 "step-by-step SOP" (illustrative). Stage O/R.*

```gherkin
Feature: SOPs grounded in the catalogue

  @BDD-F14-S01 @ws @ui @demo
  Scenario: Recommendation comes with its SOP
    When a job is recommended
    Then the action has sop_doc_id and the Recommendation Card shows an "SOP" link
    When I say "How is this job done?"
    Then the agent lists SOP steps with document title and page

  @BDD-F14-S02 @data
  Scenario: SOP coverage
    Then every intervention class IC-01..IC-14 maps to at least one D11 SOP
```

### F-15 · Medallion Lakehouse

*Anchor: T2 — "showcase that in the Medallion architecture … Lakehouse"; "whether it should go ultimately into BigQuery or if there is a better database". §5 partitioning. D-9 · Stage X.*

```gherkin
Feature: Medallion lakehouse on GCS + BigQuery (BigQuery asia-south1, project workover-operations-agentic-ai)

  @BDD-F15-S01 @data
  Scenario: Layers exist and reconcile
    Then Bronze holds every landing file and PDF in GCS with BigQuery external tables
    And Silver daily_production is partitioned by production_date and clustered by field, well_id
    And Silver row counts equal Bronze row counts per table
    And Gold field KPIs equal the TC-028 output for the same window

  @BDD-F15-S02 @ws @voice @demo
  Scenario: Explain the architecture
    When I say "Where does this data live, and why BigQuery?"
    Then the agent describes Bronze, Silver and Gold and the storage rationale from the decision record
    And names at least one alternative considered and why it was not chosen

  @BDD-F15-S03 @api
  Scenario: Backend parity
    When the API runs with DATA_BACKEND=bigquery
    Then responses for the fixture wells equal DATA_BACKEND=parquet
```

### F-16 · Role-based access (minimal, optional)

*Anchor: T2 — "role-based access … if an Executive Director is asking … versus a field engineer … If it is overcomplicating, we can leave it." §6 matrix. D-8 · Stage Y. PE maps to role ASSET_MANAGER (derived).*

```gherkin
Feature: Persona-scoped answers

  @BDD-F16-S01 @ui @demo
  Scenario: Same question, different persona
    Given I pick persona "ED" in the persona picker
    When I ask "Tell me about LKW-047"
    Then I get bucket, deferred barrels, recommended action and field context, without casing tallies
    Given I pick persona "FIELD_ENGINEER"
    When I ask "Tell me about LKW-047"
    Then I get the mechanical schema, tallies, last interventions, SOP and dossier link, without field roll-ups

  @BDD-F16-S02 @api
  Scenario: Gating is enforced in tools, not the prompt
    Given header X-Persona "FIELD_ENGINEER"
    When I GET /api/fields/compare
    Then status is 403 with "not permitted for persona FIELD_ENGINEER"
    And the same tool called by the agent returns status "UNAVAILABLE"

  @BDD-F16-S03 @ws
  Scenario: Live voice honours persona
    Given persona "FIELD_ENGINEER" in VoiceAgentPanel
    When I say "Compare all fields"
    Then the spoken answer says this view is not permitted for my role
```

### F-17 · Multi-screen interface

*Anchor: T2 — "different screens opened, like what we currently have the interface … they can see different fields … and the wells where they are currently represented". Builds on baseline FEAT-01/14 · Stages T, Y.*

```gherkin
Feature: Fields and wells visible on screen

  @BDD-F17-S01 @ui @demo
  Scenario: Map shows all fields
    When I open the app with field selector "All fields"
    Then I see Geleki, Lakwa and Lakhmani boundaries, cluster polygons and every well coloured by TC-020 bucket
    And the boundaries carry the label "synthetic coordinates"  # derived: D-3
    And header counts equal GET /api/wells/kpis per field

  @BDD-F17-S02 @ui
  Scenario: Screen and chat agree
    When I click a well on the map
    Then the drawer values equal GET /api/wells/{id}/profile for that well
    And asking the agent about it returns the same values

  @BDD-F17-S03 @ui
  Scenario: Dense fields cluster
    When the map is zoomed out on "All fields"
    Then wells are clustered with counts and expand on zoom
```

### F-18 · Five-level drill-down (end-to-end acceptance)

*Anchor: T2 — "do you see the hierarchy of question and answering?" and the L1–L5 prompts. §8 Milestone 6 "Automated pytest … all 5 demo turns". Stage V.*

```gherkin
Feature: Five-level drill-down in one session

  @BDD-F18-S01 @api @demo @L1 @L2 @L3 @L4 @L5
  Scenario: Full run via POST /api/chat
    When I run in one session_id:
      | level | prompt                                                                      | required tool calls                      |
      | L1    | Can you give me the past 5 year production data field-wise?                 | field_production_history                 |
      | L1    | Can you give me a plot?                                                     | field_production_history (artifact field_history_chart) |
      | L2    | How many wells in Geleki are either sick or have lost production?           | classify_well_health, attribute_decline  |
      | L3    | Can you give me a priority list of all the wells that need intervention?    | rank_candidates                          |
      | L4    | Tell me more about GK-129 and show me its production history                | well_profile, plot_production            |
      | L5    | What are the next best recommended interventions?                           | recommend_next_best_action               |
      | L5    | Why not just wax removal?                                                   | compare_interventions                    |
    Then each turn calls its required tools
    And L2 reports "sick or lost production" as AT_RISK + UNDERPERFORMING with NOT_PRODUCING separate, plus a field factor breakdown
    And L3 ranks wells by deferred barrels recovered × p_success ÷ rig-days with cost band, without NPV, ₹ or payback  # derived: D-1, SDD §9.1
    And no answer contains a number missing from that turn's tool returns
    And total wall time is under 3 minutes on a warm instance

  @BDD-F18-S02 @ui @ws @demo
  Scenario: Same run by voice drives the screens
    Given VoiceAgentPanel is connected
    When I speak the L1–L5 prompts in order
    Then the field chart opens at L1, the map filters to Geleki at L2, the priority table shows at L3,
        the GK-129 drawer opens at L4 and the Recommendation Card shows at L5

  @BDD-F18-S03 @ws @voice
  Scenario: Hinglish L2
    When I say "Geleki mein kitne wells sick hain ya production lose kar rahe hain?"
    Then the answer equals the English L2 answer's counts
```

### F-19 · Delegation behind deterministic gates (process)

*Anchor: T2 — "what are the tasks that Opus would do and what … can be outsourced to the Flash models. For example, the document generation". See [`DELEGATION.md`](./DELEGATION.md). All stages.*

```gherkin
Feature: Flash output passes deterministic gates

  @BDD-F19-S01 @data
  Scenario: Flash never types data digits
    Given a document produced by a Flash worker from a fact-slot template
    Then every digit in it comes from a filled fact slot
    And the F-10 validator passes before the document is merged

  @BDD-F19-S02 @data
  Scenario: Orchestrator review is recorded
    Then every Flash-produced artefact has a review entry in checklist.md before commit
```

---

## Part C · Cross-cutting (X)

*Derived: integrity guardrails (brief "never fabricate numbers"; ADK prompt guardrails). X-S02 anchors to T2 "everything needs to be generated".*

```gherkin
Feature: Integrity guardrails (all features)

  @BDD-X-S01 @api @ws @regression
  Scenario: The agent never computes its own numbers
    When any answer from POST /api/chat, POST /api/wells/{id}/chat or WS /ws/live contains a number
    Then that number appears in a tool return from the same turn

  @BDD-X-S02 @api
  Scenario: Synthetic disclosure
    When I ask "Is this real Lakwa data?"
    Then the agent says the data is synthetic and representative

  @BDD-X-S03 @api @regression
  Scenario: Golden demo regression
    When the golden demo prompts run
    Then the answers contain the same key figures as the pinned Stage N snapshot

  @BDD-X-S04 @api @regression
  Scenario: No money anywhere  # derived: D-1
    When any REST response or UI screen is captured
    Then it contains no cost_usd, estimated_cost_usd, payback, ₹ or INR value

  @BDD-X-S05 @api
  Scenario: Text model unchanged, called via Vertex AI  # derived: D-13 resolved
    Then the configured text model is "gemini-3.8-flash"
    And calls go to Vertex AI with ADC and GEMINI_API_KEY is not read
```

---

## Part D · v0.5 features (F-20 … F-26)

*Authoritative source: [`v05_change_brief.md`](./v05_change_brief.md). User feedback U-1…U-7; Stages AC, DF, DG, NN, FR, W2; Decisions D-25…D-32; Tool contracts TC-030…TC-033.*

### F-20 · Answer canvas

*Anchor: U-1 — "The moment I ask the first question I get the whole well history at once"; U-2 — "Every time a user asks a specific question, the relevant data should be shown." Decision D-25. Replaces all-in-one Deep Dive with question-routed canvas views. Stage AC · Tool contract pickCanvasView.*

```gherkin
Feature: Question-driven answer canvas
  As the ED or Production Engineer
  I want specific questions to open only the matching view in the middle panel
  So that I am not overwhelmed with an all-in-one well history dump

  @BDD-F20-S01 @ui @demo
  Scenario: Production question opens production view
    Given the dashboard is open for well "LKW-019"
    When I ask in chat "show production history"
    Then the answer canvas opens in the middle panel with view "production"
    And the panel displays oil, gas, water cut and GOR time series with intervention markers
    And the all-in-one deep dive drawer remains closed

  @BDD-F20-S02 @ui @demo
  Scenario: Interventions question opens interventions view
    Given the dashboard is open for well "LKW-019"
    When I ask in chat "past interventions"
    Then the answer canvas opens in the middle panel with view "interventions"
    And the panel displays a job table with columns for date, job type, rig-days, uplift, outcome and document link
    And views for wellbore, pressures and diagnosis are not rendered in this view

  @BDD-F20-S03 @api @ui @demo
  Scenario: Chat answer is concise without multi-section history
    When I POST /api/chat "Tell me about LKW-019"
    Then the chat response text contains at most 3 sentences
    And the response contains an optional collapsed card
    And the response contains no multi-section well history dump

  @BDD-F20-S04 @ui @api
  Scenario: Full history is reached only via report
    Given the answer canvas is open on well "LKW-019"
    When I request the complete well history
    Then the chat does not dump the full well history into the conversation
    And the full history is accessible only via the "report" view or field report route
```

### F-21 · Expandable middle panel / command centre

*Anchor: U-3 — "Expand the middle screen like the map; the agent is the command centre on the right." Stage AC.*

```gherkin
Feature: Expandable middle panel with persistent command centre
  As the user
  I want to expand the middle answer canvas while keeping the agent on the right
  So that I can examine detailed well data without losing conversational context

  @BDD-F21-S01 @ui @demo
  Scenario: Expand middle panel hides map and ESC restores
    Given the answer canvas is open in the middle panel
    When I click the expand button on the middle panel
    Then the middle panel expands across the map area
    And the map is hidden
    When I press the "Escape" key or click the restore button
    Then the map is restored to its original layout and the middle panel returns to standard width

  @BDD-F21-S02 @ui @demo
  Scenario: Agent panel stays on the right during expansion
    Given VoiceAgentPanel is open on the right side of the screen
    When the middle panel transitions between standard and expanded states
    Then the agent panel remains docked on the right side as the command centre
    And voice and chat interactions remain active without interruption
```

### F-22 · Synthetic data-gap tables

*Anchor: Brief §4 — 6 new tables for 100% of wells in well_master (412 wells), written to landing then bronze → silver in BigQuery. Decision D-29. Stage DG · Tool contract TC-033.*

```gherkin
Feature: Synthetic data-gap tables and consistency
  As the analytics engine and field engineer
  I want realistic wellbore, integrity, hazard, and survey tables for all wells
  So that engineering decisions and field reports have complete data coverage

  @BDD-F22-S01 @data @gate
  Scenario: Data-gap tables cover 100% of wells
    When the Stage DG data generator executes
    Then each of the 6 tables "tubing_tally", "deviation_survey", "barrier_tests", "wellhead_rating", "fluid_hazards", and "fishing_records" contains rows for all 412 wells in well_master
    And no well in well_master is missing from tubing_tally, deviation_survey, barrier_tests, wellhead_rating, or fluid_hazards

  @BDD-F22-S02 @data @regression
  Scenario: Every synthetic row carries provenance metadata
    When the Stage DG tables are inspected in landing or BigQuery silver
    Then 100% of rows have is_synthetic set to true
    And 100% of rows have _source_system set to "wellpulse_dg_v1"
    And 100% of rows contain a non-empty _batch_id
    And generation with fixed seed 20261008 reproduces identical datasets deterministically

  @BDD-F22-S03 @data
  Scenario: Synthetic data adheres to physical and relational consistency rules
    When backend/tests/unit/test_dg_consistency.py runs against the DG tables
    Then tubing tally total length matches tubing_string depth within ±1 joint
    And deviation survey TVD is monotonic and TVD is less than or equal to MD for all stations
    And barrier test dates fall after the well's last workover end date and on or before AS_OF
    And barrier test FAIL rate is at most 5% and occurs only on wells with annulus-pressure flags
    And wellhead rating class is at least 1.5 times the field maximum THP
    And fluid hazard flags for wax, sand, and scale align with historical failure codes
    And fishing records exist only for wells with fishing or stuck pipe failure codes within their workover window
```

### F-23 · Multimodal success engine (demo scorer)

*Anchor: U-5 — "A multimodal neural network trained on history, geology, casing, production." Decision D-32 (no model training in v0.5; demo scorer formula in brief §5; production Vertex training path described in architecture panel). Stage NN · Tool contracts TC-030, success_engine.py.*

```gherkin
Feature: Multimodal intervention success engine (demo scorer)
  As the Production Engineer or Asset Manager
  I want intervention recommendations backed by stable, believable success probabilities
  So that I understand the ranking, analog evidence, and drivers consistent with well history

  @BDD-F23-S01 @data @gate
  Scenario: Deterministic success probability in valid range
    Given the demo success engine in success_engine.py
    When P(success) is evaluated for candidate interventions across producing wells
    Then p_success is strictly in the range [0.05, 0.95]
    And repeated evaluations for the same well and candidate yield identical, deterministic results
    And ranking is determined by deferred barrels recovered times p_success divided by rig-days

  @BDD-F23-S02 @data @gate
  Scenario: Analog well counts recompute exactly from data
    Given the candidate intervention class and target well
    When the success engine identifies the k = 5 most similar analog wells via cosine similarity on standardized features
    Then the analog counts n and n_success recompute exactly from workover_history
    And the analog success rate is blended 50/50 with the Bayesian-shrunk field base rate

  @BDD-F23-S03 @api @gate
  Scenario: Explanation panel presents evidence chain, analogs, drivers, and architecture
    When I request recommendations and explanation for well "LKW-019"
    Then the response includes the evidence chain linking signals to mechanism to candidate
    And the response includes the 5 analog look-alike wells with their prior outcomes
    And the response includes the top 3 drivers from SHAP on ic-hgb-v1
    And the explanation panel renders the multimodal neural network architecture diagram representing the production path
```

### F-24 · Top-3 recommendation with analogs and drivers

*Anchor: U-4 — "Recommendation can't be one; 2–3 interventions, and show how it arrived at it." Stage NN · Tool contracts TC-030, TC-031 · Route GET /api/wells/{id}/recommendations?k=3.*

```gherkin
Feature: Top-3 intervention recommendations with evidence
  As the ED or Asset Manager
  I want to see ranked intervention options with success probabilities, analog wells, and drivers
  So that I understand the rationale, trade-offs, and alternatives before committing rig resources

  @BDD-F24-S01 @api @demo
  Scenario: Recommendations return top 3 candidates and handle low expected value
    When I GET /api/wells/LKW-019/recommendations?k=3
    Then the response status is 200
    And the recommendations list contains at most 3 ranked candidates ordered by deferred barrels recovered times p_success divided by rig-days
    And when the best candidate's expected value is below the threshold in pinned_values.md, the recommendation status is NO_JOB_JUSTIFIED

  @BDD-F24-S02 @api @demo
  Scenario: Each candidate discloses probability, rig-days, cost band, and risks
    When I inspect each candidate returned by recommend_interventions for "LKW-019"
    Then each candidate object specifies class, sop_id, p_success, expected_uplift_bopd, rig_days, cost_band, risks, and why
    And cost_band is categorical without currency figures or NPV

  @BDD-F24-S03 @api @demo
  Scenario: Analog wells report look-alike success count and drivers
    When I inspect the explanation fields for a recommended candidate via TC-030 or TC-031
    Then the analogs field reports 5 nearest look-alikes on the NN embedding space of the same class
    And the explanation states "n look-alikes, m succeeded" where m is the count of successful prior jobs among those 5 wells
    And the top_drivers list contains exactly 3 feature attributions for that candidate

  @BDD-F24-S04 @ui @demo
  Scenario: Asking why not an alternative opens the compare view
    Given the recommendation view is active for well "LKW-019"
    When I ask "why not sand cleanout"
    Then the answer canvas automatically switches to view "compare"
    And the middle panel renders a side-by-side counterfactual comparison between the primary recommendation and sand cleanout
```

### F-25 · HTML field report with job program

*Anchor: U-6 — "A final report the workover crew takes to the field, with completion diagrams." Decision D-30. Stage FR · Tool contract TC-032 · Route GET /api/wells/{id}/report.*

```gherkin
Feature: Server-rendered HTML field report
  As a Field Engineer or Workover Crew Lead
  I want a printable, branded field report with a complete job program and wellbore diagram
  So that I can execute the workover safely and accurately on the well pad

  @BDD-F25-S01 @api @gate
  Scenario: Field report renders server-side HTML for all wells
    When I GET /api/wells/LKW-019/report?intervention=WATER_SHUTOFF_SQUEEZE
    Then the response status is 200
    And the response Content-Type is "text/html"
    And the report renders server-side from tool data without client-side hydration
    And local response latency p95 is under 3 seconds across all 412 wells

  @BDD-F25-S02 @ui @demo
  Scenario: ONGC branding with fallback and synthetic banner
    When the field report HTML is rendered
    Then the header and print footer display the ONGC logo SVG from frontend/public/brand/ongc_logo.svg
    And if the SVG logo file is absent, the header displays the fallback text wordmark "ONGC"
    And every printed and viewed page displays a prominent "SYNTHETIC DATA — DEMO" banner

  @BDD-F25-S03 @api @ui
  Scenario: Job program specifies kill fluid weight and barriers
    When I inspect the job program section in the field report for "LKW-019"
    Then the program specifies required rig or equipment class and step-by-step procedural steps
    And the program specifies kill fluid weight calculated directly from current reservoir pressure
    And the program specifies primary and secondary well barriers, operational risks, and contingency procedures
    And every numeric value validates against the facts.json sidecar

  @BDD-F25-S04 @ui @ws @demo
  Scenario: Chat provides one-line report link and report supports A4 printing
    When I say or type "Prepare me for the field"
    Then the chat response provides a single-line link "Field report for LKW-019 is ready → open"
    And clicking the link opens the field report in the expanded middle panel iframe
    And the view includes a Print button formatted for standard A4 page layout
```

### F-26 · Eleven-step demo flow (end-to-end acceptance)

*Anchor: Brief §6 · Lakwa to LKW-019 11-step script; eval cases in backend/eval/. Stage DF.*

```gherkin
Feature: Eleven-step demo flow in chat and voice
  As the Executive Director or Asset Manager
  I want to progress smoothly through the 11-step operational inquiry from field to wellpad
  So that I get immediate visual answers without chat clutter or conversational delay

  @BDD-F26-S01 @api @demo
  Scenario: 11-step demo flow passes via chat
    When I run the 11-step sequence in one session for field "Lakwa" and well "LKW-019":
      | step | prompt                                                 | expected view    |
      | 1    | Compare field performance                              | overview         |
      | 2    | Which wells in Lakwa are sick?                         | overview         |
      | 3    | Show priority list of wells needing intervention       | overview         |
      | 4    | Tell me about LKW-019                                  | overview         |
      | 5    | Show production history                                | production       |
      | 6    | Past interventions and workovers                       | interventions    |
      | 7    | Show wellbore diagram and completion details           | wellbore         |
      | 8    | Why is production declining?                           | diagnosis        |
      | 9    | What are the recommended interventions?                | recommendation   |
      | 10   | Why not sand cleanout?                                 | compare          |
      | 11   | Prepare me for the field                               | report           |
    Then each turn sets the corresponding answer canvas view in the middle panel
    And every chat answer is 3 sentences or fewer
    And no turn outputs a multi-section well history dump into chat

  @BDD-F26-S02 @ws @voice @demo
  Scenario: 11-step demo flow passes via Gemini Live voice
    Given VoiceAgentPanel is connected over WS /ws/live
    When I speak the 11 demo prompts in sequence for "LKW-019"
    Then the spoken responses remain under 3 sentences per turn
    And the middle panel synchronously switches to each matching canvas view
    And step 10 opens the compare view and step 11 provides the field report link
    And the conversation maintains low latency without dropped turns
```

---

## Traceability

**Answer:** 126 scenarios across 35 features; every F-xx maps to one stage gate. Summary first, full scenario list below.

### Summary per feature
| Feature | Scenarios | Stage | Tool / surface |
|---|---|---|---|
| B-01 | 4 | P/Y | TC-020, WellMap |
| B-02 | 2 | N | /api/wells/{id}/history, TelemetryCharts |
| B-03 | 1 | N | /api/wells/{id}/workovers, WorkoverTimeline |
| B-04 | 3 | U/V | WS /ws/live (legacy /api/wells/{id}/live shim until V), VoiceAgentPanel |
| B-05 | 1 | R | TC-022, Recommendation Card |
| B-06 | 2 | U/V | local fallback, VoiceAgentPanel |
| B-07 | 2 | O | /api/wells/{id}/reports, /api/docs/{doc_id}.pdf, WellReportsTab |
| B-08 | 1 | S | /api/wells/{id}/export |
| F-01 | 6 | P | TC-019 |
| F-02 | 5 | P | TC-020 |
| F-03 | 6 | Q | TC-021 |
| F-04 | 5 | R | TC-022 |
| F-05 | 4 | N, T | TC-025, TC-016 v2 |
| F-06 | 5 | S | TC-023 |
| F-07 | 8 | U | WS /ws/live, Live proxy |
| F-08 | 6 | N | generator v2 |
| F-09 | 5 | T | TC-024 |
| F-10 | 4 | O | docs_pdf, TC-026 |
| F-11 | 3 | T | TC-028 |
| F-12 | 5 | T | TC-029, TC-017 v2 |
| F-13 | 5 | R | TC-027 |
| F-14 | 2 | O, R | D11 SOPs |
| F-15 | 3 | X | BigQuery medallion |
| F-16 | 3 | Y | require() RBAC |
| F-17 | 3 | T, Y | WellMap multi-field |
| F-18 | 3 | V | all |
| F-19 | 2 | all | DELEGATION.md |
| F-20 | 4 | AC | pickCanvasView, WellDeepDiveDrawer |
| F-21 | 2 | AC | WellDeepDiveDrawer, VoiceAgentPanel |
| F-22 | 3 | DG | TC-033, test_dg_consistency.py |
| F-23 | 3 | NN | success_engine.py, demo scorer |
| F-24 | 4 | NN | TC-030, TC-031 |
| F-25 | 4 | FR | TC-032, /api/wells/{id}/report |
| F-26 | 2 | DF | /api/chat, WS /ws/live |
| X | 5 | V | all |
| **Total** | **126** | | |

### Scenario → feature → stage
| Scenario | Feature | Baseline FEAT | Stage | Runner | Tags |
|---|---|---|---|---|---|
| BDD-B01-S01 | B-01 | FEAT-01, FEAT-02, FEAT-14 | P/Y | Playwright | `@ui @regression` |
| BDD-B01-S02 | B-01 | FEAT-01, FEAT-02, FEAT-14 | P/Y | Playwright | `@ui @regression` |
| BDD-B01-S03 | B-01 | FEAT-01, FEAT-02, FEAT-14 | P/Y | Playwright | `@ui` |
| BDD-B01-S04 | B-01 | FEAT-01, FEAT-02, FEAT-14 | P/Y | Playwright | `@ui` |
| BDD-B02-S01 | B-02 | FEAT-03 | N | Playwright | `@ui @regression` |
| BDD-B02-S02 | B-02 | FEAT-03 | N | Playwright + pytest-bdd | `@ui @api @regression` |
| BDD-B03-S01 | B-03 | FEAT-04 | N | Playwright + pytest-bdd | `@ui @api @regression` |
| BDD-B04-S01 | B-04 | FEAT-05, FEAT-06, FEAT-07, FEAT-12 | U/V | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws` |
| BDD-B04-S02 | B-04 | FEAT-05, FEAT-06, FEAT-07, FEAT-12 | U/V | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws` |
| BDD-B04-S03 | B-04 | FEAT-05, FEAT-06, FEAT-07, FEAT-12 | U/V | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws` |
| BDD-B05-S01 | B-05 | FEAT-08 | R | Playwright + pytest-bdd | `@ui @api @regression` |
| BDD-B06-S01 | B-06 | FEAT-13 | U/V | pytest-bdd | `@api @regression` |
| BDD-B06-S02 | B-06 | FEAT-13 | U/V | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws` |
| BDD-B07-S01 | B-07 | FEAT-11 | O | Playwright + pytest-bdd | `@ui @api @regression` |
| BDD-B07-S02 | B-07 | FEAT-11 | O | Playwright + pytest-bdd | `@ui @api @regression` |
| BDD-B08-S01 | B-08 | FEAT-15 | S | pytest-bdd | `@api @regression` |
| BDD-F01-S01 | F-01 | NEW | P | pytest-bdd | `@api @demo` |
| BDD-F01-S02 | F-01 | NEW | P | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F01-S03 | F-01 | NEW | P | pytest-bdd | `@api` |
| BDD-F01-S04 | F-01 | NEW | P | pytest-bdd | `@api` |
| BDD-F01-S05 | F-01 | NEW | P | pytest-bdd | `@api` |
| BDD-F01-S06 | F-01 | NEW | P | Playwright + pytest-bdd | `@api @ui` |
| BDD-F02-S01 | F-02 | FEAT-02 (REPLACE) | P | pytest-bdd | `@api @demo` |
| BDD-F02-S02 | F-02 | FEAT-02 (REPLACE) | P | pytest-bdd | `@api @regression` |
| BDD-F02-S03 | F-02 | FEAT-02 (REPLACE) | P | pytest-bdd | `@api` |
| BDD-F02-S04 | F-02 | FEAT-02 (REPLACE) | P | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F02-S05 | F-02 | FEAT-02 (REPLACE) | P | Playwright | `@ui` |
| BDD-F03-S01 | F-03 | NEW | Q | pytest-bdd | `@api @demo` |
| BDD-F03-S02 | F-03 | NEW | Q | pytest-bdd | `@api` |
| BDD-F03-S03 | F-03 | NEW | Q | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F03-S04 | F-03 | NEW | Q (Gate Q) | pytest-bdd | `@gate` |
| BDD-F03-S05 | F-03 | NEW | Q | pytest-bdd | `@api` |
| BDD-F03-S06 | F-03 | NEW | N, Q | pytest-bdd | `@data` |
| BDD-F04-S01 | F-04 | FEAT-08 (REPLACE) | R | pytest-bdd | `@api @demo` |
| BDD-F04-S02 | F-04 | FEAT-08 (REPLACE) | R | pytest-bdd | `@api` |
| BDD-F04-S03 | F-04 | FEAT-08 (REPLACE) | R | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F04-S04 | F-04 | FEAT-08 (REPLACE) | R | pytest-bdd | `@api` |
| BDD-F04-S05 | F-04 | FEAT-08 (REPLACE) | R | Playwright + pytest-bdd | `@api @ui @regression` |
| BDD-F05-S01 | F-05 | NEW | N, T | pytest-bdd | `@api @demo` |
| BDD-F05-S02 | F-05 | NEW | N, T | Playwright | `@ui @demo` |
| BDD-F05-S03 | F-05 | NEW | N, T | pytest-bdd | `@api` |
| BDD-F05-S04 | F-05 | NEW | N, T | pytest-bdd | `@api` |
| BDD-F06-S01 | F-06 | FEAT-15 | S | pytest-bdd | `@api @demo` |
| BDD-F06-S02 | F-06 | FEAT-15 | S | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F06-S03 | F-06 | FEAT-15 | S | pytest-bdd | `@api` |
| BDD-F06-S04 | F-06 | FEAT-15 | S | pytest-bdd | `@api` |
| BDD-F06-S05 | F-06 | FEAT-15 | S | pytest-bdd | `@api` |
| BDD-F07-S01 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F07-S02 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | Playwright + pytest-bdd + FakeLiveSession | `@ws @ui` |
| BDD-F07-S03 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | pytest-bdd + FakeLiveSession | `@ws` |
| BDD-F07-S04 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | Playwright + pytest-bdd + FakeLiveSession | `@ws @ui` |
| BDD-F07-S05 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | pytest-bdd + FakeLiveSession | `@ws @regression` |
| BDD-F07-S06 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | pytest-bdd + FakeLiveSession | `@ws @voice` |
| BDD-F07-S07 | F-07 | FEAT-06, FEAT-07, FEAT-12 (REPLACE) | U | pytest-bdd + FakeLiveSession | `@ws` |
| BDD-F07-S08 | F-07 | FEAT-06 (REPLACE) | U | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws` |
| BDD-F08-S01 | F-08 | FEAT-09 (REPLACE) | N | pytest-bdd | `@data @regression` |
| BDD-F08-S02 | F-08 | FEAT-09 (REPLACE) | N | pytest-bdd | `@data` |
| BDD-F08-S03 | F-08 | FEAT-09 (REPLACE) | N | pytest-bdd | `@data` |
| BDD-F08-S04 | F-08 | FEAT-09 (REPLACE) | N | pytest-bdd | `@data` |
| BDD-F08-S05 | F-08 | FEAT-09 (REPLACE) | N | pytest-bdd | `@data` |
| BDD-F08-S06 | F-08 | FEAT-09 (REPLACE) | N | pytest-bdd | `@api @regression` |
| BDD-F09-S01 | F-09 | NEW | T | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F09-S02 | F-09 | NEW | T | Playwright | `@ui` |
| BDD-F09-S03 | F-09 | NEW | T | pytest-bdd | `@api` |
| BDD-F09-S04 | F-09 | NEW | T | pytest-bdd + FakeLiveSession | `@ws` |
| BDD-F09-S05 | F-09 | NEW | T | pytest-bdd | `@api` |
| BDD-F10-S01 | F-10 | FEAT-11 | O | pytest-bdd | `@data` |
| BDD-F10-S02 | F-10 | FEAT-11 | O | Playwright + pytest-bdd | `@api @ui @demo` |
| BDD-F10-S03 | F-10 | FEAT-11 | O | pytest-bdd | `@api` |
| BDD-F10-S04 | F-10 | FEAT-11 | O | pytest-bdd | `@data` |
| BDD-F11-S01 | F-11 | NEW | T | pytest-bdd + FakeLiveSession | `@ws @voice @demo @L1` |
| BDD-F11-S02 | F-11 | NEW | T | Playwright | `@ui @demo @L1` |
| BDD-F11-S03 | F-11 | NEW | T | pytest-bdd | `@api` |
| BDD-F12-S01 | F-12 | NEW | T | Playwright + pytest-bdd + FakeLiveSession | `@ws @ui @demo @L4` |
| BDD-F12-S02 | F-12 | NEW | T | Playwright | `@ui` |
| BDD-F12-S03 | F-12 | NEW | T | pytest-bdd | `@api` |
| BDD-F12-S04 | F-12 | NEW | T | Playwright | `@ui` |
| BDD-F12-S05 | F-12 | NEW | N, T | Playwright + pytest-bdd | `@api @ui` |
| BDD-F13-S01 | F-13 | NEW | R | pytest-bdd + FakeLiveSession | `@ws @voice @demo @L5` |
| BDD-F13-S02 | F-13 | NEW | R | pytest-bdd | `@api` |
| BDD-F13-S03 | F-13 | NEW | R | pytest-bdd | `@api` |
| BDD-F13-S04 | F-13 | NEW | R | pytest-bdd + FakeLiveSession | `@ws @voice` |
| BDD-F13-S05 | F-13 | NEW | N, R | pytest-bdd | `@api` |
| BDD-F14-S01 | F-14 | NEW | O, R | Playwright + pytest-bdd + FakeLiveSession | `@ws @ui @demo` |
| BDD-F14-S02 | F-14 | NEW | O, R | pytest-bdd | `@data` |
| BDD-F15-S01 | F-15 | NEW | X | pytest-bdd | `@data` |
| BDD-F15-S02 | F-15 | NEW | X | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |
| BDD-F15-S03 | F-15 | NEW | X | pytest-bdd | `@api` |
| BDD-F16-S01 | F-16 | NEW | Y | Playwright | `@ui @demo` |
| BDD-F16-S02 | F-16 | NEW | Y | pytest-bdd | `@api` |
| BDD-F16-S03 | F-16 | NEW | Y | pytest-bdd + FakeLiveSession | `@ws` |
| BDD-F17-S01 | F-17 | FEAT-01, FEAT-14 | T, Y | Playwright | `@ui @demo` |
| BDD-F17-S02 | F-17 | FEAT-01, FEAT-14 | T, Y | Playwright | `@ui` |
| BDD-F17-S03 | F-17 | FEAT-01, FEAT-14 | T, Y | Playwright | `@ui` |
| BDD-F18-S01 | F-18 | NEW | V | pytest-bdd | `@api @demo @L1 @L2 @L3 @L4 @L5` |
| BDD-F18-S02 | F-18 | NEW | V | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws @demo` |
| BDD-F18-S03 | F-18 | NEW | V | pytest-bdd + FakeLiveSession | `@ws @voice` |
| BDD-F19-S01 | F-19 | NEW | all | pytest-bdd | `@data` |
| BDD-F19-S02 | F-19 | NEW | all | pytest-bdd | `@data` |
| BDD-X-S01 | X | NEW | V | pytest-bdd + FakeLiveSession | `@api @ws @regression` |
| BDD-X-S02 | X | NEW | V | pytest-bdd | `@api` |
| BDD-X-S03 | X | NEW | V | pytest-bdd | `@api @regression` |
| BDD-X-S04 | X | NEW | V | pytest-bdd | `@api @regression` |
| BDD-X-S05 | X | NEW | V | pytest-bdd | `@api` |
| BDD-F20-S01 | F-20 | NEW | AC | Playwright | `@ui @demo` |
| BDD-F20-S02 | F-20 | NEW | AC | Playwright | `@ui @demo` |
| BDD-F20-S03 | F-20 | NEW | AC | pytest-bdd + Playwright | `@api @ui @demo` |
| BDD-F20-S04 | F-20 | NEW | AC | Playwright + pytest-bdd | `@ui @api` |
| BDD-F21-S01 | F-21 | NEW | AC | Playwright | `@ui @demo` |
| BDD-F21-S02 | F-21 | NEW | AC | Playwright | `@ui @demo` |
| BDD-F22-S01 | F-22 | NEW | DG (Gate DG) | pytest-bdd | `@data @gate` |
| BDD-F22-S02 | F-22 | NEW | DG | pytest-bdd | `@data @regression` |
| BDD-F22-S03 | F-22 | NEW | DG | pytest-bdd | `@data` |
| BDD-F23-S01 | F-23 | NEW | NN (Gate NN) | pytest-bdd | `@data @gate` |
| BDD-F23-S02 | F-23 | NEW | NN (Gate NN) | pytest-bdd | `@data @gate` |
| BDD-F23-S03 | F-23 | NEW | NN | pytest-bdd | `@api @gate` |
| BDD-F24-S01 | F-24 | NEW | NN | pytest-bdd | `@api @demo` |
| BDD-F24-S02 | F-24 | NEW | NN | pytest-bdd | `@api @demo` |
| BDD-F24-S03 | F-24 | NEW | NN | pytest-bdd | `@api @demo` |
| BDD-F24-S04 | F-24 | NEW | NN | Playwright | `@ui @demo` |
| BDD-F25-S01 | F-25 | NEW | FR (Gate FR) | pytest-bdd | `@api @gate` |
| BDD-F25-S02 | F-25 | NEW | FR | Playwright | `@ui @demo` |
| BDD-F25-S03 | F-25 | NEW | FR | pytest-bdd + Playwright | `@api @ui` |
| BDD-F25-S04 | F-25 | NEW | FR | Playwright + pytest-bdd + FakeLiveSession | `@ui @ws @demo` |
| BDD-F26-S01 | F-26 | NEW | DF (Gate DF) | pytest-bdd | `@api @demo` |
| BDD-F26-S02 | F-26 | NEW | DF | pytest-bdd + FakeLiveSession | `@ws @voice @demo` |

---

## How the scenarios run

**Answer:** one `.feature` file per feature under `backend/tests/bdd/features/`, executed by **pytest-bdd** for `@api`/`@ws`/`@data`/`@gate`, by **Playwright** for `@ui`, and by a **FakeLiveSession** for `@ws` so CI never needs Vertex AI. Stage V wires them; each stage adds its own scenarios as it lands (§8 Milestone 6: "Automated pytest execution covering all 5 demo turns … RBAC view gating validation").

| Runner | Scope | How | Command (proposed) |
|---|---|---|---|
| pytest-bdd | `@api`, `@data`, `@gate` | FastAPI `TestClient` against the app; `DATA_BACKEND=parquet`; the agent trace (tool calls + returns) is exposed to tests by a debug header so "number appears in a tool return" (X-S01) is checkable | `uv run pytest backend/tests/bdd -m "api or data or gate"` |
| pytest-bdd + FakeLiveSession | `@ws`, `@voice` | Dependency override swaps the google-genai Live client for a scripted fake that emits `input_transcript`, `tool_call`, `caption_delta`, 24 kHz PCM chunks, `GoAway` and failures. Tool calls hit the **real** deterministic tools. Voice prompts are injected as transcripts; one recorded 16 kHz WAV per language checks the audio path | `uv run pytest backend/tests/bdd -m ws` |
| Playwright | `@ui` | Builds `frontend/`, starts the backend with fixtures, drives map, field selector, well drawer, VoiceAgentPanel (WS mocked to FakeLiveSession), WellReportsTab; asserts UI values equal the matching API response | `npx playwright test` in `frontend/` |
| Real Live smoke | `@demo @ws` subset | Manual / nightly against the deployed revision with ADC; not in CI | Stage W smoke script |

Rules: step definitions are Gherkin glue only (Flash work, F-19); assertions on numbers compare to tool or API returns, never to literals, except pinned «» values after Gate N. Golden REST snapshots from Stage M back B-0x `@regression` and F08-S06.

---

## Verbatim gaps found (added in this version)

These verbatim asks were missing or weak in the prior ADK BDD and are now covered:

| Verbatim anchor | Gap | Added |
|---|---|---|
| T2 "2-3 year history or 5 year history" | Only a 3-year window was tested | F12-S02 window outline 24/36/60 |
| T2 "Let's say perforation … why not just wax removal?" | Only one alternative | F13-S01 examples incl. REPERFORATION |
| T2 "different screens … see different fields" + "drill down to a particular field" | Voice/chat did not drive screens | F05-S02, F09-S04, F18-S02 |
| T2 "information of nearby wells" | Neighbours not navigable | F12-S04 |
| T2 "whether it should go … into BigQuery or if there is a better database" | Alternatives not required | F15-S02 names an alternative considered |
| T2 "delegation … Opus … Flash" | No scenario for F-19 | F19-S01, S02 |
| T1 "Gemini Live is not working well" (WellPulse root cause: fake WS + browser TTS) | — | F07-S01 (no speechSynthesis), F07-S07 |
| WS4 "lithology" | Missing from dossier sections | F06-S01 "Construction & Lithology" |
| WS5 "hands-free field technician" + §6 FE "Gemini Live voice guidance" | No FE voice scenario | F06-S02 (Hinglish), F16-S03 |
| WS6 telemetry "temperature, … GOR, artificial lift metrics" | Columns not asserted | F08-S05 (data), F12-S05 (API + TelemetryCharts: `wht_degc`, GOR, gas-lift injection rate + pressure) |
| WS6 docs "Chemical Treatment Logs" | Not asserted | F10-S04 |
| WS1 "active intervention counts" | Missing KPI | F09-S03 `active_interventions` |
| §4 Turn 1 gas trend (illustrative) | Gas not plotted | F11-S01/S02 gas series |
| §4 Turn 2 factor breakdown at L2 (illustrative) | — | F18-S01 L2 factor breakdown |
| T1 "which … not producing now … already built" | Baseline status hard-coded | F02-S05, B01-S01 |
| WS3 "ESP Replacement" | No ESP wells in the Assam data | F03-S06 (maps to IC-08) |
| WS5 "Voice/Multimodal … hands-free" | Push-to-talk only; image input undefined | F07-S08 (open-mic option; audio-only in v0.4) |
| §4 Turn 5 "reservoir pressure check … IPR" (illustrative) | No pressure evidence in the data | F13-S05 (`pressure_surveys` in the diagnostic-fit row) |

Conflicts resolved against verbatim (not gaps): §4 ₹ cost / NPV / payback → cost band + rig-days, ranked by deferred barrels × p_success ÷ rig-days (D-1, SDD §9.1); §8 "25 / 20 wells" → 160 / 110 (D-2); WS2 three health categories → four TC-020 buckets (SDD §6.3); WS5 "Multimodal" → audio-only in v0.4; V§5 Vertex AI Search → TF-IDF in v0.4, Vertex AI Search optional later (D-17).
