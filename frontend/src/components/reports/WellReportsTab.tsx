import React, { useEffect, useMemo, useState } from 'react';
import {
  FileText,
  Clock,
  Gauge,
  FlaskConical,
  AlertTriangle,
  Layers,
  ExternalLink,
  Download,
  ScanLine,
  Search,
  Loader2,
  Library,
} from 'lucide-react';
import { WellDetail } from '../../types/well';

/**
 * Well Reports tab (Stage O, F-10): real documents from the synthetic PDF corpus.
 *
 * Data: GET /api/wells/{id}/documents -> DocumentHit[] (SDD §13.1 envelope).
 * PDFs: GET /api/docs/{doc_id}.pdf (#page=N), rendered inline in an iframe.
 * Every number shown inside a PDF is a fact slot traced to a source table (facts.json).
 */

interface WellReportsTabProps {
  well: WellDetail;
}

export interface DocumentHit {
  doc_id: string;
  title: string;
  doc_type: string; // D1..D11
  doc_type_id: string; // D01..D11
  doc_type_name: string;
  doc_date: string;
  well_id: string | null;
  field: string;
  page: number;
  pages: number;
  score: number | null;
  snippet: string | null;
  uri: string;
  pdf_url: string;
  has_text_layer: boolean;
  scanned: boolean;
  flags: string[];
  workover_id: string | null;
  intervention_class: string | null;
  job_code: string | null;
}

interface Envelope<T> {
  status: string;
  data: T;
  message: string;
}

type ReportSubTab = 'workover' | 'bhp' | 'lab' | 'completion' | 'all';

const SUB_TABS: {
  key: ReportSubTab;
  label: string;
  types: string[];
  icon: React.ReactNode;
  active: string;
}[] = [
  {
    key: 'workover',
    label: 'Workover Reports',
    types: ['D2', 'D3', 'D8'],
    icon: <Clock className="w-3.5 h-3.5" />,
    active: 'bg-accent/20 text-accent border border-accent/40 shadow-sm',
  },
  {
    key: 'bhp',
    label: 'Well Test & Pressure',
    types: ['D7'],
    icon: <Gauge className="w-3.5 h-3.5" />,
    active: 'bg-purple-950/60 text-purple-300 border border-purple-700/60 shadow-sm',
  },
  {
    key: 'lab',
    label: 'Chemical Treatment',
    types: ['D6'],
    icon: <FlaskConical className="w-3.5 h-3.5" />,
    active: 'bg-amber-950/60 text-amber-300 border border-amber-700/60 shadow-sm',
  },
  {
    key: 'completion',
    label: 'Completion & Wellbore',
    types: ['D1', 'D4', 'D5'],
    icon: <FileText className="w-3.5 h-3.5" />,
    active: 'bg-blue-950/60 text-blue-300 border border-blue-700/60 shadow-sm',
  },
  {
    key: 'all',
    label: 'All Documents',
    types: [],
    icon: <Library className="w-3.5 h-3.5" />,
    active: 'bg-emerald-950/60 text-emerald-300 border border-emerald-700/60 shadow-sm',
  },
];

const TYPE_LABELS: Record<string, string> = {
  D1: 'Completion report',
  D2: 'Workover report',
  D3: 'Daily workover report',
  D4: 'Wellbore schematic',
  D5: 'Cement bond log',
  D6: 'Chemical treatment',
  D7: 'Well test / pressure',
  D8: 'Failure RCA',
  D9: 'Field study',
  D10: 'Monthly report',
  D11: 'SOP',
};

const typeOrder = (t: string) => parseInt(t.replace('D', ''), 10) || 99;

