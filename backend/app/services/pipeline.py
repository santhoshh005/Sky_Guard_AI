"""Pure (I/O-free) scoring pipeline shared by the API and the offline benchmark.

Keeping one implementation guarantees that the benchmark measures exactly what production runs.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.anomaly_detector import AnomalyDetectionResult, AnomalyDetector
from app.services.drift import DriftDetector, DriftEvidence
from app.services.feature_engineer import PARAMETERS, FeatureEngineer
from app.services.quality_checks import QualityChecker, has_hard_flag
from app.services.root_cause import RootCauseClassifier, RootCauseResult


@dataclass
class ScoringResult:
    qc_flags: Dict[str, Any]
    shap_values: Dict[str, Any]
    ae_param_errors: Dict[str, float]
    fusion: AnomalyDetectionResult
    root_cause: RootCauseResult
    drift: Dict[str, DriftEvidence] = field(default_factory=dict)


def score_observation(
    observation: Dict[str, Any],
    recent_history: List[Dict[str, Any]],
    *,
    station_code: str,
    if_inference,
    ae_inference,
    drift_detector: Optional[DriftDetector] = None,
    expected_interval_min: int = 15,
    longitude: Optional[float] = None,
    explain: bool = True,
) -> ScoringResult:
    """Run QC, ML scoring, fusion, drift detection and root-cause classification.

    ``recent_history`` must be sorted ascending and contain only observations strictly
    earlier than ``observation``.
    """
    full_vec, compact_vec, _ = FeatureEngineer.extract_features(observation, recent_history, longitude=longitude)
    qc_score, qc_flags = QualityChecker.run_checks(observation, recent_history, expected_interval_min, longitude)

    if_score = if_inference.score(full_vec)
    ae_score, orig_scaled, recon = ae_inference.score(compact_vec)
    ae_param_errors = {p: ae_inference.get_per_parameter_error(recon, orig_scaled, p) for p in PARAMETERS}

    fusion = AnomalyDetector.fuse_scores(qc_score, if_score, ae_score, hard_qc_flag=has_hard_flag(qc_flags))

    drift = drift_detector.detect(station_code, observation, recent_history) if drift_detector else {}
    # Drift evidence is itself proof of a sensor fault even when single readings look plausible
    if drift and not fusion.is_anomaly:
        fusion = AnomalyDetectionResult(
            qc_score=fusion.qc_score, if_score=fusion.if_score, ae_score=fusion.ae_score,
            fused_score=fusion.fused_score, confidence=max(fusion.confidence, 0.6),
            is_anomaly=True, severity="warning",
        )

    shap_values = if_inference.explain(full_vec) if (explain and fusion.is_anomaly) else {
        "top_features": [], "parameter_contributions": {p: 0.0 for p in PARAMETERS}
    }

    root_cause = RootCauseClassifier.classify(
        observation=observation,
        qc_flags=qc_flags,
        shap_values=shap_values,
        ae_score=ae_score,
        is_anomaly=fusion.is_anomaly,
        recent_history=recent_history,
        drift_evidence=drift,
    )
    return ScoringResult(qc_flags, shap_values, ae_param_errors, fusion, root_cause, drift)
