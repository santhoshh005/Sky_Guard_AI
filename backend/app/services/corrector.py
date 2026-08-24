"""Corrected-value estimation service.

Implement correction methods by root cause:
- Spike: temporal median filter (3 neighbors each side)
- Frozen: linear interpolation or diurnal trend
- Drift: cross-parameter regression
- Communication/Multivariate: no correction (null)

Raw value is ALWAYS preserved.
See /docs/HANDOFF.md §6 for complete specification.
"""
