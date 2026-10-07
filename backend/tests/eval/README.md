# WellPulse Agent Tool-Selection Evaluation Dataset (v0.4)

This directory contains evaluation datasets for WellPulse agent tool-selection and routing verification.

## Files
- `datasets/v04-dataset.json`: Canonical evaluation dataset containing 46 test cases.
- `wellpulse-eval.json`: Byte-identical copy of `datasets/v04-dataset.json` for runner compatibility.
- `README.md`: Documentation of dataset schema, field definitions, and BDD scenario mapping.

## Schema & Field Definitions

Each evaluation case conforms to the `agents-cli` inference input specification extended with WellPulse operational metadata:

| Field | Type | Description |
|---|---|---|
| `eval_case_id` | `string` | Unique identifier for the test case (e.g., `f18_l1_tell_ed`). |
| `bdd` | `list[string]` | BDD scenario identifiers from `docs/BDD.md` mapped to this test case. |
| `level` | `string` | Hierarchy level (`L1` to `L5`). |
| `persona` | `string` | User persona: `ED` (Executive Director), `ASSET_MANAGER`, or `FIELD_ENGINEER`. |
| `language` | `string` | Query language: `english`, `hinglish`, or `hindi`. |
| `context` | `object` | Session state containing `field` (`ALL`, `Geleki`, `Lakwa`, `Lakhmani`), `well_id` (`GK-129`, `LKW-047`, `LKM-090`, `LKM-061`, or `null`), and `screen`. |
| `history` | `list[string]` | Prior conversation turns in the session required to establish conversational context. |
| `prompt` | `object` | Current turn prompt with `role: "user"` and `parts: [{"text": "..."}]`. |
| `expected_tools` | `list[string]` | Tools that must be invoked in the evaluated turn. All listed tools are required. |
| `expected_any_of` | `list[list[string]]` | Disjunctive tool requirement: at least one tool from each inner list must be invoked. |
| `forbidden_tools` | `list[string]` | Tools that must not be invoked during the turn. |
| `expect_refusal` | `boolean` | `true` when RBAC denies access (tool is called, returns `UNAVAILABLE`, agent provides refusal message) or when domain logic indicates `NO_JOB_JUSTIFIED`. |
| `tags` | `list[string]` | Metadata tags (`demo`, `L1`-`L5`, `voice`, `hinglish`, `hindi`, `rbac`, `refusal`, `disclosure`, `holdout`). |

## BDD Scenario Mapping

