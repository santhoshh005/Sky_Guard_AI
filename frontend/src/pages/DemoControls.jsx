import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Flame,
  Globe2,
  Radio,
  Sliders,
  Sparkles,
  Terminal,
  Zap,
} from 'lucide-react';
import { api } from '../services/api';

const SCENARIOS = [
  {
    type: 'spike',
    title: 'Transient Sensor Spike',
    code: 'SPIKE',
    color: 'orange',
    desc: 'Simulates a sudden sharp transient spike (+15°C to +30°C) on selected parameters. Triggers Spike QC check, high IF score & temporal median value correction.',
  },
  {
    type: 'frozen',
    title: 'Frozen / Stuck Sensor',
    code: 'FROZEN',
    color: 'cyan',
    desc: 'Repeats the exact same sensor value for 4+ readings (simulating mechanical ADC freeze). Triggers Frozen QC rule & linear/diurnal trend value estimation.',
  },
  {
    type: 'drift',
    title: 'Sensor Calibration Drift',
    code: 'DRIFT',
    color: 'purple',
    desc: 'Applies progressive baseline drift exceeding 2σ over a 24h time-series window. Triggers high Autoencoder reconstruction MSE and cross-parameter regression correction.',
  },
  {
    type: 'missing',
    title: 'Telemetry Dropout / Missing Data',
    code: 'COMMUNICATION',
    color: 'crimson',
    desc: 'Simulates station transceiver packet loss (null/missing parameters). Triggers station-level communication failure classification & health degradation alert.',
  },
  {
    type: 'multivariate',
    title: 'Multivariate Extreme Coupling',
    code: 'MULTIVARIATE',
    color: 'fuchsia',
    desc: 'Coupled anomaly across temperature, humidity, and pressure simultaneously. Triggers full Autoencoder + Isolation Forest multi-channel detection.',
  },
];

const STATIONS = [
  { id: 'AWS_MUM_001', name: 'Mumbai Colaba', loc: 'Mumbai, Maharashtra' },
  { id: 'AWS_DEL_001', name: 'Delhi Safdarjung', loc: 'New Delhi, Delhi' },
  { id: 'AWS_CHN_001', name: 'Chennai Nungambakkam', loc: 'Chennai, Tamil Nadu' },
  { id: 'AWS_KOL_001', name: 'Kolkata Alipore', loc: 'Kolkata, West Bengal' },
  { id: 'AWS_BLR_001', name: 'Bengaluru HAL', loc: 'Bengaluru, Karnataka' },
];

const PARAMETERS = [
  'temperature',
  'humidity',
  'pressure',
  'wind_speed',
  'wind_direction',
  'rainfall',
  'solar_radiation',
];

