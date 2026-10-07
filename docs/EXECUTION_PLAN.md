# WellPulse v0.4 — Execution Plan

**Version:** 3.0.0 · **Date:** 2026-10-07 · **Source:** [`verbatim.md`](../verbatim.md) · **Authoritative design:** [`SDD.md`](./SDD.md) (routes §13, layout §4) · **Commands and gates:** [`build.md`](./build.md) Part II · **Tracker:** [`checklist.md`](./checklist.md) · **Task split:** [`DELEGATION.md`](./DELEGATION.md)

> [!IMPORTANT]
> **Answer first: build all 13 stages (M→W) autonomously overnight, and commit + push to `origin main` after each passed gate.** Test before every commit. A gate that fails 3 times is marked BLOCKED, and the run continues with independent stages. Never fake a gate, never change the model, and never delete cloud resources. The user authorised this on 2026-10-07 at 19:52.

---

## 1. Locked decisions

| ID | Decision |
|---|---|
| D-1 | Cost = band `LOW`/`MED`/`HIGH` + rig-days; no ₹/USD, NPV, payback or ROI |
| D-2 / D-11 | Geleki 142 `GK-`, Lakwa 160 `LKW-` / 3 GGS, Lakhmani 110 `LKM-` / 2 GGS; 60 months, 2021-10-01…2026-09-30 |
| D-4 | Project `workover-operations-agentic-ai`; Cloud Run `us-central1`; BigQuery `asia-south1` |
| D-7 | Hero well GK-129 (squeeze vs. wax removal); backup LKM-061 |
| D-8 | Personas `ED`, `ASSET_MANAGER`, `FIELD_ENGINEER`, gated at the tool layer (`require()`) |
| D-12 / D-13 | ADK `Runner` in-process; text model `gemini-3.8-flash` on Vertex AI + ADC (no API key); Live model taken from the listing, never guessed |
| D-14 | `uv` + `pyproject.toml`; multi-stage Dockerfile |
| D-15 | `AS_OF` = 2026-09-23; data runs to 2026-09-30 |
| D-16 | Demo: in-memory sessions; Cloud Run max-instances=1 + session affinity. Later: Vertex AI sessions |
| D-17 | TF-IDF document search in v0.4; Vertex AI Search optional later |
| D-18 | Commit parquet + model artefacts if every file is < 50 MB, else git-ignore and regenerate in the Docker build; PDFs + index built in a Docker stage, uploaded to GCS in Stage X |
| D-19 | Add `wht_degc`, `gl_inj_rate_mscfd`, `gl_inj_pressure_kgcm2`, `pressure_surveys`, `formation_tops` (append-only) |
| D-20 | Legacy WS `/api/wells/{id}/live` and `/audio` shims kept until Gate V; removed in Stage V |
| Q-1 | Meeting date unknown: build everything; if time-boxed, cut Y first, then X |
| Q-2 | English-only dossier |
| Bucket | Existing `gs://workover-operations-agentic-ai-datalake` (`bronze/`, `documents/`, `silver_exports/`) |
| Ranking | Deferred bbl × p_success ÷ rig-days, shown with cost band (K-7) |
| Gate Q | Holdout macro-F1 0.70–0.92 (above 0.92 = leakage = fail) |
| Health | TC-020 buckets `PRODUCING_OK` / `AT_RISK` / `UNDERPERFORMING` / `NOT_PRODUCING` (SDD §6.3) |
| Scope | Live is audio-only (open-mic option; FE persona has voice); ESP replacement → IC-08 |
| frontend/dist | Untracked in Stage W |

## 2. Autonomy and git policy

- **Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources.** This covers BigQuery DDL apply (Stage X, after `--dry_run`) and the Cloud Run deploy of `wellpulse-app` (Stage W, after the local container test; smoke test after deploy).
- No questions to the user during the run; decisions not listed in §1 follow [`SDD.md`](./SDD.md) and are logged in the morning report.
- **Git:** after each passed gate only: `git add -A && git commit -m "v0.4(<stage>): <name> — Gate <stage> passed" && git push origin main`. Never commit with a red gate, `.env`, secrets or git-ignored baselines. Only the orchestrator runs git; Flash workers never do.

## 3. Delegation tiers (per [`DELEGATION.md`](./DELEGATION.md))

| Tier | Owns | Never does |
|---|---|---|
| **Orchestrator** (Pro/Opus-class) | Contracts, numbers, guardrails, ML gates, counterfactual, RBAC policy, reviews, gates, commits, cloud apply/deploy | Hand off numeric logic |
| **Stage lead** (orchestrator sub-agent, one per active stage) | Runs one stage end to end: briefs Flash workers with exact packets on disjoint files, runs the stage tests, reports the gate result | Commit, push or deploy |
| **Flash worker** | Templates and prose (fact slots, no digits), DDL / loaders / Dataform, Recharts and React scaffolds, Gherkin glue, eval JSON, checklist ticks | Type digits, run git, touch files outside its packet |

17 orchestrator tasks / 39 Flash tasks (56 total).

## 4. Milestones

Every milestone = stage tasks → stage test command green → gate items ticked in `checklist.md` → commit + push.

