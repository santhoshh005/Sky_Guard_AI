import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowUpRight, Filter, RefreshCw, Search } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function Anomalies() {
  const [anomalies, setAnomalies] = useState([]);
  const [severityFilter, setSeverityFilter] = useState('');
  const [rootCauseFilter, setRootCauseFilter] = useState('');
  const [loading, setLoading] = useState(true);

  async function loadAnomalies() {
    try {
      setLoading(true);
      const params = { limit: 50 };
      if (severityFilter) params.severity = severityFilter;
      if (rootCauseFilter) params.root_cause = rootCauseFilter;
      const res = await api.getAnomalies(params);
      setAnomalies(res.anomalies || []);
    } catch (err) {
      console.error('Failed to load anomalies:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnomalies();
  }, [severityFilter, rootCauseFilter]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-amber-400" />
            <span>AI Anomaly Detections</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time anomaly audit log with root-cause classification & SHAP explainability.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical (≥80%)</option>
            <option value="warning">Warning (50-79%)</option>
          </select>

          <select
            value={rootCauseFilter}
            onChange={(e) => setRootCauseFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Root Causes</option>
            <option value="spike">Spike</option>
            <option value="frozen">Frozen</option>
            <option value="drift">Drift</option>
            <option value="communication">Communication</option>
            <option value="multivariate">Multivariate</option>
          </select>

          <button
            onClick={loadAnomalies}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Anomalies Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold bg-slate-950/60">
              <tr>
                <th className="py-3 px-4">Station</th>
                <th className="py-3 px-4">Observation Timestamp</th>
                <th className="py-3 px-4">Root Cause</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Anomaly Score</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Diagnostic Summary</th>
                <th className="py-3 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {anomalies.length > 0 ? (
                anomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4 font-sans font-medium text-white">
                      <div>{anom.station_name || anom.station_code}</div>
                      <span className="text-[10px] text-slate-500 font-mono">{anom.station_code}</span>
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
                    <td className="py-3 px-4 font-sans text-slate-300 max-w-sm truncate">
                      {anom.explanation || 'Anomaly detected.'}
                    </td>
                    <td className="py-3 px-4 text-right font-sans">
                      <Link
                        to={`/anomalies/${anom.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300"
                      >
                        <span>Explain</span>
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="py-12 text-center text-slate-500 font-sans">
                    No anomalies found matching current criteria.
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
