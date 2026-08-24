import React, { useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Compass, LocateFixed, Radio } from 'lucide-react';
import StatusBadge from './StatusBadge';

// Helper component to programmatically pan map
function MapFlyTo({ center, zoom }) {
  const map = useMap();
  if (center) {
    map.flyTo(center, zoom, { duration: 1.2 });
  }
  return null;
}

export default function StationMap({ stations = [], selectedStation = null, height = '480px' }) {
  const [mapTarget, setMapTarget] = useState({ center: [21.5, 78.9], zoom: 4.5 });

  const getColor = (health) => {
    if (health >= 70) return '#00ff88'; // Neon Emerald
    if (health >= 40) return '#ffb800'; // Solar Amber
    return '#ff0055'; // Laser Crimson
  };

  const focusStation = (lat, lon) => {
    setMapTarget({ center: [lat, lon], zoom: 8 });
  };

  return (
    <div
      style={{ height, width: '100%' }}
      className="relative rounded-2xl overflow-hidden border border-cyan-500/20 shadow-2xl bg-[#060b1e]"
    >
      {/* Top HUD Overlay bar */}
      <div className="absolute top-3 left-3 right-3 z-[1000] flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        <div className="flex items-center gap-2 bg-[#070e24]/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-cyan-500/30 text-xs font-mono pointer-events-auto shadow-lg">
          <Radio className="h-3.5 w-3.5 text-cyan-400 animate-pulse" />
          <span className="text-cyan-300 font-bold">RADAR SWEEP ACTIVE</span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-300">{stations.length} NODES LINKED</span>
        </div>

        {/* Quick Focus station chips */}
        <div className="hidden sm:flex items-center gap-1.5 bg-[#070e24]/90 backdrop-blur-md p-1 rounded-lg border border-cyan-500/30 text-[11px] font-mono pointer-events-auto shadow-lg">
          <button
            onClick={() => setMapTarget({ center: [21.5, 78.9], zoom: 4.5 })}
            className="px-2 py-1 rounded hover:bg-cyan-500/20 text-slate-300 hover:text-cyan-300 transition"
          >
            All India
          </button>
          {stations.slice(0, 4).map((s) => (
            <button
              key={s.id}
              onClick={() => focusStation(s.latitude, s.longitude)}
              className="px-2 py-1 rounded hover:bg-cyan-500/20 text-slate-400 hover:text-cyan-300 transition"
            >
              {s.name.split(' ')[0]}
            </button>
          ))}
        </div>
      </div>

      <MapContainer
        center={mapTarget.center}
        zoom={mapTarget.zoom}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%' }}
      >
        <MapFlyTo center={mapTarget.center} zoom={mapTarget.zoom} />
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {stations.map((stn) => {
          const lat = parseFloat(stn.latitude);
          const lon = parseFloat(stn.longitude);
          if (isNaN(lat) || isNaN(lon)) return null;

          const health = parseFloat(stn.overall_health || 100);
          const color = getColor(health);
          const hasAlerts = (stn.active_alerts || 0) > 0;

          return (
            <React.Fragment key={stn.id}>
              {/* Outer Pulsing Radar Ring */}
              <CircleMarker
                center={[lat, lon]}
                radius={hasAlerts ? 22 : 16}
                pathOptions={{
                  fillColor: color,
                  fillOpacity: 0.12,
                  color: color,
                  weight: 1,
                  dashArray: '3, 6',
                }}
              />

              {/* Core Node Marker */}
              <CircleMarker
                center={[lat, lon]}
                radius={hasAlerts ? 9 : 7}
                pathOptions={{
                  fillColor: color,
                  fillOpacity: 0.95,
                  color: '#ffffff',
                  weight: hasAlerts ? 2.5 : 1.5,
                }}
              >
                <Popup className="custom-leaflet-popup">
                  <div className="p-3 min-w-[220px] text-slate-200 font-sans">
                    <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2 mb-2">
                      <div>
                        <span className="font-bold text-sm text-white block">{stn.name}</span>
                        <span className="text-[10px] font-mono text-cyan-400">{stn.station_code}</span>
                      </div>
                      <StatusBadge status={stn.health_status} size="sm" />
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-300 font-mono mb-3">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Region:</span>
                        <span className="text-white font-sans">{stn.district}, {stn.state}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Reliability:</span>
                        <span className="font-bold" style={{ color }}>{stn.overall_health}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Active Incidents:</span>
                        <span className={hasAlerts ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                          {stn.active_alerts || 0}
                        </span>
                      </div>
                    </div>

                    <Link
                      to={`/stations/${stn.id}`}
                      className="inline-flex items-center justify-center w-full py-1.5 px-3 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white rounded-lg text-xs font-bold shadow-md shadow-cyan-500/20 transition-all"
                    >
                      <span>Open Station Telemetry Lab</span>
                      <ArrowUpRight className="h-3.5 w-3.5 ml-1" />
                    </Link>
                  </div>
                </Popup>
              </CircleMarker>
            </React.Fragment>
          );
        })}
      </MapContainer>
    </div>
  );
}
