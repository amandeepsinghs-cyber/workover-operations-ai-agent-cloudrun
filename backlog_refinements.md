# Urvi AI Agent · WellPulse — Backlog & Refinements

**This is the reference sheet for the latest changes.** Read it first. It has two working lists: **Current refinements** (changes to what exists today) and **Feature backlog** (new capability, scoped later). Every item gets full clarity with the user before anything is built. The detailed build tracking stays in [`docs/checklist.md`](./docs/checklist.md).

**Current release:** V 1.1, live at https://wellpulse-app-806277846965.us-central1.run.app (`wellpulse-app-00009-kt4`, image `v1-1-c242a4e`; rollback: `wellpulse-app-00008-g49`)  
**Local dev:** `./run_local.sh` → app http://localhost:5180 · API http://localhost:8002/docs  
**Last updated:** 2026-11-15

> [!IMPORTANT]
> **Answer first:** V 1.0 is functionally complete and tests are green (718 passed, 0 failed). **Clarity phase: nothing is being built.** The user will give requirements one by one, and each goes into Current refinements or Feature backlog.

---

## 1. Latest changes (newest first)

| Date | Change | Files | Commit |
|---|---|---|---|
| 2026-11-15 | BL-9 moved to the separate Cairn replica repo (`urvi-cairn-barmer`); this ONGC repo and its deployment are not changed by Cairn work. | `backlog_refinements.md` | not committed |
| 2026-11-15 | **Pushed and deployed V 1.1** (user: *"push and deploy"*). Commits `eb7c249` (BL-12), `3996384` (R-6), `ca371e5` (BL-8 / BL-10 architecture), `c242a4e` (docs) on origin/main. Cloud Build `829e1c17` → image `v1-1-c242a4e` → revision `wellpulse-app-00009-kt4` serving 100%. Smoke 6/6; architecture pages and Explain JSON served; GK-101 / GK-012 recommendations work on the live URL (LKW-052 returns UNAVAILABLE by design, no crash). Rollback target `wellpulse-app-00008-g49`. | `APP_LINK.md`, `backlog_refinements.md` | this commit |
| 2026-11-15 | **Architecture: every box now has an icon** (user: *"a lot of logos are missing"* → *"use actual icons for actual systems like SAP"*). Real marks where the box is that product: **SAP, AVEVA PI (SCADA + OSI PI), Esri, Leaflet, OSDU (EDP on-prem)**; generic single-colour glyphs for our own code (API, Live proxy, analytics, data access / EDP adapter, document search, field report, sessions, generator), ONGC-internal systems (DPR, WIS / EDS, LIMS, DISHA) and people (users, SSO, voice client, UI, hands-off, canvas); Google products keep official icons. Wide wordmark tiles; compact layout for the narrow left-column boxes; a few labels shortened to fit. | `frontend/scripts/build_architecture.py`, `frontend/scripts/architecture_icons/*`, `frontend/public/architecture/*.html` | not committed |
| 2026-11-15 | **Created `docs/ml_recommendation_engine.md`** (user: *"explicitly write a document that explains the ML and recommendation engine, the present and the future production system"*): inventory of all 17 components (2 trained models, 4 statistical methods, 8 physics rule sets, uplift, effort, ranking); training procedure (classifier, CoxPH, look-alike index); inference step by step with the GK-129 worked example; validation incl. unseen-field test; production design (labels, models M1–M3 + multimodal network spec, rig-queue optimiser, Vertex AI pipeline, nightly serving, decision workflow, governance, monitoring); phased path; appendices (features, job classes, thresholds, files). `docs/recommendation_engine.md` now points to it. | `docs/ml_recommendation_engine.md`, `docs/recommendation_engine.md`, `README.md`, `frontend/scripts/*` | not committed |
| 2026-11-15 | **Architecture "Explain" button + `docs/how_urvi_works.md`** (user: *"can it be added as commentary in the architecture? as a button that gives explanation"*). The Architecture tab gets an **Explain** button that opens a side panel with plain-English commentary for the view shown (Current or Target): the three ways a request is handled, step-by-step ①–⑦ / Ⓐ–Ⓒ / D1–D4 matching the diagram badges, "is it multi-agent?" (no: one agent, 34 chat tools, 13 voice tools), recommendations, data / build / identity, glossary. The same text is generated into `docs/how_urvi_works.md` from one source file. | `frontend/scripts/architecture_explain.py`, `frontend/scripts/build_architecture.py`, `frontend/public/architecture/explain-*.json`, `frontend/src/components/architecture/{ArchitectureView,ExplainPanel}.tsx`, `docs/how_urvi_works.md` | not committed |
| 2026-11-15 | **BL-12 fixed:** `nba._pressure` now computes PI / SBHP change only when both surveys have the value (a missing latest PI no longer raises `TypeError`); those wells show "PI trend unknown" (stimulation / re-perforation marked UNCLEAR). New regression test runs a recommendation for all 412 wells: 4 passed. | `backend/app/analytics/tools/nba.py`, `backend/tests/unit/test_bl12_all_wells.py` | not committed |
| 2026-11-15 | **Architecture diagrams: clarity + standards pass** (user: *"do all the changes that provide clarity and consistency"*). Users stay on the left (left-to-right is the convention). Added numbered main path ①–⑦, voice path Ⓐ–Ⓒ, data path D1–D4 (target), a reading guide under each title; secondary flows thin and muted. Switched to **official Google Cloud icons** (go/cloud-icons H1 2026: unique icons for BigQuery, Cloud Run, Cloud Storage, Apigee, Vertex AI; category icons for everything else; Gemini spark) stored in `frontend/scripts/architecture_icons/`; **removed third-party logos** (React, FastAPI, Python, Leaflet). Consistent names across Current and Target (Gemini 3.8 Flash / Live, Urvi API). Added **light Google Cloud style versions** (`current-light.html`, `target-light.html`) + "Light version" button in the Architecture tab. | `frontend/scripts/build_architecture.py`, `frontend/scripts/architecture_icons/*`, `frontend/public/architecture/*.html`, `ArchitectureView.tsx` | not committed |
| 2026-11-15 | **Created `docs/recommendation_engine.md`**: how recommendations are trained and inferred today (worked example GK-129 with real engine numbers), the production design (data, labels, Vertex AI training pipeline, models M1–M3, nightly scoring, ranking, decision workflow, validation, monitoring). Logged BL-11 (production engine) and BL-12 (crash on 31 wells). | `docs/recommendation_engine.md`, `backlog_refinements.md` | not committed |
| 2026-11-15 | **Removed the on-prem AI option** (user: *"there is no on prem option for running the models, that is a GDC conversation. The cloud is used for running AI"*). Matches RFP §3.1.2(d) / §3.1.3 (AI/ML in the cloud). Removed Route C (on-prem / GDC) and Route D (PSU wrapper) from the plan and the Target diagram; Category A raw data stays in the EDP on-prem zone, Urvi stays in the India cloud. | `docs/data_access_plan.md`, `frontend/scripts/build_architecture.py`, `frontend/public/architecture/target.html` | not committed |
| 2026-11-15 | **Target architecture redrawn for ONGC production in India regions** (user: *"in the actual deployment we will use India regions"*): ONGC sources (DPR, SCADA + PI, WIS / EDS, SAP, LIMS, DISHA) → EDP on-prem + cloud zone → Consumption API → Urvi EDP adapter; Urvi + Gemini on India endpoints; IAP + ONGC SSO; KMS / Access Approval / Secret Manager / Logging in India; Routes B / P. Demo stays in us-central1 (Gemini Live not yet in India). `data_access_plan.md` §8 reworded. | `frontend/scripts/build_architecture.py`, `frontend/public/architecture/target.html`, `docs/data_access_plan.md` | not committed |
| 2026-11-15 | **Created `docs/data_access_plan.md`** (draft): where Urvi's data comes from, how it is fetched (via the ONGC EDP, RFP ZV7AL26011, whose Annex H 1.5 "Well Health & Opportunity" use case is Urvi), residency routes A / B / P aligned to RFP §3.2.6, the MeitY OM and CERT-In, controls, phased plan and gaps (Cloud Run + Gemini must move to India regions for real data). | `docs/data_access_plan.md` | not committed |
| 2026-11-15 | **Built locally (awaiting user test): BL-8 Architecture tab + R-6 English default.** BL-8: two diagrams (Current V 1.0 / Target) generated by `frontend/scripts/build_architecture.py` (architecture-diagram skill style, official Google Cloud icons `@iconify-json/gcp` 1.2.3 + brand logos, CSS hover tooltips on every component, no ONGC logo); **Architecture** button in the header; tab with Current ↔ Target toggle, "New tab" link, Esc to close; `ui_control architecture open|current|target|close` for chat + voice, plus browser phrases EN / Hinglish / Hindi. R-6: English default in settings, voice panel, Live fallback and both prompts; switching rule added. Tests added. | `frontend/scripts/build_architecture.py`, `frontend/public/architecture/{current,target}.html`, `frontend/src/components/architecture/ArchitectureView.tsx`, `App.tsx`, `Header.tsx`, `agent/uiCommands.ts`, `VoiceAgentPanel.tsx`, `backend/app/{settings.py, agent/ui_control.py, agent/adk_tools_ext.py, agent/prompt.py, live/live_prompt.md, live/voice_tools.py, live/fallback.py, api/wells.py}`, tests `test_r6_language_default.py`, `test_ed11_ui_control.py`, `test_ed11_ui_parser.py` | not committed |
| 2026-11-15 | Captured R-6 (English default; switch only on request) | `backlog_refinements.md` | not committed |
| 2026-11-15 | BL-8 fully scoped (export later); BL-9: one app, Barmer auto-focus, no client switch; R-1 lowered (demo focus is the field) | `backlog_refinements.md` | not committed |
| 2026-11-15 | BL-9: recorded answers Q3–Q6, the Argon + Flash delegation requirement and 4 pre-build deliverables | `backlog_refinements.md` | not committed |
| 2026-11-15 | Captured R-5 (no ONGC logo in the interface; report keeps it) and BL-9 (Barmer Basin for Vedanta Oil and Gas / Cairn); closed BL-8 Q10 | `backlog_refinements.md` | not committed |
| 2026-11-15 | BL-8: recorded Q6–Q10 answers and a draft definition of done | `backlog_refinements.md` | not committed |
| 2026-11-15 | BL-8: recorded answers to Q1–Q5; added Q6–Q11 | `backlog_refinements.md` | not committed |
| 2026-11-15 | Captured BL-8 (architecture diagram for the demo) | `backlog_refinements.md` | not committed |
| 2026-11-15 | Created this reference sheet; the backlog moved here from the checklist | `backlog_refinements.md`, `docs/checklist.md`, `README.md` | not committed |
| 2026-11-15 | Checklist reconciled with code and git: gate commits ticked; T-F2/F3, DF, NN, FR, ED and W2 marked done where verified; persona switch reopened as Stage RB; D-43 added | `docs/checklist.md` | not committed |
| 2026-11-15 | Fresh baseline: backend pytest 718 passed / 24 skipped / 0 failed; `tsc --noEmit` green. Skips: 23 BigQuery parity tests (local ADC expired), 1 opt-in live-LLM test | — | — |
| 2026-10-09 | V 1.0: ONGC logo source asset; ignore local fake-run eval outputs | — | `ae14698` |
| 2026-10-08 | V 1.0: Urvi AI Agent (name, U mark, personality, Aoede voice); greetings never drive the screen; green mic states | — | `4b8463d`, `eaa669d` |
| 2026-10-08 | v0.6 ED pack: showcase mode, completion diagram, offset decline, anomalies, wax/sand, India map, hands-off `ui_control`, health filter | — | `2037bc5`, `93faff4`, `229116e` |

