# SkyGuard AI — System Architecture

> AI/ML Anomaly Detection Platform for Automatic Weather Stations  
> SIH26073 · Disaster Management · MoES/IMD

## High-Level Architecture

```
┌──────────────┐     ┌──────────────────────────────────────────────────────┐
│  AWS Station  │────▶│                  FastAPI Backend                     │
│  (or Demo     │     │                                                      │
│   Injector)   │     │  ┌─────────┐  ┌──────────┐  ┌─────────────────────┐ │
└──────────────┘     │  │ Ingest  │─▶│ QC Engine │─▶│ ML Scoring Pipeline │ │
                      │  │ Router  │  │(determin.)│  │  ┌──────┐ ┌─────┐  │ │
                      │  └─────────┘  └──────────┘  │  │  IF  │ │ AE  │  │ │
                      │       │                       │  └──┬───┘ └──┬──┘  │ │
                      │       │                       │     └───┬────┘     │ │
                      │       ▼                       │         ▼          │ │
                      │  ┌──────────┐            ┌───┴──────────────┐     │ │
                      │  │Supabase  │◀───────────│  Fusion Engine   │     │ │
                      │  │PostgreSQL│            │  + Root Cause    │     │ │
                      │  │          │            │  + Health Scorer │     │ │
                      │  └──────────┘            │  + Corrector     │     │ │
                      │       │                   └─────────────────┘     │ │
                      │       │                                            │ │
                      │  ┌────┴─────┐   ┌───────────┐                    │ │
                      │  │ REST API │   │ WebSocket  │                    │ │
                      │  │ /api/v1  │   │ /ws/live   │                    │ │
                      │  └──────────┘   └───────────┘                    │ │
                      └──────────────────────────────────────────────────────┘
                              │                │
                              ▼                ▼
                      ┌──────────────────────────────┐
                      │     React SPA Dashboard       │
                      │  (Vite + Tailwind + Recharts) │
                      │  + Leaflet Map                │
                      └──────────────────────────────┘
```

## Data Flow

1. **Ingest** — Station pushes observation via `POST /api/v1/observations`
2. **QC** — Deterministic quality checks (missing, frozen, range, spike, timestamp)
3. **Feature Engineering** — Extract ~110 features for IF, 14-dim for AE
4. **ML Scoring** — Isolation Forest + Autoencoder score in parallel
5. **Fusion** — Weighted combination: `0.35·QC + 0.30·IF + 0.35·AE`
6. **Root Cause** — Rule-based classification from SHAP + QC flags
7. **Health Update** — Per-sensor health score updated with penalty/recovery
8. **Correction** — Estimated true value if fault is high-confidence
9. **Store** — All results persisted to Supabase PostgreSQL
10. **Alert** — If severity ≥ warning, create alert record
11. **Push** — Broadcast via WebSocket to connected dashboard clients

## Tech Stack

| Layer      | Technology                                  |
|------------|---------------------------------------------|
| Backend    | Python 3.11+, FastAPI, SQLAlchemy (async)   |
| Database   | Supabase PostgreSQL (ap-south-1)            |
| ML         | scikit-learn (IF), TensorFlow/Keras (AE), SHAP |
| Frontend   | React 18, Vite, TailwindCSS, Recharts, Leaflet |
| Real-time  | WebSockets (native FastAPI)                 |

## Key Design Decisions

- **Near-real-time** per-observation processing, not batch
- **3-channel fusion** (deterministic + 2 ML) for robustness
- **Asymmetric health decay** — fast penalty, slow recovery
- **Rule-based root-cause** with SHAP evidence, not end-to-end classifier
- **Raw values always preserved** — corrections are supplementary
- **Demo injection endpoints** — synthetic anomaly generation for SIH judging

## Repository Structure

```
skyguard-ai/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/   # DB + Pydantic models
│   │   ├── routers/  # API endpoints
│   │   └── services/ # Core business logic
│   └── requirements.txt
├── ml/               # Machine learning
│   ├── models/       # Trained model artifacts
│   ├── training/     # Training scripts
│   ├── inference/    # Inference modules
│   └── notebooks/    # Exploration notebooks
├── frontend/         # React SPA
├── docs/             # Specs and handoff docs
│   └── HANDOFF.md    # Implementation-ready spec
└── ARCHITECTURE.md   # This file
```

## Database

6 tables in Supabase PostgreSQL. See `/docs/HANDOFF.md` for complete schema.

| Table                   | Purpose                                    |
|-------------------------|--------------------------------------------|
| `stations`              | AWS station metadata + location            |
| `observations`          | Raw weather parameter readings             |
| `anomaly_scores`        | 3-channel scores + fusion + root cause     |
| `alerts`                | Generated alerts with severity             |
| `sensor_health_history` | Per-parameter health score time series     |
| `corrected_values`      | Estimated true values alongside raw        |
