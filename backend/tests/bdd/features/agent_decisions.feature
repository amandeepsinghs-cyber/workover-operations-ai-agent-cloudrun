@BDD-F04 @BDD-F09 @BDD-F11 @BDD-F12 @BDD-F13 @decisions
Feature: Agent decisions, domain intelligence and analytical deep dives

  @BDD-F04-S01 @api @demo
  Scenario: Ranked top-3 actions with evidence
    When I GET /api/wells/GK-129/nba
    Then ranked actions are returned with evidence
    And each action has job_code, intervention_class, uplift_bopd, deferred_bbl_12mo, p_success, rig_days, requires_rig, cost_band
    And FIELD_ENGINEER persona sees no cost_band key in nba JSON

  @BDD-F04-S03 @api @ws @demo
  Scenario: Engineering refusal on LKM-090
    Given persona "ASSET_MANAGER" and well "LKM-090" in field "Lakhmani"
    When I say "What should we do on LKM-090?"
    Then action 1 is "NO_JOB_JUSTIFIED"
    And recommend_next_best_action is called

  @BDD-F04-S05 @api @regression
  Scenario: Cost is a band, never money
    When recommendations are retrieved for "GK-129"
    Then cost shows only LOW, MED or HIGH plus rig_days
    And no ₹, INR, USD, "$" or payback figure appears in the API body

  @BDD-F09-S01 @api @ws @demo
  Scenario: Which field is not performing
    When I say "Which field is not performing, and why?"
    Then a tool_call for "compare_fields" is emitted
    And Lakwa is identified as underperforming

  @BDD-F09-S03 @api
  Scenario: KPI completeness
    When I GET /api/fields/compare as "ASSET_MANAGER"
    Then each field row has actual_bopd, target_bopd, gap_pct, expected_bopd, uptime_pct, water_cut_pct

  @BDD-F11-S01 @api @demo @L1
  Scenario: Tell first
    When I say "Can you give me the past 5 year production data field-wise?"
    Then a tool_call for "field_production_history" is emitted
    And no chart is shown yet

  @BDD-F11-S02 @api @demo @L1
  Scenario: Then plot
    Given I already asked for field 5 year production data
    When I say "Can you give me a plot?"
    Then a tool_call for "field_production_history" is emitted
    And the field history chart artifact is returned with action screen "field_history"

  @BDD-F12-S01 @api @demo @L4
  Scenario: Profile, history with interventions, neighbours
    When I say "Tell me more about GK-129 and show me its production history"
    Then tool_calls for "well_profile" and "plot_production" are emitted
    And artifacts include "well_profile" and "well_production_chart"
    And the action screen is "well" with well_id "GK-129"

  @BDD-F13-S01 @api @demo @L5
  Scenario: Defend the recommendation against an alternative
    Given persona "ASSET_MANAGER" and well "GK-129"
    When I say "Why not just wax removal?"
    Then a tool_call for "compare_interventions" is emitted with alternative "wax removal"
    And artifact kind "counterfactual" is returned

  @BDD-F13-S05 @api
  Scenario: Counterfactual REST endpoint
    When I GET /api/wells/GK-129/compare with alternative "wax removal"
    Then status is 200 with status OK and comparison data
