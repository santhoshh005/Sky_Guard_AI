"""Deterministic quality check service.

Implement QC flags:
- MISSING: null parameter check
- FROZEN: >= 4 consecutive identical values (exempt rainfall=0)
- RANGE: outside physical bounds (see HANDOFF.md §3 for bounds table)
- SPIKE: |delta| > 5x rolling_std(24h)
- TIMESTAMP: gap > 2x expected_interval

qc_score = min(1.0, sum(flags) / total_checks)

See /docs/HANDOFF.md §3 for complete bounds table and logic.
"""
