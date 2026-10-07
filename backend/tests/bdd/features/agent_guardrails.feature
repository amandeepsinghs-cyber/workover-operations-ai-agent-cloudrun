@BDD-X @BDD-F16 @guardrails
Feature: Integrity guardrails and role-based access

  @BDD-X-S01 @api @regression
  Scenario: The agent never computes its own numbers
    When any answer from POST /api/chat contains a number
    Then that number appears in a tool return from the same turn

  @BDD-X-S02 @api
  Scenario: Synthetic disclosure
    When I ask "Is this real Lakwa data?"
    Then the agent says the data is synthetic and representative

  @BDD-X-S04 @api @regression
  Scenario: No money anywhere
    When any REST response or UI screen is captured
    Then it contains no cost_usd, estimated_cost_usd, payback, ₹ or INR value

  @BDD-X-S05 @api
  Scenario: Text model unchanged, called via Vertex AI
    Then the configured text model is "gemini-3.8-flash"
    And calls go to Vertex AI with ADC and GEMINI_API_KEY is not read

  @BDD-F16-S02 @api
  Scenario: Gating is enforced in tools, not the prompt
    Given header X-Persona "FIELD_ENGINEER"
    When I GET /api/fields/compare
    Then status is 403 with "not permitted for persona FIELD_ENGINEER"
    And the same tool called by the agent returns status "UNAVAILABLE"

  @BDD-F16-S03 @api @ws
  Scenario: Field engineer denied field aggregate in chat
    Given header X-Persona "FIELD_ENGINEER"
    When I ask "Compare all fields"
    Then compare_fields tool call returns status "UNAVAILABLE"
    And artifacts list is empty
