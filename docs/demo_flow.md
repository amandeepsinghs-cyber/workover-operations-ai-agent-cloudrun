# WellPulse v0.5 Demo Script — Lakwa to LKW-019 (11 Steps)

**Stage:** DF (Demo Flow & Evaluation) · **Feature:** F-26 · **Anchor:** Brief §6, BDD-F26-S01/S02, F-20, F-21 · **Status:** Authoritative Demo Flow

> [!IMPORTANT]
> **Demo Rule:** The chat interface never outputs a multi-section well history dump. Every agent response is strictly **≤ 3 sentences** (plus an optional collapsed card). All numbers, rates, depths, and dates are dynamically populated by backend tools (`value from tool`). The middle panel serves as the active answer canvas, updating synchronously with each query.

---

## Executive Overview & Presenter Flow

This 11-step demonstration guides an executive (Executive Director / Asset Manager) from field-level performance comparison down to a specific sick well in Lakwa (**LKW-019**), diagnosing its decline root causes, evaluating top-3 AI recommendations, defending against alternative counterfactual interventions, and handing off a field execution package.

```
[Step 1: Field Compare] ──▶ [Step 2: Sick Wells] ──▶ [Step 3: Priority List]
                                                              │
                                                              ▼
[Step 6: Interventions] ◀── [Step 5: Production] ◀── [Step 4: LKW-019 Overview]
       │
       ▼
[Step 7: Wellbore] ──▶ [Step 8: Diagnosis] ──▶ [Step 9: Recommendation Top 3]
                                                         │
                                                         ▼
[Step 11: Field Report Link] ◀── [Step 10: Why Not Sand Cleanout?]
```

---

## 11-Step Demo Script Matrix

| Step | Objective | Exact Typed Phrase | Voice Variant | Expected Tool(s) | Expected Canvas View (`pickCanvasView`) | Chat Answer Rule | What the Presenter Points At |
|---|---|---|---|---|---|---|---|
| **1** | Field compare | `Compare field performance` | `"Compare Lakwa with other fields"` | `compare_fields` | `compare` *(see routing note)* | ≤ 3 sentences, summary of Lakwa production vs Geleki and Lakhmani | Field comparison bar charts, target gap, Lakwa underperformance KPI |
| **2** | Sick wells | `Which wells in Lakwa are sick?` | `"Show me sick wells in Lakwa"` | `classify_well_health`, `attribute_decline` | `overview` *(see routing note)* | ≤ 3 sentences, count of sick and lost-production wells | Health bucket breakdown card (`value from tool` wells sick) |
| **3** | Priority list | `Show priority list of wells needing intervention` | `"Give me the priority queue for Lakwa"` | `rank_candidates` | `interventions` *(see routing note)* | ≤ 3 sentences, top candidate wells by deferred oil and priority | Priority candidate queue, top-ranked well `LKW-019` |
| **4** | LKW-019 Overview | `Tell me about LKW-019` | `"Open overview for LKW-019"` | `well_profile` | `overview` | ≤ 3 sentences, current status, latest test rates, health bucket; no history dump | Well header, status badge, current rate `value from tool` bopd |
| **5** | Production | `Show production history for LKW-019` | `"Plot production trend for LKW-019"` | `plot_production` | `production` | ≤ 3 sentences, baseline rate vs current decline and water cut trend | Production time-series chart, rising water cut, historical job markers |
| **6** | Interventions | `Show past interventions for LKW-019` | `"What past workovers were done on LKW-019?"` | `well_profile` | `interventions` | ≤ 3 sentences, summary of prior workovers and last job outcome | Workover history table: date, job type, rig-days, outcome |
| **7** | Wellbore | `Show wellbore diagram and completion details for LKW-019` | `"Show casing and completion schematic for LKW-019"` | `well_profile` | `wellbore` | ≤ 3 sentences, casing/tubing sizes, perforations, packer depth | Wellbore schematic, completion string, perforation intervals |
| **8** | Diagnosis | `Why is production declining on LKW-019?` | `"What is the root cause of decline for LKW-019?"` | `attribute_decline` | `diagnosis` | ≤ 3 sentences, dominant decline mechanism (water channeling/coning) | Decline attribution waterfall, water breakthrough percentage |
| **9** | Recommendation top 3 | `What should we do for LKW-019?` | `"What is the next best action for LKW-019?"` | `recommend_next_best_action` | `recommendation` | ≤ 3 sentences, primary recommendation + 2 alternatives with P(success) | Top-3 NBA cards: P(success) `value from tool`, uplift `value from tool` bopd |
| **10** | Counterfactual compare | `Why not sand cleanout for LKW-019?` | `"Why not sand cleanout instead of water shutoff?"` | `compare_interventions` | `compare` | ≤ 3 sentences, direct comparative defense of water shutoff over sand cleanout | Side-by-side counterfactual comparison table, risk and NPV difference |
| **11** | Field report link | `Prepare me for the field` | `"Generate field pack for LKW-019"` | `build_well_dossier` | `overview` *(Stage FR target: `report`)* | ≤ 3 sentences, single actionable link to open printable HTML field report | Chat action link: *"Field report for LKW-019 is ready → open"* |

