import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { WellSummary, FieldInfrastructure, GatheringStation } from '../../types/well';
import { Globe, Layers, Network, Building2, Maximize2, Minimize2, X } from 'lucide-react';

interface WellMapProps {
  wells: WellSummary[];
  selectedWellId: string | null;
  onSelectWell: (wellId: string) => void;
}

export const WellMap: React.FC<WellMapProps> = ({
  wells,
  selectedWellId,
  onSelectWell,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const infraLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const markersRef = useRef<{ [id: string]: L.Marker }>({});
  const [mapStyle, setMapStyle] = useState<'satellite' | 'dark'>('satellite');
  const [showFlowlines, setShowFlowlines] = useState<boolean>(true);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [infrastructure, setInfrastructure] = useState<FieldInfrastructure | null>(null);

  // Resize Leaflet Map when toggling Fullscreen
  useEffect(() => {
    const timer = setTimeout(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [isFullscreen]);

  // Handle ESC key to exit fullscreen
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  // Fetch Geleki Field Infrastructure (GGS stations, CDP)
  useEffect(() => {
    fetch('/api/field/infrastructure')
      .then((res) => res.json())
      .then((data: FieldInfrastructure) => {
        setInfrastructure(data);
      })
      .catch((err) => {
        console.warn('Field infrastructure fetch failed, using fallback:', err);
      });
  }, []);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Centered on Geleki Oil Field (Sivasagar, Assam, India)
    const map = L.map(mapContainerRef.current, {
      center: [26.775, 94.690],
      zoom: 12,
      zoomControl: true,
      attributionControl: false,
    });

    const tileGroup = L.layerGroup().addTo(map);
    tileLayerGroupRef.current = tileGroup;

    const infraGroup = L.layerGroup().addTo(map);
    infraLayerGroupRef.current = infraGroup;

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Tile Layers when mapStyle changes
  useEffect(() => {
    const tileGroup = tileLayerGroupRef.current;
    if (!tileGroup) return;

    tileGroup.clearLayers();

    if (mapStyle === 'satellite') {
      // High-Resolution Satellite Aerial Photography (Esri World Imagery)
      const satellite = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
          maxZoom: 18,
          attribution: 'Esri World Imagery, Maxar, Earthstar Geographics',
        }
      );

      // Boundary and Place Reference Overlays
      const reference = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        {
          maxZoom: 18,
        }
      );

      tileGroup.addLayer(satellite);
      tileGroup.addLayer(reference);
    } else {
      // Dark Gray SCADA GIS Basemap
      const darkBase = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        {
          maxZoom: 16,
          attribution: 'Esri, DeLorme, NAVTEQ',
        }
      );

      const darkRef = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
        {
          maxZoom: 16,
        }
      );

      tileGroup.addLayer(darkBase);
      tileGroup.addLayer(darkRef);
    }
  }, [mapStyle]);

  // Update Markers whenever wells list or selection changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear previous markers
    Object.values(markersRef.current).forEach((marker) => marker.remove());
    markersRef.current = {};

    wells.forEach((well) => {
      const isSelected = well.id === selectedWellId;

      // Color mapping
      let color = '#2ea043'; // healthy green
      let pulseClass = '';
      let statusText = 'HEALTHY';

      if (well.status === 'warning') {
        color = '#d29922'; // amber
        pulseClass = 'pin-pulse-warning';
        statusText = 'NEEDS ATTENTION';
      } else if (well.status === 'failed') {
        color = '#f85149'; // critical red
        pulseClass = 'pin-pulse-critical';
        statusText = 'CRITICAL / TRIPPED';
      }

      const size = isSelected ? 32 : 24;
      const wellNumber = well.id.replace('GLK-', '');

      // Custom Tagged Pin with Well Name Header Badge and Oil Derrick Icon
      const customIcon = L.divIcon({
        className: 'custom-tagged-well-pin',
        html: `
          <div style="position: relative; width: ${size}px; height: ${size}px; cursor: pointer;">
            <!-- Permanent Tagged Well Name Badge Above Pin -->
            <div style="
              position: absolute;
              bottom: ${size + 4}px;
              left: 50%;
              transform: translateX(-50%);
              background: rgba(13, 17, 23, 0.92);
              border: 1.5px solid ${color};
              color: #ffffff;
              font-family: 'JetBrains Mono', monospace;
              font-size: 10px;
              font-weight: 700;
              padding: 1px 5px;
              border-radius: 4px;
              white-space: nowrap;
              box-shadow: 0 2px 8px rgba(0,0,0,0.8);
              pointer-events: none;
              letter-spacing: 0.5px;
              display: flex;
              align-items: center;
              gap: 3px;
            ">
              <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background-color: ${color};"></span>
              <span>${well.id}</span>
            </div>

            <!-- Pulsing Radar Glow on Critical/Warning Wells -->
            ${(well.status === 'failed' || well.status === 'warning') ? `
              <div class="${pulseClass}" style="position: absolute; top: -5px; left: -5px; width: ${size + 10}px; height: ${size + 10}px; border-radius: 50%; border: 2px solid ${color};"></div>
            ` : ''}

            <!-- Circular Wellhead Pin -->
            <div style="
              width: ${size}px;
              height: ${size}px;
              border-radius: 50%;
              background-color: ${color};
              border: ${isSelected ? '3px solid #ffffff' : '2px solid #0d1117'};
              box-shadow: 0 4px 14px rgba(0,0,0,0.7);
              display: flex;
              align-items: center;
              justify-content: center;
              transition: transform 0.2s ease;
            ">
              <!-- Oil Derrick Wellhead Glyph (Replacing confusing dollar sign) -->
              <svg width="${size * 0.55}" height="${size * 0.55}" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2 L4 22 M12 2 L20 22 M7 14 L17 14 M9 9 L15 9 M12 2 V6 M8 22 L16 22"/>
              </svg>
            </div>
          </div>
        `,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const marker = L.marker([well.coordinates.lat, well.coordinates.lng], {
        icon: customIcon,
      }).addTo(map);

      // Popup content
      const popupHtml = `
        <div style="font-family: 'Inter', sans-serif; font-size: 12px; color: #e6edf3;">
          <div style="font-weight: 700; font-size: 13px; margin-bottom: 2px; color: #ffffff;">${well.name}</div>
          <div style="font-family: monospace; font-size: 10px; color: #8b949e; margin-bottom: 8px;">${well.id} • ${well.formation}</div>
          
          <div style="display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; font-family: monospace; background: ${color}20; color: ${color}; border: 1px solid ${color}60; margin-bottom: 8px;">
            ${statusText}
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px solid #30363d; padding-top: 6px;">
            <div>
              <span style="color: #8b949e; font-size: 10px;">Oil Production:</span><br/>
              <strong style="color: #e6edf3;">${well.current_metrics.oil_bopd} BOPD</strong>
            </div>
            <div>
              <span style="color: #8b949e; font-size: 10px;">Water Cut:</span><br/>
              <strong style="color: #e6edf3;">${well.current_metrics.water_cut_pct}%</strong>
            </div>
            <div>
              <span style="color: #8b949e; font-size: 10px;">Artificial Lift:</span><br/>
              <strong style="color: #e6edf3;">${well.lift_type}</strong>
            </div>
            <div>
              <span style="color: #8b949e; font-size: 10px;">Tubing Head:</span><br/>
              <strong style="color: #e6edf3;">${well.current_metrics.tubing_pressure_psi} psi</strong>
            </div>
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml);

      marker.on('click', () => {
        onSelectWell(well.id);
      });

      markersRef.current[well.id] = marker;
    });

    // If well selected, pan smoothly to it
    if (selectedWellId && markersRef.current[selectedWellId]) {
      const selectedWell = wells.find((w) => w.id === selectedWellId);
      if (selectedWell) {
        map.panTo([selectedWell.coordinates.lat, selectedWell.coordinates.lng], {
          animate: true,
          duration: 0.6,
        });
      }
    }
  }, [wells, selectedWellId, onSelectWell]);

  // Update Infrastructure and Flowlines Layer
  useEffect(() => {
    const infraGroup = infraLayerGroupRef.current;
    if (!infraGroup) return;

    infraGroup.clearLayers();

    if (!infrastructure || !showFlowlines) return;

    const cdpStation = infrastructure.gathering_stations.find((s) => s.id.startsWith('CDP'));

    // 1. Render Trunk Flowlines from GGS stations to Central Desalting Plant (CDP)
    if (cdpStation) {
      infrastructure.gathering_stations.forEach((station) => {
        if (!station.id.startsWith('CDP')) {
          const trunkLine = L.polyline(
            [
              [station.coordinates.lat, station.coordinates.lng],
              [cdpStation.coordinates.lat, cdpStation.coordinates.lng],
            ],
            {
              color: '#10b981',
              weight: 3,
              dashArray: '8, 8',
              opacity: 0.75,
              smoothFactor: 1,
            }
          );
          trunkLine.bindTooltip(`Main Gathering Header: ${station.id} ➔ ${cdpStation.id}`, {
            sticky: true,
            className: 'font-mono text-[10px]',
          });
          infraGroup.addLayer(trunkLine);
        }
      });
    }

    // 2. Render Field Flowlines from Wells to their Servicing GGS
    const wellMapById: { [id: string]: WellSummary } = {};
    wells.forEach((w) => {
      wellMapById[w.id] = w;
    });

    infrastructure.gathering_stations.forEach((station) => {
      if (station.serviced_wells) {
        station.serviced_wells.forEach((wellId) => {
          const well = wellMapById[wellId];
          if (well) {
            const isTargetWell = well.id === selectedWellId;
            const flowline = L.polyline(
              [
                [well.coordinates.lat, well.coordinates.lng],
                [station.coordinates.lat, station.coordinates.lng],
              ],
              {
                color: isTargetWell ? '#60a5fa' : '#38bdf8',
                weight: isTargetWell ? 3.5 : 1.8,
                dashArray: '4, 6',
                opacity: isTargetWell ? 0.95 : 0.55,
                smoothFactor: 1,
              }
            );
            flowline.bindTooltip(`${well.id} ➔ ${station.id} Flowline`, {
              sticky: true,
              className: 'font-mono text-[10px]',
            });
            infraGroup.addLayer(flowline);
          }
        });
      }
    });

    // 3. Render Gathering Station (GGS) & CDP Facility Markers
    infrastructure.gathering_stations.forEach((station) => {
      const isCDP = station.id.startsWith('CDP');
      const facilityColor = isCDP ? '#06b6d4' : '#f59e0b';
      const facilityBg = isCDP ? 'rgba(6, 182, 212, 0.25)' : 'rgba(245, 158, 11, 0.25)';

      const facilityIcon = L.divIcon({
        className: 'custom-facility-pin',
        html: `
          <div style="position: relative; width: 34px; height: 34px; cursor: pointer;">
            <!-- Permanent Facility Label -->
            <div style="
              position: absolute;
              bottom: 38px;
              left: 50%;
              transform: translateX(-50%);
              background: rgba(13, 17, 23, 0.94);
              border: 1.5px solid ${facilityColor};
              color: ${facilityColor};
              font-family: 'JetBrains Mono', monospace;
              font-size: 10px;
              font-weight: 800;
              padding: 2px 6px;
              border-radius: 4px;
              white-space: nowrap;
              box-shadow: 0 4px 12px rgba(0,0,0,0.85);
              pointer-events: none;
              letter-spacing: 0.5px;
            ">
              ${station.id}
            </div>

            <!-- Pulsing Ring -->
            <div style="
              position: absolute;
              top: -4px;
              left: -4px;
              width: 42px;
              height: 42px;
              border-radius: 8px;
              border: 2px solid ${facilityColor};
              opacity: 0.4;
            "></div>

            <!-- Facility Hexagon/Square Hub Icon -->
            <div style="
              width: 34px;
              height: 34px;
              border-radius: 8px;
              background-color: #0d1117;
              border: 2px solid ${facilityColor};
              box-shadow: 0 0 12px ${facilityBg};
              display: flex;
              align-items: center;
              justify-content: center;
            ">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${facilityColor}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2" />
                <path d="M9 22v-4h6v4" />
                <path d="M8 6h.01" />
                <path d="M16 6h.01" />
                <path d="M12 6h.01" />
                <path d="M12 10h.01" />
                <path d="M12 14h.01" />
                <path d="M16 10h.01" />
                <path d="M16 14h.01" />
                <path d="M8 10h.01" />
                <path d="M8 14h.01" />
              </svg>
            </div>
          </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      });

      const facilityMarker = L.marker([station.coordinates.lat, station.coordinates.lng], {
        icon: facilityIcon,
        zIndexOffset: 500,
      });

      const stationPopup = `
        <div style="font-family: 'Inter', sans-serif; font-size: 12px; color: #e6edf3; min-width: 200px;">
          <div style="font-weight: 700; font-size: 13px; color: ${facilityColor}; margin-bottom: 2px;">
            ${station.name}
          </div>
          <div style="font-family: monospace; font-size: 10px; color: #8b949e; margin-bottom: 8px;">
            Infrastructure Node: ${station.id}
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px solid #30363d; padding-top: 6px;">
            <div>
              <span style="color: #8b949e; font-size: 10px;">Throughput Cap:</span><br/>
              <strong style="color: #ffffff;">${station.capacity_bopd.toLocaleString()} BOPD</strong>
            </div>
            ${station.compressor_capacity_mmscfd ? `
              <div>
                <span style="color: #8b949e; font-size: 10px;">Compressor Cap:</span><br/>
                <strong style="color: #ffffff;">${station.compressor_capacity_mmscfd} MMSCFD</strong>
              </div>
            ` : ''}
            ${station.water_handling_bwpd ? `
              <div>
                <span style="color: #8b949e; font-size: 10px;">Effluent Treatment:</span><br/>
                <strong style="color: #ffffff;">${station.water_handling_bwpd.toLocaleString()} BWPD</strong>
              </div>
            ` : ''}
          </div>
          ${station.serviced_wells ? `
            <div style="margin-top: 8px; border-top: 1px solid #30363d; padding-top: 6px;">
              <span style="color: #8b949e; font-size: 10px;">Serviced Production Wells:</span><br/>
              <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                ${station.serviced_wells.map((wId) => `
                  <span style="font-family: monospace; font-size: 9px; padding: 1px 4px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 3px;">${wId}</span>
                `).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      `;

      facilityMarker.bindPopup(stationPopup);
      infraGroup.addLayer(facilityMarker);
    });
  }, [infrastructure, showFlowlines, wells, selectedWellId]);

  const selectedWell = wells.find((w) => w.id === selectedWellId);

  return (
    <div className={isFullscreen ? "fixed inset-0 z-[1000] w-screen h-screen bg-background flex flex-col" : "relative w-full h-full"}>
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Fullscreen Floating Header Banner (HUD) */}
      {isFullscreen && (
        <div className="absolute top-3 left-3 z-[400] flex items-center gap-3 bg-surface/95 backdrop-blur-md border border-border px-4 py-2 rounded-lg shadow-2xl font-mono text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-bold text-white tracking-wide">GELEKI FIELD GIS • FULLSCREEN</span>
          </div>
          <span className="text-border">|</span>
          <span className="text-textMuted text-[11px]">
            Press <kbd className="px-1.5 py-0.5 bg-[#0d1117] border border-border rounded text-white text-[10px]">ESC</kbd> to return
          </span>
          {selectedWell && (
            <>
              <span className="text-border">|</span>
              <div className="flex items-center gap-1.5">
                <span className="text-textMuted">Inspecting:</span>
                <span className="text-accent font-bold">{selectedWell.name} ({selectedWell.id})</span>
                <span className="text-emerald-400 font-semibold">• {selectedWell.current_metrics.oil_bopd} BOPD</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* Layer Style & Flowline Controls */}
      <div className="absolute top-3 right-3 z-[400] flex items-center gap-1.5 bg-surface/90 backdrop-blur-md border border-border p-1 rounded-lg shadow-xl font-mono text-xs">
        <button
          onClick={() => setShowFlowlines(!showFlowlines)}
          title="Toggle Geleki Field Flowline Network & GGS Gathering Stations"
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
            showFlowlines
              ? 'bg-emerald-600 text-white font-bold shadow-sm'
              : 'text-textMuted hover:text-white'
          }`}
        >
          <Network className="w-3.5 h-3.5" /> Flowlines
        </button>

        <span className="text-border">|</span>

        <button
          onClick={() => setMapStyle('satellite')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
            mapStyle === 'satellite'
              ? 'bg-blue-600 text-white font-bold shadow-sm'
              : 'text-textMuted hover:text-white'
          }`}
        >
          <Globe className="w-3.5 h-3.5" /> Satellite
        </button>
        <button
          onClick={() => setMapStyle('dark')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
            mapStyle === 'dark'
              ? 'bg-blue-600 text-white font-bold shadow-sm'
              : 'text-textMuted hover:text-white'
          }`}
        >
          <Layers className="w-3.5 h-3.5" /> SCADA
        </button>

        <span className="text-border">|</span>

        {/* Fullscreen Map Toggle */}
        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          title={isFullscreen ? 'Exit full screen view (ESC)' : 'Expand map to full screen view'}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
            isFullscreen
              ? 'bg-accent hover:bg-accent/80 text-white font-bold shadow-sm'
              : 'text-textMuted hover:text-white'
          }`}
        >
          {isFullscreen ? (
            <>
              <Minimize2 className="w-3.5 h-3.5" /> Normal View
            </>
          ) : (
            <>
              <Maximize2 className="w-3.5 h-3.5" /> Fullscreen
            </>
          )}
        </button>
      </div>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-4 left-4 z-[400] bg-surface/90 backdrop-blur-md border border-border px-3 py-2.5 rounded-lg text-xs font-mono shadow-xl max-w-xs">
        <div className="text-[10px] text-textMuted uppercase font-bold tracking-wider mb-2">
          Geleki Production & Infrastructure
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-healthy border border-surface"></span>
            <span className="text-textMain text-[11px]">Healthy Producing Well</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-warning border border-surface"></span>
            <span className="text-textMain text-[11px]">Needs Attention (Wax / Water Cut)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-critical border border-surface animate-pulse"></span>
            <span className="text-textMain text-[11px]">Critical / Tripped</span>
          </div>
          <div className="border-t border-border/80 my-0.5"></div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded bg-amber-500 border border-amber-300"></span>
            <span className="text-textMain text-[11px]">Gas Gathering Station (GGS)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded bg-cyan-500 border border-cyan-300"></span>
            <span className="text-textMain text-[11px]">Central Desalting Plant (CDP)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 h-0.5 border-t border-dashed border-sky-400"></span>
            <span className="text-textMain text-[11px]">Well Flowlines & Headers</span>
          </div>
        </div>
      </div>
    </div>
  );
};

