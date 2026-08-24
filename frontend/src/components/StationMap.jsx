import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { Link } from 'react-router-dom';
import StatusBadge from './StatusBadge';
import { Radio, ArrowUpRight } from 'lucide-react';

export default function StationMap({ stations = [], selectedStation = null, height = '450px' }) {
  // Center of India
  const defaultCenter = [21.0, 78.5];
  const defaultZoom = 4;

  const getColor = (health) => {
    if (health >= 70) return '#22c55e'; // healthy green
    if (health >= 40) return '#f59e0b'; // degraded amber
    return '#ef4444'; // critical red
  };

  return (
    <div style={{ height, width: '100%' }} className="relative rounded-xl overflow-hidden border border-slate-800 shadow-xl bg-slate-950">
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%' }}
      >
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
            <CircleMarker
              key={stn.id}
              center={[lat, lon]}
              radius={hasAlerts ? 10 : 8}
              pathOptions={{
                fillColor: color,
                fillOpacity: 0.85,
                color: hasAlerts ? '#ffffff' : color,
                weight: hasAlerts ? 2.5 : 1.5,
              }}
            >
              <Popup className="custom-leaflet-popup">
                <div className="p-2 min-w-[200px] text-slate-900 font-sans">
                  <div className="flex items-center justify-between border-b pb-1.5 mb-2">
                    <span className="font-bold text-sm text-slate-900">{stn.name}</span>
                    <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 bg-slate-100 rounded text-slate-700">
                      {stn.station_code}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs text-slate-600 mb-3">
                    <div className="flex justify-between">
                      <span>Location:</span>
                      <span className="font-medium text-slate-800">{stn.district}, {stn.state}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Health Index:</span>
                      <span className="font-bold" style={{ color }}>{stn.overall_health}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Active Alerts:</span>
                      <span className={`font-semibold ${hasAlerts ? 'text-red-600' : 'text-slate-700'}`}>
                        {stn.active_alerts || 0}
                      </span>
                    </div>
                  </div>
                  <Link
                    to={`/stations/${stn.id}`}
                    className="inline-flex items-center justify-center w-full py-1.5 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold transition-colors"
                  >
                    <span>View Telemetry & Health</span>
                    <ArrowUpRight className="h-3.5 w-3.5 ml-1" />
                  </Link>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
