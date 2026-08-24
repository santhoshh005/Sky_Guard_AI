"""Root-cause classification service.

Implement rule-based classifier (evaluation order):
1. Communication/Missing - >= 3 params missing or timestamp gap
2. Frozen - frozen_flag + SHAP evidence
3. Spike - spike_flag + delta in top SHAP + <= 2 params affected
4. Drift - rolling mean shift + ae_score > 0.5
5. Multivariate - catch-all for >= 3 params in top SHAP

See /docs/HANDOFF.md §5 for exact decision boundaries.
"""
