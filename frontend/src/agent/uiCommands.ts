/**
 * v0.6 ED-11 (F-41, D-40): hands-off screen control.
 *
 * - `UI_ACTIONS`: the allow-list. Keep in sync with backend/app/agent/ui_control.py (unit test compares them).
 * - `parseUiCommands(text)`: browser parser (EN / Hinglish / Hindi). Returns commands only when the whole
 *   message is commands ("plain command"); anything else returns null and goes to the agent.
 * - `dispatchUi` / `useUiCommands`: a tiny window event bus. App, WellMap, FloatingAgent and the agent panel
 *   each handle their own actions.
 */
import { useEffect, useRef } from 'react';

export const UI_ACTIONS = {
  map_view: ['india', 'assam'],
  fullscreen: ['on', 'off'],
  basemap: ['satellite', 'scada'],
  flowlines: ['on', 'off'],
  legend: ['on', 'off'],
  zoom: ['in', 'out'],
  focus_field: ['Geleki', 'Lakwa', 'Lakhmani', 'ALL'],
  focus_cluster: null,
  focus_well: null,
  open_well: null,
  open_screen: ['field_history', 'field_compare', 'field_health'],
  panel: ['expand', 'restore', 'close'],
  language: ['english', 'hinglish', 'hindi'],
  report: ['open', 'print', 'close'],
  agent: ['dock', 'undock'],
  health_filter: ['all', 'healthy', 'attention', 'not_producing'], // ED-14 (D-41)
} as const;

export type UiAction = keyof typeof UI_ACTIONS;

export interface UiCommand {
  action: UiAction;
  value?: string;
  well_id?: string;
  view?: string;
  label?: string;
}

// ------------------------------------------------------------------------------------------------
// Event bus
// ------------------------------------------------------------------------------------------------
const EVT = 'wellpulse:ui';

export function dispatchUi(cmd: UiCommand): void {
  if (!cmd || !(cmd.action in UI_ACTIONS)) return; // allow-list guard (D-40)
  window.dispatchEvent(new CustomEvent<UiCommand>(EVT, { detail: { ...cmd, label: cmd.label ?? labelOf(cmd) } }));
}

/** Subscribe to UI commands; the handler may change between renders (kept in a ref). */
export function useUiCommands(handler: (cmd: UiCommand) => void): void {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const fn = (e: Event) => ref.current((e as CustomEvent<UiCommand>).detail);
    window.addEventListener(EVT, fn);
    return () => window.removeEventListener(EVT, fn);
  }, []);
}

// ------------------------------------------------------------------------------------------------
// Labels (chat chips)
// ------------------------------------------------------------------------------------------------
const LABELS: Record<string, string> = {
  'map_view:india': 'India view',
  'map_view:assam': 'Assam Asset view',
  'fullscreen:on': 'Full screen on',
  'fullscreen:off': 'Full screen off',
  'basemap:satellite': 'Satellite map',
  'basemap:scada': 'SCADA map',
  'flowlines:on': 'Flowlines on',
  'flowlines:off': 'Flowlines off',
  'legend:on': 'Legend shown',
  'legend:off': 'Legend hidden',
  'zoom:in': 'Zoomed in',
  'zoom:out': 'Zoomed out',
  'panel:expand': 'Panel expanded',
  'panel:restore': 'Map restored',
  'panel:close': 'Panel closed',
  'report:open': 'Field report opened',
  'report:print': 'Field report printing',
  'report:close': 'Field report closed',
  'agent:dock': 'Agent docked',
  'agent:undock': 'Agent undocked',
  'open_screen:field_history': 'Field history',
  'open_screen:field_compare': 'Compare fields',
  'open_screen:field_health': 'Health & priority',
  'health_filter:all': 'Showing all wells',
  'health_filter:healthy': 'Showing: Healthy',
  'health_filter:attention': 'Showing: Needs attention',
  'health_filter:not_producing': 'Showing: Not producing',
};

export function labelOf(c: UiCommand): string {
  const k = `${c.action}:${c.value ?? ''}`;
  if (LABELS[k]) return LABELS[k];
  if (c.action === 'focus_field') return c.value === 'ALL' ? 'All fields' : `${c.value} field`;
  if (c.action === 'focus_well') return `${c.well_id} on map`;
  if (c.action === 'focus_cluster') return `${c.value} wells`;
  if (c.action === 'open_well') return `${c.well_id ?? 'Well'} · ${c.view ?? 'overview'}`;
  if (c.action === 'language') return `Language: ${(c.value ?? '').replace(/^./, (s) => s.toUpperCase())}`;
  return `${c.action} ${c.value ?? ''}`.trim();
}

