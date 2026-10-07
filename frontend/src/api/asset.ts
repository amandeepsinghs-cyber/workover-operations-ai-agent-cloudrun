/**
 * Typed client for the Stage T asset / drill-down routes (SDD §13.4, backend/app/api/asset.py).
 *
 * Every route returns the tool envelope {status, data, message, missing_fields, provenance} (SDD §13.1).
 * Components must render numbers ONLY from these payloads (no hard-coded values, Gate T).
 * A non-OK status (UNAVAILABLE / INSUFFICIENT_HISTORY / LOW_CONFIDENCE) must be shown, not hidden.
 */

import { getPersona } from '../state/persona';

export type FieldName = 'Geleki' | 'Lakwa' | 'Lakhmani';
export type FieldFilter = FieldName | 'ALL';
export type ToolStatus =
  | 'OK'
  | 'UNAVAILABLE'
  | 'INSUFFICIENT_HISTORY'
  | 'LOW_CONFIDENCE'
  | 'DISCRIMINATOR_UNAVAILABLE';
export type HealthBucket = 'PRODUCING_OK' | 'AT_RISK' | 'UNDERPERFORMING' | 'NOT_PRODUCING';
export type FactorClass =
  | 'SUBSURFACE'
  | 'EQUIPMENT'
  | 'OPERATIONAL'
  | 'HUMAN_PROCESS'
  | 'EXTERNAL'
  | 'UNEXPLAINED';

export interface Provenance {
  tool_id: string;
  input_hash: string;
  config_version: string;
  data_backend: string;
  as_of: string;
  duration_ms: number;
  [k: string]: unknown;
}

export interface Envelope<T> {
  status: ToolStatus;
  data: T | null;
  message: string;
  missing_fields: string[];
  provenance: Provenance;
}

export type HealthCounts = Record<HealthBucket, number>;

/* ------------------------------------------------------------------ TC-025 + /api/fields */
export interface ClusterNode {
  cluster_id: string;
  cluster_type: string; // GGS | FAULT_BLOCK
  n_wells: number;
  n_active: number;
  center_lat: number | null;
  center_lon: number | null;
}

export interface FieldNode {
  field: FieldName;
  n_wells: number;
  n_active: number;
  clusters: ClusterNode[];
  /* added by GET /api/fields (not by the bare TC-025 tool) */
  health_counts?: HealthCounts | null;
  centroid?: { lat: number; lon: number } | null;
  boundary_geojson?: GeoJSON | null; // FeatureCollection: field boundary + cluster (GGS) polygons
  is_synthetic_geometry?: boolean;
}

export interface Hierarchy {
  asset: string;
  fields: FieldNode[];
  n_wells: number;
}

