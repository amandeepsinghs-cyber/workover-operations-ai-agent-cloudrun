import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Calendar, TrendingDown, TrendingUp } from 'lucide-react';
import { TelemetryPoint } from '../../types/well';

interface TelemetryChartsProps {
  wellId: string;
}

export const TelemetryCharts: React.FC<TelemetryChartsProps> = ({ wellId }) => {
  const [timeRange, setTimeRange] = useState<'30d' | '6m' | '1y' | '2y'>('1y');
  const [data, setData] = useState<TelemetryPoint[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    fetch(`/api/wells/${wellId}/history?range=${timeRange}`)
      .then((res) => res.json())
      .then((history) => {
        if (isMounted) {
          setData(history);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load history:', err);
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [wellId, timeRange]);

  const ranges: { label: string; value: '30d' | '6m' | '1y' | '2y' }[] = [
    { label: '30 Days', value: '30d' },
    { label: '6 Months', value: '6m' },
    { label: '1 Year', value: '1y' },
    { label: '2 Years', value: '2y' },
  ];

  return (
    <div className="space-y-6">
      {/* Time Range Selector Bar */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2 text-xs font-mono text-textMuted">
          <Calendar className="w-3.5 h-3.5 text-accent" />
          <span>Historical Production Timeline</span>
        </div>
        <div className="flex items-center gap-1 bg-[#0d1117] border border-border p-1 rounded-lg">
          {ranges.map((r) => (
            <button
              key={r.value}
              onClick={() => setTimeRange(r.value)}
              className={`text-xs px-2.5 py-1 rounded font-mono transition-colors ${
                timeRange === r.value
                  ? 'bg-surface text-white font-semibold border border-border shadow-sm'
                  : 'text-textMuted hover:text-white'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-textMuted text-xs font-mono">
          <span className="animate-spin mr-2">◌</span> Loading 24-Month Telemetry...
        </div>
      ) : (
        <div className="space-y-6">
          {/* Chart 1: Oil (BOPD) and Gas (MCFD) Production */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono uppercase text-textMuted font-bold">
                Production Flow Rates (Oil BOPD & Gas MCFD)
              </span>
              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="flex items-center gap-1.5 text-emerald-400">
                  <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500"></span> Oil (BOPD)
                </span>
                <span className="flex items-center gap-1.5 text-sky-400">
                  <span className="w-2.5 h-2.5 rounded-sm bg-sky-500"></span> Gas (MCFD)
                </span>
              </div>
            </div>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis
                    dataKey="date"
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={(tick) => tick.slice(5)}
                  />
                  <YAxis stroke="#8b949e" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      borderColor: '#30363d',
                      fontSize: '11px',
                      color: '#e6edf3',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="oil_bopd"
                    stroke="#2ea043"
                    strokeWidth={2}
                    dot={false}
                    name="Oil (BOPD)"
                  />
                  <Line
                    type="monotone"
                    dataKey="gas_mcfd"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    dot={false}
                    name="Gas (MCFD)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Water Cut (%) Area */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono uppercase text-textMuted font-bold">
                Water Cut (%) Progression
              </span>
              <span className="text-xs font-mono text-amber-400">
                Current: {data.length > 0 ? `${data[data.length - 1].water_cut_pct}%` : 'N/A'}
              </span>
            </div>
            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="waterCutGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#d29922" stopOpacity={0.6} />
                      <stop offset="95%" stopColor="#d29922" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis
                    dataKey="date"
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={(tick) => tick.slice(5)}
                  />
                  <YAxis stroke="#8b949e" fontSize={10} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      borderColor: '#30363d',
                      fontSize: '11px',
                      color: '#e6edf3',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="water_cut_pct"
                    stroke="#d29922"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#waterCutGrad)"
                    name="Water Cut (%)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 3: Tubing vs Casing Pressure (psi) */}
          <div className="bg-[#0d1117] border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono uppercase text-textMuted font-bold">
                Wellhead & Annulus Pressure Trends (psi)
              </span>
              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="flex items-center gap-1.5 text-purple-400">
                  <span className="w-2.5 h-2.5 rounded-sm bg-purple-500"></span> Tubing (psi)
                </span>
                <span className="flex items-center gap-1.5 text-orange-400">
                  <span className="w-2.5 h-2.5 rounded-sm bg-orange-500"></span> Casing (psi)
                </span>
              </div>
            </div>
            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis
                    dataKey="date"
                    stroke="#8b949e"
                    fontSize={10}
                    tickFormatter={(tick) => tick.slice(5)}
                  />
                  <YAxis stroke="#8b949e" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      borderColor: '#30363d',
                      fontSize: '11px',
                      color: '#e6edf3',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="tubing_pressure_psi"
                    stroke="#a855f7"
                    strokeWidth={1.8}
                    dot={false}
                    name="Tubing (psi)"
                  />
                  <Line
                    type="monotone"
                    dataKey="casing_pressure_psi"
                    stroke="#fb923c"
                    strokeWidth={1.8}
                    dot={false}
                    name="Casing (psi)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