| BDD Scenario | Feature | Description | Eval Case IDs |
|---|---|---|---|
| `BDD-F18-S01` | F-18 | Five-level drill-down end-to-end matrix (7 prompts × 3 personas) | `f18_l1_tell_ed`, `f18_l1_tell_am`, `f18_l1_tell_fe`, `f18_l1_plot_ed`, `f18_l1_plot_am`, `f18_l1_plot_fe`, `f18_l2_ed`, `f18_l2_am`, `f18_l2_fe`, `f18_l3_ed`, `f18_l3_am`, `f18_l3_fe`, `f18_l4_ed`, `f18_l4_am`, `f18_l4_fe`, `f18_l5_nba_ed`, `f18_l5_nba_am`, `f18_l5_nba_fe`, `f18_l5_counter_ed`, `f18_l5_counter_am`, `f18_l5_counter_fe` |
| `BDD-F18-S03` | F-18 | Hinglish L2 well health query | `f18_s03_hinglish_l2` |
| `BDD-F01-S01` | F-01 | Decline factor attribution | `f18_l2_ed`, `f18_l2_am` |
| `BDD-F01-S02` | F-01 | Voice decline attribution (LKW-047) | `f01_s02_attribution` |
| `BDD-F02-S01` | F-02 | Health screening 4-bucket classification | `f18_l2_ed`, `f18_l2_am`, `f18_l2_fe` |
| `BDD-F02-S04` | F-02 | Hinglish well health query (Lakhmani) | `f02_s04_hinglish_health` |
| `BDD-F03-S03` | F-03 | Model quality and trust disclosure | `f03_s03_classifier_trust` |
| `BDD-F04-S01` | F-04 | Next-best-action recommendations & candidate ranking | `f18_l3_ed`, `f18_l3_am`, `f18_l3_fe`, `f18_l5_nba_ed`, `f18_l5_nba_am`, `f18_l5_nba_fe` |
| `BDD-F04-S03` | F-04 | NBA refusal (LKM-090 NO_JOB_JUSTIFIED) | `f04_s03_refusal_lkm090` |
| `BDD-F06-S02` | F-06 | Hinglish field dispatch well dossier (LKW-047) | `f06_s02_hinglish_dossier` |
| `BDD-F07-S01` | F-07 | Voice field performance comparison | `f07_s01_underperforming` |
| `BDD-F07-S06` | F-07 | Multi-lingual worst well queries (Hinglish, Hindi, English) | `f07_s06_hinglish_worst_well`, `f07_s06_hindi_worst_well`, `f07_s06_english_worst_well` |
| `BDD-F09-S01` | F-09 | Field comparison and performance drivers | `f09_s01_not_performing_why`, `f16_s02_fe_refusal_which_field` |
| `BDD-F09-S04` | F-09 | Field to wells drill-down | `f09_s04_worst_wells_in_field` |
| `BDD-F11-S01` | F-11 | 5-year field-wise production history (tell) | `f18_l1_tell_ed`, `f18_l1_tell_am`, `f18_l1_tell_fe`, `f11_s01_5year_history` |
| `BDD-F11-S02` | F-11 | 5-year field-wise production history (plot) | `f18_l1_plot_ed`, `f18_l1_plot_am`, `f18_l1_plot_fe` |
| `BDD-F12-S01` | F-12 | Well profile and 3-year production history plot | `f18_l4_ed`, `f18_l4_am`, `f18_l4_fe`, `f12_s01_3year_deepdive` |
| `BDD-F13-S01` | F-13 | Counterfactual intervention defense against alternatives | `f18_l5_counter_ed`, `f18_l5_counter_am`, `f18_l5_counter_fe`, `f13_s01_gk129_wax_removal`, `f13_s01_gk129_reperforation`, `f13_s01_lkm061_reperforation` |
| `BDD-F13-S04` | F-13 | Hinglish counterfactual defense (GK-129) | `f13_s04_hinglish_counterfactual` |
| `BDD-F14-S01` | F-14 | SOP retrieval and procedure explanation | `f14_s01_sop_how_job_done` |
| `BDD-F15-S02` | F-15 | Architectural storage explanation | `f15_s02_architecture_storage` |
| `BDD-F16-S01` | F-16 | Persona-dependent well information (ED vs FIELD_ENGINEER) | `f16_s01_tell_lkw047_ed`, `f16_s01_tell_lkw047_fe` |
| `BDD-F16-S02` | F-16 | RBAC tool enforcement for FIELD_ENGINEER | `f18_l1_tell_fe`, `f18_l1_plot_fe`, `f16_s02_fe_refusal_which_field` |
| `BDD-F16-S03` | F-16 | Voice RBAC refusal for FIELD_ENGINEER | `f16_s03_fe_refusal_compare_all_fields` |
| `BDD-X-S02` | X | Synthetic data disclosure guardrail | `x_s02_synthetic_disclosure` |

## Validation Gate

Run the evaluation gate to confirm dataset validity and consistency:
```bash
cd backend && uv run python -c "import json;d=json.load(open('tests/eval/datasets/v04-dataset.json'));c=d['eval_cases'];print(len(c));assert len(c)>=36;assert len({x['eval_case_id'] for x in c})==len(c);print(sorted({t for x in c for t in x['expected_tools']}))" && cmp tests/eval/datasets/v04-dataset.json tests/eval/wellpulse-eval.json
```
