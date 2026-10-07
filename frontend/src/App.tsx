import React, { useState, useEffect, useMemo } from 'react';
import { Header } from './components/common/Header';
import { WellMap } from './components/map/WellMap';
import { WellDetails } from './components/telemetry/WellDetails';
import { VoiceAgentPanel } from './components/agent/VoiceAgentPanel';
import { FleetKPIs, WellDetail, WellSummary } from './types/well';
import { AlertCircle, Layers, MapPin, Search } from 'lucide-react';
import { assetApi, FieldFilter, Hierarchy } from './api/asset';
import { FieldSelector } from './components/fields/FieldSelector';
import { FieldHistoryChart } from './components/fields/FieldHistoryChart';
import { FieldComparison } from './components/fields/FieldComparison';
import { WellDeepDiveDrawer } from './components/well/WellDeepDiveDrawer';
import { usePersona } from './state/persona'; // Stage Y: tabs hidden per persona (UI hint; server enforces)
// Stage R (additive): field health buckets (TC-020) + priority queue (TC-010)
import { HealthBucketsCard } from './components/decision/HealthBucketsCard';
import { PriorityQueueTable } from './components/decision/PriorityQueueTable';
import type { FieldName } from './api/asset';

type ScreenTab = 'map' | 'field_history' | 'field_compare' | 'field_health';

