# SkyGuard AI

Anomaly detection, sensor health scoring and value correction for Automatic Weather Stations (AWS).
Built for Smart India Hackathon problem statement **SIH26073** (MoES / IMD).

Every 15-minute observation is checked by deterministic quality control and two ML models. The
results are fused into one anomaly score, the probable cause is identified, sensor health is
updated, and a corrected value is estimated. Raw telemetry is never modified.

| Layer | Stack |
| --- | --- |
| API | Python, FastAPI, httpx (Supabase PostgREST) |
| ML | scikit-learn: Isolation Forest + MLP autoencoder, SHAP TreeExplainer, linear regressions |
| Database | Supabase PostgreSQL (`backend/schema.sql`) |
| Dashboard | React 18, Vite, Tailwind CSS, Recharts, Leaflet |
| Live updates | WebSocket (`/api/v1/ws/live`) |

## How detection works

```
observation ─► QC checks ──────────┐
           ├─► Isolation Forest ───┼─► fusion ─► root cause ─► health score ─► correction ─► store + alert + push
           ├─► Autoencoder ────────┘                ▲
           └─► drift detector ──────────────────────┘
```

**1. Deterministic QC**, per sensor:
- **Missing:** no value reported.
- **Range:** outside physical limits (e.g. humidity 0–100 %).
- **Frozen:** 4 identical consecutive readings. Natural constants are exempt: no rain, calm wind, night-time solar radiation, saturated humidity.
- **Spike:** a step from the recent median larger than both 5× the station's robust 15-minute step scale and a plausible weather-change floor.
- **Timestamp gap:** station-level, a reporting interval that is too long.

The QC score is a noisy-OR of severity-weighted flags, so one hard violation dominates instead of being diluted.

**2. Isolation Forest** runs on 110 engineered features: rolling 1 h / 6 h / 24 h stats, deltas, correlations, local solar time and missingness. It is calibrated with a logistic map.

**3. Autoencoder** (14 → 8 → 4 → 8 → 14) runs on raw values plus deltas. The score is (MSE / p99.5 training error)².

**4. Fusion:** `fused = 0.35·QC + 0.30·IF + 0.35·AE`.
- An observation is anomalous when `fused ≥ 0.5`, or when a hard QC rule (range, frozen or spike) fires.
- Severity is critical at `fused ≥ 0.8`.
- Confidence is the agreement between the three channels, raised to the QC score when a deterministic rule fired.

**5. Drift detection:** a residual (measured minus expected value) that keeps the same sign and grows over consecutive readings. The expected value comes from a per-station cross-parameter regression, with yesterday's value at the same time of day as a fallback.

**6. Root cause** rules, evaluated in this order:

| Order | Cause | Condition |
| --- | --- | --- |
| 1 | communication | 3+ sensors missing |
| 2 | frozen | stuck-sensor QC flag |
| 3 | spike | step-test spike on 1–2 sensors |
| 4 | drift | growing same-sign residual (see step 5) |
| 5 | communication | 1–2 sensors missing, or a reporting gap |
| 6 | multivariate | anything else |

**7. Sensor health (0–100):**
- **Penalty:** applied only to the sensors actually implicated, growing with consecutive anomalies.
- **Recovery:** +0.5 per clean reading.
- **Gap decay:** capped at 10 points per outage.
- **Persistence:** scores are restored from `sensor_health_history` on startup.

**8. Correction:** temporal median for spikes, diurnal trend for frozen sensors, and cross-parameter regression for drift. Only the affected sensors are corrected.

## Measured accuracy

`python -m ml.training.train_models` trains on synthetic data and then benchmarks with the exact production scoring code (`app/services/pipeline.py`). It uses held-out synthetic data for all 5 stations: 1,635 normal and 225 faulty readings. Results are written to `ml/benchmark_results.json`.

| Metric | Value |
| --- | --- |
| Precision | 82.7 % |
| Recall | 78.7 % |
| F1 | 80.6 % |
| False-positive rate (normal readings) | 2.3 % |
| Recall by fault type | spike, frozen, multivariate, communication: 100 %; drift: 60 % |
| Root-cause accuracy (detected faults) | 75.7 % |

The labelling rules:
- Readings 2–3 of a stuck run can't be told apart from "no change", so they aren't scored.
- The single reading where a synthetic fault snaps back to normal isn't scored either.
- Early drift readings, whose offset is still within sensor noise, count as misses.

Most root-cause errors are wind-speed drift being labelled `multivariate`. The faults are still detected; wind speed is deliberately excluded from drift classification because gusty data produces false drift alarms. All figures come from synthetic data and must be re-validated on real IMD telemetry before operational use.

