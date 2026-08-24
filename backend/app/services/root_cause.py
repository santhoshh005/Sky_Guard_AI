"""Root-cause classification service for SkyGuard AI.
Implements hierarchical 5-category decision rules from SHAP and QC evidence.
Specified in /docs/HANDOFF.md §5 & §14.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.services.feature_engineer import PARAMETERS, extract_base_param


@dataclass
class RootCauseResult:
    root_cause: Optional[str]  # 'spike', 'frozen', 'drift', 'communication', 'multivariate', None
    explanation: Optional[str]


class RootCauseClassifier:
    @staticmethod
    def get_top_shap_parameters(shap_values: Dict[str, Any], n: int = 3) -> List[str]:
        """Extract unique base parameter names from top-N SHAP feature contributions."""
        features = shap_values.get("top_features", [])[:n]
        params = []
        for f in features:
            name = f.get("feature", "")
            base = extract_base_param(name)
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
        baselines: Optional[Dict[str, Dict[str, float]]] = None
    ) -> RootCauseResult:
        """
        Classify root cause in strict evaluation order:
        1. Communication / Missing
        2. Frozen
        3. Spike
        4. Drift
        5. Multivariate
        """
        if not is_anomaly:
            return RootCauseResult(root_cause=None, explanation="Normal station operation.")

        top_shap_params = cls.get_top_shap_parameters(shap_values, n=3)
        top_shap_feature_names = [f.get("feature", "") for f in shap_values.get("top_features", [])]

        # ----------------------------------------------------------------------
        # Rule 1: Communication / Missing
        # ----------------------------------------------------------------------
        missing_params = [p for p in PARAMETERS if observation.get(p) is None or np.isnan(observation.get(p))]
        has_timestamp_gap = "timestamp_gap" in qc_flags.get("_station", [])

        if len(missing_params) >= 3 or has_timestamp_gap:
            if has_timestamp_gap:
                expl = "Data gap detected between reporting intervals. Potential communication failure or AWS downtime."
            else:
                expl = f"{len(missing_params)} parameters missing ({', '.join(missing_params)}). Suspected telemetry or multiplexer failure."
            return RootCauseResult(root_cause="communication", explanation=expl)

        # ----------------------------------------------------------------------
        # Rule 2: Frozen
        # ----------------------------------------------------------------------
        frozen_params = [p for p in PARAMETERS if "frozen" in qc_flags.get(p, [])]
        if frozen_params:
            for p in frozen_params:
                if p in top_shap_params or not top_shap_params:
                    val = observation.get(p)
                    expl = f"{p.capitalize()} sensor is stuck at {val} across consecutive readings. Mechanical jam or ADC lockup detected."
                    return RootCauseResult(root_cause="frozen", explanation=expl)

        # ----------------------------------------------------------------------
        # Rule 3: Spike
        # ----------------------------------------------------------------------
        spike_params = [p for p in PARAMETERS if "spike" in qc_flags.get(p, [])]
        if spike_params and len(spike_params) <= 2:
            worst = spike_params[0]
            curr_val = observation.get(worst, 0.0)
            prev_val = recent_history[-1].get(worst, curr_val) if recent_history else curr_val
            delta = abs(curr_val - prev_val) if (curr_val is not None and prev_val is not None) else 0.0
            expl = f"Sudden transient spike in {worst}: jumped from {prev_val} to {curr_val} (delta {delta:.2f}). Probable electrical noise or transient fault."
            return RootCauseResult(root_cause="spike", explanation=expl)

        # ----------------------------------------------------------------------
        # Rule 4: Drift
        # ----------------------------------------------------------------------
        if ae_score > 0.5 and baselines:
            for p in top_shap_params:
                b_info = baselines.get(p)
                if b_info and b_info.get("std", 0.0) > 0.0:
                    b_mean = b_info["mean"]
                    b_std = b_info["std"]
                    # Calculate rolling mean over recent history
                    vals = [h[p] for h in recent_history if p in h and h[p] is not None]
                    if len(vals) >= 4:
                        curr_mean = float(np.mean(vals))
                        if abs(curr_mean - b_mean) > 2.0 * b_std:
                            shift = curr_mean - b_mean
                            expl = f"{p.capitalize()} baseline has shifted by {shift:+.2f} relative to seasonal norm ({b_mean:.2f} ± {b_std:.2f}). Calibration drift detected."
                            return RootCauseResult(root_cause="drift", explanation=expl)

        # ----------------------------------------------------------------------
        # Rule 5: Multivariate (catch-all for coupled anomalous features)
        # ----------------------------------------------------------------------
        top_5_params = cls.get_top_shap_parameters(shap_values, n=5)
        affected_str = ", ".join(top_5_params[:3]) if top_5_params else "weather sensors"
        expl = f"Coupled multivariate anomaly detected across {affected_str}. Complex pattern divergence or extreme weather event."
        return RootCauseResult(root_cause="multivariate", explanation=expl)
