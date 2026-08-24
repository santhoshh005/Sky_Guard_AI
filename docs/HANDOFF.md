# SkyGuard AI — Implementation Handoff Specification

> **For: Flash model implementation pass**  
> **From: Architecture pass (Opus)**  
> **Date: 2026-08-24**  
> **Supabase Project ID: `ncjejgcosipagizirjxs`**  
> **Supabase Region: `ap-south-1`**  
> **DB Schema: Already applied via migration `create_skyguard_schema`**

---

## §0 — Execution Order

Implement in this exact order. Each step depends on the previous.

| # | Task | Files | Est. |
|---|------|-------|------|
| 1 | Backend config + DB connection | `config.py`, `database.py` | 15m |
| 2 | Pydantic schemas | `schemas.py` | 20m |
| 3 | Synthetic data generator | `demo.py` (router) + service | 30m |
| 4 | Feature engineering service | `feature_engineer.py` | 30m |
| 5 | Quality checks service | `quality_checks.py` | 20m |
| 6 | ML training scripts | `train_isolation_forest.py`, `train_autoencoder.py` | 30m |
| 7 | ML inference modules | `isolation_forest.py`, `autoencoder.py` | 20m |
| 8 | Anomaly fusion service | `anomaly_detector.py` | 20m |
| 9 | Root-cause classifier | `root_cause.py` | 15m |
| 10 | Health scorer service | `health_scorer.py` | 20m |
| 11 | Corrected-value estimator | `corrector.py` | 20m |
| 12 | Observation ingestion router | `observations.py` | 25m |
| 13 | Station/Anomaly/Alert/Health/Dashboard routers | remaining routers | 30m |
| 14 | WebSocket handler | `websocket.py` | 15m |
| 15 | FastAPI main app assembly | `main.py` | 10m |
| 16 | Frontend React app | `frontend/` | 90m |
| 17 | Docker + README | root files | 15m |

---

## §1 — Database Schema (LIVE in Supabase)

The following tables are already created. Use SQLAlchemy async ORM models that mirror them exactly.

### 1.1 stations

```sql
CREATE TABLE stations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_code VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  elevation_m DOUBLE PRECISION,
  state VARCHAR(100),
  district VARCHAR(100),
  station_type VARCHAR(50) DEFAULT 'AWS',
  expected_interval_min INTEGER DEFAULT 15,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 1.2 observations

```sql
CREATE TABLE observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  observed_at TIMESTAMPTZ NOT NULL,
  temperature DOUBLE PRECISION,
  humidity DOUBLE PRECISION,
  pressure DOUBLE PRECISION,
  wind_speed DOUBLE PRECISION,
  wind_direction DOUBLE PRECISION,
  rainfall DOUBLE PRECISION,
  solar_radiation DOUBLE PRECISION,
  ingested_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(station_id, observed_at)
);
```

### 1.3 anomaly_scores

```sql
CREATE TABLE anomaly_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id UUID NOT NULL REFERENCES observations(id) ON DELETE CASCADE UNIQUE,
  qc_score DOUBLE PRECISION NOT NULL CHECK (qc_score >= 0 AND qc_score <= 1),
  if_score DOUBLE PRECISION NOT NULL CHECK (if_score >= 0 AND if_score <= 1),
  ae_score DOUBLE PRECISION NOT NULL CHECK (ae_score >= 0 AND ae_score <= 1),
  fused_score DOUBLE PRECISION NOT NULL CHECK (fused_score >= 0 AND fused_score <= 1),
  confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  is_anomaly BOOLEAN NOT NULL,
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('normal', 'warning', 'critical')),
  root_cause VARCHAR(30) CHECK (root_cause IN ('spike', 'frozen', 'drift', 'communication', 'multivariate')),
  explanation TEXT,
  qc_flags JSONB DEFAULT '{}',
  shap_values JSONB DEFAULT '{}',
  scored_at TIMESTAMPTZ DEFAULT now()
);
```

### 1.4 alerts

```sql
CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  anomaly_score_id UUID REFERENCES anomaly_scores(id) ON DELETE SET NULL,
  alert_type VARCHAR(30) NOT NULL CHECK (alert_type IN ('anomaly', 'health_degraded', 'maintenance_required', 'communication_loss')),
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
  title VARCHAR(500) NOT NULL,
  description TEXT,
  parameter VARCHAR(50),
  is_resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 1.5 sensor_health_history

```sql
CREATE TABLE sensor_health_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  parameter VARCHAR(50) NOT NULL CHECK (parameter IN ('temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'rainfall', 'solar_radiation')),
  health_score DOUBLE PRECISION NOT NULL CHECK (health_score >= 0 AND health_score <= 100),
  status VARCHAR(30) NOT NULL CHECK (status IN ('healthy', 'degraded', 'maintenance_recommended', 'sensor_critical')),
  anomaly_streak INTEGER DEFAULT 0,
  recorded_at TIMESTAMPTZ DEFAULT now()
);
```

### 1.6 corrected_values

```sql
CREATE TABLE corrected_values (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id UUID NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
  parameter VARCHAR(50) NOT NULL CHECK (parameter IN ('temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'rainfall', 'solar_radiation')),
  raw_value DOUBLE PRECISION,
  corrected_value DOUBLE PRECISION,
  correction_method VARCHAR(50) NOT NULL CHECK (correction_method IN ('temporal_median', 'interpolation', 'diurnal_trend', 'cross_parameter_regression', 'none')),
  correction_confidence DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (correction_confidence >= 0 AND correction_confidence <= 1),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(observation_id, parameter)
);
```

### 1.7 Parameter Constants

Use this enum/list everywhere:

```python
PARAMETERS = ['temperature', 'humidity', 'pressure', 'wind_speed',
              'wind_direction', 'rainfall', 'solar_radiation']
```

---

## §2 — Feature Engineering

### 2.1 Raw Features (7)

Direct observation values: `temperature, humidity, pressure, wind_speed, wind_direction, rainfall, solar_radiation`

### 2.2 Rolling Statistics (84 features)

