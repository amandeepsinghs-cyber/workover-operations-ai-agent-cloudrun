# WellPulse v0.4 — Doc-set Consistency Report

**Version:** 3.0.0 · **Date:** 2026-10-07 · **Scope:** `docs/` (BRD, features, BDD, SDD, build, checklist, DELEGATION, EXECUTION_PLAN) + repo `README.md` · **Source:** [`verbatim.md`](../verbatim.md)

> [!IMPORTANT]
> **Answer first: the doc set is aligned and ready to drive the build.** All docs now share the same authority (SDD §13 for routes, §4 for layout), the same decisions (D-1…D-20, Q-1, Q-2, bucket, ranking, frontend/dist, autonomy) and the same gates. No blocking contradictions remain. Five minor residual issues are listed in §3; none of them blocks a stage.

---

## 1. Alignment rules applied everywhere

| Topic | Final value |
|---|---|
| Routes | [`SDD.md`](./SDD.md) §13 authoritative: `WS /ws/live`, `/api/fields/{field}/priority`, `/api/wells/{id}/compare?recommended=&alternative=`, `/api/wells/{id}/production`, `/api/fields/{field}/health?cluster_id=`, `/api/fields/{field}/attribution?window_days=`, export JSON + `?format=pdf`, `POST /api/wells/{id}/dossier`, `/api/docs/{doc_id}.pdf`, `/api/healthz` |
| Approvals | Every "⛔ requires explicit approval / Stop. Get approval" → **Authorised by user (2026-10-07) — dry-run / local-test first, then apply; never delete existing resources** |
| Git | Commit + push to `origin main` after every passed gate; test first |
| Gate Q | Holdout macro-F1 0.70–0.92 |
| Health | TC-020 `PRODUCING_OK` / `AT_RISK` / `UNDERPERFORMING` / `NOT_PRODUCING` (SDD §6.3) |
| Personas | `ED`, `ASSET_MANAGER`, `FIELD_ENGINEER` (Production Engineer → `ASSET_MANAGER`) |
| Model / project | `gemini-3.8-flash` on Vertex ADC; `workover-operations-agentic-ai` |
| Stage letters | M, N, O, P, Q, R, S, T, X, U, Y, V, W |
| Verbatim gaps | `wht_degc` / GOR / gas-lift rate + pressure (data → API → TelemetryCharts → Gates N, T); lithology via `formation_tops`; audio-only Live; ESP → IC-08; ranking deferred bbl × p_success ÷ rig-days + cost band; Vertex AI Search optional; `pressure_surveys` in counterfactual row 1; `active_interventions` in TC-024; open-mic option; FE persona has Live voice |
| Links | `verbatim.md` lives at the repo root → `../verbatim.md` from `docs/` |

## 2. Changes per document

