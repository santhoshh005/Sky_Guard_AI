"""Feature engineering service.

Implement:
- Rolling statistics (mean, std, min, max) for 1h, 6h, 24h windows
- Rate of change (delta from previous observation)
- Inter-parameter correlations (temp-humidity, pressure-wind, solar-temp)
- Temporal features (hour_of_day, is_daytime)
- Missingness indicators

Two output vectors:
- Full feature vector (~110 dims) for Isolation Forest
- Compact vector (14 dims: 7 normalized raw + 7 deltas) for Autoencoder

See /docs/HANDOFF.md §2 for complete feature specification.
"""
