import React, { useState, useEffect, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Calendar, Filter, AlertTriangle } from 'lucide-react';
import {
  assetApi,
  FieldName,
  FieldSeries,
  Envelope,
  FIELD_COLORS,
} from '../../api/asset';

export interface FieldHistoryChartProps {
  initialFields?: FieldName[];
}

interface ChartRow {
  period: string;
  is_partial?: boolean;
  [key: string]: string | number | boolean | null | undefined;
}

export const FieldHistoryChart: React.FC<FieldHistoryChartProps> = ({ initialFields }) => {
  const [freq, setFreq] = useState<'M' | 'Q' | 'Y'>('M');
  const [envelope, setEnvelope] = useState<Envelope<FieldSeries> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedFields, setSelectedFields] = useState<Set<FieldName>>(
    () => new Set(initialFields ?? [])
  );
  const [hasInitializedSelection, setHasInitializedSelection] = useState<boolean>(
    Boolean(initialFields && initialFields.length > 0)
  );

  // Fetch field history on mount and when freq changes
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);

    assetApi
      .fieldHistory(undefined, freq)
      .then((res) => {
        if (!isMounted) return;
        setEnvelope(res);
        if (res.data?.fields && !hasInitializedSelection) {
          setSelectedFields(new Set(res.data.fields));
          setHasInitializedSelection(true);
        }
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error('Failed to load field history:', err);
        setError(err instanceof Error ? err.message : String(err));
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [freq]);

  const toggleField = (field: FieldName) => {
    setHasInitializedSelection(true);
    setSelectedFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) {
        next.delete(field);
      } else {
        next.add(field);
      }
      return next;
    });
  };

  const availableFields: FieldName[] = envelope?.data?.fields ?? [];
  const visibleFields = useMemo(() => {
    return availableFields.filter((f) => selectedFields.has(f));
  }, [availableFields, selectedFields]);

  // Pivot data.series into Recharts rows keyed by period:
  // { period, Geleki_oil, Lakwa_oil, ..., Geleki_gas, ..., Geleki_wc, ... }
  const chartData = useMemo(() => {
    if (!envelope?.data?.series) return [];
    const map = new Map<string, ChartRow>();

    for (const row of envelope.data.series) {
      let entry = map.get(row.period);
      if (!entry) {
        entry = { period: row.period, is_partial: row.is_partial };
        map.set(row.period, entry);
      }
      if (row.is_partial) {
        entry.is_partial = true;
      }
      entry[`${row.field}_oil`] = row.oil_bopd;
      entry[`${row.field}_gas`] = row.gas_mscfd;
      entry[`${row.field}_wc`] = row.water_cut_pct;
    }

    return Array.from(map.values()).sort((a, b) => a.period.localeCompare(b.period));
  }, [envelope?.data?.series]);

  // Check if last period is partial
  const { isLastPeriodPartial, lastPeriodLabel } = useMemo(() => {
    if (chartData.length === 0) {
      return { isLastPeriodPartial: false, lastPeriodLabel: '' };
    }
    const lastRow = chartData[chartData.length - 1];
    const isPartial = Boolean(lastRow.is_partial);
    const label = lastRow.period.length >= 7 ? lastRow.period.slice(0, 7) : lastRow.period;
    return { isLastPeriodPartial: isPartial, lastPeriodLabel: label };
  }, [chartData]);

  // Visible summaries
  const visibleSummaries = useMemo(() => {
    if (!envelope?.data?.summary) return [];
    return envelope.data.summary.filter((s) => selectedFields.has(s.field));
  }, [envelope?.data?.summary, selectedFields]);

  const formatPeriodTick = (val: string) => {
    if (!val) return '';
    return val.length >= 7 ? val.slice(0, 7) : val;
  };

  const tooltipFormatter = (value: any, name: any) => {
    if (value === null || value === undefined) return ['—', name];
    const num = typeof value === 'number' ? value : Number(value);
    return [isNaN(num) ? String(value) : num.toFixed(1), name];
  };

  return (
    <div className="space-y-4">
      {/* Top Controls: Title, Freq Toggle, Field Chips */}
      <div className="flex flex-col gap-3 pb-2 border-b border-border">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase text-textMuted">
            <Calendar className="w-3.5 h-3.5 text-accent" />
            <span>Field Production History (5-Year Aggregated)</span>
          </div>

          {/* M / Q / Y Toggle */}
          <div className="flex items-center gap-1 bg-[#0d1117] border border-border p-1 rounded-lg">
            {(['M', 'Q', 'Y'] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFreq(f)}
                className={`text-xs px-2.5 py-1 rounded font-mono transition-colors ${
                  freq === f
                    ? 'bg-surface text-white font-semibold border border-border shadow-sm'
                    : 'text-textMuted hover:text-white'
                }`}
              >
                {f === 'M' ? 'Monthly (M)' : f === 'Q' ? 'Quarterly (Q)' : 'Yearly (Y)'}
              </button>
            ))}
          </div>
        </div>

        {/* Field Toggle Chips */}
        {availableFields.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="flex items-center gap-1 text-xs font-mono text-textMuted mr-1">
              <Filter className="w-3 h-3 text-textMuted" />
              <span>Fields:</span>
            </span>
            {availableFields.map((field) => {
              const isSelected = selectedFields.has(field);
              const color = FIELD_COLORS[field] || '#8b949e';
              return (
                <button
                  key={field}
                  type="button"
                  onClick={() => toggleField(field)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono border transition-all ${
                    isSelected
                      ? 'bg-surface text-textMain'
                      : 'bg-[#0d1117] text-textMuted border-border opacity-50 hover:opacity-80'
                  }`}
                  style={{
                    borderColor: isSelected ? color : undefined,
                  }}
                >
                  <span
                    className="w-2.5 h-2.5 rounded-sm transition-colors"
                    style={{
                      backgroundColor: isSelected ? color : 'transparent',
                      border: `1.5px solid ${color}`,
                    }}
                  />
                  <span>{field}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="h-64 flex items-center justify-center text-textMuted text-xs font-mono">
          <span className="animate-spin mr-2">◌</span> Loading field production history...
        </div>
      )}

      {/* Network / Fetch Error */}
      {error && (
        <div className="bg-critical/10 border border-critical/30 rounded-lg p-3 text-critical text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>Error loading field history: {error}</span>
        </div>
      )}

      {/* Non-OK Envelope Status Warning */}
      {envelope && envelope.status !== 'OK' && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-3 text-warning text-xs font-mono flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">[{envelope.status}]</span>{' '}
            {envelope.message || 'Field history returned non-OK status.'}
          </div>
        </div>
      )}

      {/* Render Data if present */}
      {envelope?.data && (
        <div className="space-y-4">
          {/* Panel 1: Oil BOPD (h-64) */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3 flex items-center justify-between">
              <span>Oil Production Rate (BOPD)</span>
              <span className="text-[11px] font-normal text-textMuted">
                {freq === 'M' ? 'Monthly' : freq === 'Q' ? 'Quarterly' : 'Yearly'} Average
              </span>
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis
                    dataKey="period"
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={formatPeriodTick}
                  />
                  <YAxis
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={(v: number) => v.toLocaleString()}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      borderColor: '#30363d',
                      fontSize: '11px',
                      color: '#e6edf3',
                    }}
                    formatter={tooltipFormatter}
                    labelFormatter={(label) => `Period: ${formatPeriodTick(String(label))}`}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', color: '#8b949e', paddingTop: '4px' }} />
                  {visibleFields.map((field) => (
                    <Line
                      key={`${field}_oil`}
                      type="monotone"
                      dataKey={`${field}_oil`}
                      name={`${field} oil (BOPD)`}
                      stroke={FIELD_COLORS[field] || '#8b949e'}
                      dot={false}
                      strokeWidth={2}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Panel 2: Gas MSCFD (h-44) */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3">
              Gas Production Rate (MSCFD)
            </div>
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis
                    dataKey="period"
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={formatPeriodTick}
                  />
                  <YAxis
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={(v: number) => v.toLocaleString()}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      borderColor: '#30363d',
                      fontSize: '11px',
                      color: '#e6edf3',
                    }}
                    formatter={tooltipFormatter}
                    labelFormatter={(label) => `Period: ${formatPeriodTick(String(label))}`}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', color: '#8b949e', paddingTop: '4px' }} />
                  {visibleFields.map((field) => (
                    <Line
                      key={`${field}_gas`}
                      type="monotone"
                      dataKey={`${field}_gas`}
                      name={`${field} gas (MSCFD)`}
                      stroke={FIELD_COLORS[field] || '#8b949e'}
                      strokeDasharray="4 2"
                      dot={false}
                      strokeWidth={1.5}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Panel 3: Water Cut % (h-40) */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3">
              Water Cut Progression (%)
            </div>
            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis
                    dataKey="period"
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={formatPeriodTick}
                  />
                  <YAxis
                    stroke="#8b949e"
                    fontSize={10}
                    domain={[0, 100]}
                    tickFormatter={(v: number) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      borderColor: '#30363d',
                      fontSize: '11px',
                      color: '#e6edf3',
                    }}
                    formatter={tooltipFormatter}
                    labelFormatter={(label) => `Period: ${formatPeriodTick(String(label))}`}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', color: '#8b949e', paddingTop: '4px' }} />
                  {visibleFields.map((field) => (
                    <Line
                      key={`${field}_wc`}
                      type="monotone"
                      dataKey={`${field}_wc`}
                      name={`${field} water cut (%)`}
                      stroke={FIELD_COLORS[field] || '#8b949e'}
                      dot={false}
                      strokeWidth={1.5}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Summary Table */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4 overflow-x-auto">
            <div className="text-xs font-mono uppercase text-textMuted font-bold mb-3">
              Field History Summary (Visible Fields)
            </div>
            <table className="w-full text-xs font-mono text-left">
              <thead>
                <tr className="border-b border-border text-textMuted">
                  <th className="pb-2 pr-3">Field</th>
                  <th className="pb-2 px-3">Start → End Period</th>
                  <th className="pb-2 px-3 text-right">Start Oil</th>
                  <th className="pb-2 px-3 text-right">End Oil</th>
                  <th className="pb-2 px-3 text-right">Change %</th>
                  <th className="pb-2 px-3 text-right">Gas Start → End</th>
                  <th className="pb-2 px-3 text-right">WC Start → End</th>
                  <th className="pb-2 px-3 text-right">WC Change (pp)</th>
                  <th className="pb-2 pl-3 text-right">Producing Wells Start → End</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50 text-textMain">
                {visibleSummaries.map((s) => {
                  const color = FIELD_COLORS[s.field] || '#8b949e';
                  const isChangeNeg = s.change_pct != null && s.change_pct < 0;
                  const isWcChangeNeg = s.wc_change_pp != null && s.wc_change_pp < 0;

                  return (
                    <tr key={s.field} className="hover:bg-surface/50 transition-colors">
                      <td className="py-2.5 pr-3 font-bold" style={{ color }}>
                        {s.field}
                      </td>
                      <td className="py-2.5 px-3 text-textMuted">
                        {formatPeriodTick(s.start_period)} → {formatPeriodTick(s.end_period)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {s.start_oil != null ? s.start_oil.toFixed(1) : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {s.end_oil != null ? s.end_oil.toFixed(1) : '—'}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right ${
                          isChangeNeg
                            ? 'text-critical font-semibold'
                            : s.change_pct != null && s.change_pct > 0
                            ? 'text-healthy'
                            : 'text-textMain'
                        }`}
                      >
                        {s.change_pct != null
                          ? `${s.change_pct > 0 ? '+' : ''}${s.change_pct.toFixed(1)}%`
                          : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right text-textMuted">
                        {s.start_gas != null ? s.start_gas.toFixed(1) : '—'} →{' '}
                        {s.end_gas != null ? s.end_gas.toFixed(1) : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right text-textMuted">
                        {s.start_wc_pct != null ? `${s.start_wc_pct.toFixed(1)}%` : '—'} →{' '}
                        {s.end_wc_pct != null ? `${s.end_wc_pct.toFixed(1)}%` : '—'}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right ${
                          isWcChangeNeg ? 'text-critical font-semibold' : 'text-textMain'
                        }`}
                      >
                        {s.wc_change_pp != null
                          ? `${s.wc_change_pp > 0 ? '+' : ''}${s.wc_change_pp.toFixed(1)} pp`
                          : '—'}
                      </td>
                      <td className="py-2.5 pl-3 text-right text-textMuted">
                        {s.start_producing_wells != null
                          ? s.start_producing_wells.toFixed(1)
                          : '—'}{' '}
                        →{' '}
                        {s.end_producing_wells != null
                          ? s.end_producing_wells.toFixed(1)
                          : '—'}
                      </td>
                    </tr>
                  );
                })}
                {visibleSummaries.length === 0 && (
                  <tr>
                    <td colSpan={9} className="py-4 text-center text-textMuted italic">
                      No visible field summary selected.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Reconciliation & Partial period footer note */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
            <div className="text-xs font-mono text-textMuted flex flex-wrap items-center gap-x-2 gap-y-1">
              {envelope.data.reconciliation && envelope.data.reconciliation.length > 0 && (
                <span>
                  Reconciles to well sums:{' '}
                  {envelope.data.reconciliation
                    .map((r) => `${r.field} max err ${r.max_rel_error_pct.toFixed(3)}%`)
                    .join(' · ')}
                </span>
              )}
              {isLastPeriodPartial && (
                <span className="text-warning">
                  {envelope.data.reconciliation && envelope.data.reconciliation.length > 0
                    ? '· '
                    : ''}
                  Note: Last period ({lastPeriodLabel}) is partial
                </span>
              )}
            </div>

            {/* Provenance footer */}
            {envelope.provenance && (
              <div className="text-[10px] font-mono text-textMuted/60 pt-2 border-t border-border/40">
                {envelope.provenance.tool_id} · as of {envelope.provenance.as_of}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
