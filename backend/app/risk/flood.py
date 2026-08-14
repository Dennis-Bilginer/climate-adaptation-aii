"""
Flood risk scoring module.

Mirrors heat.py's structure. All thresholds are prototype
calibrations for the MVP, not scientifically validated.
"""


def normalize_cloudburst_change(reference_days, future_days):
    """
    Same logic shape as normalize_heatwave_change in heat.py —
    scores the percent increase in cloudburst (skybrud) days.
    """
    if reference_days <= 0:
        return 50

    increase = ((future_days - reference_days) / reference_days) * 100

    if increase <= 0:
        return 0
    elif increase <= 25:
        return 10
    elif increase <= 50:
        return 20
    elif increase <= 100:
        return 40
    elif increase <= 200:
        return 60
    elif increase <= 400:
        return 80
    else:
        return 100


def calculate_flood_exposure(cloudburst_score):
    """
    Single-indicator exposure for now — cloudburst days is our only
    flood indicator so far. Structured as a function (not just the
    raw score) so more precipitation indicators can be weighted in
    later without changing the caller's interface.
    """
    return cloudburst_score


def calculate_building_flood_susceptibility(basement, building_age):
    """
    Flood-specific susceptibility factors differ from heat's —
    a basement is a major flood risk factor, age matters less
    directly than for heat (older drainage infrastructure is more
    of a neighborhood-level factor than a building-level one, but
    we treat pre-1960 buildings as slightly more susceptible here
    as a rough proxy for older, less flood-resilient construction).
    """
    score = 50

    if basement is True:
        score += 25
    elif basement is False:
        score -= 10
    # basement is None (unknown) -> no adjustment, stays at 50

    if building_age < 1960:
        score += 5

    return max(0, min(100, score))


def calculate_flood_protection(has_flood_barriers, has_improved_drainage):
    """
    Placeholder protection factors for flood — mirrors heat's
    calculate_protection shape. Real interventions (e.g. flood
    barriers, sump pumps, improved drainage) will be refined once
    the adaptation library has flood-specific entries.
    """
    protection = 0

    if has_flood_barriers is True:
        protection += 15

    if has_improved_drainage is True:
        protection += 10

    return min(protection, 25)


def calculate_flood_risk(climate_exposure, building_susceptibility, protection):
    base_risk = (
        0.65 * climate_exposure
        + 0.35 * building_susceptibility
    )

    final_risk = base_risk - protection

    return max(0, min(100, final_risk))


def categorize_risk(score):
    """Identical categorization bands to heat.py, kept consistent across hazards."""
    if score < 20:
        return "very_low"
    if score < 40:
        return "low"
    if score < 60:
        return "moderate"
    if score < 80:
        return "high"
    return "very_high"