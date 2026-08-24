"""WebSocket endpoint for real-time anomaly feed.

Implement:
- WS /ws/live - push anomaly/alert/health events to connected clients
- Support station_id filtering via subscribe message
- Use ConnectionManager pattern for broadcast

See /docs/HANDOFF.md for message format.
"""
