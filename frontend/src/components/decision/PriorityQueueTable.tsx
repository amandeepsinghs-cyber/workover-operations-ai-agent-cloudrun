import React, { useState, useEffect } from 'react';
import { AlertCircle, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import {
  decisionApi,
  BAND_COLORS,
  type Envelope,
  type FieldName,
  type PriorityQueues,
  type PriorityRow,
} from '../../api/decision';

export interface PriorityQueueTableProps {
  field: FieldName;
  limit?: number;
  selectedWellId?: string | null;
  onSelectWell?: (wellId: string) => void;
}

export const PriorityQueueTable: React.FC<PriorityQueueTableProps> = ({
  field,
  limit,
  selectedWellId,
  onSelectWell,
}) => {
  const [envelope, setEnvelope] = useState<Envelope<PriorityQueues> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'RIG' | 'RIGLESS'>('RIG');
  const [refusalsOpen, setRefusalsOpen] = useState<boolean>(false);
  const [unroutedOpen, setUnroutedOpen] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setFetchError(null);

    decisionApi
      .fieldPriority(field, 'all', limit ?? 20)
      .then((res) => {
        if (!cancelled) {
          setEnvelope(res);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setFetchError(err instanceof Error ? err.message : String(err));
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [field, limit]);

  const data = envelope?.data;
  const rigQueue: PriorityRow[] = data?.rig_queue ?? [];
  const riglessQueue: PriorityRow[] = data?.rigless_queue ?? [];
  const excludedRefusals: [string, string, string][] = data?.excluded_refusals ?? [];
  const excludedUnrouted: [string, string][] = data?.excluded_unrouted ?? [];
  const currentQueue = activeTab === 'RIG' ? rigQueue : riglessQueue;

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain space-y-4">
      {/* Title & Score Formula */}
      <div>
        <h2 className="text-sm font-semibold text-textMain tracking-tight">
          Priority queue — {field}
        </h2>
        {data?.score_formula && (
          <div className="text-[11px] font-mono text-textMuted mt-1">
            <span className="text-textMuted">Ranking: </span>
            <span>{data.score_formula}</span>
          </div>
        )}
      </div>

      {/* Fetch Error Banner */}
      {fetchError && (
        <div className="bg-red-950/40 border border-red-800/60 text-red-300 p-3 rounded-lg text-xs font-mono flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-critical" />
          <span>Error loading priority queue: {fetchError}</span>
        </div>
      )}

      {/* Non-OK Envelope Status Banner */}
      {envelope && envelope.status !== 'OK' && (
        <div className="bg-amber-950/40 border border-amber-800/60 text-amber-300 p-3 rounded-lg text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-warning" />
          <span>
            Status: {envelope.status} {envelope.message ? `— ${envelope.message}` : ''}
          </span>
        </div>
      )}

      {/* Loading Indicator */}
      {isLoading && (
        <div className="flex items-center justify-center p-8 font-mono text-xs text-textMuted">
          <span className="animate-spin mr-2">◌</span> Loading priority queue...
        </div>
      )}

      {/* Empty Data Placeholder (when not loading and data is null) */}
      {!isLoading && !data && !fetchError && (
        <div className="text-textMuted text-center py-6 font-mono text-xs">
          {envelope?.message || 'No priority queue data available'}
        </div>
      )}

      {/* Main Content Area */}
      {!isLoading && data && (
        <>
          {/* Tabs */}
          <div className="flex items-center gap-2 border-b border-border pb-2">
            <button
              type="button"
              onClick={() => setActiveTab('RIG')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'RIG'
                  ? 'bg-surface text-white border border-border font-medium'
                  : 'text-textMuted hover:text-textMain'
              }`}
            >
              Rig queue ({rigQueue.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('RIGLESS')}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === 'RIGLESS'
                  ? 'bg-surface text-white border border-border font-medium'
                  : 'text-textMuted hover:text-textMain'
              }`}
            >
              Rigless queue ({riglessQueue.length})
            </button>
          </div>

          {/* Table Container (sticky header, max-height ~420px with scroll) */}
          <div className="overflow-x-auto max-h-[420px] overflow-y-auto border border-border/60 rounded-md">
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-[#0d1117] z-10 shadow-sm">
                <tr className="border-b border-border text-[11px] font-mono uppercase text-textMuted font-bold">
                  <th className="py-2.5 px-3">Rank</th>
                  <th className="py-2.5 px-3">Well</th>
                  <th className="py-2.5 px-3">Mechanism</th>
                  <th className="py-2.5 px-3">Job</th>
                  <th className="py-2.5 px-3 text-right">Uplift BOPD</th>
                  <th className="py-2.5 px-3 text-right">Deferred bbl/12mo</th>
                  <th className="py-2.5 px-3 text-right">p_success</th>
                  <th className="py-2.5 px-3 text-right">Rig-days</th>
                  <th className="py-2.5 px-3 text-center">Cost band</th>
                  <th className="py-2.5 px-3 text-right">Score</th>
                  <th className="py-2.5 px-3">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono text-xs">
                {currentQueue.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="text-textMuted text-center py-6 font-mono text-xs">
                      No candidate wells in this queue
                    </td>
                  </tr>
                ) : (
                  currentQueue.map((row) => {
                    const isSelected = selectedWellId === row.well_id;
                    const bandColor = row.cost_band ? BAND_COLORS[row.cost_band] : null;

                    return (
                      <tr
                        key={`${row.well_id}-${row.rank}`}
                        onClick={() => onSelectWell?.(row.well_id)}
                        className={`cursor-pointer transition-colors hover:bg-surface/60 ${
                          isSelected ? 'bg-surface text-white font-semibold' : 'text-textMain'
                        }`}
                      >
                        {/* Rank */}
                        <td className="py-2.5 px-3 text-textMuted">
                          {row.rank != null ? row.rank : '—'}
                        </td>

                        {/* Well */}
                        <td className="py-2.5 px-3 font-medium text-accent">
                          {row.well_id || '—'}
                        </td>

                        {/* Mechanism (+ mechanism_source as tooltip/title) */}
                        <td className="py-2.5 px-3 font-sans" title={row.mechanism_source || undefined}>
                          <span className="truncate block max-w-[140px]">
                            {row.mechanism || '—'}
                          </span>
                        </td>

                        {/* Job (job_name, job_code muted) */}
                        <td className="py-2.5 px-3 font-sans">
                          <div className="flex flex-col">
                            <span className="truncate max-w-[160px]">{row.job_name || '—'}</span>
                            {row.job_code && (
                              <span className="text-[10px] font-mono text-textMuted">
                                {row.job_code}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Uplift BOPD */}
                        <td className="py-2.5 px-3 text-right">
                          {row.uplift_bopd != null
                            ? typeof row.uplift_bopd === 'number'
                              ? row.uplift_bopd.toFixed(1)
                              : row.uplift_bopd
                            : '—'}
                        </td>

                        {/* Deferred bbl/12mo */}
                        <td className="py-2.5 px-3 text-right">
                          {row.deferred_bbl_avoided_12mo != null
                            ? typeof row.deferred_bbl_avoided_12mo === 'number'
                              ? row.deferred_bbl_avoided_12mo.toLocaleString(undefined, {
                                  maximumFractionDigits: 0,
                                })
                              : row.deferred_bbl_avoided_12mo
                            : '—'}
                        </td>

                        {/* p_success (percentage, with '(n=' p_success_n ')') */}
                        <td className="py-2.5 px-3 text-right text-textMuted">
                          {row.p_success != null
                            ? `${Math.round(row.p_success * 100)}% (n=${row.p_success_n ?? 0})`
                            : '—'}
                        </td>

                        {/* Rig-days */}
                        <td className="py-2.5 px-3 text-right text-textMuted">
                          {row.rig_days != null
                            ? typeof row.rig_days === 'number'
                              ? row.rig_days.toFixed(1)
                              : row.rig_days
                            : '—'}
                        </td>

                        {/* Cost band (chip using BAND_COLORS) */}
                        <td className="py-2.5 px-3 text-center">
                          {row.cost_band && bandColor ? (
                            <span
                              className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono font-medium tracking-wide whitespace-nowrap"
                              style={{
                                backgroundColor: `${bandColor}20`,
                                color: bandColor,
                                border: `1px solid ${bandColor}40`,
                              }}
                            >
                              {row.cost_band}
                            </span>
                          ) : (
                            <span className="text-textMuted font-mono">—</span>
                          )}
                        </td>

                        {/* Score (priority_score) */}
                        <td className="py-2.5 px-3 text-right font-semibold">
                          {row.priority_score != null
                            ? typeof row.priority_score === 'number'
                              ? row.priority_score.toFixed(1)
                              : row.priority_score
                            : '—'}
                        </td>

                        {/* Severity (highest_severity or '—') */}
                        <td className="py-2.5 px-3 text-textMuted text-[11px]">
                          {row.highest_severity || '—'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Collapsible Sections Below Table */}
          <div className="space-y-2 pt-1">
            {/* Refusals — no job justified (n) */}
            <div className="border border-border/70 rounded-lg overflow-hidden bg-surface/30">
              <button
                type="button"
                onClick={() => setRefusalsOpen((prev) => !prev)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono text-textMuted hover:text-textMain hover:bg-surface/50 transition-colors"
              >
                <div className="flex items-center gap-1.5 font-medium">
                  {refusalsOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-textMuted" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-textMuted" />
                  )}
                  <span>Refusals — no job justified ({excludedRefusals.length})</span>
                </div>
              </button>
              {refusalsOpen && (
                <div className="border-t border-border/50 max-h-48 overflow-y-auto">
                  {excludedRefusals.length === 0 ? (
                    <div className="p-3 text-[11px] text-textMuted font-mono">None</div>
                  ) : (
                    <table className="w-full border-collapse text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/40 text-[10px] font-mono uppercase text-textMuted bg-[#0d1117]/80">
                          <th className="py-1.5 px-3">Well</th>
                          <th className="py-1.5 px-3">Job Code</th>
                          <th className="py-1.5 px-3">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/20 font-mono text-[11px]">
                        {excludedRefusals.map(([wellId, jobCode, reason], idx) => {
                          const isSelected = selectedWellId === wellId;
                          return (
                            <tr
                              key={`${wellId}-${jobCode}-${idx}`}
                              onClick={() => onSelectWell?.(wellId)}
                              className={`cursor-pointer transition-colors hover:bg-surface/60 ${
                                isSelected ? 'bg-surface text-white font-semibold' : 'text-textMain'
                              }`}
                            >
                              <td className="py-1.5 px-3 font-medium text-accent">
                                {wellId || '—'}
                              </td>
                              <td className="py-1.5 px-3 text-textMuted">{jobCode || '—'}</td>
                              <td className="py-1.5 px-3 text-textMuted">{reason || '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>

            {/* Needs engineer review (n) */}
            <div className="border border-border/70 rounded-lg overflow-hidden bg-surface/30">
              <button
                type="button"
                onClick={() => setUnroutedOpen((prev) => !prev)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono text-textMuted hover:text-textMain hover:bg-surface/50 transition-colors"
              >
                <div className="flex items-center gap-1.5 font-medium">
                  {unroutedOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-textMuted" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-textMuted" />
                  )}
                  <span>Needs engineer review ({excludedUnrouted.length})</span>
                </div>
              </button>
              {unroutedOpen && (
                <div className="border-t border-border/50 max-h-48 overflow-y-auto">
                  {excludedUnrouted.length === 0 ? (
                    <div className="p-3 text-[11px] text-textMuted font-mono">None</div>
                  ) : (
                    <table className="w-full border-collapse text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/40 text-[10px] font-mono uppercase text-textMuted bg-[#0d1117]/80">
                          <th className="py-1.5 px-3">Well</th>
                          <th className="py-1.5 px-3">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/20 font-mono text-[11px]">
                        {excludedUnrouted.map(([wellId, reason], idx) => {
                          const isSelected = selectedWellId === wellId;
                          return (
                            <tr
                              key={`${wellId}-${idx}`}
                              onClick={() => onSelectWell?.(wellId)}
                              className={`cursor-pointer transition-colors hover:bg-surface/60 ${
                                isSelected ? 'bg-surface text-white font-semibold' : 'text-textMain'
                              }`}
                            >
                              <td className="py-1.5 px-3 font-medium text-accent">
                                {wellId || '—'}
                              </td>
                              <td className="py-1.5 px-3 text-textMuted">{reason || '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Provenance Badge Footer */}
      {envelope?.provenance && (
        <div className="text-[10px] font-mono text-textMuted/70 border-t border-border/50 pt-2 flex items-center justify-between">
          <span>
            {envelope.provenance.tool_id} · as of {envelope.provenance.as_of}
          </span>
          {envelope.provenance.duration_ms != null && (
            <span>{envelope.provenance.duration_ms} ms</span>
          )}
        </div>
      )}
    </div>
  );
};
