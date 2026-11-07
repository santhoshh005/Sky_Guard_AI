"""Calibration-drift detection for SkyGuard AI.

A drifting sensor shows a residual (measured minus expected value) that keeps the same sign
and grows over consecutive readings, while a spike is a one-off jump. Two expectations are used:

1. Cross-parameter regression (per station, trained offline): expected value of a parameter
   from the other six. Residual sigma is learnt at training time.
2. Diurnal persistence fallback (any station): the value 24 h earlier at the same time of day.

Residuals are measured relative to their own recent baseline (median over the preceding
``BASELINE`` readings), because expectation errors are autocorrelated (e.g. a linear model never
fits a diurnal cycle perfectly). Drift is declared for a parameter when the last ``RUN``
baseline-relative residuals (including the current one) share a sign, each exceeds ``RUN_SIGMA``,
their magnitude is non-decreasing, and the current one exceeds ``CURRENT_SIGMA``.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.services.feature_engineer import is_valid_number, param_delta, parse_ts

# wind speed is excluded: it is bounded at 0, heavy-tailed and gusty, so residual runs are
# common in healthy anemometers (gross wind faults are still caught by QC and the ML channels)
DRIFT_CANDIDATES = ("temperature", "humidity", "pressure")
RUN = 3
BASELINE = 12  # readings before the run used as the residual baseline (3 h at 15 min)
RUN_SIGMA = 1.5
CURRENT_SIGMA = 3.5

# Lower bounds on the residual sigma for the diurnal-persistence method (sqrt(2) x sensor noise)
DIURNAL_SIGMA_FLOOR = {"temperature": 0.7, "humidity": 2.8, "pressure": 0.7}


@dataclass
class DriftEvidence:
    parameter: str
    method: str  # 'cross_parameter_regression' | 'diurnal_persistence'
    shift: float  # current residual (measured - expected)
    sigma: float


def value_near(history: List[Dict[str, Any]], target, param: str, tolerance_min: float = 20.0) -> Optional[float]:
    """Value of ``param`` in the history record closest to ``target`` (within tolerance)."""
    best, best_gap = None, tolerance_min * 60.0
    for h in history:
        ts = parse_ts(h.get("observed_at"))
        if ts is None or not is_valid_number(h.get(param)):
            continue
        gap = abs((ts - target).total_seconds())
        if gap <= best_gap:
            best, best_gap = float(h[param]), gap
    return best


def _is_drift_run(residuals: List[float], sigma: float) -> bool:
    if len(residuals) < RUN or sigma <= 0:
        return False
    run = residuals[-RUN:]
    signs = {np.sign(r) for r in run}
    if len(signs) != 1 or 0 in signs:
        return False
    mags = [abs(r) / sigma for r in run]
    if any(m < RUN_SIGMA for m in mags) or mags[-1] < CURRENT_SIGMA:
        return False
    return all(b >= a * 0.9 for a, b in zip(mags, mags[1:]))  # non-decreasing (10% tolerance)


class DriftDetector:
    def __init__(self, regression_models: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None):
        self.regression_models = regression_models or {}

    def _regression_residual(self, info: Dict[str, Any], obs: Dict[str, Any], param: str) -> Optional[float]:
        feats = []
        for fp in info.get("feature_params", []):
            fv = obs.get(fp)
            if not is_valid_number(fv):
                return None
            feats.append(float(fv))
        if not is_valid_number(obs.get(param)):
            return None
        predicted = float(info["model"].predict(np.asarray([feats]))[0])
        return float(obs[param]) - predicted

    def _residuals(self, station_code: str, param: str, series: List[Dict[str, Any]], history: List[Dict[str, Any]]):
        """Residual series with (method, sigma), or (None, None, None) if unavailable."""
        info = self.regression_models.get((station_code, param))
        if info and info.get("residual_std"):
            residuals = [self._regression_residual(info, o, param) for o in series]
            if None not in residuals:
                return residuals, "cross_parameter_regression", float(info["residual_std"])
        residuals = []
        for o in series:
            ts = parse_ts(o.get("observed_at"))
            past = value_near(history, ts - timedelta(hours=24), param) if ts else None
            if past is None or not is_valid_number(o.get(param)):
                return None, None, None
            residuals.append(param_delta(param, float(o[param]), past))
        return residuals, "diurnal_persistence", DIURNAL_SIGMA_FLOOR[param]

    def detect(
        self,
        station_code: str,
        observation: Dict[str, Any],
        recent_history: List[Dict[str, Any]],
    ) -> Dict[str, DriftEvidence]:
        evidence: Dict[str, DriftEvidence] = {}
        series = list(recent_history[-(RUN - 1 + BASELINE):]) + [observation]
        if len(series) < RUN + 4:
            return evidence

        for param in DRIFT_CANDIDATES:
            residuals, method, sigma = self._residuals(station_code, param, series, recent_history)
            if residuals is None:
                continue
            baseline = float(np.median(residuals[:-RUN])) if len(residuals) > RUN else 0.0
            relative = [r - baseline for r in residuals]
            if _is_drift_run(relative, sigma):
                evidence[param] = DriftEvidence(param, method, round(relative[-1], 3), sigma)
        return evidence