// ------------------------------------------------------------------------------------------------
// Browser parser (plain commands only)
// ------------------------------------------------------------------------------------------------
const WELL_RE = /\b(gk|lkw|lkm)[\s-]?(\d{3})\b/i;

/** Words that carry no meaning in a UI command (EN / Hinglish / Hindi). */
const FILLERS = new Set(
  (
    'please pls plz kindly can could you would will now just the a an to on of in into at for me my us it this that ' +
    'show display open go switch turn set change make put take bring back again let lets let\'s view mode screen ' +
    'map page tab ok okay baat bolo speak talk language bhasha reply answer karein kariye  hey wellpulse agent ji karo kar kardo kar do do dikhao dikha dikhaiye dikhana kholo ' +
    'chalo jao le lo par pe mein me ka ki ke ko bhi toh hai sir also then and aur phir fir with up over ' +
    'only sirf just keval filter दिखाओ करो कर दो खोलो पर में का की के को भी केवल सिर्फ'
  ).split(/\s+/),
);

interface Rule {
  re: RegExp;
  build: (m: RegExpMatchArray, clause: string) => UiCommand | null;
}

const off = (s: string) => /\b(off|hide|band|hatao|remove|disable|exit|leave|close|nahi)\b|बंद|हटाओ/.test(s);

const VIEW_WORDS: [RegExp, string][] = [
  [/\b(wellbore|completion|schematic|diagram|casing|tubing|perforations?)\b|कंप्लीशन/, 'wellbore'],
  [/\b(production|decline curve|rate history)\b|प्रोडक्शन/, 'production'],
  [/\b(interventions?|jobs?|workovers?)\b/, 'interventions'],
  [/\b(pressures?|thp|chp)\b/, 'pressures'],
  [/\b(recommendations?|nba|next best action)\b/, 'recommendation'],
  [/\b(offsets?|nearby wells?|neighbou?rs?)\b/, 'offsets'],
  [/\b(history|anomal(y|ies)|wax|sand)\b|इतिहास/, 'history'],
  [/\b(diagnosis|diagnostics)\b/, 'diagnosis'],
  [/\b(summary)\b/, 'summary'],
  [/\b(overview|details?)\b/, 'overview'],
];

