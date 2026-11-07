# SkyGuard AI — Architecture

## Components

```
AWS station / demo injector
        │  POST /api/v1/observations
        ▼
┌──────────────────────── FastAPI backend ─────────────────────────┐
│ routers/observations.py  (per-station lock, CPU work in a thread) │
│   └─ services/pipeline.py  score_observation()  ◄── also used by  │
│        ├─ quality_checks.py   deterministic QC       the benchmark│
│        ├─ feature_engineer.py 110-dim + 14-dim vectors            │
│        ├─ ml/inference        Isolation Forest (+SHAP), autoencoder│
│        ├─ anomaly_detector.py fusion, severity, confidence        │
│        ├─ drift.py            residual-trend drift detection      │
│        └─ root_cause.py       ordered rules → cause + parameters  │
│   ├─ health_scorer.py   per-sensor health (in memory, persisted)  │
│   ├─ corrector.py       corrected values for affected sensors     │
│   └─ websocket.py       push: anomaly / alert / health_update     │
└───────────────┬───────────────────────────────────┬──────────────┘
                │ PostgREST (httpx)                 │ REST + WS
                ▼                                   ▼
        Supabase PostgreSQL                 React dashboard (Vite)
```

## Data flow per observation

1. Fetch up to 110 earlier readings for the station (strictly before this one; covers 24 h plus same-time-yesterday).
2. QC flags and score; feature extraction in local solar time.
3. Isolation Forest and autoencoder scores; fusion → `is_anomaly`, severity, confidence.
4. Drift check; SHAP attribution (only for anomalies); root cause with affected parameters.
5. Health update for implicated sensors; corrections for spike / frozen / drift.
6. Persist observation → anomaly score → health history, corrected values and alerts (parallel).
7. Broadcast events to WebSocket subscribers (concurrent sends with timeout).

## Design decisions

- **One scoring implementation.** The offline benchmark imports the same `score_observation` as the API, so
  reported accuracy is the accuracy of what runs in production.
- **Deterministic rules are authoritative.** Range, frozen and spike flags mark an anomaly on their own;
  ML channels catch subtler, multi-sensor patterns.
- **Raw data is immutable.** Corrections are stored in `corrected_values`, never written over observations.
- **Health is evidence-based.** Only sensors implicated by QC or by the root cause of an actual anomaly are
  penalised; recovery is slow; long outages decay health by at most 10 points.
- **Local solar time.** Day/night logic and diurnal features use station longitude, not UTC.
- **Stateless scale-out caveat.** Health state and station caches live in process memory (rehydrated from the
  database on startup). Run a single API worker, or move this state to the database / Redis before scaling out.

## Database

Six tables, defined with indexes in `backend/schema.sql`:

| Table | Purpose |
| --- | --- |
| `stations` | station metadata and location |
| `observations` | raw readings, unique per (station, time) |
| `anomaly_scores` | channel scores, fusion, root cause, QC flags, SHAP |
| `alerts` | anomaly, health and communication alerts |
| `sensor_health_history` | per-sensor health time series |
| `corrected_values` | estimated values next to raw values |

## Security

- Secrets only from the environment (`backend/.env`, git-ignored).
- Optional `X-API-Key` on every write endpoint (constant-time comparison); demo routes can be disabled.
- Strict request validation (finite numbers, bounds, enums, typed timestamps for range filters, UUID checks).
- Database errors are logged server-side and returned to clients as a generic 503.
- CORS restricted to configured origins without credentials; basic security headers on every response.