---

## Detailed Step Walkthroughs

### Step 1 · Field Performance Comparison
* **User Phrase (Typed):** `Compare field performance`
* **Voice Variant:** `"Compare Lakwa with other fields"`
* **Expected Tool(s):** `compare_fields`
* **Canvas View:** `compare` (Routed by `pickCanvasView('', phrase)` via `\bcompare\b` keyword match).
  * *Note on routing:* In `chat.ts`, `KW` maps `\bcompare\b` to canvas view `compare`. In the full UI, field-level comparison also renders the comparison chart on the main screen.
* **Chat Answer Rule:** Maximum 3 sentences. Summarize total production across Lakwa, Geleki, and Lakhmani without verbose data tables.
* **Presenter Script:**
  > *"Lakwa is currently producing `value from tool` bopd, trailing its target by `value from tool` bopd, primarily due to rising water cut in mature blocks. Geleki and Lakhmani remain on target at `value from tool` bopd and `value from tool` bopd respectively. Let's look closer into Lakwa's sick wells."*
* **Presenter Points At:** Lakwa's shortfall bar on the comparison chart, highlighting the target deficit.

---

### Step 2 · Sick Wells Identification
* **User Phrase (Typed):** `Which wells in Lakwa are sick?`
* **Voice Variant:** `"Show me sick wells in Lakwa"`
* **Expected Tool(s):** `classify_well_health`, `attribute_decline`
* **Canvas View:** `overview` (Falls back to `overview` because "sick" is not an explicit keyword in `KW`).
* **Chat Answer Rule:** Maximum 3 sentences. State the number of sick wells and wells with lost production.
* **Presenter Script:**
  > *"Lakwa has `value from tool` active wells, of which `value from tool` are classified as sick and `value from tool` have severe production loss. The primary decline drivers are water channeling and mechanical lift degradation. Here is the breakdown across clusters."*
* **Presenter Points At:** Health bucket classification summary badges (`CRITICAL`, `MONITOR`, `HEALTHY`).

---

### Step 3 · Candidate Priority List
* **User Phrase (Typed):** `Show priority list of wells needing intervention`
* **Voice Variant:** `"Give me the priority queue for Lakwa"`
* **Expected Tool(s):** `rank_candidates`
* **Canvas View:** `interventions` (Routed to `interventions` by `pickCanvasView` because "intervention" matches `\binterventions?\b` in `KW`).
  * *Note on routing:* In `chat.ts`, the word "intervention" triggers the `interventions` canvas view. Presenter notes that `LKW-019` tops the candidate list.
* **Chat Answer Rule:** Maximum 3 sentences. Highlight the top candidate well with deferred production.
* **Presenter Script:**
  > *"We have ranked the top intervention candidates in Lakwa by deferred oil volume and rig-days. Well LKW-019 is ranked #1 with `value from tool` bopd of unrecovered potential. Let's inspect LKW-019."*
* **Presenter Points At:** Top-ranked candidate row for `LKW-019` showing deferred bopd and rig-day index.

---

### Step 4 · LKW-019 Overview (Identity & Status)
* **User Phrase (Typed):** `Tell me about LKW-019`
* **Voice Variant:** `"Open overview for LKW-019"`
* **Expected Tool(s):** `well_profile`
* **Canvas View:** `overview`
* **Chat Answer Rule:** Maximum 3 sentences. Identity, current operating status, and latest test. **Strict guardrail:** No multi-section well history dump.
* **Presenter Script:**
  > *"LKW-019 is an oil producer completed in the Lakwa TS-2 sand, currently operating on gas lift. Latest test recorded `value from tool` bopd oil with an elevated water cut of `value from tool`%. The well has been flagged under the sick bucket since `value from tool`."*
