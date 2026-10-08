/**
 * Typed client for the Stage R decision routes (SDD §9, §13.4) plus the Stage P field / well analytics the
 * decision components show:
 *
 *   GET /api/wells/{id}/nba?top_k=3                         -> NextBestActions   (TC-022)
 *   GET /api/wells/{id}/compare?alternative=&recommended=   -> Counterfactual    (TC-027)
 *   GET /api/wells/{id}/attribution?window_days=180         -> DeclineAttribution (TC-019)
 *   GET /api/fields/{field}/health?cluster_id=              -> HealthBuckets     (TC-020)
 *   GET /api/fields/{field}/priority?queue=&limit=          -> CandidateQueues   (TC-010)
 *
 * Every route returns the envelope {status, data, message, missing_fields, provenance} (SDD §13.1).
 * Rules for components (Gate R / D-1):
 *   - render numbers ONLY from these payloads: no hard-coded wells, jobs, values or thresholds;
 *   - cost is `cost_band` (LOW | MED | HIGH) + `rig_days` — never a currency symbol, amount or payback;
 *   - a non-OK status (UNAVAILABLE / INSUFFICIENT_HISTORY / LOW_CONFIDENCE) must be shown, not hidden;
 *   - show `provenance.tool_id · provenance.as_of` on every card (ProvenanceBadge pattern).
 */
import type { CandidateRow, Envelope, FactorClass, FieldName, HealthBucket, HealthCounts } from './asset';

export type { Envelope, FieldName, HealthBucket } from './asset';

export type CostBand = 'LOW' | 'MED' | 'HIGH';
export type DiagnosticFit = 'FIT' | 'UNCLEAR' | 'CONTRADICTED';
export type FitSymbol = '✔' | '?' | '✘';
export type RiskFlag = 'WELL_INTEGRITY' | 'REPEAT_FAILURE' | 'LOGISTICS_DELAY' | 'LOW_EVIDENCE';
export type MroStatus = 'IN_STOCK' | 'TRANSFER_REQUIRED' | 'NO_STOCK' | 'NOT_REQUIRED';

/* ------------------------------------------------------------------ TC-022 next best action */
export interface SopPhase {
  phase: string;
  steps: string[];
}

export interface PSuccessDetail {
  intervention_class: string;
  alpha: number;
  n_asset: number;
  s_asset: number;
  p_asset: number | null;
  n_field: number;
  s_field: number;
  p_field: number | null;
  n_well: number;
  s_well: number;
  p_success: number | null;
  scope: string;
}

export interface RigSlot {
  status: 'OK' | 'NO_SLOT' | 'UNAVAILABLE';
  message?: string;
  rig_id?: string;
  rig_class?: string;
  start_date?: string;
  basis?: string;
}

export interface NbaAction {
  rank: number;
  job_code: string;
  job_name: string;
  ic: string; // IC-01..IC-15
  ic_label: string;
  sources: string[]; // e.g. "ML IC-11 p=0.68", "TC-008 physics route (CHANNELLING)", "G-1 guardrail (Chan coning)"
  ml_prob: number | null;
  diagnostic_fit: DiagnosticFit;
  fit_symbol: FitSymbol;
  fit_evidence: string;
  uplift_bopd: number | null;
  deferred_bbl_12mo: number | null;
  uplift_method: string | null;
  p_success: number | null;
  p_success_n: number;
  p_success_detail: PSuccessDetail;
  rig_days: number;
  requires_rig: boolean;
  unit_type: string; // catalogue equipment, e.g. WORKOVER_RIG, PULLING_UNIT, SURFACE_CREW
  duration_days_min: number;
  duration_days_max: number;
  cost_band: CostBand;
  risk_flags: RiskFlag[];
  mro_status: MroStatus;
  mro_blocker: string | null;
  earliest_start_date: string | null;
  rig_slot: RigSlot | null;
  score: number; // deferred_bbl_12mo × p_success ÷ max(rig_days, 0.5) × risk discount
  why: string;
  sop_doc_id: string | null; // resolves via sopUrl()
  sop_title: string | null;
  sop_url: string | null;
  sop_steps: SopPhase[];
  guardrail: string | null; // "G-1 CONING" | "G-2 RESERVOIR_DECLINE" | null
}

export interface RejectedAction {
  job_code: string | null;
  ic: string;
  source: string;
  reason: string;
  demoted_by?: string | null;
}

export interface JobMenuItem {
  job_code: string;
  job_name: string;
  ic: string;
  ic_label: string;
}

