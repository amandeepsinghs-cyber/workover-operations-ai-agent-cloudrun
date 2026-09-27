import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { WellSummary } from '../../types/well';
import { Globe, Layers } from 'lucide-react';

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
  const markersRef = useRef<{ [id: string]: L.Marker }>({});
  const [mapStyle, setMapStyle] = useState<'satellite' | 'dark'>('satellite');

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

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Layer Style Switcher (Satellite vs Dark GIS) */}
      <div className="absolute top-3 right-3 z-[400] flex items-center bg-surface/90 backdrop-blur-md border border-border p-1 rounded-lg shadow-xl font-mono text-xs">
        <button
          onClick={() => setMapStyle('satellite')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
            mapStyle === 'satellite'
              ? 'bg-blue-600 text-white font-bold shadow-sm'
              : 'text-textMuted hover:text-white'
          }`}
        >
          <Globe className="w-3.5 h-3.5" /> Satellite Field
        </button>
        <button
          onClick={() => setMapStyle('dark')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
            mapStyle === 'dark'
              ? 'bg-blue-600 text-white font-bold shadow-sm'
              : 'text-textMuted hover:text-white'
          }`}
        >
          <Layers className="w-3.5 h-3.5" /> Dark SCADA
        </button>
      </div>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-4 left-4 z-[400] bg-surface/90 backdrop-blur-md border border-border px-3 py-2 rounded-lg text-xs font-mono shadow-xl">
        <div className="text-[10px] text-textMuted uppercase font-bold tracking-wider mb-1.5">
          Geleki Field Health Legend
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-healthy border border-surface"></span>
            <span className="text-textMain">Healthy / Flowing</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-warning border border-surface"></span>
            <span className="text-textMain">Needs Attention (Wax / Water Cut)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-critical border border-surface animate-pulse"></span>
            <span className="text-textMain">Critical / Tripped</span>
          </div>
        </div>
      </div>
    </div>
  );
};
