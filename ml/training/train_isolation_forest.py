"""Training script for Isolation Forest model.

Implement:
- Load clean training data from Supabase
- Extract full feature vectors (~110 dims)
- Train sklearn IsolationForest(n_estimators=200, contamination=0.05)
- Save model to ml/models/isolation_forest.pkl
- Save feature scaler to ml/models/if_scaler.pkl
- Log training metrics
"""
