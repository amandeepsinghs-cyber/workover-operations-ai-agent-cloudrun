import React from 'react';
import { Droplets, HardHat, Wrench, CheckCircle2, Clock } from 'lucide-react';
import { WorkoverRecord, CostBand } from '../../types/well';

interface WorkoverTimelineProps {
  workovers: WorkoverRecord[];
}

const costBandStyles: Record<CostBand, string> = {
  LOW: 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60',
  MED: 'bg-amber-950/60 text-amber-300 border-amber-700/60',
  HIGH: 'bg-rose-950/60 text-rose-300 border-rose-700/60',
};

export const WorkoverTimeline: React.FC<WorkoverTimelineProps> = ({ workovers }) => {
  const totalRigDays = workovers.reduce((acc, wo) => acc + (wo.rig_days || 0), 0);
  const bandCounts = workovers.reduce(
    (acc, wo) => {
      if (wo.cost_band in acc) {
        acc[wo.cost_band]++;
      }
      return acc;
    },
    { LOW: 0, MED: 0, HIGH: 0 } as Record<CostBand, number>
  );

  return (
    <div className="space-y-6">
      {/* Summary KPI Banner */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
          <span className="text-[10px] font-mono uppercase text-textMuted flex items-center gap-1.5 mb-1">
            <Wrench className="w-3 h-3 text-accent" /> Total 2-Year Interventions
          </span>
          <div className="text-lg font-bold font-mono text-white">{workovers.length} Operations</div>
        </div>
        <div className="bg-[#0d1117] border border-border p-3 rounded-lg">
          <span className="text-[10px] font-mono uppercase text-textMuted flex items-center gap-1.5 mb-1">
            <Clock className="w-3 h-3 text-emerald-400" /> Cumulative Rig-Days
          </span>
          <div className="text-lg font-bold font-mono text-emerald-400">
            {totalRigDays.toFixed(1)} Rig-Days
          </div>
          <div className="text-[10px] font-mono text-textMuted mt-0.5">
            LOW {bandCounts.LOW} · MED {bandCounts.MED} · HIGH {bandCounts.HIGH}
          </div>
        </div>
      </div>

      {/* Chronological List of Workovers */}
      <div className="relative border-l-2 border-border/70 ml-3 space-y-6">
        {workovers.map((wo) => (
          <div key={wo.id} className="relative pl-6">
            {/* Timeline Dot */}
            <div className="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-surface border-2 border-accent flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-accent"></div>
            </div>

            {/* Workover Card */}
            <div className="bg-[#0d1117] border border-border rounded-lg p-4 space-y-3 hover:border-accent/40 transition-colors">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-white tracking-wide font-sans">{wo.type}</h4>
                    {wo.intervention_class && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-surface border border-border text-accent">
                        {wo.intervention_class}
                      </span>
                    )}
                    <span
                      className={`text-[9px] font-mono px-2 py-0.5 rounded font-semibold border ${
                        wo.outcome.toLowerCase() === 'success'
                          ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                          : 'bg-amber-950/60 text-amber-300 border-amber-700/60'
                      }`}
                    >
                      {wo.outcome.toUpperCase()}
                    </span>
                  </div>
                  {wo.intervention_label && (
                    <div className="text-[11px] text-accent/80 font-mono mt-0.5">
                      {wo.intervention_label}
                    </div>
                  )}
                  <div className="flex items-center gap-3 text-[11px] font-mono text-textMuted mt-1">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {wo.date}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <HardHat className="w-3 h-3 text-amber-400" /> {wo.contractor}
                    </span>
                  </div>
                </div>

                {/* Uplift & Rig-Days / Cost Band Badges */}
                <div className="text-right font-mono space-y-1">
                  <div className="text-xs font-bold text-emerald-400 flex items-center justify-end gap-1">
                    <Droplets className="w-3 h-3" /> +{wo.flow_delta_bopd} BOPD
                  </div>
                  <div className="flex items-center justify-end gap-1.5">
                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold border ${
                        costBandStyles[wo.cost_band] || 'bg-surface border-border text-white'
                      }`}
                    >
                      {wo.cost_band}
                    </span>
                    <span className="text-[11px] text-textMuted">
                      {wo.rig_days != null ? wo.rig_days.toFixed(1) : '0.0'} rig-days
                    </span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-textMain/90 leading-relaxed font-sans bg-surface/50 border border-border/40 p-2.5 rounded">
                {wo.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