export interface NextBestActions {
  well_id: string;
  field: FieldName;
  lift_type: string;
  as_of: string;
  actions: NbaAction[];
  rejected: RejectedAction[];
  flags: string[]; // e.g. MODEL_PHYSICS_DISAGREEMENT, G1_CONING_GUARDRAIL, G2_RESERVOIR_DECLINE, ML_LOW_CONFIDENCE
  physics_route: {
    mechanism: string;
    source: string;
    evidence: string;
    job_code: string;
    ic: string;
    selection_evidence: string;
  } | null;
  ml_suggestion: { ic: string; label: string; prob: number; job_code: string | null; status: string } | null;
  evidence: Record<string, unknown>;
  score_formula: string;
  notes: string[];
  job_menu: JobMenuItem[]; // catalogue jobs for the "why not X?" picker (from job_catalogue)
}

/* ------------------------------------------------------------------ TC-030 recommendations (v0.5 Multimodal NN) */
export interface RecArchitectureInput {
  modality: string;
  encoder: string;
}

export interface RecArchitecture {
  name: string;
  inputs: RecArchitectureInput[];
  fusion: string;
  training: string;
  serving: string;
}

export interface PInputs {
  p_mechanism: number;
  ml_prob: number | null;
  diagnostic_fit: DiagnosticFit;
  base_rate: number | null;
  base_rate_n: number;
  analog_rate: number;
}

export interface AnalogJob {
  well_id: string;
  workover_id: string;
  job_code: string;
  start_date: string;
  outcome: string;
  uplift_bopd: number | null;
  similarity: number;
}

export interface CandidateAnalogs {
  n: number;
  n_success: number;
  well_ids: string[];
  jobs: AnalogJob[];
}

export interface RecCandidate {
  rank: number;
  job_code: string;
  job_name: string;
  ic: string;
  ic_label: string;
  p_success: number;
  p_inputs: PInputs;
  expected_uplift_bopd: number | null;
  deferred_bbl_12mo: number | null;
  rig_days: number;
  requires_rig: boolean;
  cost_band?: CostBand | null;
  risks: string[];
  why: string;
  fit_symbol: FitSymbol;
  fit_evidence: string;
  sources: string[];
  sop_doc_id: string | null;
  sop_title: string | null;
  sop_url: string | null;
  sop_steps?: SopPhase[];
  earliest_start_date: string | null;
  guardrail: string | null;
  alternative_note: string | null;
  analogs: CandidateAnalogs;
}

export interface RecEvidenceChain {
  signals: string[];
  mechanism: string | null;
  candidates: string[];
}

export interface RecDriver {
  feature: string;
  label: string;
  modality: string;
  value: number | null;
  direction: 'supports' | 'argues against' | string;
  weight: number;
}

export interface Recommendations {
  status: string;
  well_id: string;
  field: string;
  lift_type: string;
  as_of: string;
  engine: string;
  architecture: RecArchitecture;
  candidates: RecCandidate[];
  rejected?: RejectedAction[];
  flags?: string[];
  evidence_chain: RecEvidenceChain;
  drivers: RecDriver[];
  message?: string | null;
  is_synthetic?: boolean;
}

/* ------------------------------------------------------------------ TC-027 counterfactual */
export type CounterfactualDimension =
  | 'diagnostic_fit'
  | 'well_history'
  | 'field_efficacy'
  | 'execution'
  | 'value'
  | 'verdict';

export interface CounterfactualCell {
  summary: string; // one-line, already formatted from tool values
  symbol: FitSymbol | null; // only on the diagnostic_fit row
  values: Record<string, string | number | boolean | null>;
}

export interface CounterfactualRow {
  dimension: CounterfactualDimension;
  title: string;
  recommended: CounterfactualCell;
  alternative: CounterfactualCell;
  winner: 'RECOMMENDED' | 'ALTERNATIVE' | 'TIE' | null;
  evidence_refs: string[]; // tool ids, table rows (e.g. pressure_surveys:PS-…) and doc ids
}

export interface JobRef {
  job_code: string;
  job_name: string;
  ic: string;
  ic_label: string;
  requested_as: string; // what the user typed (e.g. WAX_REMOVAL)
  resolution: string; // how it was mapped to a catalogue job
}

export interface Citation {
  doc_id: string;
  title: string | null;
  doc_type: string | null;
  doc_date: string | null;
  url: string; // /api/docs/{doc_id}.pdf
  why: string;
}

export type CounterfactualVerdict = 'RECOMMENDED_PREFERRED' | 'ALTERNATIVE_PREFERRED' | 'CLOSE' | 'NEITHER_FITS';

export interface Counterfactual {
  well_id: string;
  as_of: string;
  recommended: JobRef;
  alternative: JobRef;
  rows: CounterfactualRow[]; // 6 rows, in SDD §9.2 order
  verdict: CounterfactualVerdict;
  deciding_dimension: CounterfactualDimension;
  margin_pct: number | null;
  verdict_text: string;
  citations: Citation[];
  pressure_survey: Record<string, unknown> | null;
  flags: string[];
}

/* ------------------------------------------------------------------ TC-019 attribution */
export interface AttributionComponent {
  factor_class: FactorClass;
  sub_factor: string;
  bbl: number;
  pct: number;
  controllable: boolean;
  evidence_refs: string[];
  days: number;
  responsible_function: string | null;
}