## Quick start

Prerequisites: Python 3.12+, Node.js 18+, and a Supabase project.

### 1. Database

Create a Supabase project, then run `backend/schema.sql` in the SQL editor.

### 2. Backend

```bash
cd backend
cp .env.example .env
```

Fill in `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`. Then install the dependencies and seed the data:

```bash
pip install -r requirements-dev.txt
```

```bash
python -m app.services.seeder
```

The seeder creates the 5 demo stations and 7 days of baseline data.

```bash
cd .. && python -m ml.training.train_models && cd backend
```

This trains the models (about 1 minute) and writes the benchmark results.

```bash
uvicorn app.main:app --reload --port 8000
```

API docs are at http://localhost:8000/docs.

### 3. Dashboard

```bash
cd frontend
npm ci
npm run dev
```

The dashboard is at http://localhost:5173. Optional frontend variables: `VITE_API_URL`, `VITE_WS_URL`, `VITE_MAP_TILE_URL`.

### Tests

```bash
cd backend && python -m pytest
```

The suite runs the full API against an in-memory PostgREST stand-in, so it needs no Supabase project.

### Docker (backend)

```bash
docker compose up --build -d
```

Docker reads its secrets from `backend/.env`. Train the models before building, so that `ml/models/*.pkl` exists.

## Configuration (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Database connection (required) |
| `API_KEY` | When set, all write endpoints require header `X-API-Key` |
| `CORS_ORIGINS` | Comma-separated dashboard origins |
| `ENABLE_DEMO_ENDPOINTS` | `false` removes the `/demo/*` fault-injection routes |
| `MAX_BATCH_SIZE`, `MAX_DEMO_GENERATE_HOURS` | Request-size limits |
| `ML_MODEL_DIR`, `LOG_LEVEL` | Optional overrides |

### Production checklist

- Set `API_KEY`. Set `ENABLE_DEMO_ENDPOINTS=false`. Restrict `CORS_ORIGINS` to the real dashboard host.
- Enable Supabase Row Level Security. Better still, give the backend a service-role key and keep the anon key away from writes.
- Retrain the models on real station history; the shipped models are trained on synthetic data.

## API overview

All routes are under `/api/v1`.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/observations`, `/observations/batch` | Ingest and score observations (write) |
| GET | `/stations`, `/stations/{id}` | Stations with live health and open alerts |
| GET | `/stations/{id}/observations?parameter=&hours=` | Raw vs corrected series |
| POST | `/stations` | Register a station (write) |
| GET | `/anomalies`, `/anomalies/{id}` | Anomalies, filterable by station, severity, cause and time; detail includes SHAP and corrections |
| GET | `/alerts` | Alerts, filterable by station, severity, status and time |
| PATCH | `/alerts/{id}/resolve` | Resolve an alert (write) |
| GET | `/health/{station_id}`, `/health/{station_id}/history` | Per-sensor health |
| GET | `/dashboard/summary` | Network KPIs |
| POST | `/demo/inject-anomaly`, `/demo/generate-data` | Fault simulation (write, can be disabled) |
| WS | `/ws/live` | Push events: `anomaly`, `alert`, `health_update` |

## Demo walkthrough

1. Open the dashboard. The map shows the 5 seeded stations: Mumbai, Delhi, Chennai, Kolkata and Bengaluru.
2. Open **Demo Center**, pick a station, and inject each scenario in turn:
   - **Spike:** classified `spike`, corrected with the temporal median.
   - **Frozen:** classified `frozen` after 4 identical readings, corrected with the diurnal trend.
   - **Drift:** classified `drift` once the offset grows consistently, corrected with cross-parameter regression.
   - **Telemetry dropout:** classified `communication`; raises a communication-loss alert.
   - **Multivariate:** coupled deviation across several sensors.
3. Open **Neural Diagnostics** and select a row to see the channel scores, the SHAP attribution and the corrected values.
4. Open **Alert Feeds** and resolve an alert.

## Repository layout

```
backend/
  app/
    main.py            FastAPI app, CORS, error handling, warm start
    config.py          settings from environment / backend/.env
    models/            PostgREST client, Pydantic schemas
    routers/           REST + WebSocket endpoints
    services/          QC, features, fusion, drift, root cause, health, correction, pipeline
  tests/               pytest suite with an in-memory PostgREST stand-in
  schema.sql           database schema and indexes
ml/
  inference/           Isolation Forest + SHAP, autoencoder scoring
  training/            training and benchmark script
  benchmark_results.json
frontend/              React dashboard
ARCHITECTURE.md        design notes
```
