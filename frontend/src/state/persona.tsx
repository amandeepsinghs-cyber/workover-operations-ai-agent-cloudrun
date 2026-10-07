/**
 * persona.tsx — demo persona switch (SDD §14.2 / §16.1, F-16, Stage Y).
 *
 * - One module-level store (so non-React code — fetch wrapper, Live client — can read it).
 * - `installPersonaFetch()` wraps `window.fetch` once: every same-origin `/api/*` request gets
 *   `X-Persona: <persona>` unless the caller already set that header. No component needs editing.
 * - `PersonaProvider` / `usePersona()` expose `{persona, setPersona, capabilities}`; capabilities come from
 *   `GET /api/me/capabilities` and are a UI hint only (enforcement is server-side, SDD §16).
 * - Persisted in localStorage so a reload keeps the demo persona.
 */
import React, { createContext, useContext, useEffect, useState } from 'react';

export type Persona = 'ED' | 'ASSET_MANAGER' | 'FIELD_ENGINEER';
export const PERSONAS: Persona[] = ['ED', 'ASSET_MANAGER', 'FIELD_ENGINEER'];
export const DEFAULT_PERSONA: Persona = 'ASSET_MANAGER';

export interface Capabilities {
  persona: Persona;
  label: string;
  capabilities: string[];
  denied: string[];
  access: Record<string, 'FULL' | 'SUMMARY' | 'OWN_CLUSTER' | 'NONE'>;
  denied_doc_types: string[];
  personas: { id: Persona; label: string }[];
}

const STORAGE_KEY = 'wellpulse.persona';

function initialPersona(): Persona {
  try {
    const v = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (v && (PERSONAS as string[]).includes(v)) return v as Persona;
  } catch {
    /* storage unavailable */
  }
  return DEFAULT_PERSONA;
}

let currentPersona: Persona = initialPersona();
const listeners = new Set<(p: Persona) => void>();

export function getPersona(): Persona {
  return currentPersona;
}

export function setPersona(p: Persona): void {
  if (p === currentPersona) return;
  currentPersona = p;
  try {
    window.localStorage.setItem(STORAGE_KEY, p);
  } catch {
    /* ignore */
  }
  listeners.forEach((fn) => fn(p));
}

export function subscribePersona(fn: (p: Persona) => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

function isApiUrl(input: RequestInfo | URL): boolean {
  let url: string;
  if (typeof input === 'string') url = input;
  else if (input instanceof URL) url = input.toString();
  else url = input.url;
  if (url.startsWith('/api/')) return true;
  try {
    const u = new URL(url, window.location.href);
    return u.pathname.startsWith('/api/') && (u.host === window.location.host || u.port === '8002');
  } catch {
    return false;
  }
}

let installed = false;

/** Wrap window.fetch so every /api/* call carries X-Persona (idempotent). */
export function installPersonaFetch(): void {
  if (installed || typeof window === 'undefined' || !window.fetch) return;
  installed = true;
  const original = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (!isApiUrl(input)) return original(input, init);
    const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
    if (!headers.has('X-Persona')) headers.set('X-Persona', currentPersona);
    return original(input, { ...init, headers });
  };
}

installPersonaFetch();

interface PersonaCtx {
  persona: Persona;
  setPersona: (p: Persona) => void;
  capabilities: Capabilities | null;
  /** UI hint: may this persona use the capability? (true while capabilities are loading) */
  can: (capability: string) => boolean;
}

const Ctx = createContext<PersonaCtx>({
  persona: currentPersona,
  setPersona,
  capabilities: null,
  can: () => true,
});

export const PersonaProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [persona, setLocal] = useState<Persona>(currentPersona);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);

  useEffect(() => subscribePersona(setLocal), []);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/me/capabilities', { headers: { 'X-Persona': persona } })
      .then((r) => r.json())
      .then((env) => {
        if (!cancelled && env && env.data) setCapabilities(env.data as Capabilities);
      })
      .catch((err) => console.warn('capabilities fetch failed:', err));
    return () => {
      cancelled = true;
    };
  }, [persona]);

  const can = (capability: string) => {
    if (!capabilities || capabilities.persona !== persona) return true;
    return (capabilities.access[capability] ?? 'FULL') !== 'NONE';
  };

  return <Ctx.Provider value={{ persona, setPersona, capabilities, can }}>{children}</Ctx.Provider>;
};

export function usePersona(): PersonaCtx {
  return useContext(Ctx);
}
