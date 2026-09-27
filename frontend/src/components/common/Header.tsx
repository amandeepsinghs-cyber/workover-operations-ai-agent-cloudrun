import React from 'react';
import { Activity, AlertTriangle, CheckCircle, Flame, Layers, Radio, XCircle } from 'lucide-react';
import { FleetKPIs, WellStatus } from '../../types/well';

interface HeaderProps {
  kpis: FleetKPIs | null;
  selectedStatus: string;
  onSelectStatus: (status: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  kpis,
  selectedStatus,
  onSelectStatus,
  searchQuery,
  onSearchChange,
}) => {
  return (
    <header className="h-16 bg-surface border-b border-border px-6 flex items-center justify-between shrink-0">
      {/* Brand & Identity */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Flame className="w-6 h-6 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold tracking-tight text-white font-sans">WellPulse</h1>
            <span className="text-[10px] font-mono uppercase bg-blue-900/60 text-blue-300 border border-blue-700/50 px-2 py-0.5 rounded-full font-semibold">
              Ops Copilot
            </span>
          </div>
          <p className="text-xs text-textMuted font-mono">Geleki Brownfield Asset • Sivasagar, Assam (ONGC)</p>
        </div>
      </div>

      {/* Fleet Status Metrics Ribbon */}
      {kpis && (
        <div className="flex items-center gap-2 bg-[#0d1117] border border-border px-3 py-1.5 rounded-lg text-xs font-mono">
          <button
            onClick={() => onSelectStatus('all')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
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
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
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
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
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
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
              selectedStatus === 'failed'
                ? 'bg-rose-950/60 text-rose-300 border border-rose-700/60'
                : 'text-textMuted hover:text-rose-400'
            }`}
          >
            <XCircle className="w-3.5 h-3.5 text-critical animate-pulse" />
            <span>Failed:</span>
            <strong className="text-critical">{kpis.failed_count}</strong>
          </button>
        </div>
      )}

      {/* Global Search & Live Indicator */}
      <div className="flex items-center gap-4">
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search well or formation..."
            className="w-56 bg-[#0d1117] border border-border text-xs px-3 py-1.5 rounded-lg text-white placeholder-textMuted focus:outline-none focus:border-accent font-sans"
          />
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2.5 py-1 rounded-full">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span>SYSTEM ONLINE</span>
        </div>
      </div>
    </header>
  );
};
