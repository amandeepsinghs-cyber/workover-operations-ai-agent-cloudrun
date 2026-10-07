import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { ProductionSeries, productionRows } from '../../api/asset';

export interface ProductionMarkersChartProps {
  data: ProductionSeries;
  showTelemetry?: boolean;
  compact?: boolean;
}

function getOutcomeColor(outcome: string): string {
  switch (outcome) {
    case 'SUCCESS':
      return '#2ea043';
    case 'PARTIAL':
      return '#d29922';
    case 'FAILED':
      return '#f85149';
    default:
      return '#8b949e';
  }
}

function getOutcomePillStyle(outcome: string): string {
  switch (outcome) {
    case 'SUCCESS':
      return 'bg-emerald-950/60 text-[#2ea043] border border-emerald-700/60';
    case 'PARTIAL':
      return 'bg-amber-950/60 text-[#d29922] border border-amber-700/60';
    case 'FAILED':
      return 'bg-rose-950/60 text-[#f85149] border border-rose-700/60';
    default:
      return 'bg-slate-900/60 text-[#8b949e] border border-slate-700/60';
  }
}

export const ProductionMarkersChart: React.FC<ProductionMarkersChartProps> = ({
  data,
  showTelemetry = false,
  compact = false,
}) => {
  const rows = productionRows(data);

  const hasWht = Boolean(data.series && 'wht' in data.series && data.series.wht);
  const hasGor = Boolean(data.series && 'gor' in data.series && data.series.gor);
  const hasGlSeries = Boolean(
    data.series && ('gl_inj_rate' in data.series || 'gl_inj_pressure' in data.series)
  );
  const hasThpChp = Boolean(
    data.series && ('thp' in data.series || 'chp' in data.series)
  );

  return (
    <div className="space-y-4">
      {/* Panel: Oil & water cut with interventions */}
      <div className="bg-[#0d1117] border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-mono uppercase text-textMuted font-bold">
            Oil & water cut with interventions
          </span>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#2ea043]"></span> Oil (
              {data.units?.oil || 'BOPD'})
            </span>
            {data.decline_fit && (
              <span className="flex items-center gap-1.5 text-textMuted">
                <span className="w-2.5 h-0.5 border-t border-dashed border-[#8b949e]"></span> Arps
                decline fit
              </span>
            )}
            <span className="flex items-center gap-1.5 text-amber-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#d29922]"></span> Water Cut (
              {data.units?.water_cut || '%'})
            </span>
          </div>
        </div>

        <div className={`${compact ? 'h-44' : 'h-56'} w-full`}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
              <XAxis
                dataKey="date"
                type="category"
                stroke="#8b949e"
                fontSize={10}
                tickFormatter={(tick: string) =>
                  tick && tick.length >= 7 ? tick.slice(0, 7) : String(tick ?? '')
                }
              />
              <YAxis yAxisId="left" stroke="#8b949e" fontSize={10} />
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={[0, 100]}
                stroke="#8b949e"
                fontSize={10}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#161b22',
                  borderColor: '#30363d',
                  fontSize: '11px',
                  color: '#e6edf3',
                }}
                formatter={(value: any, name: any) => [
                  typeof value === 'number' ? value.toFixed(1) : value != null ? value : '—',
                  name,
                ]}
                labelFormatter={(label: any) => `Date: ${label}`}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="oil"
                stroke="#2ea043"
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                name={`Oil (${data.units?.oil || 'BOPD'})`}
              />
              {data.decline_fit && (
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="decline_fit"
                  stroke="#8b949e"
                  strokeDasharray="3 3"
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls={false}
                  name="Arps decline fit"
                />
              )}
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="water_cut"
                stroke="#d29922"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
                name={`Water Cut (${data.units?.water_cut || '%'})`}
              />
              {data.interventions.map((m, idx) => {
                const strokeColor = getOutcomeColor(m.outcome);
                return (
                  <ReferenceLine
                    key={m.workover_id || `${m.date}-${m.job_code}-${idx}`}
                    x={m.date}
                    yAxisId="left"
                    stroke={strokeColor}
                    strokeDasharray="3 3"
                    label={{
                      value: m.job_code,
                      fill: strokeColor,
                      fontSize: 9,
                      position: 'insideTop',
                    }}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Compact Interventions List Below Chart */}
        <div className="mt-4 pt-3 border-t border-border/60">
          <div className="text-xs font-mono uppercase text-textMuted font-bold mb-2">
            {data.interventions.length} interventions in window
          </div>
          {data.interventions.length > 0 && (
            <div className="space-y-1.5">
              {data.interventions.map((m, idx) => {
                const jobLabel = m.job_name || m.job_code;
                const rigDaysDisplay = m.is_rigless
                  ? 'rigless'
                  : m.rig_days != null
                  ? `${m.rig_days} rig days`
                  : '—';
                const upliftDisplay =
                  m.uplift_bopd != null ? `${m.uplift_bopd.toFixed(1)} BOPD` : '—';

                return (
                  <div
                    key={m.workover_id || `${m.date}-${idx}`}
                    className="flex flex-wrap items-center gap-2 py-1 text-xs font-mono text-textMain border-b border-border/40 last:border-0"
                  >
                    <span className="text-textMuted">{m.date}</span>
                    <span className="text-textMuted">·</span>
                    <span className="font-semibold text-white">{jobLabel}</span>
                    <span className="text-textMuted">·</span>
                    <span className="text-textMuted">{m.intervention_class || '—'}</span>
                    <span className="text-textMuted">·</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${getOutcomePillStyle(
                        m.outcome
                      )}`}
                    >
                      {m.outcome}
                    </span>
                    <span className="text-textMuted">·</span>
                    <span>{rigDaysDisplay}</span>
                    <span className="text-textMuted">·</span>
                    <span>{upliftDisplay}</span>
                    {m.doc_url && (
                      <>
                        <span className="text-textMuted">·</span>
                        <a
                          href={m.doc_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-accent underline hover:opacity-80"
                        >
                          report
                        </a>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {data.historical_interventions && data.historical_interventions.length > 0 && (
            <div className="mt-3 text-xs font-mono text-textMuted">
              <span className="font-semibold text-textMuted">Historical (before window): </span>
              {data.historical_interventions
                .map((h) => `${h.year} ${h.job_name || h.job_code} (${h.outcome})`)
                .join(', ')}
            </div>
          )}
        </div>
      </div>

      {/* Telemetry Panels (h-36 each) */}
      {showTelemetry && (
        <div className="space-y-4">
          {/* Wellhead Temperature */}
          {hasWht && (
            <div className="bg-[#0d1117] border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase text-textMuted font-bold">
                  Wellhead temperature ({data.units?.wht || '°C'})
                </span>
              </div>
              <div className="h-36 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis
                      dataKey="date"
                      type="category"
                      stroke="#8b949e"
                      fontSize={10}
                      tickFormatter={(tick: string) =>
                        tick && tick.length >= 7 ? tick.slice(0, 7) : String(tick ?? '')
                      }
                    />
                    <YAxis stroke="#8b949e" fontSize={10} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        fontSize: '11px',
                        color: '#e6edf3',
                      }}
                      formatter={(value: any, name: any) => [
                        typeof value === 'number' ? value.toFixed(1) : value != null ? value : '—',
                        name,
                      ]}
                      labelFormatter={(label: any) => `Date: ${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="wht"
                      stroke="#fb923c"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls={false}
                      name={`WHT (${data.units?.wht || '°C'})`}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* GOR */}
          {hasGor && (
            <div className="bg-[#0d1117] border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase text-textMuted font-bold">
                  GOR ({data.units?.gor || 'scf/bbl'})
                </span>
              </div>
              <div className="h-36 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis
                      dataKey="date"
                      type="category"
                      stroke="#8b949e"
                      fontSize={10}
                      tickFormatter={(tick: string) =>
                        tick && tick.length >= 7 ? tick.slice(0, 7) : String(tick ?? '')
                      }
                    />
                    <YAxis stroke="#8b949e" fontSize={10} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        fontSize: '11px',
                        color: '#e6edf3',
                      }}
                      formatter={(value: any, name: any) => [
                        typeof value === 'number' ? value.toFixed(1) : value != null ? value : '—',
                        name,
                      ]}
                      labelFormatter={(label: any) => `Date: ${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="gor"
                      stroke="#38bdf8"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls={false}
                      name={`GOR (${data.units?.gor || 'scf/bbl'})`}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Gas-Lift Injection */}
          {data.gas_lift ? (
            hasGlSeries && (
              <div className="bg-[#0d1117] border border-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono uppercase text-textMuted font-bold">
                    Gas-lift injection
                  </span>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    {data.series?.gl_inj_rate && (
                      <span className="flex items-center gap-1.5 text-purple-400">
                        <span className="w-2.5 h-2.5 rounded-sm bg-[#a855f7]"></span> Rate (
                        {data.units?.gl_inj_rate || 'MSCFD'})
                      </span>
                    )}
                    {data.series?.gl_inj_pressure && (
                      <span className="flex items-center gap-1.5 text-sky-400">
                        <span className="w-2.5 h-2.5 rounded-sm bg-[#38bdf8]"></span> Pressure (
                        {data.units?.gl_inj_pressure || 'kg/cm²'})
                      </span>
                    )}
                  </div>
                </div>
                <div className="h-36 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={rows}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                      <XAxis
                        dataKey="date"
                        type="category"
                        stroke="#8b949e"
                        fontSize={10}
                        tickFormatter={(tick: string) =>
                          tick && tick.length >= 7 ? tick.slice(0, 7) : String(tick ?? '')
                        }
                      />
                      <YAxis yAxisId="left" stroke="#8b949e" fontSize={10} />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        stroke="#8b949e"
                        fontSize={10}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#161b22',
                          borderColor: '#30363d',
                          fontSize: '11px',
                          color: '#e6edf3',
                        }}
                        formatter={(value: any, name: any) => [
                          typeof value === 'number'
                            ? value.toFixed(1)
                            : value != null
                            ? value
                            : '—',
                          name,
                        ]}
                        labelFormatter={(label: any) => `Date: ${label}`}
                      />
                      {data.series?.gl_inj_rate && (
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="gl_inj_rate"
                          stroke="#a855f7"
                          strokeWidth={1.5}
                          dot={false}
                          connectNulls={false}
                          name={`Inj Rate (${data.units?.gl_inj_rate || 'MSCFD'})`}
                        />
                      )}
                      {data.series?.gl_inj_pressure && (
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="gl_inj_pressure"
                          stroke="#38bdf8"
                          strokeWidth={1.5}
                          dot={false}
                          connectNulls={false}
                          name={`Inj Pressure (${data.units?.gl_inj_pressure || 'kg/cm²'})`}
                        />
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )
          ) : (
            <div className="bg-[#0d1117] border border-border rounded-lg p-4">
              <div className="text-xs font-mono text-textMuted italic">
                Gas-lift series not applicable (lift type: {data.lift_type || 'Unknown'})
              </div>
            </div>
          )}

          {/* THP / CHP */}
          {hasThpChp && (
            <div className="bg-[#0d1117] border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase text-textMuted font-bold">
                  Tubing & Casing Pressure (THP / CHP)
                </span>
                <div className="flex items-center gap-4 text-xs font-mono">
                  {data.series?.thp && (
                    <span className="flex items-center gap-1.5 text-purple-400">
                      <span className="w-2.5 h-2.5 rounded-sm bg-[#a855f7]"></span> THP (
                      {data.units?.thp || 'kg/cm²'})
                    </span>
                  )}
                  {data.series?.chp && (
                    <span className="flex items-center gap-1.5 text-orange-400">
                      <span className="w-2.5 h-2.5 rounded-sm bg-[#fb923c]"></span> CHP (
                      {data.units?.chp || 'kg/cm²'})
                    </span>
                  )}
                </div>
              </div>
              <div className="h-36 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis
                      dataKey="date"
                      type="category"
                      stroke="#8b949e"
                      fontSize={10}
                      tickFormatter={(tick: string) =>
                        tick && tick.length >= 7 ? tick.slice(0, 7) : String(tick ?? '')
                      }
                    />
                    <YAxis stroke="#8b949e" fontSize={10} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        fontSize: '11px',
                        color: '#e6edf3',
                      }}
                      formatter={(value: any, name: any) => [
                        typeof value === 'number' ? value.toFixed(1) : value != null ? value : '—',
                        name,
                      ]}
                      labelFormatter={(label: any) => `Date: ${label}`}
                    />
                    {data.series?.thp && (
                      <Line
                        type="monotone"
                        dataKey="thp"
                        stroke="#a855f7"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls={false}
                        name={`THP (${data.units?.thp || 'kg/cm²'})`}
                      />
                    )}
                    {data.series?.chp && (
                      <Line
                        type="monotone"
                        dataKey="chp"
                        stroke="#fb923c"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls={false}
                        name={`CHP (${data.units?.chp || 'kg/cm²'})`}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
