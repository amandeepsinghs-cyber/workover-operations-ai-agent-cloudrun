/**
 * v0.6 Stage ED: client for the ED meeting pack (F-29 offset decline; F-30 anomalies and F-31 wax/sand follow).
 */
import { getPersona } from '../state/persona';
import type { Envelope } from './asset';

async function getEnvelope<T>(url: string): Promise<Envelope<T>> {
  const res = await fetch(url, { headers: { 'X-Persona': getPersona() } });
  const body = await res.json();
  if (!res.ok && !(body && typeof body === 'object' && 'status' in body)) {
    throw new Error((body && body.detail) || `HTTP ${res.status} for ${url}`);
  }
  return body as Envelope<T>;
}

/* ------------------------------------------------------------------ TC-033 offset decline */
export type OffsetVerdict = 'WELL_SPECIFIC' | 'RESERVOIR_WIDE' | 'WATER' | 'RESTORED' | 'MIXED' | 'INSUFFICIENT';

export interface MonthPoint {
  month: string;
  oil_bopd: number | null;
  oil_norm: number | null;
  wc_pct: number | null;
  thp_kgcm2: number | null;
}

export interface WellTrend {
  well_id: string;
  decline_pct_yr: number | null;
  wc_change_pts: number | null;
  thp_change: number | null;
  oil_now_bopd: number | null;
  series: MonthPoint[];
}

export interface OffsetWell extends WellTrend {
  distance_m: number | null;
  last_job: { job_code: string; date: string; outcome: string; uplift_bopd: number | null } | null;
}

export interface OffsetDecline {
  well_id: string;
  as_of: string;
  months: number;
  verdict: OffsetVerdict;
  water_scope: 'AREA' | 'WELL' | null;
  headline: string;
  subject: WellTrend & { residual_pct: number | null };
  offsets: OffsetWell[];
  offsets_median: { decline_pct_yr: number | null; wc_change_pts: number | null; residual_pct: number | null };
  mechanical: { signature: string; evidence: string } | null;
  status_now: { status: string; since: string; reason: string | null } | null;
}

/* ------------------------------------------------------------------ TC-034 anomalies */
export type AnomalyType = 'RATE_DROP' | 'WC_JUMP' | 'WC_TREND' | 'THP_SHIFT' | 'DOWNTIME';

export interface AnomalyEvent {
  type: AnomalyType;
  date: string;
  before?: number | null;
  after?: number | null;
  days?: number;
  status?: string;
  reason?: string | null;
  deferred_bbl?: number | null;
  ongoing?: boolean;
  linked_job?: { job_code: string; date: string; outcome: string };
  severity: number;
  text: string;
}

export interface WellAnomalies {
  well_id: string;
  months: number;
  counts: Record<AnomalyType, number>;
  n_total: number;
  events: AnomalyEvent[];
  summary: string;
}

/* ------------------------------------------------------------------ TC-035 wax / sand */
export type DepositVerdict = 'NOT_PRONE' | 'FLAGGED_NO_JOBS' | 'DOWNTIME_ONLY' | 'ISOLATED' | 'REPEAT' | 'PREDICTABLE';

export interface DepositBlock {
  kind: 'WAX' | 'SAND';
  flag: boolean | null;
  verdict: DepositVerdict;
  n_jobs: number;
  last_job: { job_code: string; date: string; outcome: string; uplift_bopd: number | null } | null;
  own_interval_days: number | null;
  field_interval_days: number | null;
  next_due: string | null;
  overdue_days: number | null;
  downtime_episodes: number;
  downtime_days: number;
  deferred_bbl: number;
  ongoing: { status: string; since: string } | null;
  job_dates: string[];
  text: string;
}

export interface WaxSand {
  well_id: string;
  field: string;
  wax: DepositBlock;
  sand: DepositBlock;
  summary: string;
  data_note: string;
}

export const edApi = {
  offsetDecline: (wellId: string, months = 24) =>
    getEnvelope<OffsetDecline>(`/api/wells/${encodeURIComponent(wellId)}/offset-decline?months=${months}`),
  anomalies: (wellId: string, months = 24) =>
    getEnvelope<WellAnomalies>(`/api/wells/${encodeURIComponent(wellId)}/anomalies?months=${months}`),
  waxSand: (wellId: string) => getEnvelope<WaxSand>(`/api/wells/${encodeURIComponent(wellId)}/wax-sand`),
};
