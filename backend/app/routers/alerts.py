"""Alert management endpoints.

Implement:
- GET /alerts - list with filters (station_id, severity, is_resolved, date range, pagination)
- PATCH /alerts/{alert_id}/resolve - mark alert as resolved

See /docs/HANDOFF.md for response shapes.
"""
