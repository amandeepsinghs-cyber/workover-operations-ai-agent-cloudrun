import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { WellSummary, FieldInfrastructure, GatheringStation } from '../../types/well';
import { Globe, Layers, Network, Building2, Maximize2, Minimize2, X } from 'lucide-react';
import {
  assetApi,
  FieldFilter,
  WellMapData,
  GeoJSONFeature,
  HealthBucket,
  MapPoint,
  BUCKET_COLORS,
} from '../../api/asset';
import { t } from '../../i18n/strings';

/** Stage Y: at or below this zoom the map shows one marker per GGS cluster (BDD-F17-S03). */
const CLUSTER_MAX_ZOOM = 11;
const HEALTH_BUCKETS: HealthBucket[] = ['PRODUCING_OK', 'AT_RISK', 'UNDERPERFORMING', 'NOT_PRODUCING'];

interface WellMapProps {
  wells: WellSummary[];
  selectedWellId: string | null;
  onSelectWell: (wellId: string) => void;
  /** Stage T: field filter ('ALL' = whole asset). Defaults to 'ALL'. */
  field?: FieldFilter;
  /** Stage Y: open the well deep-dive drawer (TC-029 profile) from a map popup. */
  onOpenWell?: (wellId: string) => void;
  /** Reports map full-screen on/off so the app can dock the agent beside it. */
  onFullscreenChange?: (fullscreen: boolean) => void;
  /** Right inset (CSS length) kept free in full-screen, e.g. the docked agent column width. */
  fullscreenRightInset?: string;
}

/** Central processing facility (CDP / CTF) — uses facility_master `type` when present. */
const isCentralFacility = (s: GatheringStation): boolean =>
  (s as GatheringStation & { type?: string }).type === 'CDP' || s.id.startsWith('CDP');

