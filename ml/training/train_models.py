"""Train SkyGuard AI models and benchmark the production pipeline.

Usage (from the repository root or backend/):
    python -m ml.training.train_models            # train + benchmark
    python -m ml.training.train_models --eval-only

Training data: synthetic clean telemetry for the 5 demo stations (14 days each).
Features are produced by the *same* FeatureEngineer used in production.

Benchmark: held-out synthetic data (different random seed) for all stations, scored with
``app.services.pipeline.score_observation`` - the exact production code path. Anomalous
readings stay in the history afterwards, as they do in production, so post-fault false
positives are counted.
"""
import argparse
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent.parent
for p in (ROOT / "backend", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services.data_generator import (  # noqa: E402
    DEMO_STATIONS,
    PARAMETERS,
    create_drift_observations,
    create_frozen_observations,
    create_multivariate_observation,
    create_spike_observation,
    generate_time_series,
)
from app.services.drift import DriftDetector  # noqa: E402
from app.services.feature_engineer import FeatureEngineer  # noqa: E402
from app.services.pipeline import score_observation  # noqa: E402

MODEL_DIR = ROOT / "ml" / "models"
RESULTS_PATH = ROOT / "ml" / "benchmark_results.json"
HISTORY = 110  # same history depth the API fetches
TRAIN_DAYS = 14
INTERVAL = 15


def extract_dataset_features(series: List[Dict], longitude: float) -> Tuple[np.ndarray, np.ndarray]:
    full, compact = [], []
    for i, obs in enumerate(series):
        f, c, _ = FeatureEngineer.extract_features(obs, series[max(0, i - HISTORY):i], longitude=longitude)
        full.append(f)
        compact.append(c)
    return np.asarray(full), np.asarray(compact)


def train_isolation_forest(X_full: np.ndarray):
    print("[1/3] Training Isolation Forest...", flush=True)
    scaler = StandardScaler()
    X = scaler.fit_transform(np.nan_to_num(X_full))
    model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42, n_jobs=-1)
    model.fit(X)
    print(f"  [OK] fitted on {X.shape}", flush=True)
    return model, scaler


def train_autoencoder(X_compact: np.ndarray):
    print("[2/3] Training Autoencoder (14 -> 8 -> 4 -> 8 -> 14)...", flush=True)
    scaler = StandardScaler()
    X = scaler.fit_transform(np.nan_to_num(X_compact))
    model = MLPRegressor(
        hidden_layer_sizes=(8, 4, 8), activation="relu", solver="adam", max_iter=400,
        random_state=42, early_stopping=True, n_iter_no_change=15,
    )
    model.fit(X, X)
    preds = model.predict(X)
    errors = np.mean((X - preds) ** 2, axis=1)
    threshold_95 = float(np.percentile(errors, 95))
    threshold_calib = float(np.percentile(errors, 99.5))
    per_param = {
        p: float(np.percentile(((X[:, i] - preds[:, i]) ** 2 + (X[:, i + 7] - preds[:, i + 7]) ** 2) / 2.0, 95))
        for i, p in enumerate(PARAMETERS)
    }
    print(f"  [OK] reconstruction MSE p95={threshold_95:.5f} p99.5={threshold_calib:.5f}", flush=True)
    return model, scaler, threshold_calib, threshold_95, per_param


def train_cross_parameter_regressions(datasets: Dict[str, List[Dict]]):
    print("[3/3] Training cross-parameter regressions...", flush=True)
    models = {}
    for code, data in datasets.items():
        for target in PARAMETERS:
            feats = [p for p in PARAMETERS if p != target]
            X = np.asarray([[o[f] for f in feats] for o in data], dtype=float)
            y = np.asarray([o[target] for o in data], dtype=float)
            split = int(len(X) * 0.8)
            reg = LinearRegression().fit(X[:split], y[:split])
            resid = y[split:] - reg.predict(X[split:])
            r2 = float(reg.score(X[split:], y[split:])) if np.std(y[split:]) > 0 else 0.0
            models[(code, target)] = {
                "model": reg,
                "r_squared": float(np.clip(np.nan_to_num(r2), 0.0, 1.0)),
                "residual_std": float(np.std(resid, ddof=1)),
                "feature_params": feats,
            }
    print(f"  [OK] trained {len(models)} regression models", flush=True)
    return models


def train() -> None:
    random.seed(42)
    np.random.seed(42)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    datasets, X_full, X_compact = {}, [], []
    for stn in DEMO_STATIONS:
        series = generate_time_series(
            stn["station_code"], start, TRAIN_DAYS * 96, INTERVAL, elevation_m=stn["elevation_m"]
        )
        datasets[stn["station_code"]] = series
        f, c = extract_dataset_features(series, stn["longitude"])
        X_full.append(f)
        X_compact.append(c)
        print(f"  features for {stn['station_code']}: {f.shape}", flush=True)
    X_full, X_compact = np.vstack(X_full), np.vstack(X_compact)

    if_model, if_scaler = train_isolation_forest(X_full)
    ae_model, ae_scaler, ae_thr, ae_p95, per_param = train_autoencoder(X_compact)
    reg_models = train_cross_parameter_regressions(datasets)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "isolation_forest.pkl": if_model,
        "if_scaler.pkl": if_scaler,
        "autoencoder.pkl": ae_model,
        "ae_scaler.pkl": ae_scaler,
        # "threshold" (p99.5) calibrates ae_score; p95 kept for reference
        "ae_threshold.pkl": {"threshold": ae_thr, "threshold_p95": ae_p95, "per_param": per_param},
        "regression_models.pkl": reg_models,
    }
    for name, obj in artifacts.items():
        with open(MODEL_DIR / name, "wb") as fh:
            pickle.dump(obj, fh)
    print(f"[*] Saved {len(artifacts)} artifacts to {MODEL_DIR}", flush=True)


