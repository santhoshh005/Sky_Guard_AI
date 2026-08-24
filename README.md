# 🛡️ SkyGuard AI — Automatic Weather Station Anomaly Detection Platform

[![SIH 2026](https://img.shields.io/badge/SIH-2026-blue.svg)](https://sih.gov.in)
[![Ministry](https://img.shields.io/badge/Ministry-MoES%20%2F%20IMD-orange.svg)](https://mausam.imd.gov.in)
[![ML Precision](https://img.shields.io/badge/Benchmark%20F1-94.9%25-emerald.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg)]()
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)]()

> **SIH26073 Problem Statement**: AI/ML-driven automated anomaly detection, sensor health scoring, TreeSHAP root-cause explainability, and telemetry value correction for Indian Meteorological Department (IMD) Automatic Weather Stations (AWS).

---

## 🌟 Key Architecture & Capabilities

```
                  ┌────────────────────────────────────────┐
                  │ 15-Minute Raw AWS Telemetry Ingestion  │
                  └───────────────────┬────────────────────┘
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
  ┌─────────────────────────┐                   ┌─────────────────────────┐
  │ Deterministic QC Engine │                   │ Feature Engineering     │
  │ • Physical range bounds │                   │ • Time-range rolling    │
  │ • Frozen value check    │                   │ • Rate-of-change deltas │
  │ • 24h rolling spike std │                   │ • Correlations (24h)    │
  │ • Timestamp gap check   │                   │ • Temporal day/night    │
  └────────────┬────────────┘                   └────────────┬────────────┘
               │ (Weight: 0.35)                              │
               │                                ┌────────────┴────────────┐
               │                                ▼                         ▼
               │                   ┌─────────────────────────┐ ┌─────────────────────────┐
               │                   │  Isolation Forest (IF)  │ │  14-8-4-8-14 Autoenc.   │
               │                   │  (~110-dim density)     │ │  (14-dim reconstruction)│
               │                   └────────────┬────────────┘ └────────────┬────────────┘
               │                                │ (Weight: 0.30)          │ (Weight: 0.35)
               └────────────────────────────────┼─────────────────────────┘
                                                ▼
                               ┌─────────────────────────────────┐
                               │ 3-Channel Fusion & Confidence   │
                               │ fused = 0.35·QC+0.30·IF+0.35·AE │
                               └────────────────┬────────────────┘
                                                │
         ┌──────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                      ▼                                      ▼
┌─────────────────────────┐            ┌─────────────────────────┐            ┌─────────────────────────┐
│ Root-Cause & TreeSHAP   │            │ Sensor Health Engine    │            │ Automated Value Correct.│
│ • Spike (transient jump)│            │ • Health Index [0-100]  │            │ • Temporal median       │
│ • Frozen (stuck sensor) │            │ • Streak penalties      │            │ • Diurnal trend inter.  │
│ • Drift (calibration)   │            │ • Time decay            │            │ • Cross-param regression│
│ • Communication dropout │            │ • Maintenance alerts    │            │ (Raw telemetry preserved│
│ • Multivariate extreme  │            └─────────────────────────┘            └─────────────────────────┘
└─────────────────────────┘
```

1. **3-Channel Multi-Paradigm Fusion**:
   $$\text{Fused Score} = 0.35 \times \text{QC} + 0.30 \times \text{IF} + 0.35 \times \text{AE}$$
   Achieves **94.94% F1-Score** on benchmark datasets.
2. **TreeSHAP Explainability**: Translates high-dimensional vector anomalies into plain English diagnostic reports explaining which sensors deviated and why.
3. **Adaptive Sensor Health Scoring [0–100]**: Accelerates penalty on consecutive anomalies ($2.0 \times [1 + 0.5 \cdot \min(\text{streak}, 10)]$), applies time decay for missed reporting intervals, and recovers gradually ($+0.5$ per clean observation).
4. **Automated Correction without Data Loss**: Preserves raw telemetry permanently in `observations` table while deriving replacement values using temporal median filters, diurnal trends, or cross-parameter linear regression.
5. **Real-time Push Stream**: Low-latency WebSocket event broadcaster ($<2\text{s}$ response).

---

## 🚀 Quick Start (Local Run)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Seed the 5 IMD demo stations & 7-day baseline observations
python -m app.services.seeder

# Train ML models & run benchmark evaluation
python -m ml.training.train_models

# Start FastAPI backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be live at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend Setup
```bash
# In a new terminal, navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
Dashboard UI will be live at: [http://localhost:5173](http://localhost:5173)

---

## 🐳 Docker Deployment

To run the entire backend in a container:
```bash
docker-compose up --build -d
```

---

## 🔬 SIH Judge Live Demonstration Script

Follow this step-by-step walkthrough to demonstrate the system live to judges:

| Step | Action | Expected Output in UI |
| :--- | :--- | :--- |
| **1. Overview** | Open `http://localhost:5173` | Interactive national Leaflet map shows all 5 seeded AWS stations (Mumbai, Delhi, Chennai, Kolkata, Bengaluru) with green healthy status markers. |
| **2. Demo Center** | Click **Demo Center** in top navbar | Opens the Fault Simulation console. Select **Mumbai Colaba (`AWS_MUM_001`)**. |
| **3. Spike Injection** | Select **Transient Sensor Spike**, choose `temperature`, click **Inject Fault Scenario Live** | Within &lt;1 second: <br>• Diagnostic Terminal shows execution success.<br>• Live Alert Stream flashes with critical anomaly alert.<br>• Root-cause classified as **`SPIKE`**.<br>• Value estimated via **Temporal Median Filter**. |
| **4. Frozen Sensor** | Select **Frozen / Stuck Sensor**, choose `humidity`, click **Inject Fault** | • Anomaly registered with **`FROZEN`** badge.<br>• Explains: *Humidity sensor is stuck at 78% across consecutive readings*.<br>• Corrected value estimated via **Diurnal Trend**. |
| **5. Calibration Drift** | Select **Sensor Calibration Drift**, choose `temperature`, click **Inject Fault** | • Autoencoder reconstruction MSE spikes.<br>• Root-cause classified as **`DRIFT`**.<br>• Corrected value predicted via **Cross-Parameter Regression** using other 6 sensor channels. |
| **6. Comm Dropout** | Select **Telemetry Dropout**, click **Inject Fault** | • Root-cause classified as **`COMMUNICATION`**.<br>• Health degradation alert triggered. |
| **7. SHAP Breakdown** | Navigate to **Anomalies** &rarr; click **Explain** | Waterfall bar chart displays TreeSHAP feature attribution demonstrating exact physical parameter contributions. |
| **8. Resolution** | Navigate to **Alerts Feed** &rarr; click **Resolve** | Alert status immediately transitions from active to resolved with timestamp audit. |

---

## 📁 Repository Structure

```
skyguard-ai/
├── backend/
│   ├── app/
│   │   ├── config.py              # Pydantic settings & DB config
│   │   ├── main.py                # FastAPI app with CORS & lifespan
│   │   ├── models/
│   │   │   ├── database.py        # SQLAlchemy models + Supabase PostgREST async client
│   │   │   └── schemas.py         # Request/response Pydantic models
│   │   ├── routers/
│   │   │   ├── alerts.py          # Alert listing and resolution
│   │   │   ├── anomalies.py       # Anomaly logs & SHAP inspector
│   │   │   ├── dashboard.py       # Aggregated KPIs summary
│   │   │   ├── demo.py            # Real-time anomaly injection & generation
│   │   │   ├── health.py          # Sensor reliability scores & history
│   │   │   ├── observations.py    # Main ingestion pipeline
│   │   │   ├── stations.py        # AWS station metadata & gauges
│   │   │   └── websocket.py       # Real-time WebSocket connection manager
│   │   └── services/
│   │       ├── anomaly_detector.py# 3-channel score fusion (QC + IF + AE)
│   │       ├── corrector.py       # Fault value estimation engine
│   │       ├── data_generator.py  # IMD weather profiles & anomaly recipes
│   │       ├── feature_engineer.py# Time-range rolling statistics & deltas
│   │       ├── health_scorer.py   # Degradation, recovery & streak scoring
│   │       ├── quality_checks.py  # Physical bounds & deterministic checks
│   │       ├── root_cause.py      # 5-category hierarchical decision rules
│   │       └── seeder.py          # Baseline data & stations seeder
│   ├── requirements.txt
│   └── Dockerfile
├── ml/
│   ├── models/                    # Serialized model artifacts (.pkl)
│   ├── inference/
│   │   ├── isolation_forest.py    # IF inference + TreeSHAP explainer
│   │   └── autoencoder.py         # 14-dim MLPRegressor Autoencoder
│   └── training/
│       └── train_models.py        # ML training & benchmark evaluation
├── frontend/
│   ├── src/
│   │   ├── components/            # Navbar, StationMap, StatCard, StatusBadge
│   │   ├── pages/                 # Dashboard, Stations, Anomalies, Alerts, Health, Demo
│   │   ├── services/api.js        # API & WebSocket client
│   │   ├── App.jsx                # Router & live WebSocket dispatcher
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── docs/
│   └── HANDOFF.md                 # Complete system handoff specification
├── docker-compose.yml
├── ARCHITECTURE.md
└── README.md
```

---

## 🏛️ Built for MoES / IMD Disaster Management (SIH26073)
Developed with precision AI architectures ensuring robust weather monitoring across India.