* **Presenter Points At:** Well status badge, formation tag (TS-2), and latest test KPI card.

---

### Step 5 · Production Time Series
* **User Phrase (Typed):** `Show production history for LKW-019`
* **Voice Variant:** `"Plot production trend for LKW-019"`
* **Expected Tool(s):** `plot_production`
* **Canvas View:** `production`
* **Chat Answer Rule:** Maximum 3 sentences. State historical baseline rate, onset of steep decline, and water cut escalation.
* **Presenter Script:**
  > *"LKW-019 historically produced `value from tool` bopd until a sharp decline occurred over the past `value from tool` months. Water cut climbed rapidly from `value from tool`% to `value from tool`%, while gas-oil ratio remained stable. Historical workover markers are indicated along the timeline."*
* **Presenter Points At:** Production trend chart, pointing at the steep water-cut divergence and job marker pins.

---

### Step 6 · Past Interventions History
* **User Phrase (Typed):** `Show past interventions for LKW-019`
* **Voice Variant:** `"What past workovers were done on LKW-019?"`
* **Expected Tool(s):** `well_profile`
* **Canvas View:** `interventions`
* **Chat Answer Rule:** Maximum 3 sentences. Summarize previous workover count and last intervention outcome.
* **Presenter Script:**
  > *"LKW-019 has undergone `value from tool` previous interventions, most recently a gas-lift valve change in `value from tool`. That job provided temporary uplift of `value from tool` bopd but declined within `value from tool` days due to underlying water coning. No water shutoff has ever been attempted on this well."*
* **Presenter Points At:** Workover history table columns: Date, Job Type, Rig Days, Uplift, Outcome.

---

### Step 7 · Wellbore & Completion Diagram
* **User Phrase (Typed):** `Show wellbore diagram and completion details for LKW-019`
* **Voice Variant:** `"Show casing and completion schematic for LKW-019"`
* **Expected Tool(s):** `well_profile`
* **Canvas View:** `wellbore`
* **Chat Answer Rule:** Maximum 3 sentences. Outline production casing size, tubing diameter, perforation interval, and packer depth.
* **Presenter Script:**
  > *"The well is completed with a `value from tool`\" production casing set at `value from tool` m MD and `value from tool`\" tubing. Current perforations are open in the TS-2 interval from `value from tool` m to `value from tool` m MD with a retrievable packer set at `value from tool` m MD. Wellbore integrity is verified with no annular pressure recorded."*
* **Presenter Points At:** Wellbore schematic schematic, casing shoes, perforation interval, and packer placement.

---

### Step 8 · Decline Diagnosis & Root Cause
* **User Phrase (Typed):** `Why is production declining on LKW-019?`
* **Voice Variant:** `"What is the root cause of decline for LKW-019?"`
* **Expected Tool(s):** `attribute_decline`
* **Canvas View:** `diagnosis`
* **Chat Answer Rule:** Maximum 3 sentences. Identify primary attribution mechanism and confidence level.
* **Presenter Script:**
  > *"Decline attribution identifies water breakthrough via bottom-water coning and channeling as the primary root cause, accounting for `value from tool`% of production loss. Mechanical lift is functioning normally, ruling out gas-lift failure. Formation skin and reservoir depletion account for the remaining `value from tool`%."*
* **Presenter Points At:** Attribution waterfall chart showing water channeling as the dominant red deficit bar.

---

### Step 9 · Recommendation (Top 3 Interventions)
* **User Phrase (Typed):** `What should we do for LKW-019?`
* **Voice Variant:** `"What is the next best action for LKW-019?"`
* **Expected Tool(s):** `recommend_next_best_action`
* **Canvas View:** `recommendation`
* **Chat Answer Rule:** Maximum 3 sentences. Rank top 3 intervention choices with P(success), uplift, and rig-days.
* **Presenter Script:**
  > *"The multimodal recommendation model ranks Water Shutoff Squeeze as the top intervention with P(success) of `value from tool`% and expected uplift of `value from tool` bopd over `value from tool` rig-days. Alternative 2 is Reperforation of upper TS-1 (`value from tool`% success, `value from tool` bopd), and Alternative 3 is Gas Lift Optimization (`value from tool`% success, `value from tool` bopd). Analogs show `value from tool` out of `value from tool` offset water-shutoff jobs succeeded."*
* **Presenter Points At:** Top-3 recommendation cards, P(success) probability bars, and analog well badges.

