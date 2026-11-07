"""Root-cause classification for SkyGuard AI.

Hierarchical rules evaluated in order of evidential strength:

1. communication - 3+ parameters missing (telemetry / logger failure)
2. frozen        - deterministic stuck-sensor QC flag
3. spike         - step-test spike on 1-2 parameters
4. drift         - growing same-sign residual against expected value (see drift.py)
5. communication - 1-2 sensors missing, or a reporting gap with no sensor-level fault
6. multivariate  - anything else (coupled deviation found by the ML channels)

Each result also names the affected parameters, used for alerts and value correction.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.drift import DriftEvidence
from app.services.feature_engineer import PARAMETERS, extract_base_param, is_valid_number


@dataclass
class RootCauseResult:
    root_cause: Optional[str]  # 'spike', 'frozen', 'drift', 'communication', 'multivariate', None
    explanation: Optional[str]
    parameters: List[str] = field(default_factory=list)


def _label(param: str) -> str:
    return param.replace("_", " ")


class RootCauseClassifier:
    @staticmethod
    def get_top_shap_parameters(shap_values: Dict[str, Any], n: int = 3) -> List[str]:
        """Unique base parameter names from the top-N SHAP feature contributions."""
        params: List[str] = []
        for f in shap_values.get("top_features", [])[:n]:
            base = extract_base_param(f.get("feature", ""))
            if base in PARAMETERS and base not in params:
                params.append(base)
        return params

    @classmethod
    def classify(
        cls,
        observation: Dict[str, Any],
        qc_flags: Dict[str, Any],
        shap_values: Dict[str, Any],
        ae_score: float,
        is_anomaly: bool,
        recent_history: List[Dict[str, Any]],
        drift_evidence: Optional[Dict[str, DriftEvidence]] = None,
    ) -> RootCauseResult:
        if not is_anomaly:
            return RootCauseResult(root_cause=None, explanation="Normal station operation.")

        drift_evidence = drift_evidence or {}
        prev = recent_history[-1] if recent_history else {}

        # 1. Communication: telemetry dropout across several channels
        missing = [p for p in PARAMETERS if not is_valid_number(observation.get(p))]
        if len(missing) >= 3:
            return RootCauseResult(
                "communication",
                f"{len(missing)} parameters missing ({', '.join(map(_label, missing))}). "
                "Suspected telemetry, data-logger or multiplexer failure.",
                missing,
            )

        # 2. Frozen: deterministic stuck-sensor evidence
        frozen = [p for p in PARAMETERS if "frozen" in qc_flags.get(p, [])]
        if frozen:
            desc = ", ".join(f"{_label(p)} = {observation.get(p)}" for p in frozen)
            return RootCauseResult(
                "frozen",
                f"Sensor output stuck across 4+ consecutive readings ({desc}). "
                "Mechanical jam, ADC lock-up or logger repeating its last value.",
                frozen,
            )

        # 3. Spike: abrupt step on one or two sensors
        jumped = [p for p in PARAMETERS if "spike" in qc_flags.get(p, [])]
        if 1 <= len(jumped) <= 2:
            parts = []
            for p in jumped:
                curr, before = observation.get(p), prev.get(p)
                if is_valid_number(curr) and is_valid_number(before):
                    parts.append(f"{_label(p)} {before} -> {curr} (delta {float(curr) - float(before):+.2f})")
                else:
                    parts.append(f"{_label(p)} = {curr}")
            return RootCauseResult(
                "spike",
                f"Sudden transient spike: {'; '.join(parts)}. Probable electrical noise, "
                "loose connection or transient sensor fault.",
                jumped,
            )

        # 4. Drift: sustained, growing offset on few sensors
        if drift_evidence and len(drift_evidence) <= 2:
            parts = [
                f"{_label(e.parameter)} offset {e.shift:+.2f} ({abs(e.shift) / e.sigma:.1f} sigma, {e.method.replace('_', ' ')})"
                for e in drift_evidence.values()
            ]
            return RootCauseResult(
                "drift",
                f"Calibration drift: {'; '.join(parts)}, growing over consecutive readings.",
                list(drift_evidence.keys()),
            )

        # 5. Communication: partial dropout or reporting gap
        if missing:
            return RootCauseResult(
                "communication",
                f"No data from {', '.join(map(_label, missing))}. Sensor cable, power or channel failure.",
                missing,
            )
        if "timestamp_gap" in qc_flags.get("_station", []):
            return RootCauseResult(
                "communication",
                "Data gap between reporting intervals. Potential communication failure or AWS downtime.",
                [],
            )

        # 6. Multivariate: coupled deviation detected by the ML channels
        out_of_range = [p for p in PARAMETERS if "range" in qc_flags.get(p, [])]
        affected = out_of_range or jumped or cls.get_top_shap_parameters(shap_values, n=3)
        detail = "outside physical limits" if out_of_range else "jointly deviating from learned behaviour"
        return RootCauseResult(
            "multivariate",
            f"Coupled multivariate anomaly: {', '.join(map(_label, affected)) or 'several sensors'} {detail}. "
            "Possible extreme weather event or multi-sensor fault.",
            affected,
        )