export const WellReportsTab: React.FC<WellReportsTabProps> = ({ well }) => {
  const [activeSubTab, setActiveSubTab] = useState<ReportSubTab>('workover');
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [docs, setDocs] = useState<DocumentHit[]>([]);
  const [status, setStatus] = useState<'loading' | 'ok' | 'empty' | 'error'>('loading');
  const [message, setMessage] = useState<string>('');
  const [selected, setSelected] = useState<DocumentHit | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [query, setQuery] = useState<string>('');
  const [searchHits, setSearchHits] = useState<DocumentHit[] | null>(null);
  const [searching, setSearching] = useState<boolean>(false);

  // ------------------------------------------------------------------ load the well's documents
  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    setSelected(null);
    setSearchHits(null);
    setQuery('');
    fetch(`/api/wells/${encodeURIComponent(well.id)}/documents?limit=5000`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as Envelope<DocumentHit[]>;
      })
      .then((env) => {
        if (cancelled) return;
        const list = Array.isArray(env.data) ? env.data : [];
        setDocs(list);
        setMessage(env.message || '');
        setStatus(list.length ? 'ok' : 'empty');
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('Failed to load well documents:', err);
        setDocs([]);
        setMessage(String(err));
        setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [well.id]);

  const tab = SUB_TABS.find((t) => t.key === activeSubTab)!;

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    docs.forEach((d) => {
      c[d.doc_type] = (c[d.doc_type] || 0) + 1;
    });
    return c;
  }, [docs]);

  const visible = useMemo(() => {
    if (searchHits) return searchHits;
    let list = docs;
    if (tab.types.length) list = list.filter((d) => tab.types.includes(d.doc_type));
    if (activeSubTab === 'all' && typeFilter) list = list.filter((d) => d.doc_type === typeFilter);
    return list;
  }, [docs, tab, activeSubTab, typeFilter, searchHits]);

  // Default selection: newest document of the tab (list is already newest-first from the API).
  useEffect(() => {
    if (!visible.length) {
      setSelected(null);
      return;
    }
    if (!selected || !visible.some((d) => d.doc_id === selected.doc_id)) setSelected(visible[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) {
      setSearchHits(null);
      return;
    }
    setSearching(true);
    try {
      const params = new URLSearchParams({ q, limit: '50' });
      const types = activeSubTab === 'all' ? (typeFilter ? [typeFilter] : []) : tab.types;
      if (types.length) params.set('doc_types', types.join(','));
      const res = await fetch(`/api/wells/${encodeURIComponent(well.id)}/documents?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const env = (await res.json()) as Envelope<DocumentHit[]>;
      setSearchHits(Array.isArray(env.data) ? env.data : []);
    } catch (err) {
      console.error('Document search failed:', err);
      setSearchHits([]);
    } finally {
      setSearching(false);
    }
  };

  const handleExportDossier = async () => {
    setIsExporting(true);
    try {
      const res = await fetch(`/api/wells/${well.id}/export`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${well.id}_Engineering_Dossier_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export dossier:', err);
      alert('Failed to export well dossier. Please retry.');
    } finally {
      setIsExporting(false);
    }
  };

  // Stage S (F-06, TC-023): pre-job field dossier PDF (2-4 pages, every number fact-slotted).
  const [dossierBusy, setDossierBusy] = useState<boolean>(false);
  const [dossierInfo, setDossierInfo] = useState<{ pages: number; highlights: string[]; pdf_url: string } | null>(null);
  const handleGenerateDossier = async () => {
    setDossierBusy(true);
    const win = window.open('', '_blank'); // open synchronously so the popup is not blocked
    try {
      const res = await fetch(`/api/wells/${encodeURIComponent(well.id)}/dossier?refresh=false`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const env = (await res.json()) as Envelope<{ pages: number; highlights: string[]; pdf_url: string } | null>;
      if (!env.data) throw new Error(env.message || 'dossier unavailable');
      setDossierInfo(env.data);
      if (win) win.location.href = env.data.pdf_url;
      else window.open(env.data.pdf_url, '_blank');
    } catch (err) {
      if (win) win.close();
      console.error('Failed to generate field dossier:', err);
      alert('Failed to generate the field dossier. Please retry.');
    } finally {
      setDossierBusy(false);
    }
  };

  const typeBadge = (t: string) => (
    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-border bg-[#0d1117] text-textMuted">
      {t}
    </span>
  );

  const scannedBadge = (
    <span
      className="inline-flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded border border-amber-700/60 bg-amber-950/60 text-amber-300"
      title="Image-only scan (no text layer); retrieved through OCR-equivalent index text"
    >
      <ScanLine className="w-3 h-3" /> SCANNED
    </span>
  );

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Sub-tab navigation & dossier download */}
      <div className="flex items-center justify-between border-b border-border/80 pb-2 gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {SUB_TABS.map((t) => {
            const n = t.types.length ? t.types.reduce((s, x) => s + (counts[x] || 0), 0) : docs.length;
            return (
              <button
                key={t.key}
                onClick={() => {
                  setActiveSubTab(t.key);
                  setSearchHits(null);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold flex items-center gap-2 transition-all ${
                  activeSubTab === t.key
                    ? t.active
                    : 'text-textMuted hover:text-white hover:bg-surface border border-transparent'
                }`}
              >
                {t.icon}
                <span>{t.label}</span>
                {status === 'ok' && (
                  <span className="text-[10px] px-1.5 rounded bg-surface text-textMuted font-mono">{n}</span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerateDossier}
            disabled={dossierBusy}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0d1117] hover:bg-surface text-sky-300 hover:text-sky-200 border border-sky-500/40 hover:border-sky-400 rounded-lg text-xs font-mono font-semibold transition-all shadow-sm"
            title="Generate the pre-job field dossier PDF (history, construction & lithology, NBA + SOP, hazards)"
          >
            {dossierBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
            <span>{dossierBusy ? 'Building dossier...' : 'Generate field dossier'}</span>
          </button>
          <button
            onClick={handleExportDossier}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0d1117] hover:bg-surface text-emerald-400 hover:text-emerald-300 border border-emerald-500/40 hover:border-emerald-400 rounded-lg text-xs font-mono font-semibold transition-all shadow-sm"
            title="Download the engineering dossier (JSON)"
          >
            <Download className={`w-3.5 h-3.5 ${isExporting ? 'animate-bounce' : ''}`} />
            <span>{isExporting ? 'Exporting...' : 'Export Dossier'}</span>
          </button>
        </div>
      </div>

      {dossierInfo && (
        <div className="text-[11px] font-mono text-sky-200/90 bg-sky-950/30 border border-sky-800/50 rounded-lg px-3 py-2 flex items-start gap-2">
          <FileText className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <div className="flex-1">
            {dossierInfo.highlights.map((h, i) => (
              <div key={i}>• {h}</div>
            ))}
          </div>
          <a href={dossierInfo.pdf_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sky-300 hover:text-white">
            <ExternalLink className="w-3 h-3" /> PDF ({dossierInfo.pages} pp)
          </a>
        </div>
      )}

      {status === 'loading' && (
        <div className="flex items-center gap-2 text-xs font-mono text-textMuted p-4">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading documents for {well.id}...
        </div>
      )}

      {(status === 'empty' || status === 'error') && (
        <div className="p-4 rounded-xl border border-amber-800/50 bg-amber-950/20 flex items-start gap-2.5 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-mono font-bold text-amber-300 uppercase text-[10px]">
              {status === 'error' ? 'Document service error' : 'No documents available'}
            </div>
            <p className="text-amber-100/90 mt-1">{message || `No documents indexed for ${well.id}.`}</p>
          </div>
        </div>
      )}

      {status === 'ok' && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-0 flex-1">
          {/* Document list */}
          <div className="lg:col-span-2 bg-[#12161c] border border-border rounded-xl p-3 flex flex-col min-h-0">
            <form onSubmit={runSearch} className="flex items-center gap-2 mb-2">
              <div className="flex-1 flex items-center gap-1.5 bg-[#0d1117] border border-border rounded-lg px-2">
                <Search className="w-3.5 h-3.5 text-textMuted" />
                <input
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    if (!e.target.value) setSearchHits(null);
                  }}
                  placeholder={`Search ${tab.label.toLowerCase()}...`}
                  className="flex-1 bg-transparent py-1.5 text-xs font-mono text-white outline-none"
                />
              </div>
              {activeSubTab === 'all' && (
                <select
                  value={typeFilter}
                  onChange={(e) => {
                    setTypeFilter(e.target.value);
                    setSearchHits(null);
                  }}
                  className="bg-[#0d1117] border border-border rounded-lg text-xs font-mono text-white px-2 py-1.5"
                >
                  <option value="">All types</option>
                  {Object.keys(counts)
                    .sort((a, b) => typeOrder(a) - typeOrder(b))
                    .map((t) => (
                      <option key={t} value={t}>
                        {t} · {TYPE_LABELS[t] || t} ({counts[t]})
                      </option>
                    ))}
                </select>
              )}
              <button
                type="submit"
                className="px-2.5 py-1.5 rounded-lg text-xs font-mono border border-accent/40 text-accent hover:bg-accent/10"
              >
                {searching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Go'}
              </button>
            </form>

            <div className="text-[10px] font-mono text-textMuted mb-1.5">
              {searchHits ? `${visible.length} match(es) for “${query}”` : `${visible.length} document(s), newest first`}
            </div>

            <div className="overflow-y-auto space-y-1.5 pr-1 max-h-[560px]">
              {visible.length === 0 && (
                <div className="text-xs text-textMuted p-2">No documents of this type for {well.id}.</div>
              )}
              {visible.map((d) => (
                <button
                  key={`${d.doc_id}-${d.page}`}
                  onClick={() => setSelected(d)}
                  className={`w-full text-left p-2.5 rounded-lg border transition-all ${
                    selected?.doc_id === d.doc_id
                      ? 'bg-accent/10 border-accent/50'
                      : 'bg-[#0d1117] border-border hover:border-accent/30'
                  }`}
                >
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {typeBadge(d.doc_type)}
                    {d.scanned && scannedBadge}
                    <span className="text-[10px] font-mono text-textMuted ml-auto">{d.doc_date}</span>
                  </div>
                  <div className="text-xs text-white font-semibold mt-1 leading-snug">{d.title}</div>
                  <div className="text-[10px] font-mono text-textMuted mt-0.5">
                    {d.doc_id}
                    {d.intervention_class ? ` · ${d.intervention_class}` : ''}
                    {d.job_code ? ` · ${d.job_code}` : ''}
                  </div>
                  {d.snippet && (
                    <div className="text-[10px] text-textMuted mt-1 line-clamp-2">
                      p.{d.page}: {d.snippet}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* PDF preview */}
          <div className="lg:col-span-3 bg-[#12161c] border border-border rounded-xl p-3 flex flex-col min-h-[600px]">
            {selected ? (
              <>
                <div className="flex items-start justify-between gap-2 border-b border-border/80 pb-2 mb-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 text-[10px] font-mono text-accent font-bold uppercase tracking-wider">
                      <Layers className="w-3.5 h-3.5" />
                      {selected.doc_type_name}
                      {selected.scanned && scannedBadge}
                    </div>
                    <h3 className="text-sm font-bold text-white mt-1 truncate" title={selected.title}>
                      {selected.title}
                    </h3>
                    <div className="text-[10px] font-mono text-textMuted mt-0.5">
                      {selected.doc_id} · {selected.doc_date} · {selected.pages} page(s) · {selected.field}
                    </div>
                  </div>
                  <a
                    href={selected.uri}
                    target="_blank"
                    rel="noreferrer"
                    className="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono border border-accent/40 text-accent hover:bg-accent/10"
                  >
                    <ExternalLink className="w-3.5 h-3.5" /> Open PDF
                  </a>
                </div>
                <iframe
                  key={selected.uri}
                  src={selected.uri}
                  title={selected.title}
                  className="w-full flex-1 rounded-lg border border-border bg-white min-h-[520px]"
                />
              </>
            ) : (
              <div className="text-xs text-textMuted p-4">Select a document to preview.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
