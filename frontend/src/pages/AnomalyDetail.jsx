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
  Layers,
  ShieldAlert,
  Sparkles,
  Zap,
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
    return (
      <div className="p-12 text-center text-slate-400 font-mono text-sm">
        <Sparkles className="h-6 w-6 text-cyan-400 animate-spin mx-auto mb-2" />
        Extracting TreeSHAP Feature Attribution & Neural Weights...
      </div>
    );
  }

  if (!data) {
    return <div className="p-8 text-center text-rose-400 font-mono">Anomaly diagnostic record not found.</div>;
  }

  const { anomaly, observation, corrected_values } = data;
  const shapData = (anomaly.shap_values?.top_features || []).map((f) => ({
    name: f.feature.replace(/_/g, ' '),
    contribution: Math.abs(f.contribution),
    raw_contribution: f.contribution,
    value: f.value,
  }));

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header & Badges */}
      <div className="p-5 rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

        <Link
          to="/anomalies"
          className="inline-flex items-center text-xs text-slate-400 hover:text-cyan-400 mb-2 transition font-mono"
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> &larr; Return to Detections Ledger
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-black text-white tracking-tight">AI Neural Diagnostic Inspector</h1>
            <StatusBadge status={anomaly.root_cause || 'multivariate'} size="lg" />
            <StatusBadge status={anomaly.severity} size="lg" />
          </div>
          <span className="text-xs font-mono font-bold text-cyan-400 bg-[#050b1a] px-3 py-1 rounded-lg border border-cyan-500/30">
            Observation ID: {anomaly.id ? anomaly.id.slice(0, 8) : '--'}
          </span>
        </div>
      </div>

      {/* 2. Human-Readable AI Diagnostic Summary */}
      <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-[#08122c]/90 to-[#050b1a] p-5 shadow-2xl relative overflow-hidden">
        <div className="flex items-start gap-3.5">
          <div className="rounded-xl p-2.5 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 shrink-0">
            <Sparkles className="h-6 w-6 animate-pulse" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-widest font-mono">
              AI Root-Cause Diagnostic Report (§5 & §7.3)
            </h3>
            <p className="text-sm sm:text-base text-slate-100 mt-1 font-medium leading-relaxed font-sans">
              {anomaly.explanation || 'Anomaly detected based on combined statistical, spatial, and structural deviations.'}
            </p>
          </div>
        </div>
      </div>

      {/* 3. 3-Channel Fusion Decomposition */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-cyan-500/15 bg-[#08122c]/75 backdrop-blur-xl p-4 shadow-xl">
          <span className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
            1. Deterministic QC (35%)
          </span>
          <span className="text-3xl font-black font-mono text-white mt-1.5 block">
            {(anomaly.qc_score * 100).toFixed(1)}%
          </span>
          <p className="text-[11px] text-slate-400 mt-1">Physical range bounds, frozen & spike deviation</p>
        </div>

        <div className="rounded-2xl border border-cyan-500/15 bg-[#08122c]/75 backdrop-blur-xl p-4 shadow-xl">
          <span className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
            2. Isolation Forest (30%)
          </span>
          <span className="text-3xl font-black font-mono text-cyan-300 mt-1.5 block">
            {(anomaly.if_score * 100).toFixed(1)}%
          </span>
          <p className="text-[11px] text-slate-400 mt-1">~110-dim multivariate density outlier</p>
        </div>

        <div className="rounded-2xl border border-cyan-500/15 bg-[#08122c]/75 backdrop-blur-xl p-4 shadow-xl">
          <span className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
            3. Deep Autoencoder (35%)
          </span>
          <span className="text-3xl font-black font-mono text-purple-300 mt-1.5 block">
            {(anomaly.ae_score * 100).toFixed(1)}%
          </span>
          <p className="text-[11px] text-slate-400 mt-1">14-dim structural reconstruction MSE</p>
        </div>

        <div className="rounded-2xl border border-cyan-400/40 bg-gradient-to-br from-cyan-950/40 to-[#08122c] p-4 shadow-xl shadow-cyan-500/10">
          <span className="text-[11px] font-mono font-bold text-cyan-300 uppercase tracking-wider block">
            Fused Score & Confidence
          </span>
          <div className="flex items-baseline justify-between mt-1.5">
            <span className="text-3xl font-black font-mono text-cyan-300">
              {(anomaly.fused_score * 100).toFixed(1)}%
            </span>
            <span className="text-xs font-mono font-bold text-emerald-400">
              {(anomaly.confidence * 100).toFixed(0)}% agreement
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1 font-mono">Severity: {anomaly.severity.toUpperCase()}</p>
        </div>
      </div>

      {/* 4. TreeSHAP Attribution & Value Correction */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SHAP Waterfall Chart */}
        <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

          <h3 className="text-sm font-bold uppercase tracking-wider text-white mb-1 flex items-center gap-2 font-mono">
            <Layers className="h-4 w-4 text-cyan-400" />
            <span>TreeSHAP Feature Attribution Waterfall</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4 font-mono">
            Top feature contributions driving the neural classification score.
          </p>

          <div className="h-72 w-full">
            {shapData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={shapData} margin={{ top: 5, right: 20, left: 30, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" stroke="#64748b" fontSize={11} fontFamily="JetBrains Mono" />
                  <YAxis type="category" dataKey="name" stroke="#cbd5e1" fontSize={11} width={110} fontFamily="JetBrains Mono" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#070e24',
                      borderColor: 'rgba(0,240,255,0.3)',
                      borderRadius: '0.75rem',
                      fontFamily: 'JetBrains Mono',
                      fontSize: '12px',
                    }}
                    formatter={(val) => [`${(val * 100).toFixed(2)}%`, 'Weight Contribution']}
                  />
                  <Bar dataKey="contribution" fill="#00f0ff" radius={[0, 4, 4, 0]}>
                    {shapData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={index === 0 ? '#ff0055' : index === 1 ? '#ffb800' : '#00f0ff'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                TreeSHAP feature contributions computed for anomalous samples.
              </div>
            )}
          </div>
        </div>

        {/* Corrected Physical Values Table */}
        <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-2xl flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent" />

          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-white mb-1 flex items-center gap-2 font-mono">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>Telemetry Value Estimation (§6)</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4 font-mono">
              Estimated physical value replacing faulty reading (raw values preserved).
            </p>

            <div className="overflow-x-auto rounded-xl border border-cyan-500/10 bg-[#050b1a]">
              <table className="w-full text-left text-xs font-mono">
                <thead className="border-b border-cyan-500/15 text-[11px] uppercase text-slate-400 bg-[#070e24]">
                  <tr>
                    <th className="py-2.5 px-3">Parameter</th>
                    <th className="py-2.5 px-3">Raw Value</th>
                    <th className="py-2.5 px-3">AI Corrected</th>
                    <th className="py-2.5 px-3">Method</th>
                    <th className="py-2.5 px-3">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyan-500/10">
                  {corrected_values && corrected_values.length > 0 ? (
                    corrected_values.map((cv) => (
                      <tr key={cv.parameter} className="hover:bg-cyan-500/5">
                        <td className="py-2.5 px-3 font-sans font-bold text-white capitalize">{cv.parameter}</td>
                        <td className="py-2.5 px-3 text-rose-400 font-bold">
                          {cv.raw_value !== null ? cv.raw_value : 'NULL'}
                        </td>
                        <td className="py-2.5 px-3 text-cyan-300 font-black">
                          {cv.corrected_value !== null ? cv.corrected_value : '--'}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 text-[11px]">{cv.correction_method}</td>
                        <td className="py-2.5 px-3 text-emerald-400 font-bold">
                          {cv.correction_confidence ? `${(cv.correction_confidence * 100).toFixed(0)}%` : '--'}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="5" className="py-6 text-center text-slate-500 font-sans">
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