For each of the 7 parameters, compute over 3 **time-range** windows (1h, 6h, 24h).
Query: `SELECT {param} FROM observations WHERE station_id = ? AND observed_at BETWEEN (current - window) AND current`.
This is **not** a fixed observation count — it adapts to each station's `expected_interval_min` and tolerates gaps.

- `{param}_mean_{window}`
- `{param}_std_{window}`
- `{param}_min_{window}`
- `{param}_max_{window}`

If a window contains < 2 observations, fill the stat features with 0 (mean/std) or the raw value (min/max).

Total: 7 × 3 × 4 = 84 features

> **APPLIES UNIFORMLY**: This time-range convention governs all rolling/baseline
> functions throughout the spec: `rolling_std_24h` (§3.1), `rolling_mean_24h` (§4.2, §5),
> `baseline_mean` / `baseline_std` (§4.2, §5 Rule 4). Never use fixed obs counts.

### 2.3 Rate of Change (7 features)

```python
delta_{param} = current_value - previous_value
```

### 2.4 Inter-Parameter Correlations (3 features)

Compute Pearson correlation over last 24h window between:
- `corr_temp_humidity` (expected: negative)
- `corr_pressure_wind` (expected: positive during storms)
- `corr_solar_temp` (expected: positive during daytime)

### 2.5 Temporal Features (2 features)

```python
hour_of_day = observed_at.hour  # 0-23, normalized to [0,1]
is_daytime = 1 if 6 <= hour_of_day <= 18 else 0
```

### 2.6 Missingness Indicators (7 features)

```python
missing_{param} = 1 if value is None else 0
```

### 2.7 Output Vectors

**Isolation Forest input** (~110 dims): All of the above concatenated.

**Autoencoder input** (14 dims): 7 normalized raw values + 7 deltas. Normalize using StandardScaler fitted on training data.

---

## §3 — Anomaly Detection Fusion

### 3.1 Channel 1: Deterministic Quality Checks

#### Physical bounds table

| Parameter        | Min   | Max   | Unit  |
|------------------|-------|-------|-------|
| temperature      | -50   | 60    | °C    |
| humidity         | 0     | 100   | %     |
| pressure         | 870   | 1084  | hPa   |
| wind_speed       | 0     | 120   | m/s   |
| wind_direction   | 0     | 360   | °     |
| rainfall         | 0     | 500   | mm    |
| solar_radiation  | 0     | 1500  | W/m²  |

#### QC flag rules

```python
flags = {}  # param_name -> list of flag strings

for param in PARAMETERS:
    val = observation[param]
    flags[param] = []
    
    # MISSING
    if val is None:
        flags[param].append('missing')
        continue  # skip other checks for null values
    
    # RANGE
    if val < BOUNDS[param]['min'] or val > BOUNDS[param]['max']:
        flags[param].append('range')
    
    # FROZEN: same value for >= 4 consecutive observations
    # Exception: rainfall == 0 is valid anytime (no rain); solar_radiation == 0 is valid ONLY at night (outside §9.1 06:00-18:00 window)
    is_daytime = 6 <= current_observed_at.hour <= 18
    is_zero_natural = (param == 'rainfall' and val == 0) or (param == 'solar_radiation' and val == 0 and not is_daytime)
    if not is_zero_natural:
        recent = last_N_values(station_id, param, n=4)
        if len(set(recent)) == 1 and len(recent) == 4:
            flags[param].append('frozen')
    
    # SPIKE: |delta| > 5 * rolling_std_24h
    delta = abs(val - previous_value(station_id, param))
    rolling_std = rolling_std_24h(station_id, param)
    if rolling_std > 0 and delta > 5 * rolling_std:
        flags[param].append('spike')

# TIMESTAMP check (station-level, not per-parameter)
time_gap = (current_observed_at - previous_observed_at).total_seconds() / 60
expected = station.expected_interval_min
if time_gap > 2 * expected:
    flags['_station'] = ['timestamp_gap']

# Compute QC score
total_flags = sum(len(f) for f in flags.values())
total_checks = len(PARAMETERS) * 4 + 1  # 4 checks per param + 1 timestamp
qc_score = min(1.0, total_flags / total_checks)
```

#### QC flags JSONB format

```json
{
  "temperature": ["spike"],
  "humidity": [],
  "pressure": [],
  "wind_speed": [],
  "wind_direction": [],
  "rainfall": ["frozen"],
  "solar_radiation": [],
  "_station": [],
  "qc_score": 0.069
}
```

### 3.2 Channel 2: Isolation Forest

```python
# At inference time:
raw_score = model.decision_function(feature_vector)  # negative = more anomalous
if_score = max(0, min(1, (1 - raw_score) / 2))
# Result: 0 = definitely normal, 1 = definitely anomalous
```

### 3.3 Channel 3: Autoencoder

```python
# At inference time:
reconstructed = model.predict(compact_vector)
mse = np.mean((compact_vector - reconstructed) ** 2)
ae_score = min(1.0, mse / threshold_95th_percentile)
# Result: 0 = reconstruction is perfect, 1 = very high error
```

### 3.4 Fusion Formula

```python
W_QC = 0.35
W_IF = 0.30
W_AE = 0.35

fused_score = W_QC * qc_score + W_IF * if_score + W_AE * ae_score

# Confidence: how much the three channels agree
scores = [qc_score, if_score, ae_score]
agreement = 1 - (np.std(scores) / 0.577)  # 0.577 = max std for [0,1] values
confidence = max(0.0, min(1.0, agreement))

# Classification
is_anomaly = fused_score >= 0.5
if fused_score >= 0.8:
    severity = 'critical'
elif fused_score >= 0.5:
    severity = 'warning'
else:
    severity = 'normal'
```

---

## §4 — Sensor Health Score

### 4.1 State

Per `(station_id, parameter)` tuple, track:

```python
@dataclass
class SensorHealthState:
    health_score: float = 100.0   # [0, 100]
    anomaly_streak: int = 0
    last_updated: datetime = None
```

### 4.2 Update Rule (called per observation)