export const WellMap: React.FC<WellMapProps> = ({
  wells,
  selectedWellId,
  onSelectWell,
  field = 'ALL',
  onOpenWell,
  onFullscreenChange,
  fullscreenRightInset,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const infraLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const boundaryLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const markersRef = useRef<{ [id: string]: L.Marker }>({});
  const clusterMarkersRef = useRef<L.Marker[]>([]);
  const lastPannedRef = useRef<string | null>(null);
  const [mapStyle, setMapStyle] = useState<'satellite' | 'dark'>('satellite');
  const [showFlowlines, setShowFlowlines] = useState<boolean>(true);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [legendOpen, setLegendOpen] = useState<boolean>(true);
  const [infrastructure, setInfrastructure] = useState<FieldInfrastructure | null>(null);
  const [mapData, setMapData] = useState<WellMapData | null>(null);
  const [zoom, setZoom] = useState<number>(10);
  const fieldLabel = field === 'ALL' ? 'Assam Asset' : field;
  // Stage Y: TC-020 bucket + cluster per well from /api/fields/map (same source as the KPI header counts)
  const bucketById = useMemo(() => {
    const m: Record<string, MapPoint> = {};
    (mapData?.points || []).forEach((p) => {
      m[p.well_id] = p;
    });
    return m;
  }, [mapData]);
  const clusterMode = zoom <= CLUSTER_MAX_ZOOM && wells.length > 1;
  const healthCounts = useMemo(() => {
    const c: Record<HealthBucket, number> = { PRODUCING_OK: 0, AT_RISK: 0, UNDERPERFORMING: 0, NOT_PRODUCING: 0 };
    HEALTH_BUCKETS.forEach((b) => {
      c[b] = Number(mapData?.counts_by_color?.[b] ?? 0);
    });
    return c;
  }, [mapData]);
  const isSynthetic = (mapData?.boundaries || []).some((b) => b.is_synthetic_geometry !== false);

  // Resize Leaflet Map when toggling Fullscreen
  useEffect(() => {
    const timer = setTimeout(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [isFullscreen]);

  // Tell the app when full-screen changes (agent docks beside a full-screen map).
  useEffect(() => {
    onFullscreenChange?.(isFullscreen);
  }, [isFullscreen, onFullscreenChange]);

  // Keep Leaflet tiles correct whenever the container is resized (50/50 split, agent dock, full-screen).
  useEffect(() => {
    const el = mapContainerRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => mapInstanceRef.current?.invalidateSize());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

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

  // Stage T: fetch TC-016 v2 map payload (boundaries, GGS polygons, bbox) for the selected field(s),
  // then the facility network for every field in scope (merged when field = ALL).
  useEffect(() => {
    let cancelled = false;
    assetApi
      .wellMap(field)
      .then((env) => {
        if (cancelled) return;
        const md = env.data;
        setMapData(md);
        const fields = md && md.fields.length ? md.fields : field === 'ALL' ? [] : [field];
        return Promise.all(
          fields.map((f) =>
            fetch(`/api/field/infrastructure?field=${encodeURIComponent(f)}`).then((res) =>
              res.ok ? (res.json() as Promise<FieldInfrastructure>) : null,
            ),
          ),
        ).then((infras) => {
          if (cancelled) return;
          const ok = infras.filter((x): x is FieldInfrastructure => !!x);
          if (!ok.length) {
            setInfrastructure(null);
            return;
          }
          setInfrastructure({
            field_name: ok.map((i) => i.field_name).join(' + '),
            center_coordinates: ok[0].center_coordinates,
            gathering_stations: ok.flatMap((i) => i.gathering_stations),
          });
        });
      })
      .catch((err) => {
        console.warn('Field map / infrastructure fetch failed:', err);
      });
    return () => {
      cancelled = true;
    };
  }, [field]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Initial view; re-fitted to the API bbox once /api/fields/map returns
    const map = L.map(mapContainerRef.current, {
      center: [26.9, 94.7],
      zoom: 10,
      zoomControl: true,
      attributionControl: false,
    });

    const tileGroup = L.layerGroup().addTo(map);
    tileLayerGroupRef.current = tileGroup;

    const boundaryGroup = L.layerGroup().addTo(map);
    boundaryLayerGroupRef.current = boundaryGroup;

    const infraGroup = L.layerGroup().addTo(map);
    infraLayerGroupRef.current = infraGroup;

    mapInstanceRef.current = map;
    setZoom(map.getZoom());
    map.on('zoomend', () => setZoom(map.getZoom()));

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Stage T: field boundaries + GGS cluster polygons (synthetic, data-derived geometry), fit to bbox
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = boundaryLayerGroupRef.current;
    if (!map || !group) return;
    group.clearLayers();
    if (!mapData) return;
    mapData.boundaries.forEach((b) => {
      let gj: unknown = b.geojson;
      if (typeof gj === 'string') {
        try {
          gj = JSON.parse(gj);
        } catch {
          return;
        }
      }
      if (!gj) return;
      const layer = L.geoJSON(gj as GeoJSON.GeoJsonObject, {
        filter: (f) => !f.properties || f.properties.kind !== 'CLUSTER_POLYGON',
        style: { color: '#e6edf3', weight: 2, opacity: 0.8, fillOpacity: 0.03, dashArray: '6 4' },
      });
      layer.bindTooltip(`${b.field} field boundary${b.is_synthetic_geometry ? ' (synthetic)' : ''}`, { sticky: true });
      group.addLayer(layer);
    });
    mapData.cluster_polygons.forEach((f: GeoJSONFeature) => {
      const layer = L.geoJSON(f as unknown as GeoJSON.GeoJsonObject, {
        style: { color: '#f59e0b', weight: 1.5, opacity: 0.9, fillOpacity: 0.07 },
      });
      layer.bindTooltip(`${f.properties.name || f.properties.cluster_id} (${f.properties.field})`, { sticky: true });
      group.addLayer(layer);
    });
    const bb = mapData.bbox;
    if (bb && bb.min_lat != null && bb.max_lat != null && bb.min_lng != null && bb.max_lng != null) {
      map.fitBounds(
        [
          [bb.min_lat, bb.min_lng],
          [bb.max_lat, bb.max_lng],
        ],
        { padding: [24, 24] },
      );
    }
  }, [mapData]);

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
    clusterMarkersRef.current.forEach((m) => m.remove());
    clusterMarkersRef.current = [];

    // Stage Y (BDD-F17-S03): zoomed out → one marker per GGS cluster with counts; expands on zoom / click.
    if (clusterMode) {
      const groups = new Map<string, WellSummary[]>();
      wells.forEach((w) => {
        const cid = bucketById[w.id]?.cluster_id || (w as WellSummary & { cluster_id?: string }).cluster_id || w.field || 'UNASSIGNED';
        if (!groups.has(cid)) groups.set(cid, []);
        groups.get(cid)!.push(w);
      });
      groups.forEach((members, cid) => {
        const lat = members.reduce((s, w) => s + w.coordinates.lat, 0) / members.length;
        const lng = members.reduce((s, w) => s + w.coordinates.lng, 0) / members.length;
        const counts: Record<string, number> = { PRODUCING_OK: 0, AT_RISK: 0, UNDERPERFORMING: 0, NOT_PRODUCING: 0 };
        members.forEach((w) => {
          const b = bucketById[w.id]?.bucket;
          if (b && b in counts) counts[b] += 1;
        });
        let acc = 0;
        const stops = (Object.keys(counts) as HealthBucket[])
          .filter((b) => counts[b] > 0)
          .map((b) => {
            const from = (acc / members.length) * 360;
            acc += counts[b];
            const to = (acc / members.length) * 360;
            return `${BUCKET_COLORS[b]} ${from}deg ${to}deg`;
          });
        const bg = stops.length ? `conic-gradient(${stops.join(', ')})` : '#8b949e';
        const size = Math.min(56, 28 + Math.round(Math.sqrt(members.length) * 2.5));
        const icon = L.divIcon({
          className: 'well-cluster-marker',
          html: `<div data-testid="well-cluster" style="width:${size}px;height:${size}px;border-radius:50%;background:${bg};
                   display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(0,0,0,.8);cursor:pointer;">
                   <div style="width:${size - 12}px;height:${size - 12}px;border-radius:50%;background:rgba(13,17,23,.92);
                     color:#fff;font:700 11px 'JetBrains Mono',monospace;display:flex;align-items:center;justify-content:center;">
                     ${members.length}</div></div>`,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
        });
        const m = L.marker([lat, lng], { icon }).addTo(map);
        const field0 = members[0]?.field || '';
        m.bindTooltip(
          `<b>${cid}</b> (${field0}) — ${members.length} ${t('map.wells')}<br/>` +
            (Object.keys(counts) as HealthBucket[])
              .map((b) => `<span style="color:${BUCKET_COLORS[b]}">●</span> ${t(`map.health.${b}`)}: ${counts[b]}`)
              .join('<br/>') +
            `<br/><i>${t('map.cluster_hint')}</i>`,
          { sticky: true },
        );
        m.on('click', () => {
          const b = L.latLngBounds(members.map((w) => [w.coordinates.lat, w.coordinates.lng] as [number, number]));
          map.fitBounds(b, { padding: [32, 32], maxZoom: CLUSTER_MAX_ZOOM + 2 });
        });
        clusterMarkersRef.current.push(m);
      });
      return;
    }

    wells.forEach((well) => {
      const isSelected = well.id === selectedWellId;

      // Color mapping — Stage Y: TC-020 health bucket from /api/fields/map (same source as the KPI header);
      // legacy status colours only if the map payload has not arrived yet.
      let color = '#2ea043'; // healthy green
      let pulseClass = '';
      let statusText = 'HEALTHY';

      const bucket = bucketById[well.id]?.bucket as HealthBucket | null | undefined;
      if (bucket && BUCKET_COLORS[bucket]) {
        color = BUCKET_COLORS[bucket];
        statusText = t(`map.health.${bucket}`).toUpperCase();
        pulseClass = bucket === 'NOT_PRODUCING' ? 'pin-pulse-critical' : bucket === 'PRODUCING_OK' ? '' : 'pin-pulse-warning';
      } else if (well.status === 'warning') {
        color = '#d29922'; // amber
        pulseClass = 'pin-pulse-warning';
        statusText = 'NEEDS ATTENTION';
      } else if (well.status === 'failed') {
        color = '#f85149'; // critical red
        pulseClass = 'pin-pulse-critical';
        statusText = 'CRITICAL / TRIPPED';
      }

      const size = isSelected ? 32 : 24;
      const wellNumber = well.id.split('-').pop();

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
            ${pulseClass ? `
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
          ${onOpenWell ? `<button data-open-well="${well.id}" style="margin-top: 8px; width: 100%; padding: 3px 6px; border-radius: 4px;
              border: 1px solid #388bfd; color: #58a6ff; background: transparent; font: 600 10px monospace; cursor: pointer;">
              Open well profile (TC-029)</button>` : ''}
        </div>
      `;

      marker.bindPopup(popupHtml);

      marker.on('click', () => {
        onSelectWell(well.id);
      });
      // Stage Y (BDD-F17-S02): popup action opens the deep-dive drawer (values from /api/wells/{id}/profile)
      marker.on('popupopen', (e: L.PopupEvent) => {
        const btn = e.popup.getElement()?.querySelector(`[data-open-well="${well.id}"]`);
        btn?.addEventListener('click', () => onOpenWell?.(well.id), { once: true });
      });

      markersRef.current[well.id] = marker;
    });

    // If the selection changed, pan smoothly to it (not on zoom-driven re-renders)
    if (selectedWellId && markersRef.current[selectedWellId] && lastPannedRef.current !== selectedWellId) {
      const selectedWell = wells.find((w) => w.id === selectedWellId);
      if (selectedWell) {
        lastPannedRef.current = selectedWellId;
        map.panTo([selectedWell.coordinates.lat, selectedWell.coordinates.lng], {
          animate: true,
          duration: 0.6,
        });
      }
    }
  }, [wells, selectedWellId, onSelectWell, onOpenWell, clusterMode, bucketById]);

  // Update Infrastructure and Flowlines Layer
  useEffect(() => {
    const infraGroup = infraLayerGroupRef.current;
    if (!infraGroup) return;

    infraGroup.clearLayers();

    if (!infrastructure || !showFlowlines) return;

    const centralStations = infrastructure.gathering_stations.filter(isCentralFacility);
    const nearestCentral = (s: GatheringStation): GatheringStation | undefined =>
      centralStations.reduce<GatheringStation | undefined>((best, c) => {
        const d = (c.coordinates.lat - s.coordinates.lat) ** 2 + (c.coordinates.lng - s.coordinates.lng) ** 2;
        if (!best) return c;
        const bd = (best.coordinates.lat - s.coordinates.lat) ** 2 + (best.coordinates.lng - s.coordinates.lng) ** 2;
        return d < bd ? c : best;
      }, undefined);

    // 1. Render Trunk Flowlines from GGS stations to their (nearest) central facility (CDP / CTF)
    if (centralStations.length) {
      infrastructure.gathering_stations.forEach((station) => {
        const cdpStation = nearestCentral(station);
        if (!isCentralFacility(station) && cdpStation) {
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
      const isCDP = isCentralFacility(station);
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
    <div
      className={isFullscreen ? "fixed inset-0 z-[1000] h-screen bg-background flex flex-col" : "relative w-full h-full"}
      style={isFullscreen && fullscreenRightInset ? { right: fullscreenRightInset } : undefined}
    >
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Fullscreen Floating Header Banner (HUD) */}
      {isFullscreen && (
        <div className="absolute top-3 left-3 z-[400] flex items-center gap-3 bg-surface/95 backdrop-blur-md border border-border px-4 py-2 rounded-lg shadow-2xl font-mono text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-bold text-white tracking-wide">{fieldLabel.toUpperCase()} GIS • FULLSCREEN</span>
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
          title={`Toggle ${fieldLabel} Flowline Network & GGS Gathering Stations`}
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

      {/* Stage Y (D-3): synthetic geometry label, always visible */}
      {isSynthetic && (
        <div
          data-testid="map-synthetic-label"
          className="absolute bottom-4 right-4 z-[400] bg-amber-950/80 border border-amber-700/60 text-amber-200 px-2 py-1 rounded text-[10px] font-mono shadow-xl"
          title="Field boundaries, GGS polygons and well locations are synthetic (demo data, D-3)"
        >
          ⚠ {t('map.synthetic')}
        </div>
      )}

      {/* Map legend — slim, see-through strip along the bottom; collapsible so it never hides wells */}
      <div
        className={`absolute bottom-3 left-3 z-[400] flex items-center gap-3 flex-wrap rounded-md bg-black/35 backdrop-blur-sm border border-white/10 px-2.5 py-1 text-[10px] font-mono text-white/85 ${
          isSynthetic ? 'max-w-[calc(100%-13rem)]' : 'max-w-[calc(100%-1.5rem)]'
        }`}
      >
        <button
          type="button"
          onClick={() => setLegendOpen((v) => !v)}
          className="text-white/60 hover:text-white uppercase tracking-wider font-bold"
          title={legendOpen ? 'Hide legend' : 'Show legend'}
        >
          {fieldLabel} {legendOpen ? '▾' : '▸'}
        </button>
        {legendOpen && (
          <>
            {/* Stage Y: TC-020 health buckets with counts (same numbers as the KPI header / GET /api/wells/kpis) */}
            <div data-testid="map-health-counts" className="flex items-center gap-2.5">
              {HEALTH_BUCKETS.map((b) => (
                <span key={b} className="flex items-center gap-1" data-bucket={b} title={t(`map.health.${b}`)}>
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: BUCKET_COLORS[b] }}></span>
                  <span className="text-white/70">{t(`map.health.${b}`)}</span>
                  <strong className="text-white">{mapData ? healthCounts[b] : '–'}</strong>
                </span>
              ))}
            </div>
            <span className="text-white/20">|</span>
            <span className="flex items-center gap-1" title="Gas Gathering Station">
              <span className="w-2 h-2 rounded-sm bg-amber-500"></span>GGS
            </span>
            <span className="flex items-center gap-1" title="Central Facility (CDP / CTF)">
              <span className="w-2 h-2 rounded-sm bg-cyan-500"></span>CDP/CTF
            </span>
            <span className="flex items-center gap-1" title="Well flowlines and headers">
              <span className="w-4 border-t border-dashed border-sky-400"></span>Flowlines
            </span>
            {clusterMode && <span className="text-white/50 italic">{t('map.cluster_hint')}</span>}
          </>
        )}
      </div>
    </div>
  );
};