---

### Step 10 · Counterfactual Defense ("Why Not Sand Cleanout?")
* **User Phrase (Typed):** `Why not sand cleanout for LKW-019?`
* **Voice Variant:** `"Why not sand cleanout instead of water shutoff?"`
* **Expected Tool(s):** `compare_interventions`
* **Canvas View:** `compare`
* **Chat Answer Rule:** Maximum 3 sentences. Explain why sand cleanout is suboptimal compared to water shutoff.
* **Presenter Script:**
  > *"Sand cleanout has only a `value from tool`% P(success) on LKW-019 because acoustic diagnostics confirm minimal sand fill in the rathole (`value from tool` m). A sand cleanout does not isolate the lower water-coning channel and would yield only `value from tool` bopd uplift versus `value from tool` bopd from water shutoff. Water shutoff squeeze offers significantly higher return per rig-day."*
* **Presenter Points At:** Counterfactual comparison side-by-side table, highlighting NPV, risk metrics, and diagnostic indicators.

---

### Step 11 · Field Report Link ("Prepare Me for the Field")
* **User Phrase (Typed):** `Prepare me for the field`
* **Voice Variant:** `"Generate field pack for LKW-019"`
* **Expected Tool(s):** `build_well_dossier`
* **Canvas View:** `overview` *(Stage AC behavior; Stage FR will route to dedicated `report` view).*
* **Chat Answer Rule:** Maximum 3 sentences. Output a single clickable link to open the HTML field workover report.
* **Presenter Script:**
  > *"The complete field report for LKW-019 has been generated, including the step-by-step water shutoff job program, kill fluid calculations, and barrier checklist. You can open the printable A4 dossier below."*
* **Presenter Points At:** Chat action link card: **"Field report for LKW-019 is ready → open"**, clicking to expand the report preview.

---

## Negative Guardrail Case (Case 12)

* **User Phrase (Typed):** `Tell me about LKW-019 and dump full history`
* **Voice Variant:** `"Show me complete history for LKW-019"`
* **Expected Tool(s):** `well_profile`
* **Forbidden Tool(s):** `build_well_dossier` (agent must not trigger full multi-page dossier dump in chat text)
* **Expected Canvas View:** `overview`
* **Chat Answer Rule:** Maximum 3 sentences. Concise summary only; full history is accessible exclusively via the field report link or answer canvas switcher.

---

## ED Rehearsal Script (v0.6 Stage ED · Ajay Ratan, 2026-10-09)

**Setup (v0.6, updated 2026-10-08 for ED-10…14):**
- Open the Cloud Run URL **https://wellpulse-app-806277846965.us-central1.run.app** (local fallback: `bash run_local.sh`, open :5180).
- The map opens on **India** with 13 ONGC assets. Tags outside Assam are well names and positions only (not clickable).
- Click the **Urvi AI Agent** pill (or Ctrl+K). It docks on the right; the map fits beside it.
- For voice: press **Live**, then **Open mic** (or hold **Hold to talk**). From here on nothing needs a click.
- Showcase mode is on, so nothing is hidden; the persona menu notes that role-based access can be switched on.

### Part A · Hands-off and voice (≈ 3 min, show it is an agent, not a chatbot)

Say (or type) each line. Every command leaves a green **↗** chip in the chat; the screen changes in about 0.5–1 s.

| # | Say | Screen result |
|---|---|---|
| A0 | "Namaste Urvi" → "Aap kaun ho?" | Greets back in one line, nothing on screen changes; then "Main Urvi AI Agent hoon…" |
| A1 | "Assam dikhao" / "Take me to Assam" | India → Assam Asset (Lakwa, Lakhmani, Geleki) |
| A2 | "Sirf band wells dikhao" / "Only show non producing wells" | Map shows only red wells; chip "Showing: Not producing (79)". Health & priority screen does **not** open |
| A3 | "Sirf healthy wells dikhao" → "Sab wells dikhao" | Only green wells (245) → all wells back |
| A4 | "GGS three dikhao" | Zooms to GGS-03 and opens its popup; serviced wells are buttons coloured by health tag |
| A5 | (one click, optional) a red well button in the popup | That well opens in the panel and the map zooms to it |
| A6 | "Full screen karo" → "SCADA map" → "Satellite dikhao" | Full-screen map with the agent docked on the right; basemap switches |
| A7 | "Full screen band karo" | Back to map + panel |
| A8 | "GK one two nine wellbore kholo" | GK-129 completion diagram in the panel |
| A9 | "Hindi mein bolo" | Agent switches to Hindi (Devanagari captions) |
| A10 | "Print the report" | Field report opens and the print dialog appears |