```python
def update_health(state: SensorHealthState, observation, anomaly_result, station):
    param_value = observation[param]
    param_is_anomalous = param in anomaly_result.flagged_parameters
    
    # Time decay for missed observations
    if state.last_updated is not None:
        elapsed_min = (observation.observed_at - state.last_updated).total_seconds() / 60
        expected_min = station.expected_interval_min
        if elapsed_min > 2 * expected_min:
            missed_intervals = int(elapsed_min / expected_min) - 1
            state.health_score = max(0, state.health_score - 1.0 * missed_intervals)
    
    if param_is_anomalous:
        state.anomaly_streak += 1
        
        # Penalty: accelerates with streak
        penalty = 2.0 * (1 + 0.5 * min(state.anomaly_streak, 10))
        
        # Additional penalties
        if param_value is None:
            penalty += 3.0  # missing
        if is_drifting(station_id, param):  # mean over 24h deviates > 2σ from 30-day baseline
            penalty += 5.0
        if ae_per_param_error(param) > 0.7:
            penalty += 1.5
        
        state.health_score = max(0, state.health_score - penalty)
    else:
        # Recovery: deliberately slow
        state.health_score = min(100, state.health_score + 0.5)
        state.anomaly_streak = 0
    
    state.last_updated = observation.observed_at
    
    # Determine status
    if state.health_score < 15:
        status = 'sensor_critical'
    elif state.health_score < 40:
        status = 'maintenance_recommended'
    elif state.health_score < 70:
        status = 'degraded'
    else:
        status = 'healthy'
    
    return state, status
```

### 4.3 Alert Generation from Health

```python
if status == 'maintenance_recommended' and previous_status != 'maintenance_recommended':
    create_alert(type='maintenance_required', severity='warning',
                 title=f'Sensor {param} at {station.name} needs maintenance',
                 parameter=param)
if status == 'sensor_critical' and previous_status != 'sensor_critical':
    create_alert(type='health_degraded', severity='critical',
                 title=f'Sensor {param} at {station.name} is critically degraded',
                 parameter=param)
```

---

## §5 — Root-Cause Classification

Evaluate in this exact order. First match wins.

### Rule 1: Communication/Missing

```python
missing_params = [p for p in PARAMETERS if observation[p] is None]
has_timestamp_gap = '_station' in qc_flags and 'timestamp_gap' in qc_flags['_station']

if len(missing_params) >= 3 or has_timestamp_gap:
    root_cause = 'communication'
    if has_timestamp_gap:
        explanation = f'Data gap of {gap_minutes} minutes detected.'
    else:
        explanation = f'{len(missing_params)} parameters missing: {", ".join(missing_params)}. Possible communication failure.'
```

### Rule 2: Frozen

```python
frozen_params = [p for p in PARAMETERS if 'frozen' in qc_flags.get(p, [])]
if frozen_params:
    # Check if any frozen param is in top-3 SHAP contributors
    top_shap_params = get_top_shap_parameters(shap_values, n=3)
    if any(p in top_shap_params for p in frozen_params):
        worst = frozen_params[0]  # most contributing
        root_cause = 'frozen'
        explanation = f'{worst} has been constant at {observation[worst]} for {streak_count} consecutive readings ({streak_count * interval}min). Sensor may be stuck.'
```

### Rule 3: Spike

```python
spike_params = [p for p in PARAMETERS if 'spike' in qc_flags.get(p, [])]
if spike_params and len(spike_params) <= 2:
    top_shap_params = get_top_shap_parameters(shap_values, n=3)
    # Check that delta features for spiked params are in top SHAP
    if any(f'{p}_delta' in top_shap_features for p in spike_params):
        worst = spike_params[0]
        delta = observation[worst] - previous_observation[worst]
        sigma = delta / rolling_std_24h(station_id, worst)
        root_cause = 'spike'
        explanation = f'Sudden spike in {worst}: value jumped from {prev} to {current} ({sigma:.1f}σ deviation). Likely sensor malfunction.'
```

### Rule 4: Drift

```python
if ae_score > 0.5:
    top_shap_params = get_top_shap_parameters(shap_values, n=3)
    for param in top_shap_params:
        mean_24h = rolling_mean_24h(station_id, param)
        # ADAPTIVE BASELINE: use all history older than 24h, require >= 3 days
        baseline = get_baseline(station_id, param)  # see §14.3
        if baseline is None:
            continue  # not enough history
        if baseline.std > 0 and abs(mean_24h - baseline.mean) > 2 * baseline.std:
            shift = mean_24h - baseline.mean
            root_cause = 'drift'
            explanation = f'{param} mean shifted by {shift:.2f} over last 24h (baseline: {baseline.mean:.2f}±{baseline.std:.2f}). Possible calibration drift.'
            break
```

### Rule 5: Multivariate (catch-all)

```python
if is_anomaly and root_cause is None:
    top_shap_params = get_top_shap_parameters(shap_values, n=5)
    unique_params = set(extract_base_param(f) for f in top_shap_params)
    root_cause = 'multivariate'
    explanation = f'Correlated anomaly across {", ".join(unique_params)}. Pattern inconsistent with normal weather variation.'
```

### Helper: get_top_shap_parameters

```python
def get_top_shap_parameters(shap_values: dict, n: int) -> list[str]:
    """Extract base parameter names from top-N SHAP feature contributions."""
    # shap_values['top_features'] is sorted by |contribution| descending
    features = shap_values.get('top_features', [])[:n]
    params = []
    for f in features:
        name = f['feature']
        # Extract base param: 'temperature_delta' -> 'temperature'
        for p in PARAMETERS:
            if name.startswith(p):
                params.append(p)
                break
    return params
```

---

## §6 — Corrected-Value Estimation

### 6.1 Trigger Condition

```python
if anomaly_score >= 0.6 and confidence >= 0.7 and root_cause not in ('communication', 'multivariate'):
    corrected = estimate_correction(observation, root_cause, station_id, param)
else:
    corrected = CorrectedValue(raw_value=val, corrected_value=None, method='none', confidence=0)
```

### 6.2 Methods

#### Spike → Temporal Median

