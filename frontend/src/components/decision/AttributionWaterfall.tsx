import React, { useState, useEffect, useMemo } from 'react';
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { Envelope, FactorClass } from '../../api/asset';
import { decisionApi, DeclineAttribution, FACTOR_COLORS } from '../../api/decision';

export interface AttributionWaterfallProps {
  wellId: string;
  windowDays?: number;
}

interface WaterfallBarData {
  sub_factor: string;
  factor_class?: FactorClass;
  base: number;
  value: number;
  bbl: number;
  pct: number;
  days: number;
  controllable: boolean;
  responsible_function?: string | null;
  color: string;
  isTotal: boolean;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: WaterfallBarData;
  }>;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null;
  const item = payload[0].payload;
  if (!item) return null;

  return (
    <div className="bg-[#161b22] border border-border rounded p-2.5 shadow-xl text-[11px] font-sans text-textMain max-w-xs space-y-1.5 z-50">
      <div className="font-semibold text-white break-words">{item.sub_factor}</div>
      {item.factor_class && (
        <div className="flex items-center gap-1.5 font-mono text-[10px] text-textMuted">
          <span
            className="w-2 h-2 rounded-full inline-block shrink-0"
            style={{ backgroundColor: item.color }}
          />
          <span>{item.factor_class}</span>
        </div>
      )}
      <div className="space-y-1 border-t border-border/40 pt-1 font-mono text-[11px]">
        <div className="flex justify-between gap-4">
          <span className="text-textMuted">Volume:</span>
          <span className="text-white font-medium">{item.bbl.toFixed(0)} bbl</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-textMuted">Share:</span>
          <span className="text-white font-medium">{item.pct.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-textMuted">Duration:</span>
          <span className="text-white font-medium">{item.days} days</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-textMuted">Controllable:</span>
          <span className={item.controllable ? 'text-amber-400 font-medium' : 'text-textMuted font-medium'}>
            {item.controllable ? 'Yes' : 'No'}
          </span>
        </div>
        {item.responsible_function && (
          <div className="flex justify-between gap-4 text-[10px] font-sans">
            <span className="text-textMuted">Responsible:</span>
            <span className="text-sky-400 font-medium break-words text-right">
              {item.responsible_function}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export const AttributionWaterfall: React.FC<AttributionWaterfallProps> = ({
  wellId,
  windowDays = 180,
}) => {
  const [envelope, setEnvelope] = useState<Envelope<DeclineAttribution> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;
    setIsLoading(true);
    setError(null);

    decisionApi
      .wellAttribution(wellId, windowDays ?? 180)
      .then((res) => {
        if (!isCancelled) {
          setEnvelope(res);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [wellId, windowDays]);

  const chartData = useMemo<WaterfallBarData[]>(() => {
    if (!envelope?.data?.components) return [];

    const items: WaterfallBarData[] = [];
    let runningBase = 0;

    for (const comp of envelope.data.components) {
      const bbl = comp.bbl;
      items.push({
        sub_factor: comp.sub_factor,
        factor_class: comp.factor_class,
        base: runningBase,
        value: bbl,
        bbl: bbl,
        pct: comp.pct,
        days: comp.days,
        controllable: comp.controllable,
        responsible_function: comp.responsible_function,
        color: FACTOR_COLORS[comp.factor_class] || '#8b949e',
        isTotal: false,
      });
      runningBase += bbl;
    }

    items.push({
      sub_factor: 'Total',
      factor_class: undefined,
      base: 0,
      value: envelope.data.total_loss_bbl,
      bbl: envelope.data.total_loss_bbl,
      pct: 100,
      days: envelope.data.window_days,
      controllable: false,
      responsible_function: null,
      color: '#6e7681',
      isTotal: true,
    });

    return items;
  }, [envelope?.data]);

  const presentClasses = useMemo<FactorClass[]>(() => {
    if (!envelope?.data?.components) return [];
    const classes = new Set<FactorClass>();
    for (const comp of envelope.data.components) {
      if (comp.factor_class) {
        classes.add(comp.factor_class);
      }
    }
    return Array.from(classes);
  }, [envelope?.data?.components]);

  if (isLoading) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans">
        <div className="text-textMuted py-8 text-center font-mono">
          Loading decline attribution...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans">
        <div className="bg-red-950/30 border border-red-800/50 text-red-300 p-3 rounded font-mono text-[11px]">
          <div className="font-bold">Error loading attribution</div>
          <div className="mt-1">{error}</div>
        </div>
      </div>
    );
  }

  if (!envelope) return null;

  const { status, message, data, provenance } = envelope;
  const isNonOk = status !== 'OK';

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans">
      {/* Non-OK status banner */}
      {isNonOk && (
        <div
          className={`mb-3 p-2.5 rounded text-[11px] border font-mono ${
            status === 'UNAVAILABLE' || status === 'DISCRIMINATOR_UNAVAILABLE'
              ? 'bg-red-950/30 border-red-800/50 text-red-300'
              : 'bg-amber-950/30 border-amber-800/50 text-amber-300'
          }`}
        >
          <span className="font-bold">{status}:</span> {message || 'Non-standard status reported.'}
        </div>
      )}

      {/* Main body if data is present, else message */}
      {!data ? (
        <div className="text-textMuted py-4 text-center">
          {message || 'No decline attribution data available.'}
        </div>
      ) : (
        <>
          {/* Header row: Window dates, BOPD baseline, bbl lost, largest class */}
          <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-textMuted font-bold">
                Decline Attribution
              </div>
              <div className="text-[11px] font-mono text-textMuted mt-0.5">
                {data.window_start} – {data.window_end}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {data.largest_class && (
                <span
                  className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-semibold tracking-wide uppercase"
                  style={{
                    backgroundColor: `${FACTOR_COLORS[data.largest_class] || '#8b949e'}20`,
                    color: FACTOR_COLORS[data.largest_class] || '#8b949e',
                    border: `1px solid ${FACTOR_COLORS[data.largest_class] || '#8b949e'}40`,
                  }}
                >
                  {data.largest_class}
                </span>
              )}
              <div className="text-right font-mono">
                <div className="text-white font-semibold text-sm">
                  {data.total_loss_bbl != null ? Math.round(data.total_loss_bbl).toLocaleString() : '—'} bbl lost
                </div>
                <div className="text-[11px] text-textMuted">
                  {data.baseline_bopd != null ? data.baseline_bopd.toFixed(1) : '—'} BOPD baseline
                </div>
              </div>
            </div>
          </div>

          {/* Three stat pills */}
          <div className="flex flex-wrap items-center gap-2 mb-3 text-[11px]">
            <div className="px-2.5 py-1 rounded bg-[#161b22] border border-border flex items-center gap-1.5 font-mono">
              <span className="text-textMuted">Controllable:</span>
              <span className="text-amber-400 font-semibold">
                {data.controllable_pct != null ? `${data.controllable_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
            <div className="px-2.5 py-1 rounded bg-[#161b22] border border-border flex items-center gap-1.5 font-mono">
              <span className="text-textMuted">Subsurface:</span>
              <span className="text-sky-400 font-semibold">
                {data.subsurface_pct != null ? `${data.subsurface_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
            <div className="px-2.5 py-1 rounded bg-[#161b22] border border-border flex items-center gap-1.5 font-mono">
              <span className="text-textMuted">Unexplained:</span>
              <span className="text-gray-400 font-semibold">
                {data.unexplained_pct != null ? `${data.unexplained_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
          </div>

          {/* Flags chips */}
          {data.flags && data.flags.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-3">
              {data.flags.map((flag) => (
                <span
                  key={flag}
                  className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-500/15 text-amber-300 border border-amber-500/30 font-medium"
                >
                  {flag}
                </span>
              ))}
            </div>
          )}

          {/* Gains (not netted) */}
          {data.gains_bbl > 0 && (
            <div className="mb-3 px-3 py-2 rounded bg-emerald-950/20 border border-emerald-800/40 text-[11px]">
              <span className="font-semibold text-emerald-400 font-mono">
                Gains (not netted): {data.gains_bbl.toFixed(0)} bbl
              </span>
              {data.gains && data.gains.length > 0 && (
                <span className="text-textMuted ml-2">
                  ({data.gains.map((g) => g.sub_factor).join(', ')})
                </span>
              )}
            </div>
          )}

          {/* Waterfall Recharts Chart */}
          <div className="w-full h-[240px]">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={chartData}
                margin={{ top: 10, right: 10, left: 10, bottom: 40 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                <XAxis
                  dataKey="sub_factor"
                  angle={-30}
                  textAnchor="end"
                  interval={0}
                  height={50}
                  tick={{ fill: '#8b949e', fontSize: 10 }}
                  tickFormatter={(val: string) =>
                    val && val.length > 18 ? `${val.slice(0, 18)}…` : val
                  }
                />
                <YAxis
                  tick={{ fill: '#8b949e', fontSize: 10 }}
                  tickFormatter={(val: number) => val.toLocaleString()}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar
                  dataKey="base"
                  stackId="waterfall"
                  fill="transparent"
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="value"
                  stackId="waterfall"
                  isAnimationActive={false}
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Factor Class Legend */}
          {presentClasses.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 mt-3 pt-2 border-t border-border/40 text-[10px] text-textMuted font-mono">
              {presentClasses.map((fc) => (
                <div key={fc} className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: FACTOR_COLORS[fc] || '#8b949e' }}
                  />
                  <span>{fc}</span>
                </div>
              ))}
              <div className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: '#6e7681' }}
                />
                <span>TOTAL</span>
              </div>
            </div>
          )}

          {/* Methodology notes (collapsible) */}
          {data.method_notes && data.method_notes.length > 0 && (
            <details className="mt-2.5 text-[11px] text-textMuted border-t border-border/40 pt-2">
              <summary className="cursor-pointer select-none font-medium hover:text-textMain transition-colors">
                Methodology Notes ({data.method_notes.length})
              </summary>
              <ul className="mt-1 space-y-0.5 list-disc list-inside text-textMuted/80 text-[10px] leading-relaxed">
                {data.method_notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}

      {/* Provenance footer */}
      {provenance && (
        <div className="mt-3 pt-2 border-t border-border/40 text-[10px] font-mono text-textMuted">
          {provenance.tool_id} · as of {provenance.as_of}
        </div>
      )}
    </div>
  );
};
