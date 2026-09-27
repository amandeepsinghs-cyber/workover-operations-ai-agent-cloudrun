import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Compass,
  Droplets,
  Flame,
  Gauge,
  Layers,
  Sliders,
  Wrench,
  XCircle,
  FileText,
} from 'lucide-react';
import { WellDetail } from '../../types/well';
import { TelemetryCharts } from './TelemetryCharts';
import { WorkoverTimeline } from '../timeline/WorkoverTimeline';
import { WellReportsTab } from '../reports/WellReportsTab';

interface WellDetailsProps {
  well: WellDetail;
}

export const WellDetails: React.FC<WellDetailsProps> = ({ well }) => {
  const [activeTab, setActiveTab] = useState<'telemetry' | 'workovers' | 'reports'>('telemetry');
  const { current_metrics } = well;

  // Status configuration
  let statusBadge = (
    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-700/60">
      <CheckCircle className="w-3.5 h-3.5 text-healthy" /> OPTIMAL / HEALTHY
    </span>
  );

  if (well.status === 'warning') {
    statusBadge = (
      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-950/60 text-amber-400 border border-amber-700/60">
        <AlertTriangle className="w-3.5 h-3.5 text-warning" /> NEEDS ATTENTION (&gt;15% DECLINE)
      </span>
    );
  } else if (well.status === 'failed') {
    statusBadge = (
      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-950/60 text-rose-400 border border-rose-700/60 animate-pulse">
        <XCircle className="w-3.5 h-3.5 text-critical" /> CRITICAL / MECHANICAL TRIP
      </span>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0d1117] overflow-y-auto">
      {/* Top Banner: Identity & Health Status */}
      <div className="p-6 border-b border-border bg-surface shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-xl font-bold text-white font-sans tracking-tight">{well.name}</h2>
              {statusBadge}
            </div>
            <div className="flex items-center gap-4 text-xs font-mono text-textMuted mt-2">
              <span className="text-white font-semibold">{well.id}</span>
              <span>•</span>
              <span className="text-accent">{well.formation}</span>
              <span>•</span>
              <span>{well.basin}</span>
              <span>•</span>
              <span className="text-emerald-400">{well.lift_type}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Compass className="w-3 h-3 text-textMuted" />
                {well.coordinates.lat.toFixed(4)}°N, {Math.abs(well.coordinates.lng).toFixed(4)}°E
              </span>
            </div>
          </div>
        </div>

        {/* High-Density KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-5">
          {/* Oil Flow */}
          <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
            <span className="text-[10px] font-mono text-textMuted uppercase flex items-center gap-1">
              <Droplets className="w-3 h-3 text-emerald-400" /> Oil Production
            </span>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {current_metrics.oil_bopd} <span className="text-xs text-textMuted font-normal">BOPD</span>
            </div>
          </div>

          {/* Gas Flow */}
          <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
            <span className="text-[10px] font-mono text-textMuted uppercase flex items-center gap-1">
              <Flame className="w-3 h-3 text-sky-400" /> Gas Flow
            </span>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {current_metrics.gas_mcfd} <span className="text-xs text-textMuted font-normal">MCFD</span>
            </div>
          </div>

          {/* Water Cut */}
          <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
            <span className="text-[10px] font-mono text-textMuted uppercase flex items-center gap-1">
              <Activity className="w-3 h-3 text-amber-400" /> Water Cut
            </span>
            <div className="text-lg font-bold font-mono text-amber-400 mt-1">
              {current_metrics.water_cut_pct}%
            </div>
          </div>

          {/* Tubing Pressure */}
          <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
            <span className="text-[10px] font-mono text-textMuted uppercase flex items-center gap-1">
              <Gauge className="w-3 h-3 text-purple-400" /> Tubing Pressure
            </span>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {current_metrics.tubing_pressure_psi} <span className="text-xs text-textMuted font-normal">psi</span>
            </div>
          </div>

          {/* Casing Pressure */}
          <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
            <span className="text-[10px] font-mono text-textMuted uppercase flex items-center gap-1">
              <Gauge className="w-3 h-3 text-orange-400" /> Casing Pressure
            </span>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {current_metrics.casing_pressure_psi} <span className="text-xs text-textMuted font-normal">psi</span>
            </div>
          </div>

          {/* Uptime / Choke */}
          <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
            <span className="text-[10px] font-mono text-textMuted uppercase flex items-center gap-1">
              <Sliders className="w-3 h-3 text-accent" /> Choke / Uptime
            </span>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {current_metrics.choke_pct}% <span className="text-xs text-textMuted font-normal">/ {current_metrics.uptime_pct}%</span>
            </div>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-4 border-b border-border/80 mt-6 -mb-6">
          <button
            onClick={() => setActiveTab('telemetry')}
            className={`flex items-center gap-2 pb-3 font-mono text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'telemetry'
                ? 'border-accent text-accent'
                : 'border-transparent text-textMuted hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" /> 24-Month Telemetry & Pressure Curves
          </button>

          <button
            onClick={() => setActiveTab('workovers')}
            className={`flex items-center gap-2 pb-3 font-mono text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'workovers'
                ? 'border-accent text-accent'
                : 'border-transparent text-textMuted hover:text-white'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" /> Workover History ({well.workovers.length})
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`flex items-center gap-2 pb-3 font-mono text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'reports'
                ? 'border-accent text-accent'
                : 'border-transparent text-textMuted hover:text-white'
            }`}
          >
            <FileText className="w-3.5 h-3.5" /> Engineering Reports Dossier (4 Docs)
          </button>
        </div>
      </div>

      {/* Tab Body */}
      <div className="p-6 flex-1">
        {activeTab === 'telemetry' ? (
          <TelemetryCharts wellId={well.id} />
        ) : activeTab === 'workovers' ? (
          <WorkoverTimeline workovers={well.workovers} />
        ) : (
          <WellReportsTab well={well} />
        )}
      </div>
    </div>
  );
};