```python
def correct_spike(station_id, param, observation_index):
    # Get 3 neighbors before and 3 after (excluding the anomalous observation)
    neighbors = get_neighbor_values(station_id, param, observation_index, window=3)
    if len(neighbors) >= 2:
        corrected = np.median(neighbors)
        confidence = 1.0 - (np.std(neighbors) / PARAM_RANGE[param])
        return corrected, 'temporal_median', max(0, min(1, confidence))
    return None, 'none', 0
```

#### Frozen → Interpolation / Diurnal Trend

```python
def correct_frozen(station_id, param, observation):
    last_good = get_last_non_frozen_value(station_id, param)
    next_good = get_next_non_frozen_value(station_id, param)  # may be None in real-time
    
    if last_good and next_good:
        # Linear interpolation
        position = (observation.observed_at - last_good.observed_at) / \
                   (next_good.observed_at - last_good.observed_at)
        corrected = last_good.value + position * (next_good.value - last_good.value)
        return corrected, 'interpolation', 0.8
    elif last_good:
        # Use diurnal trend: value from same time yesterday
        yesterday_value = get_value_at_offset(station_id, param, observation.observed_at, hours=-24)
        yesterday_prev = get_value_at_offset(station_id, param, last_good.observed_at, hours=-24)
        if yesterday_value and yesterday_prev:
            trend = yesterday_value - yesterday_prev
            corrected = last_good.value + trend
            return corrected, 'diurnal_trend', 0.6
    return None, 'none', 0
```

#### Drift → Cross-Parameter Regression

```python
def correct_drift(station_id, param, observation):
    # Use pre-trained linear regression coefficients
    # Stored per station, mapping: param -> {coefficients for correlated params, intercept}
    model = load_regression_model(station_id, param)
    if model is None:
        return None, 'none', 0
    
    # Build input from correlated parameters (exclude the drifting one)
    correlated_params = [p for p in PARAMETERS if p != param and observation[p] is not None]
    input_values = [observation[p] for p in correlated_params]
    
    corrected = model.predict(input_values)
    confidence = model.r_squared  # pre-computed during training
    return corrected, 'cross_parameter_regression', confidence
```

### 6.3 Storage

Always store in `corrected_values` table:

```python
insert_corrected_value(
    observation_id=obs.id,
    parameter=param,
    raw_value=observation[param],
    corrected_value=corrected,
    correction_method=method,
    correction_confidence=confidence
)
```

---

## §7 — SHAP Explainability

### 7.1 Integration

```python
import shap

# At startup: create explainer from trained Isolation Forest
explainer = shap.TreeExplainer(isolation_forest_model)

# Per anomalous observation:
shap_values = explainer.shap_values(feature_vector.reshape(1, -1))

# Group by source parameter
parameter_contributions = {}
for i, feature_name in enumerate(FEATURE_NAMES):
    base_param = extract_base_param(feature_name)
    parameter_contributions[base_param] = parameter_contributions.get(base_param, 0) + abs(shap_values[0][i])

# Normalize to sum to 1
total = sum(parameter_contributions.values())
if total > 0:
    parameter_contributions = {k: v/total for k, v in parameter_contributions.items()}

# Top features
sorted_features = sorted(enumerate(FEATURE_NAMES), key=lambda x: abs(shap_values[0][x[0]]), reverse=True)
top_features = [
    {"feature": FEATURE_NAMES[i], "contribution": float(shap_values[0][i]), "value": float(feature_vector[i])}
    for i, _ in sorted_features[:5]
]
```

### 7.2 Storage Format (JSONB in anomaly_scores.shap_values)

```json
{
  "top_features": [
    {"feature": "temperature_delta", "contribution": 0.23, "value": 15.2},
    {"feature": "humidity_rolling_std_6h", "contribution": 0.18, "value": 42.1},
    {"feature": "temperature_mean_1h", "contribution": 0.12, "value": 38.5},
    {"feature": "pressure_delta", "contribution": 0.08, "value": -2.3},
    {"feature": "wind_speed_max_24h", "contribution": 0.06, "value": 45.0}
  ],
  "parameter_contributions": {
    "temperature": 0.35,
    "humidity": 0.22,
    "pressure": 0.15,
    "wind_speed": 0.12,
    "wind_direction": 0.08,
    "rainfall": 0.05,
    "solar_radiation": 0.03
  }
}
```

### 7.3 Explanation Templates

```python
EXPLANATION_TEMPLATES = {
    'spike': 'Sudden spike detected in {param}: value jumped from {prev} to {current} ({sigma:.1f}σ deviation). Likely sensor malfunction or data transmission error.',
    'frozen': '{param} has been constant at {value} for {count} consecutive readings ({duration} minutes). Sensor may be stuck or disconnected.',
    'drift': '{param} has gradually shifted by {shift:.2f} over the last {hours}h, deviating from expected range (baseline: {baseline:.2f}±{baseline_std:.2f}). Possible sensor calibration drift.',
    'communication': 'Data gap of {gap_min} minutes detected. {n_missing} parameters missing. Possible communication failure or station downtime.',
    'multivariate': 'Correlated anomaly across {params}. Pattern inconsistent with normal weather variation. Investigate station-wide sensor array.',
}
```

---

## §8 — API Contract

All endpoints prefixed with `/api/v1`. All responses use `application/json`.

### 8.1 Observation Ingestion

#### `POST /observations`

```
Request:
{
  "station_code": "AWS_MUM_001",
  "observed_at": "2026-08-24T10:30:00+05:30",
  "temperature": 32.5,
  "humidity": 78.2,
  "pressure": 1008.3,
  "wind_speed": 4.2,
  "wind_direction": 225.0,
  "rainfall": 0.0,
  "solar_radiation": 650.0
}

Response 201:
{
  "observation_id": "uuid",
  "anomaly": {
    "fused_score": 0.12,
    "is_anomaly": false,
    "severity": "normal",
    "root_cause": null,
    "confidence": 0.92,
    "explanation": null
  }
}

Errors:
  400 - Invalid data / unknown station_code
  409 - Duplicate (station_id, observed_at)
```

#### `POST /observations/batch`

