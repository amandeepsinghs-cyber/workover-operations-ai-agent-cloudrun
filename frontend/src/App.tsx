import React, { useState, useEffect, useMemo } from 'react';
import { Header } from './components/common/Header';
import { WellMap } from './components/map/WellMap';
import { WellDetails } from './components/telemetry/WellDetails';
import { VoiceAgentPanel } from './components/agent/VoiceAgentPanel';
import { FleetKPIs, WellDetail, WellSummary } from './types/well';
import { AlertCircle, Layers, MapPin, Search } from 'lucide-react';

export function App() {
  const [wells, setWells] = useState<WellSummary[]>([]);
  const [kpis, setKpis] = useState<FleetKPIs | null>(null);
  const [selectedWellId, setSelectedWellId] = useState<string | null>(null);
  const [selectedWellDetail, setSelectedWellDetail] = useState<WellDetail | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);

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

  // Filter wells by status and search query
  const filteredWells = useMemo(() => {
    return wells.filter((well) => {
      const matchesStatus =
        selectedStatus === 'all' || well.status.toLowerCase() === selectedStatus.toLowerCase();
      const matchesSearch =
        !searchQuery.trim() ||
        well.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        well.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        well.formation.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [wells, selectedStatus, searchQuery]);

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

      {/* Main Multi-Pane View */}
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center font-mono text-xs text-textMuted">
          <span className="animate-spin mr-2">◌</span> Initializing WellPulse Operations Core...
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Column: Interactive Map & Well Selection (34% width) */}
          <section className="w-[34%] min-w-[340px] flex flex-col border-r border-border relative bg-surface">
            {/* Map Header Indicator */}
            <div className="h-10 px-4 border-b border-border/80 flex items-center justify-between bg-[#12161c] text-xs font-mono text-textMuted shrink-0">
              <span className="flex items-center gap-1.5 text-white font-semibold">
                <MapPin className="w-3.5 h-3.5 text-accent" />
                Geleki Field Assets ({filteredWells.length})
              </span>
              <span className="text-[10px]">Click pin to inspect</span>
            </div>

            {/* Map Canvas */}
            <div className="flex-1 relative">
              <WellMap
                wells={filteredWells}
                selectedWellId={selectedWellId}
                onSelectWell={setSelectedWellId}
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
    </div>
  );
}

export default App;