| Doc | Changes |
|---|---|
| **SDD.md** (orchestrator) | Status + EXECUTION_PLAN link; §1.2 out-of-scope (audio-only, Q-2, D-17); §4 frontend/dist → W; §5.4 D-19; §5.8 history fields; §8.1 explicit IC-01…IC-15 table + ESP → IC-08; §9.1 ranking; §10.2 bucket / D-18; §10.3 Q-2; §11.4–11.5 shims until V, FE voice, audio-only; §12.2 sessions; §13.2/13.4 routes and renamed-route list; §14.3 TelemetryCharts series; §15.1 bucket; §17.1–17.3 D-18, AS_OF, bucket; R-2 BLOCKED policy; §19.2 D-15…D-20, Q-1, Q-2 resolved, **D-21 bucket, D-22 ranking, D-23 frontend/dist, D-24 autonomy added**; §20 six new traceability rows |
| **BDD.md** | 22 route/value edits (Flash, reviewed): `/ws/live`, final route paragraph, as_of 2026-09-23, «1819 ± 0» points, gas mscf/d, Contractor → Equipment, status "degraded", export JSON → `?format=pdf`, attribution `window_days`, health `cluster_id`, `deferred_bbl_12mo`, history `fields=&freq=M`, L1 artifact. Added F03-S06 (ESP → IC-08), F07-S08 (open-mic, audio-only), F12-S05 (WHT / GOR / GL series), F13-S05 (`pressure_surveys`); lithology and ranking lines; counts → **104 scenarios** |
| **features.md** | Header links; §2 summary (BDD ranges, SDD component names, routes); F-01 AttributionWaterfall; F-02 buckets per SDD §6.3; F-03 ESP → IC-08 explicit, Gate Q band; F-04 routes `/api/fields/{field}/priority` + `/api/wells/{id}/nba`, G-3 wording, ranking formula; F-05 `/api/fields`; F-06 dossier POST, `formation_tops`, English-only, S01…S05; F-07 `session.py`, `/ws/live`, 12-tool subset, open-mic, FE voice, S01…S08, gap resolved; F-08 D-19 tables/columns, S01…S06; F-09 FieldComparisonTable, `active_interventions`, S01…S05; F-10 `{doc_id}`; F-12 production route, components, S01…S05; F-13 `/compare`, CounterfactualTable, `pressure_surveys`, S01…S05; F-15 bucket, TF-IDF (D-17); F-16/F-17/F-18 scenario ranges, PersonaPicker, L3 ranking; X-7/X-8 autonomy text; C-11; §6 out-of-scope; §7 adds D-15…D-20, Q-1, Q-2, bucket, ranking, frontend/dist, autonomy |
| **build.md** (Part II) | Drives line (SDD authority, EXECUTION_PLAN, `../verbatim.md`); rule 3 → authorised text + BLOCKED policy; fixed parameters + AS_OF, bucket, doc search, sessions; env exports; stage map W; target layout → pointer to SDD §4 with key paths; N.1/N.3 D-19; V-N7; `generator/docs_pdf`; TF-IDF index; Gate P LKW-088 `EXTERNAL`; `analytics/config/factor_map.yaml`; classifier artefact names; Gate Q band; Gate R ranking + `pressure_surveys`; Stage S export/dossier; Stage T files, routes, Gate T WHT/GOR/GL + `active_interventions`; Stage X bucket, dry-run → apply, `doc_chunks`, SDD §15.2; Stage U `session.py`, `/ws/live`, shims (D-20), env `TEXT_MODEL`/`LIVE_MODEL`/`LIVE_LOCATION`, BLOCKED not "ask", open-mic; Stage Y no `rbac.yaml`, `common/PersonaPicker`; Stage V ≥ 30 cases `wellpulse-eval.json`, shim removal; Stage W authorised, SDD §17.1 Dockerfile (selfcheck + uvicorn), dist untracked, env + AS_OF, `/api/healthz`, `scripts/smoke.sh`; DoD; open items → resolved |
| **checklist.md** | Same changes as build.md, task/gate level. **All 60 existing `[x]` ticks preserved** (count verified before and after; edits never touched ticked lines). Status line → "in progress"; autonomy + BLOCKED rule in header |
| **BRD.md** | Status; `../verbatim.md`; companion links; audio-only + open-mic + FE voice; D-19 telemetry names; Contractor → Equipment; L3 ranking formula; dossier English-only + TF-IDF; bucket + Vertex AI Search optional; SM-06 → macro-F1 0.70–0.92; C-06 → authorised text |
| **DELEGATION.md** | 34 edits (Flash, reviewed): `../verbatim.md`; D1–D11 per SDD §10.1; V-N7; D-1…D-20; SDD-aligned paths; F-P3 → **O-P3**; commit after green gate; autonomy text. §10 summary fixed by orchestrator: P = 3 O / 0 F; totals **17 O / 39 F / 56** (30.4% / 69.6%) |
| **EXECUTION_PLAN.md** | New: locked decisions, autonomy + git, delegation tiers, MS-0…MS-13 with gate / test command / commit message, test-before-commit, failure policy, morning report |
| **README.md** | New "Documentation" index linking all docs + `verbatim.md` |

**Delegation record:** two Flash workers ran exact-packet edits on disjoint files — BDD.md (22 edits, all DONE) and DELEGATION.md (34 edits, all DONE). The orchestrator verified both by grep. All other edits were made by the orchestrator using exact-string replacement scripts; every replacement matched.

**Final sweep (clean):** no remaining `./verbatim.md` links from `docs/`, `WS /api/live`, `/api/priority`, `/api/wells/priority`, `counterfactual?`, `⛔`, approval gates, `**Open**`, `wellhead_temp_c`, `live_session.py` (except DI 2.0 source references), `ETTF`, `≥ 20 cases`, `FactorWaterfall`, `EvidenceTable`, `format=md`, `WELLPULSE_*` env names or `ic_classifier_*`. The remaining `/api/wells/{id}/live` mentions are the deliberate D-20 legacy shim.

## 3. Residual issues (not fixed; none blocking)

| # | Severity | Issue | Recommendation |
|---|---|---|---|
| R-1 | Important | Language default: features X-6 / BRD C-04 say **Hinglish default**; SDD `ChatRequest.language` defaults to `"english"` | Make SDD default `"hinglish"` (matches baseline UI) in Stage V |
| R-2 | Cosmetic | BDD B-02 shows THP/CHP in "ksc", while the baseline adapter emits psi | Pin units with the adapter in Stage N (pinned_values.md) |
| R-3 | Cosmetic | BDD B-07 tab names (WCR/DWR/BHP/Chemistry) vs. SDD renamed document-driven tabs | Accept either; Stage O WellReportsTab maps tabs to D1/D3/D7/D6 |
| R-4 | Cosmetic | DELEGATION F-S1 output `analytics/tools/dossier_render.py` is not in the SDD §4 tree | Fold into `dossier.py` or add to SDD §4 when Stage S starts |
| R-5 | Note | IDs D-21 (bucket), D-22 (ranking), D-23 (frontend/dist), D-24 (autonomy) were newly assigned in SDD §19.2; other docs refer to these by name, not ID | No action needed |
| R-6 | Note | Pinned values (Lakwa gap, BDD «target ± tol») remain placeholders until Stage N.5 by design | Replace at Gate N |