export default function DemoControls() {
  const [stationId, setStationId] = useState('AWS_BLR_001');
  const [anomalyType, setAnomalyType] = useState('spike');
  const [selectedParams, setSelectedParams] = useState(['temperature']);
  const [magnitude, setMagnitude] = useState(3.5);
  const [durationMin, setDurationMin] = useState(30);

  const [loading, setLoading] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  function toggleParam(p) {
    if (selectedParams.includes(p)) {
      if (selectedParams.length > 1) {
        setSelectedParams(selectedParams.filter((x) => x !== p));
      }
    } else {
      setSelectedParams([...selectedParams, p]);
    }
  }

  async function handleInject() {
    try {
      setLoading(true);
      setError(null);
      setResult(null);

      const startTime = performance.now();
      const res = await api.injectAnomaly({
        station_id: stationId,
        anomaly_type: anomalyType,
        parameters: selectedParams,
        magnitude: parseFloat(magnitude),
        duration_min: parseInt(durationMin, 10),
      });
      const elapsed = Math.round(performance.now() - startTime);

      setResult({ ...res, latency_ms: elapsed });
    } catch (err) {
      console.error('Injection failed:', err);
      setError(err.message || 'Injection failed. Check server logs.');
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateBaseline() {
    try {
      setGenLoading(true);
      setError(null);
      await api.generateData({
        station_ids: [stationId],
        days: 1,
        interval_min: 15,
      });
      setResult({
        message: `Successfully generated 24h nominal baseline telemetry (96 records) for ${stationId}.`,
        status: 'ok',
      });
    } catch (err) {
      setError(err.message || 'Failed to generate baseline data.');
    } finally {
      setGenLoading(false);
    }
  }

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header */}
      <div className="p-5 rounded-2xl border border-cyan-500/20 bg-gradient-to-r from-blue-950/50 via-[#08122c]/90 to-[#050b1a] backdrop-blur-xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-400 via-emerald-400 to-indigo-500" />

        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
            <Zap className="h-6 w-6 fill-current animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight font-sans">
                Interactive SIH Judge Simulation Center
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                REAL-TIME INJECTION
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 font-sans">
              Trigger live physical fault scenarios into the AI pipeline and observe sub-second detection, root-cause diagnosis & WebSocket push.
            </p>
          </div>
        </div>
      </div>

      {/* 2. Interactive Selection Deck */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Config Deck (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {/* Station Selector */}
          <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-xl">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <Globe2 className="h-4 w-4 text-cyan-400" />
              <span>1. Target Automatic Weather Station (AWS)</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {STATIONS.map((stn) => {
                const isSelected = stationId === stn.id;
                return (
                  <button
                    key={stn.id}
                    onClick={() => setStationId(stn.id)}
                    className={`p-3 rounded-xl border text-left transition-all ${
                      isSelected
                        ? 'bg-gradient-to-br from-cyan-950/60 to-[#08122c] border-cyan-400 text-white shadow-lg shadow-cyan-500/20 scale-[1.02]'
                        : 'bg-[#050b1a]/80 border-cyan-500/10 text-slate-400 hover:border-cyan-500/30 hover:text-white'
                    }`}
                  >
                    <span className="text-xs font-bold block">{stn.name}</span>
                    <span className="text-[10px] font-mono text-cyan-400 block mt-0.5">{stn.id}</span>
                    <span className="text-[10px] text-slate-500 block truncate">{stn.loc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Fault Scenario Selector */}
          <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-xl">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <span>2. Select Fault / Anomaly Scenario</span>
            </h2>

            <div className="space-y-3">
              {SCENARIOS.map((sc) => {
                const isSelected = anomalyType === sc.type;
                return (
                  <button
                    key={sc.type}
                    onClick={() => setAnomalyType(sc.type)}
                    className={`w-full p-4 rounded-xl border text-left transition-all ${
                      isSelected
                        ? 'bg-gradient-to-r from-cyan-950/40 via-[#08122c] to-[#050b1a] border-cyan-400 shadow-lg shadow-cyan-500/10 scale-[1.01]'
                        : 'bg-[#050b1a]/70 border-cyan-500/10 hover:border-cyan-500/30'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-white font-sans">{sc.title}</span>
                      <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        {sc.code}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1.5 font-sans leading-relaxed">{sc.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Parameter & Magnitude Controls */}
          <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/75 backdrop-blur-xl p-5 shadow-xl space-y-4">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Sliders className="h-4 w-4 text-cyan-400" />
              <span>3. Target Parameters & Magnitude</span>
            </h2>

            <div>
              <label className="text-xs text-slate-400 block mb-2 font-mono">Affected Sensor Channels:</label>
              <div className="flex flex-wrap gap-2">
                {PARAMETERS.map((p) => {
                  const isSelected = selectedParams.includes(p);
                  return (
                    <button
                      key={p}
                      onClick={() => toggleParam(p)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold uppercase border transition-all ${
                        isSelected
                          ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400 shadow-md shadow-cyan-500/10'
                          : 'bg-[#050b1a] text-slate-400 border-cyan-500/10 hover:border-cyan-500/30'
                      }`}
                    >
                      {p.replace(/_/g, ' ')}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-400">Severity Multiplier:</span>
                  <span className="text-cyan-300 font-bold">{magnitude}x</span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="6.0"
                  step="0.5"
                  value={magnitude}
                  onChange={(e) => setMagnitude(e.target.value)}
                  className="w-full accent-cyan-400 bg-slate-900 h-2 rounded-lg"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-400">Duration (Frozen/Drift):</span>
                  <span className="text-cyan-300 font-bold">{durationMin} min</span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="180"
                  step="15"
                  value={durationMin}
                  onChange={(e) => setDurationMin(e.target.value)}
                  className="w-full accent-cyan-400 bg-slate-900 h-2 rounded-lg"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Execution & Diagnostic Terminal Deck (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Execution Button Card */}
          <div className="rounded-2xl border border-cyan-500/20 bg-[#08122c]/80 backdrop-blur-xl p-5 shadow-2xl space-y-4">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-400">
              Execute Simulation
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Injecting this scenario routes the synthetic reading through the exact ingestion endpoint. Watch the live dashboard & WebSocket update in real time.
            </p>

            <button
              onClick={handleInject}
              disabled={loading}
              className="w-full py-3.5 px-4 bg-gradient-to-r from-blue-600 via-cyan-500 to-emerald-500 hover:from-blue-500 hover:to-emerald-400 disabled:opacity-50 text-white rounded-xl text-sm font-black tracking-wide font-sans shadow-xl shadow-cyan-500/25 transition-all hover:scale-[1.02] flex items-center justify-center gap-2"
            >
              <Zap className={`h-4 w-4 fill-current ${loading ? 'animate-bounce' : ''}`} />
              <span>{loading ? 'Injecting Fault Telemetry...' : 'Inject Fault Scenario Live'}</span>
            </button>

            <button
              onClick={handleGenerateBaseline}
              disabled={genLoading}
              className="w-full py-2.5 px-4 bg-[#050b1a] hover:bg-slate-800 disabled:opacity-50 text-slate-300 border border-cyan-500/20 hover:border-cyan-500/40 rounded-xl text-xs font-mono font-bold transition shadow-inner flex items-center justify-center gap-2"
            >
              <span>{genLoading ? 'Generating...' : 'Generate 24h Clean Baseline Data'}</span>
            </button>
          </div>

          {/* Diagnostic Terminal View */}
          <div className="rounded-2xl border border-cyan-500/20 bg-[#040814] p-5 shadow-2xl font-mono text-xs space-y-3 relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-cyan-500/15 pb-2 text-[11px] text-slate-400 font-bold">
              <span className="flex items-center gap-1.5 text-cyan-400">
                <Terminal className="h-3.5 w-3.5" />
                <span>DIAGNOSTIC TERMINAL</span>
              </span>
              {result?.latency_ms && (
                <span className="text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-500/30">
                  {result.latency_ms}ms
                </span>
              )}
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 space-y-1">
                <p className="font-bold">Execution Error</p>
                <p className="text-[11px]">{error}</p>
              </div>
            )}

            {result ? (
              <div className="space-y-2 text-slate-300">
                <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Pipeline Execution Success</span>
                </div>
                <p className="text-[11px] text-slate-300 font-sans">{result.message}</p>
                {result.anomaly_type && (
                  <div className="bg-[#08122c] p-2.5 rounded-lg border border-cyan-500/15 text-[11px] space-y-1 text-slate-300">
                    <div>Type: <span className="text-cyan-300 font-bold">{result.anomaly_type.toUpperCase()}</span></div>
                    <div>Affected: <span className="text-white">{result.parameters?.join(', ')}</span></div>
                    <div>Station: <span className="text-white">{result.station_id}</span></div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-500 py-6 text-center">
                Ready for anomaly injection. Select a scenario and press "Inject Fault Scenario Live".
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
