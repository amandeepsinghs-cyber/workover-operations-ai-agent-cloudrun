@BDD-F18 @demo
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
    And L3 ranks wells by deferred barrels recovered × p_success ÷ rig-days with cost band, without NPV, ₹ or payback
    And no answer contains a number missing from that turn's tool returns
    And total wall time is under 3 minutes on a warm instance

  @BDD-F18-S02 @ui @ws @demo
  Scenario: Same run by voice drives the screens
    When I run the demo turns in order
    Then the field chart opens at L1, the map filters to Geleki at L2, the priority table shows at L3, the GK-129 drawer opens at L4 and the Recommendation Card shows at L5

  @BDD-F18-S03 @ws @voice
  Scenario: Hinglish L2
    When I say "Geleki mein kitne wells sick hain ya production lose kar rahe hain?"
    Then the answer equals the English L2 answer's counts

  @BDD-F18-S04 @api
  Scenario: Sessions do not leak tool calls between turns
    When I ask about GK-129 and then ask about Geleki well health in the same session
    Then the second turn does not contain well profile tool calls or artifacts
