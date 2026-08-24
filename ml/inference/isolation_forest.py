"""Isolation Forest inference module.

Implement:
- Load trained model and scaler from ml/models/
- score(feature_vector) -> float [0, 1]
  Uses: if_score = (1 - decision_function) / 2, clamped to [0, 1]
- explain(feature_vector) -> dict of SHAP values
  Uses: shap.TreeExplainer
"""
