import React from 'react';
import { Activity, AlertTriangle, CheckCircle, Layers, Radio, XCircle } from 'lucide-react';
import { FleetKPIs, WellStatus } from '../../types/well';
import { PersonaPicker } from '../persona/PersonaPicker';
import { UrviMark } from './UrviMark';

interface HeaderProps {
  kpis: FleetKPIs | null;
  selectedStatus: string;
  onSelectStatus: (status: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  /** ED-15: agent docked on the right → less room; hide the search below 2xl and shorten the status pill. */
  compact?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  kpis,
  selectedStatus,
  onSelectStatus,
  searchQuery,
  onSearchChange,
  compact = false,
}) => {
  return (
    <header className="h-16 bg-surface border-b border-border px-4 gap-3 flex items-center justify-between shrink-0 min-w-0">
      {/* Brand & Identity */}
      <div className="flex items-center gap-3 shrink-0">
        {/* D-42: Urvi is the front-facing brand; WellPulse is the platform underneath */}
        <UrviMark size={40} className="rounded-lg shadow-lg shadow-blue-500/20" title="Urvi AI Agent" />
        <div className="flex flex-col leading-tight">
          <h1 className="text-base font-bold tracking-tight text-white font-sans whitespace-nowrap">Urvi AI Agent</h1>
          <span className="text-[10px] font-sans text-textMuted whitespace-nowrap">on WellPulse</span>
        </div>
      </div>

      {/* Fleet Status Metrics Ribbon */}
      {kpis && (
        <div className="flex items-center gap-1 bg-[#0d1117] border border-border px-2 py-1.5 rounded-lg text-xs font-mono shrink-0 whitespace-nowrap">
          <button
            onClick={() => onSelectStatus('all')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              selectedStatus === 'all'
                ? 'bg-surface text-white border border-border shadow-sm'
                : 'text-textMuted hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-textMuted" />
            <span>Total:</span>
            <strong className="text-white">{kpis.total_wells}</strong>
          </button>

          <span className="text-border">|</span>

          <button
            onClick={() => onSelectStatus('healthy')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              selectedStatus === 'healthy'
                ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-700/60'
                : 'text-textMuted hover:text-emerald-400'
            }`}
          >
            <CheckCircle className="w-3.5 h-3.5 text-healthy" />
            <span>Healthy:</span>
            <strong className="text-emerald-400">{kpis.healthy_count}</strong>
          </button>

          <button
            onClick={() => onSelectStatus('warning')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              selectedStatus === 'warning'
                ? 'bg-amber-950/60 text-amber-300 border border-amber-700/60'
                : 'text-textMuted hover:text-amber-400'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-warning" />
            <span>Attention:</span>
            <strong className="text-amber-400">{kpis.warning_count}</strong>
          </button>

          <button
            onClick={() => onSelectStatus('failed')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              selectedStatus === 'failed'
                ? 'bg-rose-950/60 text-rose-300 border border-rose-700/60'
                : 'text-textMuted hover:text-rose-400'
            }`}
          >
            <XCircle className="w-3.5 h-3.5 text-critical animate-pulse" />
            <span className="whitespace-nowrap">Not producing:</span>
            <strong className="text-critical">{kpis.failed_count}</strong>
          </button>
        </div>
      )}

      {/* Global Search & Live Indicator */}
      <div className="flex items-center gap-2 min-w-0">
        {/* Stage Y (F-16): demo persona switch; X-Persona is added to every /api call */}
        <PersonaPicker compact />
        <div className={compact ? 'relative hidden 2xl:block' : 'relative'}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search well or formation..."
            className="w-40 xl:w-48 bg-[#0d1117] border border-border text-xs px-3 py-1.5 rounded-lg text-white placeholder-textMuted focus:outline-none focus:border-accent font-sans"
          />
        </div>

        <div
          className={`${compact ? 'hidden 2xl:flex' : 'flex'} items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-1 rounded-full shrink-0 whitespace-nowrap`}
          title="System online"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          {!compact && <span>ONLINE</span>}
        </div>
      </div>
    </header>
  );
};
