/**
 * chat.ts — Typed client and session handling for WellPulse ADK Copilot (POST /api/chat).
 */

import { getPersona } from '../state/persona';

export type ChatLanguage = 'english' | 'hinglish' | 'hindi';
export type ChatField = 'Geleki' | 'Lakwa' | 'Lakhmani';

export interface ChatRequest {
  message: string;
  session_id?: string;
  language: ChatLanguage;
  field?: ChatField | null;
  well_id?: string | null;
  screen?: string | null;
}

export type ArtifactKind =
  | 'field_history_chart'
  | 'field_comparison'
  | 'health_buckets'
  | 'attribution_waterfall'
  | 'priority_queue'
  | 'well_production_chart'
  | 'well_profile'
  | 'nba'
  | 'counterfactual'
  | 'dossier'
  | 'citations'
  | 'intervention_classification'
  | 'well_map'
  | 'offset_decline'
  | 'well_anomalies'
  | 'wax_sand';

export interface ChatArtifact {
  kind: ArtifactKind;
  tool_id: string;
  tool: string;
  data: any;
  provenance: any;
}

export interface ChatToolCall {
  name: string;
  args: Record<string, any>;
  status: string;
  duration_ms: number;
}

export interface ChatAction {
  kind: 'navigate';
  screen: 'map' | 'field_history' | 'field_compare' | 'field_health' | 'priority' | 'well';
  field: string | null;
  well_id: string | null;
  source_tool: string;
  /** True only when the user explicitly asked for the full well view / history / report. */
  explicit?: boolean;
  /** Focused middle-panel view for this answer (answer canvas). */
  view?: CanvasViewKey;
  /** For the 'compare' view: the recommended job code to compare against. */
  compare_recommended?: string;
}

/**
 * Does the user's own message ask for the full well view (history, deep dive, report)?
 * Agent answers never open the Deep Dive drawer unless this is true (UI rule, 2026-10-08).
 * English + Hinglish/Hindi phrasing.
 */
const EXPLICIT_DETAIL_RE =
  /\b(history|histories|deep[\s-]?dive|full\s+(view|details?|report|profile|picture)|complete\s+(history|details?|report)|well\s+report|report|dossier|pre[\s-]?field|field\s+pack|everything|open\s+(the\s+)?(well|drawer|details?))\b|itihaas|poora|pura|sab\s*kuch|इतिहास|पूरा|रिपोर्ट/i;

export function isExplicitDetailRequest(text: string | null | undefined): boolean {
  return !!text && EXPLICIT_DETAIL_RE.test(text);
}

/** Focused middle-panel view (mirrors CanvasView in WellDeepDiveDrawer). */
export type CanvasViewKey =
  | 'overview'
  | 'production'
  | 'interventions'
  | 'wellbore'
  | 'pressures'
  | 'diagnosis'
  | 'recommendation'
  | 'compare'
  | 'offsets'
  | 'history'
  | 'nearby';

