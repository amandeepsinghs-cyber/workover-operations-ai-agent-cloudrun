import React, { useState, useEffect, useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  LabelList,
  Legend,
} from 'recharts';
import { AlertCircle, AlertTriangle } from 'lucide-react';
import {
  assetApi,
  Envelope,
  FieldComparison as FieldComparisonData,
  FieldComparisonRow,
  FieldName,
  FactorClass,
  HealthBucket,
  BUCKET_COLORS,
} from '../../api/asset';

export interface FieldComparisonProps {
  onSelectField?: (f: FieldName) => void;
}

const FACTOR_COLORS: Record<string, string> = {
  SUBSURFACE: '#64748b',
  EQUIPMENT: '#fb923c',
  OPERATIONAL: '#d29922',
  HUMAN_PROCESS: '#f85149',
  EXTERNAL: '#38bdf8',
  UNEXPLAINED: '#8b949e',
};

const FACTOR_FALLBACK_COLOR = '#a855f7';

export const FieldComparison: React.FC<FieldComparisonProps> = ({ onSelectField }) => {
  const [period, setPeriod] = useState<FieldComparisonData['period']>('QTD');
  const [envelope, setEnvelope] = useState<Envelope<FieldComparisonData> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setFetchError(null);

    assetApi
      .compareFields(period)
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
  }, [period]);

  const periods: Array<FieldComparisonData['period']> = ['QTD', 'MTD', 'YTD', 'L12M'];

  const data = envelope?.data;

  // Order rows according to data.ranking (worst first)
  const rankedRows = useMemo(() => {
    if (!data || !data.rows) return [];
    const rowMap = new Map(data.rows.map((r) => [r.field, r]));
    const ordered: FieldComparisonRow[] = [];
    if (data.ranking && data.ranking.length > 0) {
      for (const f of data.ranking) {
        const r = rowMap.get(f);
        if (r) ordered.push(r);
      }
    }
    // Append any rows not covered by ranking
    for (const r of data.rows) {
      if (!ordered.includes(r)) {
        ordered.push(r);
      }
    }
    return ordered;
  }, [data]);

  // Dynamic factor keys found across all rows
  const factorKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const r of rankedRows) {
      if (r.deferred_by_factor) {
        for (const k of Object.keys(r.deferred_by_factor)) {
          keys.add(k);
        }
      }
    }
    return Array.from(keys);
  }, [rankedRows]);

  // Panel 1 chart data: gap_pct per field
  const gapChartData = useMemo(() => {
    return rankedRows.map((r) => ({
      field: r.field,
      gap_pct: r.gap_pct,
    }));
  }, [rankedRows]);

  // Panel 2 chart data: deferred_by_factor stacked per field
  const deferredChartData = useMemo(() => {
    return rankedRows.map((r) => {
      const rowData: Record<string, string | number> = {
        field: r.field,
      };
      if (r.deferred_by_factor) {
        for (const [k, v] of Object.entries(r.deferred_by_factor)) {
          rowData[k] = v ?? 0;
        }
      }
      return rowData;
    });
  }, [rankedRows]);

  return (
    <div className="space-y-4 text-textMain">
      {/* Top Bar: Title & Period Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-border">
        <div>
          <h2 className="text-base font-sans font-bold text-white tracking-tight">
            Field Performance Comparison
          </h2>
          <p className="text-xs font-mono text-textMuted">
            Field-level production, targets, uptime, and loss drivers
          </p>
        </div>

        {/* Period Selector */}
        <div className="flex items-center gap-1 bg-[#0d1117] border border-border p-1 rounded-lg shrink-0">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`text-xs px-2.5 py-1 rounded font-mono transition-colors ${
                period === p
                  ? 'bg-surface text-white font-semibold border border-border shadow-sm'
                  : 'text-textMuted hover:text-white'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Fetch Error Display */}
      {fetchError && (
        <div className="bg-rose-950/40 border border-rose-800/60 text-rose-300 p-3 rounded-lg text-xs font-mono flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-critical" />
          <span>Error loading field comparison: {fetchError}</span>
        </div>
      )}

      {/* Non-OK Envelope Status Amber Note */}
      {envelope && envelope.status !== 'OK' && (
        <div className="bg-amber-950/40 border border-amber-800/60 text-amber-300 p-3 rounded-lg text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-warning" />
          <span>
            Status: {envelope.status} {envelope.message ? `— ${envelope.message}` : ''}
          </span>
        </div>
      )}

      {/* Loading Spinner */}
      {isLoading && (
        <div className="flex items-center justify-center p-8 font-mono text-xs text-textMuted">
          <span className="animate-spin mr-2">◌</span> Loading field comparison...
        </div>
      )}

      {/* Main Content Area */}
      {!isLoading && data && (
        <>
          {/* Headline Card */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/80 pb-3">
              <div>
                <span className="text-xs font-mono uppercase text-textMuted font-bold block">
                  Asset Performance ({data.asset})
                </span>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs font-sans text-textMuted">Worst Field:</span>
                  <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-rose-950/60 border border-rose-700/60 text-rose-300">
                    {data.worst_field ?? '—'}
                  </span>
                </div>
              </div>
              <div className="sm:text-right">
                <span className="text-[10px] font-mono text-textMuted uppercase block">
                  Window Range
                </span>
                <span className="text-xs font-mono text-textMain">
                  {data.window_start} → {data.window_end}
                </span>
              </div>
            </div>

            {/* Top Driver Row */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-mono">
              <span className="text-textMuted uppercase text-[10px] font-bold">Top Driver:</span>
              {data.top_driver ? (
                <>
                  <span className="text-white font-semibold">{data.top_driver.field}</span>
                  <span className="text-textMuted">•</span>
                  <span className="text-amber-400">
                    {data.top_driver.factor_class.replace(/_/g, ' ')}
                  </span>
                  <span className="text-textMuted">•</span>
                  <span className="text-textMain">
                    {data.top_driver.bbl.toFixed(0)} bbl ({data.top_driver.pct.toFixed(1)}%)
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold ${
                      data.top_driver.controllable
                        ? 'bg-rose-950/60 border border-rose-700/60 text-rose-300'
                        : 'bg-slate-800/80 border border-slate-600 text-slate-300'
                    }`}
                  >
                    {data.top_driver.controllable ? 'controllable' : 'uncontrollable'}
                  </span>
                </>
              ) : (
                <span className="text-textMuted">—</span>
              )}
            </div>
          </div>

          {/* Charts Row: Panel 1 & Panel 2 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Panel 1 (h-48): BarChart of gap_pct per field */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4">
              <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3">
                Production Gap (% vs Target)
              </div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={gapChartData} margin={{ top: 16, right: 16, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis dataKey="field" stroke="#8b949e" fontSize={10} />
                    <YAxis
                      stroke="#8b949e"
                      fontSize={10}
                      tickFormatter={(val: number) => `${val}%`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        fontSize: '11px',
                        color: '#e6edf3',
                      }}
                      formatter={(value: any) => [
                        typeof value === 'number' ? `${value.toFixed(1)}%` : '—',
                        'Gap %',
                      ]}
                    />
                    <ReferenceLine y={0} stroke="#8b949e" strokeDasharray="3 3" />
                    <Bar dataKey="gap_pct" isAnimationActive={false}>
                      {gapChartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={(entry.gap_pct ?? 0) < 0 ? '#f85149' : '#2ea043'}
                        />
                      ))}
                      <LabelList
                        dataKey="gap_pct"
                        position="top"
                        formatter={(val: any) =>
                          typeof val === 'number' ? `${val.toFixed(1)}%` : ''
                        }
                        fill="#e6edf3"
                        fontSize={10}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Panel 2 (h-56): stacked BarChart of deferred_by_factor per field */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4">
              <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3">
                Deferred Production by Factor (bbl)
              </div>
              <div className="h-56 w-full">
                {factorKeys.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={deferredChartData}
                      margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                      <XAxis dataKey="field" stroke="#8b949e" fontSize={10} />
                      <YAxis
                        stroke="#8b949e"
                        fontSize={10}
                        tickFormatter={(val: number) => `${val}`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#161b22',
                          borderColor: '#30363d',
                          fontSize: '11px',
                          color: '#e6edf3',
                        }}
                        formatter={(value: any, name: any) => [
                          `${typeof value === 'number' ? value.toFixed(0) : value} bbl`,
                          String(name).replace(/_/g, ' '),
                        ]}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: '10px', paddingTop: '4px' }}
                        formatter={(value: string) => value.replace(/_/g, ' ')}
                      />
                      {factorKeys.map((factor) => (
                        <Bar
                          key={factor}
                          dataKey={factor}
                          stackId="d"
                          name={factor.replace(/_/g, ' ')}
                          fill={FACTOR_COLORS[factor] || FACTOR_FALLBACK_COLOR}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center font-mono text-xs text-textMuted">
                    No deferred factors recorded for this period
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* KPI Table */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3">
              Field KPI Performance Summary
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border text-[10px] text-textMuted uppercase bg-[#161b22]/50">
                    <th className="py-2 px-2.5">Field</th>
                    <th className="py-2 px-2 text-right">Actual BOPD</th>
                    <th className="py-2 px-2 text-right">Target BOPD</th>
                    <th className="py-2 px-2 text-right">Gap %</th>
                    <th className="py-2 px-2 text-right">Expected BOPD</th>
                    <th className="py-2 px-2 text-right">Uptime %</th>
                    <th className="py-2 px-2 text-right">WC %</th>
                    <th className="py-2 px-2.5 text-center">Health Status</th>
                    <th className="py-2 px-2 text-right">Active Intv</th>
                    <th className="py-2 px-2 text-right">Wait Rig</th>
                    <th className="py-2 px-2 text-center">Rig / Rigless</th>
                    <th className="py-2 px-2 text-right">Controllable %</th>
                    <th className="py-2 px-2.5 text-center">Pinned Band</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {rankedRows.map((row, idx) => {
                    const isWorst = idx === 0 || row.field === data.worst_field;
                    const pinnedBandTitle = row.pinned_band
                      ? `Target: ${row.pinned_band.target_pct.toFixed(1)}% ± ${row.pinned_band.tol_pp.toFixed(1)} pp`
                      : 'No pinned band configured';

                    return (
                      <tr
                        key={row.field}
                        onClick={() => onSelectField?.(row.field)}
                        className={`transition-colors cursor-pointer ${
                          isWorst
                            ? 'bg-rose-950/30 hover:bg-rose-950/50'
                            : 'hover:bg-surface/60'
                        }`}
                      >
                        {/* Field */}
                        <td className="py-2 px-2.5 font-bold text-white whitespace-nowrap">
                          {row.field}
                          {isWorst && (
                            <span className="ml-1.5 px-1.5 py-0.2 rounded text-[9px] font-mono bg-rose-900/60 text-rose-300 border border-rose-700/60 uppercase">
                              Worst
                            </span>
                          )}
                        </td>

                        {/* Actual BOPD */}
                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {row.actual_bopd != null ? row.actual_bopd.toFixed(1) : '—'}
                        </td>

                        {/* Target BOPD */}
                        <td className="py-2 px-2 text-right whitespace-nowrap text-textMuted">
                          {row.target_bopd != null ? row.target_bopd.toFixed(1) : '—'}
                        </td>

                        {/* Gap % */}
                        <td
                          className={`py-2 px-2 text-right font-bold whitespace-nowrap ${
                            (row.gap_pct ?? 0) < 0 ? 'text-critical' : 'text-healthy'
                          }`}
                        >
                          {row.gap_pct != null ? `${row.gap_pct.toFixed(1)}%` : '—'}
                        </td>

                        {/* Expected BOPD */}
                        <td className="py-2 px-2 text-right whitespace-nowrap text-textMuted">
                          {row.expected_bopd != null ? row.expected_bopd.toFixed(1) : '—'}
                        </td>

                        {/* Uptime % (vs target_uptime_pct) */}
                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          <span>{row.uptime_pct != null ? `${row.uptime_pct.toFixed(1)}%` : '—'}</span>
                          {row.target_uptime_pct != null && (
                            <span className="text-textMuted text-[10px]">
                              {' '}/ {row.target_uptime_pct.toFixed(1)}%
                            </span>
                          )}
                        </td>

                        {/* WC % */}
                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {row.water_cut_pct != null ? `${row.water_cut_pct.toFixed(1)}%` : '—'}
                        </td>

                        {/* Health Counts */}
                        <td className="py-2 px-2.5 whitespace-nowrap">
                          {row.health_counts ? (
                            <div className="flex items-center justify-center gap-2 text-[10px]">
                              <span
                                className="flex items-center gap-0.5"
                                title={`Producing OK: ${row.health_counts.PRODUCING_OK}`}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full"
                                  style={{ backgroundColor: BUCKET_COLORS.PRODUCING_OK }}
                                />
                                <span style={{ color: BUCKET_COLORS.PRODUCING_OK }}>
                                  {row.health_counts.PRODUCING_OK}
                                </span>
                              </span>
                              <span
                                className="flex items-center gap-0.5"
                                title={`At Risk: ${row.health_counts.AT_RISK}`}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full"
                                  style={{ backgroundColor: BUCKET_COLORS.AT_RISK }}
                                />
                                <span style={{ color: BUCKET_COLORS.AT_RISK }}>
                                  {row.health_counts.AT_RISK}
                                </span>
                              </span>
                              <span
                                className="flex items-center gap-0.5"
                                title={`Underperforming: ${row.health_counts.UNDERPERFORMING}`}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full"
                                  style={{ backgroundColor: BUCKET_COLORS.UNDERPERFORMING }}
                                />
                                <span style={{ color: BUCKET_COLORS.UNDERPERFORMING }}>
                                  {row.health_counts.UNDERPERFORMING}
                                </span>
                              </span>
                              <span
                                className="flex items-center gap-0.5"
                                title={`Not Producing: ${row.health_counts.NOT_PRODUCING}`}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full"
                                  style={{ backgroundColor: BUCKET_COLORS.NOT_PRODUCING }}
                                />
                                <span style={{ color: BUCKET_COLORS.NOT_PRODUCING }}>
                                  {row.health_counts.NOT_PRODUCING}
                                </span>
                              </span>
                            </div>
                          ) : (
                            <span className="text-center block text-textMuted">—</span>
                          )}
                        </td>

                        {/* Active interventions */}
                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {row.active_interventions != null ? row.active_interventions : '—'}
                        </td>

                        {/* Waiting on rig */}
                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {row.waiting_on_rig != null ? row.waiting_on_rig : '—'}
                        </td>

                        {/* Rig / Rigless candidates */}
                        <td className="py-2 px-2 text-center whitespace-nowrap">
                          {row.rig_candidates != null || row.rigless_candidates != null ? (
                            <span>
                              {row.rig_candidates ?? '—'} / {row.rigless_candidates ?? '—'}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>

                        {/* Controllable % */}
                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {row.controllable_pct != null
                            ? `${row.controllable_pct.toFixed(1)}%`
                            : '—'}
                        </td>

                        {/* Pinned band check */}
                        <td className="py-2 px-2.5 text-center whitespace-nowrap" title={pinnedBandTitle}>
                          {row.in_pinned_band === true ? (
                            <span className="text-emerald-400 font-bold">✓</span>
                          ) : row.in_pinned_band === false ? (
                            <span className="text-critical font-bold">✗</span>
                          ) : (
                            <span className="text-textMuted">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Excluded Fields Amber Notes */}
          {data.excluded && data.excluded.length > 0 && (
            <div className="space-y-1.5">
              {data.excluded.map((exc, idx) => (
                <div
                  key={idx}
                  className="bg-amber-950/40 border border-amber-800/50 text-amber-300 px-3 py-2 rounded-lg text-xs font-mono flex items-center gap-2"
                >
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                  <span>
                    <strong>{exc.field}</strong> excluded: {exc.reason}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Provenance Footer */}
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
