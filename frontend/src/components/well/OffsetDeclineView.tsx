import React, { useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, Loader2, Users } from 'lucide-react';
import { edApi, OffsetDecline, OffsetVerdict } from '../../api/ed';

/** F-29 (v0.6 ED-3): decline vs. nearby wells → "what is wrong". */

const VERDICT_STYLE: Record<OffsetVerdict, { label: string; cls: string }> = {
  WELL_SPECIFIC: { label: 'Problem in this well', cls: 'bg-red-950/50 border-red-700/60 text-red-200' },
  WATER: { label: 'Water problem', cls: 'bg-sky-950/50 border-sky-700/60 text-sky-200' },
  RESERVOIR_WIDE: { label: 'Reservoir-wide decline', cls: 'bg-amber-950/50 border-amber-700/60 text-amber-200' },
  RESTORED: { label: 'Rate restored', cls: 'bg-emerald-950/50 border-emerald-700/60 text-emerald-200' },
  MIXED: { label: 'No single clear cause', cls: 'bg-slate-800/60 border-slate-600/60 text-slate-200' },
  INSUFFICIENT: { label: 'Not enough offsets', cls: 'bg-slate-800/60 border-slate-600/60 text-slate-300' },
};

const OFFSET_COLORS = ['#94a3b8', '#a78bfa', '#f59e0b', '#34d399', '#f472b6'];

const fmt = (v: number | null | undefined, unit = '', digits = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : `${v.toFixed(digits)}${unit}`;
const trend = (d: number | null) => (d === null ? '—' : d >= 0 ? `↓ ${d.toFixed(1)}%/yr` : `↑ ${Math.abs(d).toFixed(1)}%/yr`);

export const OffsetDeclineView: React.FC<{ wellId: string; onSelectWell?: (id: string) => void }> = ({
  wellId,
  onSelectWell,
}) => {
  const [data, setData] = useState<OffsetDecline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState<'oil_norm' | 'oil_bopd' | 'wc_pct'>('oil_norm');

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    edApi
      .offsetDecline(wellId)
      .then((env) => !cancelled && (env.data ? setData(env.data) : setError(env.message)))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [wellId]);

  const chartRows = useMemo(() => {
    if (!data) return [];
    const byMonth = new Map<string, Record<string, number | string | null>>();
    const add = (id: string, pts: OffsetDecline['subject']['series']) =>
      pts.forEach((p) => {
        const row = byMonth.get(p.month) ?? { month: p.month };
        row[id] = p[metric];
        byMonth.set(p.month, row);
      });
    add(data.well_id, data.subject.series);
    data.offsets.forEach((o) => add(o.well_id, o.series));
    return Array.from(byMonth.values()).sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [data, metric]);

  if (error)
    return (
      <div className="text-xs text-red-300 flex items-center gap-2 p-3 border border-red-800/50 rounded">
        <AlertTriangle className="w-4 h-4" /> {error}
      </div>
    );
  if (!data)
    return (
      <div className="text-xs text-textMuted flex items-center gap-2 p-3">
        <Loader2 className="w-4 h-4 animate-spin" /> Comparing with nearby wells…
      </div>
    );

  const v = VERDICT_STYLE[data.verdict];
  const rows = [{ ...data.subject, distance_m: null as number | null, last_job: null, isSubject: true }, ...data.offsets.map((o) => ({ ...o, isSubject: false }))];

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-4">
      <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
        <Users className="w-3.5 h-3.5 text-accent" />
        Decline vs. nearby wells
      </div>

      {/* Verdict — the answer first */}
      <div className={`border rounded-lg p-3 ${v.cls}`}>
        <div className="text-[10px] font-mono uppercase tracking-wider opacity-80">{v.label}</div>
        <div className="text-sm font-sans mt-1 leading-snug">{data.headline}</div>
        {data.mechanical?.evidence && (
          <div className="text-[11px] font-sans mt-1.5 opacity-80">Evidence: {data.mechanical.evidence}</div>
        )}
      </div>

      {/* Curves */}
      <div>
        <div className="flex items-center gap-1 mb-2 text-[11px] font-sans">
          {(
            [
              ['oil_norm', 'Oil (start = 100)'],
              ['oil_bopd', 'Oil bopd'],
              ['wc_pct', 'Water cut %'],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setMetric(k)}
              className={`px-2 py-0.5 rounded border ${
                metric === k ? 'border-accent text-white bg-accent/20' : 'border-border text-textMuted hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
          <span className="ml-auto text-[10px] text-textMuted font-mono">last {data.months} months · monthly mean</span>
        </div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid stroke="#30363d" strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fill: '#8b949e', fontSize: 10 }} minTickGap={24} />
              <YAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0d1117', border: '1px solid #30363d', fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              {data.offsets.map((o, i) => (
                <Line
                  key={o.well_id}
                  type="monotone"
                  dataKey={o.well_id}
                  stroke={OFFSET_COLORS[i % OFFSET_COLORS.length]}
                  strokeWidth={1.2}
                  strokeDasharray="4 3"
                  dot={false}
                  connectNulls
                />
              ))}
              <Line type="monotone" dataKey={data.well_id} stroke="#ef4444" strokeWidth={2.6} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Table: this well vs. each offset */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] font-mono">
          <thead className="text-textMuted">
            <tr className="border-b border-border">
              <th className="text-left py-1 pr-2">Well</th>
              <th className="text-right pr-2">Dist</th>
              <th className="text-right pr-2">Oil now</th>
              <th className="text-right pr-2">12-mo trend</th>
              <th className="text-right pr-2">WC Δ</th>
              <th className="text-left">Last job</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.well_id} className={`border-b border-border/40 ${r.isSubject ? 'text-white font-semibold' : 'text-textMain'}`}>
                <td className="py-1 pr-2">
                  {r.isSubject ? (
                    <span className="text-red-400">{r.well_id} (this well)</span>
                  ) : (
                    <button type="button" className="text-accent hover:text-white" onClick={() => onSelectWell?.(r.well_id)}>
                      {r.well_id}
                    </button>
                  )}
                </td>
                <td className="text-right pr-2">{r.distance_m === null ? '—' : `${r.distance_m.toFixed(0)} m`}</td>
                <td className="text-right pr-2">{fmt(r.oil_now_bopd, '')}</td>
                <td className="text-right pr-2">{trend(r.decline_pct_yr)}</td>
                <td className="text-right pr-2">{r.wc_change_pts === null ? '—' : `${r.wc_change_pts >= 0 ? '+' : ''}${r.wc_change_pts.toFixed(1)} pts`}</td>
                <td className="text-left text-textMuted">
                  {r.last_job ? `${r.last_job.job_code.replace(/_/g, ' ').toLowerCase()} · ${r.last_job.date} · ${r.last_job.outcome.toLowerCase()}` : r.isSubject ? '' : '—'}
                </td>
              </tr>
            ))}
            <tr className="text-textMuted">
              <td className="py-1 pr-2">Offsets median</td>
              <td />
              <td />
              <td className="text-right pr-2">{trend(data.offsets_median.decline_pct_yr)}</td>
              <td className="text-right pr-2">
                {data.offsets_median.wc_change_pts === null ? '—' : `${data.offsets_median.wc_change_pts >= 0 ? '+' : ''}${data.offsets_median.wc_change_pts.toFixed(1)} pts`}
              </td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};
