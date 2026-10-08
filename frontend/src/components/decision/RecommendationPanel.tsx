import React, { useState, useEffect, useMemo } from 'react';
import {
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  ArrowRight,
} from 'lucide-react';
import {
  decisionApi,
  Recommendations,
  RecCandidate,
  RecDriver,
  FIT_COLORS,
  BAND_COLORS,
} from '../../api/decision';

export interface RecommendationPanelProps {
  wellId: string;
  onCompare?: (jobCode: string) => void;
  onOpenWell?: (wellId: string) => void;
}

function humanizeFeature(feature: string, label?: string): string {
  let text = label || feature || '';
  text = text.replace(/_/g, ' ');
  text = text.replace(/\bwc\b/gi, 'water cut');
  text = text.replace(/\bthp\b/gi, 'tubing-head pressure');
  text = text.replace(/\bchp\b/gi, 'casing pressure');
  text = text.replace(/\b5d\b/gi, '(5-day)');
  text = text.replace(/\bpp\b/gi, 'pts');
  return text;
}

export const RecommendationPanel: React.FC<RecommendationPanelProps> = ({
  wellId,
  onCompare,
  onOpenWell,
}) => {
  const [data, setData] = useState<Recommendations | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [howDecidedOpen, setHowDecidedOpen] = useState<boolean>(true);
  const [activeAnalogTab, setActiveAnalogTab] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    decisionApi
      .recommendations(wellId, 3)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [wellId]);

  const maxDriverWeight = useMemo(() => {
    if (!data?.drivers || data.drivers.length === 0) return 1.0;
    const max = Math.max(...data.drivers.map((d) => Math.abs(d.weight || 0)));
    return max > 0 ? max : 1.0;
  }, [data?.drivers]);

  const driversByModality = useMemo(() => {
    if (!data?.drivers) return {};
    return data.drivers.reduce<Record<string, RecDriver[]>>((acc, d) => {
      const mod = d.modality || 'Other';
      if (!acc[mod]) acc[mod] = [];
      acc[mod].push(d);
      return acc;
    }, {});
  }, [data?.drivers]);

  if (loading) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain space-y-3">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="font-mono uppercase font-bold text-white tracking-wide">
              Recommended interventions · Multimodal NN
            </span>
            <span className="font-mono text-textMuted">·</span>
            <span className="font-mono font-medium text-textMain">{wellId}</span>
          </div>
        </div>
        <div className="py-12 flex flex-col items-center justify-center gap-2 text-textMuted font-mono">
          <Loader2 className="w-5 h-5 animate-spin text-accent" />
          <span>Loading multimodal neural network recommendations...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain space-y-3">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="font-mono uppercase font-bold text-white tracking-wide">
              Recommended interventions · Multimodal NN
            </span>
            <span className="font-mono text-textMuted">·</span>
            <span className="font-mono font-medium text-textMain">{wellId}</span>
          </div>
        </div>
        <div className="p-3 my-4 rounded bg-critical/10 border border-critical/30 text-critical text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error || 'No recommendations returned'}</span>
        </div>
      </div>
    );
  }

  const candidates: RecCandidate[] = data.candidates || [];
  const currentAnalogCand = candidates[activeAnalogTab] ?? candidates[0];

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-border">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono uppercase font-bold text-white tracking-wide text-xs">
            Recommended interventions · Multimodal NN
          </span>
          <span className="font-mono text-textMuted">·</span>
          <span className="font-mono font-medium text-textMain text-xs">{wellId}</span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="px-2 py-0.5 rounded bg-accent/15 border border-accent/30 text-accent text-[10px] font-mono font-semibold">
            engine: {data.engine || 'multimodal NN'}
          </span>
          {(data.is_synthetic || data.flags?.includes('SYNTHETIC_TRAINING_DATA')) && (
            <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] font-mono font-semibold">
              synthetic demo data
            </span>
          )}
        </div>
      </div>

      {/* Candidate Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {candidates.map((cand) => {
          const pSuccessPct = Math.round(cand.p_success * 100);
          const rankLabel = cand.rank === 1 ? 'Primary' : 'Alternative';

          const fitColor =
            cand.fit_symbol === '✔'
              ? FIT_COLORS.FIT
              : cand.fit_symbol === '✘'
              ? FIT_COLORS.CONTRADICTED
              : FIT_COLORS.UNCLEAR;

          return (
            <div
              key={cand.job_code}
              className={`bg-surface/70 border rounded-lg p-3 flex flex-col justify-between space-y-3 transition-colors ${
                cand.rank === 1 ? 'border-emerald-500/40 bg-surface' : 'border-border/80'
              }`}
            >
              <div className="space-y-2.5">
                {/* Top Badge & Fit */}
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase ${
                      cand.rank === 1
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : 'bg-accent/15 text-accent border border-accent/30'
                    }`}
                  >
                    #{cand.rank} {rankLabel}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {cand.cost_band && (
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold"
                        style={{
                          backgroundColor: `${BAND_COLORS[cand.cost_band]}20`,
                          color: BAND_COLORS[cand.cost_band],
                          border: `1px solid ${BAND_COLORS[cand.cost_band]}40`,
                        }}
                        title={`Cost Band: ${cand.cost_band}`}
                      >
                        {cand.cost_band}
                      </span>
                    )}
                    <span
                      className="font-bold text-sm leading-none"
                      style={{ color: fitColor }}
                      title={cand.fit_evidence}
                    >
                      {cand.fit_symbol}
                    </span>
                  </div>
                </div>

                {/* Job Name & IC */}
                <div>
                  <div className="text-sm font-semibold text-white font-mono leading-tight">
                    {cand.job_name}
                  </div>
                  <div className="text-[11px] font-mono text-textMuted mt-0.5 truncate">
                    {cand.ic} · {cand.ic_label}
                  </div>
                </div>

                {/* Big P(success) with horizontal bar */}
                <div className="space-y-1 bg-[#0d1117]/60 border border-border/40 rounded p-2">
                  <div className="flex items-baseline justify-between">
                    <span className="text-[10px] font-mono uppercase text-textMuted font-bold">
                      P(success)
                    </span>
                    <span className="text-lg font-bold font-mono text-white">
                      {pSuccessPct}%
                    </span>
                  </div>
                  <div className="w-full bg-surface border border-border/50 rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min(100, Math.max(0, pSuccessPct))}%`,
                        backgroundColor:
                          cand.p_success >= 0.5
                            ? '#2ea043'
                            : cand.p_success >= 0.3
                            ? '#d29922'
                            : '#f85149',
                      }}
                    />
                  </div>
                </div>

                {/* Key Metrics */}
                <div className="space-y-1 text-xs font-mono pt-1">
                  <div className="flex items-center justify-between">
                    <span className="text-textMuted">Expected uplift</span>
                    <span className="text-emerald-400 font-semibold">
                      {cand.expected_uplift_bopd != null
                        ? `+${cand.expected_uplift_bopd} BOPD`
                        : '—'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-textMuted">Rig-days</span>
                    <span className="text-white">
                      {cand.rig_days != null ? `${cand.rig_days} d` : '—'}{' '}
                      <span className="text-textMuted text-[10px]">
                        {cand.requires_rig ? '(rig)' : '(rigless)'}
                      </span>
                    </span>
                  </div>
                </div>

                {/* Look-alike Wells */}
                {cand.analogs && (
                  <div className="space-y-1.5 text-xs font-mono pt-2 border-t border-border/40">
                    <div className="text-[11px] text-textMuted">
                      Look-alike wells:{' '}
                      <span className="text-white font-semibold">
                        {cand.analogs.n_success} of {cand.analogs.n}
                      </span>{' '}
                      succeeded
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {cand.analogs.well_ids.map((wId) => (
                        <button
                          key={wId}
                          type="button"
                          onClick={() => onOpenWell?.(wId)}
                          className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px] font-mono text-textMain hover:border-accent hover:text-white transition-colors"
                          title={`Open well ${wId}`}
                        >
                          {wId}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Risks */}
                {cand.risks && cand.risks.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {cand.risks.map((risk) => (
                      <span
                        key={risk}
                        className="px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] font-mono"
                      >
                        {risk.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                )}

                {/* SOP Link */}
                {cand.sop_url && (
                  <div className="pt-1 truncate">
                    <a
                      href={cand.sop_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline inline-flex items-center gap-1 text-[11px] font-mono truncate"
                      title={cand.sop_title || 'SOP document'}
                    >
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">
                        {cand.sop_title || cand.sop_doc_id || 'Standard Operating Procedure'}
                      </span>
                    </a>
                  </div>
                )}

                {/* Alternative Note */}
                {cand.alternative_note && (
                  <div className="text-[10px] font-mono text-textMuted italic pt-1 border-t border-border/30">
                    {cand.alternative_note}
                  </div>
                )}
              </div>

              {/* Compare Button */}
              <button
                type="button"
                onClick={() => onCompare?.(cand.job_code)}
                className="w-full mt-2 py-1.5 px-3 rounded bg-surface hover:bg-border/60 border border-border text-xs font-mono text-textMain hover:text-white transition-colors flex items-center justify-center gap-1.5 font-medium shadow-sm"
              >
                <span>Compare</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Collapsible 'How did you decide?' Section */}
      <div className="pt-2 border-t border-border/70">
        <button
          type="button"
          onClick={() => setHowDecidedOpen((prev) => !prev)}
          className="w-full flex items-center justify-between text-xs font-mono uppercase text-textMuted font-bold hover:text-white py-1.5 transition-colors select-none"
        >
          <span className="flex items-center gap-1.5">
            {howDecidedOpen ? (
              <ChevronDown className="w-4 h-4 text-accent" />
            ) : (
              <ChevronRight className="w-4 h-4 text-textMuted" />
            )}
            How did you decide?
          </span>
          <span className="text-[10px] text-textMuted font-normal lowercase">
            {howDecidedOpen ? 'click to collapse' : 'click to expand'}
          </span>
        </button>

        {howDecidedOpen && (
          <div className="space-y-4 mt-3">
            {/* (a) Evidence Chain */}
            <div className="bg-surface/40 border border-border/80 rounded-lg p-3 space-y-2">
              <div className="text-[11px] font-mono font-bold uppercase text-textMuted flex items-center gap-1.5">
                <span>(a) Evidence Chain: Signals → Mechanism → Candidates</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs font-mono py-1 overflow-x-auto">
                {/* Signals */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  {data.evidence_chain.signals && data.evidence_chain.signals.length > 0 ? (
                    data.evidence_chain.signals.map((sig) => (
                      <span
                        key={sig}
                        className="px-2 py-1 rounded bg-[#0d1117] border border-border text-textMain text-[11px]"
                      >
                        {sig.replace(/_/g, ' ')}
                      </span>
                    ))
                  ) : (
                    <span className="text-textMuted italic text-[11px]">No signals</span>
                  )}
                </div>

                {/* Arrow */}
                <ArrowRight className="w-4 h-4 text-textMuted flex-shrink-0" />

                {/* Mechanism */}
                <div>
                  <span className="px-2.5 py-1 rounded bg-accent/20 border border-accent/40 text-accent font-semibold text-[11px]">
                    {data.evidence_chain.mechanism || 'Unspecified mechanism'}
                  </span>
                </div>

                {/* Arrow */}
                <ArrowRight className="w-4 h-4 text-textMuted flex-shrink-0" />

                {/* Candidates */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  {data.evidence_chain.candidates && data.evidence_chain.candidates.length > 0 ? (
                    data.evidence_chain.candidates.map((cCode) => (
                      <span
                        key={cCode}
                        className="px-2 py-1 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[11px] font-medium"
                      >
                        {cCode.replace(/_/g, ' ')}
                      </span>
                    ))
                  ) : (
                    <span className="text-textMuted italic text-[11px]">No candidates</span>
                  )}
                </div>
              </div>
            </div>

            {/* (b) Drivers */}
            <div className="bg-surface/40 border border-border/80 rounded-lg p-3 space-y-3">
              <div className="text-[11px] font-mono font-bold uppercase text-textMuted flex items-center justify-between">
                <span>(b) Drivers by Modality</span>
                <span className="text-[10px] text-textMuted font-normal lowercase">
                  supports in green · argues against in amber
                </span>
              </div>
              <div className="space-y-3">
                {Object.entries(driversByModality).map(([modality, drivers]) => (
                  <div key={modality} className="space-y-1.5">
                    <div className="text-[10px] font-mono font-bold uppercase text-accent/80 tracking-wide">
                      {modality}
                    </div>
                    <div className="space-y-1.5">
                      {drivers.map((d, i) => {
                        const isSupports = d.direction.toLowerCase().includes('support');
                        const humanLabel = humanizeFeature(d.feature, d.label);
                        const barWidth = Math.min(
                          100,
                          Math.max(4, (Math.abs(d.weight || 0) / maxDriverWeight) * 100)
                        );

                        return (
                          <div
                            key={i}
                            className="bg-[#0d1117] border border-border/60 rounded p-2 text-xs font-mono space-y-1"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase flex-shrink-0 ${
                                    isSupports
                                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                      : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                  }`}
                                >
                                  {d.direction}
                                </span>
                                <span className="text-textMain font-medium truncate" title={humanLabel}>
                                  {humanLabel}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0 text-[11px]">
                                {d.value !== null && (
                                  <span className="text-textMuted">val: {d.value}</span>
                                )}
                                <span className="text-white font-semibold">
                                  {d.weight.toFixed(3)}
                                </span>
                              </div>
                            </div>
                            <div className="w-full bg-surface rounded-full h-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-300 ${
                                  isSupports ? 'bg-emerald-500' : 'bg-amber-500'
                                }`}
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* (c) Look-alike Analysis */}
            <div className="bg-surface/40 border border-border/80 rounded-lg p-3 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[11px] font-mono font-bold uppercase text-textMuted">
                  (c) Look-alike Analysis (Historical Analogs)
                </span>
                <div className="flex flex-wrap gap-1">
                  {candidates.map((cand, idx) => (
                    <button
                      key={cand.job_code}
                      type="button"
                      onClick={() => setActiveAnalogTab(idx)}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                        activeAnalogTab === idx
                          ? 'bg-accent text-white font-semibold'
                          : 'bg-surface text-textMuted hover:text-white border border-border'
                      }`}
                    >
                      #{cand.rank} {cand.job_code} ({cand.analogs?.jobs?.length ?? 0})
                    </button>
                  ))}
                </div>
              </div>

              {currentAnalogCand && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="font-semibold text-textMain">
                      #{currentAnalogCand.rank} {currentAnalogCand.job_name}{' '}
                      <span className="text-textMuted font-normal">
                        ({currentAnalogCand.ic} · {currentAnalogCand.ic_label})
                      </span>
                    </span>
                    <span className="text-[11px] text-textMuted">
                      {currentAnalogCand.analogs?.n_success ?? 0} of{' '}
                      {currentAnalogCand.analogs?.n ?? 0} succeeded
                    </span>
                  </div>
                  {currentAnalogCand.analogs?.jobs && currentAnalogCand.analogs.jobs.length > 0 ? (
                    <div className="overflow-x-auto border border-border/60 rounded">
                      <table className="w-full text-left text-[11px] font-mono">
                        <thead className="bg-[#0d1117] text-[10px] text-textMuted uppercase border-b border-border/60">
                          <tr>
                            <th className="py-1.5 px-2">Well ID</th>
                            <th className="py-1.5 px-2">Job Code</th>
                            <th className="py-1.5 px-2">Start Date</th>
                            <th className="py-1.5 px-2">Outcome</th>
                            <th className="py-1.5 px-2 text-right">Uplift BOPD</th>
                            <th className="py-1.5 px-2 text-right">Similarity</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30 text-textMain">
                          {currentAnalogCand.analogs.jobs.map((job) => {
                            const outcomeColor =
                              job.outcome === 'SUCCESS'
                                ? 'text-emerald-400'
                                : job.outcome === 'FAILED'
                                ? 'text-red-400'
                                : 'text-amber-300';
                            return (
                              <tr
                                key={`${job.well_id}-${job.workover_id || job.start_date}`}
                                className="hover:bg-surface/60 transition-colors"
                              >
                                <td className="py-1 px-2 font-medium">
                                  {onOpenWell ? (
                                    <button
                                      type="button"
                                      onClick={() => onOpenWell(job.well_id)}
                                      className="text-accent hover:underline font-mono"
                                      title={`Open well ${job.well_id}`}
                                    >
                                      {job.well_id}
                                    </button>
                                  ) : (
                                    job.well_id
                                  )}
                                </td>
                                <td className="py-1 px-2 text-textMuted">{job.job_code}</td>
                                <td className="py-1 px-2 text-textMuted">{job.start_date}</td>
                                <td className={`py-1 px-2 font-semibold ${outcomeColor}`}>
                                  {job.outcome}
                                </td>
                                <td className="py-1 px-2 text-right">
                                  {job.uplift_bopd != null
                                    ? job.uplift_bopd > 0
                                      ? `+${job.uplift_bopd.toFixed(1)}`
                                      : job.uplift_bopd.toFixed(1)
                                    : '—'}
                                </td>
                                <td className="py-1 px-2 text-right text-textMuted">
                                  {(job.similarity * 100).toFixed(1)}%
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-[11px] text-textMuted italic py-1">
                      No analog jobs recorded
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* (d) Model Architecture & Score Breakdown */}
            <div className="bg-surface/40 border border-border/80 rounded-lg p-3 space-y-3">
              <div className="text-[11px] font-mono font-bold uppercase text-textMuted">
                (d) Model: Multimodal Architecture & Score Breakdown
              </div>

              {/* Diagram */}
              {data.architecture && (
                <div className="bg-[#0d1117] border border-border/70 rounded-lg p-3 space-y-3">
                  <div className="text-xs font-mono font-bold text-white">
                    {data.architecture.name}
                  </div>
                  <div className="flex flex-col md:flex-row items-center gap-2 text-xs font-mono">
                    {/* 4 Inputs */}
                    <div className="flex flex-col gap-1.5 w-full md:w-5/12">
                      {data.architecture.inputs.map((inp, idx) => (
                        <div
                          key={idx}
                          className="bg-surface border border-border/80 rounded p-2 text-left"
                        >
                          <div className="font-semibold text-textMain text-[11px]">
                            {inp.modality}
                          </div>
                          <div className="text-[10px] text-textMuted mt-0.5 line-clamp-2">
                            {inp.encoder}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Arrow */}
                    <div className="text-textMuted flex items-center justify-center p-1">
                      <span className="hidden md:inline text-lg font-bold">→</span>
                      <span className="md:hidden text-lg font-bold">↓</span>
                    </div>

                    {/* Fusion MLP */}
                    <div className="bg-surface border border-accent/40 rounded p-3 text-center w-full md:w-3/12 flex flex-col justify-center items-center shadow-sm">
                      <div className="font-bold text-accent text-xs">Fusion MLP</div>
                      <div className="text-[10px] text-textMuted mt-1 leading-tight">
                        {data.architecture.fusion}
                      </div>
                    </div>

                    {/* Arrow */}
                    <div className="text-textMuted flex items-center justify-center p-1">
                      <span className="hidden md:inline text-lg font-bold">→</span>
                      <span className="md:hidden text-lg font-bold">↓</span>
                    </div>

                    {/* P(success) */}
                    <div className="bg-surface border border-emerald-500/40 rounded p-3 text-center w-full md:w-4/12 flex flex-col justify-center items-center shadow-sm">
                      <div className="font-bold text-emerald-400 text-xs">
                        P(success) per candidate
                      </div>
                      <div className="text-[10px] text-textMuted mt-1">
                        Calibrated sigmoid ranking
                      </div>
                    </div>
                  </div>

                  {/* Training and Serving lines */}
                  <div className="bg-surface/50 border border-border/60 rounded p-2.5 space-y-1 text-[11px] font-mono">
                    <div>
                      <span className="text-textMuted uppercase font-bold text-[10px]">
                        Training:{' '}
                      </span>
                      <span className="text-textMain">{data.architecture.training}</span>
                    </div>
                    <div>
                      <span className="text-textMuted uppercase font-bold text-[10px]">
                        Serving:{' '}
                      </span>
                      <span className="text-textMain">{data.architecture.serving}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Tiny Score Breakdown per candidate */}
              <div className="space-y-1.5 pt-1">
                <div className="text-[10px] font-mono font-bold uppercase text-textMuted">
                  Score Breakdown (Inputs to P(success))
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {candidates.map((cand) => (
                    <div
                      key={cand.job_code}
                      className="bg-[#0d1117] border border-border/70 rounded p-2 text-xs font-mono space-y-1"
                    >
                      <div className="font-semibold text-white text-[11px] truncate">
                        #{cand.rank} {cand.job_name}
                      </div>
                      <div className="flex justify-between text-[10px]">
                        <span className="text-textMuted">Mechanism match:</span>
                        <span className="text-textMain font-medium">
                          {cand.p_inputs.p_mechanism != null
                            ? `${(cand.p_inputs.p_mechanism * 100).toFixed(0)}%`
                            : '—'}
                          {cand.p_inputs.diagnostic_fit
                            ? ` (${cand.p_inputs.diagnostic_fit})`
                            : ''}
                        </span>
                      </div>
                      <div className="flex justify-between text-[10px]">
                        <span className="text-textMuted">Historical success rate:</span>
                        <span className="text-textMain font-medium">
                          {cand.p_inputs.base_rate != null
                            ? `${(cand.p_inputs.base_rate * 100).toFixed(1)}%`
                            : '—'}
                          {cand.p_inputs.base_rate_n != null
                            ? ` (n=${cand.p_inputs.base_rate_n})`
                            : ''}
                        </span>
                      </div>
                      <div className="flex justify-between text-[10px]">
                        <span className="text-textMuted">Look-alike success rate:</span>
                        <span className="text-textMain font-medium">
                          {cand.p_inputs.analog_rate != null
                            ? `${(cand.p_inputs.analog_rate * 100).toFixed(1)}%`
                            : '—'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
