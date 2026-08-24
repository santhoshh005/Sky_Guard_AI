import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Cpu,
  FileText,
  Layers,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function AnomalyDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadDetail() {
    try {
      setLoading(true);
      const res = await api.getAnomalyDetail(id);
      setData(res);
    } catch (err) {
      console.error('Failed to load anomaly detail:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetail();
  }, [id]);

  if (loading && !data) {
    return <div className="p-8 text-center text-slate-400">Loading AI diagnostics & SHAP explanation...</div>;
  }

  if (!data) {
    return <div className="p-8 text-center text-red-400">Anomaly detail record not found.</div>;
  }

  const { anomaly, observation, corrected_values } = data;
  const shapData = (anomaly.shap_values?.top_features || []).map((f) => ({
    name: f.feature.replace(/_/g, ' '),
    contribution: Math.abs(f.contribution),
    raw_contribution: f.contribution,
    value: f.value,
  }));

  return (
    <div className="space-y-6 pb-12">
      {/* Header & Badges */}
      <div className="pb-4 border-b border-slate-800">
        <Link
          to="/anomalies"
          className="inline-flex items-center text-xs text-slate-400 hover:text-cyan-400 mb-2 transition"
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back to Anomalies
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">AI Anomaly Diagnostic Breakdown</h1>
            <StatusBadge status={anomaly.root_cause || 'multivariate'} size="lg" />
            <StatusBadge status={anomaly.severity} size="lg" />
          </div>
          <span className="text-xs font-mono text-slate-400">
            Observation ID: {anomaly.id ? anomaly.id.slice(0, 8) : '--'}
          </span>
        </div>
      </div>

      {/* Human-Readable Explanation Card (§5 & §7.3) */}
      <div className="rounded-xl border border-blue-500/30 bg-gradient-to-r from-blue-950/40 via-slate-900/60 to-slate-950 p-5 shadow-lg">
        <div className="flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-cyan-400 mt-0.5 shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-cyan-300 uppercase tracking-wider">AI Root-Cause Diagnostic Summary</h3>
            <p className="text-sm text-slate-200 mt-1 font-medium leading-relaxed">
              {anomaly.explanation || 'Anomaly detected based on combined statistical, spatial, and structural deviations.'}
            </p>
          </div>
        </div>
      </div>

      {/* 3-Channel Fusion Decomposition (§3.4) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">1. Deterministic QC (35%)</span>
          <span className="text-2xl font-bold font-mono text-white mt-1 block">
            {(anomaly.qc_score * 100).toFixed(1)}%
          </span>
          <p className="text-[11px] text-slate-400 mt-1">Physical bounds, frozen & spike checks</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">2. Isolation Forest (30%)</span>
          <span className="text-2xl font-bold font-mono text-cyan-300 mt-1 block">
            {(anomaly.if_score * 100).toFixed(1)}%
          </span>
          <p className="text-[11px] text-slate-400 mt-1">~110-dim multivariate density outlier</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">3. Autoencoder (35%)</span>
          <span className="text-2xl font-bold font-mono text-purple-300 mt-1 block">
            {(anomaly.ae_score * 100).toFixed(1)}%
          </span>
          <p className="text-[11px] text-slate-400 mt-1">14-dim structural reconstruction MSE</p>
        </div>

        <div className="rounded-xl border border-cyan-500/40 bg-cyan-950/30 p-4 shadow">
          <span className="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider block">Fused Score & Confidence</span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-2xl font-bold font-mono text-cyan-300">
              {(anomaly.fused_score * 100).toFixed(1)}%
            </span>
            <span className="text-xs font-mono text-slate-300">
              {(anomaly.confidence * 100).toFixed(0)}% agreement
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">Severity: {anomaly.severity.toUpperCase()}</p>
        </div>
      </div>

      {/* SHAP Feature Contribution Waterfall (§7) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 shadow-xl">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2">
            <Layers className="h-4 w-4 text-cyan-400" />
            <span>SHAP Feature Attribution (TreeExplainer)</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Top feature contributions driving the anomaly classification score.
          </p>

          <div className="h-64 w-full">
            {shapData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  layout="vertical"
                  data={shapData}
                  margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" stroke="#64748b" fontSize={11} />
                  <YAxis type="category" dataKey="name" stroke="#cbd5e1" fontSize={11} width={100} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                    formatter={(val) => [`${(val * 100).toFixed(2)}%`, 'Contribution']}
                  />
                  <Bar dataKey="contribution" fill="#06b6d4" radius={[0, 4, 4, 0]}>
                    {shapData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={index === 0 ? '#ef4444' : index === 1 ? '#f59e0b' : '#06b6d4'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                SHAP feature contributions computed for anomalous samples.
              </div>
            )}
          </div>
        </div>

        {/* Corrected Values vs Raw Telemetry Table (§6) */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 shadow-xl flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>Corrected Value Estimation (§6)</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Estimated physical value replacing faulty reading (raw values preserved).
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="border-b border-slate-800 text-[11px] uppercase text-slate-400 bg-slate-950/40">
                  <tr>
                    <th className="py-2 px-3">Parameter</th>
                    <th className="py-2 px-3">Raw Value</th>
                    <th className="py-2 px-3">AI Corrected</th>
                    <th className="py-2 px-3">Method</th>
                    <th className="py-2 px-3">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {corrected_values && corrected_values.length > 0 ? (
                    corrected_values.map((cv) => (
                      <tr key={cv.parameter} className="hover:bg-slate-800/30">
                        <td className="py-2 px-3 font-sans font-medium text-white capitalize">{cv.parameter}</td>
                        <td className="py-2 px-3 text-red-400">{cv.raw_value !== null ? cv.raw_value : 'NULL'}</td>
                        <td className="py-2 px-3 text-cyan-300 font-bold">
                          {cv.corrected_value !== null ? cv.corrected_value : '--'}
                        </td>
                        <td className="py-2 px-3 text-slate-400 text-[11px]">{cv.correction_method}</td>
                        <td className="py-2 px-3 text-slate-300">
                          {cv.correction_confidence ? `${(cv.correction_confidence * 100).toFixed(0)}%` : '--'}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="5" className="py-4 text-center text-slate-500 font-sans">
                        No correction estimation required for this observation.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
