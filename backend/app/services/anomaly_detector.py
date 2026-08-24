"""Anomaly detection 3-channel fusion service for SkyGuard AI.
Combines Deterministic QC (0.35), Isolation Forest (0.30), and Autoencoder (0.35).
Specified in /docs/HANDOFF.md §3.4.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np


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

    @classmethod
    def fuse_scores(
        cls,
        qc_score: float,
        if_score: float,
        ae_score: float
    ) -> AnomalyDetectionResult:
        """
        Combine 3 independent channels into fused anomaly score and confidence.
        
        Formula:
          fused_score = 0.35 * qc_score + 0.30 * if_score + 0.35 * ae_score
          agreement = 1.0 - (std([qc, if, ae]) / 0.577)
          confidence = clamp(agreement, 0.0, 1.0)
          is_anomaly = fused_score >= 0.5
          severity = 'critical' if >= 0.8 else 'warning' if >= 0.5 else 'normal'
        """
        qc = float(max(0.0, min(1.0, qc_score)))
        if_s = float(max(0.0, min(1.0, if_score)))
        ae = float(max(0.0, min(1.0, ae_score)))

        fused = cls.W_QC * qc + cls.W_IF * if_s + cls.W_AE * ae
        fused = float(max(0.0, min(1.0, fused)))

        scores = [qc, if_s, ae]
        std_val = float(np.std(scores))
        # 0.577 is max theoretical std for a set of 3 values bounded in [0, 1]
        agreement = 1.0 - (std_val / 0.57735)
        confidence = float(max(0.0, min(1.0, agreement)))

        is_anomaly = bool(fused >= 0.5)

        if fused >= 0.8:
            severity = "critical"
        elif fused >= 0.5:
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
