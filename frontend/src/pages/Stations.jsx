import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Compass, Filter, Globe2, Radio, Search, ShieldCheck, Zap } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function Stations() {
  const [stations, setStations] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  async function loadStations() {
    try {
      setLoading(true);
      const res = await api.getStations({ limit: 100 });
      setStations(res.stations || []);
    } catch (err) {
      console.error('Failed to load stations:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStations();
  }, []);

  const filtered = stations.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.station_code.toLowerCase().includes(search.toLowerCase()) ||
      (s.state && s.state.toLowerCase().includes(search.toLowerCase())) ||
      (s.district && s.district.toLowerCase().includes(search.toLowerCase()));

    const matchesStatus = !statusFilter || s.health_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6 pb-16">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <Globe2 className="h-6 w-6 text-cyan-400" />
            <h1 className="text-xl font-extrabold text-white tracking-tight font-sans">
              Automatic Weather Station (AWS) Fleet
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-sans">
            Surface meteorological telemetry nodes transmitting 7-channel physical weather parameters every 15 minutes.
          </p>
        </div>

        {/* Filter / Search Controls */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              id="stationSearch"
              name="stationSearch"
              type="text"
              placeholder="Search station, state, district..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-[#050b1a] border border-cyan-500/20 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 transition"
            />
          </div>

          <select
            id="stationStatusFilter"
            name="stationStatusFilter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#050b1a] border border-cyan-500/20 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 font-mono transition"
          >
            <option value="">All Health Statuses</option>
            <option value="healthy">Healthy (≥70%)</option>
            <option value="degraded">Degraded (40-69%)</option>
            <option value="maintenance_recommended">Maintenance Required (&lt;40%)</option>
            <option value="sensor_critical">Critical (&lt;15%)</option>
          </select>
        </div>
      </div>

      {/* Stations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filtered.map((stn) => {
          const healthColor =
            stn.overall_health >= 70
              ? 'text-emerald-400'
              : stn.overall_health >= 40
              ? 'text-amber-400'
              : 'text-rose-400';

          const hasAlerts = (stn.active_alerts || 0) > 0;

          return (
            <div
              key={stn.id}
              className="rounded-2xl border border-cyan-500/15 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-xl hover:border-cyan-500/40 hover:shadow-2xl hover:shadow-cyan-500/10 transition-all flex flex-col justify-between group relative overflow-hidden"
            >
              {/* Top Accent Lightbar */}
              <div
                className={`absolute top-0 left-0 right-0 h-[2px] ${
                  stn.overall_health >= 70
                    ? 'bg-gradient-to-r from-transparent via-emerald-400 to-transparent'
                    : stn.overall_health >= 40
                    ? 'bg-gradient-to-r from-transparent via-amber-400 to-transparent'
                    : 'bg-gradient-to-r from-transparent via-rose-500 to-transparent'
                }`}
              />

              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-cyan-300 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                      {stn.station_code}
                    </span>
                    <h3 className="text-base font-bold text-white mt-2 group-hover:text-cyan-300 transition-colors">
                      {stn.name}
                    </h3>
                    <p className="text-xs text-slate-400">{stn.district}, {stn.state}</p>
                  </div>
                  <StatusBadge status={stn.health_status} size="sm" />
                </div>

                {/* Health Progress Bar */}
                <div className="mt-4 space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-slate-400">Sensor Reliability Index</span>
                    <span className={`font-bold ${healthColor}`}>{stn.overall_health}%</span>
                  </div>
                  <div className="h-2 w-full bg-[#050b1a] rounded-full overflow-hidden border border-cyan-500/10 p-0.5">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        stn.overall_health >= 70
                          ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                          : stn.overall_health >= 40
                          ? 'bg-gradient-to-r from-amber-500 to-yellow-400'
                          : 'bg-gradient-to-r from-rose-600 to-red-500 animate-pulse'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(5, stn.overall_health))}%` }}
                    />
                  </div>
                </div>

                {/* Geographical & Technical Specs */}
                <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] font-mono bg-[#050b1a]/80 p-3 rounded-xl border border-cyan-500/10 text-slate-300">
                  <div>
                    <span className="text-slate-500 font-sans block text-[10px]">COORDINATES</span>
                    {stn.latitude.toFixed(3)}°N, {stn.longitude.toFixed(3)}°E
                  </div>
                  <div>
                    <span className="text-slate-500 font-sans block text-[10px]">ELEVATION</span>
                    {stn.elevation_m ? `${stn.elevation_m}m ASL` : 'Mean Sea Level'}
                  </div>
                </div>
              </div>

              {/* Action Footer */}
              <div className="mt-5 pt-3 border-t border-cyan-500/10 flex items-center justify-between">
                <div className="flex items-center text-xs font-mono text-slate-400">
                  <Radio className={`h-3.5 w-3.5 mr-1.5 ${hasAlerts ? 'text-rose-400 animate-pulse' : 'text-slate-500'}`} />
                  <span className={hasAlerts ? 'text-rose-400 font-bold' : ''}>
                    {stn.active_alerts || 0} active faults
                  </span>
                </div>
                <Link
                  to={`/stations/${stn.id}`}
                  className="inline-flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300 transition group-hover:translate-x-0.5"
                >
                  <span>Telemetry Lab</span>
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
