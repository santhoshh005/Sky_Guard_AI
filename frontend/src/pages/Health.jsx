import React, { useEffect, useState } from 'react';
import { HeartPulse, Wrench, ShieldAlert, CheckCircle2, AlertTriangle, ArrowUpRight } from 'lucide-react';
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
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <HeartPulse className="h-6 w-6 text-emerald-400" />
          <span>Sensor Health Scoring & Maintenance Matrix</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Dynamic sensor reliability index [0-100] tracking streak penalties, gradual recovery & calibration drift.
        </p>
      </div>

      {/* Degradation / Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-red-400 uppercase tracking-wider">Maintenance Recommended</span>
            <Wrench className="h-5 w-5 text-red-400" />
          </div>
          <span className="text-3xl font-extrabold font-mono text-white mt-3 block">{needingMaintenance.length}</span>
          <p className="text-xs text-slate-400 mt-1">AWS nodes with reliability index &lt;40%</p>
        </div>

        <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">Degraded Sensors</span>
            <AlertTriangle className="h-5 w-5 text-amber-400" />
          </div>
          <span className="text-3xl font-extrabold font-mono text-white mt-3 block">{degraded.length}</span>
          <p className="text-xs text-slate-400 mt-1">Sensors in recovery / observation window (40-69%)</p>
        </div>

        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Healthy Stations</span>
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          </div>
          <span className="text-3xl font-extrabold font-mono text-white mt-3 block">{healthy.length}</span>
          <p className="text-xs text-slate-400 mt-1">Operating at normal reliability (≥70%)</p>
        </div>
      </div>

      {/* Station Health Overview Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Network Health Status</h2>
          <span className="text-xs text-slate-400 font-mono">{stations.length} Active Nodes</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold bg-slate-950/40">
              <tr>
                <th className="py-3 px-4">Station Name</th>
                <th className="py-3 px-4">Code</th>
                <th className="py-3 px-4">State & District</th>
                <th className="py-3 px-4">Reliability Index</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Active Alerts</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {stations.map((stn) => (
                <tr key={stn.id} className="hover:bg-slate-800/40 transition">
                  <td className="py-3 px-4 font-medium text-white">{stn.name}</td>
                  <td className="py-3 px-4 font-mono text-cyan-400">{stn.station_code}</td>
                  <td className="py-3 px-4 text-slate-300">{stn.district}, {stn.state}</td>
                  <td className="py-3 px-4 font-mono font-bold">
                    <span
                      className={
                        stn.overall_health >= 70
                          ? 'text-emerald-400'
                          : stn.overall_health >= 40
                          ? 'text-amber-400'
                          : 'text-red-400'
                      }
                    >
                      {stn.overall_health}%
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={stn.health_status} size="sm" />
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-300">{stn.active_alerts || 0}</td>
                  <td className="py-3 px-4 text-right">
                    <Link
                      to={`/stations/${stn.id}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300"
                    >
                      <span>Gauges</span>
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
