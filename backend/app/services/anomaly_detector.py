"""Anomaly detection 3-channel fusion service for SkyGuard AI.
Combines Deterministic QC (0.35), Isolation Forest (0.30), and Autoencoder (0.35).
Specified in /docs/HANDOFF.md §3.4.
"""
from dataclasses import dataclass
import numpy as np

from app.config import settings


@dataclass
class AnomalyDetectionResult:
    qc_score: float
    if_score: float
    ae_score: float
    fused_score: float
    confidence: float
    is_anomaly: bool
    severity: str  # 'normal', 'warning', 'critical'


class AnomalyDetector:
    W_QC: float = 0.35
    W_IF: float = 0.30
    W_AE: float = 0.35
    MAX_STD: float = 0.57735  # max std of 3 values bounded in [0, 1]

    @classmethod
    def fuse_scores(
        cls,
        qc_score: float,
        if_score: float,
        ae_score: float,
        hard_qc_flag: bool = False,
    ) -> AnomalyDetectionResult:
        """
        Combine the 3 channels into a fused score, decision, severity and confidence.

          fused_score = 0.35 * qc + 0.30 * if + 0.35 * ae
          is_anomaly  = fused_score >= ANOMALY_THRESHOLD  OR  a hard QC flag fired
          severity    = 'critical' if fused >= CRITICAL_THRESHOLD else 'warning' if anomalous else 'normal'
          confidence  = channel agreement 1 - std/0.577; when a deterministic hard rule fired
                        (range / frozen / spike) the evidence is certain, so confidence >= qc_score.
        """
        qc = float(max(0.0, min(1.0, qc_score)))
        if_s = float(max(0.0, min(1.0, if_score)))
        ae = float(max(0.0, min(1.0, ae_score)))

        fused = float(max(0.0, min(1.0, cls.W_QC * qc + cls.W_IF * if_s + cls.W_AE * ae)))

        agreement = 1.0 - (float(np.std([qc, if_s, ae])) / cls.MAX_STD)
        confidence = float(max(0.0, min(1.0, agreement)))
        if hard_qc_flag:
            confidence = max(confidence, qc)

        is_anomaly = bool(fused >= settings.ANOMALY_THRESHOLD or hard_qc_flag)
        if fused >= settings.CRITICAL_THRESHOLD:
            severity = "critical"
        elif is_anomaly:
            severity = "warning"
        else:
            severity = "normal"

        return AnomalyDetectionResult(
            qc_score=round(qc, 4),
            if_score=round(if_s, 4),
            ae_score=round(ae, 4),
            fused_score=round(fused, 4),
            confidence=round(confidence, 4),
            is_anomaly=is_anomaly,
            severity=severity,
        )
