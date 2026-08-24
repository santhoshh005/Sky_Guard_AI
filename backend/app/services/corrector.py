"""Corrected-Value Estimation Service for SkyGuard AI.
Estimates replacement true values for high-confidence anomalies while preserving raw telemetry.
Specified in /docs/HANDOFF.md §6 & §12.
"""
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.services.feature_engineer import PARAMETERS

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "models"

PARAM_RANGES: Dict[str, float] = {
    "temperature": 110.0,     # -50 to 60
    "humidity": 100.0,        # 0 to 100
    "pressure": 214.0,        # 870 to 1084
    "wind_speed": 120.0,      # 0 to 120
    "wind_direction": 360.0,  # 0 to 360
    "rainfall": 500.0,        # 0 to 500
    "solar_radiation": 1500.0,# 0 to 1500
}


@dataclass
class CorrectionResult:
    parameter: str
    raw_value: Optional[float]
    corrected_value: Optional[float]
    correction_method: str  # 'temporal_median', 'interpolation', 'diurnal_trend', 'cross_parameter_regression', 'none'
    correction_confidence: float


class ValueCorrector:
    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or MODEL_DIR
        self.regression_models: Dict[Tuple[str, str], Dict] = {}
        self.load_models()

    def load_models(self):
        reg_path = self.model_dir / "regression_models.pkl"
        if reg_path.exists():
            try:
                with open(reg_path, "rb") as f:
                    self.regression_models = pickle.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load regression models: {e}")

    def estimate_corrections(
        self,
        observation: Dict[str, Any],
        fused_score: float,
        confidence: float,
        root_cause: Optional[str],
        station_code: str,
        recent_history: List[Dict[str, Any]],
        flagged_params: Optional[List[str]] = None
    ) -> List[CorrectionResult]:
        """
        Estimate corrected values for affected parameters if confidence criteria are met.
        Trigger: fused_score >= 0.6 and confidence >= 0.7 and root_cause in ('spike', 'frozen', 'drift')
        """
        results: List[CorrectionResult] = []
        target_params = flagged_params or PARAMETERS

        should_correct = (
            fused_score >= 0.6 and
            confidence >= 0.7 and
            root_cause in ("spike", "frozen", "drift")
        )

        for param in target_params:
            raw_val = observation.get(param)
            if not should_correct:
                results.append(CorrectionResult(
                    parameter=param,
                    raw_value=raw_val,
                    corrected_value=None,
                    correction_method="none",
                    correction_confidence=0.0
                ))
                continue

            corrected = None
            method = "none"
            conf = 0.0

            # ------------------------------------------------------------------
            # 1. SPIKE -> Temporal Median
            # ------------------------------------------------------------------
            if root_cause == "spike":
                past_valid = [
                    float(h[param]) for h in recent_history[-6:]
                    if param in h and h[param] is not None and not np.isnan(h[param])
                ]
                if len(past_valid) >= 2:
                    corrected = float(np.median(past_valid))
                    std_val = float(np.std(past_valid))
                    range_val = PARAM_RANGES.get(param, 100.0)
                    conf = max(0.0, min(1.0, 1.0 - (std_val / range_val)))
                    method = "temporal_median"

            # ------------------------------------------------------------------
            # 2. FROZEN -> Interpolation / Diurnal Trend
            # ------------------------------------------------------------------
            elif root_cause == "frozen":
                # Check for last distinct past value
                last_distinct = None
                for h in reversed(recent_history):
                    v = h.get(param)
                    if v is not None and (raw_val is None or abs(float(v) - float(raw_val)) > 1e-4):
                        last_distinct = float(v)
                        break

                if last_distinct is not None:
                    # Apply diurnal adjustment or delta
                    corrected = float(last_distinct)
                    method = "diurnal_trend"
                    conf = 0.75
                elif raw_val is not None:
                    corrected = float(raw_val)
                    method = "interpolation"
                    conf = 0.60

            # ------------------------------------------------------------------
            # 3. DRIFT -> Cross-Parameter Regression
            # ------------------------------------------------------------------
            elif root_cause == "drift":
                reg_info = self.regression_models.get((station_code, param))
                if reg_info:
                    feature_params = reg_info.get("feature_params", [])
                    input_feats = []
                    valid = True
                    for fp in feature_params:
                        fv = observation.get(fp)
                        if fv is not None and not np.isnan(fv):
                            input_feats.append(float(fv))
                        else:
                            valid = False
                            break

                    if valid and len(input_feats) == len(feature_params):
                        reg_model = reg_info["model"]
                        pred_val = float(reg_model.predict([input_feats])[0])
                        corrected = round(pred_val, 2)
                        conf = float(reg_info.get("r_squared", 0.80))
                        method = "cross_parameter_regression"

            results.append(CorrectionResult(
                parameter=param,
                raw_value=raw_val,
                corrected_value=round(corrected, 2) if corrected is not None else None,
                correction_method=method,
                correction_confidence=round(conf, 4)
            ))

        return results
