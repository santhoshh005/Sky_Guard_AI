"""Sensor Health Scoring Service for SkyGuard AI.
Tracks per-parameter reliability score [0, 100] with degradation, recovery, and streak acceleration.
Specified in /docs/HANDOFF.md §4, §14.1, §14.2.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from app.services.feature_engineer import PARAMETERS


@dataclass
class SensorHealthState:
    health_score: float = 100.0
    anomaly_streak: int = 0
    last_updated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "health_score": round(self.health_score, 2),
            "status": self.get_status(),
            "anomaly_streak": self.anomaly_streak,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    def get_status(self) -> str:
        if self.health_score < 15.0:
            return "sensor_critical"
        if self.health_score < 40.0:
            return "maintenance_recommended"
        if self.health_score < 70.0:
            return "degraded"
        return "healthy"


class HealthScorer:
    """Manages sensor health states in-memory and handles degradation updates."""

    def __init__(self):
        # Key: (station_id, parameter) -> SensorHealthState
        self.states: Dict[Tuple[str, str], SensorHealthState] = {}

    def get_state(self, station_id: str, parameter: str) -> SensorHealthState:
        key = (station_id, parameter)
        if key not in self.states:
            self.states[key] = SensorHealthState()
        return self.states[key]

    @staticmethod
    def get_flagged_parameters(qc_flags: Dict[str, Any], shap_values: Dict[str, Any]) -> Set[str]:
        """
        Derive flagged anomalous parameters per §14.1:
        Union of QC-flagged parameters + SHAP parameters with normalized contribution >= 0.15.
        """
        flagged = set()

        # (a) QC flags
        for param in PARAMETERS:
            flags = qc_flags.get(param, [])
            if flags and len(flags) > 0:
                flagged.add(param)

        # (b) SHAP contributions >= 0.15
        contributions = shap_values.get("parameter_contributions", {})
        for param, contrib in contributions.items():
            if contrib >= 0.15:
                flagged.add(param)

        return flagged

    def update_sensor_health(
        self,
        station_id: str,
        observation: Dict[str, Any],
        qc_flags: Dict[str, Any],
        shap_values: Dict[str, Any],
        ae_param_errors: Optional[Dict[str, float]] = None,
        is_drifting_map: Optional[Dict[str, bool]] = None,
        expected_interval_min: int = 15
    ) -> Dict[str, Tuple[SensorHealthState, str, Optional[str]]]:
        """
        Update health for all 7 parameters for a given station.
        
        Returns:
            Dict mapping param -> (state, status, alert_type_to_create_or_None)
        """
        flagged_params = self.get_flagged_parameters(qc_flags, shap_values)
        obs_time = observation.get("observed_at")
        if isinstance(obs_time, str):
            obs_time = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
        elif obs_time is None:
            obs_time = datetime.now(timezone.utc)

        results: Dict[str, Tuple[SensorHealthState, str, Optional[str]]] = {}

        for param in PARAMETERS:
            state = self.get_state(station_id, param)
            prev_status = state.get_status()
            param_val = observation.get(param)
            is_anomalous = param in flagged_params

            # 1. Time decay for missed observations
            if state.last_updated is not None:
                elapsed_min = (obs_time - state.last_updated).total_seconds() / 60.0
                if elapsed_min > 2.0 * expected_interval_min:
                    missed = int(elapsed_min / expected_interval_min) - 1
                    state.health_score = max(0.0, state.health_score - 1.0 * missed)

            # 2. Penalty or Recovery
            if is_anomalous:
                state.anomaly_streak += 1
                penalty = 2.0 * (1.0 + 0.5 * min(state.anomaly_streak, 10))

                # Extra penalties
                if param_val is None:
                    penalty += 3.0
                if is_drifting_map and is_drifting_map.get(param, False):
                    penalty += 5.0
                if ae_param_errors and ae_param_errors.get(param, 0.0) > 0.7:
                    penalty += 1.5

                state.health_score = max(0.0, state.health_score - penalty)
            else:
                # Recovery is slow and deliberate
                state.health_score = min(100.0, state.health_score + 0.5)
                state.anomaly_streak = 0

            state.last_updated = obs_time
            new_status = state.get_status()

            # 3. Check for health alert transition
            alert_type = None
            if new_status == "sensor_critical" and prev_status != "sensor_critical":
                alert_type = "health_degraded"
            elif new_status == "maintenance_recommended" and prev_status not in ("maintenance_recommended", "sensor_critical"):
                alert_type = "maintenance_required"

            results[param] = (state, new_status, alert_type)

        return results

    def get_overall_health(self, station_id: str) -> Tuple[float, str]:
        """Compute average health score across all 7 parameters for a station."""
        scores = [self.get_state(station_id, p).health_score for p in PARAMETERS]
        avg_score = float(np.mean(scores)) if scores else 100.0
        
        if avg_score < 15.0:
            status = "sensor_critical"
        elif avg_score < 40.0:
            status = "maintenance_recommended"
        elif avg_score < 70.0:
            status = "degraded"
        else:
            status = "healthy"
            
        return round(avg_score, 2), status
