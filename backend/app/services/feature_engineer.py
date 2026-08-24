"""Feature engineering service for SkyGuard AI.
Computes time-range based rolling statistics, deltas, correlations, and temporal features.
Produces full (~110 dims) feature vector for Isolation Forest and 14-dim vector for Autoencoder.
Specified in /docs/HANDOFF.md §2 & §14.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

PARAMETERS = [
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
    "rainfall",
    "solar_radiation",
]

# Standard feature order for ~110-dim vector
FEATURE_NAMES: List[str] = []

# 1. Raw features (7)
for p in PARAMETERS:
    FEATURE_NAMES.append(f"{p}_raw")

# 2. Rolling stats (84): 7 params x 3 windows x 4 stats
WINDOWS = ["1h", "6h", "24h"]
STATS = ["mean", "std", "min", "max"]
for p in PARAMETERS:
    for w in WINDOWS:
        for s in STATS:
            FEATURE_NAMES.append(f"{p}_{s}_{w}")

# 3. Deltas (7)
for p in PARAMETERS:
    FEATURE_NAMES.append(f"{p}_delta")

# 4. Correlations (3)
FEATURE_NAMES.extend(["corr_temp_humidity", "corr_pressure_wind", "corr_solar_temp"])

# 5. Temporal (2)
FEATURE_NAMES.extend(["hour_of_day", "is_daytime"])

# 6. Missingness flags (7)
for p in PARAMETERS:
    FEATURE_NAMES.append(f"missing_{p}")


def extract_base_param(feature_name: str) -> str:
    """Extract base parameter name from derived feature name."""
    for p in PARAMETERS:
        if feature_name.startswith(p) or feature_name.endswith(f"_{p}"):
            return p
    return "other"


class FeatureEngineer:
    """Extracts features from recent observation time-series for a station."""

    @staticmethod
    def extract_features(
        current_obs: Dict[str, Any],
        recent_history: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
        """
        Extract features from current observation + recent history (within 24h).
        
        Args:
            current_obs: Dict with parameter values and 'observed_at'
            recent_history: List of past observation dicts sorted by observed_at asc
            
        Returns:
            Tuple of:
              - full_feature_vector (~110 dims, numpy float64)
              - compact_vector (14 dims: 7 raw + 7 deltas, numpy float64)
              - feature_dict (mapping of feature_name -> float)
        """
        curr_time = current_obs.get("observed_at")
        if isinstance(curr_time, str):
            curr_time = datetime.fromisoformat(curr_time.replace("Z", "+00:00"))

        # Convert recent history to DataFrame if available
        records = list(recent_history)
        # Ensure current_obs is included as latest point
        curr_copy = dict(current_obs)
        curr_copy["observed_at"] = curr_time
        records.append(curr_copy)

        df = pd.DataFrame(records)
        if "observed_at" in df.columns:
            df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
            df = df.sort_values("observed_at").drop_duplicates(subset=["observed_at"])

        features: Dict[str, float] = {}

        # 1. Raw values & missingness
        for p in PARAMETERS:
            val = current_obs.get(p)
            if val is None or np.isnan(val):
                features[f"{p}_raw"] = 0.0
                features[f"missing_{p}"] = 1.0
            else:
                features[f"{p}_raw"] = float(val)
                features[f"missing_{p}"] = 0.0

        # 2. Time-range based rolling stats (1h, 6h, 24h)
        window_deltas = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
        }

        for w_name, w_delta in window_deltas.items():
            start_window = curr_time - w_delta
            sub_df = df[df["observed_at"] >= start_window]

            for p in PARAMETERS:
                series = sub_df[p].dropna() if p in sub_df.columns else pd.Series([], dtype=float)
                raw_val = features[f"{p}_raw"]

                if len(series) >= 2:
                    features[f"{p}_mean_{w_name}"] = float(series.mean())
                    features[f"{p}_std_{w_name}"] = float(series.std(ddof=1)) if len(series) > 1 else 0.0
                    features[f"{p}_min_{w_name}"] = float(series.min())
                    features[f"{p}_max_{w_name}"] = float(series.max())
                elif len(series) == 1:
                    features[f"{p}_mean_{w_name}"] = raw_val
                    features[f"{p}_std_{w_name}"] = 0.0
                    features[f"{p}_min_{w_name}"] = raw_val
                    features[f"{p}_max_{w_name}"] = raw_val
                else:
                    features[f"{p}_mean_{w_name}"] = 0.0
                    features[f"{p}_std_{w_name}"] = 0.0
                    features[f"{p}_min_{w_name}"] = 0.0
                    features[f"{p}_max_{w_name}"] = 0.0

        # 3. Rate of change (deltas from immediate previous observation)
        prev_obs = recent_history[-1] if recent_history else None
        for p in PARAMETERS:
            curr_val = current_obs.get(p)
            prev_val = prev_obs.get(p) if prev_obs else None

            if curr_val is not None and prev_val is not None:
                features[f"{p}_delta"] = float(curr_val - prev_val)
            else:
                features[f"{p}_delta"] = 0.0

        # 4. Inter-parameter correlations over 24h
        df_24h = df[df["observed_at"] >= (curr_time - timedelta(hours=24))]
        
        def calc_corr(col1: str, col2: str) -> float:
            if col1 in df_24h.columns and col2 in df_24h.columns:
                valid = df_24h[[col1, col2]].dropna()
                if len(valid) >= 4:
                    std1 = valid[col1].std()
                    std2 = valid[col2].std()
                    if std1 > 1e-4 and std2 > 1e-4:
                        r = valid[col1].corr(valid[col2])
                        return float(r) if not np.isnan(r) else 0.0
            return 0.0

        features["corr_temp_humidity"] = calc_corr("temperature", "humidity")
        features["corr_pressure_wind"] = calc_corr("pressure", "wind_speed")
        features["corr_solar_temp"] = calc_corr("solar_radiation", "temperature")

        # 5. Temporal features
        hour = curr_time.hour + curr_time.minute / 60.0
        features["hour_of_day"] = float(hour / 24.0)
        features["is_daytime"] = 1.0 if (6.0 <= hour <= 18.0) else 0.0

        # Build full ~110-dim vector
        full_vector = np.array([features.get(f, 0.0) for f in FEATURE_NAMES], dtype=np.float64)

        # Build 14-dim compact vector (7 raw values + 7 deltas)
        compact_values = []
        for p in PARAMETERS:
            compact_values.append(features[f"{p}_raw"])
        for p in PARAMETERS:
            compact_values.append(features[f"{p}_delta"])
        compact_vector = np.array(compact_values, dtype=np.float64)

        return full_vector, compact_vector, features
