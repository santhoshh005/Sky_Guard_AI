"""Fast Training and evaluation script for SkyGuard AI ML models.
Vectorized feature extraction, training Isolation Forest, Autoencoder, and 35 regression models.
Evaluates end-to-end anomaly detection on synthetic test set and reports F1-score.
"""
import os
import sys
import pickle
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, precision_score, recall_score

backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.data_generator import (
    DEMO_STATIONS,
    NORMAL_PROFILES,
    PARAMETERS,
    create_drift_observations,
    create_frozen_observations,
    create_multivariate_observation,
    create_spike_observation,
    generate_time_series,
)
from app.services.feature_engineer import FEATURE_NAMES, FeatureEngineer
from app.services.quality_checks import QualityChecker

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def extract_dataset_features(series: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """Fast vectorized feature extraction over a continuous time series."""
    df = pd.DataFrame(series)
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
    df = df.sort_values("observed_at").reset_index(drop=True)

    n_samples = len(df)
    full_matrix = np.zeros((n_samples, len(FEATURE_NAMES)), dtype=np.float64)
    compact_matrix = np.zeros((n_samples, 14), dtype=np.float64)

    # 1. Raw values (indices 0..6)
    for i, p in enumerate(PARAMETERS):
        full_matrix[:, i] = df[p].fillna(0.0).values
        compact_matrix[:, i] = df[p].fillna(0.0).values

    # 2. Rolling stats (1h = 4, 6h = 24, 24h = 96)
    col_idx = 7
    window_sizes = [4, 24, 96]
    for p in PARAMETERS:
        series_vals = df[p]
        for w in window_sizes:
            # Mean
            full_matrix[:, col_idx] = series_vals.rolling(w, min_periods=1).mean().fillna(0.0).values
            col_idx += 1
            # Std
            full_matrix[:, col_idx] = series_vals.rolling(w, min_periods=2).std().fillna(0.0).values
            col_idx += 1
            # Min
            full_matrix[:, col_idx] = series_vals.rolling(w, min_periods=1).min().fillna(0.0).values
            col_idx += 1
            # Max
            full_matrix[:, col_idx] = series_vals.rolling(w, min_periods=1).max().fillna(0.0).values
            col_idx += 1

    # 3. Deltas
    for i, p in enumerate(PARAMETERS):
        delta = df[p].diff().fillna(0.0).values
        full_matrix[:, col_idx] = delta
        compact_matrix[:, 7 + i] = delta
        col_idx += 1

    # 4. Correlations (rolling 96)
    r_th = df["temperature"].rolling(96, min_periods=4).corr(df["humidity"]).fillna(0.0).values
    r_pw = df["pressure"].rolling(96, min_periods=4).corr(df["wind_speed"]).fillna(0.0).values
    r_st = df["solar_radiation"].rolling(96, min_periods=4).corr(df["temperature"]).fillna(0.0).values
    full_matrix[:, col_idx] = r_th
    full_matrix[:, col_idx + 1] = r_pw
    full_matrix[:, col_idx + 2] = r_st
    col_idx += 3

    # 5. Temporal
    hours = df["observed_at"].dt.hour + df["observed_at"].dt.minute / 60.0
    full_matrix[:, col_idx] = hours / 24.0
    full_matrix[:, col_idx + 1] = ((hours >= 6.0) & (hours <= 18.0)).astype(float)
    col_idx += 2

    # 6. Missingness
    for p in PARAMETERS:
        full_matrix[:, col_idx] = df[p].isna().astype(float)
        col_idx += 1

    return full_matrix, compact_matrix


def train_isolation_forest(X_full: np.ndarray) -> Tuple[IsolationForest, StandardScaler]:
    print("[1/3] Training Isolation Forest...", flush=True)
    X_clean = np.nan_to_num(X_full, nan=0.0, posinf=0.0, neginf=0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clean)

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_scaled)
    print(f"  [OK] Isolation Forest fitted on {X_scaled.shape}", flush=True)
    return model, scaler