export function App() {
  const [wells, setWells] = useState<WellSummary[]>([]);
  const [kpis, setKpis] = useState<FleetKPIs | null>(null);
  const [selectedWellId, setSelectedWellId] = useState<string | null>(null);
  const [selectedWellDetail, setSelectedWellDetail] = useState<WellDetail | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  // Stage T: multi-field navigation
  const [fieldFilter, setFieldFilter] = useState<FieldFilter>('ALL');
  const [hierarchy, setHierarchy] = useState<Hierarchy | null>(null);
  const [screenTab, setScreenTab] = useState<ScreenTab>('map');
  const { can } = usePersona(); // Stage Y
  const canAggregate = can('field.aggregate');
  // Stage R: health / priority tab (TC-020 field.health, TC-010 queue.read)
  const canHealth = can('field.health') || can('queue.read');
  const [healthField, setHealthField] = useState<FieldName>('Lakwa');
  useEffect(() => {
    if (fieldFilter !== 'ALL') setHealthField(fieldFilter);
  }, [fieldFilter]);
  useEffect(() => {
    if (screenTab === 'field_health' && !canHealth) setScreenTab('map');
  }, [canHealth, screenTab]);
  useEffect(() => {
    if (!canAggregate && screenTab !== 'map' && screenTab !== 'field_health') setScreenTab('map');
  }, [canAggregate, screenTab]);
  const [drawerWellId, setDrawerWellId] = useState<string | null>(null);

  // Fetch initial fleet data and KPIs
  useEffect(() => {
    Promise.all([
      fetch('/api/wells').then((res) => res.json()),
      fetch('/api/wells/kpis').then((res) => res.json()),
    ])
      .then(([wellsData, kpisData]) => {
        setWells(wellsData);
        setKpis(kpisData);
        if (wellsData.length > 0) {
          // Default to first critical or warning well for interesting demo
          const priorityWell =
            wellsData.find((w: WellSummary) => w.status === 'failed') ||
            wellsData.find((w: WellSummary) => w.status === 'warning') ||
            wellsData[0];
          setSelectedWellId(priorityWell.id);
        }
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Initialization error:', err);
        setIsLoading(false);
      });
  }, []);

  // Stage T: asset → field → cluster hierarchy for the field selector
  useEffect(() => {
    assetApi
      .fields()
      .then((env) => setHierarchy(env.data))
      .catch((err) => console.warn('Field hierarchy fetch failed:', err));
  }, []);

  // Stage T: KPI ribbon follows the field filter (BDD-F05-S02: equals /api/wells/kpis?field=)
  useEffect(() => {
    if (isLoading) return;
    const url = fieldFilter === 'ALL' ? '/api/wells/kpis' : `/api/wells/kpis?field=${encodeURIComponent(fieldFilter)}`;
    fetch(url)
      .then((res) => res.json())
      .then((k) => setKpis(k))
      .catch((err) => console.warn('KPI fetch failed:', err));
  }, [fieldFilter, isLoading]);

  // Fetch full details whenever selected well changes
  useEffect(() => {
    if (!selectedWellId) return;

    fetch(`/api/wells/${selectedWellId}`)
      .then((res) => res.json())
      .then((detail) => {
        setSelectedWellDetail(detail);
      })
      .catch((err) => {
        console.error(`Failed to fetch well ${selectedWellId}:`, err);
      });
  }, [selectedWellId]);

  // Filter wells by field, status and search query
  const filteredWells = useMemo(() => {
    return wells.filter((well) => {
      const matchesField =
        fieldFilter === 'ALL' || (well.field || '').toLowerCase() === fieldFilter.toLowerCase();
      const matchesStatus =
        selectedStatus === 'all' || well.status.toLowerCase() === selectedStatus.toLowerCase();
      const matchesSearch =
        !searchQuery.trim() ||
        well.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        well.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        well.formation.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesField && matchesStatus && matchesSearch;
    });
  }, [wells, fieldFilter, selectedStatus, searchQuery]);

  // Stage T: keep the selected well inside the chosen field
  useEffect(() => {
    if (fieldFilter === 'ALL' || !wells.length) return;
    const current = wells.find((w) => w.id === selectedWellId);
    if (current && (current.field || '').toLowerCase() === fieldFilter.toLowerCase()) return;
    const inField = wells.filter((w) => (w.field || '').toLowerCase() === fieldFilter.toLowerCase());
    const pick =
      inField.find((w) => w.status === 'failed') || inField.find((w) => w.status === 'warning') || inField[0];
    if (pick) setSelectedWellId(pick.id);
  }, [fieldFilter, wells]); // eslint-disable-line react-hooks/exhaustive-deps

  const mapTitle = fieldFilter === 'ALL' ? 'Assam Asset — all fields' : `${fieldFilter} Field Assets`;
  const tabBtn = (t: ScreenTab, label: string) => (
    <button
      key={t}
      onClick={() => setScreenTab(t)}
      className={`px-3 py-1 rounded transition-colors ${
        screenTab === t ? 'bg-surface text-white font-semibold border border-border' : 'text-textMuted hover:text-white'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="flex flex-col h-screen w-screen bg-background overflow-hidden text-textMain">
      {/* Top Header */}
      <Header
        kpis={kpis}
        selectedStatus={selectedStatus}
        onSelectStatus={setSelectedStatus}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* Stage T: field selector + screen tabs */}
      <div className="h-10 px-4 border-b border-border flex items-center gap-4 bg-[#0d1117] text-xs font-mono shrink-0">
        <FieldSelector value={fieldFilter} onChange={setFieldFilter} hierarchy={hierarchy} />
        <span className="text-border">|</span>
        <div className="flex items-center gap-1">
          {tabBtn('map', 'Map & wells')}
          {canAggregate && tabBtn('field_history', 'Field history (5y)')}
          {canAggregate && tabBtn('field_compare', 'Field comparison')}
          {canHealth && tabBtn('field_health', 'Health & priority')}
        </div>
      </div>

      {/* Main Multi-Pane View */}
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center font-mono text-xs text-textMuted">
          <span className="animate-spin mr-2">◌</span> Initializing WellPulse Operations Core...
        </div>
      ) : screenTab === 'field_history' ? (
        <div className="flex-1 overflow-y-auto p-4">
          <FieldHistoryChart initialFields={fieldFilter === 'ALL' ? undefined : [fieldFilter]} />
        </div>
      ) : screenTab === 'field_compare' ? (
        <div className="flex-1 overflow-y-auto p-4">
          <FieldComparison
            onSelectField={(f) => {
              setFieldFilter(f);
              setScreenTab('map');
            }}
          />
        </div>
      ) : screenTab === 'field_health' ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-textMuted">Field:</span>
            {(['Geleki', 'Lakwa', 'Lakhmani'] as FieldName[]).map((f) => (
              <button
                key={f}
                onClick={() => setHealthField(f)}
                className={`px-2.5 py-1 rounded border ${
                  healthField === f ? 'border-accent text-white bg-surface' : 'border-border text-textMuted hover:text-white'
                }`}
              >
                {f}
              </button>
            ))}
            <span className="text-textMuted ml-2">Click a well to open its deep dive (next best action, counterfactual).</span>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(320px,2fr)_3fr] gap-4">
            <HealthBucketsCard
              field={healthField}
              selectedWellId={drawerWellId}
              onSelectWell={(id) => {
                setSelectedWellId(id);
                setDrawerWellId(id);
              }}
            />
            <PriorityQueueTable
              field={healthField}
              limit={20}
              selectedWellId={drawerWellId}
              onSelectWell={(id) => {
                setSelectedWellId(id);
                setDrawerWellId(id);
              }}
            />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Column: Interactive Map & Well Selection (34% width) */}
          <section className="w-[34%] min-w-[340px] flex flex-col border-r border-border relative bg-surface">
            {/* Map Header Indicator */}
            <div className="h-10 px-4 border-b border-border/80 flex items-center justify-between bg-[#12161c] text-xs font-mono text-textMuted shrink-0">
              <span className="flex items-center gap-1.5 text-white font-semibold">
                <MapPin className="w-3.5 h-3.5 text-accent" />
                {mapTitle} ({filteredWells.length})
              </span>
              {selectedWellId ? (
                <button
                  onClick={() => setDrawerWellId(selectedWellId)}
                  className="text-[10px] px-2 py-0.5 rounded border border-accent text-accent hover:bg-accent hover:text-white"
                  title="Open well deep dive: history, interventions, construction, nearby wells"
                >
                  Deep dive {selectedWellId}
                </button>
              ) : (
                <span className="text-[10px]">Click pin to inspect</span>
              )}
            </div>

            {/* Map Canvas */}
            <div className="flex-1 relative">
              <WellMap
                wells={filteredWells}
                selectedWellId={selectedWellId}
                onSelectWell={setSelectedWellId}
                field={fieldFilter}
                onOpenWell={setDrawerWellId}
              />
            </div>

            {/* Compact Well Selector Drawer at bottom of Map */}
            <div className="h-44 border-t border-border bg-[#0d1117] flex flex-col shrink-0">
              <div className="px-3 py-1.5 border-b border-border text-[10px] font-mono text-textMuted flex items-center justify-between">
                <span>QUICK SELECTOR</span>
                <span>{filteredWells.length} WELLS FILTERED</span>
              </div>
              <div className="flex-1 overflow-y-auto divide-y divide-border/40 text-xs">
                {filteredWells.map((w) => {
                  const isSelected = w.id === selectedWellId;
                  const statusColor =
                    w.status === 'healthy'
                      ? 'text-healthy'
                      : w.status === 'warning'
                      ? 'text-warning'
                      : 'text-critical';

                  return (
                    <div
                      key={w.id}
                      onClick={() => setSelectedWellId(w.id)}
                      className={`px-3 py-2 flex items-center justify-between cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-surface border-l-4 border-accent text-white font-semibold'
                          : 'hover:bg-surface/50 text-textMuted hover:text-white'
                      }`}
                    >
                      <div>
                        <div className="font-sans text-xs">{w.name}</div>
                        <div className="font-mono text-[10px] text-textMuted">
                          {w.id} • {w.formation}
                        </div>
                      </div>
                      <div className="text-right font-mono">
                        <div className="text-xs text-white">{w.current_metrics.oil_bopd} BOPD</div>
                        <div className={`text-[10px] font-bold uppercase ${statusColor}`}>
                          {w.status}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          {/* Middle Column: Well Telemetry, 24-Month History & Workovers (38% width) */}
          <section className="flex-1 min-w-[400px] flex flex-col border-r border-border overflow-hidden">
            {selectedWellDetail ? (
              <WellDetails well={selectedWellDetail} />
            ) : (
              <div className="flex-1 flex items-center justify-center font-mono text-xs text-textMuted">
                Select a well from the map or list to view historical telemetry
              </div>
            )}
          </section>

          {/* Right Column: Voice-Enabled AI Copilot (28% width, ~380px) */}
          <section className="w-[28%] min-w-[340px] max-w-[420px] flex flex-col overflow-hidden">
            {selectedWellDetail ? (
              <VoiceAgentPanel well={selectedWellDetail} />
            ) : (
              <div className="flex-1 flex items-center justify-center font-mono text-xs text-textMuted p-6 text-center">
                Select a wellhead to activate the contextual Voice AI Copilot.
              </div>
            )}
          </section>
        </div>
      )}

      {/* Stage T: well deep-dive drawer */}
      {drawerWellId && (
        <WellDeepDiveDrawer
          wellId={drawerWellId}
          onClose={() => setDrawerWellId(null)}
          onSelectWell={(id) => {
            setDrawerWellId(id);
            setSelectedWellId(id);
          }}
        />
      )}
    </div>
  );
}

export default App;