/** Minimal GeoJSON typing (FeatureCollection of Polygon features). */
export interface GeoJSONFeature {
  type: 'Feature';
  properties: {
    kind: 'FIELD_BOUNDARY' | 'CLUSTER_POLYGON';
    field: FieldName;
    cluster_id?: string;
    name: string;
    is_synthetic_geometry: boolean;
    [k: string]: unknown;
  };
  geometry: { type: 'Polygon'; coordinates: number[][][] };
}
export interface GeoJSON {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

/* ------------------------------------------------------------------ TC-028 field history */
export interface FieldPeriodRow {
  field: FieldName;
  period: string; // ISO date of period start (YYYY-MM-01)
  days_in_period: number;
  is_partial: boolean;
  wells_reporting: number;
  oil_bbl: number;
  water_bbl: number;
  gas_mscf: number;
  liquid_bbl: number;
  oil_bopd: number;
  water_bwpd: number;
  gas_mscfd: number;
  liquid_blpd: number;
  water_cut_pct: number | null;
  producing_wells: number;
  uptime_pct: number;
  target_oil_bopd: number | null;
  gap_pct: number | null;
}

export interface FieldHistorySummary {
  field: FieldName;
  start_period: string;
  end_period: string;
  start_oil: number;
  end_oil: number;
  change_pct: number | null;
  start_gas: number;
  end_gas: number;
  gas_change_pct: number | null;
  start_wc_pct: number | null;
  end_wc_pct: number | null;
  wc_change_pp: number | null;
  start_producing_wells: number;
  end_producing_wells: number;
  n_periods: number;
}

export interface FieldSeries {
  freq: 'M' | 'Q' | 'Y';
  start: string;
  end: string;
  fields: FieldName[];
  series: FieldPeriodRow[]; // one row per (field, period), sorted by field then period
  summary: FieldHistorySummary[];
  reconciliation: { field: FieldName; max_rel_error_pct: number; periods_checked: number }[];
  definitions: Record<string, string>;
}

/* ------------------------------------------------------------------ TC-024 field comparison */
export interface FieldComparisonRow {
  field: FieldName;
  actual_bopd: number;
  target_bopd: number | null;
  expected_bopd: number | null; // healthy-state potential (field_targets.potential_oil_bopd)
  gap_pct: number | null;
  gap_to_expected_pct: number | null;
  uptime_pct: number;
  target_uptime_pct: number | null;
  water_cut_pct: number | null;
  health_counts: HealthCounts | null;
  sick_or_lost_count: number | null;
  deferred_by_factor: Partial<Record<FactorClass, number>>; // bbl lost in the window by factor class (TC-019)
  controllable_pct: number | null;
  top_factor: FactorClass | null;
  active_interventions: number; // open UNDER_WORKOVER episodes at as_of
  waiting_on_rig: number;
  waiting_on_material: number;
  rig_candidates: number | null;
  rigless_candidates: number | null;
  n_wells: number;
  in_pinned_band: boolean | null;
  pinned_band: { target_pct: number; tol_pp: number } | null;
}

export interface FieldComparison {
  asset: string;
  period: 'QTD' | 'MTD' | 'YTD' | 'L12M';
  window_start: string;
  window_end: string;
  rows: FieldComparisonRow[];
  ranking: FieldName[]; // worst first (most negative gap)
  worst_field: FieldName | null;
  top_driver: { field: FieldName; factor_class: FactorClass; bbl: number; pct: number; controllable: boolean } | null;
  excluded: { field: FieldName; reason: string }[];
}

/* ------------------------------------------------------------------ TC-010 priority */
export interface CandidateRow {
  rank: number;
  well_id: string;
  queue: 'RIG' | 'RIGLESS';
  mechanism: string;
  job_code: string;
  job_name: string;
  rig_days: number;
  deferred_bbl_avoided_12mo: number;
  p_success: number | null;
  p_success_n: number;
  priority_score: number;
  cost_band: 'LOW' | 'MED' | 'HIGH';
  uplift_bopd: number;
  cluster_id: string | null;
}
export interface CandidateQueues {
  rig_queue: CandidateRow[];
  rigless_queue: CandidateRow[];
}

/* ------------------------------------------------------------------ TC-029 well profile */
export interface NeighbourWell {
  well_id: string;
  distance_m: number;
  cluster_id: string | null;
  same_zone: boolean;
  zone: string | null;
  lift_type: string | null;
  bucket: HealthBucket | null;
  status: string | null; // open status episode at as_of (PRODUCING / SHUT_IN / UNDER_WORKOVER / ...)
  oil_bopd: number | null; // mean of last 7 producing days <= as_of
  water_cut_pct: number | null;
  residual_pct: number | null; // TC-001 decline residual
  fit_quality: string | null;
  last_job_code: string | null;
  last_job_date: string | null;
}

export interface WellProfile {
  identity: {
    well_id: string;
    field: FieldName;
    cluster_id: string | null;
    lat: number | null;
    lon: number | null;
    zone: string | null;
    formation: string | null;
    spud_date: string | null;
    completion_date: string | null;
    total_depth_md_m: number | null;
    total_depth_tvd_m: number | null;
    perf_top_m: number | null;
    perf_bottom_m: number | null;
    well_status: string | null;
  };
  construction: {
    casing: { string_type: string; od_in: number; weight_ppf: number | null; grade: string | null; top_m: number | null; shoe_m: number | null; cement_top_m: number | null }[];
    tubing: { seq: number; component: string; od_in: number | null; length_m: number | null; top_m: number | null; install_date: string | null }[];
    perfs: { zone: string; top_m: number; bottom_m: number; spf: number | null; perf_date: string | null; status: string | null }[];
    casing_size_in: number | null;
    tubing_size_in: number | null;
  };
  lithology: { formation: string; top_md_m: number; bottom_md_m: number; lithology: string }[];
  lift: { lift_type: string; [k: string]: unknown };
  status: { bucket: HealthBucket | null; reason: string | null; episode_status: string | null; episode_since: string | null; reason_code: string | null };
  current: { oil_bopd: number | null; water_cut_pct: number | null; gas_mscfd: number | null; last_producing_date: string | null };
  decline: { residual_pct: number | null; expected_bopd: number | null; fit_quality: string | null; status: string };
  last_test: Record<string, unknown> | null;
  last_pressure_survey: Record<string, unknown> | null;
  interventions_summary: { total: number; last_job_code: string | null; last_job_date: string | null; last_outcome: string | null };
  neighbours: NeighbourWell[];
  neighbour_basis: string;
}

/* ------------------------------------------------------------------ TC-017 v2 production */
export type ProductionMetric =
  | 'oil'
  | 'water'
  | 'gas'
  | 'liquid'
  | 'water_cut'
  | 'gor'
  | 'wht'
  | 'gl_inj_rate'
  | 'gl_inj_pressure'
  | 'thp'
  | 'chp';

export interface InterventionMarker {
  date: string;
  end_date: string | null;
  workover_id: string;
  job_code: string;
  job_name: string | null;
  intervention_class: string | null;
  outcome: string; // SUCCESS | PARTIAL | FAILED | NO_ACTION | CENSORED | IN_PROGRESS | UNKNOWN
  rig_days: number | null;
  is_rigless: boolean | null;
  uplift_bopd: number | null;
  doc_id: string | null;
  doc_url: string | null;
}

export interface HistoricalIntervention {
  year: number;
  date: string;
  job_code: string;
  job_name: string | null;
  outcome: string;
}

export interface ProductionSeries {
  well_id: string;
  lift_type: string | null;
  gas_lift: boolean;
  months: number;
  window_start: string;
  window_end: string;
  dates: string[]; // daily ISO dates
  series: Partial<Record<ProductionMetric, (number | null)[]>>; // aligned to dates; null = shut-in / not measured
  units: Partial<Record<ProductionMetric, string>>;
  decline_fit: (number | null)[] | null; // aligned to dates
  interventions: InterventionMarker[]; // every job starting inside the window
  historical_interventions: HistoricalIntervention[]; // older jobs, disclosed as "Historical"
  n_producing_days: number;
  n_null_days: number;
}

/* ------------------------------------------------------------------ TC-016 v2 map */
export interface MapPoint {
  well_id: string;
  field: FieldName;
  cluster_id: string | null;
  lat: number | null;
  lng: number | null;
  lift_type: string;
  status: string;
  bucket: HealthBucket | null;
  oil_bopd: number | null;
  highlighted: boolean;
  color_key: string | null;
}
export interface WellMapData {
  fields: FieldName[];
  points: MapPoint[];
  boundaries: { field: FieldName; geojson: unknown; is_synthetic_geometry?: boolean }[];
  cluster_polygons: GeoJSONFeature[];
  facilities: Record<string, unknown>[];
  bbox: { min_lat: number | null; max_lat: number | null; min_lng: number | null; max_lng: number | null };
  counts_by_color: Record<string, number>;
}

/* ------------------------------------------------------------------ fetch helpers */
async function getEnvelope<T>(url: string): Promise<Envelope<T>> {
  const res = await fetch(url, { headers: { 'X-Persona': getPersona() } }); // Stage Y: demo persona switch
  const body = await res.json();
  if (!res.ok && !(body && typeof body === 'object' && 'status' in body)) {
    throw new Error((body && body.detail) || `HTTP ${res.status} for ${url}`);
  }
  return body as Envelope<T>;
}

export const assetApi = {
  fields: () => getEnvelope<Hierarchy>('/api/fields'),
  fieldHistory: (fields?: FieldName[], freq: 'M' | 'Q' | 'Y' = 'M', start?: string, end?: string) => {
    const q = new URLSearchParams({ freq });
    if (fields && fields.length) q.set('fields', fields.join(','));
    if (start) q.set('start', start);
    if (end) q.set('end', end);
    return getEnvelope<FieldSeries>(`/api/fields/history?${q.toString()}`);
  },
  compareFields: (period: FieldComparison['period'] = 'QTD') =>
    getEnvelope<FieldComparison>(`/api/fields/compare?period=${period}`),
  priority: (field: FieldName, queue: 'rig' | 'rigless' | 'all' = 'all', limit = 20) =>
    getEnvelope<CandidateQueues>(`/api/fields/${field}/priority?queue=${queue}&limit=${limit}`),
  wellMap: (field: FieldFilter = 'ALL') =>
    getEnvelope<WellMapData>(`/api/fields/map${field === 'ALL' ? '' : `?field=${field}`}`),
  wellProfile: (wellId: string, kNeighbours = 4) =>
    getEnvelope<WellProfile>(`/api/wells/${wellId}/profile?k_neighbours=${kNeighbours}`),
  wellProduction: (wellId: string, months: 24 | 36 | 60 = 36, metrics?: ProductionMetric[]) =>
    getEnvelope<ProductionSeries>(
      `/api/wells/${wellId}/production?months=${months}${metrics && metrics.length ? `&metrics=${metrics.join(',')}` : ''}`,
    ),
};

/** Zip a ProductionSeries into Recharts rows: [{date, oil, water_cut, ..., decline_fit}]. */
export function productionRows(ps: ProductionSeries): Record<string, string | number | null>[] {
  return ps.dates.map((d, i) => {
    const row: Record<string, string | number | null> = { date: d };
    for (const [m, vals] of Object.entries(ps.series)) row[m] = (vals as (number | null)[])[i] ?? null;
    if (ps.decline_fit) row.decline_fit = ps.decline_fit[i] ?? null;
    return row;
  });
}

export const BUCKET_COLORS: Record<HealthBucket, string> = {
  PRODUCING_OK: '#2ea043',
  AT_RISK: '#d29922',
  UNDERPERFORMING: '#fb923c',
  NOT_PRODUCING: '#f85149',
};

export const FIELD_COLORS: Record<FieldName, string> = {
  Geleki: '#38bdf8',
  Lakwa: '#f85149',
  Lakhmani: '#a855f7',
};
