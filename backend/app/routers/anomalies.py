"""Anomaly query endpoints.

Implement:
- GET /anomalies - list with filters (station_id, severity, root_cause, date range, pagination)
- GET /anomalies/{anomaly_score_id} - detail with SHAP values + corrected values

See /docs/HANDOFF.md for response shapes.
"""