def train_autoencoder(X_compact: np.ndarray) -> Tuple[MLPRegressor, StandardScaler, float, Dict[str, float]]:
    print("[2/3] Training Autoencoder (14 -> 8 -> 4 -> 8 -> 14)...", flush=True)
    X_clean = np.nan_to_num(X_compact, nan=0.0, posinf=0.0, neginf=0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clean)

    model = MLPRegressor(
        hidden_layer_sizes=(8, 4, 8),
        activation="relu",
        solver="adam",
        max_iter=400,
        random_state=42,
        early_stopping=True,
        n_iter_no_change=15
    )
    model.fit(X_scaled, X_scaled)

    preds = model.predict(X_scaled)
    errors = np.mean((X_scaled - preds) ** 2, axis=1)
    threshold_95 = float(np.percentile(errors, 95))

    per_param_thresholds = {}
    for i, p in enumerate(PARAMETERS):
        dim_err = (X_scaled[:, i] - preds[:, i]) ** 2 + (X_scaled[:, i + 7] - preds[:, i + 7]) ** 2
        per_param_thresholds[p] = float(np.percentile(dim_err / 2.0, 95))

    print(f"  [OK] Autoencoder trained. 95th percentile MSE: {threshold_95:.6f}", flush=True)
    return model, scaler, threshold_95, per_param_thresholds


def train_cross_parameter_regressions(station_datasets: Dict[str, List[Dict]]) -> Dict[Tuple[str, str], Dict]:
    print("[3/3] Training 35 cross-parameter regression models...", flush=True)
    reg_models = {}

    for stn in DEMO_STATIONS:
        code = stn["station_code"]
        data = station_datasets.get(code, [])
        df = pd.DataFrame(data)

        for target_p in PARAMETERS:
            feats = [p for p in PARAMETERS if p != target_p]
            X = df[feats].values
            y = df[target_p].values

            split = int(len(X) * 0.8)
            X_tr, X_te = X[:split], X[split:]
            y_tr, y_te = y[:split], y[split:]

            reg = LinearRegression()
            reg.fit(X_tr, y_tr)
            r2 = float(reg.score(X_te, y_te))

            reg_models[(code, target_p)] = {
                "model": reg,
                "r_squared": max(0.0, min(1.0, r2 if not np.isnan(r2) else 0.6)),
                "feature_params": feats,
            }

    print(f"  [OK] Trained {len(reg_models)} regression models.", flush=True)
    return reg_models


def evaluate_benchmark(
    if_model: IsolationForest,
    if_scaler: StandardScaler,
    ae_model: MLPRegressor,
    ae_scaler: StandardScaler,
    ae_threshold: float,
    regression_models: Dict
):
    print("\n--- Pipeline Evaluation Benchmark ---", flush=True)
    stn_code = "AWS_MUM_001"
    t_start = datetime.now(timezone.utc) - timedelta(days=3)
    clean_obs = generate_time_series(stn_code, t_start, 250, interval_min=15)
    
    test_samples: List[Tuple[Dict, int, str]] = []
    # 200 normal observations
    for o in clean_obs[:200]:
        test_samples.append((o, 0, "normal"))

    # Sequential anomalies starting at obs 200
    curr_t = t_start + timedelta(minutes=15 * 200)

    # 1. Spikes (15)
    for i in range(15):
        curr_t += timedelta(minutes=15)
        p = random.choice(["temperature", "humidity", "pressure", "wind_speed"])
        obs = create_spike_observation(stn_code, curr_t, [p], magnitude=3.5)
        test_samples.append((obs, 1, "spike"))

    # 2. Frozen (15)
    frozen_obs = create_frozen_observations(stn_code, curr_t + timedelta(minutes=15), 15, ["temperature"])
    for o in frozen_obs:
        curr_t += timedelta(minutes=15)
        o["observed_at"] = curr_t.isoformat()
        test_samples.append((o, 1, "frozen"))

    # 3. Drift (20)
    drift_obs = create_drift_observations(stn_code, curr_t + timedelta(minutes=15), 20, ["temperature"], magnitude=3.0)
    for o in drift_obs:
        curr_t += timedelta(minutes=15)
        o["observed_at"] = curr_t.isoformat()
        test_samples.append((o, 1, "drift"))

    # 4. Multivariate (15)
    for i in range(15):
        curr_t += timedelta(minutes=15)
        obs = create_multivariate_observation(stn_code, curr_t, ["temperature", "humidity", "pressure"], magnitude=3.0)
        test_samples.append((obs, 1, "multivariate"))

    # 5. Missing / Communication (10)
    for i in range(10):
        curr_t += timedelta(minutes=15)
        obs = {"station_code": stn_code, "observed_at": curr_t.isoformat(), "temperature": None, "humidity": None, "pressure": None}
        test_samples.append((obs, 1, "communication"))

    y_true = []
    y_pred = []
    history = list(clean_obs[:30])

    for obs, label, cause in test_samples:
        y_true.append(label)
        hist_window = history[-96:]
        full_vec, compact_vec, _ = FeatureEngineer.extract_features(obs, hist_window)
        qc_score, qc_flags = QualityChecker.run_checks(obs, hist_window)

        scaled_full = if_scaler.transform(np.nan_to_num(full_vec.reshape(1, -1)))
        raw_if = float(if_model.decision_function(scaled_full)[0])
        # Inlier raw_if > 0 -> if_score near 0. Outlier raw_if < 0 -> if_score up to 1.0
        if_score = float(max(0.0, min(1.0, 1.0 / (1.0 + np.exp(raw_if * 25.0)))))

        scaled_compact = ae_scaler.transform(np.nan_to_num(compact_vec.reshape(1, -1)))
        recon = ae_model.predict(scaled_compact)[0]
        mse = float(np.mean((scaled_compact[0] - recon) ** 2))
        # Non-linear scaling: normal points (mse < thresh) stay small (<0.2), anomalies scale to 1.0
        ratio = mse / max(1e-6, ae_threshold)
        ae_score = float(min(1.0, ratio ** 2 if ratio < 1.0 else min(1.0, 0.5 + 0.5 * ratio)))

        # 3-channel fusion: 0.35*QC + 0.30*IF + 0.35*AE
        has_qc = any(len(v) > 0 for k, v in qc_flags.items() if k != "qc_score")
        effective_qc = 1.0 if has_qc else float(qc_score)

        fused = 0.35 * effective_qc + 0.30 * if_score + 0.35 * ae_score
        is_anom = 1 if (fused >= 0.5 or has_qc) else 0
        y_pred.append(is_anom)

        if label == 0:
            history.append(obs)

    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    print(f"Precision: {prec * 100:.2f}%", flush=True)
    print(f"Recall:    {rec * 100:.2f}%", flush=True)
    print(f"F1-Score:  {f1 * 100:.2f}%", flush=True)

    if f1 >= 0.90:
        print("  [PASS] Target F1 >= 90% ACHIEVED!", flush=True)
    else:
        print(f"  [INFO] F1 score is {f1 * 100:.2f}%", flush=True)