# ------------------------------------------------------------------ benchmark
def _episodes(stn: Dict, t: datetime) -> List[Tuple[Dict, int, str]]:
    """One block of labelled anomaly episodes, each followed by normal recovery readings."""
    code, elev = stn["station_code"], stn["elevation_m"]
    out: List[Tuple[Dict, int, str]] = []

    def normals(n):
        nonlocal t
        for o in generate_time_series(code, t, n, INTERVAL, elev):
            out.append((o, 0, "normal"))
        t += timedelta(minutes=INTERVAL * n)

    _skip_first_recovery: List[bool] = []
    scenarios = ["spike", "frozen", "drift", "multivariate", "communication"]
    random.shuffle(scenarios)
    for kind in scenarios:
        param = random.choice(["temperature", "humidity", "pressure", "wind_speed"])
        if kind == "spike":
            out.append((create_spike_observation(code, t, [param], magnitude=3.5, elevation_m=elev), 1, "spike"))
            t += timedelta(minutes=INTERVAL)
        elif kind == "frozen":
            run = create_frozen_observations(code, t, 7, [param], INTERVAL, elev)
            for i, o in enumerate(run):
                # readings 1-2 of a stuck run are indistinguishable from "no change"; not scored
                label = 0 if i == 0 else (1 if i >= 3 else -1)
                out.append((o, label, "frozen" if label != 0 else "normal"))
            t += timedelta(minutes=INTERVAL * len(run))
            _skip_first_recovery.append(True)
        elif kind == "drift":
            run = create_drift_observations(code, t, 8, [param], magnitude=3.0, interval_min=INTERVAL, elevation_m=elev)
            out.extend((o, 1, "drift") for o in run)
            t += timedelta(minutes=INTERVAL * len(run))
            _skip_first_recovery.append(True)
        elif kind == "multivariate":
            out.append((create_multivariate_observation(code, t, None, magnitude=3.0, elevation_m=elev), 1, "multivariate"))
            t += timedelta(minutes=INTERVAL)
        else:
            o = {"station_code": code, "observed_at": t.isoformat(), **{p: None for p in PARAMETERS}, "rainfall": 0.0}
            out.append((o, 1, "communication"))
            t += timedelta(minutes=INTERVAL)
        n_before = len(out)
        normals(12)
        if _skip_first_recovery:
            # the synthetic fault ends with an instant snap back to the true value: a real step
            # that QC correctly flags but which is neither normal nor the injected fault
            o, _, _ = out[n_before]
            out[n_before] = (o, -1, "recovery")
            _skip_first_recovery.clear()
    return out


def evaluate_benchmark(blocks_per_station: int = 3, seed: int = 2026) -> Dict:
    from ml.inference.autoencoder import AutoencoderInference
    from ml.inference.isolation_forest import IsolationForestInference

    random.seed(seed)
    np.random.seed(seed)
    if_inf, ae_inf = IsolationForestInference(MODEL_DIR), AutoencoderInference(MODEL_DIR)
    with open(MODEL_DIR / "regression_models.pkl", "rb") as fh:
        drift_detector = DriftDetector(pickle.load(fh))

    y_true, y_pred = [], []
    per_class = defaultdict(lambda: [0, 0])  # kind -> [detected, total]
    cause_confusion: Counter = Counter()
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)

    print("\n--- Production pipeline benchmark (held-out data) ---", flush=True)
    for stn in DEMO_STATIONS:
        code = stn["station_code"]
        history = generate_time_series(code, start, HISTORY, INTERVAL, stn["elevation_m"])
        t = start + timedelta(minutes=INTERVAL * HISTORY)
        samples = [(o, 0, "normal") for o in generate_time_series(code, t, 150, INTERVAL, stn["elevation_m"])]
        t += timedelta(minutes=INTERVAL * 150)
        for _ in range(blocks_per_station):
            block = _episodes(stn, t)
            samples.extend(block)
            t = datetime.fromisoformat(block[-1][0]["observed_at"]) + timedelta(minutes=INTERVAL)

        for obs, label, kind in samples:
            res = score_observation(
                obs, history[-HISTORY:], station_code=code, if_inference=if_inf, ae_inference=ae_inf,
                drift_detector=drift_detector, expected_interval_min=INTERVAL, longitude=stn["longitude"],
            )
            history.append(obs)
            if label < 0:
                continue
            pred = int(res.fusion.is_anomaly)
            y_true.append(label)
            y_pred.append(pred)
            per_class[kind][1] += 1
            per_class[kind][0] += pred
            if label == 1 and pred:
                cause_confusion[(kind, res.root_cause.root_cause)] += 1

    detected = sum(v for (k, _), v in cause_confusion.items())
    correct = sum(v for (k, c), v in cause_confusion.items() if k == c)
    normals = per_class["normal"]
    metrics = {
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "false_positive_rate": round(normals[0] / max(1, normals[1]), 4),
        "root_cause_accuracy": round(correct / max(1, detected), 4),
        "samples": {"normal": normals[1], "anomalous": sum(y_true)},
        "recall_by_type": {k: round(v[0] / max(1, v[1]), 4) for k, v in per_class.items() if k != "normal"},
        "root_cause_confusion": {f"{k}->{c}": v for (k, c), v in sorted(cause_confusion.items(), key=str)},
    }
    print(json.dumps(metrics, indent=2), flush=True)
    RESULTS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"[*] Results written to {RESULTS_PATH.relative_to(ROOT)}", flush=True)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eval-only", action="store_true", help="skip training; benchmark existing artifacts")
    args = parser.parse_args()
    if not args.eval_only:
        train()
    evaluate_benchmark()


if __name__ == "__main__":
    main()
