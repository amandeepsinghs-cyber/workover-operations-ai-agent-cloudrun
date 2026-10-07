import React, { useState } from 'react';
import {
  FileText,
  Clock,
  Gauge,
  FlaskConical,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Calendar,
  UserCheck,
  Shield,
  Activity,
  Droplet,
  ExternalLink,
  ChevronRight,
  Info,
  Download,
} from 'lucide-react';
import { WellDetail, WellReports } from '../../types/well';

interface WellReportsTabProps {
  well: WellDetail;
}

type ReportSubTab = 'completion' | 'workover' | 'bhp' | 'lab';

export const WellReportsTab: React.FC<WellReportsTabProps> = ({ well }) => {
  const [activeSubTab, setActiveSubTab] = useState<ReportSubTab>('workover');
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const reports: WellReports = well.reports || {};

  const handleExportDossier = async () => {
    setIsExporting(true);
    try {
      const res = await fetch(`/api/wells/${well.id}/export`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${well.id}_Engineering_Dossier_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export dossier:', err);
      alert('Failed to export well dossier. Please retry.');
    } finally {
      setIsExporting(false);
    }
  };

  const wcr = reports.completion_report;
  const dwr = reports.daily_workover_report;
  const bhp = reports.bottomhole_pressure_survey;
  const lab = reports.water_and_scale_lab_report;

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Sub-Tab Navigation Bar & Dossier Download */}
      <div className="flex items-center justify-between border-b border-border/80 pb-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveSubTab('workover')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold flex items-center gap-2 transition-all ${
              activeSubTab === 'workover'
                ? 'bg-accent/20 text-accent border border-accent/40 shadow-sm'
                : 'text-textMuted hover:text-white hover:bg-surface border border-transparent'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Daily Workover Shift Log</span>
            {dwr && (
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-accent/20 text-accent font-mono">
                Latest
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveSubTab('bhp')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold flex items-center gap-2 transition-all ${
              activeSubTab === 'bhp'
                ? 'bg-purple-950/60 text-purple-300 border border-purple-700/60 shadow-sm'
                : 'text-textMuted hover:text-white hover:bg-surface border border-transparent'
            }`}
          >
            <Gauge className="w-3.5 h-3.5" />
            <span>BHP & Acoustic Sonolog</span>
          </button>

          <button
            onClick={() => setActiveSubTab('lab')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold flex items-center gap-2 transition-all ${
              activeSubTab === 'lab'
                ? 'bg-amber-950/60 text-amber-300 border border-amber-700/60 shadow-sm'
                : 'text-textMuted hover:text-white hover:bg-surface border border-transparent'
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Water & Scale Assay</span>
          </button>

          <button
            onClick={() => setActiveSubTab('completion')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold flex items-center gap-2 transition-all ${
              activeSubTab === 'completion'
                ? 'bg-blue-950/60 text-blue-300 border border-blue-700/60 shadow-sm'
                : 'text-textMuted hover:text-white hover:bg-surface border border-transparent'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Well Completion (WCR)</span>
          </button>
        </div>

        {/* Export Engineering Dossier Button */}
        <button
          onClick={handleExportDossier}
          disabled={isExporting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0d1117] hover:bg-surface text-emerald-400 hover:text-emerald-300 border border-emerald-500/40 hover:border-emerald-400 rounded-lg text-xs font-mono font-semibold transition-all shadow-sm"
          title="Download complete engineering dossier (WCR, DWR, BHP, Lab Assay, and production telemetry in JSON format)"
        >
          <Download className={`w-3.5 h-3.5 ${isExporting ? 'animate-bounce' : ''}`} />
          <span>{isExporting ? 'Exporting...' : 'Export Dossier'}</span>
        </button>
      </div>

      {/* Report 1: Daily Workover Report (DWR) */}
      {activeSubTab === 'workover' && dwr && (
        <div className="space-y-4 font-sans text-xs">
          {/* Document Header Card */}
          <div className="bg-[#12161c] border border-border p-4 rounded-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 transform translate-x-3 -translate-y-2 pointer-events-none opacity-5">
              <Clock className="w-36 h-36" />
            </div>

            <div className="flex items-start justify-between relative z-10">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-accent font-bold uppercase tracking-wider">
                  <Shield className="w-3.5 h-3.5" />
                  {dwr.issuing_authority}
                </div>
                <h3 className="text-base font-bold text-white mt-1">{dwr.title}</h3>
                <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-textMuted mt-2">
                  <span className="text-white font-semibold">Doc Ref: {dwr.report_id}</span>
                  <span>•</span>
                  <span>Date: {dwr.date}</span>
                  <span>•</span>
                  <span>Shift: {dwr.shift_hours}</span>
                  <span>•</span>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold border ${
                        dwr.cost_band === 'LOW'
                          ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                          : dwr.cost_band === 'MED'
                          ? 'bg-amber-950/60 text-amber-300 border-amber-700/60'
                          : 'bg-rose-950/60 text-rose-300 border-rose-700/60'
                      }`}
                    >
                      {dwr.cost_band}
                    </span>
                    <span className="text-emerald-400 font-semibold">{dwr.rig_days} rig-days</span>
                  </span>
                </div>
              </div>

              <div className="text-right">
                <span className="px-2.5 py-1 rounded bg-accent/20 border border-accent/40 text-accent font-mono text-[10px] font-bold uppercase">
                  CONFIDENTIAL • WELL SERVICES
                </span>
              </div>
            </div>

            {/* Supervising Engineer & Rig Personnel Banner */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4 pt-3 border-t border-border/80 font-mono text-xs">
              <div className="bg-[#0d1117] p-2.5 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase flex items-center gap-1.5">
                  <UserCheck className="w-3 h-3 text-accent" /> Supervising In-Charge
                </span>
                <div className="text-white font-semibold text-[11px] mt-1">
                  {dwr.supervising_engineer}
                </div>
              </div>

              <div className="bg-[#0d1117] p-2.5 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase flex items-center gap-1.5">
                  <Layers className="w-3 h-3 text-purple-400" /> Operating Rig & Spread
                </span>
                <div className="text-white font-semibold text-[11px] mt-1">
                  {dwr.workover_rig}
                </div>
              </div>

              <div className="bg-[#0d1117] p-2.5 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase flex items-center gap-1.5">
                  <Activity className="w-3 h-3 text-emerald-400" /> Operation & Contractor
                </span>
                <div className="text-white font-semibold text-[11px] mt-1">
                  {dwr.operation_type} ({dwr.contractor})
                </div>
              </div>
            </div>
          </div>

          {/* Hour-by-Hour Operational Timeline */}
          <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
            <div className="flex items-center justify-between border-b border-border/80 pb-2">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                <Clock className="w-4 h-4 text-accent" />
                Shift Execution Log & Hourly Milestones
              </h4>
              <span className="text-[10px] font-mono text-textMuted">
                {dwr.hourly_logs.length} Sequential Operations
              </span>
            </div>

            <div className="space-y-2.5 pt-2">
              {dwr.hourly_logs.map((log, index) => {
                const isObstruction = log.activity.toLowerCase().includes('tagged hard obstruction') || log.activity.toLowerCase().includes('bridge');
                const isHotOil = log.activity.toLowerCase().includes('hot oil') || log.activity.toLowerCase().includes('xylene');
                const isPressureTest = log.activity.toLowerCase().includes('pressure tested') || log.activity.toLowerCase().includes('zero leak-off');

                return (
                  <div
                    key={index}
                    className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                      isObstruction
                        ? 'bg-rose-950/20 border-rose-800/40 text-rose-200'
                        : isHotOil
                        ? 'bg-amber-950/20 border-amber-800/40 text-amber-200'
                        : isPressureTest
                        ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-200'
                        : 'bg-[#0d1117] border-border text-textMain'
                    }`}
                  >
                    <div className="w-24 shrink-0 font-mono text-[11px] font-bold text-accent flex items-center gap-1">
                      <ChevronRight className="w-3 h-3 text-textMuted" />
                      {log.time}
                    </div>

                    <div className="flex-1 font-sans text-xs leading-relaxed">
                      {log.activity}
                      {isObstruction && (
                        <div className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950/80 text-rose-300 border border-rose-700/60">
                          <AlertTriangle className="w-3 h-3" /> Tagged Wax/Sand Bridge Obstruction
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Outcome Callout Box */}
            <div className="mt-3 p-3 rounded-lg bg-emerald-950/30 border border-emerald-800/50 flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <span className="text-[10px] font-mono uppercase font-bold text-emerald-400">
                  Certified Shift Outcome:
                </span>
                <p className="text-xs text-emerald-200/90 mt-0.5">
                  {dwr.outcome_summary}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Report 2: Bottomhole Pressure Survey (BHP) */}
      {activeSubTab === 'bhp' && bhp && (
        <div className="space-y-4 font-sans text-xs">
          {/* Header */}
          <div className="bg-[#12161c] border border-border p-4 rounded-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-purple-400 font-bold uppercase tracking-wider">
                  <Gauge className="w-3.5 h-3.5" />
                  {bhp.issuing_authority}
                </div>
                <h3 className="text-base font-bold text-white mt-1">{bhp.title}</h3>
                <div className="flex items-center gap-3 text-[11px] font-mono text-textMuted mt-2">
                  <span className="text-white font-semibold">Survey Ref: {bhp.report_id}</span>
                  <span>•</span>
                  <span>Date: {bhp.survey_date}</span>
                  <span>•</span>
                  <span>Datum: {bhp.datum_depth_m_tvd}m TVD</span>
                </div>
              </div>

              <span className="px-2.5 py-1 rounded bg-purple-950/60 border border-purple-700/60 text-purple-300 font-mono text-[10px] font-bold uppercase">
                RESERVOIR MONITORING
              </span>
            </div>

            {/* Reservoir Pressure Metric Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-3 border-t border-border/80 font-mono">
              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">Static BHP (SBHP)</span>
                <div className="text-lg font-bold text-white mt-1">
                  {bhp.static_bottomhole_pressure_sbhp_psi.toFixed(1)}{' '}
                  <span className="text-xs font-normal text-textMuted">psi</span>
                </div>
                <span className="text-[10px] text-textMuted">Shut-in equilibrium</span>
              </div>

              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">Flowing BHP (FBHP)</span>
                <div className="text-lg font-bold text-sky-400 mt-1">
                  {bhp.flowing_bottomhole_pressure_fbhp_psi.toFixed(1)}{' '}
                  <span className="text-xs font-normal text-textMuted">psi</span>
                </div>
                <span className="text-[10px] text-textMuted">Dynamic bottomhole</span>
              </div>

              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">Drawdown (ΔP)</span>
                <div className="text-lg font-bold text-purple-400 mt-1">
                  {bhp.drawdown_psi.toFixed(1)}{' '}
                  <span className="text-xs font-normal text-textMuted">psi</span>
                </div>
                <span className="text-[10px] text-textMuted">SBHP − FBHP</span>
              </div>

              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">Productivity Index (PI)</span>
                <div className="text-lg font-bold text-emerald-400 mt-1">
                  {bhp.productivity_index_pi.toFixed(3)}{' '}
                  <span className="text-xs font-normal text-textMuted">BOPD/psi</span>
                </div>
                <span className="text-[10px] text-textMuted">Inflow deliverability</span>
              </div>
            </div>
          </div>

          {/* Acoustic Sonolog & Gas Lift Diagnostic Card */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Acoustic Sonolog Survey */}
            <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
                <Activity className="w-4 h-4 text-accent" />
                Acoustic Sonolog Wellbore Sounding
              </h4>

              <div className="space-y-2.5 font-mono text-xs">
                <div className="flex justify-between p-2 rounded bg-[#0d1117] border border-border">
                  <span className="text-textMuted">Fluid Level from Surface:</span>
                  <span className="font-bold text-white">{bhp.sonolog_fluid_level_m} meters</span>
                </div>
                <div className="flex justify-between p-2 rounded bg-[#0d1117] border border-border">
                  <span className="text-textMuted">Hydrostatic Fluid Gradient:</span>
                  <span className="font-bold text-white">{bhp.fluid_gradient_psi_ft} psi/ft</span>
                </div>
                <div className="flex justify-between p-2 rounded bg-[#0d1117] border border-border">
                  <span className="text-textMuted">Liquid Column Submergence:</span>
                  <span className="font-bold text-emerald-400">
                    {(bhp.datum_depth_m_tvd - bhp.sonolog_fluid_level_m).toFixed(0)} meters
                  </span>
                </div>
              </div>

              <p className="text-[11px] text-textMuted leading-relaxed pt-1">
                Acoustic reflections confirmed clear gas/liquid meniscus. Zero liquid loading observed above operating gas lift valve.
              </p>
            </div>

            {/* Continuous Gas Lift Telemetry */}
            <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
                <Layers className="w-4 h-4 text-purple-400" />
                Continuous Gas Lift Aeration State
              </h4>

              <div className="space-y-2.5 font-mono text-xs">
                <div className="flex justify-between p-2 rounded bg-[#0d1117] border border-border">
                  <span className="text-textMuted">Annulus Injection Pressure:</span>
                  <span className="font-bold text-white">
                    {bhp.gas_lift_status.injection_pressure_casing_psi.toFixed(1)} psi
                  </span>
                </div>
                <div className="flex justify-between p-2 rounded bg-[#0d1117] border border-border">
                  <span className="text-textMuted">Gas Injection Rate:</span>
                  <span className="font-bold text-white">
                    {bhp.gas_lift_status.injection_rate_mcfd.toFixed(1)} MCFD
                  </span>
                </div>
                <div className="flex justify-between p-2 rounded bg-[#0d1117] border border-border">
                  <span className="text-textMuted">Active Operating Valve Depth:</span>
                  <span className="font-bold text-accent">
                    {bhp.gas_lift_status.operating_valve_depth_m} meters
                  </span>
                </div>
              </div>

              <div className="p-2 rounded bg-purple-950/30 border border-purple-800/40 text-[11px] text-purple-200">
                <span className="font-bold">Status:</span> {bhp.gas_lift_status.status}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Report 3: Water Chemistry & Scale Assay */}
      {activeSubTab === 'lab' && lab && (
        <div className="space-y-4 font-sans text-xs">
          {/* Header */}
          <div className="bg-[#12161c] border border-border p-4 rounded-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-amber-400 font-bold uppercase tracking-wider">
                  <FlaskConical className="w-3.5 h-3.5" />
                  {lab.issuing_authority}
                </div>
                <h3 className="text-base font-bold text-white mt-1">{lab.title}</h3>
                <div className="flex items-center gap-3 text-[11px] font-mono text-textMuted mt-2">
                  <span className="text-white font-semibold">Lab Assay Ref: {lab.report_id}</span>
                  <span>•</span>
                  <span>Sample Date: {lab.sample_date}</span>
                  <span>•</span>
                  <span className="text-amber-400">Tested Water Cut: {lab.water_cut_tested_pct}%</span>
                </div>
              </div>

              <span className="px-2.5 py-1 rounded bg-amber-950/60 border border-amber-700/60 text-amber-300 font-mono text-[10px] font-bold uppercase">
                GEOCHEMISTRY LABORATORY
              </span>
            </div>

            {/* General Chemistry KPIs */}
            <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-border/80 font-mono">
              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">Total Dissolved Solids</span>
                <div className="text-lg font-bold text-white mt-1">
                  {lab.total_dissolved_solids_tds_mg_l.toLocaleString()}{' '}
                  <span className="text-xs font-normal text-textMuted">mg/L</span>
                </div>
              </div>

              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">pH @ 25°C</span>
                <div className="text-lg font-bold text-emerald-400 mt-1">
                  {lab.ph_at_25c}
                </div>
                <span className="text-[10px] text-textMuted">Neutral to slightly alkaline</span>
              </div>

              <div className="bg-[#0d1117] p-3 rounded-lg border border-border">
                <span className="text-[10px] text-textMuted uppercase">Specific Gravity</span>
                <div className="text-lg font-bold text-sky-400 mt-1">
                  {lab.specific_gravity}
                </div>
              </div>
            </div>
          </div>

          {/* Ionic Distribution Table & Scaling Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Ionic Breakdown Table */}
            <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
                <Layers className="w-4 h-4 text-accent" />
                Ionic Constituents Distribution
              </h4>

              <div className="divide-y divide-border/60 font-mono text-xs">
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Chloride (Cl⁻)</span>
                  <span className="text-white font-bold">{lab.ionic_constituents_mg_l.chloride_cl.toLocaleString()} mg/L</span>
                </div>
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Sodium (Na⁺)</span>
                  <span className="text-white font-bold">{lab.ionic_constituents_mg_l.sodium_na.toLocaleString()} mg/L</span>
                </div>
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Calcium (Ca²⁺)</span>
                  <span className="text-white font-bold">{lab.ionic_constituents_mg_l.calcium_ca} mg/L</span>
                </div>
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Magnesium (Mg²⁺)</span>
                  <span className="text-white font-bold">{lab.ionic_constituents_mg_l.magnesium_mg} mg/L</span>
                </div>
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Barium (Ba²⁺)</span>
                  <span className="text-amber-400 font-bold">{lab.ionic_constituents_mg_l.barium_ba} mg/L</span>
                </div>
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Sulfate (SO₄²⁻)</span>
                  <span className="text-amber-400 font-bold">{lab.ionic_constituents_mg_l.sulfate_so4} mg/L</span>
                </div>
                <div className="py-1.5 flex justify-between">
                  <span className="text-textMuted">Bicarbonate (HCO₃⁻)</span>
                  <span className="text-white font-bold">{lab.ionic_constituents_mg_l.bicarbonate_hco3} mg/L</span>
                </div>
              </div>
            </div>

            {/* Scaling Tendency & Chemist Advice */}
            <div className="space-y-3">
              <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Mineral Scale Deposition Tendency
                </h4>

                <div className="space-y-2 text-xs">
                  <div className="p-2.5 rounded bg-[#0d1117] border border-border">
                    <div className="flex justify-between items-center font-mono">
                      <span className="text-white font-bold">Calcium Carbonate (CaCO₃)</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/60 text-amber-300 border border-amber-700/60">
                        {lab.scaling_tendency_analysis.stiff_davis_index} Index
                      </span>
                    </div>
                    <p className="text-[11px] text-textMuted mt-1">
                      {lab.scaling_tendency_analysis.calcium_carbonate_caco3}
                    </p>
                  </div>

                  <div className="p-2.5 rounded bg-[#0d1117] border border-border">
                    <div className="flex justify-between items-center font-mono">
                      <span className="text-white font-bold">Barium Sulfate (BaSO₄)</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-700/60">
                        Stable
                      </span>
                    </div>
                    <p className="text-[11px] text-textMuted mt-1">
                      {lab.scaling_tendency_analysis.barium_sulfate_baso4}
                    </p>
                  </div>
                </div>
              </div>

              {/* Chemist Recommendation */}
              <div className="bg-amber-950/20 border border-amber-800/40 p-3.5 rounded-xl flex items-start gap-2.5">
                <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="text-[10px] font-mono uppercase font-bold text-amber-400">
                    Lead Geochemist Recommendation:
                  </span>
                  <p className="text-xs text-amber-100/90 mt-0.5 leading-relaxed">
                    {lab.chemist_recommendation}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Report 4: Well Completion Report (WCR) */}
      {activeSubTab === 'completion' && wcr && (
        <div className="space-y-4 font-sans text-xs">
          {/* Header */}
          <div className="bg-[#12161c] border border-border p-4 rounded-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-mono text-blue-400 font-bold uppercase tracking-wider">
                  <FileText className="w-3.5 h-3.5" />
                  {wcr.issuing_authority}
                </div>
                <h3 className="text-base font-bold text-white mt-1">{wcr.title}</h3>
                <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-textMuted mt-2">
                  <span className="text-white font-semibold">WCR Ref: {wcr.report_id}</span>
                  <span>•</span>
                  <span>Spud Date: {wcr.spud_date}</span>
                  <span>•</span>
                  <span>Completion: {wcr.completion_date}</span>
                  <span>•</span>
                  <span className="text-accent">Total Depth: {wcr.total_depth_m}m TVD</span>
                </div>
              </div>

              <span className="px-2.5 py-1 rounded bg-blue-950/60 border border-blue-700/60 text-blue-300 font-mono text-[10px] font-bold uppercase">
                ASSET ARCHIVE
              </span>
            </div>
          </div>

          {/* Casing Policy & Perforation Tables */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Casing Policy */}
            <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
                <Layers className="w-4 h-4 text-accent" />
                Casing Program & Setting Depths
              </h4>

              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs">
                  <thead>
                    <tr className="border-b border-border text-textMuted text-[10px] uppercase">
                      <th className="pb-1.5">String</th>
                      <th className="pb-1.5">Shoe Depth</th>
                      <th className="pb-1.5">Cement Class</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {wcr.casing_policy.map((c, i) => (
                      <tr key={i} className="hover:bg-surface/50">
                        <td className="py-2 text-white font-semibold">{c.string}</td>
                        <td className="py-2 text-accent">{c.depth_m}m</td>
                        <td className="py-2 text-textMuted">{c.cement_class}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Perforated Intervals */}
            <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Perforated Pay Intervals
              </h4>

              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs">
                  <thead>
                    <tr className="border-b border-border text-textMuted text-[10px] uppercase">
                      <th className="pb-1.5">Depth Interval</th>
                      <th className="pb-1.5">Formation</th>
                      <th className="pb-1.5">Density</th>
                      <th className="pb-1.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {wcr.perforated_intervals.map((p, i) => (
                      <tr key={i} className="hover:bg-surface/50">
                        <td className="py-2 text-white font-semibold">{p.top_depth_m} - {p.bottom_depth_m}m</td>
                        <td className="py-2 text-accent">{p.formation}</td>
                        <td className="py-2 text-textMuted">{p.shots_per_meter} spm</td>
                        <td className="py-2 text-emerald-400 font-bold">{p.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Crude Assay Properties & Initial Test */}
          <div className="bg-[#12161c] border border-border p-4 rounded-xl space-y-3">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2 border-b border-border/80 pb-2">
              <Droplet className="w-4 h-4 text-amber-400" />
              Geleki Crude Oil Chemistry & Initial Production Test
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
              <div className="bg-[#0d1117] p-2.5 rounded border border-border">
                <span className="text-[10px] text-textMuted uppercase">API Gravity</span>
                <div className="text-base font-bold text-white mt-1">
                  {wcr.crude_assay.api_gravity}° API
                </div>
              </div>

              <div className="bg-[#0d1117] p-2.5 rounded border border-border">
                <span className="text-[10px] text-textMuted uppercase">Paraffin Wax %</span>
                <div className="text-base font-bold text-amber-400 mt-1">
                  {wcr.crude_assay.paraffin_wax_pct}%
                </div>
                <span className="text-[9px] text-amber-500/80">High Wax Content</span>
              </div>

              <div className="bg-[#0d1117] p-2.5 rounded border border-border">
                <span className="text-[10px] text-textMuted uppercase">Pour Point</span>
                <div className="text-base font-bold text-rose-400 mt-1">
                  {wcr.crude_assay.pour_point_c}°C
                </div>
                <span className="text-[9px] text-textMuted">Requires heat/PPD</span>
              </div>

              <div className="bg-[#0d1117] p-2.5 rounded border border-border">
                <span className="text-[10px] text-textMuted uppercase">Initial Flow Test</span>
                <div className="text-base font-bold text-emerald-400 mt-1">
                  {wcr.initial_production_test.oil_flow_bopd} BOPD
                </div>
                <span className="text-[9px] text-textMuted">At spud commissioning</span>
              </div>

              <div className="bg-[#0d1117] p-2.5 rounded border border-border">
                <span className="text-[10px] text-textMuted uppercase">Initial Water Cut</span>
                <div className="text-base font-bold text-sky-400 mt-1">
                  {wcr.initial_production_test.water_cut_pct}%
                </div>
                <span className="text-[9px] text-textMuted">Virgin reservoir state</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
