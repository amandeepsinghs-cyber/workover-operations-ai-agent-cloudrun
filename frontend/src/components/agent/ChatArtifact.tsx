import React from 'react';
import {
  FileText,
  ExternalLink,
  Zap,
  ListOrdered,
  Activity,
  TrendingDown,
  TrendingUp,
  BarChart2,
  LineChart,
  Layers,
  MapPin,
  Tag,
  Scale,
} from 'lucide-react';
import { ChatArtifact as ChatArtifactType } from '../../api/chat';

export interface ChatArtifactProps {
  artifact: ChatArtifactType;
  /** Opens the full well view (Deep Dive) for a well; shown as an "Open full view" button. */
  onOpenFullView?: (wellId: string) => void;
}

// Small link-style artifacts stay open; data-heavy ones start collapsed so the chat stays a
// question/answer space (UI rule, 2026-10-08). The user expands on demand.
const OPEN_BY_DEFAULT = new Set(['dossier', 'citations']);
const WELL_KINDS = new Set(['well_profile', 'well_production_chart', 'nba', 'counterfactual', 'intervention_classification', 'dossier']);

export const ChatArtifact: React.FC<ChatArtifactProps> = ({ artifact, onOpenFullView }) => {
  const { kind, data, provenance, tool_id, tool } = artifact;
  const [expanded, setExpanded] = React.useState<boolean>(OPEN_BY_DEFAULT.has(kind));
  const artifactWellId: string | null =
    (data && (data.well_id || (kind === 'well_profile' ? data.id : null))) || null;

  const renderDossier = () => {
    const pdfUrl = data?.pdf_url || data?.url || data?.dossier_url;
    const highlights: string[] = Array.isArray(data?.highlights) ? data.highlights : [];
    const wellId = data?.well_id;
    const title = data?.title || (wellId ? `Field Dispatch Dossier (${wellId})` : 'Well Dossier PDF');

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-textMain text-xs font-sans">{title}</span>
          {pdfUrl && (
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent/20 border border-accent/40 text-accent hover:bg-accent hover:text-white transition-colors text-[10px] font-mono shrink-0"
            >
              <span>Open PDF</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          )}
        </div>
        {highlights.length > 0 && (
          <ul className="list-disc pl-4 space-y-1 text-textMuted text-[11px] font-sans">
            {highlights.map((h: string, idx: number) => (
              <li key={idx}>{h}</li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  const renderCitations = () => {
    const hits: any[] = Array.isArray(data)
      ? data
      : Array.isArray(data?.hits)
      ? data.hits
      : Array.isArray(data?.citations)
      ? data.citations
      : [];

    if (hits.length === 0) {
      return <span className="text-textMuted italic text-[11px]">No citations available</span>;
    }

    return (
      <div className="space-y-1.5">
        <div className="flex flex-wrap gap-1.5">
          {hits.map((hit, idx) => {
            const docId = hit.doc_id || hit.id || 'doc';
            const page = hit.page ?? 1;
            const href = `/api/docs/${encodeURIComponent(docId)}.pdf#page=${page}`;
            const title = hit.title || docId;
            return (
              <a
                key={idx}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                title={`${title} (Page ${page})`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#161b22] border border-border hover:border-accent text-accent transition-colors text-[10px] font-mono group"
              >
                <FileText className="w-2.5 h-2.5 text-textMuted group-hover:text-accent" />
                <span className="truncate max-w-[120px]">{docId}</span>
                <span className="text-textMuted">p.{page}</span>
                <ExternalLink className="w-2.5 h-2.5 opacity-60" />
              </a>
            );
          })}
        </div>
        {hits.some((h) => h.snippet) && (
          <div className="text-[10px] text-textMuted italic font-sans bg-[#0d1117] p-1.5 rounded border border-border/40 line-clamp-2">
            "{hits.find((h) => h.snippet)?.snippet}"
          </div>
        )}
      </div>
    );
  };

  const renderPriorityQueue = () => {
    const rigQueue = Array.isArray(data?.rig_queue) ? data.rig_queue : [];
    const riglessQueue = Array.isArray(data?.rigless_queue) ? data.rigless_queue : [];
    const rows =
      rigQueue.length > 0
        ? rigQueue
        : Array.isArray(data?.rows)
        ? data.rows
        : Array.isArray(data)
        ? data
        : riglessQueue;

    return (
      <div className="space-y-1.5 font-mono text-[10px]">
        {data?.field && (
          <div className="text-textMuted">
            Field: <span className="text-white font-semibold">{data.field}</span>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border text-textMuted">
                <th className="py-1 pr-2">Rank</th>
                <th className="py-1 pr-2">Well</th>
                <th className="py-1 pr-2">Job</th>
                <th className="py-1 pr-2 text-right">Uplift</th>
                <th className="py-1 pr-2 text-right">Band</th>
                <th className="py-1 text-right">Days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {rows.slice(0, 5).map((r: any, idx: number) => (
                <tr key={idx} className="hover:bg-surface/50">
                  <td className="py-1 pr-2 text-textMuted">#{r.candidate_rank ?? r.rank ?? idx + 1}</td>
                  <td className="py-1 pr-2 font-semibold text-white">{r.well_id ?? r.id}</td>
                  <td
                    className="py-1 pr-2 text-accent truncate max-w-[80px]"
                    title={r.catalogue_job_code || r.job_code || r.action}
                  >
                    {r.catalogue_job_code || r.job_code || r.action || '-'}
                  </td>
                  <td className="py-1 pr-2 text-right text-emerald-400">
                    {typeof r.projected_flow_uplift_bopd === 'number'
                      ? `+${r.projected_flow_uplift_bopd}`
                      : typeof r.uplift_bopd === 'number'
                      ? `+${r.uplift_bopd}`
                      : '-'}
                  </td>
                  <td className="py-1 pr-2 text-right text-amber-400">{r.cost_band ?? '-'}</td>
                  <td className="py-1 text-right text-sky-400">
                    {typeof r.rig_days === 'number' ? r.rig_days.toFixed(1) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length > 5 && (
          <div className="text-[9px] text-textMuted text-right">...and {rows.length - 5} more candidates</div>
        )}
      </div>
    );
  };

  const renderNba = () => {
    const actions: any[] = Array.isArray(data?.actions)
      ? data.actions
      : Array.isArray(data?.recommendations)
      ? data.recommendations
      : Array.isArray(data)
      ? data
      : [];

    return (
      <div className="space-y-1.5 font-mono text-[10px]">
        {data?.well_id && (
          <div className="text-textMuted">
            Well: <span className="text-white font-semibold">{data.well_id}</span>
          </div>
        )}
        {actions.map((act: any, idx: number) => (
          <div key={idx} className="p-2 rounded bg-[#0d1117] border border-border/60 space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-accent">
                #{act.rank ?? idx + 1} {act.title || act.job_code || act.catalogue_job_code}
              </span>
              {act.cost_band && (
                <span className="px-1.5 py-0.2 rounded bg-surface border border-border text-amber-400">
                  {act.cost_band}
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-1 text-[9px] text-textMuted">
              {typeof act.uplift_bopd === 'number' && (
                <div>
                  Uplift: <span className="text-emerald-400 font-semibold">+{act.uplift_bopd} BOPD</span>
                </div>
              )}
              {typeof act.p_success === 'number' && (
                <div>
                  p(succ): <span className="text-sky-400 font-semibold">{Math.round(act.p_success * 100)}%</span>
                </div>
              )}
              {typeof act.rig_days === 'number' && (
                <div>
                  Rig-days: <span className="text-white font-semibold">{act.rig_days.toFixed(1)}</span>
                </div>
              )}
            </div>
          </div>
        ))}
        {Array.isArray(data?.rejected_jobs) && data.rejected_jobs.length > 0 && (
          <div className="text-[9px] text-textMuted">
            <span className="font-semibold">Rejected:</span>{' '}
            {data.rejected_jobs.map((j: any) => `${j.job_code || j} (${j.reason || 'ruled out'})`).join(', ')}
          </div>
        )}
      </div>
    );
  };

  const renderCounterfactual = () => {
    const rec = data?.recommended_job || data?.recommended;
    const alt = data?.alternative_job || data?.alternative;
    const verdict = data?.verdict;
    const deciding = data?.deciding_dimension;
    const dims: any[] = Array.isArray(data?.dimensions) ? data.dimensions : [];

    return (
      <div className="space-y-1.5 font-mono text-[10px]">
        <div className="flex items-center justify-between gap-1">
          <span className="text-white font-semibold truncate">
            {rec} vs {alt}
          </span>
          {verdict && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-700/60 text-emerald-300 uppercase text-[9px] shrink-0">
              {verdict}
            </span>
          )}
        </div>
        {deciding && (
          <div className="text-[9px] text-textMuted">
            Deciding: <span className="text-accent">{deciding}</span>
          </div>
        )}
        {dims.length > 0 && (
          <table className="w-full text-left border-collapse text-[9px]">
            <thead>
              <tr className="border-b border-border text-textMuted">
                <th className="py-0.5">Dimension</th>
                <th className="py-0.5">{rec || 'Rec'}</th>
                <th className="py-0.5">{alt || 'Alt'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {dims.map((d: any, idx: number) => (
                <tr key={idx}>
                  <td className="py-0.5 text-textMuted">{d.dimension || d.name}</td>
                  <td className="py-0.5 text-emerald-400">{String(d.recommended_value ?? d.rec_val ?? '-')}</td>
                  <td className="py-0.5 text-amber-400">{String(d.alternative_value ?? d.alt_val ?? '-')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  };

  const renderAttributionWaterfall = () => {
    const factors: any[] = Array.isArray(data?.factors)
      ? data.factors
      : Array.isArray(data?.attribution)
      ? data.attribution
      : Array.isArray(data)
      ? data
      : [];

    return (
      <div className="space-y-1 font-mono text-[10px]">
        {typeof data?.total_decline_bopd === 'number' && (
          <div className="text-[10px] text-textMuted">
            Total Decline: <span className="text-rose-400 font-semibold">{data.total_decline_bopd} BOPD</span>
          </div>
        )}
        <table className="w-full text-left border-collapse text-[9px]">
          <thead>
            <tr className="border-b border-border text-textMuted">
              <th className="py-0.5">Factor</th>
              <th className="py-0.5 text-right">bbl</th>
              <th className="py-0.5 text-right">%</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {factors.map((f: any, idx: number) => (
              <tr key={idx}>
                <td className="py-0.5 text-textMain truncate max-w-[120px]">{f.sub_factor || f.factor || f.name}</td>
                <td className="py-0.5 text-right text-rose-400">{f.bbl != null ? f.bbl : '-'}</td>
                <td className="py-0.5 text-right text-textMuted">{f.pct != null ? `${f.pct}%` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderHealthBuckets = () => {
    const counts =
      data?.counts ||
      data?.summary ||
      (data?.buckets && !Array.isArray(data.buckets)
        ? Object.fromEntries(
            Object.entries(data.buckets).map(([k, v]) => [k, Array.isArray(v) ? v.length : v])
          )
        : null);

    return (
      <div className="space-y-1.5 font-mono text-[10px]">
        {data?.field && (
          <div className="text-textMuted">
            Field: <span className="text-white font-semibold">{data.field}</span>
          </div>
        )}
        {counts && typeof counts === 'object' && (
          <div className="grid grid-cols-2 gap-1.5">
            {Object.entries(counts).map(([bucket, count]: [string, any], idx: number) => (
              <div
                key={idx}
                className="p-1.5 rounded bg-[#0d1117] border border-border/50 flex items-center justify-between"
              >
                <span className="text-[9px] text-textMuted truncate max-w-[90px]">{bucket}</span>
                <span className="text-white font-bold">{String(count)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderFieldComparison = () => {
    const rows: any[] = Array.isArray(data?.rows)
      ? data.rows
      : Array.isArray(data?.fields)
      ? data.fields
      : Array.isArray(data)
      ? data
      : [];

    return (
      <div className="space-y-1 font-mono text-[10px]">
        {data?.period && (
          <div className="text-textMuted">
            Period: <span className="text-white font-semibold">{data.period}</span>
          </div>
        )}
        <table className="w-full text-left border-collapse text-[9px]">
          <thead>
            <tr className="border-b border-border text-textMuted">
              <th className="py-0.5">Field</th>
              <th className="py-0.5 text-right">Actual BOPD</th>
              <th className="py-0.5 text-right">Target</th>
              <th className="py-0.5 text-right">Variance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {rows.map((r: any, idx: number) => (
              <tr key={idx}>
                <td className="py-0.5 font-semibold text-white">{r.field || r.name}</td>
                <td className="py-0.5 text-right text-emerald-400">{r.actual_bopd ?? r.oil_bopd ?? '-'}</td>
                <td className="py-0.5 text-right text-textMuted">{r.target_bopd ?? '-'}</td>
                <td
                  className={`py-0.5 text-right ${
                    typeof r.variance_bopd === 'number' && r.variance_bopd < 0
                      ? 'text-rose-400'
                      : 'text-emerald-400'
                  }`}
                >
                  {r.variance_bopd != null ? (r.variance_bopd > 0 ? `+${r.variance_bopd}` : r.variance_bopd) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderFieldHistory = () => {
    const rows: any[] = Array.isArray(data?.summary)
      ? data.summary
      : Array.isArray(data?.fields)
      ? data.fields
      : Array.isArray(data?.series)
      ? data.series.slice(-5)
      : Array.isArray(data)
      ? data
      : [];

    return (
      <div className="space-y-1 font-mono text-[10px]">
        {data?.series_rows != null && (
          <div className="text-textMuted">
            History: <span className="text-white font-semibold">{data.series_rows} monthly records</span>
          </div>
        )}
        {rows.length > 0 && (
          <table className="w-full text-left border-collapse text-[9px]">
            <thead>
              <tr className="border-b border-border text-textMuted">
                <th className="py-0.5">Field / Metric</th>
                <th className="py-0.5 text-right">Start</th>
                <th className="py-0.5 text-right">End</th>
                <th className="py-0.5 text-right">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {rows.map((r: any, idx: number) => (
                <tr key={idx}>
                  <td className="py-0.5 text-white">{r.field || r.period || r.name}</td>
                  <td className="py-0.5 text-right text-textMuted">{r.start_bopd ?? r.start ?? '-'}</td>
                  <td className="py-0.5 text-right text-emerald-400">{r.end_bopd ?? r.end ?? r.oil_bopd ?? '-'}</td>
                  <td className="py-0.5 text-right text-sky-400">{r.change_pct != null ? `${r.change_pct}%` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  };

  const renderWellProfile = () => {
    return (
      <div className="space-y-1.5 font-mono text-[10px]">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-white">{data?.name || data?.well_id}</span>
          {data?.status && (
            <span className="px-1.5 py-0.2 rounded bg-surface border border-border text-[9px] uppercase">
              {data.status}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-1 text-[9px] text-textMuted">
          {data?.formation && (
            <div>
              Zone: <span className="text-white">{data.formation}</span>
            </div>
          )}
          {data?.lift_type && (
            <div>
              Lift: <span className="text-white">{data.lift_type}</span>
            </div>
          )}
          {data?.current_metrics?.oil_bopd != null && (
            <div>
              Oil: <span className="text-emerald-400">{data.current_metrics.oil_bopd} BOPD</span>
            </div>
          )}
          {data?.current_metrics?.water_cut_pct != null && (
            <div>
              Water cut: <span className="text-amber-400">{data.current_metrics.water_cut_pct}%</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderWellProductionChart = () => {
    const series: any[] = Array.isArray(data?.series) ? data.series.slice(-5) : [];
    return (
      <div className="space-y-1 font-mono text-[10px]">
        {data?.well_id && (
          <div className="text-textMuted">
            Well: <span className="text-white font-semibold">{data.well_id}</span>
          </div>
        )}
        {series.length > 0 && (
          <table className="w-full text-left border-collapse text-[9px]">
            <thead>
              <tr className="border-b border-border text-textMuted">
                <th className="py-0.5">Date</th>
                <th className="py-0.5 text-right">Oil (BOPD)</th>
                <th className="py-0.5 text-right">Water Cut</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {series.map((p: any, idx: number) => (
                <tr key={idx}>
                  <td className="py-0.5 text-textMuted">{p.date}</td>
                  <td className="py-0.5 text-right text-emerald-400">{p.oil_bopd ?? '-'}</td>
                  <td className="py-0.5 text-right text-amber-400">
                    {p.water_cut_pct != null ? `${p.water_cut_pct}%` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  };

  const renderInterventionClassification = () => {
    return (
      <div className="space-y-1 font-mono text-[10px]">
        <div className="flex items-center justify-between">
          <span className="text-textMuted">Predicted Class:</span>
          <span className="font-bold text-accent">{data?.predicted_class || data?.classification || '-'}</span>
        </div>
        {typeof data?.confidence === 'number' && (
          <div className="flex items-center justify-between text-[9px]">
            <span className="text-textMuted">Confidence:</span>
            <span className="text-emerald-400 font-semibold">{Math.round(data.confidence * 100)}%</span>
          </div>
        )}
      </div>
    );
  };

  const renderWellMap = () => {
    return (
      <div className="space-y-1 font-mono text-[10px]">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-white">{data?.well_id || data?.name}</span>
          {data?.field && <span className="text-accent">{data.field}</span>}
        </div>
        {(data?.lat != null || data?.coordinates?.lat != null) && (
          <div className="text-[9px] text-textMuted">
            Coords: {data?.lat ?? data?.coordinates?.lat}, {data?.lng ?? data?.coordinates?.lng}
          </div>
        )}
      </div>
    );
  };

  const renderGeneric = () => {
    if (!data || typeof data !== 'object') {
      return <div className="text-textMuted font-mono text-[10px]">{String(data)}</div>;
    }
    const entries = Object.entries(data).slice(0, 6);
    return (
      <div className="space-y-0.5 font-mono text-[9px]">
        {entries.map(([k, v], idx) => (
          <div key={idx} className="flex items-center justify-between gap-2">
            <span className="text-textMuted truncate max-w-[120px]">{k}:</span>
            <span className="text-white truncate max-w-[140px]">
              {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  const getHeaderInfo = () => {
    switch (kind) {
      case 'dossier':
        return { label: 'Pre-Job Well Dossier', icon: <FileText className="w-3 h-3 text-accent" /> };
      case 'citations':
        return { label: 'Cited Documents', icon: <ExternalLink className="w-3 h-3 text-accent" /> };
      case 'priority_queue':
        return { label: 'Candidate Priority Queue', icon: <ListOrdered className="w-3 h-3 text-sky-400" /> };
      case 'nba':
        return { label: 'Next Best Actions (NBA)', icon: <Zap className="w-3 h-3 text-amber-400" /> };
      case 'counterfactual':
        return { label: 'Intervention Comparison', icon: <Scale className="w-3 h-3 text-purple-400" /> };
      case 'attribution_waterfall':
        return { label: 'Decline Attribution', icon: <TrendingDown className="w-3 h-3 text-rose-400" /> };
      case 'health_buckets':
        return { label: 'Field Health Buckets', icon: <Activity className="w-3 h-3 text-emerald-400" /> };
      case 'field_history_chart':
        return { label: 'Field Production History', icon: <LineChart className="w-3 h-3 text-cyan-400" /> };
      case 'field_comparison':
        return { label: 'Field Comparison', icon: <BarChart2 className="w-3 h-3 text-indigo-400" /> };
      case 'well_profile':
        return { label: 'Well Architecture', icon: <Layers className="w-3 h-3 text-emerald-400" /> };
      case 'well_production_chart':
        return { label: 'Production History', icon: <TrendingUp className="w-3 h-3 text-emerald-400" /> };
      case 'intervention_classification':
        return { label: 'Intervention Classifier', icon: <Tag className="w-3 h-3 text-amber-400" /> };
      case 'well_map':
        return { label: 'Well Location', icon: <MapPin className="w-3 h-3 text-rose-400" /> };
      default:
        return { label: tool_id || tool || 'Artifact', icon: <Activity className="w-3 h-3 text-accent" /> };
    }
  };

  const { label, icon } = getHeaderInfo();
  const asOf = provenance?.as_of;
  const toolLabel = tool_id || tool || 'TC';

  return (
    <div className="my-2 p-2.5 rounded-lg bg-[#12161c] border border-border/80 space-y-2 shadow-sm">
      {/* Header bar: label + on-demand controls */}
      <div
        className={`flex items-center gap-1.5 text-[11px] font-sans font-semibold text-textMain ${
          expanded ? 'pb-1.5 border-b border-border/50' : ''
        }`}
      >
        {icon}
        <span className="truncate">{label}</span>
        {artifactWellId && <span className="font-mono text-[10px] text-textMuted">{artifactWellId}</span>}
        <span className="ml-auto flex items-center gap-1 shrink-0">
          {onOpenFullView && artifactWellId && WELL_KINDS.has(kind) && (
            <button
              onClick={() => onOpenFullView(artifactWellId)}
              className="px-1.5 py-0.5 rounded border border-accent/50 text-accent hover:bg-accent hover:text-white text-[9px] font-mono"
              title="Open the full well view (deep dive)"
            >
              Open full view
            </button>
          )}
          <button
            onClick={() => setExpanded((e) => !e)}
            className="px-1.5 py-0.5 rounded border border-border text-textMuted hover:text-white text-[9px] font-mono"
            aria-expanded={expanded}
          >
            {expanded ? 'Hide' : 'Details'}
          </button>
        </span>
      </div>

      {/* Body (on demand) */}
      {expanded && (
      <div>
        {kind === 'dossier' && renderDossier()}
        {kind === 'citations' && renderCitations()}
        {kind === 'priority_queue' && renderPriorityQueue()}
        {kind === 'nba' && renderNba()}
        {kind === 'counterfactual' && renderCounterfactual()}
        {kind === 'attribution_waterfall' && renderAttributionWaterfall()}
        {kind === 'health_buckets' && renderHealthBuckets()}
        {kind === 'field_comparison' && renderFieldComparison()}
        {kind === 'field_history_chart' && renderFieldHistory()}
        {kind === 'well_profile' && renderWellProfile()}
        {kind === 'well_production_chart' && renderWellProductionChart()}
        {kind === 'intervention_classification' && renderInterventionClassification()}
        {kind === 'well_map' && renderWellMap()}
        {![
          'dossier',
          'citations',
          'priority_queue',
          'nba',
          'counterfactual',
          'attribution_waterfall',
          'health_buckets',
          'field_comparison',
          'field_history_chart',
          'well_profile',
          'well_production_chart',
          'intervention_classification',
          'well_map',
        ].includes(kind) && renderGeneric()}
      </div>
      )}

      {/* Provenance tiny line: tool_id · as_of */}
      {expanded && (
      <div className="text-[9px] font-mono text-textMuted pt-1.5 border-t border-border/40 flex items-center justify-between">
        <span>
          {toolLabel}
          {asOf ? ` · ${asOf}` : ''}
        </span>
      </div>
      )}
    </div>
  );
};