def main():
    print("==================================================", flush=True)
    print("  SkyGuard AI — Fast ML Pipeline Training & Eval  ", flush=True)
    print("==================================================", flush=True)

    now = datetime.now(timezone.utc) - timedelta(days=7)
    station_datasets = {}
    X_full_list, X_compact_list = [], []

    for stn in DEMO_STATIONS:
        code = stn["station_code"]
        series = generate_time_series(code, now, 672, interval_min=15, elevation_m=stn.get("elevation_m", 0.0))
        station_datasets[code] = series
        f_mat, c_mat = extract_dataset_features(series)
        X_full_list.append(f_mat)
        X_compact_list.append(c_mat)

    X_full = np.vstack(X_full_list)
    X_compact = np.vstack(X_compact_list)
    print(f"[*] Training matrices: Full {X_full.shape}, Compact {X_compact.shape}", flush=True)

    if_model, if_scaler = train_isolation_forest(X_full)
    ae_model, ae_scaler, ae_threshold, per_param_ae = train_autoencoder(X_compact)
    reg_models = train_cross_parameter_regressions(station_datasets)

    print("\n[*] Saving model artifacts to", MODEL_DIR, flush=True)
    with open(MODEL_DIR / "isolation_forest.pkl", "wb") as f:
        pickle.dump(if_model, f)
    with open(MODEL_DIR / "if_scaler.pkl", "wb") as f:
        pickle.dump(if_scaler, f)
    with open(MODEL_DIR / "autoencoder.pkl", "wb") as f:
        pickle.dump(ae_model, f)
    with open(MODEL_DIR / "ae_scaler.pkl", "wb") as f:
        pickle.dump(ae_scaler, f)
    with open(MODEL_DIR / "ae_threshold.pkl", "wb") as f:
        pickle.dump({"threshold": ae_threshold, "per_param": per_param_ae}, f)
    with open(MODEL_DIR / "regression_models.pkl", "wb") as f:
        pickle.dump(reg_models, f)

    print("  [OK] All 6 model artifacts saved successfully.", flush=True)
    evaluate_benchmark(if_model, if_scaler, ae_model, ae_scaler, ae_threshold, reg_models)


if __name__ == "__main__":
    main()
