import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertTriangle, Layers, Activity, Wrench, Shield, Compass, Calendar, Gauge } from 'lucide-react';
import {
  assetApi,
  WellProfile,
  ProductionSeries,
  NeighbourWell,
  BUCKET_COLORS,
  Envelope,
} from '../../api/asset';
import { ProductionMarkersChart } from './ProductionMarkersChart';
import { NearbyWellsList } from './NearbyWellsList';
// Stage R (additive): TC-022 next best action, TC-027 counterfactual, TC-019 attribution
import { NbaCard } from '../decision/NbaCard';
import { RecommendationPanel } from '../decision/RecommendationPanel';
import { CounterfactualTable } from '../decision/CounterfactualTable';
import { AttributionWaterfall } from '../decision/AttributionWaterfall';

/** One focused view per question (answer canvas). Undefined = all sections (legacy overlay). */
export type CanvasView =
  | 'summary'
  | 'overview'
  | 'production'
  | 'interventions'
  | 'wellbore'
  | 'pressures'
  | 'diagnosis'
  | 'recommendation'
  | 'compare'
  | 'nearby';

export const CANVAS_VIEWS: { key: CanvasView; label: string }[] = [
  { key: 'summary', label: 'Summary' },
  { key: 'overview', label: 'Overview' },
  { key: 'production', label: 'Production' },
  { key: 'interventions', label: 'Interventions' },
  { key: 'wellbore', label: 'Wellbore' },
  { key: 'pressures', label: 'Tests & Pressure' },
  { key: 'diagnosis', label: 'Diagnosis' },
  { key: 'recommendation', label: 'Recommendation' },
  { key: 'nearby', label: 'Nearby' },
];

export interface WellDeepDiveDrawerProps {
  wellId: string;
  onClose: () => void;
  onSelectWell: (id: string) => void;
  /** Render inside the parent (middle panel) instead of as a fixed right-hand overlay. */
  embedded?: boolean;
  /** Show only the sections for this view (answer canvas). */
  view?: CanvasView;
  onViewChange?: (v: CanvasView) => void;
  /** Recommended job to compare against in the 'compare' view. */
  compareRecommended?: string;
}

function formatNum(val: number | null | undefined, digits = 1): string {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return val.toFixed(digits);
}

function formatVal(val: unknown, digits = 1): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'number') return isNaN(val) ? '—' : val.toFixed(digits);
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  return String(val);
}

const LITHOLOGY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  Sandstone: { bg: 'bg-amber-950/40', border: 'border-amber-700/60', text: 'text-amber-300' },
  Shale: { bg: 'bg-slate-800/60', border: 'border-slate-600/60', text: 'text-slate-300' },
  Limestone: { bg: 'bg-sky-950/40', border: 'border-sky-700/60', text: 'text-sky-300' },
  Siltstone: { bg: 'bg-stone-800/60', border: 'border-stone-600/60', text: 'text-stone-300' },
  Coal: { bg: 'bg-neutral-900', border: 'border-neutral-700', text: 'text-neutral-300' },
  Default: { bg: 'bg-surface/80', border: 'border-border', text: 'text-textMain' },
};

