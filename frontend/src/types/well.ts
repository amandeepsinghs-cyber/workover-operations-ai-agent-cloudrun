export type WellStatus = 'healthy' | 'warning' | 'failed';

export type CostBand = 'LOW' | 'MED' | 'HIGH';

export interface WellCoordinates {
  lat: number;
  lng: number;
}

export interface CurrentMetrics {
  oil_bopd: number;
  gas_mcfd: number;
  water_cut_pct: number;
  tubing_pressure_psi: number;
  casing_pressure_psi: number;
  choke_pct: number;
  uptime_pct: number;
}

export interface TelemetrySummary {
  peak_oil_bopd: number;
  min_oil_bopd: number;
  avg_oil_bopd: number;
  total_workovers: number;
  cost_band_mix: { LOW: number; MED: number; HIGH: number };
  total_rig_days: number;
}

export interface WorkoverRecord {
  id: string;
  date: string;
  type: string;
  contractor: string;
  description: string;
  outcome: string;
  flow_delta_bopd: number;
  cost_band: CostBand;
  rig_days: number;
  requires_rig: boolean;
  equipment: string;
  intervention_class: string;
  intervention_label: string;
  catalogue_job_code: string;
  end_date?: string;
  report_doc_id?: string | null;
}

export interface TelemetryPoint {
  date: string;
  oil_bopd: number | null;
  gas_mcfd: number | null;
  water_cut_pct: number | null;
  tubing_pressure_psi: number | null;
  casing_pressure_psi: number | null;
  water_bwpd?: number | null;
  liquid_blpd?: number | null;
  gor_scf_bbl?: number | null;
  wht_degc?: number | null;
  gl_inj_rate_mscfd?: number | null;
  gl_inj_pressure_psi?: number | null;
  runtime_fraction?: number | null;
  is_producing?: boolean;
  downtime_reason?: string | null;
}

export interface WellSummary {
  id: string;
  name: string;
  coordinates: WellCoordinates;
  basin: string;
  formation: string;
  lift_type: string;
  status: WellStatus;
  current_metrics: CurrentMetrics;
  telemetry_summary: TelemetrySummary;
  recent_workovers_count: number;
  field?: string;
  cluster_id?: string;
  health_bucket?: string;
  health_reason?: string;
  health_rule?: string;
  as_of?: string;
  current_metrics_date?: string | null;
}

export interface CasingString {
  string: string;
  depth_m: number;
  cement_class: string;
}

export interface PerforatedInterval {
  top_depth_m: number;
  bottom_depth_m: number;
  formation: string;
  shots_per_meter: number;
  status: string;
}

export interface CrudeAssay {
  api_gravity: number;
  paraffin_wax_pct: number;
  pour_point_c: number;
  sulfur_content_pct: number;
  viscosity_cp_at_50c: number;
}

export interface CompletionReport {
  report_id: string;
  title: string;
  issuing_authority: string;
  spud_date: string;
  completion_date: string;
  total_depth_m: number;
  target_formation: string;
  casing_policy: CasingString[];
  tubing_specification: string;
  perforated_intervals: PerforatedInterval[];
  initial_production_test: {
    test_duration_hours: number;
    choke_size_mm: number;
    oil_flow_bopd: number;
    gas_flow_mcfd: number;
    water_cut_pct: number;
    tubing_head_pressure_psi: number;
  };
  crude_assay: CrudeAssay;
}

export interface HourlyLog {
  time: string;
  activity: string;
}

export interface DailyWorkoverReport {
  report_id: string;
  title: string;
  issuing_authority: string;
  date: string;
  supervising_engineer: string;
  workover_rig: string;
  operation_type: string;
  contractor: string;
  cost_band: CostBand;
  rig_days: number;
  shift_hours: string;
  hourly_logs: HourlyLog[];
  outcome_summary: string;
}

export interface GasLiftStatus {
  status: string;
  injection_pressure_casing_psi: number;
  injection_rate_mcfd: number;
  operating_valve_depth_m: number;
}

export interface BottomholePressureSurvey {
  report_id: string;
  title: string;
  issuing_authority: string;
  survey_date: string;
  datum_depth_m_tvd: number;
  static_bottomhole_pressure_sbhp_psi: number;
  flowing_bottomhole_pressure_fbhp_psi: number;
  drawdown_psi: number;
  productivity_index_pi: number;
  sonolog_fluid_level_m: number;
  fluid_gradient_psi_ft: number;
  gas_lift_status: GasLiftStatus;
}

export interface IonicConstituents {
  chloride_cl: number;
  sodium_na: number;
  calcium_ca: number;
  magnesium_mg: number;
  barium_ba: number;
  sulfate_so4: number;
  bicarbonate_hco3: number;
}

export interface ScalingTendency {
  calcium_carbonate_caco3: string;
  stiff_davis_index: string;
  barium_sulfate_baso4: string;
}

export interface WaterAndScaleLabReport {
  report_id: string;
  title: string;
  issuing_authority: string;
  sample_date: string;
  water_cut_tested_pct: number;
  total_dissolved_solids_tds_mg_l: number;
  ph_at_25c: number;
  specific_gravity: number;
  ionic_constituents_mg_l: IonicConstituents;
  scaling_tendency_analysis: ScalingTendency;
  chemist_recommendation: string;
}

export interface WellReports {
  completion_report?: CompletionReport;
  daily_workover_report?: DailyWorkoverReport;
  bottomhole_pressure_survey?: BottomholePressureSurvey;
  water_and_scale_lab_report?: WaterAndScaleLabReport;
}

export interface WellDetail extends WellSummary {
  workovers: WorkoverRecord[];
  reports?: WellReports;
}

export interface FleetKPIs {
  total_wells: number;
  healthy_count: number;
  warning_count: number;
  failed_count: number;
  total_oil_bopd: number;
  total_gas_mcfd: number;
  avg_water_cut_pct: number;
}

export interface Recommendation {
  title: string;
  urgency: string;
  urgency_badge: 'healthy' | 'warning' | 'critical';
  cost_band: CostBand;
  projected_flow_uplift_bopd: number;
  rig_days: number;
  action_items: string[];
  risk_mitigation: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  timestamp: string;
  text: string;
  recommendation?: Recommendation;
}

export interface GatheringStation {
  id: string;
  name: string;
  coordinates: WellCoordinates;
  capacity_bopd: number;
  compressor_capacity_mmscfd?: number;
  water_handling_bwpd?: number;
  serviced_wells?: string[];
}

export interface FieldInfrastructure {
  field_name: string;
  center_coordinates: WellCoordinates;
  gathering_stations: GatheringStation[];
}

