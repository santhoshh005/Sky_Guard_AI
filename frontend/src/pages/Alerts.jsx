import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Filter, Radio, RefreshCw, ShieldAlert } from 'lucide-react';
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
    <div className="space-y-6 pb-12">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            <Radio className="h-6 w-6 text-rose-400" />
            <span>Alerts & Incident Management</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time AWS sensor anomalies, health degradation alerts, and maintenance tickets.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={resolvedFilter}
            onChange={(e) => setResolvedFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="false">Active / Unresolved</option>
            <option value="true">Resolved Incidents</option>
            <option value="">All Alerts</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          <button
            onClick={loadAlerts}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold bg-slate-950/60">
              <tr>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Station</th>
                <th className="py-3 px-4">Alert Title</th>
                <th className="py-3 px-4">Sensor / Parameter</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {alerts.length > 0 ? (
                alerts.map((al) => (
                  <tr key={al.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4">
                      <StatusBadge status={al.severity} size="sm" />
                    </td>
                    <td className="py-3 px-4 font-medium text-white">
                      <div>{al.station_name || al.station_code}</div>
                      <span className="text-[10px] text-slate-500 font-mono">{al.station_code}</span>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-semibold text-slate-200">{al.title}</p>
                      {al.description && (
                        <p className="text-[11px] text-slate-400 mt-0.5 max-w-md">{al.description}</p>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono uppercase text-slate-300">
                      {al.parameter || 'Station'}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400 text-[11px]">
                      {new Date(al.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      {al.is_resolved ? (
                        <span className="inline-flex items-center text-emerald-400 text-xs font-semibold">
                          <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Resolved
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-amber-400 text-xs font-semibold">
                          <AlertCircle className="h-3.5 w-3.5 mr-1" /> Active
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {!al.is_resolved ? (
                        <button
                          onClick={() => handleResolve(al.id)}
                          className="px-3 py-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded text-xs font-semibold transition"
                        >
                          Resolve
                        </button>
                      ) : (
                        <span className="text-slate-500 text-[11px] font-mono">Closed</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-500 font-sans">
                    No alerts found for selected criteria.
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
