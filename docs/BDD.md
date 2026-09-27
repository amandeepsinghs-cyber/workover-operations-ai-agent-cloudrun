# Behavior-Driven Development (BDD) Specifications
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 1.0.0  
**Test Framework Compatibility:** Cucumber / Behave / Cypress / Playwright  

---

```gherkin
Feature: Geospatial Well Health Prioritization & Triage
  As a Production Engineer
  I want to view all operational wells on an interactive map categorized by health status
  So that I can immediately triage critical assets requiring urgent intervention

  Background:
    Given the WellPulse platform is running locally
    And the synthetic dataset of 50 Geleki Brownfield wells (Assam, ONGC) is loaded

  Scenario: Initial fleet overview on dashboard load
    When the user navigates to the dashboard
    Then the high-resolution satellite map of Geleki Field (Assam) should display 50 well markers
    And each marker must display a permanent tag badge with the well name (e.g. "GLK-101")
    And each marker must display an authentic oil derrick wellhead glyph
    And the fleet KPI summary ribbon should display:
      | Metric                 | Expected Value |
      | Total Wells            | 50             |
      | Healthy Wells (Green)  | 32             |
      | Attention (Amber)      | 12             |
      | Failed/Critical (Red)  | 6              |
    And critical well markers must display an active visual pulse animation across the satellite terrain

  Scenario Outline: Filter wellheads by operational status
    When the user clicks the filter chip "<status_filter>"
    Then the map should render only markers with status "<status_filter>"
    And the well count in the table/sidebar should match "<expected_count_type>"

    Examples:
      | status_filter   | expected_count_type |
      | All             | 50                  |
      | Healthy         | 32                  |
      | Needs Attention | 12                  |
      | Critical/Failed | 6                   |

  Scenario: Toggle between Satellite Imagery and Dark SCADA layers
    When the user clicks "Dark SCADA" on the map layer control
    Then the map tile layer should switch from Esri World Imagery to Esri Dark Gray Canvas
    And all tagged wellhead markers and pulsing indicators must remain visible

  Scenario: Search for a specific well by name or formation
    When the user enters "Tipam Sand TS-2" into the search bar
    Then the map should highlight and pan to "GLK-101"
    And other non-matching wellheads should be dimmed or hidden

---

Feature: Well Selection and 24-Month Telemetry Drilldown
  As a Reservoir Engineer
  I want to select a specific well from the map or list
  So that I can inspect its complete 24-month production history and pressure dynamics

  Scenario: Select a well from the map
    Given the operator clicks on marker "WELL-TX-104 (Wolfcamp A-12)"
    Then the telemetry panel on the dashboard must populate with data for "WELL-TX-104"
    And the wellhead KPI cards should display:
      | Metric                 | Units |
      | Current Oil Production | BOPD  |
      | Current Gas Production | MCFD  |
      | Water Cut              | %     |
      | Tubing Pressure        | psi   |
      | Casing Pressure        | psi   |
      | Artificial Lift Type   | Text  |
    And the production timeseries chart must render 730 historical daily points
    And the user can toggle the time range between "1 Month", "6 Months", "1 Year", and "2 Years"

  Scenario: Inspect water breakthrough anomaly in historical chart
    Given "WELL-TX-104" is currently selected
    When the user inspects the historical Water Cut chart around month 14
    Then the chart tooltip must show a sharp increase from 32% to 64%
    And the corresponding oil production chart must show a decline from 350 to 180 BOPD

---

Feature: Workover and Intervention History Timeline
  As a Workover Specialist
  I want to review past operations performed on the selected well
  So that I can assess intervention frequency, cost, and effectiveness

  Scenario: View historical workovers chronologically
    Given "WELL-TX-104" is selected
    When the operator opens the "Workover History" tab
    Then a chronological list of workover events should be rendered
    And each event card must display:
      | Field            | Description                                  |
      | Date             | ISO Date of intervention                     |
      | Operation Type   | e.g. Acid Stimulation, ESP Replacement       |
      | Total Cost       | USD formatted currency                       |
      | Contractor       | Servicing company name                       |
      | Scope Summary    | Narrative of work done                       |
      | Delta Flow Rate  | Net change in BOPD following the operation   |

---

Feature: Voice-Enabled Contextual AI Agent
  As a Field Operations Engineer
  I want to verbally interact with an AI agent that possesses the active well's full context
  So that I can diagnose issues and evaluate history hands-free

  Scenario: Voice query about historical interventions
    Given "WELL-TX-104" is the active well
    When the user clicks the microphone button and speaks:
      """
      What was the last workover done on this well and how much did it cost?
      """
    Then the Speech-to-Text engine must transcribe the audio into the chat prompt
    And the AI Agent must receive the well's complete workover history in its context
    And the AI Agent must generate a response containing:
      - The exact operation type (e.g. Acid Stimulation)
      - The date of execution
      - The total cost in USD
      - The post-workover production uplift
    And the agent's text response must be displayed in the chat stream
    And the audio synthesis engine (TTS) must speak the response aloud
    And the audio waveform must animate while speech is outputting

  Scenario: Diagnostic inquiry regarding production decline
    Given "WELL-TX-104" is the active well with status "Needs Attention"
    When the user asks:
      """
      Why has production declined over the last 90 days?
      """
    Then the agent must identify the correlation between rising water cut, declining tubing pressure, and probable scale deposition
    And the response must cite the historical data points

---

Feature: Prescriptive Workover Recommendations
  As an Operations Manager
  I want the AI agent to provide actionable engineering recommendations
  So that I can expedite workover scheduling with cost and production estimates

  Scenario: Request intervention recommendation
    Given "WELL-TX-104" is the active well
    When the user clicks "Generate Recommendation" or asks "What should we do to fix this well?"
    Then the agent must output a structured Recommendation Card containing:
      | Attribute           | Expectation                                        |
      | Recommended Action  | Specific engineering job (e.g., Scale Squeeze)     |
      | Urgency Level       | Immediate, High, or Routine                        |
      | Estimated Cost      | Approximate operational expense in USD             |
      | Expected Uplift     | Forecasted barrels per day increase (+BOPD)        |
      | Payback Period      | Estimated days to recoup investment                |
      | Safety & Risk Notes | Containment and environmental protocols            |

---

Feature: Offline and Local Fallback Resilience
  As a Software Engineer running WellPulse locally
  I want the application to operate even without cloud API keys
  So that local development and demo testing never crash

  Scenario: Run AI queries without GEMINI_API_KEY set
    Given the environment variable "GEMINI_API_KEY" is empty
    When an operator submits a question to the AI Agent
    Then the backend must gracefully switch to the built-in Local Petroleum Expert Engine
    And return an accurate, well-grounded contextual response based on the well's telemetry
    And no 500 error or crash should occur
```
