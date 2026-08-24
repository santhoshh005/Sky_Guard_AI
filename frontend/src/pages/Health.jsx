import React, { useEffect, useState } from 'react';
import { HeartPulse, Wrench, ShieldAlert, CheckCircle2, AlertTriangle, ArrowUpRight, Cpu } from 'lucide-react';
import { Link } from 'react-router-dom';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function Health() {
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);

  async function loadHealth() {
    try {
      setLoading(true);
      const res = await api.getStations({ limit: 100 });
      setStations(res.stations || []);
    } catch (err) {
      console.error('Failed to load stations health:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHealth();
  }, []);

  const needingMaintenance = stations.filter((s) => s.overall_health < 40);
  const degraded = stations.filter((s) => s.overall_health >= 40 && s.overall_health < 70);
  const healthy = stations.filter((s) => s.overall_health >= 70);

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header */}
      <div className="p-5 rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl shadow-xl">
        <div className="flex items-center gap-2">
          <HeartPulse className="h-6 w-6 text-emerald-400" />
          <h1 className="text-xl font-extrabold text-white tracking-tight font-sans">
            Sensor Health Matrix & Reliability Index
          </h1>
        </div>
        <p className="text-xs text-slate-400 mt-1 font-sans">
          Dynamic per-channel reliability index [0-100] tracking streak penalties, gradual recovery dynamics & calibration drift.
        </p>
      </div>

      {/* 2. Degradation & Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="rounded-2xl border border-rose-500/30 bg-[#08122c]/80 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-rose-500 to-transparent" />
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-rose-400 uppercase tracking-wider">Maintenance Queue</span>
            <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
              <Wrench className="h-5 w-5" />
            </div>
          </div>
          <span className="text-4xl font-black font-mono text-white mt-3 block">{needingMaintenance.length}</span>
          <p className="text-xs text-slate-400 mt-1">AWS nodes with reliability index &lt;40%</p>
        </div>

        <div className="rounded-2xl border border-amber-500/30 bg-[#08122c]/80 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-amber-400 to-transparent" />
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider">Degraded Sensors</span>
            <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
          </div>
          <span className="text-4xl font-black font-mono text-white mt-3 block">{degraded.length}</span>
          <p className="text-xs text-slate-400 mt-1">Sensors in recovery / monitoring window (40-69%)</p>
        </div>

        <div className="rounded-2xl border border-emerald-500/30 bg-[#08122c]/80 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent" />
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider">Healthy Fleet</span>
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </div>
          <span className="text-4xl font-black font-mono text-white mt-3 block">{healthy.length}</span>
          <p className="text-xs text-slate-400 mt-1">Operating at normal reliability (≥70%)</p>
        </div>
      </div>

      {/* 3. Fleet Health Table */}
      <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl overflow-hidden shadow-2xl relative">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent" />

        <div className="p-4 border-b border-cyan-500/15 flex items-center justify-between bg-[#070e24]">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
            <Cpu className="h-4 w-4 text-cyan-400" />
            <span>Surface AWS Fleet Reliability Matrix</span>
          </h2>
          <span className="text-xs text-slate-400 font-mono">{stations.length} Active Nodes</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-cyan-500/15 text-[11px] uppercase tracking-wider text-slate-400 font-mono font-bold bg-[#050b1a]">
              <tr>
                <th className="py-3.5 px-4">Station Node</th>
                <th className="py-3.5 px-4">Station Code</th>
                <th className="py-3.5 px-4">Geographic Region</th>
                <th className="py-3.5 px-4">Reliability Index</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Active Incidents</th>
                <th className="py-3.5 px-4 text-right">Telemetry Lab</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cyan-500/10 font-sans">
              {stations.map((stn) => (
                <tr key={stn.id} className="hover:bg-cyan-500/5 transition">
                  <td className="py-3.5 px-4 font-bold text-white">{stn.name}</td>
                  <td className="py-3.5 px-4 font-mono text-cyan-400 font-bold">{stn.station_code}</td>
                  <td className="py-3.5 px-4 text-slate-300">{stn.district}, {stn.state}</td>
                  <td className="py-3.5 px-4 font-mono font-black text-sm">
                    <span
                      className={
                        stn.overall_health >= 70
                          ? 'text-emerald-400'
                          : stn.overall_health >= 40
                          ? 'text-amber-400'
                          : 'text-rose-400'
                      }
                    >
                      {stn.overall_health}%
                    </span>
                  </td>
                  <td className="py-3.5 px-4">
                    <StatusBadge status={stn.health_status} size="sm" />
                  </td>
                  <td className="py-3.5 px-4 font-mono text-slate-300 font-bold">{stn.active_alerts || 0}</td>
                  <td className="py-3.5 px-4 text-right">
                    <Link
                      to={`/stations/${stn.id}`}
                      className="inline-flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300 transition"
                    >
                      <span>Sensor Lab</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
