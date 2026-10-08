import React, { useEffect, useState } from 'react';
import { AlertTriangle, Droplets, History, Loader2, Snowflake } from 'lucide-react';
import { AnomalyType, DepositBlock, DepositVerdict, edApi, WaxSand, WellAnomalies } from '../../api/ed';

/** v0.6 ED-4 / ED-5: F-30 well-history anomalies + F-31 wax / sand behaviour. */

const TYPE_STYLE: Record<AnomalyType, { label: string; cls: string }> = {
  RATE_DROP: { label: 'Rate drop', cls: 'bg-red-900/50 text-red-200 border-red-700/50' },
  WC_JUMP: { label: 'Water jump', cls: 'bg-sky-900/50 text-sky-200 border-sky-700/50' },
  WC_TREND: { label: 'Water trend', cls: 'bg-sky-900/50 text-sky-200 border-sky-700/50' },
  THP_SHIFT: { label: 'THP shift', cls: 'bg-violet-900/50 text-violet-200 border-violet-700/50' },
  DOWNTIME: { label: 'Downtime', cls: 'bg-amber-900/50 text-amber-200 border-amber-700/50' },
};

const VERDICT_LABEL: Record<DepositVerdict, { label: string; cls: string }> = {
  NOT_PRONE: { label: 'Not prone', cls: 'text-emerald-300' },
  FLAGGED_NO_JOBS: { label: 'Flagged, no jobs yet', cls: 'text-slate-300' },
  DOWNTIME_ONLY: { label: 'Downtime, no job yet', cls: 'text-amber-300' },
  ISOLATED: { label: 'Single event', cls: 'text-slate-300' },
  REPEAT: { label: 'Recurring', cls: 'text-amber-300' },
  PREDICTABLE: { label: 'Predictable cycle', cls: 'text-sky-300' },
};

function useEnvelope<T>(fetcher: () => Promise<{ data: T | null; message: string }>, key: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fetcher()
      .then((env) => !cancelled && (env.data ? setData(env.data) : setError(env.message)))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { data, error };
}

const Status: React.FC<{ error: string | null; label: string }> = ({ error, label }) =>
  error ? (
    <div className="text-xs text-red-300 flex items-center gap-2 p-3 border border-red-800/50 rounded">
      <AlertTriangle className="w-4 h-4" /> {error}
    </div>
  ) : (
    <div className="text-xs text-textMuted flex items-center gap-2 p-3">
      <Loader2 className="w-4 h-4 animate-spin" /> {label}
    </div>
  );

export const AnomaliesCard: React.FC<{ wellId: string }> = ({ wellId }) => {
  const { data, error } = useEnvelope<WellAnomalies>(() => edApi.anomalies(wellId), wellId);
  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
      <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
        <History className="w-3.5 h-3.5 text-accent" />
        Well history — anomalies
      </div>
      {!data ? (
        <Status error={error} label="Scanning well history…" />
      ) : (
        <>
          <div className="text-sm font-sans text-textMain leading-snug">{data.summary}</div>
          {data.events.length > 0 && (
            <ol className="relative border-l border-border ml-1.5 space-y-2">
              {data.events.map((e, i) => {
                const s = TYPE_STYLE[e.type];
                return (
                  <li key={`${e.type}-${e.date}-${i}`} className="ml-3">
                    <span className="absolute -left-[5px] mt-1.5 w-2.5 h-2.5 rounded-full bg-border" />
                    <div className="flex items-center gap-2 text-[11px] font-mono">
                      <span className="text-textMuted">{e.date}</span>
                      <span className={`px-1.5 py-0 rounded border text-[10px] ${s.cls}`}>{s.label}</span>
                      {e.ongoing && <span className="text-[10px] text-amber-300 font-semibold">ONGOING</span>}
                    </div>
                    <div className="text-xs font-sans text-textMain mt-0.5">{e.text}</div>
                  </li>
                );
              })}
            </ol>
          )}
          <div className="text-[10px] font-mono text-textMuted">
            last {data.months} months · showing {data.events.length} of {data.n_total} · rule thresholds: rate −30%, water cut +10 pts,
            THP ±25%, downtime ≥7 days
          </div>
        </>
      )}
    </div>
  );
};

const DepositPanel: React.FC<{ b: DepositBlock; icon: React.ReactNode }> = ({ b, icon }) => {
  const v = VERDICT_LABEL[b.verdict];
  return (
    <div className="border border-border rounded-lg p-3 space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-mono uppercase font-bold text-textMain">
        {icon} {b.kind}
        <span className={`ml-auto normal-case font-sans text-[11px] font-semibold ${v.cls}`}>{v.label}</span>
      </div>
      <div className="text-xs font-sans text-textMain leading-snug">{b.text}</div>
      <div className="grid grid-cols-3 gap-2 text-[11px] font-mono">
        <div>
          <div className="text-textMuted text-[10px]">Jobs</div>
          <div className="text-white">{b.n_jobs}</div>
        </div>
        <div>
          <div className="text-textMuted text-[10px]">Cycle (well / field)</div>
          <div className="text-white">
            {b.own_interval_days ?? '—'} / {b.field_interval_days ?? '—'} d
          </div>
        </div>
        <div>
          <div className="text-textMuted text-[10px]">Next due</div>
          <div className={b.overdue_days ? 'text-red-300' : 'text-white'}>
            {b.next_due ?? '—'}
            {b.overdue_days ? ` (+${b.overdue_days} d)` : ''}
          </div>
        </div>
        <div>
          <div className="text-textMuted text-[10px]">Downtime</div>
          <div className="text-white">
            {b.downtime_days} d · {b.downtime_episodes} ep
          </div>
        </div>
        <div>
          <div className="text-textMuted text-[10px]">Deferred</div>
          <div className="text-white">{b.deferred_bbl.toLocaleString()} bbl</div>
        </div>
        <div>
          <div className="text-textMuted text-[10px]">Fluid flag</div>
          <div className="text-white">{b.flag === null ? '—' : b.flag ? 'Yes' : 'No'}</div>
        </div>
      </div>
      {b.job_dates.length > 0 && (
        <div className="text-[10px] font-mono text-textMuted">Job dates: {b.job_dates.join(' · ')}</div>
      )}
    </div>
  );
};

export const WaxSandCard: React.FC<{ wellId: string }> = ({ wellId }) => {
  const { data, error } = useEnvelope<WaxSand>(() => edApi.waxSand(wellId), wellId);
  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
      <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
        <Snowflake className="w-3.5 h-3.5 text-accent" />
        Wax &amp; sand — normal? predictable?
      </div>
      {!data ? (
        <Status error={error} label="Reading wax and sand history…" />
      ) : (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            <DepositPanel b={data.wax} icon={<Snowflake className="w-3.5 h-3.5 text-sky-300" />} />
            <DepositPanel b={data.sand} icon={<Droplets className="w-3.5 h-3.5 text-amber-300" />} />
          </div>
          <div className="text-[10px] font-sans text-textMuted italic">{data.data_note}</div>
        </>
      )}
    </div>
  );
};

export const WellHistoryView: React.FC<{ wellId: string }> = ({ wellId }) => (
  <div className="space-y-4">
    <AnomaliesCard wellId={wellId} />
    <WaxSandCard wellId={wellId} />
  </div>
);
