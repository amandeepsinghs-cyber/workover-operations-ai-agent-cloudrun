import React, { useState, useEffect, useMemo } from 'react';
import { AlertCircle, AlertTriangle } from 'lucide-react';
import { BUCKET_COLORS } from '../../api/asset';
import {
  decisionApi,
  Envelope,
  FieldName,
  HealthBucket,
  HealthBuckets,
} from '../../api/decision';

export interface HealthBucketsCardProps {
  field: FieldName;
  clusterId?: string;
  selectedWellId?: string | null;
  onSelectWell?: (wellId: string) => void;
}

export const HealthBucketsCard: React.FC<HealthBucketsCardProps> = ({
  field,
  clusterId,
  selectedWellId,
  onSelectWell,
}) => {
  const [envelope, setEnvelope] = useState<Envelope<HealthBuckets> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [selectedBucket, setSelectedBucket] = useState<HealthBucket | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setFetchError(null);

    decisionApi
      .fieldHealth(field, clusterId)
      .then((res) => {
        if (isMounted) {
          setEnvelope(res);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setFetchError(err instanceof Error ? err.message : String(err));
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [field, clusterId]);

  const data = envelope?.data;

  const filteredWells = useMemo(() => {
    if (!data?.wells) return [];
    if (!selectedBucket) return data.wells;
    return data.wells.filter((w) => w.bucket === selectedBucket);
  }, [data, selectedBucket]);

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans space-y-4">
      {/* Fetch Error Display */}
      {fetchError && (
        <div className="bg-rose-950/40 border border-rose-800/60 text-rose-300 p-3 rounded-lg text-xs font-mono flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-critical" />
          <span>Error loading health data: {fetchError}</span>
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

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center p-8 font-mono text-xs text-textMuted">
          <span className="animate-spin mr-2">◌</span> Loading well health...
        </div>
      )}

      {/* Fallback when data is null and not loading */}
      {!isLoading && !data && (
        <div className="text-center py-6 text-textMuted font-mono">
          {envelope?.message || 'No health data available.'}
        </div>
      )}

      {/* Main Content */}
      {!isLoading && data && (
        <>
          {/* Header: title, total_wells, as_of */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-3">
            <div>
              <h2 className="text-xs font-mono font-bold uppercase text-textMain">
                Well health — {data.field}
                {data.cluster_id ? ` · ${data.cluster_id}` : ''}
              </h2>
            </div>
            <div className="text-[11px] font-mono text-textMuted">
              {data.total_wells} wells · as of {data.as_of}
            </div>
          </div>

          {/* Horizontal stacked bar (pure divs, widths = count/total) */}
          <div className="w-full h-2.5 rounded-full overflow-hidden flex bg-border/40">
            {(Object.keys(data.counts) as HealthBucket[]).map((bucket) => {
              const count = data.counts[bucket] ?? 0;
              const pct = data.total_wells > 0 ? (count / data.total_wells) * 100 : 0;
              if (pct <= 0) return null;
              const color = BUCKET_COLORS[bucket] || '#8b949e';
              return (
                <div
                  key={bucket}
                  style={{
                    width: `${pct}%`,
                    backgroundColor: color,
                  }}
                  title={`${bucket.replace(/_/g, ' ')}: ${count} (${pct.toFixed(1)}%)`}
                  className="h-full transition-all duration-200"
                />
              );
            })}
          </div>

          {/* Four bucket tiles in the order of Object.keys(data.counts) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {(Object.keys(data.counts) as HealthBucket[]).map((bucket) => {
              const count = data.counts[bucket] ?? 0;
              const pct = data.total_wells > 0 ? (count / data.total_wells) * 100 : 0;
              const color = BUCKET_COLORS[bucket] || '#8b949e';
              const isSelected = selectedBucket === bucket;

              return (
                <button
                  key={bucket}
                  type="button"
                  onClick={() =>
                    setSelectedBucket((prev) => (prev === bucket ? null : bucket))
                  }
                  className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
                    isSelected
                      ? 'shadow-sm ring-1'
                      : 'border-border/60 bg-[#161b22]/50 hover:bg-surface/60 hover:border-border'
                  }`}
                  style={
                    isSelected
                      ? {
                          borderColor: color,
                          backgroundColor: `${color}15`,
                          boxShadow: `0 0 0 1px ${color}40`,
                        }
                      : undefined
                  }
                >
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-[10px] font-mono uppercase text-textMuted tracking-wider truncate">
                      {bucket.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between gap-1">
                    <span className="text-base font-bold font-mono text-textMain">
                      {count}
                    </span>
                    <span className="text-[11px] font-mono text-textMuted">
                      {pct.toFixed(1)}%
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Sick or lost production line */}
          <div className="flex items-center justify-between text-xs font-mono text-textMuted py-0.5">
            <div>
              Sick or lost production:{' '}
              <span className="font-bold text-amber-400">{data.sick_or_lost_count}</span>
            </div>
            {selectedBucket && (
              <button
                type="button"
                onClick={() => setSelectedBucket(null)}
                className="text-[11px] text-accent hover:underline cursor-pointer"
              >
                Clear filter
              </button>
            )}
          </div>

          {/* Wells list: max-height with scroll */}
          <div className="max-h-64 overflow-y-auto overflow-x-auto border border-border/60 rounded-lg bg-[#0d1117]">
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-[#161b22] border-b border-border text-[11px] font-mono uppercase text-textMuted font-bold z-10">
                <tr>
                  <th className="py-2 px-3">Well</th>
                  <th className="py-2 px-3">Bucket</th>
                  <th className="py-2 px-3">Reason</th>
                  <th className="py-2 px-3 text-right">Since</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono text-xs">
                {filteredWells.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-textMuted font-sans">
                      No wells found for this selection
                    </td>
                  </tr>
                ) : (
                  filteredWells.map((well) => {
                    const isSelected = selectedWellId === well.well_id;
                    const bucketColor = BUCKET_COLORS[well.bucket] || '#8b949e';
                    const bucketText = well.bucket.replace(/_/g, ' ');

                    return (
                      <tr
                        key={well.well_id}
                        onClick={() => onSelectWell?.(well.well_id)}
                        className={`cursor-pointer transition-colors hover:bg-surface/60 ${
                          isSelected ? 'bg-surface text-white font-semibold' : 'text-textMain'
                        }`}
                      >
                        <td className="py-2 px-3 font-medium whitespace-nowrap">
                          {well.well_id || '—'}
                        </td>
                        <td className="py-2 px-3">
                          <span
                            className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium tracking-wide whitespace-nowrap capitalize font-sans"
                            style={{
                              backgroundColor: `${bucketColor}20`,
                              color: bucketColor,
                              border: `1px solid ${bucketColor}40`,
                            }}
                          >
                            {bucketText.toLowerCase()}
                          </span>
                        </td>
                        <td className="py-2 px-3 font-sans text-xs">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-textMain">{well.reason || '—'}</span>
                            {well.recoverable === false && (
                              <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-rose-950/60 border border-rose-700/60 text-rose-300">
                                unrecoverable
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2 px-3 text-right text-textMuted text-[11px] whitespace-nowrap">
                          {well.since || '—'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Footer: rule + provenance */}
          {(data.rule || envelope?.provenance) && (
            <div className="pt-2 border-t border-border/50 space-y-1">
              {data.rule && (
                <div className="text-[11px] font-sans text-textMuted italic">
                  Rule: {data.rule}
                </div>
              )}
              {envelope?.provenance && (
                <div className="text-[10px] font-mono text-textMuted/70 flex items-center justify-between">
                  <span>
                    {envelope.provenance.tool_id} · as of {envelope.provenance.as_of}
                  </span>
                  {envelope.provenance.duration_ms != null && (
                    <span>{envelope.provenance.duration_ms} ms</span>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Footer when data is null but envelope with provenance exists */}
      {!isLoading && !data && envelope?.provenance && (
        <div className="pt-2 border-t border-border/50 text-[10px] font-mono text-textMuted/70 flex items-center justify-between">
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
