"""
Adaptation recommendation scoring.

Weights are provisional prototype calibrations — not derived from
formal multi-criteria decision analysis yet.
"""


def calculate_recommendation_score(
    risk_reduction,
    cost_efficiency,
    robustness,
    evidence,
    feasibility,
    co_benefits,
):
    return (
        0.30 * risk_reduction
        + 0.20 * cost_efficiency
        + 0.15 * robustness
        + 0.15 * evidence
        + 0.10 * feasibility
        + 0.10 * co_benefits
    )