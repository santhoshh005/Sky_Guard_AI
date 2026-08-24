"""Deterministic Quality Checks (QC) Service for SkyGuard AI.
Implements physical bounds, frozen sensor, spike deviation, and timestamp gap checks.
Specified in /docs/HANDOFF.md §3.1.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

PARAMETERS = [
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
    "rainfall",
    "solar_radiation",
]

BOUNDS: Dict[str, Dict[str, float]] = {
    "temperature": {"min": -50.0, "max": 60.0},
    "humidity": {"min": 0.0, "max": 100.0},
    "pressure": {"min": 870.0, "max": 1084.0},
    "wind_speed": {"min": 0.0, "max": 120.0},
    "wind_direction": {"min": 0.0, "max": 360.0},
    "rainfall": {"min": 0.0, "max": 500.0},
    "solar_radiation": {"min": 0.0, "max": 1500.0},
}


class QualityChecker:
    @staticmethod
    def run_checks(
        current_obs: Dict[str, Any],
        recent_history: List[Dict[str, Any]],
        expected_interval_min: int = 15
    ) -> Tuple[float, Dict[str, List[str]]]:
        """
        Run deterministic quality checks against current observation.
        
        Args:
            current_obs: Dict with parameter readings and 'observed_at'
            recent_history: List of past observations sorted by observed_at asc
            expected_interval_min: Expected reporting interval in minutes
            
        Returns:
            Tuple of (qc_score: float [0, 1], qc_flags: Dict[param, List[flags]])
        """
        flags: Dict[str, List[str]] = {p: [] for p in PARAMETERS}
        flags["_station"] = []

        curr_time = current_obs.get("observed_at")
        if isinstance(curr_time, str):
            curr_time = datetime.fromisoformat(curr_time.replace("Z", "+00:00"))

        # 1. Per-parameter checks
        for param in PARAMETERS:
            val = current_obs.get(param)

            # A. MISSING
            if val is None or (isinstance(val, float) and np.isnan(val)):
                flags[param].append("missing")
                continue  # Skip other checks if missing

            val = float(val)

            # B. RANGE
            if val < BOUNDS[param]["min"] or val > BOUNDS[param]["max"]:
                flags[param].append("range")

            # C. FROZEN: >= 4 consecutive identical values
            # Rainfall == 0 is unconditionally valid (rain absence).
            # Solar radiation == 0 is ONLY valid at night (outside §9.1 sunrise=6, sunset=18 window).
            # A solar sensor stuck at 0 during daytime (06:00-18:00) is an active fault and MUST trigger frozen.
            hour_val = (curr_time.hour + curr_time.minute / 60.0) if curr_time else 12.0
            is_daytime = 6.0 <= hour_val <= 18.0
            is_zero_natural = (param == "rainfall" and val == 0.0) or (param == "solar_radiation" and val == 0.0 and not is_daytime)

            if not is_zero_natural:
                past_values = [
                    float(h[param])
                    for h in recent_history[-3:]
                    if param in h and h[param] is not None and not np.isnan(h[param])
                ]
                if len(past_values) == 3 and all(abs(pv - val) < 1e-4 for pv in past_values):
                    flags[param].append("frozen")

            # D. SPIKE: |delta| > 5 * rolling_std_24h
            if recent_history:
                prev_obs = recent_history[-1]
                prev_val = prev_obs.get(param)
                if prev_val is not None and not np.isnan(prev_val):
                    delta = abs(val - float(prev_val))
                    
                    # 24h rolling std
                    cutoff_24h = curr_time - timedelta(hours=24)
                    values_24h = [
                        float(h[param])
                        for h in recent_history
                        if param in h and h[param] is not None and not np.isnan(h[param])
                    ]
                    if len(values_24h) >= 4:
                        rolling_std = float(np.std(values_24h, ddof=1))
                        # Avoid triggering on near-zero noise floor
                        min_std_floor = {
                            "temperature": 0.5,
                            "humidity": 1.5,
                            "pressure": 0.4,
                            "wind_speed": 0.8,
                            "wind_direction": 5.0,
                            "rainfall": 2.0,
                            "solar_radiation": 15.0,
                        }.get(param, 1.0)
                        effective_std = max(rolling_std, min_std_floor)
                        if delta > 5.0 * effective_std:
                            flags[param].append("spike")

        # 2. Station-level timestamp gap check
        if recent_history:
            prev_time = recent_history[-1].get("observed_at")
            if isinstance(prev_time, str):
                prev_time = datetime.fromisoformat(prev_time.replace("Z", "+00:00"))
            if prev_time:
                time_gap_min = (curr_time - prev_time).total_seconds() / 60.0
                if time_gap_min > 2.0 * expected_interval_min:
                    flags["_station"].append("timestamp_gap")

        # 3. Compute QC score [0, 1]
        total_flags = sum(len(f_list) for f_list in flags.values())
        total_checks = len(PARAMETERS) * 4 + 1  # 29 checks total
        qc_score = float(min(1.0, total_flags / total_checks))

        # Store score inside flags dict for convenience
        result_flags = dict(flags)
        result_flags["qc_score"] = round(qc_score, 4)

        return qc_score, result_flags
