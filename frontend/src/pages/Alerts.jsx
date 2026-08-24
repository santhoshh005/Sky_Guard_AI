import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Filter, Radio, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [severityFilter, setSeverityFilter] = useState('');
  const [resolvedFilter, setResolvedFilter] = useState('false');
  const [loading, setLoading] = useState(true);

  async function loadAlerts() {
    try {
      setLoading(true);
      const params = { limit: 50 };
      if (severityFilter) params.severity = severityFilter;
      if (resolvedFilter !== '') params.is_resolved = resolvedFilter === 'true';
      const res = await api.getAlerts(params);
      setAlerts(res.alerts || []);
    } catch (err) {
      console.error('Failed to load alerts:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAlerts();
  }, [severityFilter, resolvedFilter]);

  async function handleResolve(alertId) {
    try {
      await api.resolveAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_resolved: true, resolved_at: new Date().toISOString() } : a))
      );
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  }

  return (
    <div className="space-y-6 pb-16">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="h-6 w-6 text-rose-400 animate-pulse" />
            <h1 className="text-xl font-extrabold text-white tracking-tight font-sans">
              Incident Response & Alert Terminal
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-sans">
            Real-time AWS sensor anomalies, health degradation alerts, and maintenance tickets.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={resolvedFilter}
            onChange={(e) => setResolvedFilter(e.target.value)}
            className="bg-[#050b1a] border border-cyan-500/20 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 font-mono transition"
          >
            <option value="false">Active / Open Incidents</option>
            <option value="true">Resolved Incidents</option>
            <option value="">All Incidents</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-[#050b1a] border border-cyan-500/20 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 font-mono transition"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          <button
            onClick={loadAlerts}
            className="p-2 rounded-xl bg-[#050b1a] hover:bg-slate-800 text-slate-300 border border-cyan-500/20 hover:border-cyan-400 transition shadow-inner"
          >
            <RefreshCw className={`h-4 w-4 text-cyan-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl overflow-hidden shadow-2xl relative">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-rose-500 to-transparent" />

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-cyan-500/15 text-[11px] uppercase tracking-wider text-slate-400 font-mono font-bold bg-[#070e24]">
              <tr>
                <th className="py-3.5 px-4">Severity</th>
                <th className="py-3.5 px-4">Station Node</th>
                <th className="py-3.5 px-4">Incident Headline</th>
                <th className="py-3.5 px-4">Sensor Channel</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4 text-right">Triage Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cyan-500/10 font-sans">
              {alerts.length > 0 ? (
                alerts.map((al) => (
                  <tr key={al.id} className="hover:bg-cyan-500/5 transition">
                    <td className="py-3.5 px-4">
                      <StatusBadge status={al.severity} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 font-medium text-white">
                      <div>{al.station_name || al.station_code}</div>
                      <span className="text-[10px] text-cyan-400 font-mono">{al.station_code}</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="font-bold text-slate-200">{al.title}</p>
                      {al.description && (
                        <p className="text-[11px] text-slate-400 mt-0.5 max-w-md leading-relaxed">
                          {al.description}
                        </p>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono uppercase text-slate-300 font-bold">
                      {al.parameter || 'Station Level'}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-400 text-[11px]">
                      {new Date(al.created_at).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4">
                      {al.is_resolved ? (
                        <span className="inline-flex items-center text-emerald-400 text-xs font-mono font-bold">
                          <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Resolved
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-amber-400 text-xs font-mono font-bold animate-pulse">
                          <AlertCircle className="h-3.5 w-3.5 mr-1" /> Open
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {!al.is_resolved ? (
                        <button
                          onClick={() => handleResolve(al.id)}
                          className="px-3.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-lg text-xs font-bold font-mono shadow-md shadow-emerald-500/20 transition-all hover:scale-105"
                        >
                          Resolve & Close
                        </button>
                      ) : (
                        <span className="text-slate-500 text-[11px] font-mono">Acknowledged</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="py-14 text-center text-slate-500 font-sans">
                    No active incident tickets found for selected criteria.
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
