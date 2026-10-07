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
  | 'well_map';

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
