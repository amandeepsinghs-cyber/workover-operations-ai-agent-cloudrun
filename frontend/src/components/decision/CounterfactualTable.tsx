import React, { useState, useEffect } from 'react';
import { Loader2, AlertTriangle, ExternalLink, FileText } from 'lucide-react';
import {
  decisionApi,
  docUrl,
  NextBestActions,
  Counterfactual,
  CounterfactualCell,
  CounterfactualVerdict,
  Envelope,
} from '../../api/decision';

export interface CounterfactualTableProps {
  wellId: string;
  recommended?: string;
  initialAlternative?: string;
}

const VERDICT_MAP: Record<
  CounterfactualVerdict,
  { label: string; color: string; bg: string; border: string }
> = {
  RECOMMENDED_PREFERRED: {
    label: 'Recommended preferred',
    color: '#2ea043',
    bg: 'rgba(46, 160, 67, 0.15)',
    border: 'rgba(46, 160, 67, 0.4)',
  },
  ALTERNATIVE_PREFERRED: {
    label: 'Alternative preferred',
    color: '#d29922',
    bg: 'rgba(210, 153, 34, 0.15)',
    border: 'rgba(210, 153, 34, 0.4)',
  },
  CLOSE: {
    label: 'Close call',
    color: '#d29922',
    bg: 'rgba(210, 153, 34, 0.15)',
    border: 'rgba(210, 153, 34, 0.4)',
  },
  NEITHER_FITS: {
    label: 'Neither fits',
    color: '#f85149',
    bg: 'rgba(248, 81, 73, 0.15)',
    border: 'rgba(248, 81, 73, 0.4)',
  },
};

const SYMBOL_COLORS: Record<string, string> = {
  '✔': '#2ea043',
  '?': '#d29922',
  '✘': '#f85149',
};

function renderCellContent(cell: CounterfactualCell | null | undefined) {
  if (!cell) return <span className="text-textMuted">—</span>;

  let summaryText = cell.summary || '';
  if (cell.symbol && summaryText.startsWith(cell.symbol)) {
    summaryText = summaryText.slice(cell.symbol.length).trim();
  }

  const symbolColor = cell.symbol ? SYMBOL_COLORS[cell.symbol] || '#8b949e' : undefined;

  return (
    <div className="flex items-start gap-1.5 leading-snug">
      {cell.symbol && (
        <span
          className="font-bold shrink-0 text-sm leading-none mt-0.5"
          style={{ color: symbolColor }}
        >
          {cell.symbol}
        </span>
      )}
      <span className="text-textMain break-words">{summaryText || '—'}</span>
    </div>
  );
}

