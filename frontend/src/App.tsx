import React, { useState, useEffect, useMemo } from 'react';
import { Header } from './components/common/Header';
import { WellMap } from './components/map/WellMap';
import { FloatingAgent, AGENT_DOCK_WIDTH } from './components/agent/FloatingAgent';
import { FleetKPIs, WellDetail, WellSummary } from './types/well';
import { Maximize2, Minimize2, X } from 'lucide-react';
import { assetApi, FieldFilter, Hierarchy } from './api/asset';
import { FieldSelector } from './components/fields/FieldSelector';
import { FieldHistoryChart } from './components/fields/FieldHistoryChart';
import { FieldComparison } from './components/fields/FieldComparison';
import { WellDeepDiveDrawer, CanvasView } from './components/well/WellDeepDiveDrawer';
import { FieldReportOverlay } from './components/well/FieldReportOverlay';
import { usePersona } from './state/persona'; // Stage Y: tabs hidden per persona (UI hint; server enforces)
// Stage R (additive): field health buckets (TC-020) + priority queue (TC-010)
import { HealthBucketsCard } from './components/decision/HealthBucketsCard';
import { PriorityQueueTable } from './components/decision/PriorityQueueTable';
import type { FieldName } from './api/asset';
import type { ChatAction } from './api/chat';
import { dispatchUi, useUiCommands } from './agent/uiCommands';

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
  const [canvasView, setCanvasView] = useState<CanvasView>('summary');
  const [canvasCompareRec, setCanvasCompareRec] = useState<string | undefined>(undefined);
  // Middle (well telemetry) panel expanded: map hidden, agent stays on the right as command centre.
  const [middleExpanded, setMiddleExpanded] = useState<boolean>(false);
  // Map full-screen (reported by WellMap) and whether the agent is docked as the right-hand column.
  const [mapFullscreen, setMapFullscreen] = useState<boolean>(false);
  const [agentDocked, setAgentDocked] = useState<boolean>(false);
  // Step 5: well whose printable field report is open in the full-screen overlay.
  const [reportWellId, setReportWellId] = useState<string | null>(null);
  const [reportPrint, setReportPrint] = useState<boolean>(false);
  useEffect(() => {
    if (!middleExpanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !drawerWellId && !selectedWellId) setMiddleExpanded(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [middleExpanded, drawerWellId, selectedWellId]);
  // While the full detail is open, picking another well on the map/list shows that well's detail.
  useEffect(() => {
    if (drawerWellId && selectedWellId && selectedWellId !== drawerWellId) setDrawerWellId(selectedWellId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWellId]);

  const handleAgentAction = (a: ChatAction) => {
    if (a.kind === 'ui') {
      if (a.command) dispatchUi(a.command);
      return;
    }
    if (a.kind === 'navigate') {
      if (a.field) {
        setFieldFilter(a.field as FieldFilter);
        if (a.screen === 'field_health' || a.screen === 'priority') {
          setHealthField(a.field as FieldName);
        }
      }
      if (a.well_id) {
        setSelectedWellId(a.well_id);
        // Answer canvas (2026-10-08): each well answer shows only its focused view in the middle
        // panel (production, interventions, wellbore, recommendation, ...). The chat keeps the short answer.
        if (a.screen === 'well') {
          setCanvasView((a.view as CanvasView) ?? 'overview');
          setCanvasCompareRec(a.compare_recommended);
          setDrawerWellId(a.well_id);
          // The agent now floats over every tab; well answers always land in the map + panel view.
          setScreenTab('map');
        }
      }
      if (a.screen === 'map') {
        setScreenTab('map');
      } else if (a.screen === 'field_history' && canAggregate) {
        setScreenTab('field_history');
      } else if (a.screen === 'field_compare' && canAggregate) {
        setScreenTab('field_compare');
      } else if ((a.screen === 'field_health' || a.screen === 'priority') && canHealth) {
        setScreenTab('field_health');
      }
      // Stage ED-10 (F-41): the map follows the agent — zoom to the well, or drill into the field.
      if (a.well_id && a.screen === 'well') dispatchUi({ action: 'focus_well', well_id: a.well_id });
      else if (a.field && (a.screen === 'map' || !a.well_id)) dispatchUi({ action: 'focus_field', value: a.field });
    }
  };

  // Fetch initial fleet data and KPIs
  useEffect(() => {
    Promise.all([
      fetch('/api/wells').then((res) => res.json()),
      fetch('/api/wells/kpis').then((res) => res.json()),
    ])
      .then(([wellsData, kpisData]) => {
        setWells(wellsData);
        setKpis(kpisData);
        // Step 2: no well is pre-selected — the user lands on the full map of all wells.
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
      const matchesSearch =
        !searchQuery.trim() ||
        well.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        well.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        well.formation.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesField && matchesSearch;
    });
  }, [wells, fieldFilter, searchQuery]);

  // Stage T: keep the selection inside the chosen field. Step 2: if the selected well is outside the
  // new field, clear it (the map zooms to the field) instead of auto-opening another well.
  useEffect(() => {
    if (fieldFilter === 'ALL' || !wells.length || !selectedWellId) return;
    const current = wells.find((w) => w.id === selectedWellId);
    if (current && (current.field || '').toLowerCase() === fieldFilter.toLowerCase()) return;
    setSelectedWellId(null);
    setSelectedWellDetail(null);
    setDrawerWellId(null);
  }, [fieldFilter, wells]); // eslint-disable-line react-hooks/exhaustive-deps



  // "What the agent sees": Field · Well · View (shown in the agent header, sent with each turn via props).
  const SCREEN_LABEL: Record<ScreenTab, string> = {
    map: 'Map',
    field_history: 'Field history',
    field_compare: 'Field comparison',
    field_health: 'Health & priority',
  };
  const agentContextLabel = [
    fieldFilter === 'ALL' ? 'Assam Asset' : fieldFilter,
    screenTab === 'map' ? selectedWellId : null,
    screenTab === 'map' && drawerWellId
      ? canvasView.charAt(0).toUpperCase() + canvasView.slice(1).replace(/_/g, ' ')
      : SCREEN_LABEL[screenTab],
  ]
    .filter(Boolean)
    .join(' · ');
  // Step 2 (UI redesign): the map is the home screen. The right-hand panel opens only when there is
  // something to show — a selected well, a well view, or a field view (history / comparison / health).
  const panelOpen = screenTab !== 'map' || !!drawerWellId || !!selectedWellId;
  const closePanel = () => {
    setDrawerWellId(null);
    setSelectedWellId(null);
    setSelectedWellDetail(null);
    setScreenTab('map');
    setMiddleExpanded(false);
  };
  const openWellInPanel = (id: string, view: CanvasView = 'summary') => {
    setSelectedWellId(id);
    setDrawerWellId(id);
    setCanvasView(view);
    setScreenTab('map');
  };

  // Stage ED-10 / ED-11 (F-41): hands-off commands that change app state (the map handles its own).
  useUiCommands((cmd) => {
    // Panel-bound commands: leave map full screen first so the panel is visible.
    if (
      mapFullscreen &&
      (cmd.action === 'open_well' || cmd.action === 'open_screen' || (cmd.action === 'panel' && cmd.value === 'expand'))
    ) {
      dispatchUi({ action: 'fullscreen', value: 'off' });
    }
    switch (cmd.action) {
      case 'focus_field':
        if (cmd.value) setFieldFilter(cmd.value as FieldFilter);
        if (cmd.value && cmd.value !== 'ALL' && healthField !== cmd.value) setHealthField(cmd.value as FieldName);
        return;
      case 'focus_well':
      case 'open_well': {
        const id = cmd.well_id || selectedWellId || drawerWellId;
        if (!id) return;
        const w = wells.find((x) => x.id === id);
        // Keep the well visible: switch the field filter if it hides this well.
        if (w && fieldFilter !== 'ALL' && w.field !== fieldFilter) setFieldFilter(w.field as FieldFilter);
        if (cmd.action === 'open_well') openWellInPanel(id, (cmd.view as CanvasView) || 'overview');
        else {
          setSelectedWellId(id);
          setScreenTab('map');
        }
        return;
      }
      case 'open_screen': {
        const s = cmd.value as ScreenTab;
        if ((s === 'field_history' || s === 'field_compare') && !canAggregate) return;
        if (s === 'field_health' && !canHealth) return;
        setScreenTab(s);
        return;
      }
      case 'panel':
        if (cmd.value === 'close') closePanel();
        else if (cmd.value === 'expand') setMiddleExpanded(true);
        else setMiddleExpanded(false);
        return;
      case 'health_filter':
        setSelectedStatus(
          cmd.value === 'healthy' ? 'healthy' : cmd.value === 'attention' ? 'warning' : cmd.value === 'not_producing' ? 'failed' : 'all',
        );
        return;
      case 'report': {
        if (cmd.value === 'close') {
          setReportWellId(null);
          setReportPrint(false);
        }
        else if (cmd.value === 'print' && reportWellId) return; // the open overlay prints itself
        else {
          const id = cmd.well_id || drawerWellId || selectedWellId;
          if (id) {
            setReportPrint(cmd.value === 'print');
            setReportWellId(id);
          }
        }
        return;
      }
      default:
        return;
    }
  });
  // Esc / panel close: leave expanded mode first, otherwise return to the full map.
  const handlePanelBack = () => {
    if (mapFullscreen) return; // Esc belongs to the full-screen map
    if (middleExpanded) setMiddleExpanded(false);
    else closePanel();
  };
  const fieldViewBtn = (t: ScreenTab, label: string) => (
    <button
      key={t}
      type="button"
      onClick={() => setScreenTab(screenTab === t ? 'map' : t)}
      className={`px-2.5 py-1 rounded transition-colors ${
        screenTab === t ? 'bg-accent/80 text-white font-semibold' : 'text-white/75 hover:text-white hover:bg-white/10'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div
      className="flex flex-col h-screen w-screen bg-background overflow-hidden text-textMain"
      style={agentDocked ? { paddingRight: AGENT_DOCK_WIDTH } : undefined}
    >
      {/* Top Header (KPIs, status filter, search) */}
      <Header
        kpis={kpis}
        compact={agentDocked}
        selectedStatus={selectedStatus}
        onSelectStatus={(s) =>
          // ED-14 (D-41): header KPIs drive the same health filter as the agent / voice / map legend.
          dispatchUi({
            action: 'health_filter',
            value: s === selectedStatus || s === 'all' ? 'all' : s === 'healthy' ? 'healthy' : s === 'warning' ? 'attention' : 'not_producing',
          })
        }
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center font-mono text-xs text-textMuted">
          <span className="animate-spin mr-2">◌</span> Initializing WellPulse Operations Core...
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Map — full width on the home screen, 50% when the panel is open; hidden while the panel is expanded */}
          <section
            className={`${panelOpen ? 'w-1/2 min-w-[360px] border-r border-border' : 'w-full'} flex flex-col relative bg-surface ${
              panelOpen && middleExpanded ? 'hidden' : ''
            }`}
          >
            <div className="flex-1 relative">
              <WellMap
                wells={filteredWells}
                selectedWellId={selectedWellId}
                onSelectWell={(id) => openWellInPanel(id, 'summary')}
                field={fieldFilter}
                onOpenWell={(id) => openWellInPanel(id, 'overview')}
                onFullscreenChange={setMapFullscreen}
                fullscreenRightInset={agentDocked ? AGENT_DOCK_WIDTH : undefined}
              />

              {/* Map overlay: field selector + field views (see-through, top-left) */}
              <div className="absolute top-3 left-3 z-[500] flex flex-col items-start gap-1.5 max-w-[calc(100%-1.5rem)] pointer-events-none">
                <div className="pointer-events-auto rounded-lg bg-black/45 backdrop-blur-sm border border-white/10 shadow-lg">
                  <FieldSelector value={fieldFilter} onChange={setFieldFilter} hierarchy={hierarchy} variant="overlay" />
                </div>
                {(canAggregate || canHealth) && (
                  <div className="pointer-events-auto flex items-center gap-0.5 p-1 rounded-lg bg-black/45 backdrop-blur-sm border border-white/10 shadow-lg text-[11px] font-sans">
                    {canAggregate && fieldViewBtn('field_history', 'Field history')}
                    {canAggregate && fieldViewBtn('field_compare', 'Compare fields')}
                    {canHealth && fieldViewBtn('field_health', 'Health & priority')}
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Right-hand panel: well summary / well views / field views */}
          {panelOpen && (
            <section className="flex-1 basis-1/2 min-w-[400px] flex flex-col overflow-hidden relative">
              {/* z-30: must sit above the well panel's sticky header (z-20), which would otherwise hide it. */}
              <div className="absolute top-2 right-2 z-30 flex items-center gap-1">
                <button
                  onClick={() => setMiddleExpanded((v) => !v)}
                  className="p-1.5 rounded border border-border bg-[#12161c]/90 text-textMuted hover:text-white hover:border-accent"
                  title={middleExpanded ? 'Restore map (ESC)' : 'Expand this panel (hide map)'}
                  aria-label={middleExpanded ? 'Restore map' : 'Expand panel'}
                >
                  {middleExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={closePanel}
                  className="p-1.5 rounded border border-border bg-[#12161c]/90 text-textMuted hover:text-white hover:border-accent"
                  title="Close panel — back to the full map"
                  aria-label="Close panel"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {screenTab === 'field_history' ? (
                <div className="flex-1 overflow-y-auto p-4 pt-12">
                  <FieldHistoryChart initialFields={fieldFilter === 'ALL' ? undefined : [fieldFilter]} />
                </div>
              ) : screenTab === 'field_compare' ? (
                <div className="flex-1 overflow-y-auto p-4 pt-12">
                  <FieldComparison
                    onSelectField={(f) => {
                      setFieldFilter(f);
                      setScreenTab('map');
                    }}
                  />
                </div>
              ) : screenTab === 'field_health' ? (
                <div className="flex-1 overflow-y-auto p-4 pt-12 space-y-4">
                  <div className="flex items-center gap-2 text-xs font-mono flex-wrap">
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
                    <span className="text-textMuted ml-2">Click a well to open it.</span>
                  </div>
                  <HealthBucketsCard field={healthField} selectedWellId={drawerWellId} onSelectWell={(id) => openWellInPanel(id)} />
                  <PriorityQueueTable
                    field={healthField}
                    limit={20}
                    selectedWellId={drawerWellId}
                    onSelectWell={(id) => openWellInPanel(id)}
                  />
                </div>
              ) : (
                // One well panel: Summary first, slim tab strip for the deeper views.
                <WellDeepDiveDrawer
                  embedded
                  wellId={(drawerWellId ?? selectedWellId) as string}
                  view={canvasView}
                  onViewChange={setCanvasView}
                  compareRecommended={canvasCompareRec}
                  onClose={handlePanelBack}
                  onSelectWell={(id) => openWellInPanel(id, canvasView)}
                  onFieldReport={setReportWellId}
                />
              )}
            </section>
          )}
        </div>
      )}

      {/* Urvi AI Agent — floating command centre, mounted once so it is on every screen
          and keeps its voice session + conversation when minimised or when screens change. */}
      <FloatingAgent
        well={selectedWellDetail}
        field={fieldFilter === 'ALL' ? null : fieldFilter}
        screen={screenTab}
        contextLabel={agentContextLabel}
        onAgentAction={handleAgentAction}
        autoDock={(middleExpanded && panelOpen) || mapFullscreen}
        onDockedChange={setAgentDocked}
        onOpenFieldReport={setReportWellId}
        suspended={!!reportWellId}
      />

      {/* Step 5: printable field report — full-screen overlay (Print / Close / Esc). */}
      {reportWellId && (
        <FieldReportOverlay
          key={reportWellId}
          wellId={reportWellId}
          printOnLoad={reportPrint}
          onClose={() => {
            setReportWellId(null);
            setReportPrint(false);
          }}
        />
      )}
    </div>
  );
}

export default App;
