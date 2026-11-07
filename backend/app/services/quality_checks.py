"""Deterministic Quality Checks (QC) for SkyGuard AI.

Checks per parameter: missing, physical range, frozen (stuck) sensor and spike (step test);
plus a station-level timestamp-gap check.

QC score
--------
Each flag carries a severity weight and the score is a noisy-OR of the raised flags::

    qc_score = 1 - prod(1 - w_flag)

A single hard physical violation (out-of-range value, stuck sensor, step spike) therefore
dominates the channel instead of being diluted to 1/29 as in a plain flag count.
"""
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.services.feature_engineer import PARAMETERS, is_valid_number, local_solar_hour, param_delta, parse_ts

BOUNDS: Dict[str, Dict[str, float]] = {
    "temperature": {"min": -50.0, "max": 60.0},
    "humidity": {"min": 0.0, "max": 100.0},
    "pressure": {"min": 500.0, "max": 1084.0},  # 500 hPa admits high-altitude AWS (~5.5 km)
    "wind_speed": {"min": 0.0, "max": 120.0},
    "wind_direction": {"min": 0.0, "max": 360.0},
    "rainfall": {"min": 0.0, "max": 500.0},
    "solar_radiation": {"min": 0.0, "max": 1500.0},
}

# Severity weight per QC flag (probability-like evidence that the reading is faulty)
FLAG_WEIGHTS: Dict[str, float] = {
    "range": 1.0,
    "frozen": 0.9,
    "spike": 0.9,
    "missing": 0.6,
    "timestamp_gap": 0.5,
}

# Flags that are deterministic proof of a faulty reading on their own
HARD_FLAGS = frozenset({"range", "frozen", "spike"})

# Minimum plausible 15-minute step for a genuine weather change. A step must exceed both this
# and 5x the station's recent robust step-scale to count as a spike, so real fronts and
# thunderstorm cooling are not flagged.
MIN_SPIKE_STEP: Dict[str, float] = {
    "temperature": 4.0,
    "humidity": 15.0,
    "pressure": 2.0,
    "wind_speed": 10.0,
    "solar_radiation": 800.0,
}
# Rainfall is intermittent and wind direction legitimately swings, so no step test for them.
SPIKE_EXEMPT = frozenset({"rainfall", "wind_direction"})

FROZEN_RUN = 4  # identical consecutive readings (current + 3 previous)
DAYLIGHT_START, DAYLIGHT_END = 7.5, 16.5  # local solar hours with certain daylight


def _is_natural_constant(param: str, val: float, obs: Dict[str, Any], solar_hour: float) -> bool:
    """Constant readings that are physically expected and must not be called 'frozen'."""
    if param == "rainfall" and val == 0.0:
        return True  # no rain
    if param == "solar_radiation" and val == 0.0:
        return not (DAYLIGHT_START <= solar_hour <= DAYLIGHT_END)  # night / twilight
    if param == "wind_speed" and val == 0.0:
        return True  # calm
    if param == "wind_direction" and obs.get("wind_speed") == 0.0:
        return True  # vane does not move in calm air
    if param == "humidity" and val >= 99.5:
        return True  # saturated air (fog / rain)
    return False


def _robust_step_scale(param: str, values: List[float]) -> float:
    """Robust std (1.4826 * MAD) of consecutive steps in the recent window."""
    if len(values) < 3:
        return 0.0
    steps = np.diff(np.asarray(values, dtype=float))
    mad = float(np.median(np.abs(steps - np.median(steps))))
    return 1.4826 * mad


def hard_flagged_params(qc_flags: Dict[str, Any]) -> List[str]:
    return [p for p in PARAMETERS if HARD_FLAGS.intersection(qc_flags.get(p, []))]


def has_hard_flag(qc_flags: Dict[str, Any]) -> bool:
    return bool(hard_flagged_params(qc_flags))


class QualityChecker:
    @staticmethod
    def run_checks(
        current_obs: Dict[str, Any],
        recent_history: List[Dict[str, Any]],
        expected_interval_min: int = 15,
        longitude: Optional[float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """Run deterministic quality checks.

        Args:
            current_obs: parameter readings plus ``observed_at``
            recent_history: past observations sorted by ``observed_at`` ascending (strictly before current)
            expected_interval_min: station reporting interval
            longitude: station longitude for local solar time (optional)

        Returns:
            ``(qc_score, qc_flags)`` where ``qc_flags`` maps parameter -> list of flags,
            ``_station`` -> station-level flags, and ``qc_score`` -> the rounded score.
        """
        flags: Dict[str, List[str]] = {p: [] for p in PARAMETERS}
        flags["_station"] = []

        curr_time = parse_ts(current_obs.get("observed_at"))
        solar_hour = local_solar_hour(curr_time, longitude) if curr_time else 12.0
        cutoff_24h = curr_time - timedelta(hours=24) if curr_time else None

        window = [
            h for h in recent_history
            if cutoff_24h is None or (parse_ts(h.get("observed_at")) or cutoff_24h) >= cutoff_24h
        ]

        for param in PARAMETERS:
            val = current_obs.get(param)

            if not is_valid_number(val):
                flags[param].append("missing")
                continue
            val = float(val)

            # RANGE
            if val < BOUNDS[param]["min"] or val > BOUNDS[param]["max"]:
                flags[param].append("range")

            # FROZEN: >= 4 consecutive identical values
            if not _is_natural_constant(param, val, current_obs, solar_hour):
                past = [h.get(param) for h in recent_history[-(FROZEN_RUN - 1):]]
                if len(past) == FROZEN_RUN - 1 and all(
                    is_valid_number(pv) and abs(float(pv) - val) < 1e-4 for pv in past
                ):
                    flags[param].append("frozen")

            # SPIKE: step from the recent local level exceeds max(5 x robust step scale, plausible step)
            if param not in SPIKE_EXEMPT:
                values = [float(h[param]) for h in window if is_valid_number(h.get(param))]
                if len(values) >= 4:
                    reference = float(np.median(values[-3:]))  # robust to a single preceding spike
                    step = abs(param_delta(param, val, reference))
                    threshold = max(5.0 * _robust_step_scale(param, values), MIN_SPIKE_STEP[param])
                    if step > threshold:
                        flags[param].append("spike")

        # Station-level timestamp gap
        if recent_history and curr_time:
            prev_time = parse_ts(recent_history[-1].get("observed_at"))
            if prev_time:
                gap_min = (curr_time - prev_time).total_seconds() / 60.0
                if gap_min > 2.0 * expected_interval_min:
                    flags["_station"].append("timestamp_gap")

        survival = 1.0
        for flag_list in flags.values():
            for flag in flag_list:
                survival *= 1.0 - FLAG_WEIGHTS.get(flag, 0.5)
        qc_score = float(min(1.0, max(0.0, 1.0 - survival)))

        result_flags: Dict[str, Any] = dict(flags)
        result_flags["qc_score"] = round(qc_score, 4)
        return qc_score, result_flags
