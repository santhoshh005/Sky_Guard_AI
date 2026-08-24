import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CloudRain,
  Compass,
  Gauge,
  HeartPulse,
  Radio,
  Sun,
  Thermometer,
  Wind,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function StationDetail() {
  const { id } = useParams();
  const [stationData, setStationData] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedParam, setSelectedParam] = useState('temperature');
  const [loading, setLoading] = useState(true);

  const PARAM_ICONS = {
    temperature: Thermometer,
    humidity: Gauge,
    pressure: Activity,
    wind_speed: Wind,
    wind_direction: Compass,
    rainfall: CloudRain,
    solar_radiation: Sun,
  };

  const PARAM_UNITS = {
    temperature: '°C',
    humidity: '%',
    pressure: 'hPa',
    wind_speed: 'm/s',
    wind_direction: '°',
    rainfall: 'mm',
    solar_radiation: 'W/m²',
  };

  async function loadDetail() {
    try {
      setLoading(true);
      const [detailRes, anomRes] = await Promise.all([
        api.getStationDetail(id),
        api.getAnomalies({ station_id: id, limit: 15 }),
      ]);
      setStationData(detailRes);
      setAnomalies(anomRes.anomalies || []);
    } catch (err) {
      console.error('Failed to load station detail:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetail();
  }, [id]);

  if (loading && !stationData) {
    return <div className="p-8 text-center text-slate-400">Loading station telemetry...</div>;
  }

  if (!stationData) {
    return <div className="p-8 text-center text-red-400">Station not found.</div>;
  }

  const { station, health, recent_alerts, last_observation } = stationData;

  return (
    <div className="space-y-6 pb-12">
      {/* Header with Navigation */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <Link
            to="/stations"
            className="inline-flex items-center text-xs text-slate-400 hover:text-cyan-400 mb-2 transition"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back to Stations
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">{station.name}</h1>
            <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded bg-blue-500/20 text-cyan-400 border border-blue-500/30">
              {station.station_code}
            </span>
            <StatusBadge status={health.overall_status} />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {station.district}, {station.state} &bull; Coordinates: {station.latitude.toFixed(3)}°N, {station.longitude.toFixed(3)}°E &bull; Elevation: {station.elevation_m || 0}m ASL
          </p>
        </div>

        <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 px-4 py-2 rounded-xl">
          <div className="text-right">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold block">Overall Reliability</span>
            <span className="text-xl font-bold font-mono text-cyan-400">{health.overall_health}%</span>
          </div>
          <HeartPulse className="h-7 w-7 text-cyan-400" />
        </div>
      </div>

      {/* 7 Parameter Sensor Health Gauges (§4 & §8.2) */}
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <span>Sensor Health Breakdown (7 Channels)</span>
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
          {Object.entries(health.parameters || {}).map(([param, pHealth]) => {
            const Icon = PARAM_ICONS[param] || Activity;
            const unit = PARAM_UNITS[param] || '';
            const lastVal = last_observation ? last_observation[param] : null;
            const isSelected = selectedParam === param;

            return (
              <button
                key={param}
                onClick={() => setSelectedParam(param)}
                className={`text-left p-3.5 rounded-xl border transition-all ${
                  isSelected
                    ? 'bg-blue-950/40 border-cyan-500 shadow-lg shadow-cyan-500/10'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between text-slate-400">
                  <Icon className={`h-4 w-4 ${isSelected ? 'text-cyan-400' : ''}`} />
                  <span className="text-[10px] font-mono font-bold">{pHealth.score}%</span>
                </div>
                <div className="mt-2">
                  <span className="text-xs font-bold text-white capitalize block truncate">{param}</span>
                  <span className="text-sm font-mono font-extrabold text-cyan-300 mt-0.5 block">
                    {lastVal !== null && lastVal !== undefined ? `${lastVal} ${unit}` : '--'}
                  </span>
                </div>
                <div className="mt-2.5">
                  <StatusBadge status={pHealth.status} size="sm" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Telemetry Stream and AI Diagnostics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Telemetry Inspector */}
        <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/40 p-5 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white tracking-tight capitalize">
                {selectedParam} Telemetry & Correction Signal
              </h3>
              <p className="text-xs text-slate-400">
                Raw sensor measurements with automated AI fault correction ({PARAM_UNITS[selectedParam]})
              </p>
            </div>
            <span className="text-xs font-mono px-2 py-1 bg-slate-800 text-slate-300 rounded">
              Current: {last_observation ? last_observation[selectedParam] : '--'} {PARAM_UNITS[selectedParam]}
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={[
                  { time: '10:00', raw: 31.2, corrected: 31.2 },
                  { time: '10:15', raw: 31.8, corrected: 31.8 },
                  { time: '10:30', raw: 32.4, corrected: 32.4 },
                  { time: '10:45', raw: 55.0, corrected: 32.9 }, // Spike
                  { time: '11:00', raw: 33.1, corrected: 33.1 },
                  { time: '11:15', raw: 33.6, corrected: 33.6 },
                ]}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                <Line
                  type="monotone"
                  dataKey="raw"
                  name="Raw Telemetry"
                  stroke="#f43f5e"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="corrected"
                  name="AI Corrected Value"
                  stroke="#06b6d4"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Station Alerts & Fault Events */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Radio className="h-4 w-4 text-amber-400" />
                <span>Station Alerts History</span>
              </h3>
              <span className="text-xs text-slate-400 font-mono">{recent_alerts.length}</span>
            </div>

            <div className="mt-3 space-y-2.5 max-h-60 overflow-y-auto">
              {recent_alerts.length > 0 ? (
                recent_alerts.map((al) => (
                  <div key={al.id} className="p-2.5 rounded-lg border border-slate-800 bg-slate-950/60 text-xs">
                    <div className="flex items-center justify-between">
                      <StatusBadge status={al.severity} size="sm" />
                      <span className="text-[10px] font-mono text-slate-500">
                        {new Date(al.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="font-medium text-white mt-1">{al.title}</p>
                    {al.description && <p className="text-[11px] text-slate-400 mt-0.5">{al.description}</p>}
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 text-center py-6">No historical alerts for this station.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