| MS | Stage | Gate | Test command (from `backend/` unless noted) | Commit message |
|---|---|---|---|---|
| MS-0 | Docs | Verbatim Gate 1: doc set v3.0.0 consistent | `grep` sweep in [`CONSISTENCY_REPORT.md`](./CONSISTENCY_REPORT.md) | `v0.4(docs): doc set v3.0.0 aligned` |
| MS-1 | M | Gate M | `uv sync --frozen && uv run pytest -q`; `cd ../frontend && npm run build` | `v0.4(M): preflight & baseline — Gate M passed` |
| MS-2 | N | Gate N | `uv run python -m app.analytics.generator.validate --field all` + `uv run pytest tests/test_api_shapes.py tests/unit/test_repository.py -q` | `v0.4(N): data foundation v2 — Gate N passed` |
| MS-3 | O | Gate O | `uv run python -m app.analytics.generator.docs_pdf.validate` + `uv run pytest tests/unit/test_docs_route.py -q` | `v0.4(O): PDF corpus + SOPs — Gate O passed` |
| MS-4 | P | Gate P | `uv run pytest tests/unit/test_tools_port.py tests/unit/test_tc019_attribution.py tests/unit/test_tc020_health.py tests/test_api_shapes.py -q` | `v0.4(P): analytics port + attribution + health — Gate P passed` |
| MS-5 | Q | Gate Q (macro-F1 0.70–0.92) | `uv run python -m app.analytics.model.train_classifier --as-of 2026-09-23` + `uv run pytest tests/unit/test_features_no_leakage.py tests/unit/test_tc021_classifier.py -q` | `v0.4(Q): ML classifier — Gate Q passed` |
| MS-6 | R | Gate R | `uv run pytest tests/unit/test_tc022_nba.py tests/unit/test_tc027_counterfactual.py tests/test_api_shapes.py -q` | `v0.4(R): NBA + counterfactual — Gate R passed` |
| MS-7 | S | Gate S | `uv run pytest tests/unit/test_tc023_dossier.py -q` + `curl -sf .../api/wells/GK-129/export?format=pdf` | `v0.4(S): dossier — Gate S passed` |
| MS-8 | T | Gate T | `uv run pytest tests/unit/test_tc024_fields.py tests/unit/test_tc025_hierarchy.py tests/unit/test_tc028_field_history.py tests/unit/test_tc029_well_profile.py -q`; `npm run build` | `v0.4(T): asset view & drill-down — Gate T passed` |
| MS-9 | X | Gate X | DDL `bq query --dry_run` clean → apply; `DATA_BACKEND=bigquery uv run pytest tests/integration/test_backend_parity.py -q` | `v0.4(X): medallion lakehouse — Gate X passed` |
| MS-10 | U | Gate U | `uv run pytest tests/integration/test_ws_live.py -q`; local voice check | `v0.4(U): real Gemini Live — Gate U passed` |
| MS-11 | Y | Gate Y | `uv run pytest tests/unit/test_rbac.py tests/bdd -k "rbac or gis" -q`; `npm run build` | `v0.4(Y): RBAC + multi-field GIS — Gate Y passed` |
| MS-12 | V | Gate V | `uv run pytest tests/ -q`; `agents-cli eval run` (≥ 30 cases, ≥ 90%); `cd ../frontend && npx playwright test` | `v0.4(V): agent wiring & eval — Gate V passed` |
| MS-13 | W | Gate W | local `docker run` + `curl /api/healthz`; deploy; `scripts/smoke.sh <url>` | `v0.4(W): deploy — Gate W passed` |

**Order:** N gates everything; O after N; P after N; Q after N; R after P + Q; S after O + R; T after P; X any time after N; U in parallel with P–T; Y before V; V after T, U and Y; W last.

## 5. Test-before-commit policy

1. Run the stage test command; then `uv run pytest -q` (full backend suite) and `npm run build`. All green.
2. Tick each gate item in `checklist.md` with evidence (command output or file path); no tick without evidence.
3. Commit + push only then. A red test means no commit.

## 6. Failure policy

- **3 attempts** per failing gate (fix → re-run). After the third failure: mark the stage **BLOCKED** in `checklist.md` with the failing check and the last error, do not commit that stage's broken state, and continue with stages that do not depend on it.
- **Never fake a gate:** do not loosen thresholds, skip tests, hard-code expected values or edit pinned values to pass.
- **Never change the model:** `gemini-3.8-flash` for text; the Live model comes only from the U.2 listing. If unavailable → BLOCKED.
- **Never delete cloud resources** (buckets, datasets, tables, services, revisions). Create or update only.

## 7. Morning report

One page, answer first:

1. **Status line:** stages passed / BLOCKED / not started, and the deployed URL + revision (if W passed).
2. **Gate table:** MS-0…MS-13 with result, commit SHA and the key metric (e.g. Gate Q macro-F1, eval accuracy, Live first-audio latency).
3. **BLOCKED items:** failing check, last error, three attempts tried, recommended next step.
4. **Cloud changes:** BigQuery datasets/tables created, GCS prefixes written, Cloud Run revision deployed.
5. **Decisions taken autonomously** (anything not in §1) and deviations from the docs.
6. **Ask:** the specific decisions the user needs to make next.