Also clickable as a backup: the **Healthy / Needs attention / Not producing** items in the map legend and the header filter the map the same way (click again to clear).

### Part B · Technical questions

Expected answers below come from the tools at AS_OF 2026-09-23 (smoke run 2026-10-08). The agent quotes the same numbers, and the panel opens the view in the last column.

| # | ED asks (text or voice) | Tool(s) | Expected answer (key facts) | Panel view |
|---|---|---|---|---|
| 1 | "Show me all our assets." → "Take me to Assam." | map | India with 13 assets → Assam Asset: Lakwa, Lakhmani, Geleki | Map (India → Assam) |
| 2 | "What's wrong with GK-129?" | `compare_offset_decline` (+ `well_anomalies`) | Water cut up 13.0 pts in 12 months while offsets changed 2.2 pts, so a water problem in this well (channelling / casing leak / coning), not wax | vs Offsets |
| 3 | "Compare its decline with the nearby wells." | `compare_offset_decline` | Same verdict, with the chart and table of offsets: distance, 12-month trend, WC Δ, last job | vs Offsets |
| 4 | "Any anomalies in GK-129's history?" | `well_anomalies` | 5 anomalies in 24 months (1 rate drop, 1 water-cut rise, 3 downtime). Biggest: 2024-09-21 tubing-leak workover, 34 days, 1154 bbl deferred | History & Wax/Sand |
| 5 | "Show me the completion diagram." | `well_profile` | Casing, cement, tubing / tools, perforations, formation tops, TD | Wellbore (completion diagram) |
| 6 | "Is LKW-019 a well problem or the reservoir?" | `compare_offset_decline` | 32.6% above its own decline curve: rate restored by straddle packer on 2025-10-01 (+55.7 bopd). Offsets decline 16.6%/yr. Now waiting on rig (sand) since 2026-09-06 | vs Offsets |
| 7 | "What's the sand history on LKW-019?" | `wax_sand_behaviour` | No sand jobs yet, but 1 sand downtime episode (18 days, 626 bbl deferred), ongoing since 2026-09-06. No sand-rate data: inferred from jobs and downtime | History & Wax/Sand |
| 8 | "Why is LKM-061 down?" | `compare_offset_decline`, `well_anomalies` | 37.7% below its own decline curve while offsets are at −13.5%: the problem is in this well (gas-lift valve signature). Oil fell 31.0% in 2024-11 and the GLV replacement failed | vs Offsets |
| 9 | "Is GK-031's wax normal? Can we predict the next job?" | `wax_sand_behaviour` | 7 wax jobs, repeating about every 178 days, more often than the Geleki norm of 360 days. Next due 2026-08-04, overdue by 50 days. 12132 bbl deferred to wax | History & Wax/Sand |
| 10 | "What should we do on GK-129, and why not wax removal?" | `recommend_next_best_action`, `compare_interventions` | Top 3 from the multimodal engine; counterfactual explains why wax removal loses | Recommendation → Compare |

**Pass criteria:**
- Part A: every command changes the screen and leaves a chip; no Health & priority screen for display requests.
- Each answer is ≤ 4 sentences.
- Every number appears in the tool result for that turn.
- No currency.
- The panel opens the listed view.
- India tags are not clickable.

**If something goes wrong:**
- Voice mishears → type the same phrase in the agent box (plain commands run instantly in the browser).
- Live drops → the agent falls back to text automatically; keep typing.
- Bad deploy → `gcloud run services update-traffic wellpulse-app --project workover-operations-agentic-ai --region us-central1 --to-revisions=wellpulse-app-00007-nqz=100` (revision live before the Urvi deploy).

**If asked:**
- *"Is the data real?"* No. Synthetic and representative of the Assam Asset. Asset centres are approximate public locations; the tags outside Assam are illustrative.
- *"Is it a chatbot?"* No. Urvi AI Agent drives the screen through an allow-listed `ui_control` tool (map, filters, panel, language, report); it cannot run anything outside that list.
- *"Who sees what?"* Everything is shown today; role-based access per persona (CMD / ED / field engineer) is built and can be switched on (`WELLPULSE_RBAC_ENFORCE=1`).
