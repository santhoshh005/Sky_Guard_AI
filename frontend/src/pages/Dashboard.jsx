import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Flame,
  Globe,
  HeartPulse,
  Radio,
  RefreshCw,
  TrendingDown,
  Wrench,
  Zap,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import StationMap from '../components/StationMap';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function Dashboard({ liveAlerts = [], liveAnomalies = [] }) {
  const [summary, setSummary] = useState(null);
  const [stations, setStations] = useState([]);
  const [recentAnomalies, setRecentAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    try {
      setLoading(true);
      const [sumRes, stnRes, anomRes] = await Promise.all([
        api.getDashboardSummary(),
        api.getStations({ limit: 100 }),
        api.getAnomalies({ limit: 8 }),
      ]);
      setSummary(sumRes);
      setStations(stnRes.stations || []);
      setRecentAnomalies(anomRes.anomalies || []);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-6 pb-12">
      {/* Top Bar / Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-slate-800/80">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            <span>National AWS Anomaly Operations Center</span>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-blue-500/20 text-cyan-400 border border-blue-500/30">
              IMD LIVE
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Real-time automatic anomaly detection, multi-channel neural fusion & sensor degradation tracking.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/demo"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-lg shadow-blue-500/20 transition"
          >
            <Zap className="h-3.5 w-3.5" />
            <span>Demo Console</span>
          </Link>
        </div>
      </div>

      {/* KPI Metric Cards (§8.6 & §10.3) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          title="Active Stations"
          value={summary ? `${summary.active_stations}/${summary.total_stations}` : '--'}
          subtitle="Reporting regularly"
          icon={Globe}
          color="blue"
        />
        <StatCard
          title="Anomalies (24h)"
          value={summary ? summary.anomalies_24h : '--'}
          subtitle="AI-detected events"
          icon={AlertTriangle}
          color="amber"
        />
        <StatCard
          title="Critical Alerts"
          value={summary ? summary.critical_alerts : '--'}
          subtitle="Immediate action"
          icon={AlertOctagon}
          color="red"
          alert={summary?.critical_alerts > 0}
        />
        <StatCard
          title="Avg Health Score"
          value={summary ? `${summary.avg_health}%` : '--'}
          subtitle="Sensor reliability"
          icon={HeartPulse}
          color="emerald"
        />
        <StatCard
          title="Maint. Needed"
          value={summary ? summary.stations_needing_maintenance : '--'}
          subtitle="Health score < 40%"
          icon={Wrench}
          color="purple"
        />
        <StatCard
          title="Obs. Ingested (24h)"
          value={summary ? summary.observations_24h.toLocaleString() : '--'}
          subtitle="15-min intervals"
          icon={Activity}
          color="blue"
        />
      </div>

      {/* Main Grid: Interactive Map + Live Alert Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map Section (2 cols on lg) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-white tracking-tight">Geospatial Sensor Health Grid</h2>
              <span className="text-xs text-slate-400 font-mono">({stations.length} Monitored AWS)</span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-slate-300">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Healthy (≥70%)
              </span>
              <span className="flex items-center gap-1 text-slate-300">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Degraded (40-69%)
              </span>
              <span className="flex items-center gap-1 text-slate-300">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500 animate-pulse" /> Critical (&lt;40%)
              </span>
            </div>
          </div>
          <StationMap stations={stations} height="480px" />
        </div>

        {/* Live Alert & Event Feed (1 col on lg) */}
        <div className="flex flex-col h-[520px] rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-md p-4 shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-rose-400 animate-pulse" />
              <h2 className="text-sm font-bold text-white">Live Alert Stream</h2>
            </div>
            <Link to="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center">
              View All <ArrowRight className="h-3 w-3 ml-0.5" />
            </Link>
          </div>

          <div className="flex-1 overflow-y-auto mt-3 space-y-2.5 pr-1">
            {liveAlerts.length > 0 ? (
              liveAlerts.slice(0, 10).map((alert, idx) => (
                <div
                  key={alert.id || idx}
                  className="p-3 rounded-lg border border-slate-800/80 bg-slate-950/70 hover:bg-slate-800/40 transition flex flex-col space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <StatusBadge status={alert.severity} size="sm" />
                    <span className="text-[11px] font-mono text-slate-400">
                      {alert.created_at ? new Date(alert.created_at).toLocaleTimeString() : 'Just now'}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-white">{alert.title}</p>
                  {alert.description && (
                    <p className="text-[11px] text-slate-400 line-clamp-2">{alert.description}</p>
                  )}
                </div>
              ))
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
                <CheckCircle2 className="h-8 w-8 text-emerald-500/40 mb-2" />
                <p className="text-xs font-medium text-slate-400">No active critical alerts</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Telemetry streams running nominal.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Detected Anomalies Timeline */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">Recent ML Anomaly Detections</h2>
            <p className="text-xs text-slate-400">Multi-channel scoring: Quality Checks + Isolation Forest + Autoencoder</p>
          </div>
          <Link to="/anomalies" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center">
            Explore All Anomalies <ArrowRight className="h-3.5 w-3.5 ml-1" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold bg-slate-950/40">
              <tr>
                <th className="py-2.5 px-3">Station</th>
                <th className="py-2.5 px-3">Observed Time</th>
                <th className="py-2.5 px-3">Root Cause</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Fused Score</th>
                <th className="py-2.5 px-3">Confidence</th>
                <th className="py-2.5 px-3">AI Diagnostic Summary</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {recentAnomalies.length > 0 ? (
                recentAnomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3 font-sans font-medium text-white">
                      <div>{anom.station_name || anom.station_code}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{anom.station_code}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-300 text-[11px]">
                      {new Date(anom.observed_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-3 font-sans">
                      <StatusBadge status={anom.root_cause || 'multivariate'} size="sm" />
                    </td>
                    <td className="py-3 px-3 font-sans">
                      <StatusBadge status={anom.severity} size="sm" />
                    </td>
                    <td className="py-3 px-3 font-bold text-cyan-300">
                      {(anom.fused_score * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-3 text-slate-300">
                      {(anom.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 px-3 font-sans text-slate-300 max-w-xs truncate">
                      {anom.explanation || 'Anomaly detected.'}
                    </td>
                    <td className="py-3 px-3 text-right font-sans">
                      <Link
                        to={`/anomalies/${anom.id}`}
                        className="inline-flex items-center text-xs text-blue-400 hover:text-blue-300 font-medium"
                      >
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-slate-500 font-sans">
                    No anomalies recorded yet. Use Demo Center to inject test scenarios.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
