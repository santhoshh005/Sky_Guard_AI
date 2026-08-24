"""Training script for Autoencoder model.

Implement:
- Load clean training data from Supabase
- Extract compact feature vectors (14 dims)
- Build autoencoder: 14 -> 8 -> 4 -> 8 -> 14 (symmetric)
- Train with MSE loss, Adam optimizer, 100 epochs
- Compute threshold_95th_percentile on training reconstruction errors
- Save model to ml/models/autoencoder.h5
- Save scaler + threshold to ml/models/ae_scaler.pkl, ml/models/ae_threshold.pkl
"""