export const CounterfactualTable: React.FC<CounterfactualTableProps> = ({
  wellId,
  recommended: recommendedProp,
  initialAlternative,
}) => {
  const [nbaEnvelope, setNbaEnvelope] = useState<Envelope<NextBestActions> | null>(null);
  const [nbaLoading, setNbaLoading] = useState<boolean>(true);
  const [nbaError, setNbaError] = useState<string | null>(null);

  const [selectedAlt, setSelectedAlt] = useState<string>(initialAlternative || '');
  const [compareEnvelope, setCompareEnvelope] = useState<Envelope<Counterfactual> | null>(null);
  const [compareLoading, setCompareLoading] = useState<boolean>(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Sync initialAlternative when prop changes
  useEffect(() => {
    if (initialAlternative) {
      setSelectedAlt(initialAlternative);
    }
  }, [initialAlternative]);

  // Fetch NBA on mount / wellId change
  useEffect(() => {
    if (!wellId) return;

    let cancelled = false;
    setNbaLoading(true);
    setNbaError(null);
    setSelectedAlt(initialAlternative || '');
    setCompareEnvelope(null);
    setCompareError(null);

    decisionApi
      .nba(wellId)
      .then((env) => {
        if (!cancelled) {
          setNbaEnvelope(env);
          setNbaLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setNbaError(err instanceof Error ? err.message : String(err));
          setNbaLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [wellId]);

  const rank1JobCode = nbaEnvelope?.data?.actions?.[0]?.job_code;
  const effectiveRecommended = recommendedProp || rank1JobCode;

  // Fetch Compare when wellId, selectedAlt, or effectiveRecommended is resolved
  useEffect(() => {
    if (!wellId || !selectedAlt || !effectiveRecommended) {
      if (!selectedAlt) {
        setCompareEnvelope(null);
      }
      return;
    }

    let cancelled = false;
    setCompareLoading(true);
    setCompareError(null);

    decisionApi
      .compare(wellId, selectedAlt, effectiveRecommended)
      .then((env) => {
        if (!cancelled) {
          setCompareEnvelope(env);
          setCompareLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setCompareError(err instanceof Error ? err.message : String(err));
          setCompareLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [wellId, selectedAlt, effectiveRecommended]);

  // Provenance resolution (prefer compare, fallback to nba)
  const provenance = compareEnvelope?.provenance || nbaEnvelope?.provenance;

  // Find recommended job display name
  const recAction = nbaEnvelope?.data?.actions?.find(
    (a) => a.job_code === effectiveRecommended
  );
  const recMenuItem = nbaEnvelope?.data?.job_menu?.find(
    (m) => m.job_code === effectiveRecommended
  );
  const recommendedName =
    recAction?.job_name ||
    recMenuItem?.job_name ||
    compareEnvelope?.data?.recommended?.job_name ||
    effectiveRecommended ||
    '—';

  // Menu items for alternative picker, excluding recommended job
  const menuItems = (nbaEnvelope?.data?.job_menu || []).filter(
    (item) => item.job_code !== effectiveRecommended
  );

  const cf = compareEnvelope?.data;

  const verdictInfo = cf?.verdict
    ? VERDICT_MAP[cf.verdict] || {
        label: cf.verdict,
        color: '#8b949e',
        bg: 'rgba(139, 148, 158, 0.15)',
        border: 'rgba(139, 148, 158, 0.4)',
      }
    : null;

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans text-textMain">
      {/* NBA Non-OK Status Banner */}
      {nbaEnvelope && nbaEnvelope.status !== 'OK' && (
        <div className="bg-amber-950/30 border border-amber-500/40 text-amber-200 text-xs px-3 py-2 rounded flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{nbaEnvelope.message || `Status: ${nbaEnvelope.status}`}</span>
        </div>
      )}

      {/* NBA Fetch Error */}
      {nbaError && (
        <div className="bg-critical/10 border border-critical/40 text-critical text-xs px-3 py-2 rounded flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>Failed to load actions: {nbaError}</span>
        </div>
      )}

      {/* NBA Loading */}
      {nbaLoading ? (
        <div className="flex items-center justify-center p-8 text-textMuted text-xs font-mono">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          Loading actions...
        </div>
      ) : !nbaEnvelope?.data ? (
        <div className="text-xs text-textMuted italic py-6 text-center">
          {nbaEnvelope?.message || 'No action data available'}
        </div>
      ) : (
        <>
          {/* Header Controls: Recommended (read-only) + Alternative (<select>) */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-border/60">
            <div>
              <div className="text-[10px] font-mono uppercase text-textMuted font-bold mb-1">
                Recommended Action
              </div>
              <div className="text-xs font-semibold text-healthy flex items-center gap-1.5">
                <span>{recommendedName}</span>
                {effectiveRecommended && (
                  <span className="text-[10px] font-mono text-textMuted font-normal">
                    ({effectiveRecommended})
                  </span>
                )}
              </div>
            </div>

            <div className="sm:text-right">
              <label
                htmlFor="alternative-picker"
                className="block text-[10px] font-mono uppercase text-textMuted font-bold mb-1"
              >
                Alternative Action
              </label>
              <select
                id="alternative-picker"
                value={selectedAlt}
                onChange={(e) => setSelectedAlt(e.target.value)}
                className="bg-surface border border-border rounded px-2.5 py-1 text-textMain focus:outline-none focus:border-accent text-xs font-mono max-w-full"
              >
                <option value="">Select alternative...</option>
                {menuItems.map((item) => (
                  <option key={item.job_code} value={item.job_code}>
                    {item.job_name} ({item.ic_label})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* No alternative selected */}
          {!selectedAlt ? (
            <div className="text-xs text-textMuted italic py-8 text-center bg-surface/30 rounded border border-dashed border-border/60">
              Pick an alternative to compare
            </div>
          ) : compareLoading ? (
            <div className="flex items-center justify-center p-8 text-textMuted text-xs font-mono">
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Comparing actions...
            </div>
          ) : compareError ? (
            <div className="bg-critical/10 border border-critical/40 text-critical text-xs px-3 py-2 rounded flex items-center gap-2 my-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Failed to compare: {compareError}</span>
            </div>
          ) : compareEnvelope && compareEnvelope.status !== 'OK' && !cf ? (
            <div className="bg-amber-950/30 border border-amber-500/40 text-amber-200 text-xs px-3 py-2 rounded flex items-center gap-2 my-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>{compareEnvelope.message || `Status: ${compareEnvelope.status}`}</span>
            </div>
          ) : cf ? (
            <div>
              {/* Compare Non-OK Status Banner (when data is present but status !== 'OK') */}
              {compareEnvelope && compareEnvelope.status !== 'OK' && (
                <div className="bg-amber-950/30 border border-amber-500/40 text-amber-200 text-xs px-3 py-2 rounded flex items-center gap-2 mb-3">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>{compareEnvelope.message || `Status: ${compareEnvelope.status}`}</span>
                </div>
              )}

              {/* Header: Why <recommended.job_name> and not <alternative.job_name>? */}
              <div className="mb-3">
                <h3 className="text-sm font-semibold text-textMain font-sans">
                  Why {cf.recommended.job_name} and not {cf.alternative.job_name}?
                </h3>
                {(cf.recommended.resolution || cf.alternative.resolution) && (
                  <div className="text-[11px] text-textMuted mt-1 space-y-0.5 font-mono">
                    {cf.recommended.resolution && (
                      <div>
                        <span className="text-textMuted/70">Recommended:</span>{' '}
                        {cf.recommended.resolution}
                      </div>
                    )}
                    {cf.alternative.resolution && (
                      <div>
                        <span className="text-textMuted/70">Alternative:</span>{' '}
                        {cf.alternative.resolution}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Flags as chips */}
              {cf.flags && cf.flags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {cf.flags.map((flag, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-950/40 text-amber-300 border border-amber-500/40"
                    >
                      {flag}
                    </span>
                  ))}
                </div>
              )}

              {/* Counterfactual Table (3 columns) */}
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left min-w-[500px]">
                  <thead>
                    <tr className="border-b border-border text-[11px] font-mono uppercase text-textMuted font-bold">
                      <th className="pb-2 pr-3 w-[26%]">Dimension</th>
                      <th className="pb-2 px-3 w-[37%]">Recommended</th>
                      <th className="pb-2 pl-3 w-[37%]">Alternative</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cf.rows.map((row) => {
                      const isRecWinner = row.winner === 'RECOMMENDED';
                      const isAltWinner = row.winner === 'ALTERNATIVE';
                      const hasRefs = row.evidence_refs && row.evidence_refs.length > 0;

                      return (
                        <React.Fragment key={row.dimension}>
                          <tr className={hasRefs ? '' : 'border-b border-border/40'}>
                            {/* Dimension */}
                            <td className="py-2.5 pr-3 align-top font-medium text-textMain text-xs">
                              <div className="p-2">
                                <div>{row.title}</div>
                              </div>
                            </td>

                            {/* Recommended */}
                            <td className="py-2.5 px-3 align-top">
                              <div
                                className={`p-2 rounded text-xs transition-colors ${
                                  isRecWinner
                                    ? 'border border-[#2ea043]/50 bg-[#2ea043]/5'
                                    : 'border border-transparent'
                                }`}
                              >
                                {renderCellContent(row.recommended)}
                              </div>
                            </td>

                            {/* Alternative */}
                            <td className="py-2.5 pl-3 align-top">
                              <div
                                className={`p-2 rounded text-xs transition-colors ${
                                  isAltWinner
                                    ? 'border border-[#2ea043]/50 bg-[#2ea043]/5'
                                    : 'border border-transparent'
                                }`}
                              >
                                {renderCellContent(row.alternative)}
                              </div>
                            </td>
                          </tr>

                          {/* Evidence refs under row */}
                          {hasRefs && (
                            <tr className="border-b border-border/40">
                              <td colSpan={3} className="pt-0 pb-2.5 px-2">
                                <div className="flex flex-wrap items-center gap-1.5 ml-2">
                                  <span className="text-[10px] font-mono text-textMuted/60 uppercase">
                                    Refs:
                                  </span>
                                  {row.evidence_refs.map((ref, idx) => {
                                    const isDoc =
                                      !ref.includes(':') && !ref.startsWith('TC-');
                                    return isDoc ? (
                                      <a
                                        key={idx}
                                        href={docUrl(ref)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-surface border border-border text-accent hover:border-accent hover:underline transition-colors"
                                      >
                                        <span>{ref}</span>
                                        <ExternalLink className="w-2.5 h-2.5 opacity-70" />
                                      </a>
                                    ) : (
                                      <span
                                        key={idx}
                                        className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-surface/60 border border-border/40 text-textMuted"
                                      >
                                        {ref}
                                      </span>
                                    );
                                  })}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Verdict Section */}
              {verdictInfo && (
                <div className="mt-4 pt-4 border-t border-border/60 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className="inline-block px-2.5 py-1 rounded text-xs font-semibold tracking-wide"
                      style={{
                        backgroundColor: verdictInfo.bg,
                        color: verdictInfo.color,
                        border: `1px solid ${verdictInfo.border}`,
                      }}
                    >
                      {verdictInfo.label}
                    </span>
                    {cf.deciding_dimension && (
                      <span className="text-xs text-textMuted font-mono">
                        Deciding:{' '}
                        <span className="text-textMain font-medium">
                          {cf.deciding_dimension.replace(/_/g, ' ')}
                        </span>
                      </span>
                    )}
                    {cf.margin_pct != null && (
                      <span className="text-xs font-mono text-textMuted">
                        (margin {cf.margin_pct}%)
                      </span>
                    )}
                  </div>
                  {cf.verdict_text && (
                    <p className="text-xs text-textMain leading-relaxed font-sans mt-2">
                      {cf.verdict_text}
                    </p>
                  )}
                </div>
              )}

              {/* Cited Documents */}
              {cf.citations && cf.citations.length > 0 && (
                <div className="mt-4 pt-3 border-t border-border/40 space-y-2">
                  <div className="text-[11px] font-mono uppercase text-textMuted font-bold">
                    Cited Documents
                  </div>
                  <div className="space-y-1.5">
                    {cf.citations.map((cite) => (
                      <div
                        key={cite.doc_id}
                        className="bg-surface/50 border border-border/50 rounded p-2 text-xs font-sans space-y-1"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <a
                            href={cite.url || docUrl(cite.doc_id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-mono text-accent hover:underline font-medium text-xs"
                          >
                            <FileText className="w-3.5 h-3.5 shrink-0" />
                            <span>{cite.doc_id}</span>
                            <ExternalLink className="w-3 h-3 shrink-0 opacity-70" />
                          </a>
                          {cite.doc_date && (
                            <span className="text-[10px] font-mono text-textMuted">
                              {cite.doc_date}
                            </span>
                          )}
                        </div>
                        {cite.title && (
                          <div className="text-textMain font-medium text-[11px]">
                            {cite.title}
                          </div>
                        )}
                        {cite.why && (
                          <div className="text-[11px] text-textMuted italic">
                            {cite.why}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </>
      )}

      {/* Provenance Footer */}
      {provenance && (
        <div className="mt-4 pt-2 border-t border-border/40 text-[10px] font-mono text-textMuted text-right">
          {provenance.tool_id} · as of {provenance.as_of}
        </div>
      )}
    </div>
  );
};