export interface DeclineAttribution {
  scope: 'WELL' | 'FIELD' | 'CLUSTER';
  well_id: string | null;
  field: FieldName | null;
  cluster_id: string | null;
  window_start: string;
  window_end: string;
  window_days: number;
  baseline_bopd: number;
  total_loss_bbl: number;
  gross_loss_bbl: number;
  components: AttributionComponent[];
  gains: AttributionComponent[];
  gains_bbl: number;
  by_class: Record<string, { bbl: number; pct: number; [k: string]: unknown }>;
  largest_class: FactorClass | null;
  controllable_pct: number;
  uncontrollable_pct: number;
  subsurface_pct: number;
  unexplained_pct: number;
  reconciliation_error_pct: number;
  flags: string[];
  method_notes: string[];
}

/* ------------------------------------------------------------------ TC-020 health buckets */
export interface WellHealth {
  well_id: string;
  bucket: HealthBucket;
  reason: string;
  reason_code: string | null;
  recoverable: boolean | null;
  cluster_id: string | null;
  since: string | null;
  triggers: Record<string, unknown>;
}

export interface HealthBuckets {
  field: FieldName;
  cluster_id: string | null;
  as_of: string;
  counts: HealthCounts;
  sick_or_lost_count: number;
  total_wells: number;
  wells: WellHealth[];
  rule: string;
}

/* ------------------------------------------------------------------ TC-010 priority queue */
export interface PriorityRow extends CandidateRow {
  highest_severity: string | null;
  mechanism_source: string;
}

export interface PriorityQueues {
  rig_queue: PriorityRow[];
  rigless_queue: PriorityRow[];
  excluded_refusals: [string, string, string][]; // [well_id, job_code, reason]
  excluded_unrouted: [string, string][]; // [well_id, reason]
  score_formula: string;
}

/* ------------------------------------------------------------------ fetch helpers */
async function getEnvelope<T>(url: string): Promise<Envelope<T>> {
  const res = await fetch(url, { headers: { 'X-Persona': 'ASSET_MANAGER' } });
  const body = await res.json();
  if (!res.ok && !(body && typeof body === 'object' && 'status' in body)) {
    throw new Error((body && body.detail) || `HTTP ${res.status} for ${url}`);
  }
  return body as Envelope<T>;
}

async function getDirect<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { 'X-Persona': 'ASSET_MANAGER' } });
  const body = await res.json();
  if (!res.ok) {
    throw new Error((body && body.detail) || `HTTP ${res.status} for ${url}`);
  }
  return body as T;
}

export const decisionApi = {
  nba: (wellId: string, topK = 3) => getEnvelope<NextBestActions>(`/api/wells/${wellId}/nba?top_k=${topK}`),
  recommendations: (wellId: string, k = 3) =>
    getDirect<Recommendations>(`/api/wells/${wellId}/recommendations?k=${k}`),
  compare: (wellId: string, alternative: string, recommended?: string) => {
    const q = new URLSearchParams({ alternative });
    if (recommended) q.set('recommended', recommended);
    return getEnvelope<Counterfactual>(`/api/wells/${wellId}/compare?${q.toString()}`);
  },
  wellAttribution: (wellId: string, windowDays = 180) =>
    getEnvelope<DeclineAttribution>(`/api/wells/${wellId}/attribution?window_days=${windowDays}`),
  fieldHealth: (field: FieldName, clusterId?: string) =>
    getEnvelope<HealthBuckets>(`/api/fields/${field}/health${clusterId ? `?cluster_id=${encodeURIComponent(clusterId)}` : ''}`),
  fieldPriority: (field: FieldName, queue: 'rig' | 'rigless' | 'all' = 'all', limit = 20) =>
    getEnvelope<PriorityQueues>(`/api/fields/${field}/priority?queue=${queue}&limit=${limit}`),
};

/** URL of a document PDF (SOP, workover report, CBL …). */
export const docUrl = (docId: string) => `/api/docs/${encodeURIComponent(docId)}.pdf`;

/** Display colours for decision chips (presentation only, no data). */
export const FIT_COLORS: Record<DiagnosticFit, string> = {
  FIT: '#2ea043',
  UNCLEAR: '#d29922',
  CONTRADICTED: '#f85149',
};
export const BAND_COLORS: Record<CostBand, string> = {
  LOW: '#2ea043',
  MED: '#d29922',
  HIGH: '#f85149',
};
export const FACTOR_COLORS: Record<FactorClass, string> = {
  SUBSURFACE: '#38bdf8',
  EQUIPMENT: '#a855f7',
  OPERATIONAL: '#d29922',
  HUMAN_PROCESS: '#f85149',
  EXTERNAL: '#8b949e',
  UNEXPLAINED: '#484f58',
};