// Order matters: specific before generic.
const RULES: Rule[] = [
  {
    re: /\b(full\s*-?\s*screen|fullscreen|maximi[sz]e (the )?map|poori screen|puri screen)\b|पूरी स्क्रीन|फुल स्क्रीन/,
    build: (_m, s) => ({ action: 'fullscreen', value: off(s) ? 'off' : 'on' }),
  },
  { re: /\b(exit|normal view)\b/, build: () => ({ action: 'fullscreen', value: 'off' }) },
  { re: /\b(all\s*)?india\b|भारत|इंडिया/, build: () => ({ action: 'map_view', value: 'india' }) },
  { re: /\bassam( asset)?\b|असम/, build: () => ({ action: 'map_view', value: 'assam' }) },
  { re: /\bsatellite\b|सैटेलाइट/, build: () => ({ action: 'basemap', value: 'satellite' }) },
  { re: /\b(scada|dark map|dark mode)\b/, build: () => ({ action: 'basemap', value: 'scada' }) },
  {
    re: /\b(flow\s*lines?|pipelines?)\b/,
    build: (_m, s) => ({ action: 'flowlines', value: off(s) ? 'off' : 'on' }),
  },
  { re: /\blegend\b/, build: (_m, s) => ({ action: 'legend', value: off(s) ? 'off' : 'on' }) },
  {
    // ED-14 (D-41): "only show non producing wells", "sirf band wells dikhao", "केवल बंद कुएँ दिखाओ", "show all wells"
    re: /\b(?:(?:only|sirf|just|keval)\s+(?:the\s+)?)?(non[\s-]?producing|not[\s-]?producing|shut[\s-]?in|band|dead|failed|healthy|green|needs?[\s-]?attention|attention|at[\s-]?risk|amber|red|all|sab|saare|sabhi)\s+wells?\b|\b(?:only|sirf|just)\s+(?:the\s+)?(non[\s-]?producing|not[\s-]?producing|healthy|needs?[\s-]?attention)\b|\b(?:clear|remove|reset)\s+(?:the\s+)?filter\b|\bfilter\s+(?:hatao|clear|off|remove)\b|(?:केवल|सिर्फ)?\s*(बंद|स्वस्थ|हेल्दी|सब|सभी)\s*कु(?:एँ|एं|ए)/,
    build: (m) => {
      const t = (m[1] || m[2] || m[3] || 'all').toLowerCase();
      const v = /non|not|shut|band|dead|failed|red|बंद/.test(t)
        ? 'not_producing'
        : /health|green|स्वस्थ|हेल्दी/.test(t)
          ? 'healthy'
          : /attention|risk|amber/.test(t)
            ? 'attention'
            : 'all';
      return { action: 'health_filter', value: v };
    },
  },
  { re: /\bzoom\s*in\b/, build: () => ({ action: 'zoom', value: 'in' }) },
  { re: /\bzoom\s*out\b/, build: () => ({ action: 'zoom', value: 'out' }) },
  {
    re: /\b(close|hide|band karo|hatao)\s*(the\s*)?(right\s*)?(panel|drawer|sidebar)\b|\b(panel|drawer)\s*(band|close|hatao)\b/,
    build: () => ({ action: 'panel', value: 'close' }),
  },
  {
    re: /\b(expand|maximi[sz]e|enlarge|bada karo|badha)\s*(the\s*)?(right\s*)?(panel|drawer)\b|\b(panel|drawer)\s*(bada|expand)\b/,
    build: () => ({ action: 'panel', value: 'expand' }),
  },
  {
    re: /\b(restore|shrink|minimi[sz]e|chhota karo)\s*(the\s*)?(right\s*)?(panel|drawer)\b|\b(restore|bring back) (the )?map\b/,
    build: () => ({ action: 'panel', value: 'restore' }),
  },
  { re: /\b(close|band karo)\s*(the\s*)?(field\s*)?report\b/, build: () => ({ action: 'report', value: 'close' }) },
  { re: /\bprint\s*(the\s*)?(field\s*)?(report|well pack)?\b/, build: () => ({ action: 'report', value: 'print' }) },
  {
    // ED-13: "show GGS-01", "LKW-GGS-II ke wells", "cluster GK-NE"
    re: /\b((?:gk|lkw|lkm)-)?ggs[\s-]?(\d{1,2}|i{1,3}|iv|v)\b|\bcluster\s+([a-z]{2,3}-[a-z]{1,3})\b/,
    build: (m) => {
      const v = m[3] ? m[3] : `${m[1] ?? ''}GGS-${m[2]}`;
      return { action: 'focus_cluster', value: v.toUpperCase() };
    },
  },
  { re: /\bundock\b/, build: () => ({ action: 'agent', value: 'undock' }) },
  { re: /\bdock\b/, build: () => ({ action: 'agent', value: 'dock' }) },
  {
    re: /\b(field\s*(production\s*)?history|production history of (the )?field)\b/,
    build: () => ({ action: 'open_screen', value: 'field_history' }),
  },
  {
    re: /\b(compare\s*(the\s*)?fields|field\s*comparison)\b/,
    build: () => ({ action: 'open_screen', value: 'field_compare' }),
  },
  {
    re: /\b(health\s*(and|&)?\s*priority|field\s*health|priority\s*(list|queue)?)\b/,
    build: () => ({ action: 'open_screen', value: 'field_health' }),
  },
  {
    re: /\b(hinglish|hindi|english)\b|हिंदी|हिन्दी/,
    build: (m, s) => {
      if (!/\b(language|bhasha|switch|speak|talk|bolo|baat|mein|me|in|reply|answer|change)\b|भाषा|में/.test(s) && s.trim() !== m[0])
        return null;
      const v = /hinglish/.test(s) ? 'hinglish' : /hindi|हिंदी|हिन्दी/.test(s) ? 'hindi' : 'english';
      return { action: 'language', value: v };
    },
  },
  {
    re: /\b(geleki|lakwa|lakhmani|lakmani|all fields)\b|गेलेकी|लकवा|लखमनी/,
    build: (m) => {
      const t = m[0];
      const v = /gel|गेले/.test(t) ? 'Geleki' : /lakw|लकवा/.test(t) ? 'Lakwa' : /all/.test(t) ? 'ALL' : 'Lakhmani';
      return { action: 'focus_field', value: v };
    },
  },
];

/** Words consumed by a well-view clause besides the view keyword itself. */
const WELL_VIEW_EXTRA = /\b(well|tab|section|view|curve|chart|plot|ka|ki|ke)\b/g;

/** ED-14: speech often spells ids out ("GK one two nine", "GGS teen") → digits after an id prefix. */
const DIGIT_WORDS: Record<string, string> = {
  zero: '0', oh: '0', one: '1', two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7', eight: '8',
  nine: '9', ek: '1', do: '2', teen: '3', char: '4', chaar: '4', paanch: '5', panch: '5', chhe: '6', saat: '7',
  aath: '8', nau: '9',
};
export function spokenIds(text: string): string {
  const words = Object.keys(DIGIT_WORDS).join('|');
  const re = new RegExp(`\\b(gk|lkw|lkm|ggs)((?:[\\s-]+(?:${words}))+)\\b`, 'gi');
  return text.replace(re, (_m, p: string, ds: string) => {
    const d = ds.trim().split(/[\s-]+/).map((w) => DIGIT_WORDS[w.toLowerCase()]).join('');
    const pad = /ggs/i.test(p) ? d.padStart(2, '0') : d.padStart(3, '0');
    return `${p}-${pad}`;
  });
}