---

## 2. Current refinements

| ID | Date | Feedback (user's words) | Status | Next step |
|---|---|---|---|---|
| **R-1** | 2026-11-15 | *"I see that the persona drop down menu doesn't work. I wanted hierarchy based access as in CMD and Director will have access to all the PII but the junior employees E1 to E4 should not have all the access. This should be demonstrable when E3 officer will ask to generate a named list of employees in Delhi for more than 5 years, it will not generate while if CMD will ask it will."* | **Open, lower priority** (user, 2026-11-15: *"main demo is not of hierarchy but of the field"*) | Revisit after BL-8 and BL-9 |
| R-2 | 2026-11-15 | *"Voice capability works very well so no need to verify."* | Closed (accepted) | Gate U voice items ticked as user-accepted |
| R-3 | 2026-11-15 | *"Reconnecting loses context, that is a feature not a bug. I want every demo to start fresh."* | Closed (D-43) | "Reconnect keeps context" removed from all gates |
| R-4 | 2026-11-15 | Scale-out (single Cloud Run instance): *"hold this and put this in the backlog as I do not understand the scope of it completely"* | Moved to backlog (BL-1) | — |
| **R-5** | 2026-11-15 | *"We do not need any ONGC logos in Urvi."* Clarified: *"no ONGC logos in the interface; in the report it is fine. When I am presenting Geleki, Lakwa, Lakhmani it will be presented to ONGC."* | **Captured, no build** | Rule: **no ONGC logo anywhere in the Urvi interface** (header, map, panels, agent, Architecture tab). **ONGC branding stays in the printable field report** for ONGC fields. Code check 2026-11-15: the ONGC logo is used only by the field report (`field_report.py`, shown via `FieldReportOverlay.tsx`); no logo image found in the interface. The ONGC *name* still appears as text on the India map ("13 ONGC assets"); does that text stay? (Q-R5) |
| **R-6** | 2026-11-15 | *"When I talk to the app it first responds in Hindi. I think the default should be English and only if the user switches to Hindi or Hinglish it should make that switch."* | **Deployed in V 1.1; awaiting user test** | Requirement: **English by default** (chat and voice, including the first greeting). Switch to Hindi or Hinglish only when the user asks or starts speaking it. Cause found 2026-11-15: the default is Hinglish in three places: `backend/app/settings.py` (`DEFAULT_LANGUAGE="hinglish"`, an earlier decision), `frontend/.../VoiceAgentPanel.tsx` (`useState('hinglish')`), and the greeting examples in `prompt.py` / `live_prompt.md` are Hinglish-first ("Namaste! Main Urvi AI Agent hoon…"). Small fix. |

### R-1 analysis
**Why the dropdown does nothing:**
1. Showcase mode (D-33, `WELLPULSE_RBAC_ENFORCE=0`) gives every persona FULL access (`backend/app/agent/rbac.py`).
2. `frontend/src/api/decision.ts` hard-codes `X-Persona: ASSET_MANAGER` on two calls.

**Gap against the request:** Urvi's personas are ED / Asset Manager / Field Engineer. It has no CMD / Director / E1–E4 ladder and **no employee or PII data**. The E3-vs-CMD "named employees in Delhi > 5 years" demo matches **Yukti** (`../HR and Finance_ONGC`), which already enforces that ladder.

**Possible directions (for discussion only, nothing chosen):**
- **(a)** Add a CMD / Director / E1–E4 ladder plus a synthetic employee roster to Urvi. CMD and Directors see names and PII; E1–E4 are refused or get aggregates only. The same rules apply in chat, voice and the UI.
- **(b)** Keep the HR demo in Yukti. Urvi only gets the dropdown fix (enforce RBAC, remove the hard-coded persona) so each role visibly sees different well data.

---

## 3. Feature backlog

Each item is scoped with the user before it moves into a checklist stage.

| ID | Item | Status | Notes |
|---|---|---|---|
| BL-1 | Cloud Run scale-out | **On hold** (user: scope unclear) | Today min = max = 1 instance with session affinity, because ADK / Live sessions are kept in memory (D-16). More than one instance needs an external session store. Not needed for single-presenter demos. |
| BL-2 | CMD persona features F-34…F-40 | Logged (v0.6) | Asset comparisons, field-wise production per asset, asset DPR, where it hurts, sand rate (no data), service cost (deferred, D-35), new locations (no data) |
| BL-3 | Playwright E2E click-through (V-F3) | Open | `frontend/tests/e2e` does not exist |
| BL-4 | Vertex eval re-run incl. `canvas_routing_v05.json` (DF-O3) | Open | Last Vertex run 2026-10-07 (pre-v0.5) |
| BL-5 | Hardening: `deploy/selfcheck.py` v0.5 assets + `/report` smoke check (W2-O1) | Open | Not a blocker; the image builds and runs |
| BL-6 | NN plausibility review GK-129 / LKW-019 / LKM-061 (NN-O6) | Open | Engineering-soundness read-through |
| BL-7 | Chat brevity (AC-F1) | Open | Text prompt allows 2–4 sentences, Live 1–3; D-25 says ≤ 3; no automated check |
| **BL-8** | **Architecture tab in Urvi (current + target architecture)** | **Deployed in V 1.1; awaiting user test** | User's words: *"I would like to ultimately have an updated architecture diagram which I would like to add in the demo. The architecture should have the tools and services used, the flow, and should use the architecture skill. It should also use the relevant logos."* Agreed so far: `architecture-diagram` skill + official GCP icons; visible Architecture button → Architecture tab; Current V 1.0 ↔ Target toggle; full technical architecture; HTML + inline SVG; hover explanations; Urvi opens it by chat or voice. No ONGC logo (R-5). Export decided later. **Fully scoped; first in sequence.** Answers and open questions are in §3.1. |
| **BL-10** | **Show data sources and residency in the Target architecture** | **Deployed in V 1.1; awaiting user test** | User's words: *"in the target architecture I do not see any mention of where will the data come from? how will we fetch the data? can we build a document around that first?"* Document done: [`docs/data_access_plan.md`](./docs/data_access_plan.md). Next (after the user reviews the plan): add ONGC sources → EDP → Urvi, India regions, CMEK / VPC-SC and the on-prem option (Route C) to the Target diagram. |
| **BL-11** | **Production recommendation engine (trained success + uplift models, Vertex AI pipeline, decision loop)** | Captured 2026-11-15: design in [`docs/ml_recommendation_engine.md`](./docs/ml_recommendation_engine.md) §7–12 | User asked for clarity on training, inference and decisions. Depends on ONGC data (Part D questions). |
| **BL-12** | **Defect: recommendation crashes for 31 of 412 wells** | **Fixed and deployed 2026-11-15 (V 1.1)** | `nba._pressure` divides by a missing PI value (`TypeError`). Affected: 16 Geleki, 14 Lakwa, 1 Lakhmani (e.g. GK-012, GK-101, LKW-052). Fix: skip the PI-change calculation when PI is missing, add a regression test over all wells. **Demo risk:** asking Urvi about one of these wells fails. |
| **BL-9** | **Extend Urvi to the Barmer Basin (Rajasthan) for Vedanta Oil and Gas (Cairn)** | **Moved to separate repo 2026-11-15** | Decision change (user, 2026-11-15): build Cairn in a **separate replica repo** `urvi-cairn-barmer` (folder `cloud_run_apps/urvi_cairn_barmer`), not in this ONGC app; replaces Q1 'one app, no client switch'. Rationale: zero risk to the ONGC CMD demo. All Barmer work and its backlog live there. |

### 3.1 Open questions

**BL-8 architecture diagram: answers so far (user, 2026-11-15)**

| Q | Question | User's answer | Resulting requirement |
|---|---|---|---|
| Q1 | Which skill? | *"Find the best skill to generate the architecture. It should be professional looking and clear with official logos."* | Proposed: **`architecture-diagram`** skill (standalone HTML + inline SVG, dark theme that matches Urvi's UI), with **official Google Cloud product icons** embedded as SVG. Fallback: `mermaid-designer` (2,718-icon catalog incl. GCP, auto-layout, PNG render). **Pending user OK.** |
| Q2 | Where in the demo? | *"In the Urvi app with a tab for architecture."* | A dedicated **Architecture tab** inside the Urvi app |
| Q3 | Depth? | *"It needs to be a proper architecture."* | Full technical architecture, not a marketing picture: every service, tool and data flow |
| Q4 | Current or target? | *"I think we should have both no?"* | **Two views:** (1) **Current V 1.0** as built and (2) **Target / production** (e.g. Vertex AI training + Model Registry, Vertex AI Search, external session store) |
| Q5 | Format? | *"I do not know which one is the industry standard? I feel html files were pretty good."* | **HTML + inline SVG** (crisp at any size, works inside the app tab, stays editable). Industry practice for Google Cloud is diagrams drawn with the official Google Cloud icon set; SVG/HTML is the right container for an in-app view. PNG export for slides can be added if needed. |

**Follow-up answers (user, 2026-11-15)**

| Q | Question | User's answer | Resulting requirement |
|---|---|---|---|
| Q6 | Skill choice | *"yes"* | **Agreed:** `architecture-diagram` skill + official Google Cloud product icons |
| Q7 | Toggle or side by side | *"yes, there should also be a button for architecture otherwise no one would know that you can also see the architecture"* | One tab with a **Current V 1.0 ↔ Target toggle**, plus a **visible Architecture button** in the main UI so viewers can find it |
| Q8 | Open by voice / chat | *"yes"* | Urvi opens the Architecture tab on request (chat and voice, EN / Hinglish / Hindi), e.g. *"show me the architecture"* |
| Q9 | Interactive | *"yes, hover over component that has a bit of explanation and context would be good"* | **Hover tooltip** on every component: what it is and why it is used in Urvi |
| Q10 | Extra logos | *"no ONGC logos"*, clarified: none in the interface (R-5) | **Closed:** no ONGC logo on the Architecture tab; Google Cloud icons only |
| Q11 | PNG / slide export | not answered yet | Open |

**BL-8 Q11 closed (user):** *"Something that can be decided later, we should generate one first."* → Build the in-app diagram first; decide on export later. **BL-8 is fully scoped.**

**BL-8 draft definition of done (to confirm once Q10 and Q11 are closed):**
1. A visible **Architecture** button in the Urvi UI opens an Architecture tab.
2. The tab has a **Current V 1.0 / Target** toggle; both views are full technical architectures (services, tools, data flow).
3. Built with the `architecture-diagram` skill as HTML + inline SVG, using official Google Cloud icons; professional and clear.
4. Hovering any component shows a short explanation and its context in Urvi.
5. Urvi opens the tab when asked in chat or voice (EN / Hinglish / Hindi).
6. No ONGC logo (R-5). Export decided after the first version.

**BL-8 update:** Q10 closed: no ONGC logo on the Architecture tab (follows R-5). Only Q11 (PNG export) remains open.

**R-5 open question**
- Q-R5: The India map says "13 ONGC assets" and the agent introduces itself as "for ONGC Assam Asset". Is ONGC **text** fine in the ONGC demo (only the logo is removed), or should it be neutral too?

**BL-9 Barmer / Vedanta Oil and Gas: open questions**
- Q1: **One app or two?** One Urvi with a client switch (ONGC: Assam fields; Vedanta: Barmer), or a separate Barmer deployment presented only to Vedanta? (Each client must never see the other's name or data in a demo.)
- Q2: **Which fields?** Mangala, Bhagyam, Aishwariya (MBA), and others such as Raageshwari gas or the satellite fields? Rough well counts?
- Q3: **Data:** synthetic like Assam (generated, calibrated to public facts)? Barmer differs from Assam: waxy crude, polymer / ASP EOR flooding, ESP / jet-pump lift, many more wells.
- Q4: **Report branding** for Barmer: a Vedanta / Cairn logo on the field report (like ONGC on the Assam reports)? Do we have an approved logo?
- Q5: **Personas** for Vedanta (their roles differ from ONGC's CMD / ED / E1–E4)?
- Q6: **Timeline / priority:** before or after BL-8 and R-1?

**BL-9 answers (user, 2026-11-15)**

| Q | Question | User's answer | Resulting requirement |
|---|---|---|---|
| Q1 | One app or two | *"We do not need a client switch. If we ask the app to focus on Barmer Aishwariya / Mangala fields it should automatically switch. At the end of the day we are just doing a demo… all the data is synthetic anyway."* | **One Urvi app, no client switch.** Asking about Barmer fields (e.g. Mangala, Aishwariya) moves the app to Barmer automatically, the same way asking about Geleki moves it to Assam |
| Q2 | Which fields / well counts | Fields named so far: Mangala, Aishwariya | Settle the full field list and well counts in the data strategy (deliverable 1) |
| Q3 | Synthetic data | *"Yes, we need a separate strategy on how to go about it."* | Synthetic data, but first a **separate Barmer data-generation strategy document** (fields, physics, lift, EOR, wax, well counts, calibration to public facts) |
| Q4 | Report branding | *"Yes Vedanta/Cairn, we have to check how they do it."* | Barmer field reports carry Vedanta / Cairn branding. **Research task:** how Vedanta Oil and Gas / Cairn brand their reports and documents (logo, name, layout) |
| Q5 | Personas | *"E1–E4 I feel are not needed. We can just check what they call; the data can be taken from their job openings and the leadership role names."* | No E1–E4 grades for Vedanta. **Research task:** derive Vedanta Oil and Gas role names from public job openings and leadership titles, then map them to access levels |
| Q6 | Priority | *"After the architecture; we should capture that in the backlog."* | **Sequence: BL-8 Architecture first, then BL-9 Barmer** |
| — | Delegation | *"I would like to do the data generation by Argon and Gemini Flash models; a clear delegation is also needed."* | **Data generation by Argon + Gemini Flash** workers, governed by a **clear delegation plan** (who does what, gates, review by the orchestrator), following the existing pattern in `docs/DELEGATION.md` (D-31: Argon = data generation and consistency tests, Flash = prose / templates) |

**BL-9 planned deliverables before any build (clarity phase):**
1. Barmer data-generation strategy (Q3)
2. Research note: Vedanta / Cairn report branding (Q4)
3. Research note: Vedanta Oil and Gas role names → access levels (Q5)
4. Delegation plan for Argon + Gemini Flash data generation

**BL-9 Q7 closed (user):** *"This is irrelevant… main demo is not of hierarchy but of the field."* → The demo focus is the **field**, not role hierarchy. R-1 is lower priority.

**BL-9 status:** scope is clear enough for the 4 pre-build deliverables. Field list and well counts go into the data strategy.

---

## 4. Decisions since V 1.0

| ID | Decision | Date | Detail |
|---|---|---|---|
| D-43 | Every demo starts fresh | 2026-11-15 (user) | A Live reconnect does not restore context, by design. Voice quality accepted without measurement. |

---

## How to update this sheet
- Every change: add a row at the top of §1 (date, change, files, commit hash once committed).
- New user feedback: add an R-n row in §2 with the user's exact words.
- Deferred or unclear scope: add a BL-n row in §3.
- Keep [`docs/checklist.md`](./docs/checklist.md) in sync when an item becomes a stage task.
