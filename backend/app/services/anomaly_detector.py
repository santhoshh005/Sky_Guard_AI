"""Anomaly detection fusion service.

Implement the 3-channel fusion:
- QC score (deterministic quality checks) - weight 0.35
- IF score (Isolation Forest) - weight 0.30
- AE score (Autoencoder reconstruction error) - weight 0.35

fused_score = 0.35*qc + 0.30*if + 0.35*ae
confidence = 1 - std([qc, if, ae]) / 0.577

See /docs/HANDOFF.md §3 for complete fusion specification.
"""