function splitClauses(text: string): string[] {
  return spokenIds(text)
    .toLowerCase()
    .replace(/[?!.]+$/g, '')
    .replace(/\bhealth\s+and\s+priority\b/g, 'health & priority')
    .split(/\s*(?:,|;|\band then\b|\bthen\b|\band\b|\baur\b|\bphir\b|\bfir\b|और|फिर)\s*/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function leftover(clause: string, consumed: RegExp | string): string[] {
  const rest = typeof consumed === 'string' ? clause.replace(consumed, ' ') : clause.replace(consumed, ' ');
  return rest
    .replace(/[^\p{L}\p{M}\p{N}\s'-]/gu, ' ')
    .split(/\s+/)
    .filter((w) => w && !FILLERS.has(w));
}

function parseClause(clause: string, currentWellId?: string | null): UiCommand[] | null {
  // 1) Well clauses: "<id> [view]" / "<id> on the map" / "<view> [of this well]"
  const wm = clause.match(WELL_RE);
  const view = VIEW_WORDS.find(([re]) => re.test(clause));
  const ruleHit = RULES.some((r) => r.re.test(clause));
  if (wm || (view && currentWellId && !ruleHit)) {
    const id = wm ? `${wm[1].toUpperCase()}-${wm[2]}` : (currentWellId as string);
    let rest = wm ? clause.replace(WELL_RE, ' ') : clause;
    if (view) rest = rest.replace(new RegExp(view[0].source, 'g'), ' ');
    const onMap = /\b(on|par|pe)?\s*(the\s*)?map\b|\b(locate|find|where is|zoom to|focus)\b/.test(rest);
    rest = rest.replace(/\b(on|par|pe)?\s*(the\s*)?map\b|\b(locate|find|where is|zoom to|focus)\b/g, ' ');
    rest = rest.replace(WELL_VIEW_EXTRA, ' ');
    if (leftover(rest, /$^/).length > 0) return null; // a question about the well → agent
    if (!wm && !view) return null;
    if (onMap && !view) return [{ action: 'focus_well', well_id: id }];
    return [{ action: 'open_well', well_id: id, view: view ? view[1] : 'overview' }];
  }
  // 2) Field / map / panel / app rules: every match in the clause must explain all non-filler words
  const out: UiCommand[] = [];
  let rest = clause;
  for (const r of RULES) {
    const m = rest.match(r.re);
    if (!m) continue;
    const cmd = r.build(m, clause);
    if (!cmd) continue;
    // "zoom to Lakwa" / "go to Geleki on the map" → focus_field only (drop map_view duplicates)
    out.push(cmd);
    rest = rest.replace(r.re, ' ');
  }
  if (out.length === 0) return null;
  const SWITCH_WORDS = /^(zoom|field|well|asset|map|off|hide|band|hatao|remove|disable|enable|exit|leave|close|nahi|बंद|हटाओ)$/;
  if (leftover(rest, /$^/).filter((w) => !SWITCH_WORDS.test(w)).length > 0) return null;
  // focus_field implies the Assam drill-down; drop an explicit assam map_view next to it
  if (out.some((c) => c.action === 'focus_field')) return out.filter((c) => !(c.action === 'map_view' && c.value === 'assam'));
  return out;
}

/**
 * Plain-command parser (D-40). Returns the commands when every clause of the message is a UI command;
 * null when any part is a question or unknown (the message then goes to the agent).
 */
export function parseUiCommands(text: string, currentWellId?: string | null): UiCommand[] | null {
  if (!text || !text.trim()) return null;
  const clauses = splitClauses(text.replace(/^🎙️\s*/, ''));
  if (clauses.length === 0 || clauses.length > 6) return null;
  if (/\b(what|why|how|which|who|when|kya|kyu|kyon|kaise|kaun|kab|kitna|kitne|batao|explain|tell)\b|क्या|क्यों|कैसे/.test(text.toLowerCase()))
    return null;
  const all: UiCommand[] = [];
  for (const c of clauses) {
    const cmds = parseClause(c, currentWellId);
    if (!cmds) return null;
    all.push(...cmds);
  }
  // One command per action+target (e.g. "exit full screen" matches two rules)
  const seen = new Set<string>();
  const uniq = all.filter((c) => {
    const k = `${c.action}:${c.value ?? ''}:${c.well_id ?? ''}:${c.view ?? ''}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return uniq.length ? uniq.map((c) => ({ ...c, label: labelOf(c) })) : null;
}