const KW: [CanvasViewKey, RegExp][] = [
  // v0.6 ED-7: 'what is wrong' vs. offsets, and wax / sand / anomalies
  ['offsets', /\b(offsets?|is\s+it\s+the\s+(well|reservoir)|(compare|vs\.?|versus)\s+(the\s+)?(decline\s+)?(with\s+)?(nearby|neighbou?ring|surrounding)|decline\s+(with|vs\.?)\s+nearby)\b/i],
  ['history', /\b(wax\w*|paraffin|sand\w*|anomal\w*|unusual|abnormal)\b/i],
  ['compare', /\bwhy\s+not\b|\binstead\s+of\b|\bcompare\b|\balternative/i],
  ['recommendation', /\b(next\s+best|recommend\w*|what\s+should\s+we\s+do|suggest\w*|intervention\s+options?|best\s+(intervention|option|action))\b|kya\s+karna/i],
  ['interventions', /\b(interventions?|workovers?|jobs?|job\s+history|past\s+work|well\s+service)\b/i],
  ['wellbore', /\b(casing|tubing|completion|wellbore|schematic|perforations?|perfs?|lithology|formation|construction|diagram|packer)\b/i],
  ['pressures', /\b(pressure|well\s+test|test|survey|temperature|thp|chp|bhp)\b/i],
  ['nearby', /\b(nearby|neighbou?rs?|around)\b|aas\s*paas/i],
  ['diagnosis', /\b(why\s+(did|is)|declin\w*|diagnos\w*|root\s+cause|attribution|human\s+factor|controllable|what'?s\s+wrong)\b/i],
  ['production', /\b(production|rate|bopd|oil|water\s*cut|gor|plot|chart|graph|trend)\b/i],
];

/**
 * Which single view answers this turn. Tool kind decides when it is specific (production chart, NBA,
 * counterfactual, attribution); for broad tools (well_profile / well_summary) the user's words decide.
 */
const TOOL_TO_KIND: Record<string, string> = {
  plot_production: 'well_production_chart',
  recommend_next_best_action: 'nba',
  compare_interventions: 'counterfactual',
  attribute_decline: 'attribution_waterfall',
  classify_intervention: 'intervention_classification',
  well_summary: 'well_profile',
  compare_offset_decline: 'offset_decline',
  well_anomalies: 'well_anomalies',
  wax_sand_behaviour: 'wax_sand',
};

export function pickCanvasView(toolKind: string, userText: string | null | undefined): CanvasViewKey {
  const t = userText || '';
  const byWords = KW.find(([, re]) => re.test(t))?.[0];
  switch (TOOL_TO_KIND[toolKind] ?? toolKind) {
    case 'counterfactual':
      return 'compare';
    case 'nba':
    case 'intervention_classification':
      return byWords === 'compare' ? 'compare' : 'recommendation';
    case 'attribution_waterfall':
      return 'diagnosis';
    case 'offset_decline':
      return 'offsets';
    case 'well_anomalies':
    case 'wax_sand':
      return 'history';
    case 'well_production_chart':
      return byWords === 'interventions' ? 'interventions' : 'production';
    default:
      return byWords ?? 'overview';
  }
}

export interface ChatReply {
  session_id: string;
  response: string;
  status: 'ok' | 'degraded';
  engine: string;
  language: string;
  persona: string;
  artifacts: ChatArtifact[];
  tool_calls: ChatToolCall[];
  actions: ChatAction[];
  recommendation: any | null; // same Recommendation object as before (no USD)
  number_check: { ok: boolean; unmatched: string[] };
}

const STORAGE_KEY = 'wellpulse.chat.session';

export function getChatSessionId(): string {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      let s = window.sessionStorage.getItem(STORAGE_KEY);
      if (!s) {
        s =
          typeof crypto !== 'undefined' && crypto.randomUUID
            ? crypto.randomUUID()
            : `chat-session-${Date.now()}`;
        window.sessionStorage.setItem(STORAGE_KEY, s);
      }
      return s;
    }
  } catch {
    /* sessionStorage unavailable */
  }
  return `chat-session-${Date.now()}`;
}

export function setChatSessionId(sessionId: string): void {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage && sessionId) {
      window.sessionStorage.setItem(STORAGE_KEY, sessionId);
    }
  } catch {
    /* ignore */
  }
}

export async function postChat(req: ChatRequest): Promise<ChatReply> {
  const sessionId = req.session_id || getChatSessionId();
  const payload: ChatRequest = {
    ...req,
    session_id: sessionId,
  };

  const persona = getPersona();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Persona': persona,
  };

  const response = await fetch('/api/chat', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errBody = '';
    try {
      errBody = await response.text();
    } catch {
      /* ignore */
    }
    throw new Error(`Chat API error (${response.status}): ${errBody || response.statusText}`);
  }

  const reply: ChatReply = await response.json();
  if (reply.session_id) {
    setChatSessionId(reply.session_id);
  }
  return reply;
}
