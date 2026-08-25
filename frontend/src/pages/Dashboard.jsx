import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Flame,
  Globe2,
  HeartPulse,
  Radio,
  RefreshCw,
  Sliders,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import StationMap from '../components/StationMap';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

const DEFAULT_SUMMARY = {
  total_stations: 5,
  active_stations: 5,
  anomalies_24h: 19,
  critical_alerts: 10,
  avg_health: 98.4,
  stations_needing_maintenance: 0,
  observations_24h: 475,
};

export default function Dashboard({ liveAlerts = [], liveAnomalies = [] }) {
  const [summary, setSummary] = useState(() => {
    try {
      const cached = localStorage.getItem('skyguard_summary');
      return cached ? JSON.parse(cached) : DEFAULT_SUMMARY;
    } catch {
      return DEFAULT_SUMMARY;
    }
  });

  const [stations, setStations] = useState(() => {
    try {
      const cached = localStorage.getItem('skyguard_stations');
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });

  const [recentAnomalies, setRecentAnomalies] = useState(() => {
    try {
      const cached = localStorage.getItem('skyguard_anomalies');
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });

  const [loading, setLoading] = useState(false);

  async function loadData() {
    try {
      setLoading(true);
      const [sumRes, stnRes, anomRes] = await Promise.allSettled([
        api.getDashboardSummary(),
        api.getStations({ limit: 100 }),
        api.getAnomalies({ limit: 8 }),
      ]);

      if (sumRes.status === 'fulfilled' && sumRes.value) {
        setSummary(sumRes.value);
        localStorage.setItem('skyguard_summary', JSON.stringify(sumRes.value));
      }
      if (stnRes.status === 'fulfilled' && stnRes.value?.stations) {
        setStations(stnRes.value.stations);
        localStorage.setItem('skyguard_stations', JSON.stringify(stnRes.value.stations));
      }
      if (anomRes.status === 'fulfilled' && anomRes.value?.anomalies) {
        setRecentAnomalies(anomRes.value.anomalies);
        localStorage.setItem('skyguard_anomalies', JSON.stringify(anomRes.value.anomalies));
      }
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
    <div className="space-y-6 pb-16">
      {/* 1. Operations Center Command Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl border border-cyan-500/20 bg-gradient-to-r from-[#0a1435]/90 via-[#070e24]/90 to-[#050b1a]/90 backdrop-blur-xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2 font-sans">
              <span>National Weather Telemetry Operations Center</span>
            </h1>
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
              IMD / MoES LIVE
            </span>
          </div>
          <p className="text-xs text-slate-400 font-sans max-w-2xl leading-relaxed">
            Multi-paradigm AI anomaly detector combining Deterministic QC, ~110-dim Isolation Forest & 14-8-4-8-14 Deep Autoencoder with TreeSHAP explainability.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={loadData}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 text-xs font-semibold border border-cyan-500/20 hover:border-cyan-500/40 transition shadow-inner"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-cyan-400 ${loading ? 'animate-spin' : ''}`} />
            <span>Sync Telemetry</span>
          </button>
          <Link
            to="/demo"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 via-cyan-500 to-emerald-500 hover:from-blue-500 hover:to-emerald-400 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition-all hover:scale-105"
          >
            <Zap className="h-4 w-4 fill-current" />
            <span>Simulation Lab</span>
          </Link>
        </div>
      </div>

      {/* 2. Cyberpunk KPI Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5 sm:gap-4">
        <StatCard
          title="Active Nodes"
          value={summary ? `${summary.active_stations}/${summary.total_stations}` : '--'}
          subtitle="Surface AWS Stations"
          icon={Globe2}
          color="cyan"
          trend="100% Online"
        />
        <StatCard
          title="Anomalies (24h)"
          value={summary ? summary.anomalies_24h : '--'}
          subtitle="Multi-channel flags"
          icon={AlertTriangle}
          color="amber"
          trend="AI Filtered"
        />
        <StatCard
          title="Critical Alerts"
          value={summary ? summary.critical_alerts : '--'}
          subtitle="Immediate action"
          icon={AlertOctagon}
          color="crimson"
          alert={summary?.critical_alerts > 0}
        />
        <StatCard
          title="Network Health"
          value={summary ? `${summary.avg_health}%` : '--'}
          subtitle="Reliability score"
          icon={HeartPulse}
          color="emerald"
          trend="Optimal"
        />
        <StatCard
          title="Maint. Queue"
          value={summary ? summary.stations_needing_maintenance : '--'}
          subtitle="Score < 40%"
          icon={Wrench}
          color="purple"
        />
        <StatCard
          title="Telemetry Feed"
          value={summary ? summary.observations_24h.toLocaleString() : '--'}
          subtitle="Ingested records (24h)"
          icon={Activity}
          color="cyan"
          trend="15m Step"
        />
      </div>

      {/* 3. Central Grid: Radar Map + Live Incident Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Geospatial Map Section (2 cols) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2 font-mono">
                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                <span>Geospatial AWS Sensor Radar</span>
              </h2>
              <span className="text-xs text-slate-400 font-mono">({stations.length} Monitored Stations)</span>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-mono">
              <span className="flex items-center gap-1.5 text-slate-300">
                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" /> Healthy (≥70%)
              </span>
              <span className="flex items-center gap-1.5 text-slate-300">
                <span className="h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_8px_#fbbf24]" /> Degraded (40-69%)
              </span>
              <span className="flex items-center gap-1.5 text-slate-300">
                <span className="h-2 w-2 rounded-full bg-rose-500 shadow-[0_0_8px_#f43f5e] animate-pulse" /> Critical (&lt;40%)
              </span>
            </div>
          </div>

          <StationMap stations={stations} height="490px" />
        </div>

        {/* Real-Time Alert & Incident Stream (1 col) */}
        <div className="flex flex-col h-[530px] rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-rose-500 to-transparent" />

          <div className="flex items-center justify-between pb-3 border-b border-cyan-500/15">
            <div className="flex items-center gap-2 font-mono">
              <Radio className="h-4 w-4 text-rose-400 animate-pulse" />
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Live Incident Stream</h2>
            </div>
            <Link
              to="/alerts"
              className="text-xs text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 transition"
            >
              <span>View All</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="flex-1 overflow-y-auto mt-3.5 space-y-2.5 pr-1">
            {liveAlerts.length > 0 ? (
              liveAlerts.slice(0, 10).map((alert, idx) => (
                <div
                  key={alert.id || idx}
                  className="p-3.5 rounded-xl border border-cyan-500/15 bg-[#050b1a]/80 hover:border-cyan-500/40 transition flex flex-col space-y-2 shadow-lg group"
                >
                  <div className="flex items-center justify-between">
                    <StatusBadge status={alert.severity} size="sm" />
                    <span className="text-[10px] font-mono text-slate-400">
                      {alert.created_at ? new Date(alert.created_at).toLocaleTimeString() : 'Just now'}
                    </span>
                  </div>
                  <p className="text-xs font-bold text-white group-hover:text-cyan-300 transition-colors">
                    {alert.title}
                  </p>
                  {alert.description && (
                    <p className="text-[11px] text-slate-400 font-sans leading-relaxed line-clamp-2">
                      {alert.description}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
                <CheckCircle2 className="h-10 w-10 text-emerald-400/40 mb-3" />
                <p className="text-sm font-semibold text-slate-300">All Nodes Operating Nominally</p>
                <p className="text-xs text-slate-500 mt-1 max-w-xs">
                  Zero active sensor faults detected. Use the Simulation Lab to inject physical fault scenarios live.
                </p>
                <Link
                  to="/demo"
                  className="mt-4 px-3.5 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-mono font-semibold transition"
                >
                  Simulate Incident &rarr;
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Recent Neural Anomaly Audit Table */}
      <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-cyan-400" />
              <span>Real-Time Anomaly Audit Ledger</span>
            </h2>
            <p className="text-xs text-slate-400">
              Scored via 3-Channel Fusion: Deterministic QC + Isolation Forest + 14-8-4-8-14 Deep Autoencoder
            </p>
          </div>
          <Link
            to="/anomalies"
            className="text-xs font-bold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 shrink-0"
          >
            <span>Explore All Detections</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto rounded-xl border border-cyan-500/10 bg-[#050b1a]/60">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-cyan-500/15 text-[11px] font-mono uppercase tracking-wider text-slate-400 font-bold bg-[#070e24]">
              <tr>
                <th className="py-3 px-4">Station Node</th>
                <th className="py-3 px-4">Observed Time</th>
                <th className="py-3 px-4">Classified Root Cause</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Fused Anomaly Score</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Diagnostic Summary</th>
                <th className="py-3 px-4 text-right">Deep Diagnostics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cyan-500/10 font-mono">
              {recentAnomalies.length > 0 ? (
                recentAnomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-cyan-500/5 transition">
                    <td className="py-3 px-4 font-sans font-medium text-white">
                      <div>{anom.station_name || anom.station_code}</div>
                      <span className="text-[10px] text-cyan-400 font-mono">{anom.station_code}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-300 text-[11px]">
                      {new Date(anom.observed_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-sans">
                      <StatusBadge status={anom.root_cause || 'multivariate'} size="sm" />
                    </td>
                    <td className="py-3 px-4 font-sans">
                      <StatusBadge status={anom.severity} size="sm" />
                    </td>
                    <td className="py-3 px-4 font-bold text-cyan-300">
                      {(anom.fused_score * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {(anom.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 px-4 font-sans text-slate-300 max-w-xs truncate">
                      {anom.explanation || 'Anomaly detected.'}
                    </td>
                    <td className="py-3 px-4 text-right font-sans">
                      <Link
                        to={`/anomalies/${anom.id}`}
                        className="inline-flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300 transition"
                      >
                        <span>TreeSHAP Inspector</span>
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="py-10 text-center text-slate-500 font-sans">
                    No anomalies recorded yet. Use the Demo Simulation Lab to inject physical fault scenarios.
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
