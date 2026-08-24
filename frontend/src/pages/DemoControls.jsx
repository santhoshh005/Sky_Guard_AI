import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Flame,
  Globe2,
  Play,
  RefreshCw,
  Sliders,
  Sparkles,
  Zap,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { api } from '../services/api';

export default function DemoControls() {
  const [stations, setStations] = useState([]);
  const [selectedStation, setSelectedStation] = useState('');
  const [anomalyType, setAnomalyType] = useState('spike');
  const [selectedParams, setSelectedParams] = useState(['temperature']);
  const [magnitude, setMagnitude] = useState(3.5);
  const [durationMin, setDurationMin] = useState(30);

  const [injecting, setInjecting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const ALL_PARAMS = [
    'temperature',
    'humidity',
    'pressure',
    'wind_speed',
    'wind_direction',
    'rainfall',
    'solar_radiation',
  ];

  const SCENARIOS = [
    {
      id: 'spike',
      title: 'Transient Sensor Spike',
      badge: 'spike',
      description: 'Simulates a sudden sharp transient spike (+15°C to +30°C) on selected parameters.',
      impact: 'Triggers Spike QC check, high IF score & temporal median value correction.',
    },
    {
      id: 'frozen',
      title: 'Frozen / Stuck Sensor',
      badge: 'frozen',
      description: 'Repeats the exact same sensor value for 4+ readings (simulating mechanical ADC freeze).',
      impact: 'Triggers Frozen QC rule & linear/diurnal trend value estimation.',
    },
    {
      id: 'drift',
      title: 'Sensor Calibration Drift',
      badge: 'drift',
      description: 'Applies progressive baseline drift exceeding 2σ over a 24h time-series window.',
      impact: 'Triggers high Autoencoder reconstruction MSE and cross-parameter regression correction.',
    },
    {
      id: 'missing',
      title: 'Telemetry Dropout / Missing Data',
      badge: 'communication',
      description: 'Simulates station transceiver packet loss (null/missing parameters).',
      impact: 'Triggers station-level communication failure classification & health degradation alert.',
    },
    {
      id: 'multivariate',
      title: 'Multivariate Extreme Coupling',
      badge: 'multivariate',
      description: 'Coupled anomaly across temperature, humidity, and pressure simultaneously.',
      impact: 'Triggers full Autoencoder + Isolation Forest multi-channel detection.',
    },
  ];

  useEffect(() => {
    async function fetchStations() {
      try {
        const res = await api.getStations({ limit: 50 });
        const list = res.stations || [];
        setStations(list);
        if (list.length > 0) {
          setSelectedStation(list[0].id);
        }
      } catch (err) {
        console.error('Failed to load stations:', err);
      }
    }
    fetchStations();
  }, []);

  function toggleParam(param) {
    if (selectedParams.includes(param)) {
      if (selectedParams.length > 1) {
        setSelectedParams(selectedParams.filter((p) => p !== param));
      }
    } else {
      setSelectedParams([...selectedParams, param]);
    }
  }

  async function handleInject() {
    if (!selectedStation) return;
    try {
      setInjecting(true);
      setError(null);
      setResult(null);

      const res = await api.injectAnomaly({
        station_id: selectedStation,
        anomaly_type: anomalyType,
        parameters: selectedParams,
        magnitude: parseFloat(magnitude),
        duration_minutes: parseInt(durationMin),
      });

      setResult(res);
    } catch (err) {
      setError(err.message || 'Injection failed.');
    } finally {
      setInjecting(false);
    }
  }

  async function handleGenerateClean() {
    if (!selectedStation) return;
    try {
      setInjecting(true);
      setError(null);
      setResult(null);

      const res = await api.generateData({
        station_id: selectedStation,
        hours: 24,
      });

      setResult({
        anomaly_type: 'normal',
        message: res.message,
        affected_parameters: ALL_PARAMS,
      });
    } catch (err) {
      setError(err.message || 'Generation failed.');
    } finally {
      setInjecting(false);
    }
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Sliders className="h-6 w-6 text-cyan-400" />
          <h1 className="text-2xl font-bold text-white tracking-tight">Interactive SIH Judge Demo Center</h1>
          <span className="px-2 py-0.5 text-xs font-bold uppercase rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
            Real-Time Injection
          </span>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Trigger live physical fault scenarios into the AI pipeline and observe sub-second detection, root-cause diagnosis & WebSocket push.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Configuration Controls */}
        <div className="lg:col-span-2 space-y-5">
          {/* 1. Station Selector */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-3">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Globe2 className="h-4 w-4 text-cyan-400" />
              <span>1. Target Automatic Weather Station (AWS)</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {stations.map((stn) => (
                <button
                  key={stn.id}
                  onClick={() => setSelectedStation(stn.id)}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    selectedStation === stn.id
                      ? 'bg-blue-950/50 border-cyan-500 shadow-md shadow-cyan-500/10'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-xs text-white">{stn.name}</span>
                    <span className="text-[10px] font-mono text-cyan-400">{stn.station_code}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">{stn.district}, {stn.state}</p>
                </button>
              ))}
            </div>
          </div>

          {/* 2. Anomaly Scenario Selector */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-3">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <span>2. Select Fault / Anomaly Scenario</span>
            </h2>
            <div className="space-y-2.5">
              {SCENARIOS.map((sc) => (
                <button
                  key={sc.id}
                  onClick={() => setAnomalyType(sc.id)}
                  className={`w-full p-3.5 rounded-lg border text-left transition-all flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
                    anomalyType === sc.id
                      ? 'bg-blue-950/50 border-cyan-500 shadow-md shadow-cyan-500/10'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-white">{sc.title}</span>
                      <StatusBadge status={sc.badge} size="sm" />
                    </div>
                    <p className="text-xs text-slate-300">{sc.description}</p>
                    <p className="text-[11px] text-cyan-400/80 font-mono">{sc.impact}</p>
                  </div>
                  <div className="shrink-0">
                    <span className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${
                      anomalyType === sc.id ? 'border-cyan-400 bg-cyan-400' : 'border-slate-600'
                    }`}>
                      {anomalyType === sc.id && <span className="h-1.5 w-1.5 rounded-full bg-slate-950" />}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 3. Parameter and Magnitude Adjustments */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Zap className="h-4 w-4 text-cyan-400" />
              <span>3. Target Parameters & Magnitude</span>
            </h2>

            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-2">Affected Sensor Channels:</label>
              <div className="flex flex-wrap gap-2">
                {ALL_PARAMS.map((param) => {
                  const isSelected = selectedParams.includes(param);
                  return (
                    <button
                      key={param}
                      onClick={() => toggleParam(param)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition ${
                        isSelected
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                          : 'bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {param}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                  Severity / Magnitude Multiplier: <span className="font-mono text-cyan-400">{magnitude}x</span>
                </label>
                <input
                  type="range"
                  min="1.5"
                  max="6.0"
                  step="0.5"
                  value={magnitude}
                  onChange={(e) => setMagnitude(e.target.value)}
                  className="w-full accent-cyan-400"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                  Duration (for Frozen / Drift): <span className="font-mono text-cyan-400">{durationMin} min</span>
                </label>
                <input
                  type="range"
                  min="15"
                  max="180"
                  step="15"
                  value={durationMin}
                  onChange={(e) => setDurationMin(e.target.value)}
                  className="w-full accent-cyan-400"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Trigger Action & Real-Time Console */}
        <div className="space-y-5">
          {/* Action Trigger Card */}
          <div className="rounded-xl border border-cyan-500/30 bg-gradient-to-b from-blue-950/40 to-slate-900/90 p-5 shadow-2xl space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Execute Simulation</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Injecting this scenario routes the synthetic reading through the exact ingestion endpoint. Watch the live dashboard & WebSocket update in real time.
            </p>

            <div className="space-y-2.5 pt-2">
              <button
                onClick={handleInject}
                disabled={injecting}
                className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 via-cyan-500 to-emerald-500 hover:from-blue-500 hover:to-emerald-400 text-white font-bold text-sm shadow-lg shadow-cyan-500/25 flex items-center justify-center gap-2 transition disabled:opacity-50"
              >
                {injecting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Processing Pipeline...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 fill-current" />
                    <span>Inject Fault Scenario Live</span>
                  </>
                )}
              </button>

              <button
                onClick={handleGenerateClean}
                disabled={injecting}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700 flex items-center justify-center gap-2 transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Generate 24h Clean Baseline Data</span>
              </button>
            </div>
          </div>

          {/* Feedback / Console Display */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs shadow-xl min-h-[220px]">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3 text-slate-400">
              <span className="text-[11px] uppercase tracking-wider font-semibold">Diagnostic Terminal</span>
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
            </div>

            {error && (
              <div className="p-3 bg-red-950/50 border border-red-500/50 rounded text-red-300 text-xs">
                [ERROR] {error}
              </div>
            )}

            {result ? (
              <div className="space-y-2 text-slate-300">
                <div className="flex items-center gap-2 text-emerald-400 font-bold">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Pipeline Execution Success</span>
                </div>
                <p className="text-white text-xs">{result.message}</p>
                <div className="text-[11px] text-slate-400 space-y-1 pt-2 border-t border-slate-900">
                  <div>Type: <span className="text-cyan-300 uppercase">{result.anomaly_type}</span></div>
                  <div>Affected: <span className="text-amber-300">{result.affected_parameters?.join(', ')}</span></div>
                  {result.injected_observations && (
                    <div>Injected IDs: <span className="text-slate-500">{result.injected_observations.length} records</span></div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-slate-500 text-center py-12 font-sans">
                Ready for anomaly injection. Select a scenario and press "Inject Fault Scenario Live".
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