```
Request:
{
  "observations": [
    { "station_code": "...", "observed_at": "...", ... },
    ...
  ]
}

Response 201:
{
  "results": [
    { "observation_id": "uuid", "anomaly": { ... } },
    ...
  ],
  "accepted": 98,
  "rejected": 2,
  "errors": [
    { "index": 3, "error": "Unknown station_code: XYZ" }
  ]
}
```

### 8.2 Stations

#### `GET /stations`

```
Query: ?state=Maharashtra&district=Mumbai&status=healthy&page=1&limit=20

Response 200:
{
  "stations": [
    {
      "id": "uuid",
      "station_code": "AWS_MUM_001",
      "name": "Mumbai Colaba AWS",
      "latitude": 18.907,
      "longitude": 72.805,
      "state": "Maharashtra",
      "district": "Mumbai",
      "is_active": true,
      "overall_health": 85.3,
      "health_status": "healthy",
      "last_observation_at": "2026-08-24T10:30:00+05:30",
      "active_alerts": 0
    }
  ],
  "total": 150,
  "page": 1
}
```

#### `GET /stations/{station_id}`

```
Response 200:
{
  "station": { ...full station fields... },
  "health": {
    "overall": 85.3,
    "parameters": {
      "temperature": { "score": 92.0, "status": "healthy", "anomaly_streak": 0 },
      "humidity": { "score": 78.5, "status": "healthy", "anomaly_streak": 0 },
      ...
    }
  },
  "recent_alerts": [ ...last 10 alerts... ],
  "last_observation": { ...observation fields... }
}
```

#### `POST /stations`

```
Request:
{
  "station_code": "AWS_MUM_001",
  "name": "Mumbai Colaba AWS",
  "latitude": 18.907,
  "longitude": 72.805,
  "elevation_m": 11.0,
  "state": "Maharashtra",
  "district": "Mumbai"
}

Response 201:
{ "station": { ...all fields... } }
```

### 8.3 Anomalies

#### `GET /anomalies`

```
Query: ?station_id=uuid&severity=critical&root_cause=spike&from=2026-08-20&to=2026-08-24&page=1&limit=20

Response 200:
{
  "anomalies": [
    {
      "id": "uuid",
      "observation_id": "uuid",
      "station_code": "AWS_MUM_001",
      "station_name": "Mumbai Colaba AWS",
      "observed_at": "2026-08-24T10:30:00+05:30",
      "fused_score": 0.85,
      "severity": "critical",
      "root_cause": "spike",
      "confidence": 0.91,
      "explanation": "Sudden spike in temperature...",
      "scored_at": "2026-08-24T10:30:05+05:30"
    }
  ],
  "total": 42,
  "page": 1
}
```

#### `GET /anomalies/{anomaly_score_id}`

```
Response 200:
{
  "anomaly": {
    "id": "uuid",
    "qc_score": 0.28,
    "if_score": 0.72,
    "ae_score": 0.89,
    "fused_score": 0.85,
    "confidence": 0.91,
    "is_anomaly": true,
    "severity": "critical",
    "root_cause": "spike",
    "explanation": "...",
    "qc_flags": { ... },
    "shap_values": { "top_features": [...], "parameter_contributions": {...} }
  },
  "observation": { ...all observation fields... },
  "corrected_values": [
    {
      "parameter": "temperature",
      "raw_value": 55.2,
      "corrected_value": 33.1,
      "correction_method": "temporal_median",
      "correction_confidence": 0.87
    }
  ]
}
```

### 8.4 Alerts

#### `GET /alerts`

```
Query: ?station_id=uuid&severity=critical&is_resolved=false&from=&to=&page=1&limit=20

Response 200:
{
  "alerts": [
    {
      "id": "uuid",
      "station_id": "uuid",
      "station_name": "Mumbai Colaba AWS",
      "alert_type": "anomaly",
      "severity": "critical",
      "title": "Temperature spike at Mumbai Colaba AWS",
      "description": "...",
      "parameter": "temperature",
      "is_resolved": false,
      "created_at": "2026-08-24T10:30:05+05:30"
    }
  ],
  "total": 15,
  "page": 1
}
```

#### `PATCH /alerts/{alert_id}/resolve`

```
Response 200:
{
  "alert": { ...alert with is_resolved=true, resolved_at=now()... }
}
```

### 8.5 Sensor Health

#### `GET /health/{station_id}`

```
Response 200:
{
  "station_id": "uuid",
  "overall_health": 85.3,
  "overall_status": "healthy",
  "parameters": {
    "temperature": {
      "health_score": 92.0,
      "status": "healthy",
      "anomaly_streak": 0,
      "last_updated": "2026-08-24T10:30:05+05:30"
    },
    "humidity": { ... },
    ...
  }
}
```

#### `GET /health/{station_id}/history`

```
Query: ?parameter=temperature&from=2026-08-20&to=2026-08-24

Response 200:
{
  "history": [
    {
      "recorded_at": "2026-08-24T10:30:05+05:30",
      "parameter": "temperature",
      "health_score": 92.0,
      "status": "healthy"
    },
    ...
  ]
}
```

### 8.6 Dashboard Summary

#### `GET /dashboard/summary`

```
Response 200:
{
  "total_stations": 150,
  "active_stations": 142,
  "anomalies_24h": 23,
  "critical_alerts": 3,
  "avg_health": 87.2,
  "stations_needing_maintenance": 5,
  "observations_24h": 13488
}
```

### 8.7 Demo Endpoints

#### `POST /demo/inject-anomaly`

```
Request:
{
  "station_id": "uuid",
  "anomaly_type": "spike",          // spike | frozen | drift | missing | multivariate
  "parameters": ["temperature"],    // optional, defaults to random
  "duration_minutes": 30,           // optional, defaults to 15
  "magnitude": 3.0                  // optional, multiplier for spike/drift magnitude
}

Response 200:
{
  "injected_observations": ["uuid1", "uuid2", ...],
  "anomaly_type": "spike",
  "affected_parameters": ["temperature"],
  "message": "Injected 2 spike anomalies on temperature"
}
```

#### `POST /demo/generate-data`

