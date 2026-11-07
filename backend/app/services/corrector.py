"""Corrected-value estimation for SkyGuard AI.

Estimates a replacement value for the *affected* parameters of a confirmed anomaly. Raw
telemetry is never modified; estimates are stored alongside it in ``corrected_values``.

Methods
-------
spike   -> temporal_median: median of the last valid readings (the spike is a one-off).
frozen  -> diurnal_trend: yesterday's value at this time of day, shifted by the offset
           observed just before the sensor froze; falls back to interpolation (last good value).
drift   -> cross_parameter_regression from the other six sensors (station model);
           falls back to diurnal_trend (yesterday's value at this time of day).
"""
import logging
import pickle
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from app.config import settings
from app.services.drift import value_near
from app.services.feature_engineer import PARAMETERS, is_valid_number, parse_ts

logger = logging.getLogger("skyguard.corrector")

# Typical plausible 15-min variability used to turn local spread into a confidence
TYPICAL_STEP: Dict[str, float] = {
    "temperature": 4.0,
    "humidity": 15.0,
    "pressure": 2.0,
    "wind_speed": 10.0,
    "wind_direction": 90.0,
    "rainfall": 20.0,
    "solar_radiation": 800.0,
}
CORRECTABLE_CAUSES = ("spike", "frozen", "drift")
MIN_CONFIDENCE = 0.6


@dataclass
class CorrectionResult:
    parameter: str
    raw_value: Optional[float]
    corrected_value: Optional[float]
    correction_method: str  # 'temporal_median' | 'interpolation' | 'diurnal_trend' | 'cross_parameter_regression' | 'none'
    correction_confidence: float


class ValueCorrector:
    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = Path(model_dir or settings.ML_MODEL_DIR)
        self.regression_models: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.load_models()

    def load_models(self) -> None:
        reg_path = self.model_dir / "regression_models.pkl"
        if reg_path.exists():
            try:
                with open(reg_path, "rb") as f:
                    self.regression_models = pickle.load(f)
            except Exception as e:  # corrupt / incompatible artifact
                logger.warning("Failed to load regression models: %s", e)
        else:
            logger.warning("regression_models.pkl not found in %s; regression correction disabled.", self.model_dir)

    # ------------------------------------------------------------------ methods
    @staticmethod
    def _temporal_median(param: str, history: List[Dict[str, Any]]) -> Tuple[Optional[float], float]:
        past = [float(h[param]) for h in history[-6:] if is_valid_number(h.get(param))]
        if len(past) < 2:
            return None, 0.0
        spread = float(np.std(past))
        conf = float(np.clip(1.0 - spread / TYPICAL_STEP[param], 0.3, 0.95))
        return float(np.median(past)), conf

    @staticmethod
    def _diurnal_estimate(param: str, obs_time, history: List[Dict[str, Any]], anchor=None) -> Optional[float]:
        """Yesterday's value at ``obs_time``, optionally shifted by today's offset at ``anchor``."""
        yesterday = value_near(history, obs_time - timedelta(hours=24), param)
        if yesterday is None:
            return None
        if anchor is None:
            return yesterday
        anchor_time, anchor_value = anchor
        anchor_yesterday = value_near(history, anchor_time - timedelta(hours=24), param)
        if anchor_yesterday is None:
            return yesterday
        return yesterday + (anchor_value - anchor_yesterday)

    def _frozen(self, param: str, raw: Any, obs_time, history: List[Dict[str, Any]]):
        last_good = None
        run = 1
        for h in reversed(history):
            v = h.get(param)
            if is_valid_number(v) and is_valid_number(raw) and abs(float(v) - float(raw)) < 1e-4:
                run += 1
                continue
            if is_valid_number(v):
                last_good = (parse_ts(h.get("observed_at")), float(v))
            break
        if obs_time is not None:
            est = self._diurnal_estimate(param, obs_time, history, anchor=last_good if last_good and last_good[0] else None)
            if est is not None:
                return est, "diurnal_trend", float(np.clip(0.85 - 0.02 * run, 0.5, 0.85))
        if last_good is not None:
            return last_good[1], "interpolation", float(np.clip(0.7 - 0.03 * run, 0.3, 0.7))
        return None, "none", 0.0

    def _drift(self, param: str, observation: Dict[str, Any], station_code: str, obs_time, history):
        info = self.regression_models.get((station_code, param))
        if info:
            feats = [observation.get(fp) for fp in info.get("feature_params", [])]
            if feats and all(is_valid_number(v) for v in feats):
                pred = float(info["model"].predict(np.asarray([[float(v) for v in feats]]))[0])
                return pred, "cross_parameter_regression", float(np.clip(info.get("r_squared", 0.6), 0.0, 0.95))
        if obs_time is not None:
            est = self._diurnal_estimate(param, obs_time, history)
            if est is not None:
                return est, "diurnal_trend", 0.6
        return None, "none", 0.0

    # ------------------------------------------------------------------ public
    def estimate_corrections(
        self,
        observation: Dict[str, Any],
        is_anomaly: bool,
        confidence: float,
        root_cause: Optional[str],
        station_code: str,
        recent_history: List[Dict[str, Any]],
        target_params: Optional[Iterable[str]] = None,
    ) -> List[CorrectionResult]:
        """Return corrections for the affected parameters of a correctable anomaly.

        Nothing is returned for normal observations, so no placeholder rows are stored.
        Parameters that cannot be estimated are returned with method ``none``.
        """
        if not is_anomaly or root_cause not in CORRECTABLE_CAUSES or confidence < MIN_CONFIDENCE:
            return []

        params = [p for p in (target_params or []) if p in PARAMETERS]
        obs_time = parse_ts(observation.get("observed_at"))
        results: List[CorrectionResult] = []
        for param in params:
            raw = observation.get(param)
            if root_cause == "spike":
                value, conf = self._temporal_median(param, recent_history)
                method = "temporal_median" if value is not None else "none"
            elif root_cause == "frozen":
                value, method, conf = self._frozen(param, raw, obs_time, recent_history)
            else:
                value, method, conf = self._drift(param, observation, station_code, obs_time, recent_history)

            results.append(CorrectionResult(
                parameter=param,
                raw_value=float(raw) if is_valid_number(raw) else None,
                corrected_value=round(value, 2) if value is not None else None,
                correction_method=method,
                correction_confidence=round(conf if value is not None else 0.0, 4),
            ))
        return results