export const WellDeepDiveDrawer: React.FC<WellDeepDiveDrawerProps> = ({
  wellId,
  onClose,
  onSelectWell,
  embedded = false,
  view,
  onViewChange,
  compareRecommended,
}) => {
  const show = (vs: CanvasView[]) => !view || vs.includes(view);
  const [months, setMonths] = useState<24 | 36 | 60>(36);
  // Stage R: counterfactual panel (opened from the NBA card or the toggle)
  const [compareOpen, setCompareOpen] = useState<boolean>(false);
  const [compareRec, setCompareRec] = useState<string | undefined>(undefined);
  useEffect(() => {
    if (view === 'summary') setMonths(24);
  }, [view, wellId]);
  useEffect(() => {
    setCompareOpen(view === 'compare');
    setCompareRec(view === 'compare' ? compareRecommended : undefined);
  }, [wellId, view, compareRecommended]);

  // Profile state
  const [profileEnvelope, setProfileEnvelope] = useState<Envelope<WellProfile> | null>(null);
  const [profileLoading, setProfileLoading] = useState<boolean>(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Production state
  const [productionEnvelope, setProductionEnvelope] = useState<Envelope<ProductionSeries> | null>(null);
  const [productionLoading, setProductionLoading] = useState<boolean>(true);
  const [productionError, setProductionError] = useState<string | null>(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Fetch well profile when wellId changes
  useEffect(() => {
    let isCancelled = false;
    setProfileLoading(true);
    setProfileError(null);

    assetApi
      .wellProfile(wellId)
      .then((env) => {
        if (!isCancelled) {
          setProfileEnvelope(env);
          setProfileLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setProfileError(err instanceof Error ? err.message : String(err));
          setProfileLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [wellId]);

  // Fetch well production when wellId or months selector changes
  useEffect(() => {
    let isCancelled = false;
    setProductionLoading(true);
    setProductionError(null);

    assetApi
      .wellProduction(wellId, months)
      .then((env) => {
        if (!isCancelled) {
          setProductionEnvelope(env);
          setProductionLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setProductionError(err instanceof Error ? err.message : String(err));
          setProductionLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [wellId, months]);

  const profile = profileEnvelope?.data;
  const production = productionEnvelope?.data;

  const bucket = profile?.status.bucket;
  const bucketColor = bucket ? BUCKET_COLORS[bucket] ?? '#8b949e' : '#8b949e';

  // Lithology stacked column calculations
  const lithologyRows = profile?.lithology ?? [];
  const totalThickness = lithologyRows.reduce((acc, row) => {
    const thickness = Math.max(0, (row.bottom_md_m ?? 0) - (row.top_md_m ?? 0));
    return acc + thickness;
  }, 0);

  const renderKvGrid = (obj: Record<string, unknown> | null | undefined, emptyLabel: string) => {
    if (!obj) {
      return <div className="text-xs text-textMuted italic py-2">{emptyLabel}</div>;
    }
    const entries = Object.entries(obj).filter(([k]) => !k.startsWith('_'));
    if (entries.length === 0) {
      return <div className="text-xs text-textMuted italic py-2">{emptyLabel}</div>;
    }
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {entries.map(([key, val]) => (
          <div key={key} className="bg-surface/50 border border-border/60 rounded p-2 flex flex-col">
            <span className="text-[10px] font-mono text-textMuted uppercase truncate" title={key}>
              {key.replace(/_/g, ' ')}
            </span>
            <span className="text-xs font-mono font-medium text-textMain mt-0.5 truncate" title={String(val)}>
              {formatVal(val)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <aside
      className={
        embedded
          ? 'h-full w-full bg-[#0d1117] overflow-y-auto flex flex-col'
          : 'fixed top-0 right-0 h-full w-[640px] max-w-full z-[1100] bg-[#0d1117] border-l border-border shadow-2xl overflow-y-auto flex flex-col'
      }
    >
      {/* Sticky Header */}
      <div
        className={`sticky top-0 bg-[#0d1117]/95 backdrop-blur border-b border-border p-4 z-20 flex items-start justify-between gap-3 ${
          embedded ? 'pr-20' : ''
        }`}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-bold font-mono text-white tracking-wide">{wellId}</h2>
            {bucket && (
              <span
                className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider"
                style={{
                  backgroundColor: `${bucketColor}20`,
                  color: bucketColor,
                  border: `1px solid ${bucketColor}40`,
                }}
              >
                {bucket.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          <div className="text-xs font-mono text-textMuted mt-1">
            {profile?.identity.field ?? '—'} · {profile?.identity.cluster_id ? `Cluster ${profile.identity.cluster_id}` : '—'}
          </div>
          {embedded && onViewChange && (
            <nav className="flex gap-3 mt-2.5 -mb-4 overflow-x-auto no-scrollbar" aria-label="Well views">
              {CANVAS_VIEWS.map((v) => {
                const active = view === v.key || (view === 'compare' && v.key === 'recommendation');
                return (
                  <button
                    key={v.key}
                    onClick={() => onViewChange(v.key)}
                    aria-current={active ? 'page' : undefined}
                    className={`whitespace-nowrap pb-2 text-[11px] font-sans border-b-2 transition-colors ${
                      active ? 'border-accent text-white font-semibold' : 'border-transparent text-textMuted hover:text-white'
                    }`}
                  >
                    {v.label}
                  </button>
                );
              })}
            </nav>
          )}
        </div>

        {!embedded && (
        <button
          onClick={onClose}
          className="p-1 rounded text-textMuted hover:text-white hover:bg-surface transition-colors shrink-0 flex items-center gap-1 text-[10px] font-mono"
          aria-label={embedded ? 'Back to production view' : 'Close drawer'}
          title={embedded ? 'Back to production view (ESC)' : 'Close (ESC)'}
        >
          <X className="w-5 h-5" />
        </button>
        )}
      </div>

      {/* Main Drawer Body */}
      <div className="p-4 space-y-6 flex-1">
        {/* Profile Envelope status message / error */}
        {profileError && (
          <div className="bg-red-950/30 border border-red-500/40 text-red-300 text-xs px-3 py-2 rounded flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>Failed to load well profile: {profileError}</span>
          </div>
        )}

        {profileEnvelope && profileEnvelope.status !== 'OK' && (
          <div className="bg-amber-950/30 border border-amber-500/40 text-amber-200 text-xs px-3 py-2 rounded flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{profileEnvelope.message || `Profile Status: ${profileEnvelope.status}`}</span>
          </div>
        )}

        {profileLoading ? (
          <div className="flex items-center justify-center p-12 text-textMuted text-xs font-mono">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading well profile...
          </div>
        ) : profile ? (
          <>
            {show(['summary']) && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono">
                {[
                  { k: 'Status', v: (profile.status.bucket ?? '—').replace(/_/g, ' '), c: bucketColor },
                  { k: 'Oil', v: `${formatNum(profile.current.oil_bopd)} BOPD` },
                  { k: 'Water cut', v: `${formatNum(profile.current.water_cut_pct)} %` },
                  { k: 'Gas', v: `${formatNum(profile.current.gas_mscfd)} Mscfd` },
                  { k: 'Lift', v: String(profile.lift?.lift_type ?? '—').replace(/_/g, ' ') },
                ].map((c) => (
                  <div key={c.k} className="bg-surface/50 border border-border/60 rounded p-2 min-w-0">
                    <div className="text-[10px] text-textMuted uppercase">{c.k}</div>
                    <div className="font-semibold text-sm mt-0.5 truncate" style={{ color: c.c ?? '#fff' }} title={c.v}>
                      {c.v}
                    </div>
                  </div>
                ))}
                {profile.status.reason && (
                  <div className="col-span-2 sm:col-span-5 text-[11px] text-textMuted font-sans">
                    <span className="text-white">Why: </span>
                    {profile.status.reason}
                    {profile.current.last_producing_date ? ` · last producing ${profile.current.last_producing_date}` : ''}
                  </div>
                )}
              </div>
            )}

            {show(['overview']) && (
            <>
            {/* Section 1: Status & Current Performance */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Status Box */}
              <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
                <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-accent" />
                  Status
                </div>
                <div className="space-y-1.5 text-xs font-mono">
                  <div className="flex justify-between border-b border-border/40 pb-1">
                    <span className="text-textMuted">Bucket</span>
                    <span className="text-white font-semibold" style={{ color: bucketColor }}>
                      {profile.status.bucket ?? '—'}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-1">
                    <span className="text-textMuted">Reason</span>
                    <span className="text-white text-right max-w-[200px] truncate" title={profile.status.reason ?? undefined}>
                      {profile.status.reason ?? '—'}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-1">
                    <span className="text-textMuted">Episode</span>
                    <span className="text-white">
                      {profile.status.episode_status ?? '—'} {profile.status.episode_since ? `(${profile.status.episode_since})` : ''}
                    </span>
                  </div>
                  {profile.status.reason_code && (
                    <div className="flex justify-between pb-1">
                      <span className="text-textMuted">Reason Code</span>
                      <span className="text-textMuted">{profile.status.reason_code}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Current Rates */}
              <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
                <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-accent" />
                  Current Rates
                </div>
                <div className="space-y-1.5 text-xs font-mono">
                  <div className="flex justify-between border-b border-border/40 pb-1">
                    <span className="text-textMuted">Oil Rate</span>
                    <span className="text-white font-semibold">{formatNum(profile.current.oil_bopd)} BOPD</span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-1">
                    <span className="text-textMuted">Water Cut</span>
                    <span className="text-white">{formatNum(profile.current.water_cut_pct)} %</span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-1">
                    <span className="text-textMuted">Gas Rate</span>
                    <span className="text-white">{formatNum(profile.current.gas_mscfd)} Mscfd</span>
                  </div>
                  <div className="flex justify-between pb-1">
                    <span className="text-textMuted">Last Producing</span>
                    <span className="text-textMuted">{profile.current.last_producing_date ?? '—'}</span>
                  </div>
                </div>
              </div>
            </div>
            </>
            )}

            {show(['overview', 'production']) && (
            <>
            {/* Section 2: Decline & Forecast */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
              <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                <Gauge className="w-3.5 h-3.5 text-accent" />
                Decline & Forecast
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Expected BOPD</div>
                  <div className="text-white font-bold text-sm mt-0.5">{formatNum(profile.decline.expected_bopd)}</div>
                </div>
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Residual %</div>
                  <div className="text-white font-bold text-sm mt-0.5">{formatNum(profile.decline.residual_pct)}%</div>
                </div>
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Fit Quality</div>
                  <div className="text-white text-sm mt-0.5 truncate">{profile.decline.fit_quality ?? '—'}</div>
                </div>
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Decline Status</div>
                  <div className="text-white text-sm mt-0.5 truncate">{profile.decline.status ?? '—'}</div>
                </div>
              </div>
            </div>
            </>
            )}

            {show(['overview']) && (
            <>
            {/* Section 3: Identity */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5 text-accent" />
                Identity & Wellbore Details
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2 text-xs font-mono">
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Zone</span>
                  <span className="text-white">{profile.identity.zone ?? '—'}</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Formation</span>
                  <span className="text-white">{profile.identity.formation ?? '—'}</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Well Status</span>
                  <span className="text-white">{profile.identity.well_status ?? '—'}</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Spud Date</span>
                  <span className="text-white">{profile.identity.spud_date ?? '—'}</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Completion Date</span>
                  <span className="text-white">{profile.identity.completion_date ?? '—'}</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Total Depth MD</span>
                  <span className="text-white">{formatNum(profile.identity.total_depth_md_m)} m</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Total Depth TVD</span>
                  <span className="text-white">{formatNum(profile.identity.total_depth_tvd_m)} m</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Perf Top</span>
                  <span className="text-white">{formatNum(profile.identity.perf_top_m)} m</span>
                </div>
                <div>
                  <span className="text-textMuted block text-[10px] uppercase">Perf Bottom</span>
                  <span className="text-white">{formatNum(profile.identity.perf_bottom_m)} m</span>
                </div>
              </div>
            </div>
            </>
            )}

            {show(['overview', 'wellbore']) && (
            <>
            {/* Section 4: Artificial Lift */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center justify-between">
                <span>Artificial Lift</span>
                <span className="px-2 py-0.5 rounded bg-surface border border-border text-white text-[10px] font-mono">
                  {profile.lift.lift_type ?? '—'}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(profile.lift)
                  .filter(([k]) => k !== 'lift_type' && !k.startsWith('_'))
                  .map(([key, val]) => (
                    <div key={key} className="bg-surface/50 border border-border/60 rounded p-2 flex flex-col">
                      <span className="text-[10px] font-mono text-textMuted uppercase truncate" title={key}>
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs font-mono text-white mt-0.5 truncate" title={String(val)}>
                        {formatVal(val)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
            </>
            )}

            {show(['wellbore']) && (
            <>
            {/* Section 5: Construction Tables */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-4">
              <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                <Wrench className="w-3.5 h-3.5 text-accent" />
                Wellbore Construction
              </div>

              {/* Casing Table */}
              <div>
                <div className="text-[11px] font-mono font-semibold text-textMain mb-1.5 flex justify-between">
                  <span>Casing Strings</span>
                  {profile.construction.casing_size_in != null && (
                    <span className="text-textMuted text-[10px]">Casing Size: {formatNum(profile.construction.casing_size_in)}"</span>
                  )}
                </div>
                <div className="border border-border/60 rounded overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-surface/70 text-[10px] text-textMuted uppercase border-b border-border/60">
                      <tr>
                        <th className="py-1.5 px-2">String</th>
                        <th className="py-1.5 px-2">OD (in)</th>
                        <th className="py-1.5 px-2">Weight (ppf)</th>
                        <th className="py-1.5 px-2">Grade</th>
                        <th className="py-1.5 px-2">Shoe (m)</th>
                        <th className="py-1.5 px-2">Cement Top (m)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40 text-textMain">
                      {profile.construction.casing && profile.construction.casing.length > 0 ? (
                        profile.construction.casing.map((c, i) => (
                          <tr key={i} className="hover:bg-surface/40">
                            <td className="py-1.5 px-2 font-medium">{c.string_type}</td>
                            <td className="py-1.5 px-2">{formatNum(c.od_in)}"</td>
                            <td className="py-1.5 px-2">{formatNum(c.weight_ppf)}</td>
                            <td className="py-1.5 px-2">{c.grade ?? '—'}</td>
                            <td className="py-1.5 px-2">{formatNum(c.shoe_m)}</td>
                            <td className="py-1.5 px-2">{formatNum(c.cement_top_m)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="py-2 px-2 text-center text-textMuted italic">
                            No casing records available
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Tubing Table */}
              <div>
                <div className="text-[11px] font-mono font-semibold text-textMain mb-1.5 flex justify-between">
                  <span>Tubing String</span>
                  {profile.construction.tubing_size_in != null && (
                    <span className="text-textMuted text-[10px]">Tubing Size: {formatNum(profile.construction.tubing_size_in)}"</span>
                  )}
                </div>
                <div className="border border-border/60 rounded overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-surface/70 text-[10px] text-textMuted uppercase border-b border-border/60">
                      <tr>
                        <th className="py-1.5 px-2">Seq</th>
                        <th className="py-1.5 px-2">Component</th>
                        <th className="py-1.5 px-2">OD (in)</th>
                        <th className="py-1.5 px-2">Length (m)</th>
                        <th className="py-1.5 px-2">Top (m)</th>
                        <th className="py-1.5 px-2">Installed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40 text-textMain">
                      {profile.construction.tubing && profile.construction.tubing.length > 0 ? (
                        profile.construction.tubing.map((t, i) => (
                          <tr key={i} className="hover:bg-surface/40">
                            <td className="py-1.5 px-2">{t.seq}</td>
                            <td className="py-1.5 px-2 font-medium">{t.component}</td>
                            <td className="py-1.5 px-2">{formatNum(t.od_in)}"</td>
                            <td className="py-1.5 px-2">{formatNum(t.length_m)}</td>
                            <td className="py-1.5 px-2">{formatNum(t.top_m)}</td>
                            <td className="py-1.5 px-2">{t.install_date ?? '—'}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="py-2 px-2 text-center text-textMuted italic">
                            No tubing records available
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Perforations Table */}
              <div>
                <div className="text-[11px] font-mono font-semibold text-textMain mb-1.5">Perforations</div>
                <div className="border border-border/60 rounded overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-surface/70 text-[10px] text-textMuted uppercase border-b border-border/60">
                      <tr>
                        <th className="py-1.5 px-2">Zone</th>
                        <th className="py-1.5 px-2">Top (m)</th>
                        <th className="py-1.5 px-2">Bottom (m)</th>
                        <th className="py-1.5 px-2">SPF</th>
                        <th className="py-1.5 px-2">Status</th>
                        <th className="py-1.5 px-2">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40 text-textMain">
                      {profile.construction.perfs && profile.construction.perfs.length > 0 ? (
                        profile.construction.perfs.map((p, i) => (
                          <tr key={i} className="hover:bg-surface/40">
                            <td className="py-1.5 px-2 font-medium">{p.zone}</td>
                            <td className="py-1.5 px-2">{formatNum(p.top_m)}</td>
                            <td className="py-1.5 px-2">{formatNum(p.bottom_m)}</td>
                            <td className="py-1.5 px-2">{formatNum(p.spf, 0)}</td>
                            <td className="py-1.5 px-2">{p.status ?? '—'}</td>
                            <td className="py-1.5 px-2">{p.perf_date ?? '—'}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="py-2 px-2 text-center text-textMuted italic">
                            No perforation records available
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            </>
            )}

            {show(['wellbore']) && (
            <>
            {/* Section 6: Lithology Column */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-accent" />
                  Lithology Column
                </span>
                <span className="text-[10px] text-textMuted">
                  {totalThickness > 0 ? `${formatNum(totalThickness)} m Total Column` : '—'}
                </span>
              </div>

              {lithologyRows.length > 0 ? (
                <div className="space-y-3">
                  {/* Proportional Stacked Bars Column */}
                  <div className="w-full rounded border border-border overflow-hidden flex flex-col min-h-[180px] shadow-inner">
                    {lithologyRows.map((row, idx) => {
                      const thickness = Math.max(0, (row.bottom_md_m ?? 0) - (row.top_md_m ?? 0));
                      const pct = totalThickness > 0 ? (thickness / totalThickness) * 100 : 100 / lithologyRows.length;
                      const styleInfo = LITHOLOGY_COLORS[row.lithology] ?? LITHOLOGY_COLORS.Default;

                      return (
                        <div
                          key={idx}
                          className={`${styleInfo.bg} border-b ${styleInfo.border} last:border-b-0 px-3 py-1.5 flex items-center justify-between transition-colors`}
                          style={{ minHeight: `${Math.max(34, Math.round(pct * 2.2))}px` }}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-xs font-mono font-semibold text-white truncate">
                              {row.formation}
                            </span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border border-border/40 ${styleInfo.text} bg-surface/50`}>
                              {row.lithology}
                            </span>
                          </div>
                          <div className="text-right text-[11px] font-mono text-textMuted shrink-0">
                            <span>{formatNum(row.top_md_m)} – {formatNum(row.bottom_md_m)} m</span>
                            <span className="text-[10px] text-textMuted/80 ml-1.5">({formatNum(thickness)} m)</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Summary list */}
                  <div className="border border-border/60 rounded overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-surface/70 text-[10px] text-textMuted uppercase border-b border-border/60">
                        <tr>
                          <th className="py-1 px-2">Formation</th>
                          <th className="py-1 px-2">Top MD (m)</th>
                          <th className="py-1 px-2">Bottom MD (m)</th>
                          <th className="py-1 px-2">Lithology</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/40 text-textMain">
                        {lithologyRows.map((row, i) => (
                          <tr key={i} className="hover:bg-surface/40">
                            <td className="py-1 px-2 font-medium">{row.formation}</td>
                            <td className="py-1 px-2">{formatNum(row.top_md_m)}</td>
                            <td className="py-1 px-2">{formatNum(row.bottom_md_m)}</td>
                            <td className="py-1 px-2 text-textMuted">{row.lithology}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-textMuted italic py-2">No lithology tops recorded</div>
              )}
            </div>
            </>
            )}

            {show(['pressures']) && (
            <>
            {/* Section 7: Tests & Pressure Surveys */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Last Test Grid */}
              <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
                <div className="text-xs font-mono uppercase text-textMuted font-bold">Last Test</div>
                {renderKvGrid(profile.last_test, 'No well test recorded')}
              </div>

              {/* Last Pressure Survey Grid */}
              <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
                <div className="text-xs font-mono uppercase text-textMuted font-bold">Last Pressure Survey</div>
                {renderKvGrid(profile.last_pressure_survey, 'No pressure survey recorded')}
              </div>
            </div>
            </>
            )}

            {show(['summary', 'interventions']) && (
            <>
            {/* Section 8: Interventions Summary */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-3 space-y-2">
              <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center justify-between">
                <span>Interventions Summary</span>
                <span className="text-white text-xs font-mono">
                  Total: {formatNum(profile.interventions_summary.total, 0)}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Last Job Code</div>
                  <div className="text-white font-medium mt-0.5 truncate">
                    {profile.interventions_summary.last_job_code ?? '—'}
                  </div>
                </div>
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Last Job Date</div>
                  <div className="text-white font-medium mt-0.5 truncate">
                    {profile.interventions_summary.last_job_date ?? '—'}
                  </div>
                </div>
                <div className="bg-surface/50 border border-border/60 rounded p-2">
                  <div className="text-[10px] text-textMuted uppercase">Last Outcome</div>
                  <div className="text-white font-medium mt-0.5 truncate">
                    {profile.interventions_summary.last_outcome ?? '—'}
                  </div>
                </div>
              </div>
            </div>
            </>
            )}

            {show(['summary', 'production', 'interventions']) && (
            <>
            {/* Section 9: Production Section with Months Selector */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-accent" />
                  Production History & Interventions
                </div>

                {/* Months Selector */}
                <div className="flex items-center rounded border border-border bg-surface p-0.5 text-xs font-mono">
                  {([24, 36, 60] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMonths(m)}
                      className={`px-2.5 py-1 rounded transition-colors ${
                        months === m
                          ? 'bg-accent text-white font-bold'
                          : 'text-textMuted hover:text-white'
                      }`}
                    >
                      {m / 12} Years
                    </button>
                  ))}
                </div>
              </div>

              {productionError && (
                <div className="bg-red-950/30 border border-red-500/40 text-red-300 text-xs px-3 py-2 rounded flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>Failed to load production series: {productionError}</span>
                </div>
              )}

              {productionEnvelope && productionEnvelope.status !== 'OK' && (
                <div className="bg-amber-950/30 border border-amber-500/40 text-amber-200 text-xs px-3 py-2 rounded flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>{productionEnvelope.message || `Production Status: ${productionEnvelope.status}`}</span>
                </div>
              )}

              {productionLoading ? (
                <div className="flex items-center justify-center p-8 text-textMuted text-xs font-mono">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Loading production history ({months / 12}y)...
                </div>
              ) : production ? (
                <div>
                  <ProductionMarkersChart data={production} showTelemetry compact />
                  {productionEnvelope?.provenance && (
                    <div className="text-[10px] font-mono text-textMuted mt-2 pt-2 border-t border-border/40">
                      Production: {productionEnvelope.provenance.tool_id} · as of {productionEnvelope.provenance.as_of}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-xs text-textMuted italic py-4 text-center">
                  No production series available
                </div>
              )}
            </div>
            </>
            )}

            {show(['interventions']) && production && (
              <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-2">
                <div className="text-xs font-mono uppercase text-textMuted font-bold flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-accent" />
                  Intervention History ({months / 12} years{production.historical_interventions?.length ? ' + earlier' : ''})
                </div>
                {production.interventions.length === 0 && !production.historical_interventions?.length ? (
                  <div className="text-xs text-textMuted italic py-2">No interventions recorded</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-[11px] font-mono">
                      <thead>
                        <tr className="text-textMuted text-left border-b border-border/60">
                          <th className="py-1 px-2">Date</th>
                          <th className="py-1 px-2">Job</th>
                          <th className="py-1 px-2">Class</th>
                          <th className="py-1 px-2">Outcome</th>
                          <th className="py-1 px-2 text-right">Rig-days</th>
                          <th className="py-1 px-2 text-right">Uplift BOPD</th>
                          <th className="py-1 px-2">Report</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...production.interventions].reverse().map((j) => (
                          <tr key={j.workover_id} className="border-b border-border/30">
                            <td className="py-1 px-2 text-white">{j.date}</td>
                            <td className="py-1 px-2 text-white" title={j.job_name ?? undefined}>{j.job_name ?? j.job_code}</td>
                            <td className="py-1 px-2 text-textMuted">{j.intervention_class ?? '—'}</td>
                            <td
                              className={`py-1 px-2 ${
                                j.outcome === 'SUCCESS' ? 'text-emerald-400' : j.outcome === 'FAILED' ? 'text-red-400' : 'text-amber-300'
                              }`}
                            >
                              {j.outcome}
                            </td>
                            <td className="py-1 px-2 text-right">{j.rig_days ?? '—'}</td>
                            <td className="py-1 px-2 text-right">{j.uplift_bopd ?? '—'}</td>
                            <td className="py-1 px-2">
                              {j.doc_url ? (
                                <a href={j.doc_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                                  {j.doc_id}
                                </a>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))}
                        {(production.historical_interventions ?? []).map((h, i) => (
                          <tr key={`h-${i}`} className="border-b border-border/20 text-textMuted">
                            <td className="py-1 px-2">{h.date}</td>
                            <td className="py-1 px-2">{h.job_name ?? h.job_code}</td>
                            <td className="py-1 px-2">historical</td>
                            <td className="py-1 px-2">{h.outcome}</td>
                            <td className="py-1 px-2 text-right">—</td>
                            <td className="py-1 px-2 text-right">—</td>
                            <td className="py-1 px-2">—</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {show(['recommendation']) && (
            <>
            <RecommendationPanel
              wellId={wellId}
              onCompare={(job) => {
                setCompareRec(job);
                setCompareOpen(true);
              }}
              onOpenWell={onSelectWell}
            />

            <details className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <summary className="text-xs font-mono uppercase text-textMuted font-bold cursor-pointer hover:text-white select-none">
                Full next-best-action detail (TC-022)
              </summary>
              <div className="pt-2">
                <NbaCard
                  wellId={wellId}
                  topK={3}
                  onCompare={(jobCode) => {
                    setCompareRec(jobCode);
                    setCompareOpen(true);
                  }}
                />
              </div>
            </details>
            </>
            )}

            {show(['recommendation', 'compare']) && (
            <>
            {/* Stage R: Counterfactual — why this job and not another (TC-027) */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <button
                type="button"
                onClick={() => setCompareOpen((o) => !o)}
                className="text-xs font-mono uppercase text-textMuted font-bold hover:text-white"
              >
                {compareOpen ? '▾' : '▸'} Why not another job? (counterfactual)
              </button>
              {compareOpen && <CounterfactualTable key={`${wellId}-${compareRec ?? 'nba'}`} wellId={wellId} recommended={compareRec} />}
            </div>
            </>
            )}

            {show(['diagnosis']) && (
            <>
            {/* Stage R: Decline attribution (TC-019) */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <AttributionWaterfall wellId={wellId} windowDays={180} />
            </div>
            </>
            )}

            {show(['nearby']) && (
            <>
            {/* Section 10: Nearby Wells */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3">
              <div className="text-xs font-mono uppercase text-textMuted font-bold">
                Nearby Wells
              </div>
              <NearbyWellsList
                neighbours={profile.neighbours}
                basis={profile.neighbour_basis}
                selectedWellId={wellId}
                onSelectWell={onSelectWell}
              />
            </div>
            </>
            )}

            {/* Profile Provenance Footer */}
            {profileEnvelope?.provenance && (
              <div className="text-[10px] font-mono text-textMuted text-right pt-2 border-t border-border/40">
                Profile: {profileEnvelope.provenance.tool_id} · as of {profileEnvelope.provenance.as_of}
              </div>
            )}
          </>
        ) : null}
      </div>
    </aside>
  );
};