```
Request:
{
  "station_id": "uuid",
  "hours": 24,
  "interval_min": 15       // optional, defaults to station.expected_interval_min
}

Response 200:
{
  "observation_count": 96,
  "from": "2026-08-23T10:30:00+05:30",
  "to": "2026-08-24T10:30:00+05:30",
  "message": "Generated 96 normal observations"
}
```

### 8.8 WebSocket

#### `WS /ws/live`

```
# Client → Server (subscribe message):
{
  "action": "subscribe",
  "station_ids": ["uuid1", "uuid2"]   // optional, null = all stations
}

# Server → Client (event messages):
{
  "type": "anomaly",
  "data": {
    "observation_id": "uuid",
    "station_code": "AWS_MUM_001",
    "station_name": "Mumbai Colaba AWS",
    "fused_score": 0.85,
    "severity": "critical",
    "root_cause": "spike",
    "explanation": "...",
    "observed_at": "2026-08-24T10:30:00+05:30"
  }
}

{
  "type": "alert",
  "data": { ...alert object... }
}

{
  "type": "health_update",
  "data": {
    "station_id": "uuid",
    "parameter": "temperature",
    "health_score": 45.2,
    "status": "degraded",
    "previous_status": "healthy"
  }
}
```

---

## §9 — Synthetic Data Generation

### 9.1 Normal Data Profiles (for demo/generate-data)

Generate realistic weather data using these base profiles + noise:

```python
NORMAL_PROFILES = {
    'temperature': {
        'base': 30.0,        # base value
        'diurnal_amp': 5.0,  # amplitude of daily cycle
        'noise_std': 0.5,    # random noise std
        'peak_hour': 14,     # hour of daily peak
    },
    'humidity': {
        'base': 70.0,
        'diurnal_amp': 15.0,
        'noise_std': 2.0,
        'peak_hour': 5,      # humidity peaks at dawn
    },
    'pressure': {
        'base': 1010.0,
        'diurnal_amp': 2.0,
        'noise_std': 0.5,
        'peak_hour': 10,
    },
    'wind_speed': {
        'base': 3.0,
        'diurnal_amp': 2.0,
        'noise_std': 1.0,
        'peak_hour': 15,
    },
    'wind_direction': {
        'base': 225.0,
        'diurnal_amp': 30.0,
        'noise_std': 10.0,
        'peak_hour': 12,
    },
    'rainfall': {
        'base': 0.0,
        'probability': 0.05,  # 5% chance of rain each interval
        'rain_range': [0.2, 15.0],
    },
    'solar_radiation': {
        'base': 0.0,
        'max_value': 900.0,
        'sunrise': 6,
        'sunset': 18,
    },
}

def generate_value(param, hour):
    profile = NORMAL_PROFILES[param]
    if param == 'rainfall':
        return random.uniform(*profile['rain_range']) if random.random() < profile['probability'] else 0.0
    elif param == 'solar_radiation':
        if profile['sunrise'] <= hour <= profile['sunset']:
            progress = (hour - profile['sunrise']) / (profile['sunset'] - profile['sunrise'])
            return profile['max_value'] * math.sin(progress * math.pi) + random.gauss(0, 20)
        return 0.0
    else:
        diurnal = profile['diurnal_amp'] * math.sin(2 * math.pi * (hour - profile['peak_hour'] + 6) / 24)
        return profile['base'] + diurnal + random.gauss(0, profile['noise_std'])
```

### 9.2 Anomaly Injection Recipes

```python
def inject_spike(observation, params, magnitude=3.0):
    """Add a sudden jump to specified parameters."""
    for p in params:
        std = NORMAL_PROFILES[p].get('noise_std', 1.0)
        observation[p] += magnitude * 10 * std * random.choice([-1, 1])
    return observation

def inject_frozen(station_id, params, duration_minutes=60):
    """Repeat the same value for target params only; other params get fresh normal values."""
    station = get_station(station_id)
    count = duration_minutes // station.expected_interval_min
    last_obs = get_last_observation(station_id)
    frozen_values = {p: last_obs[p] for p in params}  # snapshot values to freeze
    for i in range(count):
        timestamp = last_obs.observed_at + timedelta(minutes=station.expected_interval_min * (i + 1))
        hour = timestamp.hour + timestamp.minute / 60
        obs = {}
        for p in PARAMETERS:
            if p in frozen_values:
                obs[p] = frozen_values[p]  # held constant
            else:
                obs[p] = generate_value(p, hour)  # fresh normal value
        obs['station_code'] = station.station_code
        obs['observed_at'] = timestamp
        ingest_observation(obs)  # full pipeline: score → alert → WS

def inject_drift(station_id, params, duration_minutes=360, magnitude=2.0):
    """Gradually shift values over time."""
    count = duration_minutes // station.expected_interval_min
    for i in range(count):
        obs = generate_normal_observation(station_id, time_offset=i)
        for p in params:
            drift = magnitude * NORMAL_PROFILES[p].get('noise_std', 1.0) * (i / count)
            obs[p] += drift
        insert_observation(obs)

def inject_missing(station_id, duration_minutes=30):
    """Create a gap in observations (no data sent)."""
    # Simply don't insert any observations for the duration.
    # The timestamp gap will be detected by QC.
    pass  # No-op for injection; the absence IS the anomaly

def inject_multivariate(station_id, params, magnitude=2.0):
    """Shift multiple parameters simultaneously in correlated way."""
    obs = generate_normal_observation(station_id)
    for p in params:
        obs[p] += magnitude * NORMAL_PROFILES[p].get('noise_std', 1.0) * 5
    insert_observation(obs)
```

---

## §10 — Frontend Specification

### 10.1 Tech Stack

- React 18 + Vite
- TailwindCSS for styling
- Recharts for time-series and bar charts
- React-Leaflet for station map
- Lucide React for icons
- React Router for navigation

### 10.2 Pages

