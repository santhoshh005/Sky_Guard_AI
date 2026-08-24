"""Autoencoder inference module.

Implement:
- Load trained model, scaler, and threshold from ml/models/
- score(compact_vector) -> float [0, 1]
  Uses: ae_score = min(1.0, mse / threshold_95th_percentile)
- reconstruct(compact_vector) -> reconstructed_vector
  For per-parameter reconstruction error analysis
"""
