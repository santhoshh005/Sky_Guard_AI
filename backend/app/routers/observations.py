"""Observation ingestion endpoints.

Implement:
- POST /observations - single observation ingestion
- POST /observations/batch - batch ingestion

Flow: validate -> store raw -> run QC -> run ML scoring -> store anomaly_score -> check alerts -> push WS
See /docs/HANDOFF.md for request/response shapes.
"""
