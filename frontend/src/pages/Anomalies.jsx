import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, ArrowUpRight, Filter, Layers, RefreshCw, Search, Sparkles } from 'lucide-react';
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
    <div className="space-y-6 pb-16">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-amber-400" />
            <h1 className="text-xl font-extrabold text-white tracking-tight font-sans">
              Neural Anomaly Detections & Diagnostics
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-sans">
            Real-time anomaly audit log classified via 3-channel fusion with TreeSHAP explainability.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            id="severityFilter"
            name="severityFilter"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-[#050b1a] border border-cyan-500/20 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 font-mono transition"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical (≥80%)</option>
            <option value="warning">Warning (50-79%)</option>
          </select>

          <select
            id="rootCauseFilter"
            name="rootCauseFilter"
            value={rootCauseFilter}
            onChange={(e) => setRootCauseFilter(e.target.value)}
            className="bg-[#050b1a] border border-cyan-500/20 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 font-mono transition"
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
            className="p-2 rounded-xl bg-[#050b1a] hover:bg-slate-800 text-slate-300 border border-cyan-500/20 hover:border-cyan-400 transition shadow-inner"
          >
            <RefreshCw className={`h-4 w-4 text-cyan-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Anomalies Table */}
      <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl overflow-hidden shadow-2xl relative">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-amber-400 to-transparent" />

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-cyan-500/15 text-[11px] uppercase tracking-wider text-slate-400 font-mono font-bold bg-[#070e24]">
              <tr>
                <th className="py-3.5 px-4">Station Node</th>
                <th className="py-3.5 px-4">Observation Timestamp</th>
                <th className="py-3.5 px-4">Classified Cause</th>
                <th className="py-3.5 px-4">Severity</th>
                <th className="py-3.5 px-4">Fused Anomaly Score</th>
                <th className="py-3.5 px-4">Confidence</th>
                <th className="py-3.5 px-4">Diagnostic Summary</th>
                <th className="py-3.5 px-4 text-right">Deep Analysis</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cyan-500/10 font-mono">
              {anomalies.length > 0 ? (
                anomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-cyan-500/5 transition">
                    <td className="py-3.5 px-4 font-sans font-medium text-white">
                      <div>{anom.station_name || anom.station_code}</div>
                      <span className="text-[10px] text-cyan-400 font-mono">{anom.station_code}</span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-300 text-[11px]">
                      {new Date(anom.observed_at).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 font-sans">
                      <StatusBadge status={anom.root_cause || 'multivariate'} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 font-sans">
                      <StatusBadge status={anom.severity} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 font-black text-cyan-300 text-sm">
                      {(anom.fused_score * 100).toFixed(1)}%
                    </td>
                    <td className="py-3.5 px-4 text-slate-300">
                      {(anom.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="py-3.5 px-4 font-sans text-slate-300 max-w-sm truncate">
                      {anom.explanation || 'Anomaly detected.'}
                    </td>
                    <td className="py-3.5 px-4 text-right font-sans">
                      <Link
                        to={`/anomalies/${anom.id}`}
                        className="inline-flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300 transition"
                      >
                        <span>TreeSHAP Inspector</span>
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="py-14 text-center text-slate-500 font-sans">
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
