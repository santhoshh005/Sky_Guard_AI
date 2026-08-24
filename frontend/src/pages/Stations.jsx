import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Filter, Globe2, HeartPulse, Radio, Search, ShieldCheck } from 'lucide-react';
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
    <div className="space-y-6 pb-12">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            <Globe2 className="h-6 w-6 text-cyan-400" />
            <span>Automatic Weather Stations (AWS)</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Network registry of Automatic Weather Stations and surface telemetry nodes.
          </p>
        </div>

        {/* Filter / Search bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search station, state, code..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Health Statuses</option>
            <option value="healthy">Healthy (≥70%)</option>
            <option value="degraded">Degraded (40-69%)</option>
            <option value="maintenance_recommended">Maintenance Needed (&lt;40%)</option>
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
              : 'text-red-400';

          return (
            <div
              key={stn.id}
              className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg flex flex-col justify-between hover:border-slate-700 transition"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/50">
                      {stn.station_code}
                    </span>
                    <h3 className="text-base font-bold text-white mt-2">{stn.name}</h3>
                    <p className="text-xs text-slate-400">{stn.district}, {stn.state}</p>
                  </div>
                  <StatusBadge status={stn.health_status} size="sm" />
                </div>

                {/* Health Bar */}
                <div className="mt-4 space-y-1.5">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-400">Sensor Reliability Index</span>
                    <span className={`font-mono font-bold ${healthColor}`}>{stn.overall_health}%</span>
                  </div>
                  <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        stn.overall_health >= 70
                          ? 'bg-emerald-500'
                          : stn.overall_health >= 40
                          ? 'bg-amber-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(5, stn.overall_health))}%` }}
                    />
                  </div>
                </div>

                {/* Station Metadata */}
                <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] font-mono bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 text-slate-300">
                  <div>
                    <span className="text-slate-500 font-sans block">Coordinates:</span>
                    {stn.latitude.toFixed(3)}°N, {stn.longitude.toFixed(3)}°E
                  </div>
                  <div>
                    <span className="text-slate-500 font-sans block">Elevation:</span>
                    {stn.elevation_m ? `${stn.elevation_m}m ASL` : 'MSL'}
                  </div>
                </div>
              </div>

              {/* Action Footer */}
              <div className="mt-5 pt-3 border-t border-slate-800 flex items-center justify-between">
                <div className="flex items-center text-xs text-slate-400">
                  <Radio className="h-3.5 w-3.5 mr-1.5 text-slate-500" />
                  <span>{stn.active_alerts || 0} active alerts</span>
                </div>
                <Link
                  to={`/stations/${stn.id}`}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition"
                >
                  <span>Sensor Gauges</span>
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