| Route | Component | Data Source |
|-------|-----------|-------------|
| `/` | Dashboard | GET /dashboard/summary, GET /stations, GET /alerts, WS |
| `/stations` | StationList | GET /stations |
| `/stations/:id` | StationDetail | GET /stations/:id, GET /anomalies, GET /health/:id/history |
| `/anomalies` | AnomalyList | GET /anomalies |
| `/anomalies/:id` | AnomalyDetail | GET /anomalies/:id |
| `/alerts` | AlertList | GET /alerts |
| `/demo` | DemoControls | POST /demo/* |

### 10.3 Dashboard Layout

```
┌────────────────────────────────────────────────────────┐
│  Header: SkyGuard AI — Weather Station Anomaly Monitor │
├───────┬───────┬───────┬───────┬───────┬────────────────┤
│Active │Anom.  │Crit.  │ Avg   │Maint. │ Obs. 24h      │
│Stn:142│24h:23 │Alert:3│Hlth:87│Need:5 │ Count: 13488  │
├───────┴───────┴───────┴───────┴───────┴────────────────┤
│                                                         │
│  ┌─────────────────────────┐  ┌──────────────────────┐ │
│  │    Station Map           │  │   Live Alert Feed    │ │
│  │  (Leaflet, color-coded   │  │   (WS-driven list)   │ │
│  │   markers by health)     │  │                      │ │
│  │                          │  │   🔴 Spike: Temp...  │ │
│  │  🟢 = healthy            │  │   🟡 Drift: Hum...  │ │
│  │  🟡 = degraded           │  │   🔴 Missing: ...   │ │
│  │  🔴 = critical           │  │                      │ │
│  └─────────────────────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 10.4 Color Scheme

```
healthy:       #22c55e (green-500)
degraded:      #f59e0b (amber-500)
maintenance:   #ef4444 (red-500)
critical:      #dc2626 (red-600)
normal badge:  #6b7280 (gray-500)
warning badge: #f59e0b (amber-500)
critical badge:#ef4444 (red-500)
```

---

## §11 — Environment Variables

```env
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[password]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://ncjejgcosipagizirjxs.supabase.co
SUPABASE_ANON_KEY=<from supabase dashboard>
ML_MODEL_DIR=../../ml/models
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Frontend (.env)
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/api/v1/ws/live
```

---

## §12 — Pre-trained Model Bootstrap

For the SIH demo, the training pipeline should:

1. Generate 7 days of synthetic normal data for 5 stations (5 × 672 = 3360 observations)
2. Train Isolation Forest on the full feature vectors
3. Train Autoencoder on the compact feature vectors
4. Save models + scalers + thresholds to `ml/models/`
5. Train per-station cross-parameter regression models for corrected-value estimation

This can be a one-time script: `ml/training/bootstrap.py`

```python
"""Bootstrap script: generates training data, trains all models, saves artifacts.
Run once before starting the backend:
  python -m ml.training.bootstrap
"""
```

---

## §13 — Critical Implementation Notes

1. **Async everywhere**: Use `asyncpg` + SQLAlchemy async. The observation ingestion path must be fast.
2. **ML model loading**: Load models once at startup via FastAPI lifespan, keep in app state.
3. **Health state caching**: Keep current health state in memory (dict), persist to DB on each update. On startup, load latest health state from DB.
4. **WebSocket manager**: Use a simple `ConnectionManager` class with `broadcast()` method. Filter by station_id subscriptions.
5. **SHAP computation**: Only compute SHAP for anomalous observations (`is_anomaly=True`) to save compute.
6. **Correction estimation**: Only attempt for `fused_score >= 0.6 AND confidence >= 0.7`.
7. **Batch ingestion**: Process observations sequentially within a batch (order matters for temporal features). Use a single transaction.
8. **Demo data**: Pre-seed 5 stations covering different Indian cities. Hardcode their station_codes and coordinates.

### Demo Stations (pre-seed)

| station_code | name | lat | lon | state | district |
|-------------|------|-----|-----|-------|----------|
| AWS_MUM_001 | Mumbai Colaba | 18.907 | 72.805 | Maharashtra | Mumbai |
| AWS_DEL_001 | Delhi Safdarjung | 28.585 | 77.208 | Delhi | New Delhi |
| AWS_CHN_001 | Chennai Nungambakkam | 13.066 | 80.251 | Tamil Nadu | Chennai |
| AWS_KOL_001 | Kolkata Alipore | 22.534 | 88.339 | West Bengal | Kolkata |
| AWS_BLR_001 | Bengaluru HAL | 12.950 | 77.668 | Karnataka | Bengaluru |

---

*End of original handoff specification.*

---

## §14 — Addendum: Ambiguity Resolutions (2026-08-24 Patch)

### 14.1 Per-Parameter Anomaly Attribution (supplements §4.2)

The health scorer needs to know which *specific parameters* are anomalous in a given observation. Derive as follows:

```python
def get_flagged_parameters(qc_flags: dict, shap_values: dict) -> set[str]:
    """
    A parameter is 'flagged' if:
      (a) it has ANY QC flag in qc_flags[param], OR
      (b) its SHAP parameter_contribution >= 0.15
    Return the union.
    """
    flagged = set()

    # (a) QC-flagged
    for param in PARAMETERS:
        if qc_flags.get(param, []):
            flagged.add(param)

    # (b) SHAP-flagged (threshold: 0.15 of normalized contribution)
    contributions = shap_values.get('parameter_contributions', {})
    for param, contrib in contributions.items():
        if contrib >= 0.15:
            flagged.add(param)

    return flagged
```

### 14.2 Per-Parameter Autoencoder Error (supplements §4.2)

The autoencoder input is 14 dims: indices `[0..6]` = normalized raw values, indices `[7..13]` = deltas. Parameter `i` (by `PARAMETERS` list order) maps to dims `i` and `i+7`.

```python
def ae_per_param_error(reconstructed: np.ndarray, original: np.ndarray, param: str) -> float:
    """
    Compute per-parameter reconstruction error from the autoencoder.
    Returns mean squared error across the 2 dims belonging to this parameter.
    """
    i = PARAMETERS.index(param)
    raw_err = (original[i] - reconstructed[i]) ** 2
    delta_err = (original[i + 7] - reconstructed[i + 7]) ** 2
    return (raw_err + delta_err) / 2.0
```

Usage in health scorer (§4.2): compare `ae_per_param_error(param)` against threshold `0.7` (scaled relative to `threshold_95th_percentile`):

```python
param_ae = ae_per_param_error(reconstructed, original, param)
scaled_param_ae = min(1.0, param_ae / (threshold_95th_percentile / 7))  # per-dim share of threshold
if scaled_param_ae > 0.7:
    penalty += 1.5
```

> **CALIBRATION NOTE**: The `/ 7` divisor assumes equal error contribution per
> parameter. In practice, temperature and pressure typically dominate AE
> reconstruction error while wind_direction contributes much less. If health
> scores appear too harsh or too lenient for specific parameters during testing,
> replace the uniform `/ 7` with per-parameter thresholds computed from the
> training set: `per_param_threshold[p] = np.percentile(training_errors[:, i], 95)`
> for each parameter index `i`. This is a tuning constant, not a formula bug.

### 14.3 Adaptive Baseline for Drift Detection (supplements §5 Rule 4)

Replace all references to `baseline_mean_30d` / `baseline_std_30d` with this adaptive function:

```python
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class Baseline:
    mean: float
    std: float
    observation_count: int

def get_baseline(station_id: str, param: str, current_time=None) -> Baseline | None:
    """
    Compute baseline statistics from all observations OLDER than 24h.
    Returns None if fewer than 3 days of history exist.

    This works with 7-day bootstrap: baseline = days 1-6 (excl last 24h).
    In production with 60+ days: baseline = all history except last 24h.
    """
    if current_time is None:
        current_time = utcnow()

    cutoff = current_time - timedelta(hours=24)

    # Query: all observations for this station+param older than 24h
    values = query_param_values(station_id, param, before=cutoff)

    if len(values) == 0:
        return None

    # Check minimum history: earliest obs must be >= 3 days before cutoff
    earliest = get_earliest_observation_time(station_id)
    if (cutoff - earliest).total_seconds() < 3 * 86400:
        return None  # not enough baseline history

    return Baseline(
        mean=np.mean(values),
        std=np.std(values),
        observation_count=len(values)
    )
```

Also applies to `is_drifting()` in §4.2 health scorer — use the same `get_baseline()` function.

### 14.4 Demo Injection Pipeline (supplements §8.7, §9.2)

**All injected observations go through the full ingestion pipeline.** This is confirmed and intentional:

```
inject_* → build observation dict → call ingest_observation()
                                          ↓
                                   same path as POST /observations:
                                   store raw → QC → feature eng → ML score →
                                   fusion → root cause → health update →
                                   correction → alert generation → WS broadcast
```

This means:
1. `inject_spike` calls `ingest_observation()`, not `insert_observation()`
2. `inject_frozen` calls `ingest_observation()` (already fixed above in §9.2)
3. `inject_drift` calls `ingest_observation()`
4. `inject_multivariate` calls `ingest_observation()`
5. `inject_missing` is the exception — it inserts nothing (the absence IS the anomaly; the next real/injected observation will detect the timestamp gap)

The `ingest_observation()` function is the internal version of what `POST /observations` does:

```python
async def ingest_observation(obs_dict: dict) -> tuple[Observation, AnomalyScore]:
    """
    Full ingestion pipeline. Used by both the REST endpoint and demo injectors.
    1. Resolve station_code → station_id
    2. Insert into observations table
    3. Run QC checks
    4. Extract features
    5. Run IF + AE scoring
    6. Fuse scores
    7. Classify root cause
    8. Update sensor health
    9. Estimate corrected values
    10. Create alerts if needed
    11. Broadcast via WebSocket
    Returns (observation, anomaly_score)
    """
    ...
```

### 14.5 Updated inject_spike and inject_drift (supplements §9.2)

These must also route through the full pipeline:

```python
def inject_spike(station_id, params, magnitude=3.0):
    """Inject a single spiked observation through the full pipeline."""
    station = get_station(station_id)
    last_obs = get_last_observation(station_id)
    timestamp = last_obs.observed_at + timedelta(minutes=station.expected_interval_min)
    hour = timestamp.hour + timestamp.minute / 60
    obs = {p: generate_value(p, hour) for p in PARAMETERS}
    for p in params:
        std = NORMAL_PROFILES[p].get('noise_std', 1.0)
        obs[p] += magnitude * 10 * std * random.choice([-1, 1])
    obs['station_code'] = station.station_code
    obs['observed_at'] = timestamp
    ingest_observation(obs)  # full pipeline

def inject_drift(station_id, params, duration_minutes=360, magnitude=2.0):
    """Inject gradually drifting observations through the full pipeline."""
    station = get_station(station_id)
    count = duration_minutes // station.expected_interval_min
    last_obs = get_last_observation(station_id)
    for i in range(count):
        timestamp = last_obs.observed_at + timedelta(minutes=station.expected_interval_min * (i + 1))
        hour = timestamp.hour + timestamp.minute / 60
        obs = {p: generate_value(p, hour) for p in PARAMETERS}
        for p in params:
            drift = magnitude * NORMAL_PROFILES[p].get('noise_std', 1.0) * (i / count)
            obs[p] += drift
        obs['station_code'] = station.station_code
        obs['observed_at'] = timestamp
        ingest_observation(obs)  # full pipeline

def inject_multivariate(station_id, params=None, magnitude=2.0):
    """Inject a single observation with correlated shifts across >= 3 params."""
    station = get_station(station_id)
    if params is None:
        params = random.sample(PARAMETERS, k=min(4, len(PARAMETERS)))
    last_obs = get_last_observation(station_id)
    timestamp = last_obs.observed_at + timedelta(minutes=station.expected_interval_min)
    hour = timestamp.hour + timestamp.minute / 60
    obs = {p: generate_value(p, hour) for p in PARAMETERS}
    for p in params:
        obs[p] += magnitude * NORMAL_PROFILES[p].get('noise_std', 1.0) * 5
    obs['station_code'] = station.station_code
    obs['observed_at'] = timestamp
    ingest_observation(obs)  # full pipeline
```

---

*End of addendum. All four ambiguities resolved. Flash: proceed with §0 task list.*
