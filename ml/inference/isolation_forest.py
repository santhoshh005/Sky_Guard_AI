"""Isolation Forest inference and SHAP explainability module.
Implements scoring and TreeSHAP feature contributions specified in /docs/HANDOFF.md §3.2 & §7.
"""
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import shap

from app.services.feature_engineer import FEATURE_NAMES, PARAMETERS, extract_base_param

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


class IsolationForestInference:
    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or MODEL_DIR
        self.model = None
        self.scaler = None
        self.explainer = None
        self.load_models()

    def load_models(self):
        model_path = self.model_dir / "isolation_forest.pkl"
        scaler_path = self.model_dir / "if_scaler.pkl"

        if model_path.exists() and scaler_path.exists():
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
            try:
                self.explainer = shap.TreeExplainer(self.model)
            except Exception as e:
                print(f"[WARN] Failed to initialize TreeExplainer: {e}")

    def score(self, feature_vector: np.ndarray) -> float:
        """
        Compute normalized Isolation Forest anomaly score [0, 1].
        0 = definitely normal, 1 = definitely anomalous.
        """
        if self.model is None or self.scaler is None:
            return 0.0

        vec_2d = feature_vector.reshape(1, -1)
        scaled_vec = self.scaler.transform(vec_2d)
        raw_score = float(self.model.decision_function(scaled_vec)[0])
        # Formula from §3.2: (1 - raw_score) / 2 clamped to [0, 1]
        if_score = max(0.0, min(1.0, (1.0 - raw_score) / 2.0))
        return float(if_score)

    def explain(self, feature_vector: np.ndarray) -> Dict[str, Any]:
        """
        Compute SHAP values and group by parameter as specified in §7.
        """
        if self.model is None or self.scaler is None:
            return {"top_features": [], "parameter_contributions": {p: 0.0 for p in PARAMETERS}}

        vec_2d = feature_vector.reshape(1, -1)
        scaled_vec = self.scaler.transform(vec_2d)

        shap_matrix = None
        if self.explainer is not None:
            try:
                shap_vals = self.explainer.shap_values(scaled_vec)
                if isinstance(shap_vals, list):
                    shap_matrix = shap_vals[0]
                else:
                    shap_matrix = shap_vals
            except Exception as e:
                pass

        # Fallback to feature deviation attribution if SHAP explainer unavailable
        if shap_matrix is None or len(shap_matrix) == 0:
            deviations = np.abs(scaled_vec[0])
            shap_matrix = np.array([deviations])

        sample_shap = shap_matrix[0] if len(shap_matrix.shape) > 1 else shap_matrix

        # 1. Group parameter contributions
        param_contribs: Dict[str, float] = {p: 0.0 for p in PARAMETERS}
        for i, feat_name in enumerate(FEATURE_NAMES):
            if i < len(sample_shap):
                base_p = extract_base_param(feat_name)
                if base_p in param_contribs:
                    param_contribs[base_p] += float(abs(sample_shap[i]))

        total_contrib = sum(param_contribs.values())
        if total_contrib > 1e-6:
            normalized_param_contribs = {
                p: round(float(val / total_contrib), 4) for p, val in param_contribs.items()
            }
        else:
            normalized_param_contribs = {p: round(1.0 / len(PARAMETERS), 4) for p in PARAMETERS}

        # 2. Extract Top-5 features
        ranked_indices = sorted(
            range(min(len(FEATURE_NAMES), len(sample_shap))),
            key=lambda idx: abs(sample_shap[idx]),
            reverse=True
        )[:5]

        top_features = []
        for idx in ranked_indices:
            top_features.append({
                "feature": FEATURE_NAMES[idx],
                "contribution": round(float(sample_shap[idx]), 4),
                "value": round(float(feature_vector[idx]), 4) if idx < len(feature_vector) else 0.0,
            })

        return {
            "top_features": top_features,
            "parameter_contributions": normalized_param_contribs,
        }
