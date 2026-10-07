"""Template for D08: Failure root-cause analysis note."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import Bullets, Callout, H, KV, P, Signoff, Table


def _failure_why_chain(spec) -> list[str]:
    fc = str(spec.raw.get("failure_code") or spec.facts.get("failure_code") or "").upper()
    if fc == "PUMP_WEAR":
        return [
            "Observed symptom: Progressive decline in pump displacement efficiency, erratic polish rod load readings, and diminished liquid delivery at the surface header.",
            "Physical mechanism: Abrasive scoring and clearance enlargement across the pump barrel and plunger assembly caused by abrasive fines and repeated mechanical cycling.",
            "Intervention shortfall: The executed workover addressed component replacement but did not resolve downhole sand ingress or abrasive fluid conditioning, leading to rapid re-wear.",
            "Latent root cause: Inadequate bottomhole filtration and sand management coupled with sub-optimal pump metallurgy for high-solids Assam formation fluids.",
        ]
    if fc == "ROD_PART":
        return [
            "Observed symptom: Sudden collapse in surface polish rod load, motor unloaded condition, and total cessation of liquid lifting.",
            "Physical mechanism: Cyclic mechanical tensile fatigue and corrosion-induced micro-cracking across rod pin shoulders and coupling threads.",
            "Intervention shortfall: Splicing or replacing parted rods restored mechanical continuity without eliminating harmonic string vibrations and dogleg cyclic bending stresses.",
            "Latent root cause: String design lacked adequate rod guides and vibration damping for localized borehole doglegs, accelerating bending fatigue.",
        ]
    if fc == "TUBING_LEAK":
        return [
            "Observed symptom: Annulus pressure build-up, communication between tubing and casing strings, and progressive shortfall in delivered wellhead pressure.",
            "Physical mechanism: Internal fluid erosion, carbon dioxide corrosive pitting, and rod-on-tubing abrasive mechanical wear puncturing the production conduit.",
            "Intervention shortfall: Replacing or patching isolated tubing joints left adjacent fatigued joints with wall loss in service, triggering secondary leaks upon re-pressurization.",
            "Latent root cause: Lack of continuous corrosion inhibitor batching combined with severe rod buckling across deviated sections of the production wellbore.",
        ]
    if fc == "WAX":
        return [
            "Observed symptom: Gradual rise in flowline pressure, progressive choking of tubing flow paths, and declining liquid recovery at the gathering station.",
            "Physical mechanism: High-molecular-weight paraffin wax crystallization and deposition on conduit walls below the cloud point depth in the Upper Assam reservoir column.",
            "Intervention shortfall: Thermal and chemical scraping or soaking provided transient wax clearance without elevating long-term near-wellbore formation temperature or sustaining inhibitor film coverage.",
            "Latent root cause: Elevated paraffin content in crude oil combined with ambient shallow thermal cooling during lift, requiring continuous automated chemical dosing.",
        ]
    if fc == "SCALE":
        return [
            "Observed symptom: Sharp drop in productive inflow, scaling across downhole intake ports, and restriction within production tubing.",
            "Physical mechanism: Supersaturated mineral precipitation, predominantly calcium carbonate and barium sulfate, triggered by pressure drops across completions.",
            "Intervention shortfall: Bullhead matrix wash or acid soaking dissolved accessible scale deposits but failed to place deep squeeze protection or alter incompatible water mixing dynamics.",
            "Latent root cause: Formation water breakthrough mixing with incompatible injected fluid regimes without threshold scale inhibitor replenishment.",
        ]
    if fc == "SAND":
        return [
            "Observed symptom: Solids accumulation in surface separator boots, abrasive cut-out of chokes, and sand pack-off arresting downhole pump action.",
            "Physical mechanism: Hydrodynamic drag from formation fluid mobilization exceeding unconfined compressive rock strength in weakly consolidated Tipam and Barail sands.",
            "Intervention shortfall: Mechanical bailing or cleanout evacuated wellbore sand fill without stabilizing the unconsolidated perforations or installing mechanical sand retention screens.",
            "Latent root cause: Inappropriate drawdown pressure management and absence of downhole gravel pack or slotted liner completion in friable sand packages.",
        ]
    if fc == "WATER_CHANNELLING":
        return [
            "Observed symptom: Abrupt and severe rise in produced water cut accompanied by steep decline in oil extraction rates without prior coning signature.",
            "Physical mechanism: High-permeability thief streaks or deteriorated cement sheath allowing bypass of displacement water behind production casing.",
            "Intervention shortfall: Chemical squeeze or mechanical packer isolation failed to achieve a hydraulic seal due to micro-annular bypass and reservoir pressure differentials.",
            "Latent root cause: Degraded primary cement bond integrity behind casing and severe permeability contrast in heterogeneous laminated sands.",
        ]
    if fc == "WATER_ZONE":
        return [
            "Observed symptom: Immediate water breakthrough and dominant water production following perforation or nearby injection pressure support.",
            "Physical mechanism: Unintended hydraulic communication with an adjacent active aquifer through thin impermeable shale barriers.",
            "Intervention shortfall: Zonal isolation and plug-back treatments failed to isolate high-pressure water encroachment behind the liner or casing.",
            "Latent root cause: Insufficient geological barrier thickness and vertical fracture conductivity bridging productive oil pay with basal aquifer sand.",
        ]
    if fc == "CONING":
        return [
            "Observed symptom: Rate-sensitive water cut escalation accelerating sharply whenever production drawdowns were increased at the surface choke.",
            "Physical mechanism: Upward deformation of the oil-water contact driven by vertical pressure gradients exceeding gravity capillary forces.",
            "Intervention shortfall: Choking back and bottom-perf plug-backs produced insufficient drawdown relief while the structural contact had already invaded the perforated interval.",
            "Latent root cause: Excessive vertical reservoir permeability and narrow standoff between perforation interval base and underlying active aquifer contact.",
        ]
    if fc == "PI_DECLINE":
        return [
            "Observed symptom: Substantial drop in productivity index with intact reservoir static pressure, leading to severely depressed liquid inflow rates.",
            "Physical mechanism: Near-wellbore formation damage, fine particle migration, and organic or inorganic pore throat plugging across the drainage radius.",
            "Intervention shortfall: Stimulation fluid volume and acid placement failed to overcome deep matrix skin damage or dissolved mineral precipitates redeposited in pores.",
            "Latent root cause: Inadequate compatibility testing between completion workover fluids and sensitive indigenous clay minerals causing severe swelling.",
        ]
    if fc == "GL_INJ_ANOMALY":
        return [
            "Observed symptom: Unstable casing injection pressure, erratic gas lift injection volumes, and failure to kick off deep operating valves.",
            "Physical mechanism: Bellows fatigue, port plugging from solids, or eroded orifices in wireline-retrievable gas lift valves.",
            "Intervention shortfall: Valve changeout restored individual port function but did not rectify casing supply line pressure fluctuations or wet injection gas quality.",
            "Latent root cause: Liquid carryover and pipeline debris in the field gas distribution network damaging precision downhole valve seats.",
        ]
    if fc == "SURFACE":
        return [
            "Observed symptom: Surface flowline backpressure spikes, manifold header restrictions, or mechanical driver breakdown arresting production.",
            "Physical mechanism: Wellhead valve seat wear, stuffing box packing degradation, flowline wax sedimentation, or surface pumping unit misalignment.",
            "Intervention shortfall: Surface mechanical repair fixed the immediate surface defect but left unaddressed severe backpressures transmitted from gathering lines.",
            "Latent root cause: Gathering network bottle-necking and deferred preventative maintenance on surface pumping equipment and flow headers.",
        ]
    if fc == "CASING_LEAK":
        return [
            "Observed symptom: Sustained casing-casing annulus pressure, anomalous fluid influx, and contamination of production fluid from shallow intervals.",
            "Physical mechanism: Electrochemical corrosion, external aquifer attack, and mechanical wear from drillpipe or rod string abrasion breaching casing integrity.",
            "Intervention shortfall: Casing patch or cement squeeze exhibited pressure containment failure during subsequent thermal cycles and operational drawdowns.",
            "Latent root cause: Corrosive shallow aquifer waters in un-cemented casing sections combined with age-related casing metal degradation.",
        ]
    if fc == "LIFT_INEFFICIENCY":
        return [
            "Observed symptom: Poor volumetric lift performance, high power consumption per barrel lifted, and mismatched fluid inflow with pump capacity.",
            "Physical mechanism: Sub-optimal pump displacement setting, improper stroke rate selection, and low downhole pump submergence.",
            "Intervention shortfall: Lift adjustment restored nominal operations but did not optimize speed and stroke length to matching actual declining inflow potential.",
            "Latent root cause: Dynamic well inflow parameters deviated substantially from static nodal design assumptions without continuous acoustic fluid level surveillance.",
        ]
    if fc == "GL_HEADING":
        return [
            "Observed symptom: Severe cyclic surges in tubing head pressure, slug flow at surface separators, and intermittent gas-liquid production cycles.",
            "Physical mechanism: Hydrodynamic instability between casing gas volume and liquid column loading causing multi-phase heading behavior.",
            "Intervention shortfall: Surface choke throttling and valve adjustment failed to establish critical flow across downhole injection ports.",
            "Latent root cause: Sub-critical injection gas rate and oversized production tubing diameter for existing low-velocity liquid throughput.",
        ]
    if fc == "GL_LOADING":
        return [
            "Observed symptom: Inability of injection gas to sustain continuous unloading, liquid column accumulation in tubing, and gradual well kill.",
            "Physical mechanism: Inflow water cut rise elevating fluid gradient beyond available lift gas pressure delivery capability.",
            "Intervention shortfall: Injection kick-off cycles temporarily lifted fluid slugs but could not sustain steady continuous aeration against increasing bottomhole pressure.",
            "Latent root cause: Available field gas lift compression discharge pressure fell below threshold required to aerate high-water-cut fluid columns.",
        ]
    if fc == "GAS_INTERFERENCE":
        return [
            "Observed symptom: Sharp decrease in downhole pump volumetric efficiency, fluid pound signatures on dynamometer cards, and erratic liquid flow.",
            "Physical mechanism: Free gas entering the pump barrel during upstroke causing gas compression and lock rather than fluid intake.",
            "Intervention shortfall: Resetting pump spacing or installing standard gas anchors failed to separate high associated gas volumes before entering the suction valve.",
            "Latent root cause: High downhole gas-to-oil ratio exceeding separation capacity of installed intake configuration under low submergence pressure.",
        ]
    if fc == "SUDDEN_MECH":
        return [
            "Observed symptom: Abrupt and unexpected mechanical lockup or structural failure halting production without antecedent gradual deterioration.",
            "Physical mechanism: Mechanical parting of completion hardware, shear pin failure, or structural collapse under dynamic operational loads.",
            "Intervention shortfall: Replacing broken mechanical components returned well to service without addressing dynamic shock loads that caused the initial failure.",
            "Latent root cause: Cyclic fatigue and excessive operational vibration under harsh multi-phase operating conditions exceeding component design limits.",
        ]
    if fc == "BYPASSED_PAY":
        return [
            "Observed symptom: Rapid production decline from primary completion while log analyses indicate unproduced hydrocarbons in adjacent sub-layers.",
            "Physical mechanism: Depletion of primary perforated sub-stratum while remaining oil-bearing intervals remain unperforated or poorly drained.",
            "Intervention shortfall: Extended perforation or re-perforation achieved limited inflow due to formation compaction or skin damage in the target interval.",
            "Latent root cause: Inadequate reservoir pressure support and low initial permeability in secondary pay stringers requiring hydraulic stimulation.",
        ]
    return [
        "Observed symptom: Production underperformance, anomalous wellhead pressure behavior, and premature cessation of design operating life.",
        "Physical mechanism: Complex downhole fluid-mechanical degradation involving multi-phase flow restrictions and downhole component wear.",
        "Intervention shortfall: Standard remediation procedures restored short-term functional response but did not address complex systemic wellbore dynamics.",
        "Latent root cause: Compound reservoir and mechanical stressors interacting across the production lifecycle without continuous automated surveillance.",
    ]


def _recommendations(spec) -> list[str]:
    cat = str(spec.raw.get("job_category") or spec.facts.get("job_category") or "").upper()
    if cat == "DEPOSITION":
        return [
            "Implement routine downhole chemical squeeze treatments with verified chemical retention profiling rather than periodic reactive washing.",
            "Establish continuous monitoring of gathering line temperatures and wellhead operating backpressures to arrest flowline crystallization.",
            "Schedule periodic solvent circulation flushes ahead of critical precipitation threshold periods to prevent solid build-up.",
        ]
    if cat == "GAS_LIFT":
        return [
            "Verify gas lift valve integrity and unloading port dynamics through acoustic fluid level sounding and pressure gradient surveys.",
            "Install premium check valve trim and debris filters on lift gas distribution lines at the compressor manifold to prevent valve fouling.",
            "Optimize injection gas volumetric allocation based on dynamic nodal analysis rather than fixed header pressure delivery.",
        ]
    if cat == "INFLOW":
        return [
            "Mandate core-flood and fluid compatibility testing prior to pumping chemical or matrix stimulation treatments to prevent clay swelling.",
            "Perform high-resolution pressure buildup surveys before re-stimulation to differentiate reservoir depletion from near-wellbore skin.",
            "Deploy selective diversion techniques during matrix stimulation to ensure uniform fluid placement across the entire perforated interval.",
        ]
    if cat == "MECHANICAL":
        return [
            "Upgrade metallurgy of downhole moving components and evaluate corrosion-resistant rod couplings across high-dogleg intervals.",
            "Mandate full-length electromagnetic tubing inspection and pressure testing prior to pulling unit release.",
            "Review polish rod load cell calibration and install automated pump-off controllers to avoid chronic fluid pound.",
        ]
    if cat == "WATER_CONTROL":
        return [
            "Conduct pulsed neutron saturation logging and high-resolution temperature surveys prior to cementing or mechanical packer setting.",
            "Verify mechanical integrity of bridge plugs and straddle packer elastomer elements under downhole temperature and pressure conditions.",
            "Re-evaluate reservoir structural standoff and restrict maximum liquid withdrawal rates to suppress hydrodynamic coning.",
        ]
    if cat == "WAX":
        return [
            "Transition from batch scraping to automated capillary chemical injection of crystal modifier wax inhibitors at the pump intake.",
            "Monitor thermal loss profiles along the upper tubing string and insulate wellhead piping to maintain fluid temperature above the cloud point.",
            "Establish weekly fluid sampling and pour point verification at the group gathering station to monitor inhibitor coverage.",
        ]
    return [
        "Enhance pre-job diagnostic surveillance including diagnostic pressure testing and acoustic fluid level determination.",
        "Conduct multidisciplinary root-cause review before committing additional pulling unit or workover rig resources.",
        "Update field risk register with failure signatures to improve future candidate screening across the asset.",
    ]


def build(spec):
    blocks = [
        H("Event summary"),
        KV(
            [
                ("Workover identifier", "{workover_id}"),
                ("Intervention report", "{d02_doc_id}"),
                ("Job description", "{job_name}"),
                ("Job catalogue code", "{catalogue_job_code}"),
                ("Intervention class", "{intervention_class}"),
                ("Class description", "{ic_label}"),
                ("Start date", "{start_date}"),
                ("End date", "{end_date}"),
                ("Rig identifier", "{rig_id}"),
                ("Rig duration days", "{rig_days}"),
                ("Failure code", "{failure_code}"),
                ("Job outcome", "{outcome}"),
            ],
            cols=2,
        ),
        H("Problem statement and production response"),
    ]

    if spec.has("pre_oil_avg") and spec.has("delta_oil"):
        blocks.append(
            KV(
                [
                    ("Pre-job oil rate average", "{pre_oil_avg} BOPD"),
                    ("Post-job oil rate average", "{post_oil_avg} BOPD"),
                    ("Net oil rate shift", "{delta_oil} BOPD"),
                    ("Immediate test uplift", "{uplift_bopd} BOPD"),
                    ("Pre-job water cut average", "{pre_wc_avg}"),
                    ("Post-job water cut average", "{post_wc_avg}"),
                    ("Net water cut shift", "{delta_wc}"),
                    ("Post-job run life days", "{run_life_days}"),
                ],
                cols=2,
            )
        )
        blocks.append(
            P(
                "Across the {window_days}-day baseline surveillance window, production averaged "
                "{pre_oil_avg} BOPD oil and {pre_wc_avg} water cut. Following completion of the workover, "
                "the subsequent {window_days}-day window demonstrated an average production rate of "
                "{post_oil_avg} BOPD oil and {post_wc_avg} water cut, representing a net delta of "
                "{delta_oil} BOPD oil and {delta_wc} water cut. Although an initial post-job test uplift "
                "of {uplift_bopd} BOPD was measured, the intervention failed to establish sustained reservoir "
                "recovery, concluding with an effective operational run life of {run_life_days} days."
            )
        )
    else:
        blocks.append(
            KV(
                [
                    ("Pre-job test oil rate", "{pre_job_oil_bopd} BOPD"),
                    ("Post-job test oil rate", "{post_job_oil_bopd} BOPD"),
                    ("Immediate test uplift", "{uplift_bopd} BOPD"),
                    ("Post-job run life days", "{run_life_days}"),
                ],
                cols=2,
            )
        )
        blocks.append(
            P(
                "Continuous {window_days}-day surveillance baseline averages were not recorded for this historical "
                "intervention period. Well test logs reflect a pre-job baseline rate of {pre_job_oil_bopd} BOPD "
                "oil and an initial post-job test rate of {post_job_oil_bopd} BOPD oil, indicating an initial test "
                "uplift of {uplift_bopd} BOPD. However, the well failed to sustain production, culminating in a "
                "premature failure event after an operational run life of {run_life_days} days."
            )
        )

    if spec.has("pre_thp_avg") and spec.has("post_thp_avg") and spec.has("delta_thp"):
        blocks.append(
            P(
                "Surface wellhead measurements showed tubing head pressure shifting from {pre_thp_avg} ksc to "
                "{post_thp_avg} ksc, reflecting a net variance of {delta_thp} ksc across the surveillance interval."
            )
        )

    blocks.extend(
        [
            H("Failure mechanism and root-cause analysis"),
            Callout(
                "Root-cause investigation for failure code {failure_code} under intervention class "
                "{intervention_class} ({ic_label}).",
                tone="warning",
            ),
            Bullets(_failure_why_chain(spec)),
            H("Contributing factors and historical recurrence"),
            KV(
                [
                    ("Prior failures with same code", "{n_prior_same_failure}"),
                    ("Field jobs for this code", "{field_jobs_same_code}"),
                    ("Field failure rate for code", "{field_fail_rate_same_code}"),
                    ("Variance against planned rig days", "{rig_days_over_plan}"),
                ],
                cols=2,
            ),
            P(
                "Surveillance records indicate {n_prior_same_failure} prior failure occurrences matching "
                "failure code {failure_code} on this wellbore. Across the wider {field} field, "
                "{field_jobs_same_code} interventions have been executed under catalogue code {catalogue_job_code}, "
                "with a cumulative field failure rate of {field_fail_rate_same_code}. Operational rig duration "
                "exhibited a variance of {rig_days_over_plan} days relative to the planned schedule."
            ),
            H("Subsequent corrective action"),
        ]
    )

    if spec.has("next_workover_id"):
        blocks.append(
            KV(
                [
                    ("Next workover", "{next_workover_id}"),
                    ("Next job code", "{next_job_code}"),
                    ("Next start date", "{next_start_date}"),
                    ("Next job outcome", "{next_outcome}"),
                ],
                cols=2,
            )
        )
        blocks.append(
            P(
                "Following failure of this intervention, field operations mobilized follow-up workover "
                "{next_workover_id} ({next_job_code}) on {next_start_date}, after an elapsed interval of "
                "{days_to_next_job} days. The follow-up job concluded with an outcome assessment of {next_outcome}."
            )
        )
    else:
        blocks.append(
            P("No follow-up job recorded in the field workover database for this wellbore following the failure event.")
        )

    blocks.extend(
        [
            H("Lessons learned and engineering recommendations"),
            Bullets(_recommendations(spec)),
            H("Intervention history"),
            Table(
                "job_history",
                [
                    ("workover_id", "Workover"),
                    ("start_date", "Start"),
                    ("catalogue_job_code", "Job Code"),
                    ("intervention_class", "Class"),
                    ("failure_code", "Failure"),
                    ("rig_days", "Rig Days"),
                    ("post_job_oil_bopd", "Post BOPD"),
                    ("outcome", "Outcome"),
                ],
                title="Intervention and workover history",
                max_rows=8,
            ),
            Signoff(["Production Engineer", "Well Intervention Lead", "Asset Manager"]),
        ]
    )

    return blocks
