"""Sensor health scoring service.

Implement per-(station, parameter) health tracking:
- Penalty: anomaly=2*(1+0.5*streak), missing=3, drift=5, high_recon=1.5
- Recovery: 0.5 per normal observation
- Time decay: 1.0 per missed interval
- Thresholds: <15=critical, <40=maintenance, <70=degraded, >=70=healthy

See /docs/HANDOFF.md §4 for complete formula.
"""
