import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  AreaChart,
  Area,
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
  Cpu,
  Gauge,
  HeartPulse,
  Radio,
  Sparkles,
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
    return (
      <div className="p-12 text-center text-slate-400 font-mono text-sm">
        <Activity className="h-6 w-6 text-cyan-400 animate-spin mx-auto mb-2" />
        Connecting to AWS Telemetry Node...
      </div>
    );
  }

  if (!stationData) {
    return <div className="p-8 text-center text-rose-400 font-mono">Station record not found.</div>;
  }

  const { station, health, recent_alerts, last_observation } = stationData;

  // Mock dual waveform data for selected channel
  const chartData = [
    { time: '10:00', raw: 31.2, corrected: 31.2 },
    { time: '10:15', raw: 31.8, corrected: 31.8 },
    { time: '10:30', raw: 32.4, corrected: 32.4 },
    { time: '10:45', raw: 54.8, corrected: 32.9 }, // Simulated spike
    { time: '11:00', raw: 33.1, corrected: 33.1 },
    { time: '11:15', raw: 33.6, corrected: 33.6 },
    { time: '11:30', raw: 34.0, corrected: 34.0 },
    { time: '11:45', raw: 34.2, corrected: 34.2 },
  ];

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header & Technical HUD */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

        <div>
          <Link
            to="/stations"
            className="inline-flex items-center text-xs text-slate-400 hover:text-cyan-400 mb-2 transition font-mono"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1" /> &larr; Return to Fleet Overview
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">{station.name}</h1>
            <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
              {station.station_code}
            </span>
            <StatusBadge status={health.overall_status} size="md" />
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {station.district}, {station.state} &bull; Geo: {station.latitude.toFixed(3)}°N, {station.longitude.toFixed(3)}°E &bull; Elevation: {station.elevation_m || 0}m ASL &bull; Interval: {station.expected_interval_min}m
          </p>
        </div>

        <div className="flex items-center gap-4 bg-[#050b1a] border border-cyan-500/20 px-5 py-3 rounded-xl shadow-inner">
          <div className="text-right">
            <span className="text-[10px] uppercase tracking-widest text-slate-400 font-mono font-bold block">
              Node Reliability
            </span>
            <span className="text-2xl font-black font-mono text-cyan-300">{health.overall_health}%</span>
          </div>
          <HeartPulse className="h-8 w-8 text-cyan-400 animate-pulse" />
        </div>
      </div>

      {/* 2. 7-Channel Physical Sensor Gauges */}
      <div>
        <div className="flex items-center justify-between mb-3 px-1">
          <h2 className="text-sm font-bold uppercase tracking-wider text-white font-mono flex items-center gap-2">
            <Cpu className="h-4 w-4 text-cyan-400" />
            <span>7-Channel Sensor Telemetry Matrix (Select to Inspect)</span>
          </h2>
          <span className="text-xs text-slate-400 font-mono">Interactive Channel Selector</span>
        </div>

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
                className={`text-left p-3.5 rounded-xl border transition-all duration-200 relative overflow-hidden group ${
                  isSelected
                    ? 'bg-gradient-to-b from-cyan-950/60 to-[#08122c] border-cyan-400 shadow-lg shadow-cyan-500/20 scale-[1.02]'
                    : 'bg-[#08122c]/70 border-cyan-500/15 hover:border-cyan-500/40 hover:bg-[#08122c]'
                }`}
              >
                {isSelected && (
                  <div className="absolute top-0 left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_8px_#00f0ff]" />
                )}

                <div className="flex items-center justify-between text-slate-400">
                  <Icon className={`h-4 w-4 ${isSelected ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span className="text-[10px] font-mono font-bold text-slate-400">{pHealth.score}%</span>
                </div>

                <div className="mt-2.5">
                  <span className="text-xs font-bold text-white capitalize block truncate font-sans">{param}</span>
                  <span className="text-base font-mono font-black text-cyan-300 mt-0.5 block">
                    {lastVal !== null && lastVal !== undefined ? `${lastVal} ${unit}` : '--'}
                  </span>
                </div>

                <div className="mt-3">
                  <StatusBadge status={pHealth.status} size="sm" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Dual-Trace Telemetry Waveform Visualizer & Incident Log */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Waveform Graph (2 cols) */}
        <div className="lg:col-span-2 rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
            <div>
              <h3 className="text-base font-bold text-white tracking-tight capitalize flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-cyan-400" />
                <span>{selectedParam} Dual-Trace Waveform Signal</span>
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                Telemetry trace comparing Raw Telemetry vs Automated AI-Corrected Signal ({PARAM_UNITS[selectedParam]})
              </p>
            </div>
            <span className="text-xs font-mono font-bold px-3 py-1 bg-[#050b1a] text-cyan-300 rounded-lg border border-cyan-500/30 shrink-0">
              Live: {last_observation ? last_observation[selectedParam] : '--'} {PARAM_UNITS[selectedParam]}
            </span>
          </div>

          <div className="h-72 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRaw" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorCorrected" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00f0ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" fontSize={11} fontFamly="JetBrains Mono" />
                <YAxis stroke="#64748b" fontSize={11} fontFamily="JetBrains Mono" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#070e24',
                    borderColor: 'rgba(0,240,255,0.3)',
                    borderRadius: '0.75rem',
                    fontFamily: 'JetBrains Mono',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'JetBrains Mono', paddingTop: '10px' }} />
                <Area
                  type="monotone"
                  dataKey="raw"
                  name="Raw Sensor Telemetry"
                  stroke="#f43f5e"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorRaw)"
                />
                <Line
                  type="monotone"
                  dataKey="corrected"
                  name="AI Corrected Physical Value"
                  stroke="#00f0ff"
                  strokeWidth={2.5}
                  strokeDasharray="4 4"
                  dot={{ r: 4, fill: '#00f0ff' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Station Incident History (1 col) */}
        <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-2xl flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-amber-400 to-transparent" />

          <div>
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/15">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                <Radio className="h-4 w-4 text-amber-400" />
                <span>Station Incident Log</span>
              </h3>
              <span className="text-xs font-mono font-bold text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded">
                {recent_alerts.length} Records
              </span>
            </div>

            <div className="mt-3.5 space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
              {recent_alerts.length > 0 ? (
                recent_alerts.map((al) => (
                  <div key={al.id} className="p-3 rounded-xl border border-cyan-500/10 bg-[#050b1a] text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <StatusBadge status={al.severity} size="sm" />
                      <span className="text-[10px] font-mono text-slate-500">
                        {new Date(al.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="font-bold text-white pt-1">{al.title}</p>
                    {al.description && <p className="text-[11px] text-slate-400 leading-relaxed">{al.description}</p>}
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 text-center py-10 font-mono">
                  All telemetry streams running nominal for this station.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
