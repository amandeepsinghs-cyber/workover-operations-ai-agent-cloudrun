import React from 'react';
import { NeighbourWell, BUCKET_COLORS } from '../../api/asset';

export interface NearbyWellsListProps {
  neighbours: NeighbourWell[];
  basis?: string;
  selectedWellId?: string | null;
  onSelectWell?: (id: string) => void;
}

export const NearbyWellsList: React.FC<NearbyWellsListProps> = ({
  neighbours,
  basis,
  selectedWellId,
  onSelectWell,
}) => {
  if (!neighbours || neighbours.length === 0) {
    return (
      <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans">
        <div className="text-textMuted text-center py-4">No neighbours found</div>
        {basis && (
          <div className="mt-2 text-[11px] text-textMuted italic">{basis}</div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-[#0d1117] border border-border rounded-lg p-4 text-xs font-sans">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-border text-[11px] font-mono uppercase text-textMuted font-bold">
              <th className="pb-2 pr-3">Well</th>
              <th className="pb-2 px-3 text-right">Distance (m)</th>
              <th className="pb-2 px-3">Bucket</th>
              <th className="pb-2 px-3">Status</th>
              <th className="pb-2 px-3 text-right">Oil BOPD</th>
              <th className="pb-2 px-3 text-right">WC %</th>
              <th className="pb-2 px-3 text-right">Decline Residual %</th>
              <th className="pb-2 pl-3">Last Job</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {neighbours.map((well) => {
              const isSelected = selectedWellId === well.well_id;
              const bucketColor = well.bucket ? BUCKET_COLORS[well.bucket] || '#8b949e' : null;
              const bucketText = well.bucket ? well.bucket.replace(/_/g, ' ') : null;
              const statusText = well.status ? well.status.replace(/_/g, ' ') : null;
              const lastJobText = [well.last_job_code, well.last_job_date].filter(Boolean).join(' · ');

              return (
                <tr
                  key={well.well_id}
                  onClick={() => onSelectWell?.(well.well_id)}
                  className={`cursor-pointer transition-colors hover:bg-surface/60 ${
                    isSelected ? 'bg-surface text-white font-semibold' : 'text-textMain'
                  }`}
                >
                  {/* Well ID */}
                  <td className="py-2.5 pr-3 font-mono font-medium">
                    {well.well_id || '—'}
                  </td>

                  {/* Distance (m, toFixed(0)) */}
                  <td className="py-2.5 px-3 font-mono text-right text-textMuted">
                    {well.distance_m != null ? well.distance_m.toFixed(0) : '—'}
                  </td>

                  {/* Bucket (coloured pill) */}
                  <td className="py-2.5 px-3">
                    {bucketText && bucketColor ? (
                      <span
                        className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium tracking-wide whitespace-nowrap capitalize"
                        style={{
                          backgroundColor: `${bucketColor}20`,
                          color: bucketColor,
                          border: `1px solid ${bucketColor}40`,
                        }}
                      >
                        {bucketText.toLowerCase()}
                      </span>
                    ) : (
                      <span className="text-textMuted font-mono">—</span>
                    )}
                  </td>

                  {/* Status */}
                  <td className="py-2.5 px-3 text-textMuted uppercase text-[11px] font-mono">
                    {statusText || '—'}
                  </td>

                  {/* Oil BOPD (toFixed(1)) */}
                  <td className="py-2.5 px-3 font-mono text-right">
                    {well.oil_bopd != null ? well.oil_bopd.toFixed(1) : <span className="text-textMuted">—</span>}
                  </td>

                  {/* WC % (toFixed(1)) */}
                  <td className="py-2.5 px-3 font-mono text-right text-textMuted">
                    {well.water_cut_pct != null ? `${well.water_cut_pct.toFixed(1)}%` : '—'}
                  </td>

                  {/* Decline residual % (toFixed(1), red if < 0, green if >= 0; append ' (low fit)' muted when fit_quality === 'LOW') */}
                  <td className="py-2.5 px-3 font-mono text-right">
                    {well.residual_pct != null ? (
                      <span className={well.residual_pct < 0 ? 'text-critical' : 'text-healthy'}>
                        {well.residual_pct >= 0 ? `+${well.residual_pct.toFixed(1)}%` : `${well.residual_pct.toFixed(1)}%`}
                        {well.fit_quality === 'LOW' && (
                          <span className="text-textMuted font-sans text-[10px] font-normal ml-1">
                            (low fit)
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-textMuted">—</span>
                    )}
                  </td>

                  {/* Last job (job code + date) */}
                  <td className="py-2.5 pl-3 font-mono text-[11px] text-textMuted whitespace-nowrap">
                    {lastJobText || '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Caption under table with basis text */}
      {basis && (
        <div className="mt-2.5 text-[11px] text-textMuted italic font-sans border-t border-border/40 pt-2">
          {basis}
        </div>
      )}
    </div>
  );
};
