import React, { useState, useEffect } from 'react';
import { Loader2, AlertTriangle, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import {
  decisionApi,
  docUrl,
  FIT_COLORS,
  BAND_COLORS,
  Envelope,
  NextBestActions,
} from '../../api/decision';

export interface NbaCardProps {
  wellId: string;
  topK?: number;
  onCompare?: (jobCode: string) => void;
}

const AMBER_FLAGS = new Set([
  'MODEL_PHYSICS_DISAGREEMENT',
  'G1_CONING_GUARDRAIL',
  'G2_RESERVOIR_DECLINE',
]);

export const NbaCard: React.FC<NbaCardProps> = ({ wellId, topK = 3, onCompare }) => {
  const [envelope, setEnvelope] = useState<Envelope<NextBestActions> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [expandedWhy, setExpandedWhy] = useState<Record<string, boolean>>({});
  const [expandedSop, setExpandedSop] = useState<Record<string, boolean>>({});
  const [rejectedOpen, setRejectedOpen] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    decisionApi
      .nba(wellId, topK ?? 3)
      .then((res) => {
        if (!cancelled) {
          setEnvelope(res);
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
  }, [wellId, topK]);

  const toggleWhy = (jobCode: string) => {
    setExpandedWhy((prev) => ({ ...prev, [jobCode]: !prev[jobCode] }));
  };

  const toggleSop = (jobCode: string) => {
    setExpandedSop((prev) => ({ ...prev, [jobCode]: !prev[jobCode] }));
  };

  if (loading) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="font-mono uppercase font-bold text-textMain tracking-wide">Next best action</span>
            <span className="font-mono text-textMuted">·</span>
            <span className="font-mono font-medium text-textMain">{wellId}</span>
          </div>
        </div>
        <div className="py-8 flex items-center justify-center gap-2 text-textMuted font-mono">
          <Loader2 className="w-4 h-4 animate-spin text-accent" />
          <span>Loading next best actions...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="font-mono uppercase font-bold text-textMain tracking-wide">Next best action</span>
            <span className="font-mono text-textMuted">·</span>
            <span className="font-mono font-medium text-textMain">{wellId}</span>
          </div>
        </div>
        <div className="p-3 my-4 rounded bg-critical/10 border border-critical/30 text-critical text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  const data = envelope?.data ?? null;

  if (!data) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="font-mono uppercase font-bold text-textMain tracking-wide">Next best action</span>
            <span className="font-mono text-textMuted">·</span>
            <span className="font-mono font-medium text-textMain">{wellId}</span>
          </div>
        </div>
        <div className="py-4">
          {envelope && envelope.status !== 'OK' ? (
            <div
              className={`p-2.5 rounded border text-xs flex items-center gap-2 ${
                envelope.status === 'UNAVAILABLE' || envelope.status === 'DISCRIMINATOR_UNAVAILABLE'
                  ? 'bg-critical/10 border-critical/30 text-critical'
                  : 'bg-warning/10 border-warning/30 text-warning'
              }`}
            >
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span className="font-mono uppercase font-bold">{envelope.status}</span>
              <span className="text-textMuted">{envelope.message}</span>
            </div>
          ) : (
            <div className="text-textMuted text-center py-4">{envelope?.message || 'No action data available'}</div>
          )}
        </div>
        {envelope?.provenance && (
          <div className="pt-2.5 border-t border-border/40 text-[10px] font-mono text-textMuted flex items-center justify-between">
            <span>{envelope.provenance.tool_id}</span>
            <span>as of {envelope.provenance.as_of}</span>
          </div>
        )}
      </div>
    );
  }

  const sortedActions = [...(data.actions || [])].sort((a, b) => a.rank - b.rank);
  const showDisagreement = Boolean(
    data.ml_suggestion &&
      data.physics_route &&
      data.ml_suggestion.ic !== data.physics_route.ic
  );

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="font-mono uppercase font-bold text-textMain tracking-wide">Next best action</span>
          <span className="font-mono text-textMuted">·</span>
          <span className="font-mono font-medium text-textMain">{data.well_id}</span>
        </div>
        <div className="font-mono text-[11px] text-textMuted">
          as of {data.as_of || '—'}
        </div>
      </div>

      {/* Non-OK Envelope Status Banner */}
      {envelope && envelope.status !== 'OK' && (
        <div
          className={`p-2.5 rounded border text-xs flex items-center gap-2 ${
            envelope.status === 'UNAVAILABLE' || envelope.status === 'DISCRIMINATOR_UNAVAILABLE'
              ? 'bg-critical/10 border-critical/30 text-critical'
              : 'bg-warning/10 border-warning/30 text-warning'
          }`}
        >
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span className="font-mono uppercase font-bold">{envelope.status}</span>
          <span className="text-textMuted">{envelope.message}</span>
        </div>
      )}

      {/* Flag chips */}
      {data.flags && data.flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.flags.map((flag) => {
            const isAmber = AMBER_FLAGS.has(flag);
            return (
              <span
                key={flag}
                className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                  isAmber
                    ? 'bg-warning/15 text-warning border border-warning/40 font-medium'
                    : 'bg-surface text-textMuted border border-border'
                }`}
              >
                {flag}
              </span>
            );
          })}
        </div>
      )}

      {/* Disagreement Strip */}
      {showDisagreement && data.ml_suggestion && data.physics_route && (
        <div className="p-2.5 rounded bg-warning/10 border border-warning/30 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
            <div className="font-mono text-warning">
              <span className="font-semibold uppercase text-textMuted mr-1">ML suggests:</span>
              <span>
                {data.ml_suggestion.ic} {data.ml_suggestion.label}{' '}
                {data.ml_suggestion.prob != null
                  ? `${(data.ml_suggestion.prob > 1 ? data.ml_suggestion.prob : data.ml_suggestion.prob * 100).toFixed(1)}%`
                  : ''}
              </span>
            </div>
            <div className="font-mono text-textMain border-t md:border-t-0 md:border-l border-border/50 pt-1 md:pt-0 md:pl-2">
              <span className="font-semibold uppercase text-textMuted mr-1">Physics route:</span>
              <span>
                {data.physics_route.job_code} ({data.physics_route.mechanism}, {data.physics_route.source})
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="space-y-4">
        {sortedActions.map((action) => {
          const fitColor = action.diagnostic_fit ? FIT_COLORS[action.diagnostic_fit] || '#8b949e' : '#8b949e';
          const bandColor = action.cost_band ? BAND_COLORS[action.cost_band] || '#8b949e' : '#8b949e';
          const sopLink = action.sop_url || (action.sop_doc_id ? docUrl(action.sop_doc_id) : null);

          return (
            <div
              key={action.job_code}
              className="bg-surface/30 border border-border/70 rounded-lg p-3.5 space-y-3"
            >
              {/* Top row: Rank, Job, IC, Guardrail, onCompare button */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-accent/15 text-accent border border-accent/30">
                    #{action.rank}
                  </span>
                  <span className="font-semibold text-textMain text-sm">
                    {action.job_name}
                  </span>
                  <span className="font-mono text-textMuted text-[11px]">
                    ({action.job_code})
                  </span>
                  <span className="font-mono text-textMuted text-[11px]">
                    {action.ic} · {action.ic_label}
                  </span>
                  {action.guardrail && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-warning/15 text-warning border border-warning/40">
                      {action.guardrail}
                    </span>
                  )}
                </div>

                {action.rank === 1 && onCompare && (
                  <button
                    type="button"
                    onClick={() => onCompare(action.job_code)}
                    className="px-2.5 py-1 rounded text-[11px] font-medium bg-surface border border-border hover:border-accent hover:text-accent transition-colors flex items-center gap-1.5 text-textMain"
                  >
                    Why not another job?
                  </button>
                )}
              </div>

              {/* Diagnostic Fit Chip + Evidence */}
              <div className="flex flex-wrap items-center gap-2">
                {action.diagnostic_fit && (
                  <span
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium"
                    style={{
                      backgroundColor: `${fitColor}20`,
                      color: fitColor,
                      border: `1px solid ${fitColor}40`,
                    }}
                  >
                    <span>{action.fit_symbol}</span>
                    <span>{action.diagnostic_fit}</span>
                  </span>
                )}
                {action.fit_evidence && (
                  <span className="text-[11px] text-textMuted italic">
                    {action.fit_evidence}
                  </span>
                )}
              </div>

              {/* Compact Metric Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 p-2.5 bg-surface/50 rounded border border-border/40 text-[11px] font-mono">
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Uplift</div>
                  <div className="text-textMain font-medium">
                    {action.uplift_bopd != null ? `${action.uplift_bopd.toFixed(1)} BOPD` : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Deferred</div>
                  <div className="text-textMain font-medium">
                    {action.deferred_bbl_12mo != null ? `${action.deferred_bbl_12mo.toLocaleString()} bbl / 12 mo` : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">P(Success)</div>
                  <div className="text-textMain font-medium">
                    {action.p_success != null
                      ? `${(action.p_success > 1 ? action.p_success : action.p_success * 100).toFixed(1)}% (n=${action.p_success_n ?? '—'})`
                      : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Rig requirement</div>
                  <div className="text-textMain font-medium">
                    {!action.requires_rig
                      ? 'rigless'
                      : `${action.rig_days != null ? action.rig_days.toFixed(1) : '—'} rig-days`}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Duration</div>
                  <div className="text-textMain font-medium">
                    {action.duration_days_min != null ? action.duration_days_min : '—'}–
                    {action.duration_days_max != null ? action.duration_days_max : '—'} d
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Unit Type</div>
                  <div className="text-textMain font-medium truncate" title={action.unit_type || '—'}>
                    {action.unit_type || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Cost Band</div>
                  <div className="pt-0.5">
                    {action.cost_band ? (
                      <span
                        className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium uppercase"
                        style={{
                          backgroundColor: `${bandColor}20`,
                          color: bandColor,
                          border: `1px solid ${bandColor}40`,
                        }}
                      >
                        {action.cost_band}
                      </span>
                    ) : (
                      <span className="text-textMuted">—</span>
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">MRO Status</div>
                  <div className="text-textMain font-medium text-[10px]" title={action.mro_blocker || undefined}>
                    {action.mro_status || '—'}
                    {action.mro_blocker ? ` (${action.mro_blocker})` : ''}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Earliest Start</div>
                  <div className="text-textMain font-medium">
                    {action.earliest_start_date || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-textMuted uppercase font-sans">Score</div>
                  <div className="text-accent font-bold">
                    {action.score != null ? action.score.toFixed(1) : '—'}
                  </div>
                </div>
              </div>

              {/* Risk flags chips */}
              {action.risk_flags && action.risk_flags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {action.risk_flags.map((flag) => (
                    <span
                      key={flag}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-critical/15 text-critical border border-critical/30"
                    >
                      {flag}
                    </span>
                  ))}
                </div>
              )}

              {/* Collapsible Why */}
              <div className="border border-border/40 rounded bg-surface/20">
                <button
                  type="button"
                  onClick={() => toggleWhy(action.job_code)}
                  className="w-full px-2.5 py-1.5 text-left flex items-center justify-between text-textMuted hover:text-textMain font-mono text-[11px]"
                >
                  <span className="font-semibold uppercase">Why</span>
                  {expandedWhy[action.job_code] ? (
                    <ChevronDown className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5" />
                  )}
                </button>
                {expandedWhy[action.job_code] && (
                  <div className="px-2.5 pb-2.5 text-[11px] text-textMain border-t border-border/30 pt-1.5 leading-relaxed font-sans">
                    {action.why || '—'}
                  </div>
                )}
              </div>

              {/* Collapsible SOP */}
              <div className="border border-border/40 rounded bg-surface/20">
                <div className="w-full px-2.5 py-1.5 flex items-center justify-between text-[11px]">
                  <button
                    type="button"
                    onClick={() => toggleSop(action.job_code)}
                    className="flex items-center gap-1.5 text-textMuted hover:text-textMain font-mono font-semibold uppercase"
                  >
                    <span>SOP</span>
                    {expandedSop[action.job_code] ? (
                      <ChevronDown className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <div>
                    {sopLink ? (
                      <a
                        href={sopLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent hover:underline inline-flex items-center gap-1 font-mono text-[11px]"
                      >
                        <span>Open SOP</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="text-textMuted italic text-[11px]">No SOP (no field job)</span>
                    )}
                  </div>
                </div>
                {expandedSop[action.job_code] && (
                  <div className="px-2.5 pb-2.5 border-t border-border/30 pt-2 space-y-2">
                    {action.sop_steps && action.sop_steps.length > 0 ? (
                      action.sop_steps.map((phase, pIdx) => (
                        <div key={pIdx} className="space-y-1">
                          <div className="font-bold text-textMain text-[11px] font-mono">
                            {phase.phase}
                          </div>
                          {phase.steps && phase.steps.length > 0 && (
                            <ol className="list-decimal list-inside space-y-0.5 text-textMuted pl-1 text-[11px]">
                              {phase.steps.map((step, sIdx) => (
                                <li key={sIdx}>{step}</li>
                              ))}
                            </ol>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="text-textMuted italic text-[11px]">No SOP steps available</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Collapsible Rejected List */}
      {data.rejected && data.rejected.length > 0 && (
        <div className="border border-border/40 rounded bg-surface/30">
          <button
            type="button"
            onClick={() => setRejectedOpen(!rejectedOpen)}
            className="w-full px-3 py-2 text-left flex items-center justify-between text-textMuted hover:text-textMain font-mono uppercase text-[11px]"
          >
            <span>Rejected ({data.rejected.length})</span>
            {rejectedOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
          {rejectedOpen && (
            <div className="px-3 pb-3 space-y-2 border-t border-border/30 pt-2">
              {data.rejected.map((item, idx) => (
                <div key={idx} className="text-[11px] font-mono flex flex-wrap items-baseline gap-2 text-textMuted">
                  <span className="font-semibold text-textMain">{item.job_code || '—'}</span>
                  <span className="px-1 py-0.5 rounded bg-surface border border-border text-[10px]">{item.ic}</span>
                  <span className="font-sans text-textMuted">{item.reason}</span>
                  {item.demoted_by && (
                    <span className="text-[10px] text-warning italic font-sans">(demoted by: {item.demoted_by})</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Notes & Score Formula */}
      {data.notes && data.notes.length > 0 && (
        <ul className="list-disc list-inside space-y-0.5 text-textMuted text-[11px]">
          {data.notes.map((note, idx) => (
            <li key={idx}>{note}</li>
          ))}
        </ul>
      )}

      {data.score_formula && (
        <div className="font-mono text-[10px] text-textMuted p-2 bg-surface/60 rounded border border-border/40 overflow-x-auto">
          Score formula: {data.score_formula}
        </div>
      )}

      {/* Footer */}
      {envelope?.provenance && (
        <div className="pt-2.5 border-t border-border/40 text-[10px] font-mono text-textMuted flex items-center justify-between">
          <span>{envelope.provenance.tool_id}</span>
          <span>as of {envelope.provenance.as_of}</span>
        </div>
      )}
    </div>
  );
};
